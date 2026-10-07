"""Central configuration loaded from the workspace .env file."""
import os
from pathlib import Path

from dotenv import load_dotenv

# Workspace root: C:/D DATA/AI Engineering Projects/RAG_AI_Buddy
WORKSPACE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = WORKSPACE_DIR / ".env"
load_dotenv(ENV_FILE, override=True)

# True when running as a Vercel Function (read-only FS except /tmp)
IS_VERCEL = bool(os.environ.get("VERCEL"))


class Settings:
    # --- LLM (Groq) ---
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", os.getenv("GROQ_MODEL_NAME", "qwen/qwen3.8-27b"))

    # --- Embeddings (Google Gemini) ---
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL_NAME", "models/gemini-embedding-001")
    EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "768"))
    EMBED_BATCH_SIZE: int = int(os.getenv("EMBED_BATCH_SIZE", "16"))

    # --- Reranker (Cohere, with Groq LLM fallback) ---
    COHERE_API_KEY: str = os.getenv("COHERE_API_KEY", "")
    COHERE_RERANK_MODEL: str = os.getenv("COHERE_RERANK_MODEL", "rerank-v3.5")

    # --- Vector store (Qdrant embedded local mode; set QDRANT_URL for server mode) ---
    QDRANT_URL: str = os.getenv("QDRANT_URL", "")
    QDRANT_API_KEY: str = os.getenv("QDRANT_API_KEY", "")
    # Local default: on-disk store. On Vercel without QDRANT_URL: ephemeral /tmp instance.
    QDRANT_PATH: str = os.getenv(
        "QDRANT_PATH",
        str(Path("/tmp/qabuddy/qdrant") if IS_VERCEL else WORKSPACE_DIR / "storage" / "qdrant"),
    )
    COLLECTION_NAME: str = os.getenv("COLLECTION_NAME", "qabuddy_chunks")

    # --- Retrieval ---
    RETRIEVE_TOP_K: int = int(os.getenv("RETRIEVE_TOP_K", "30"))
    RERANK_TOP_N: int = int(os.getenv("RERANK_TOP_N", "20"))
    TOP_K: int = int(os.getenv("TOP_K", "5"))

    # --- Paths (on Vercel, writable state goes to /tmp; data/ is read-only bundle) ---
    DATA_DIR: Path = WORKSPACE_DIR / "data"
    STORAGE_DIR: Path = Path("/tmp/qabuddy") if IS_VERCEL else WORKSPACE_DIR / "storage"
    UPLOAD_DIR: Path = Path("/tmp/qabuddy/uploads") if IS_VERCEL else DATA_DIR / "uploads"
    PLAYWRIGHT_TESTS_DIR: Path = WORKSPACE_DIR / "Advance-Playwright-Framework" / "src" / "tests"
    PLAYWRIGHT_PAGES_DIR: Path = WORKSPACE_DIR / "Advance-Playwright-Framework" / "src" / "pages"
    PLAYWRIGHT_MODULES_DIR: Path = WORKSPACE_DIR / "Advance-Playwright-Framework" / "src" / "modules"
    CACHE_DB: Path = STORAGE_DIR / "cache.sqlite3"

    ALLOWED_ORIGINS: list[str] = ["*"]


settings = Settings()
try:
    settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    print(f"[config] WARNING: cannot create {settings.STORAGE_DIR} (read-only FS); using request-scoped storage.")

if not settings.GROQ_API_KEY:
    print("[config] WARNING: GROQ_API_KEY is not set - LLM answers will fail.")
if not settings.GEMINI_API_KEY:
    print("[config] WARNING: GEMINI_API_KEY is not set - ingestion will fail.")
if not settings.COHERE_API_KEY:
    print("[config] INFO: COHERE_API_KEY not set - reranker will use the Groq fallback.")
