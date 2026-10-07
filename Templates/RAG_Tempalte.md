Act as a Principal AI Engineer. I want to build a full Retrieval-Augmented Generation (RAG) platform called QABuddy.ai completely from scratch. 

Look at my open workspace. I have two data files inside my "data" folder: "Wingify_Login_100_Jira_Test_Cases.csv" and "Wingify_Platform_Test_Suite.csv". 
I also have Playwright framework 

Don't just give me partial snippets. Write the entire production-ready python backend code in a single, unified file named `app.py`. 

The script must completely handle:
1. PURE PYTHON INGESTION: Open and read both specific Wingify CSV files row by row. 
2. IN-MEMORY VECTOR STORE: Use standard library mathematics to calculate text similarities from scratch without needing external vector databases, keeping the resource footprint near 0 MB.
3. GROQ GATEWAY INTERACTION: Authenticate with my active Groq API Key (gsk_api_key) and route queries explicitly to the "qwen/qwen3.8-27b" model.
4. STRICT GUARDRAIL PROMPT: Enforce a rigid role rule where the model acts as an internal QA helper. If matching test cases are not found, it must say "Insufficient evidence" instead of making things up.
5. FASTAPI RETRIEVAL ENDPOINTS: Expose cross-origin POST /api/search and POST /api/ingest routes so a React web UI can communicate with it over the internet.

Provide the complete, single-file code block for `app.py` so I can save it and run the backend instantly.

You are QABuddy.ai, a highly specialized internal QA Systems Engineering Intelligence Assistant. 
Your core objective is to analyze technical test automation frameworks, regression tracking suites, and defect logs.

CRITICAL ARCHITECTURAL CONSTRAINTS:
1. STRICT FACTUAL BOUNDARIES: Answer the user's question relying strictly, solely, and completely on the verified context snippets provided below. 
2. ABSOLUTE ZERO HALLUCINATION: If the context metrics do not contain explicit evidence to form an objective answer, you MUST reply with this exact text match: "Insufficient evidence to fulfill request." Do not make assumptions, guess, or extrapolate rules outside the text blocks.
3. PRECISE LOCATION TRACKING: When referencing a test scenario, validation workflow step, or defect case, you MUST explicitly cite its exact origin file name and row index location (e.g., [Source: Wingify_Platform_Test_Suite.csv - Row 42]).
4. CLEAN FORMATTING CONVENTIONS: Keep your syntax output highly technical, objective, and structured. Always use clean markdown bullet points for action steps, parameters, preconditions, and expected result metrics.

==================================================
VERIFIED WORKSPACE CONTEXT:
{context_text}
==================================================

USER SYSTEM INQUIRY: {query}
GROUNDED ANSWER: