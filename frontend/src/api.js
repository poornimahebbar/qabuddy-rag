// API client for the QABuddy RAG backend (proxied through Vite in dev).
const BASE = import.meta.env.VITE_API_URL || ''

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail || detail
    } catch { /* keep statusText */ }
    throw new Error(detail)
  }
  return res.json()
}

export const getHealth = () => request('/api/health')
export const getSources = () => request('/api/sources')
export const ingest = () => request('/api/ingest', { method: 'POST' })
export const reindex = () => request('/api/reindex', { method: 'POST' })
export const search = (payload) =>
  request('/api/search', { method: 'POST', body: JSON.stringify(payload) })

/**
 * Multipart CSV upload. Do NOT set Content-Type manually — the browser must
 * append the multipart boundary itself for FormData bodies.
 */
export async function uploadCsv(file, category) {
  const form = new FormData()
  form.append('category', category)
  form.append('file', file)
  let res
  try {
    res = await fetch(`${BASE}/api/upload`, { method: 'POST', body: form })
  } catch {
    throw new Error('Backend offline — could not reach the upload service.')
  }
  if (!res.ok) {
    let detail = res.statusText || `HTTP ${res.status}`
    try {
      const body = await res.json()
      detail = body.detail || detail
    } catch { /* keep statusText */ }
    throw new Error(detail)
  }
  return res.json()
}
