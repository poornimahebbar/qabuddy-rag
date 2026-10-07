"""QABuddy RAG API entry point.
Run locally:  uvicorn main:app --reload --port 8000  (from backend/)
Vercel loads `app` from this module via pyproject.toml tool.vercel.entrypoint.
"""
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Make `core.*` importable whether launched as backend.main (Vercel) or main (local uvicorn)
_BACKEND_DIR = Path(__file__).resolve().parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from core.config import settings
from core.routes import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[startup] Loading configuration and warming vector store...")
    try:
        from core.vector_store import ensure_collection
        ensure_collection()
        print("[startup] Qdrant collection ready.")
    except Exception as e:
        print(f"[startup] WARNING: vector store warm-up failed: {e}")
    yield


app = FastAPI(
    title="QABuddy RAG API",
    version="2.0.0",
    docs_url="/api/docs",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")

# Serve the built React frontend. On Vercel, `app.frontend()` (patched into FastAPI by
# Vercel's Python runtime) promotes the directory to their CDN; locally we fall back to a
# standard StaticFiles mount. Declared last so API routes take precedence.
# NOTE: hasattr(app, "frontend") is NOT a safe Vercel check — FastAPI >= 0.135 ships an
# unrelated `frontend()` helper that raises when dist/ is missing from the backend CWD.
# Gate strictly on the VERCEL env var instead.
_DIST_DIR = _BACKEND_DIR.parent / "frontend" / "dist"
if _DIST_DIR.is_dir():
    import os as _os

    if _os.environ.get("VERCEL"):
        app.frontend("/", directory="frontend/dist")
    else:
        app.mount("/", StaticFiles(directory=str(_DIST_DIR), html=True), name="frontend")
