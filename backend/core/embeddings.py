"""Gemini embeddings via REST with a SQLite disk cache (no Google SDK required)."""
import asyncio
import hashlib
import json
import sqlite3

import httpx

from .config import settings

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
EMBED_URL = f"{GEMINI_BASE}/{settings.EMBEDDING_MODEL}:embedContent"
BATCH_EMBED_URL = f"{GEMINI_BASE}/{settings.EMBEDDING_MODEL}:batchEmbedContents"

_cache_lock = asyncio.Lock()


def _cache_key(text: str) -> str:
    payload = f"{settings.EMBEDDING_MODEL}|{settings.EMBEDDING_DIM}|{text}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _cache_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.CACHE_DB, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS embed_cache (key TEXT PRIMARY KEY, model TEXT, embedding TEXT)"
    )
    return conn


def _cache_get(keys: list[str]) -> dict[str, list[float]]:
    if not keys:
        return {}
    conn = _cache_conn()
    out: dict[str, list[float]] = {}
    for key in keys:
        row = conn.execute("SELECT embedding FROM embed_cache WHERE key = ?", (key,)).fetchone()
        if row:
            out[key] = json.loads(row[0])
    conn.close()
    return out


def _cache_put(items: dict[str, list[float]]) -> None:
    if not items:
        return
    import time as _time
    for attempt in range(5):
        try:
            conn = _cache_conn()
            conn.executemany(
                "INSERT OR REPLACE INTO embed_cache (key, model, embedding) VALUES (?, ?, ?)",
                [(k, settings.EMBEDDING_MODEL, json.dumps(v)) for k, v in items.items()],
            )
            conn.commit()
            conn.close()
            return
        except sqlite3.OperationalError:
            _time.sleep(1.0 * (attempt + 1))
    print(f"[embed-cache] WARNING: failed to write {len(items)} cache entries after retries")


async def _embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts via Gemini batchEmbedContents.
    Handles 429 rate limits with long backoff; callers may split batches on failure."""
    requests = [
        {
            "model": settings.EMBEDDING_MODEL,
            "content": {"parts": [{"text": t}]},
            "output_dimensionality": settings.EMBEDDING_DIM,
        }
        for t in texts
    ]
    async with httpx.AsyncClient(timeout=120) as client:
        last_err: Exception | None = None
        for attempt in range(4):
            try:
                r = await client.post(BATCH_EMBED_URL, headers=_headers(), json={"requests": requests})
                if r.status_code == 429:
                    wait = 15 * (attempt + 1)  # 15s, 30s, 45s, 60s - quota windows are per-minute
                    print(f"[embed] 429 rate limit, waiting {wait}s before retry {attempt + 1}/4")
                    await asyncio.sleep(wait)
                    continue
                r.raise_for_status()
                return [item["values"] for item in r.json()["embeddings"]]
            except (httpx.HTTPError, KeyError) as e:
                last_err = e
                await asyncio.sleep(3 * (attempt + 1))
    raise RuntimeError(f"Gemini batch embedding failed after retries: {last_err}")


async def _embed_resilient(texts: list[str]) -> list[list[float]]:
    """Embed texts, splitting the batch in half if the API keeps rate-limiting."""
    try:
        return await _embed_batch(texts)
    except RuntimeError:
        if len(texts) == 1:
            raise
        mid = len(texts) // 2
        print(f"[embed] splitting batch of {len(texts)} into {mid} + {len(texts) - mid}")
        left = await _embed_resilient(texts[:mid])
        await asyncio.sleep(2)
        right = await _embed_resilient(texts[mid:])
        return left + right


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts, served from cache where possible."""
    keys = [_cache_key(t) for t in texts]
    cached = _cache_get(keys)
    results: list[list[float] | None] = [cached.get(k) for k in keys]
    missing_idx = [i for i, v in enumerate(results) if v is None]
    if missing_idx:
        batch_size = settings.EMBED_BATCH_SIZE
        for start in range(0, len(missing_idx), batch_size):
            group = missing_idx[start:start + batch_size]
            vectors = await _embed_resilient([texts[i] for i in group])
            fresh = {}
            for i, vec in zip(group, vectors):
                results[i] = vec
                fresh[keys[i]] = vec
            async with _cache_lock:
                _cache_put(fresh)
            if start + batch_size < len(missing_idx):
                await asyncio.sleep(1.5)  # gentle pacing between batches
    return [r for r in results if r is not None]


async def embed_query(query: str) -> list[float]:
    """Embed a single query string (uses the same cache + API path)."""
    vectors = await embed_texts([query])
    return vectors[0]

    conn.commit()
    conn.close()


def _headers() -> dict:
    return {"x-goog-api-key": settings.GEMINI_API_KEY}
