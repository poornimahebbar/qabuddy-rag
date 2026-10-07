import { useEffect, useRef, useState } from 'react'
import { uploadCsv } from '../api.js'

const ZONES = [
  {
    key: 'test_case',
    label: 'Upload Test Automation Cases',
    hint: 'Playwright suites, keyword-driven tests (.csv)',
    icon: '🧪',
  },
  {
    key: 'defect',
    label: 'Upload Active Defect Sheets',
    hint: 'Jira defect / bug exports (.csv)',
    icon: '🐞',
  },
]

const BUSY_TEXT = 'Parsing spreadsheet matrix...'

export default function UploadPanel({ onUploaded }) {
  return (
    <div className="upload-grid">
      {ZONES.map((zone) => (
        <Zone key={zone.key} zone={zone} onUploaded={onUploaded} />
      ))}
    </div>
  )
}

function Zone({ zone, onUploaded }) {
  const [status, setStatus] = useState('idle') // idle | uploading | success | error
  const [message, setMessage] = useState('')
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef(null)

  // Success feedback reverts to a clean idle zone after a few seconds.
  useEffect(() => {
    if (status !== 'success') return
    const t = setTimeout(() => {
      setStatus('idle')
      setMessage('')
    }, 5000)
    return () => clearTimeout(t)
  }, [status])

  function handleFiles(fileList) {
    const file = fileList && fileList[0]
    if (!file) return
    if (!file.name.toLowerCase().endsWith('.csv')) {
      setStatus('error')
      setMessage('Only .csv files are accepted.')
      return
    }
    send(file)
  }

  async function send(file) {
    setStatus('uploading')
    setMessage('')
    try {
      const data = await uploadCsv(file, zone.key)
      setStatus('success')
      setMessage(`✓ ${data.records_indexed} records indexed`)
      // Requirement 4: refresh sidebar counters the moment the server confirms.
      if (onUploaded) onUploaded()
    } catch (e) {
      setStatus('error')
      const msg = e && e.message ? e.message : 'Upload failed.'
      setMessage(
        /offline|network|failed to fetch/i.test(msg)
          ? 'Backend offline — check the connection and retry.'
          : msg,
      )
    }
  }

  function onDrop(e) {
    e.preventDefault()
    setDragging(false)
    if (status === 'uploading') return
    handleFiles(e.dataTransfer.files)
  }

  function onKeyDown(e) {
    if (status === 'uploading') return
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      inputRef.current && inputRef.current.click()
    }
  }

  const busy = status === 'uploading'

  return (
    <div
      className={`upload-zone zone-${status} ${dragging ? 'zone-drag' : ''}`}
      role="button"
      tabIndex={0}
      aria-label={zone.label}
      onClick={() => !busy && inputRef.current && inputRef.current.click()}
      onKeyDown={onKeyDown}
      onDragOver={(e) => { e.preventDefault(); if (!busy) setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".csv"
        className="zone-file-input"
        disabled={busy}
        onChange={(e) => {
          handleFiles(e.target.files)
          e.target.value = '' // allow re-selecting the same file
        }}
      />
      <div className="zone-top">
        {busy ? (
          <span className="zone-busy">
            <span className="spinner spinner-sm" />
            <span className="zone-busy-text">{BUSY_TEXT}</span>
          </span>
        ) : (
          <span className="zone-icon">{zone.icon}</span>
        )}
        <span className="zone-label">{zone.label}</span>
      </div>
      {!busy && <div className="zone-hint">{zone.hint}</div>}
      {message && <div className={`zone-msg zone-msg-${status}`}>{message}</div>}
    </div>
  )
}