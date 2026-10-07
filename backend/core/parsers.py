"""Source parsers: Wingify CSVs (test cases + Jira defects) and Playwright TypeScript files."""
import csv
import re
from pathlib import Path

from .config import settings
from .vector_store import collection_counts

JIRA_CSV = "Wingify_Login_100_Jira_Test_Cases.csv"
SUITE_CSV = "Wingify_Platform_Test_Suite.csv"


def _fields_to_text(fields: dict) -> str:
    return "\n".join(f"{k}: {v}" for k, v in fields.items() if v)


def _read_csv_rows(path: Path) -> list[tuple[int, dict]]:
    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for idx, row in enumerate(csv.DictReader(f), start=2):
            fields = {
                (k or "").strip(): (v or "").strip()
                for k, v in row.items()
                if k and (v or "").strip()
            }
            if fields:
                rows.append((idx, fields))
    return rows


def parse_jira_csv(path: Path) -> list[dict]:
    """Jira-exported test cases / defects -> doc_type 'jira_defect'."""
    chunks = []
    for idx, fields in _read_csv_rows(path):
        title = fields.get("Summary") or fields.get("Test Case ID") or f"Row {idx}"
        chunks.append({
            "doc_type": "jira_defect",
            "record_id": fields.get("Test Case ID", f"ROW-{idx}"),
            "title": title,
            "priority": fields.get("Priority", ""),
            "category": fields.get("Category", ""),
            "issue_key": fields.get("Test Case ID", ""),
            "source_file": path.name,
            "row": idx,
            "location": f"{path.name} - Row {idx}",
            "text": _fields_to_text(fields),
        })
    return chunks


def parse_suite_csv(path: Path) -> list[dict]:
    """Platform test-suite CSV -> doc_type 'test_case'."""
    chunks = []
    for idx, fields in _read_csv_rows(path):
        title = fields.get("Description") or fields.get("TC Number") or f"Row {idx}"
        chunks.append({
            "doc_type": "test_case",
            "record_id": fields.get("TC Number", f"ROW-{idx}"),
            "title": title[:140],
            "priority": fields.get("Priority", ""),
            "category": fields.get("Type", ""),
            "issue_key": fields.get("TC Number", ""),
            "source_file": path.name,
            "row": idx,
            "location": f"{path.name} - Row {idx}",
            "text": _fields_to_text(fields),
        })
    return chunks


_DESC_RE = re.compile(r"""test\.describe\(\s*['"`]([^'"`]+)['"`]""")
_TEST_RE = re.compile(r"""test\(\s*['"`]([^'"`]+)['"`]""")
_STEP_RE = re.compile(r"""(?:await\s+)?(?:page|[\w]+Module)\.[\w.]+\([^;]*\)""")
_CLASS_RE = re.compile(r"""export\s+class\s+(\w+)""")
_METHOD_RE = re.compile(r"""(?:async\s+)?(\w+)\s*\([^)]*\)\s*(?::\s*[^{]+)?\s*\{""")

_MAX_TEST_BODY_LINES = 25


def _spec_location(spec: Path, tests_dir: Path) -> str:
    rel = spec.relative_to(tests_dir)
    return f"Advance-Playwright-Framework/src/tests/{rel.as_posix()}"


def parse_playwright_specs(tests_dir: Path) -> list[dict]:
    """Playwright .spec.ts files -> doc_type 'playwright_spec' (one chunk per test())."""
    chunks = []
    if not tests_dir.exists():
        return chunks
    for spec in sorted(tests_dir.rglob("*.spec.ts")):
        try:
            source = spec.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        describes = _DESC_RE.findall(source)
        describe = describes[0] if describes else ""
        matches = list(_TEST_RE.finditer(source))
        for i, m in enumerate(matches):
            test_title = m.group(1).strip()
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(source)
            body_lines = [ln.strip() for ln in source[start:end].splitlines() if ln.strip()]
            steps = [s.strip()[:160] for s in _STEP_RE.findall(source[start:end])][:15]
            body_excerpt = "\n".join(body_lines[:_MAX_TEST_BODY_LINES])
            text = "\n".join(filter(None, [
                f"Spec file: {spec.name}",
                f"Describe block: {describe}" if describe else "",
                f"Test: {test_title}",
                "Steps / code excerpt:",
                body_excerpt,
                ("Detected interactions: " + "; ".join(steps)) if steps else "",
            ]))
            chunks.append({
                "doc_type": "playwright_spec",
                "record_id": f"{spec.stem}::{test_title[:60]}",
                "title": f"{describe} > {test_title}" if describe else test_title,
                "priority": "",
                "category": "Playwright E2E",
                "issue_key": "",
                "source_file": _spec_location(spec, tests_dir),
                "row": i + 1,
                "location": f"{spec.name} - Test {i + 1}",
                "text": text,
            })
    return chunks


def parse_playwright_components(comp_dir: Path, doc_type: str, label: str) -> list[dict]:
    """Playwright page-object / module .ts files -> doc_type 'playwright_page'/'playwright_module'."""
    chunks = []
    if not comp_dir.exists():
        return chunks
    src_root = comp_dir.parent  # .../src
    for ts_file in sorted(comp_dir.rglob("*.ts")):
        if ts_file.name == "index.ts":
            continue
        try:
            source = ts_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        classes = _CLASS_RE.findall(source)
        if not classes:
            continue
        methods = []
        for m in _METHOD_RE.finditer(source):
            name = m.group(1)
            if name in ("if", "for", "while", "switch", "catch", "constructor"):
                continue
            if name not in methods:
                methods.append(name)
        text = "\n".join(filter(None, [
            f"{label} file: {ts_file.name}",
            "Classes: " + ", ".join(classes),
            "Methods: " + ", ".join(methods[:40]),
            "Code excerpt:",
            "\n".join(source.splitlines()[:40]),
        ]))
        rel = ts_file.relative_to(src_root)
        chunks.append({
            "doc_type": doc_type,
            "record_id": f"{comp_dir.name}/{ts_file.stem}",
            "title": f"{label}: {', '.join(classes)} ({ts_file.name})",
            "priority": "",
            "category": label,
            "issue_key": "",
            "source_file": f"Advance-Playwright-Framework/src/{rel.as_posix()}",
            "row": 1,
            "location": ts_file.name,
            "text": text,
        })
    return chunks


def parse_uploaded_csv(path: Path, doc_type: str) -> list[dict]:
    """Arbitrary user-uploaded CSV -> chunks. Title heuristics cover common export layouts.

    doc_type: 'test_case' (from the Test Automation zone) or 'jira_defect' (Defect zone)
    so uploaded rows land in the existing sidebar counters and filter chips.
    """
    chunks = []
    if not path.exists():
        return chunks
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        headers = [h for h in (reader.fieldnames or []) if h and h.strip()]
        if not headers:
            return chunks
        for idx, row in enumerate(reader, start=2):
            fields = {
                (k or "").strip(): (v or "").strip()
                for k, v in row.items()
                if k and (v or "").strip()
            }
            if not fields:
                continue
            title = (
                fields.get("Summary")
                or fields.get("Title")
                or fields.get("Test Case Title")
                or fields.get("Defect Title")
                or fields.get("Description")
                or fields.get("Issue key")
                or fields.get("TC Number")
                or next(iter(fields.values()))
            )
            chunks.append({
                "doc_type": doc_type,
                "record_id": fields.get("Test Case ID") or fields.get("Issue key")
                or fields.get("TC Number") or fields.get("ID") or f"UP-{idx}",
                "title": str(title)[:200],
                "priority": fields.get("Priority") or fields.get("Severity") or "",
                "category": fields.get("Category") or fields.get("Type") or "Uploaded",
                "issue_key": fields.get("Issue key") or fields.get("Test Case ID") or "",
                "source_file": f"uploads/{path.parent.name}/{path.name}",
                "row": idx,
                "location": f"{path.name} - Row {idx}",
                "text": _fields_to_text(fields),
            })
    return chunks



def parse_framework_dir(framework_dir: Path, framework_name: str) -> list[dict]:
    """Any cloned framework dir -> playwright_* chunks with a `frameworks/<name>/` prefix.

    Reuses the generic spec/component parsers, then rewrites `source_file` so
    re-pulls deterministically overwrite the same Qdrant points (stable UUIDs).
    """
    chunks: list[dict] = []
    if not framework_dir.exists():
        return chunks
    tests_dir = framework_dir / "src" / "tests"
    if not tests_dir.exists():
        # Fall back: any *.spec.ts anywhere in the clone (minus .git/node_modules).
        specs = [
            p for p in framework_dir.rglob("*.spec.ts")
            if ".git/" not in p.as_posix() and "node_modules" not in p.parts
        ]
        for spec in sorted(specs):
            chunks.extend(_parse_spec_file(spec, framework_dir, framework_name))
    else:
        raw = parse_playwright_specs(tests_dir)
        chunks.extend(_reprefix_framework_chunk(c, framework_dir, framework_name) for c in raw)
    # Pages + modules: prefer src/ layout, else scan whole clone for *page*.ts.
    pages_dir = framework_dir / "src" / "pages"
    modules_dir = framework_dir / "src" / "modules"
    if pages_dir.exists():
        raw = parse_playwright_components(pages_dir, "playwright_page", "Page Object")
        chunks.extend(_reprefix_framework_chunk(c, framework_dir, framework_name) for c in raw)
    if modules_dir.exists():
        raw = parse_playwright_components(modules_dir, "playwright_module", "Module")
        chunks.extend(_reprefix_framework_chunk(c, framework_dir, framework_name) for c in raw)
    if not pages_dir.exists() and not modules_dir.exists():
        for ts in sorted(framework_dir.rglob("*.ts")):
            posix = ts.as_posix()
            if ".git/" in posix or "node_modules" in ts.parts or ts.name == "index.ts":
                continue
            if "page" in ts.name.lower() or "module" in ts.name.lower():
                extra = parse_playwright_components(ts.parent, "playwright_page", "Page Object")
                chunks.extend(
                    _reprefix_framework_chunk(c, framework_dir, framework_name)
                    for c in extra if ts.name in c.get("location", "")
                )
    return chunks


def _reprefix_framework_chunk(chunk: dict, framework_dir: Path, framework_name: str) -> dict:
    """Rewrite a locally-parsed chunk's source_file to the frameworks/<name>/ namespace."""
    out = dict(chunk)
    try:
        # Original source_file looks like Advance-Playwright-Framework/src/... —
        # keep the tail after src/ so locations stay familiar.
        tail = out.get("source_file", "").split("src/", 1)[-1]
        out["source_file"] = f"frameworks/{framework_name}/src/{tail}"
    except Exception:
        out["source_file"] = f"frameworks/{framework_name}/{out.get('source_file', '')}"
    return out


def _parse_spec_file(spec: Path, framework_dir: Path, framework_name: str) -> list[dict]:
    """Parse a single .spec.ts found outside the conventional src/tests layout."""
    try:
        rel = spec.relative_to(framework_dir).as_posix()
    except ValueError:
        rel = spec.name
    fake_tests = framework_dir / "src" / "tests"
    raw = parse_playwright_specs(spec.parent)
    out = []
    for c in raw:
        if spec.name in c.get("location", "") or spec.stem in c.get("record_id", ""):
            c = dict(c)
            c["source_file"] = f"frameworks/{framework_name}/{rel}"
            out.append(c)
    if out:
        return out
    # No test() blocks matched — still index the file itself as one chunk.
    try:
        source = spec.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    return [{
        "doc_type": "playwright_spec",
        "record_id": f"{spec.stem}::file",
        "title": f"{framework_name} > {spec.name}",
        "priority": "",
        "category": "Playwright E2E",
        "issue_key": "",
        "source_file": f"frameworks/{framework_name}/{rel}",
        "row": 1,
        "location": spec.name,
        "text": f"Spec file: {spec.name}\nFramework: {framework_name}\n\n" + "\n".join(source.splitlines()[:60]),
    }]


def file_index_status() -> dict:
    """Inspect local sources and the vector DB index.

    Returns:
        {
            "local": {...},   # sources on disk (framework + uploaded CSVs)
            "database": {"indexed": N, "by_type": {...}},  # what Qdrant holds right now
        }
    """
    local = {
        "playwright_specs": 0,
        "playwright_pages": 0,
        "playwright_modules": 0,
        "uploaded_test_cases": 0,
        "uploaded_defects": 0,
        "frameworks": [],
    }
    if settings.PLAYWRIGHT_TESTS_DIR.exists():
        local["playwright_specs"] = len(list(settings.PLAYWRIGHT_TESTS_DIR.rglob("*.spec.ts")))
    if settings.PLAYWRIGHT_PAGES_DIR.exists():
        local["playwright_pages"] = len(list(settings.PLAYWRIGHT_PAGES_DIR.rglob("*.ts")))
    if settings.PLAYWRIGHT_MODULES_DIR.exists():
        local["playwright_modules"] = len(list(settings.PLAYWRIGHT_MODULES_DIR.rglob("*.ts")))
    for folder, key in (("test_case", "uploaded_test_cases"), ("defect", "uploaded_defects")):
        cat_dir = settings.UPLOAD_DIR / folder
        if cat_dir.exists():
            local[key] = len(list(cat_dir.glob("*.csv")))
    # Cloned frameworks pulled via the UI (data/frameworks/<name>).
    # Import here (not top-level): frameworks.py imports settings only, but this
    # keeps parsers importable even if git tooling changes later.
    try:
        from .frameworks import list_frameworks
        local["frameworks"] = list_frameworks()
    except Exception:
        local["frameworks"] = []

    db = {"indexed": 0, "by_type": {}}
    try:
        counts = collection_counts()
        db["indexed"] = counts.get("total", 0)
        db["by_type"] = counts.get("by_type", {})
    except Exception:
        db = {"indexed": 0, "by_type": {}}

    return {"local": local, "database": db}


def collect_all_chunks() -> list[dict]:
    """Parse every configured source into a unified chunk list."""
    chunks: list[dict] = []
    jira = settings.DATA_DIR / JIRA_CSV
    suite = settings.DATA_DIR / SUITE_CSV
    if jira.exists():
        chunks.extend(parse_jira_csv(jira))
    if suite.exists():
        chunks.extend(parse_suite_csv(suite))
    chunks.extend(parse_playwright_specs(settings.PLAYWRIGHT_TESTS_DIR))
    chunks.extend(parse_playwright_components(settings.PLAYWRIGHT_PAGES_DIR, "playwright_page", "Page Object"))
    chunks.extend(parse_playwright_components(settings.PLAYWRIGHT_MODULES_DIR, "playwright_module", "Module"))
    # User-uploaded CSVs (persists across Full Reindex)
    for folder, doc_type in (("test_case", "test_case"), ("defect", "jira_defect")):
        cat_dir = settings.UPLOAD_DIR / folder
        if cat_dir.exists():
            for csv_path in sorted(cat_dir.glob("*.csv")):
                chunks.extend(parse_uploaded_csv(csv_path, doc_type))
    # Pulled frameworks (data/frameworks/<name>) persist across Full Reindex too.
    if settings.FRAMEWORKS_DIR.exists():
        for fw_dir in sorted(p for p in settings.FRAMEWORKS_DIR.iterdir() if p.is_dir()):
            if (fw_dir / ".git").exists():
                chunks.extend(parse_framework_dir(fw_dir, fw_dir.name))
    return chunks

