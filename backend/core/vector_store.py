"""Qdrant vector store - embedded local mode by default, server mode via QDRANT_URL."""
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, FieldCondition, Filter, MatchValue, PointStruct, VectorParams

from .config import settings

_client: QdrantClient | None = None


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        if settings.QDRANT_URL:
            kwargs: dict = {"url": settings.QDRANT_URL}
            if settings.QDRANT_API_KEY:
                kwargs["api_key"] = settings.QDRANT_API_KEY
            _client = QdrantClient(**kwargs)
        else:
            _client = QdrantClient(path=settings.QDRANT_PATH)
    return _client


def ensure_collection() -> None:
    client = get_client()
    if not client.collection_exists(settings.COLLECTION_NAME):
        client.create_collection(
            collection_name=settings.COLLECTION_NAME,
            vectors_config=VectorParams(size=settings.EMBEDDING_DIM, distance=Distance.COSINE),
        )


def point_id(record_id: str, source_file: str, row: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{source_file}:{record_id}:{row}"))


def upsert_chunks(chunks: list[dict], vectors: list[list[float]]) -> int:
    client = get_client()
    ensure_collection()
    points = [
        PointStruct(
            id=point_id(c["record_id"], c["source_file"], c["row"]),
            vector=vec,
            payload={
                "record_id": c["record_id"],
                "doc_type": c["doc_type"],
                "title": c["title"],
                "priority": c["priority"],
                "category": c["category"],
                "issue_key": c["issue_key"],
                "source_file": c["source_file"],
                "row": c["row"],
                "location": c["location"],
                "text": c["text"],
            },
        )
        for c, vec in zip(chunks, vectors)
    ]
    client.upsert(collection_name=settings.COLLECTION_NAME, points=points, wait=True)
    return len(points)


def search_vectors(query_vector: list[float], limit: int, doc_type: str | None = None) -> list[dict]:
    client = get_client()
    ensure_collection()
    query_filter = None
    if doc_type and doc_type != "all":
        query_filter = Filter(must=[FieldCondition(key="doc_type", match=MatchValue(value=doc_type))])
    res = client.query_points(
        collection_name=settings.COLLECTION_NAME,
        query=query_vector,
        limit=limit,
        query_filter=query_filter,
        with_payload=True,
    )
    hits = []
    for pt in res.points:
        payload = dict(pt.payload or {})
        payload["vector_score"] = float(pt.score)
        hits.append(payload)
    return hits


def collection_counts() -> dict:
    client = get_client()
    ensure_collection()
    out = {"total": 0, "by_type": {}}
    res = client.count(collection_name=settings.COLLECTION_NAME, exact=True)
    out["total"] = res.count
    for doc_type in ("jira_defect", "test_case", "playwright_spec", "playwright_page", "playwright_module"):
        try:
            r = client.count(
                collection_name=settings.COLLECTION_NAME,
                exact=True,
                count_filter=Filter(must=[FieldCondition(key="doc_type", match=MatchValue(value=doc_type))]),
            )
            out["by_type"][doc_type] = r.count
        except Exception:
            out["by_type"][doc_type] = 0
    return out


def scroll_chunks(doc_type: str | None = None, limit: int = 50) -> list[dict]:
    client = get_client()
    ensure_collection()
    query_filter = None
    if doc_type and doc_type != "all":
        query_filter = Filter(must=[FieldCondition(key="doc_type", match=MatchValue(value=doc_type))])
    points, _ = client.scroll(
        collection_name=settings.COLLECTION_NAME,
        limit=limit,
        query_filter=query_filter,
        with_payload=True,
    )
    return [dict(pt.payload or {}) for pt in points]


def wipe_collection() -> None:
    client = get_client()
    if client.collection_exists(settings.COLLECTION_NAME):
        client.delete_collection(settings.COLLECTION_NAME)
    ensure_collection()


def delete_by_source(source_file: str) -> None:
    """Remove previously indexed points for a source file (clean re-upload replacement)."""
    client = get_client()
    ensure_collection()
    client.delete(
        collection_name=settings.COLLECTION_NAME,
        points_selector=Filter(
            must=[FieldCondition(key="source_file", match=MatchValue(value=source_file))]
        ),
        wait=True,
    )
