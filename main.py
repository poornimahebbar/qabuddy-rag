"""Vercel auto-detected Python entrypoint (root main.py).

Vercel loads `app` from this file; it re-exports the real FastAPI app in backend/main.py,
which sets up sys.path so `core.*` imports resolve the same way they do under local uvicorn.
"""
from backend.main import app  # noqa: F401  (Vercel looks up `app` here)
