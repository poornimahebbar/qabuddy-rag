const TYPE_META = {
  jira_defect: { label: 'Jira Defect', cls: 'tag-jira' },
  test_case: { label: 'Test Case', cls: 'tag-tc' },
  automation_spec: { label: 'Automation Spec', cls: 'tag-pw' },
  automation_page: { label: 'Page Object', cls: 'tag-pw' },
  automation_module: { label: 'Module', cls: 'tag-pw' },
  // Legacy doc_types (pre-rename index) render under the new names.
  playwright_spec: { label: 'Automation Spec', cls: 'tag-pw' },
  playwright_page: { label: 'Page Object', cls: 'tag-pw' },
  playwright_module: { label: 'Module', cls: 'tag-pw' },
}

export default function ResultCard({ result, expanded, onToggle }) {
  const meta = TYPE_META[result.doc_type] || { label: result.doc_type, cls: 'tag-tc' }
  const vectorPct = Math.round((result.vector_score || 0) * 100)
  const rerankPct = Math.round((result.rerank_score || 0) * 100)
  const id = `card-${slugify(result.location)}`

  return (
    <article className={`card ${expanded ? 'card-open' : ''}`} id={id}>
      <div className="card-top">
        <div className="card-badges">
          <span className={`tag ${meta.cls}`}>{meta.label}</span>
          {result.priority && <span className="tag tag-prio">{result.priority}</span>}
          {result.category && <span className="tag tag-cat">{result.category}</span>}
          <span className="tag tag-rank">#{result.rank}</span>
        </div>
        <div className="score-group">
          <span className="score" title={`Vector similarity ${vectorPct}%`}>
            vector {vectorPct}%
          </span>
          <span className="score score-rerank" title={`Reranker score ${rerankPct}%`}>
            rerank {rerankPct}%
          </span>
        </div>
      </div>

      <h4 className="card-title">{result.title}</h4>
      <div className="card-source">
        📄 {result.location}
        {result.snippet?.length >= 800 && (
          <button className="link-btn" onClick={onToggle}>
            {expanded ? 'Show less' : 'Show full content'}
          </button>
        )}
      </div>

      <div className="score-bars">
        <div className="bar"><div className="bar-fill" style={{ width: `${vectorPct}%` }} /></div>
        <div className="bar bar-alt"><div className="bar-fill" style={{ width: `${rerankPct}%` }} /></div>
      </div>

      <pre className={`card-snippet ${expanded ? 'snippet-open' : ''}`}>{result.snippet}</pre>
    </article>
  )
}

function slugify(text) {
  return String(text).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')
}
