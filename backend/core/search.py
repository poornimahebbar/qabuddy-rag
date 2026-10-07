"""Retrieval orchestration: embed -> vector search -> rerank -> guarded LLM answer."""
import time

from .config import settings
from .embeddings import embed_query
from .llm import generate_answer
from .reranker import rerank
from .vector_store import search_vectors

DOC_TYPE_LABELS = {
    "jira_defect": "Jira Defect",
    "test_case": "Test Case",
    "automation_spec": "Automation Spec",
    "automation_page": "Automation Page Object",
    "automation_module": "Automation Module",
    # Legacy values (pre-rename index) render under the new names.
    "playwright_spec": "Automation Spec",
    "playwright_page": "Automation Page Object",
    "playwright_module": "Automation Module",
}


async def run_search(query: str, doc_type: str | None = None, top_k: int | None = None) -> dict:
    """Full RAG pipeline. Returns answer + ranked result cards + timings."""
    t0 = time.perf_counter()
    top_k = top_k or settings.TOP_K

    query_vector = await embed_query(query)
    t_embed = time.perf_counter()

    candidates = search_vectors(query_vector, limit=settings.RETRIEVE_TOP_K, doc_type=doc_type)
    t_retrieve = time.perf_counter()

    if not candidates:
        return {
            "answer": "Insufficient evidence to fulfill request.",
            "results": [],
            "rerank_provider": "none",
            "timings_ms": {"embed": 0, "retrieve": 0, "rerank": 0, "llm": 0, "total": 0},
        }

    rerank_inputs = [f"{c['title']}\n{c['text']}" for c in candidates]
    ranked, provider = await rerank(query, rerank_inputs, top_n=settings.RERANK_TOP_N)
    t_rerank = time.perf_counter()

    ordered = []
    for rank, item in enumerate(ranked[:top_k], start=1):
        card = dict(candidates[item["index"]])
        card["rerank_score"] = item["score"]
        card["rank"] = rank
        ordered.append(card)

    context_blocks = []
    for i, card in enumerate(ordered, start=1):
        context_blocks.append(
            f"[Reference {i}]\nLocation: {card['location']}\nTitle: {card['title']}\nContent: {card['text'][:1200]}"
        )
    context_text = "\n\n".join(context_blocks)

    try:
        answer = await generate_answer(context_text, query)
        llm_error = None
    except Exception as e:
        answer = (
            "Insufficient evidence to fulfill request."
            if not context_text
            else f"(LLM generation unavailable: {e})\n\nTop retrieved evidence:\n" + context_text[:1500]
        )
        llm_error = str(e)
    t_llm = time.perf_counter()

    results = []
    for card in ordered:
        results.append({
            "id": f"{card['source_file']}::{card['record_id']}",
            "title": card["title"],
            "doc_type": card["doc_type"],
            "doc_type_label": DOC_TYPE_LABELS.get(card["doc_type"], card["doc_type"]),
            "source_type": card["doc_type"],
            "location": card["location"],
            "source_file": card["source_file"],
            "row": card["row"],
            "priority": card.get("priority", ""),
            "category": card.get("category", ""),
            "snippet": card["text"][:800],
            "vector_score": round(card.get("vector_score", 0.0), 4),
            "rerank_score": round(card.get("rerank_score", 0.0), 4),
            "rank": card["rank"],
        })

    return {
        "answer": answer,
        "results": results,
        "rerank_provider": provider,
        "candidates_considered": len(candidates),
        "llm_error": llm_error,
        "timings_ms": {
            "embed": round((t_embed - t0) * 1000, 1),
            "retrieve": round((t_retrieve - t_embed) * 1000, 1),
            "rerank": round((t_rerank - t_retrieve) * 1000, 1),
            "llm": round((t_llm - t_rerank) * 1000, 1),
            "total": round((t_llm - t0) * 1000, 1),
        },
    }
