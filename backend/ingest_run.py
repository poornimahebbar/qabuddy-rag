"""One-shot ingestion: parse -> embed (cached) -> upsert into Qdrant."""
import asyncio
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.embeddings import embed_texts
from core.parsers import collect_all_chunks
from core.vector_store import collection_counts, ensure_collection, upsert_chunks


async def main() -> None:
    t0 = time.time()
    chunks = collect_all_chunks()
    print("parsed:", len(chunks), dict(Counter(c["doc_type"] for c in chunks)), flush=True)
    ensure_collection()
    vecs = await embed_texts([c["text"] for c in chunks])
    print(f"embedded: {len(vecs)} dim={len(vecs[0])} in {time.time() - t0:.1f}s", flush=True)
    n = upsert_chunks(chunks, vecs)
    print("upserted:", n, flush=True)
    print("counts:", collection_counts(), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
