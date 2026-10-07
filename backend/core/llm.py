"""Groq LLM answer generation with strict QA guardrails and source citations."""
import httpx

from .config import settings

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = (
    "You are QABuddy.ai, a highly specialized internal QA Systems Engineering Intelligence Assistant. "
    "Your core objective is to analyze technical test automation frameworks, regression tracking suites, and defect logs.\n\n"
    "CRITICAL ARCHITECTURAL CONSTRAINTS:\n"
    "1. STRICT FACTUAL BOUNDARIES: Answer the user's question relying strictly, solely, and completely on the "
    "verified context snippets provided below.\n"
    "2. ABSOLUTE ZERO HALLUCINATION: If the context metrics do not contain explicit evidence to form an objective "
    "answer, you MUST reply with this exact text match: \"Insufficient evidence to fulfill request.\" "
    "Do not make assumptions, guess, or extrapolate rules outside the text blocks.\n"
    "3. PRECISE LOCATION TRACKING: When referencing a test scenario, validation workflow step, or defect case, "
    "you MUST explicitly cite its exact origin file name and row index location "
    "(e.g., [Source: Wingify_Platform_Test_Suite.csv - Row 42]).\n"
    "4. CLEAN FORMATTING CONVENTIONS: Keep your syntax output highly technical, objective, and structured. "
    "Always use clean markdown bullet points for action steps, parameters, preconditions, and expected result metrics."
)

USER_TEMPLATE = (
    "==================================================\n"
    "VERIFIED WORKSPACE CONTEXT:\n{context_text}\n"
    "==================================================\n\n"
    "USER SYSTEM INQUIRY: {query}\n"
    "GROUNDED ANSWER:"
)


async def generate_answer(context_text: str, query: str) -> str:
    """Call Groq chat completions with the guardrail prompt. Raises on failure."""
    async with httpx.AsyncClient(timeout=90) as client:
        r = await client.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
            json={
                "model": settings.GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": USER_TEMPLATE.format(context_text=context_text, query=query)},
                ],
                "temperature": 0.0,
                "max_tokens": 1500,
            },
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
