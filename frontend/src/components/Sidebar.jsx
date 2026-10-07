import { useEffect, useState } from 'react'
import UploadPanel from './UploadPanel.jsx'
import FrameworkPanel from './FrameworkPanel.jsx'
import { getFrameworkCheck } from '../api.js'

const TYPE_LABELS = {
  jira_defect: 'Jira Defect',
  test_case: 'Test Case',
  automation_spec: 'Automation Spec',
  automation_page: 'Page Object',
  automation_module: 'Module',
}

export default function Sidebar({ health, sources, ingesting, onIngest, onReindex, onUploadSuccess }) {
  const total = sources?.indexed_points_count ?? 0
  const byType = sources?.by_type || {}
  const status = sources?.status || 'loading'
  const [check, setCheck] = useState(null)

  useEffect(() => {
    let cancelled = false
    getFrameworkCheck()
      .then((d) => { if (!cancelled) setCheck(d) })
      .catch(() => { if (!cancelled) setCheck(null) })
    return () => { cancelled = true }
  }, [total])

  const local = check?.local || {}
  const db = check?.database || {}
  const indexed = db.indexed ?? total
  const localTotal =
    (local.automation_specs ?? local.playwright_specs ?? 0) +
    (local.automation_pages ?? local.playwright_pages ?? 0) +
    (local.automation_modules ?? local.playwright_modules ?? 0) +
    (local.uploaded_test_cases || 0) +
    (local.uploaded_defects || 0)
  const denom = Math.max(localTotal * 3, indexed, 1)
  const progress = Math.min(100, Math.round((indexed / denom) * 100))
  const byTypeDb = db.by_type || {}
  // Transition helper: pre-rename Cloud indexes report playwright_* keys.
  const LEGACY_FALLBACK = {
    automation_spec: 'playwright_spec',
    automation_page: 'playwright_page',
    automation_module: 'playwright_module',
  }
  const fallbackCount = (key) => byType[LEGACY_FALLBACK[key]] ?? 0

  return (
    <aside className="sidebar">
      <div className="side-block">
        <div className="side-title">Workspace Sources</div>
        <div className="total-chip">
          <span className="total-num">{total}</span>
          <span className="muted">indexed chunks</span>
        </div>
        <ul className="source-list">
          {Object.entries(TYPE_LABELS).map(([key, label]) => (
            <li key={key}>
              <span className={`dot dot-${key}`} />
              <span className="src-label">{label}</span>
              <span className="src-count">{byType[key] ?? fallbackCount(key)}</span>
            </li>
          ))}
        </ul>
        <div className={`status-pill ${status === 'synchronized' ? 'ok' : 'warn'}`}>
          {status === 'synchronized' ? 'synchronized' : status === 'empty' ? 'empty' : `${status}`}
        </div>
      </div>

      <div className="side-block">
        <div className="side-title">Test Frameworks (git pull)</div>
        <FrameworkPanel onIndexed={onUploadSuccess} />
      </div>

      <div className="side-block">
        <div className="side-title">Upload Management</div>
        <UploadPanel onUploaded={onUploadSuccess} />
      </div>

      <div className="side-block">
        <div className="side-title">Already Indexed?</div>
        <div className="already-index-panel">
          <div className="already-index-head">
            <div>
              <span className="already-index-label">On disk</span>
              <div className="already-index-count">
                {(local.automation_specs ?? local.playwright_specs ?? '-')} specs / {(local.automation_pages ?? local.playwright_pages ?? '-')} pages / {(local.automation_modules ?? local.playwright_modules ?? '-')} modules
                <br />
                {local.uploaded_test_cases ?? '-'} test-case files / {local.uploaded_defects ?? '-'} defect files
              </div>
            </div>
            <div>
              <span className="already-index-label">In vector DB</span>
              <div className="already-index-count">
                Total: {indexed}
                <br />
                <span className="muted">{byTypeDb.jira_defect || 0} defects / {byTypeDb.test_case || 0} test cases</span>
              </div>
            </div>
          </div>
          <div className="already-index-bar">
            <div className="already-index-fill" style={{ width: `${progress}%` }} />
          </div>
          <div className="already-index-meta">
            {indexed > 0 ? (
              <>Indexed {indexed} chunks ({progress}%) — search above to check for existing tests/methods.</>
            ) : (
              <span className="muted">Nothing indexed yet — pull a framework or upload CSVs.</span>
            )}
          </div>
        </div>
      </div>

      <div className="side-block">
        <div className="side-title">Pipeline</div>
        <div className="pipe-row">
          <span>Embeddings</span>
          <b className={health ? 'ok-text' : 'warn-text'}>{health?.embedding_model || '—'}</b>
        </div>
        <div className="pipe-row">
          <span>LLM</span>
          <b className={health ? 'ok-text' : 'warn-text'}>{health?.llm_model || '—'}</b>
        </div>
        <div className="pipe-row">
          <span>Reranker</span>
          <b className="ok-text">
            {health?.rerank_provider === 'cohere' ? 'Cohere (neural)' : 'Groq LLM (fallback)'}
          </b>
        </div>
        <div className="pipe-row">
          <span>Vector DB</span>
          <b className="ok-text" title={health?.qdrant_host || health?.collection || ''}>
            {health?.vector_store || '—'}
          </b>
        </div>
        <div className="side-actions">
          <button className="btn btn-block" onClick={onIngest} disabled={ingesting}>
            {ingesting ? 'Working…' : 'Re-ingest Sources'}
          </button>
          <button className="btn btn-block btn-ghost" onClick={onReindex} disabled={ingesting}>
            Full Reindex (wipe + rebuild)
          </button>
        </div>
      </div>

      <div className="side-footer muted">
        QABuddy.ai v2.0 — FastAPI + Qdrant + Gemini + Cohere/Groq
      </div>
    </aside>
  )
}
