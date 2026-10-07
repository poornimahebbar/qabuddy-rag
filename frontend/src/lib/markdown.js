export function slugify(text) {
  return String(text).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')
}

function escapeHtml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

/**
 * Minimal markdown renderer with clickable [Source: file - Row N] citations.
 * Citations become <span class="cite" data-cite="..."> so the app can scroll to cards.
 */
export function renderMarkdown(raw) {
  const lines = escapeHtml(raw || '').split('\n')
  const out = []
  let inList = false
  let listType = ''

  const closeList = () => {
    if (inList) {
      out.push(`</${listType}>`)
      inList = false
      listType = ''
    }
  }

  const inline = (text) => {
    let t = text
    t = t.replace(/`([^`]+)`/g, '<code>$1</code>')
    t = t.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    // [Source: xxx - Row N] -> clickable citation chip
    t = t.replace(
      /\[Source:\s*([^\]]+?)\]/g,
      (_, body) => `<span class="cite" data-cite="${escapeHtml(body.trim())}" title="Jump to source">📌 ${escapeHtml(body.trim())}</span>`,
    )
    // standalone (file.csv - Row N) citations
    t = t.replace(
      /\(([^()]*?\.(?:csv|ts)\s*[-–]\s*(?:Row|Test)\s*\d+)\)/g,
      '<span class="cite" data-cite="$1" title="Jump to source">($1)</span>',
    )
    return t
  }

  for (const rawLine of lines) {
    const line = rawLine.trimEnd()
    const h = /^(#{1,4})\s+(.*)$/.exec(line)
    if (h) {
      closeList()
      const level = Math.min(h[1].length + 2, 5)
      out.push(`<h${level}>${inline(h[2])}</h${level}>`)
      continue
    }
    const ul = /^[-*•]\s+(.*)$/.exec(line)
    if (ul) {
      if (!inList || listType !== 'ul') {
        closeList()
        out.push('<ul>')
        inList = true
        listType = 'ul'
      }
      out.push(`<li>${inline(ul[1])}</li>`)
      continue
    }
    const ol = /^\d+[.)]\s+(.*)$/.exec(line)
    if (ol) {
      if (!inList || listType !== 'ol') {
        closeList()
        out.push('<ol>')
        inList = true
        listType = 'ol'
      }
      out.push(`<li>${inline(ol[1])}</li>`)
      continue
    }
    if (line.trim() === '') {
      closeList()
      continue
    }
    closeList()
    out.push(`<p>${inline(line)}</p>`)
  }
  closeList()
  return out.join('\n')
}
