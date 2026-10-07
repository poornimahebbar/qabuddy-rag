import { useEffect, useState } from 'react'
import { getFrameworks, pullFramework } from '../api.js'

export default function FrameworkPanel({ onIndexed }) {
  const [repoUrl, setRepoUrl] = useState('')
  const [branch, setBranch] = useState('')
  const [status, setStatus] = useState('idle') // idle | pulling | success | error
  const [message, setMessage] = useState('')
  const [frameworks, setFrameworks] = useState([])

  useEffect(() => {
    let cancelled = false
    getFrameworks()
      .then((d) => { if (!cancelled) setFrameworks(d.frameworks || []) })
      .catch(() => {})
    return () => { cancelled = true }
  }, [])

  async function handlePull(e) {
    e.preventDefault()
    const url = repoUrl.trim()
    if (!url) {
      setStatus('error')
      setMessage('Paste a framework git URL first.')
      return
    }
    setStatus('pulling')
    setMessage('')
    try {
      const data = await pullFramework(url, branch.trim() || undefined)
      setStatus('success')
      const bits = [`${data.records_indexed} chunks indexed`, data.commit ? `@${data.commit}` : '']
        .filter(Boolean).join(' ')
      setMessage(`✓ ${data.framework} — ${bits}`)
      getFrameworks().then((d) => setFrameworks(d.frameworks || [])).catch(() => {})
      if (onIndexed) onIndexed()
    } catch (err) {
      setStatus('error')
      setMessage(err?.message || 'Framework pull failed.')
    }
  }

  const busy = status === 'pulling'

  return (
    <div className="fw-panel">
      <form onSubmit={handlePull}>
        <input
          className="fw-input"
          type="url"
          placeholder="https://github.com/org/playwright-framework.git"
          value={repoUrl}
          onChange={(e) => setRepoUrl(e.target.value)}
          disabled={busy}
          aria-label="Framework git repository URL"
        />
        <div className="fw-row">
          <input
            className="fw-input fw-branch"
            type="text"
            placeholder="branch (optional, default HEAD)"
            value={branch}
            onChange={(e) => setBranch(e.target.value)}
            disabled={busy}
            aria-label="Branch (optional)"
          />
          <button className="btn btn-primary fw-btn" type="submit" disabled={busy}>
            {busy ? 'Pulling…' : 'Pull & Index'}
          </button>
        </div>
      </form>
      {busy && (
        <div className="zone-busy" style={{ marginTop: 8 }}>
          <span className="spinner spinner-sm" />
          <span className="zone-busy-text">Cloning repo, parsing specs…</span>
        </div>
      )}
      {message && <div className={`zone-msg zone-msg-${status}`}>{message}</div>}
      {frameworks.length > 0 && (
        <ul className="fw-list">
          {frameworks.map((f) => (
            <li key={f.name}>
              <span className="fw-name">{f.name}</span>
              <span className="muted">{f.spec_files} specs{f.commit ? ` · @${f.commit}` : ''}</span>
            </li>
          ))}
        </ul>
      )}
      <div className="fw-hint muted">
        Pulls any Playwright repo into the vector DB — then ask “is login already automated?”.
      </div>
    </div>
  )
}
