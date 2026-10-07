<h1 align="center">QABuddy — RAG QA Assistant</h1>
<p align="center">
  <b>Find QA defects, test cases & Playwright specs with AI-powered search</b>
  <br/>
  <img src="https://img.shields.io/badge/frontend-React%20%2F%20Vite-646cff?logo=react&logoColor=white" />
  <img src="https://img.shields.io/badge/backend-FastAPI-009688?logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/vector%20DB-Qdrant%20Cloud-ffd23f?logo=qdrant&logoColor=black" />
  <img src="https://img.shields.io/badge/deploy-Vercel-000000?logo=vercel&logoColor=white" />
</p>

---

## 📌 Overview

QABuddy is a **Retrieval-Augmented Generation (RAG)** application for QA engineering teams. It indexes QA artefacts (Jira defects, test cases, Playwright spec/pages/modules) from uploaded CSV files, then answers natural-language questions over them with citations — surfacing the exact defect/test/spec snippets the answer is grounded in.

- **Frontend**: React + Vite (sidebar upload zones, preference chips, source filters, citation-backed results card)
- **Backend**: FastAPI (CSV ingestion, category whitelist, embedding + re-ranking, citation-composition LLM answer)
- **Vector DB**: Qdrant Cloud (free tier — 1GB RAM / 4GB disk, free forever)
- **Deployment**: Vercel (React frontend served from CDN; FastAPI function handles `/api/*`)

---

## 🚀 Quick Start (local)

### 1. Prerequisites
- Python 3.10+ with a virtualenv
- Node.js 18+ (for the frontend)
- Groq API key (LLM + rerank) and Gemini API key (embeddings) — see `.env.example`

### 2. Backend
```bash
cd backend
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # fill in GROQ_API_KEY, GEMINI_API_KEY, QDRANT_URL, QDRANT_API_KEY (optional)
uvicorn main:app --reload
```

### 3. Frontend
```bash
cd frontend
npm install
npm run dev
```

### 4. Ingest your data
- **Local**: use the interactive ingest script once:
  ```bash
  python ingest_run.py
  ```
- **Production (Vercel)**: use the **CSV upload zones** in the sidebar — the backend parses, validates, embeds and upserts the file, returning citations.

---

## 🏗️ Architecture

```
React (Vite, CDN) ←→ Vercel Function (FastAPI) ←→ Qdrant Cloud
                            │
              ┌─────────────┴─────────────┐
              ▼                         ▼
        CSV parse/validation          Gemini embedding
        (category whitelist, size,    + Groq rerank
         extension)                    │
              ▼                         ▼
        data/uploads/              Vector index
                                   (per-source collections)
```

| Route | Purpose |
|---|---|
| `GET /` | React SPA (served via `backend/main.py`) |
| `GET /api/health` | Service + env check (embedding/LLM/rerank model names, vector-store mode) |
| `GET /api/sources` | Indexed collections + metadata |
| `POST /api/search` | Embed query → retrieve → rerank → answered with citations |
| `GET /api/upload` | Upload zones for CSVs (invoked from the UI) |

**Video demo**: https://youtu.be/WqEg1nB7pEw

---

## ☁️ Deploying to Vercel

1. Push the repo: `git push origin main`
2. `vercel link` → select the project (create if needed) → `vercel deploy --prod`
3. Configure **environment secrets** (click **Settings → Environment Variables**):
   - `GROQ` — Groq API key
   - `GEMINI` — Gemini API key
   - `EMBEDDING` — Gemini embedding model name (default `models/gemini-embedding-001`)
   - `RERANK` — rerank provider (default `groq_llm_fallback`)
   - `QDRANT_URL` — Qdrant Cloud cluster endpoint
   - `QDRANT_API_KEY` — Qdrant Cloud API key
4. Done — `/api/*` routes hit the FastAPI function.

> **Note on Vercel serverless**: the Python compute has no persistent disk. The vector index therefore uses Qdrant Cloud; the `/tmp`-based ephemeral store is only a fallback for when no credentials are configured.

---

## 📦 Project Layout

```
backend/                 # FastAPI app
  main.py                # FastAPI + Vercel static mount (root entrypoint)
  core/                  # config, routes, vector_store, search, ingest pipeline
  ingest_run.py          # Interactive local CSV ingest (prod-safe versions)
frontend/                # React + Vite app
  src/
    api.js               # API client (proxy: /api → FastAPI)
    App.jsx              # App shell: sources, preferences, chat
    components/          # Sidebar, ResultCard, UploadPanel, ...
    lib/                 # markdown rendering helpers
data/                    # QA artefact CSVs (test suites)
```

---

## 🔑 Environment Variables

| Key | Required | Purpose |
|---|---|---|
| `GROQ` | yes | LLM + rerank provider |
| `GEMINI` | yes | Embedding model |
| `EMBEDDING` | no | Gemini embedding model id |
| `RERANK` | no | Rerank provider |
| `QDRANT_URL` | prod | Qdrant Cloud cluster endpoint |
| `QDRANT_API_KEY` | prod | Qdrant Cloud API key |

---

## ✅ Commit Status

Latest commit `1fbee7a` contains the full app + Vercel config. The `Advance-Playwright-Framework/` folder is a **separate nested git repo** and is excluded by `.gitignore` rules in the outer repo.

`git clone https://github.com/poornimahebbar/qabuddy-rag.git && cd qabuddy-rag && code .`
