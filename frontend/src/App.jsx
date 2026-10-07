import { useCallback, useEffect, useRef, useState } from 'react'
import { getHealth, getSources, ingest, reindex, search } from './api.js'
import Sidebar from './components/Sidebar.jsx'
import ResultCard from './components/ResultCard.jsx'
import { renderMarkdown, slugify } from './lib/markdown.js'

const FILTERS = [
  { key: 'all', label: 'All Sources' },
  { key: 'jira_defect', label: 'Jira Defects' },
  { key: 'test_case', label: 'Test Cases' },
  { key: 'playwright_spec', label: 'Playwright Specs' },
  { key: 'playwright_page', label: 'Page Objects' },
  { key: 'playwright_module', label: 'Modules' },
]

const SAMPLE_QUERIES = [
  'How is login validated with invalid credentials?',
  'Which test cases cover the appointment booking flow?',
  'What tests verify SmartCode debugger behavior?',
  'Find all high priority defects related to login',
]

export default function App() {
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState('all')
  const [loading, setLoading] = useState(false)
  const [ingesting, setIngesting] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [health, setHealth] = useState(null)
  const [sources, setSources] = useState(null)
  const [expanded, setExpanded] = useState({})
  const answerRef = useRef(null)

  const refreshSources = useCallback(() => {
    getSources().then(setSources).catch(() => setSources(null))
  }, [])

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth(null))
    refreshSources()
  }, [refreshSources])

  async function runSearch(q = query, docType = filter) {
    const text = (q || '').trim()
    if (!text) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await search({ query: text, doc_type: docType === 'all' ? null : docType })
      setResult(data)
      refreshSources()
    } catch (e) {
      setError(e.message || 'Search failed')
    } finally {
      setLoading(false)
    }
  }

  async function runIngest() {
    setIngesting(true)
    setError(null)
    try {
      await ingest()
      refreshSources()
    } catch (e) {
      setError(e.message || 'Ingestion failed')
    } finally {
      setIngesting(false)
    }
  }

  async function runReindex() {
    setIngesting(true)
    setError(null)
    try {
      await reindex()
      refreshSources()
    } catch (e) {
      setError(e.message || 'Reindex failed')
    } finally {
      setIngesting(false)
    }
  }

  function onCiteClick(location) {
    const target = document.getElementById(`card-${slugify(location)}`)
    if (target) {
      target.scrollIntoView({ behavior: 'smooth', block: 'center' })
      target.classList.add('flash')
      setTimeout(() => target.classList.remove('flash'), 1600)
    }
  }

  return (
    <div className="app">
      <main className="main">
        <header className="hero">
          <h1>QABuddy<span className="accent">.ai</span></h1>
          <p className="tagline">
            Grounded QA intelligence over your Jira defects, test cases and Playwright framework —
            with vector search, neural reranking and zero-hallucination answers.
          </p>
        </header>

        <div className="search-box">
          <div className="filters">
            {FILTERS.map((f) => (
              <button
                key={f.key}
                className={`chip ${filter === f.key ? 'chip-active' : ''}`}
                onClick={() => { setFilter(f.key); if (result) runSearch(query, f.key) }}
              >
                {f.label}
              </button>
            ))}
          </div>
          <div className="search-row">
            <input
              className="search-input"
              placeholder="Ask about defects, test steps, locators, coverage..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && runSearch()}
            />
            <button className="btn btn-primary" onClick={() => runSearch()} disabled={loading}>
              {loading ? 'Searching…' : 'Search'}
            </button>
          </div>
          {!result && !loading && (
            <div className="samples">
              {SAMPLE_QUERIES.map((s) => (
                <button key={s} className="sample" onClick={() => { setQuery(s); runSearch(s) }}>{s}</button>
              ))}
            </div>
          )}
        </div>

        {error && <div className="banner banner-error">{error}</div>}

        {loading && (
          <div className="panel loading-panel">
            <div className="spinner" />
            <div>
              <strong>Running the RAG pipeline…</strong>
              <div className="muted">Embedding query → Qdrant vector search → reranker → grounded LLM answer</div>
            </div>
          </div>
        )}

        {result && !loading && (
          <>
            <section className="panel answer-panel" ref={answerRef}>
              <div className="panel-head">
                <h2>Grounded Answer</h2>
                <div className="meta-row">
                  <span className="badge badge-provider">rerank: {result.rerank_provider}</span>
                  <span className="badge">{result.candidates_considered} candidates</span>
                  <span className="badge">{result.timings_ms?.total} ms</span>
                </div>
              </div>
              <div
                className="answer-body"
                onClick={(e) => { if (e.target.dataset.cite) onCiteClick(e.target.dataset.cite) }}
                dangerouslySetInnerHTML={{ __html: renderMarkdown(result.answer || '') }}
              />
            </section>

            <section className="results">
              <h3 className="results-title">Retrieved Evidence <span className="muted">({result.results.length})</span></h3>
              {result.results.length === 0 && <div className="panel muted">No matching evidence found in the index.</div>}
              {result.results.map((r) => (
                <ResultCard
                  key={r.id}
                  result={r}
                  expanded={!!expanded[r.id]}
                  onToggle={() => setExpanded((p) => ({ ...p, [r.id]: !p[r.id] }))}
                />
              ))}
            </section>
          </>
        )}
      </main>
      <Sidebar
        health={health}
        sources={sources}
        ingesting={ingesting}
        onIngest={runIngest}
        onReindex={runReindex}
        onUploadSuccess={refreshSources}
      />
    </div>
  )
}

