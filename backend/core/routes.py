"""QABuddy RAG API routes."""
from __future__ import annotations

import asyncio
import re
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from .config import settings
from .embeddings import embed_texts
from .frameworks import clone_or_pull, list_frameworks
from .parsers import collect_all_chunks, file_index_status, parse_framework_dir, parse_uploaded_csv
from .search import run_search
from .vector_store import collection_counts, delete_by_source, scroll_chunks, upsert_chunks, wipe_collection

router = APIRouter()
api_router = router

_ingest_lock = asyncio.Lock()
_last_ingest: dict = {"status": "never_run", "chunks": 0, "by_type": {}}

ALLOWED_UPLOAD_CATEGORIES = {"test_case", "defect"}
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

# On Vercel the bundle's source CSVs must not be re-ingested by these endpoints
# (read-only FS, cold-cache rate limits). Production data flows: Qdrant Cloud (seeded
# locally) + /api/upload for new CSVs. UI gets a clean 400 if buttons are used there.
IS_VERCEL = bool(__import__("os").environ.get("VERCEL"))
_PROD_BLOCKED_MSG = (
    "Bulk ingest/reindex runs from the local seeding pipeline in production. "
    "Use the sidebar upload zones to add CSV data."
)


class SearchPayload(BaseModel):
    query: str
    doc_type: str | None = Field(default=None, description="jira_defect | test_case | playwright_spec | ...")
    top_k: int | None = Field(default=None, ge=1, le=20)


@router.get("/health")
async def operational_health_status():
    qdrant_url = (settings.QDRANT_URL or "").strip()
    if not qdrant_url:
        vector_store = "Qdrant Local (embedded)"
    elif "cloud.qdrant.io" in qdrant_url:
        vector_store = "Qdrant Cloud"
    else:
        vector_store = "qdrant_server"
    try:
        host = qdrant_url.split("://", 1)[1].split("/", 1)[0] if "://" in qdrant_url else ""
    except Exception:
        host = ""
    return {
        "status": "healthy",
        "service": "QABuddy RAG API",
        "embedding_model": settings.EMBEDDING_MODEL,
        "llm_model": settings.GROQ_MODEL,
        "rerank_provider": "cohere" if settings.COHERE_API_KEY else "groq_llm_fallback",
        "vector_store": vector_store,
        "qdrant_host": host,
        "collection": settings.COLLECTION_NAME,
    }


@router.get("/sources")
async def fetch_workspace_sources():
    counts = collection_counts()
    return {
        "indexed_points_count": counts["total"],
        "by_type": counts["by_type"],
        "last_ingest": _last_ingest,
        "status": "synchronized" if counts["total"] else "empty",
    }


@router.post("/ingest")
async def trigger_workspace_ingestion():
    """Parse all sources, embed (cached), and upsert into Qdrant."""
    if IS_VERCEL:
        raise HTTPException(status_code=400, detail=_PROD_BLOCKED_MSG)
    async with _ingest_lock:
        global _last_ingest
        try:
            chunks = collect_all_chunks()
            if not chunks:
                return {"status": "success", "processed_documents": 0, "note": "No source files found."}
            vectors = await embed_texts([c["text"] for c in chunks])
            written = upsert_chunks(chunks, vectors)
            by_type: dict[str, int] = {}
            for c in chunks:
                by_type[c["doc_type"]] = by_type.get(c["doc_type"], 0) + 1
            _last_ingest = {"status": "success", "chunks": written, "by_type": by_type}
            return {"status": "success", "processed_documents": written, "by_type": by_type}
        except Exception as e:
            _last_ingest = {"status": "failed", "error": str(e)}
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")


@router.post("/search")
async def run_rag_search(payload: SearchPayload):
    try:
        return await run_search(payload.query, doc_type=payload.doc_type, top_k=payload.top_k)
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Search pipeline failed: {e}")


@router.get("/chunks")
async def browse_chunks(doc_type: str | None = None, limit: int = 50):
    return {"chunks": scroll_chunks(doc_type=doc_type, limit=min(limit, 200))}


@router.post("/reindex")
async def reindex():
    """Wipe the collection and re-ingest from scratch."""
    if IS_VERCEL:
        raise HTTPException(status_code=400, detail=_PROD_BLOCKED_MSG)
    wipe_collection()
    return await trigger_workspace_ingestion()



@router.get("/framework-check")
async def check_workspace_sources() -> dict:
    """Report what already exists on disk and in the vector DB.

    Used by the UI so a user can see, before ingesting, which test cases or
    defect rows are already indexed (and whether they match a file they are
    about to upload).
    """
    return file_index_status()


class FrameworkPullPayload(BaseModel):
    repo_url: str = Field(..., description="https:// git URL of the test-automation framework")
    branch: str | None = Field(default=None, description="Optional branch to clone/pull")


@router.get("/frameworks")
async def list_indexed_frameworks() -> dict:
    """Frameworks on disk (cloned via /api/frameworks/pull) with HEAD commits."""
    return {"frameworks": list_frameworks()}


@router.post("/frameworks/pull")
async def pull_framework(payload: FrameworkPullPayload):
    """Clone (first time) or pull (later) a framework repo, then index it into Qdrant.

    Body: {"repo_url": "https://github.com/org/framework.git", "branch": "main" (optional)}.

    Each spec test() becomes a `playwright_spec` chunk; page objects / modules
    become `playwright_page` / `playwright_module` chunks — all namespaced as
    `frameworks/<name>/...` so re-pulls overwrite the same points and anyone can
    search "is login already automated?" style questions. CSV test-case and defect
    zones are untouched.
    """
    if IS_VERCEL:
        raise HTTPException(
            status_code=400,
            detail="Framework pull needs a writable git checkout — run it locally. "
            "Production search still covers whatever was seeded into Qdrant Cloud.",
        )
    try:
        info = await asyncio.to_thread(
            clone_or_pull, payload.repo_url, payload.branch or ""
        )
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    async with _ingest_lock:
        try:
            chunks = await asyncio.to_thread(
                parse_framework_dir, info["framework_dir"], info["framework_name"]
            )
            if not chunks:
                return {
                    "status": "success",
                    "framework": info["framework_name"],
                    "commit": info["commit"],
                    "fresh_clone": info["fresh_clone"],
                    "records_indexed": 0,
                    "note": "Cloned OK but no .spec.ts / page-object .ts files found.",
                }
            vectors = await embed_texts([c["text"] for c in chunks])
            indexed = upsert_chunks(chunks, vectors)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Framework indexing failed: {e}")

    by_type: dict[str, int] = {}
    for c in chunks:
        by_type[c["doc_type"]] = by_type.get(c["doc_type"], 0) + 1
    return {
        "status": "success",
        "message": "Framework pulled and indexed.",
        "framework": info["framework_name"],
        "commit": info["commit"],
        "fresh_clone": info["fresh_clone"],
        "records_indexed": indexed,
        "by_type": by_type,
        "sources": collection_counts(),
    }


@router.post("/upload")
async def upload_spreadsheet(
    category: str = Form(..., description="test_case | defect"),
    file: UploadFile = File(...),
):
    """Accept a CSV upload, index it into Qdrant, and return a confirmation payload.

    Multipart form fields:
      - category: 'test_case' (Test Automation zone) or 'defect' (Active Defect zone)
      - file:     .csv spreadsheet
    """
    # 1. Category whitelist
    if category not in ALLOWED_UPLOAD_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category '{category}'. Expected one of: {sorted(ALLOWED_UPLOAD_CATEGORIES)}",
        )

    # 2. Extension + size validation
    filename = Path(file.filename or "").name  # strip any path components
    if not filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are accepted.")
    if not filename:
        raise HTTPException(status_code=400, detail="Missing filename.")

    # 3. Read and size-check
    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the 10 MB upload limit.")

    # 4. Persist to data/uploads/<category>/ so Full Reindex keeps it
    dest_dir = settings.UPLOAD_DIR / category
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _SAFE_NAME_RE.sub("_", filename)
    dest_path = dest_dir / safe_name
    dest_path.write_bytes(payload)

    # 5. Parse rows -> chunks
    doc_type = "test_case" if category == "test_case" else "jira_defect"
    try:
        chunks = parse_uploaded_csv(dest_path, doc_type)
    except Exception as e:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"CSV parsing failed: {e}")
    if not chunks:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="No data rows found in the CSV.")

    # 6. Embed (disk-cached) + upsert into Qdrant (replace prior copy of same file)
    source_label = f"uploads/{category}/{safe_name}"
    async with _ingest_lock:
        try:
            delete_by_source(source_label)
            vectors = await embed_texts([c["text"] for c in chunks])
            indexed = upsert_chunks(chunks, vectors)
        except Exception as e:
            dest_path.unlink(missing_ok=True)
            raise HTTPException(status_code=500, detail=f"Indexing failed: {e}")

    return {
        "status": "success",
        "message": "Spreadsheet indexed.",
        "category": category,
        "doc_type": doc_type,
        "filename": safe_name,
        "records_indexed": indexed,
        "sources": collection_counts(),
    }
