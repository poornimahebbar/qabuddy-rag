"""Clone / pull test-automation framework repos and index them into Qdrant."""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from .config import settings

# Only plain https/http git URLs — no file://, ssh://, or shell metachars.
_GIT_URL_RE = re.compile(r"^https?://[A-Za-z0-9._\-/:~%#?&=+]+$")
_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")

MAX_FRAMEWORKS = 10  # disk-safety cap for locally cloned frameworks


def _check_git_available() -> None:
    if shutil.which("git") is None:
        raise RuntimeError(
            "git binary not found on the server. Install git to use framework pull."
        )


def validate_repo_url(repo_url: str) -> str:
    url = (repo_url or "").strip()
    if not url:
        raise ValueError("Repository URL is required.")
    if len(url) > 500:
        raise ValueError("Repository URL is too long.")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("Only https:// (or http://) git URLs are accepted.")
    if not _GIT_URL_RE.match(url):
        raise ValueError("Repository URL contains unsupported characters.")
    return url


def derive_framework_name(repo_url: str) -> str:
    tail = urlparse(repo_url).path.rstrip("/").rsplit("/", 1)[-1]
    if tail.endswith(".git"):
        tail = tail[:-4]
    name = _NAME_RE.sub("-", tail).strip("-") or "framework"
    return name[:60]


def _run_git(args: list[str], cwd: Path | None = None) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "git command failed").strip()[-800:]
        raise RuntimeError(f"git {' '.join(args[:2])} failed: {err}")
    return proc.stdout


def clone_or_pull(repo_url: str, branch: str = "") -> dict:
    """Clone the repo on first pull, `git pull` on subsequent pulls.

    Returns {"framework_name", "framework_dir", "fresh_clone", "commit"}.
    """
    _check_git_available()
    url = validate_repo_url(repo_url)
    branch = (branch or "").strip()
    if branch and not re.fullmatch(r"[A-Za-z0-9._\-/]+", branch):
        raise ValueError("Invalid branch name.")

    settings.FRAMEWORKS_DIR.mkdir(parents=True, exist_ok=True)
    name = derive_framework_name(url)
    dest = settings.FRAMEWORKS_DIR / name

    if dest.exists() and not (dest / ".git").exists():
        raise RuntimeError(
            f"'{name}' exists but is not a git checkout. Remove it manually and retry."
        )
    if not dest.exists():
        existing = [p for p in settings.FRAMEWORKS_DIR.iterdir() if p.is_dir()]
        if len(existing) >= MAX_FRAMEWORKS:
            raise RuntimeError(
                f"Framework limit reached ({MAX_FRAMEWORKS}). Remove an old framework first."
            )
        args = ["clone", "--depth", "1"]
        if branch:
            args += ["--branch", branch]
        args += [url, str(dest)]
        _run_git(args)
        fresh_clone = True
    else:
        _run_git(["fetch", "origin"], cwd=dest)
        # Fast-forward the current branch; fall back to default branch pull.
        try:
            _run_git(["pull", "--ff-only"], cwd=dest)
        except RuntimeError:
            _run_git(["pull", "--ff-only", "origin", branch] if branch else ["pull", "--ff-only"], cwd=dest)
        fresh_clone = False

    try:
        commit = _run_git(["rev-parse", "--short", "HEAD"], cwd=dest).strip()
    except RuntimeError:
        commit = ""
    return {
        "framework_name": name,
        "framework_dir": dest,
        "fresh_clone": fresh_clone,
        "commit": commit,
    }


def list_frameworks() -> list[dict]:
    """Frameworks currently on disk with their HEAD commit."""
    out = []
    if not settings.FRAMEWORKS_DIR.exists():
        return out
    for child in sorted(settings.FRAMEWORKS_DIR.iterdir()):
        if not child.is_dir() or not (child / ".git").exists():
            continue
        try:
            commit = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=str(child),
                capture_output=True,
                text=True,
                timeout=15,
            ).stdout.strip()
        except Exception:
            commit = ""
        spec_count = len([
            p for p in child.rglob("*.spec.ts")
            if ".git/" not in p.as_posix() and "node_modules" not in p.parts
        ])
        out.append({"name": child.name, "commit": commit, "spec_files": spec_count})
    return out
