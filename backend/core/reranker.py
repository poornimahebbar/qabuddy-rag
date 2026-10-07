"""Reranker: Cohere Rerank v2 primary, Groq LLM rerank fallback, vector order last resort."""
import json
import re

import httpx

from .config import settings

COHERE_URL = "https://api.cohere.com/v2/rerank"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


async def _cohere_rerank(query: str, documents: list[str], top_n: int) -> list[dict] | None:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            COHERE_URL,
            headers={"Authorization": f"Bearer {settings.COHERE_API_KEY}"},
            json={
                "model": settings.COHERE_RERANK_MODEL,
                "query": query,
                "documents": documents,
                "top_n": top_n,
            },
        )
        if r.status_code != 200:
            print(f"[rerank] Cohere returned {r.status_code}: {r.text[:200]}")
            return None
        results = r.json().get("results", [])
        return [
            {"index": int(item["index"]), "score": float(item.get("relevance_score", 0.0))}
            for item in results
        ]


async def _groq_rerank(query: str, documents: list[str], top_n: int) -> list[dict] | None:
    """LLM-based rerank: ask Groq to order document indices by relevance."""
    numbered = "\n\n".join(f"[{i}] {d[:600]}" for i, d in enumerate(documents))
    prompt = (
        "Rank the documents below by relevance to the query, most relevant first.\n"
        "Return ONLY a JSON array of document indices, e.g. [3,0,2,1]. No prose.\n\n"
        f"QUERY: {query}\n\nDOCUMENTS:\n{numbered}"
    )
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
            json={
                "model": settings.GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "max_tokens": 400,
            },
        )
        if r.status_code != 200:
            print(f"[rerank] Groq rerank returned {r.status_code}: {r.text[:200]}")
            return None
        content = r.json()["choices"][0]["message"]["content"]
        match = re.search(r"\[[\d,\s]+\]", content)
        if not match:
            return None
        order = json.loads(match.group(0))
        n = len(documents)
        return [
            {"index": int(idx), "score": round((n - rank) / n, 4)}
            for rank, idx in enumerate(order)
            if isinstance(idx, int) and 0 <= idx < n
        ][:top_n]


async def rerank(query: str, documents: list[str], top_n: int) -> tuple[list[dict], str]:
    """Return ([{index, score}, ...], provider_name). Never raises."""
    if not documents:
        return [], "none"
    capped = documents[: max(top_n * 3, 20)]
    if settings.COHERE_API_KEY:
        try:
            out = await _cohere_rerank(query, capped, top_n)
            if out:
                return out, "cohere"
        except httpx.HTTPError as e:
            print(f"[rerank] Cohere error, falling back: {e}")
    try:
        out = await _groq_rerank(query, capped, top_n)
        if out:
            return out, "groq_llm"
    except httpx.HTTPError as e:
        print(f"[rerank] Groq rerank error, using vector order: {e}")
    return [{"index": i, "score": 0.0} for i in range(min(top_n, len(capped)))], "vector_only"
