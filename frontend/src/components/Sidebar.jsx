import UploadPanel from './UploadPanel.jsx'

const TYPE_LABELS = {
  jira_defect: 'Jira Defect',
  test_case: 'Test Case',
  playwright_spec: 'Playwright Spec',
  playwright_page: 'Page Object',
  playwright_module: 'Module',
}

export default function Sidebar({ health, sources, ingesting, onIngest, onReindex, onUploadSuccess }) {
  const total = sources?.indexed_points_count ?? 0
  const byType = sources?.by_type || {}
  const status = sources?.status || 'loading'

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
              <span className="src-count">{byType[key] ?? 0}</span>
            </li>
          ))}
        </ul>
        <div className={`status-pill ${status === 'synchronized' ? 'ok' : 'warn'}`}>
          {status === 'synchronized' ? '● synchronized' : status === 'empty' ? '○ empty' : `○ ${status}`}
        </div>
      </div>

      <div className="side-block">
        <div className="side-title">Upload Management</div>
        <UploadPanel onUploaded={onUploadSuccess} />
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
          <b className="ok-text">{health?.vector_store || '—'}</b>
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

      <div className="side-block side-footer muted">
        QABuddy.ai v2.0 — FastAPI · Qdrant · Gemini · Cohere/Groq
      </div>
    </aside>
  )
}
