import { CircleCheck, FileText, X } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { api, apiBlob, ApiError } from '../../lib/api'
import '../../requests.css'

/* ------------------------------------------------------------------ types -- */

type Status = 'pending' | 'approved' | 'rejected'

/** One student request, as GET /api/admin/submissions returns it. */
type RequestItem = {
  id: string
  status: Status
  course_code: string | null
  course_name: string | null
  exam_year: number
  exam_type: string
  tags: string | null
  original_filename: string
  file_size_bytes: number
  uploaded_by_name: string | null
  uploaded_by_entry_number: string | null
  created_at: string | null
  reviewed_at: string | null
  rejection_reason: string | null
}

const TABS: { status: Status; label: string }[] = [
  { status: 'pending', label: 'Pending' },
  { status: 'approved', label: 'Approved' },
  { status: 'rejected', label: 'Rejected' },
]

const sizeLabel = (bytes: number) =>
  bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB`

const dateLabel = (iso: string | null) =>
  iso ? new Date(iso).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' }) : '—'

const errorText = (err: unknown) => (err instanceof Error ? err.message : 'Something went wrong. Please try again.')

/* ------------------------------------------------------------------- page -- */

/**
 * Page 6: Manage Request (admin).
 * Students' uploads wait here as "pending". The admin opens one, previews the PDF (held in temporary
 * Supabase Storage), then approves it (the backend copies it to the shared Google Drive and it appears in
 * every student's Search) or rejects it with a reason the student can read.
 */
export default function ManageRequests() {
  const [tab, setTab] = useState<Status>('pending')
  const [items, setItems] = useState<RequestItem[]>([])
  const [pendingCount, setPendingCount] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [reviewing, setReviewing] = useState<RequestItem | null>(null)
  const [toast, setToast] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const rows = await api<RequestItem[]>(`/api/admin/submissions?status=${tab}`)
      setItems(rows)
      if (tab === 'pending') setPendingCount(rows.length)
    } catch (err) {
      setItems([])
      setError(errorText(err))
    } finally {
      setLoading(false)
    }
  }, [tab])

  useEffect(() => {
    void load()
  }, [load])

  // the pending count on its tab, even while another tab is open
  useEffect(() => {
    if (tab === 'pending') return
    api<RequestItem[]>('/api/admin/submissions?status=pending')
      .then((rows) => setPendingCount(rows.length))
      .catch(() => undefined)
  }, [tab])

  useEffect(() => {
    if (!toast) return
    const timer = window.setTimeout(() => setToast(''), 5000)
    return () => window.clearTimeout(timer)
  }, [toast])

  /** Opens an approved paper (it now lives in Google Drive) through the same viewer students use. */
  async function openApproved(item: RequestItem) {
    const tabWindow = window.open('', '_blank')
    if (!tabWindow) return
    try {
      const blob = await apiBlob(`/api/resources/${encodeURIComponent(item.id)}/view`)
      const url = URL.createObjectURL(blob)
      tabWindow.location.href = url
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000)
    } catch (err) {
      tabWindow.close()
      setError(errorText(err))
    }
  }

  function decided(message: string) {
    setReviewing(null)
    setToast(message)
    void load()
  }

  return (
    <div className="st-page">
      {toast && (
        <div className="rq-toast" role="status">
          <CircleCheck size={22} aria-hidden="true" />
          <strong>{toast}</strong>
        </div>
      )}

      <header>
        <h1>Manage Request</h1>
        <p className="st-sub">Review the papers students have uploaded. Approved papers become visible to every student.</p>
      </header>

      <div className="rq-tabs" role="tablist">
        {TABS.map(({ status, label }) => (
          <button
            key={status}
            type="button"
            role="tab"
            aria-selected={tab === status}
            className={`rq-tab${tab === status ? ' rq-tab-active' : ''}`}
            onClick={() => setTab(status)}
          >
            {label}
            {status === 'pending' && pendingCount ? <span className="rq-badge">{pendingCount}</span> : null}
          </button>
        ))}
      </div>

      {error && <p className="rq-error" role="alert">{error}</p>}

      <div className="rq-card">
        {loading ? (
          <p className="rq-empty">Loading…</p>
        ) : items.length === 0 ? (
          <p className="rq-empty">
            {tab === 'pending' ? 'No requests are waiting for review.' : `No ${tab} requests yet.`}
          </p>
        ) : (
          <div className="rq-scroll">
            <table className="rq-table">
              <thead>
                <tr>
                  <th>Paper</th>
                  <th>Course</th>
                  <th>Exam</th>
                  <th>Uploaded by</th>
                  <th>Submitted</th>
                  <th aria-label="Action" />
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <div className="rq-file">
                        <FileText size={20} aria-hidden="true" />
                        <div>
                          <strong>{item.original_filename}</strong>
                          <span>
                            {sizeLabel(item.file_size_bytes)}
                            {item.tags ? ` · ${item.tags}` : ''}
                          </span>
                        </div>
                      </div>
                    </td>
                    <td>
                      <strong>{item.course_code ?? '—'}</strong>
                      <span className="rq-sub">{item.course_name}</span>
                    </td>
                    <td>
                      {item.exam_type} {item.exam_year}
                    </td>
                    <td>
                      <strong>{item.uploaded_by_name ?? '—'}</strong>
                      <span className="rq-sub">{item.uploaded_by_entry_number}</span>
                    </td>
                    <td>{dateLabel(item.created_at)}</td>
                    <td className="rq-action">
                      {item.status === 'pending' && (
                        <button type="button" className="rq-btn rq-btn-primary" onClick={() => setReviewing(item)}>
                          Review
                        </button>
                      )}
                      {item.status === 'approved' && (
                        <button type="button" className="rq-btn rq-btn-outline" onClick={() => void openApproved(item)}>
                          Open
                        </button>
                      )}
                      {item.status === 'rejected' && (
                        <span className="rq-reason" title={item.rejection_reason ?? ''}>
                          {item.rejection_reason}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {reviewing && (
        <ReviewDialog item={reviewing} onClose={() => setReviewing(null)} onDecided={decided} onStale={() => void load()} />
      )}
    </div>
  )
}

/* ----------------------------------------------------------- review dialog -- */

function ReviewDialog({
  item,
  onClose,
  onDecided,
  onStale,
}: {
  item: RequestItem
  onClose: () => void
  onDecided: (message: string) => void
  onStale: () => void
}) {
  const [pdfUrl, setPdfUrl] = useState('')
  const [previewError, setPreviewError] = useState('')
  const [rejecting, setRejecting] = useState(false)
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState<'approve' | 'reject' | null>(null)
  const [error, setError] = useState('')

  // load the PDF held in temporary storage; the admin must be able to see it before approving
  useEffect(() => {
    let url = ''
    let cancelled = false
    apiBlob(`/api/admin/submissions/${encodeURIComponent(item.id)}/file`)
      .then((blob) => {
        if (cancelled) return
        url = URL.createObjectURL(blob)
        setPdfUrl(url)
      })
      .catch((err) => !cancelled && setPreviewError(errorText(err)))
    return () => {
      cancelled = true
      if (url) URL.revokeObjectURL(url)
    }
  }, [item.id])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && !busy && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [busy, onClose])

  async function decide(action: 'approve' | 'reject') {
    if (action === 'reject' && reason.trim().length < 3) {
      setError('Give the student a reason (at least 3 characters).')
      return
    }
    setBusy(action)
    setError('')
    try {
      await api(`/api/admin/submissions/${encodeURIComponent(item.id)}/${action}`, {
        method: 'POST',
        body: action === 'reject' ? { reason: reason.trim() } : undefined,
      })
      onDecided(action === 'approve' ? 'Approved. The paper is now available to all students.' : 'Request rejected.')
    } catch (err) {
      setError(errorText(err))
      // someone else already decided it, or the file is gone: the list is out of date
      if (err instanceof ApiError && (err.status === 409 || err.status === 404)) onStale()
      setBusy(null)
    }
  }

  return (
    <div className="rq-overlay" onMouseDown={(e) => e.target === e.currentTarget && !busy && onClose()}>
      <div className="rq-dialog" role="dialog" aria-modal="true" aria-labelledby="rq-title">
        <header className="rq-dialog-head">
          <div>
            <h2 id="rq-title">
              {item.course_code} · {item.exam_type} {item.exam_year}
            </h2>
            <p>
              {item.original_filename} · {sizeLabel(item.file_size_bytes)} · uploaded by{' '}
              <strong>{item.uploaded_by_name ?? 'unknown'}</strong>
              {item.uploaded_by_entry_number ? ` (${item.uploaded_by_entry_number})` : ''}
              {item.tags ? ` · ${item.tags}` : ''}
            </p>
          </div>
          <button type="button" className="rq-close" onClick={onClose} disabled={busy !== null} aria-label="Close">
            <X size={20} aria-hidden="true" />
          </button>
        </header>

        <div className="rq-preview">
          {pdfUrl ? (
            <iframe title={`Preview of ${item.original_filename}`} src={pdfUrl} />
          ) : previewError ? (
            <p className="rq-preview-msg rq-error">{previewError}</p>
          ) : (
            <p className="rq-preview-msg">Loading preview…</p>
          )}
        </div>

        {error && <p className="rq-error rq-dialog-error" role="alert">{error}</p>}

        <footer className="rq-dialog-foot">
          {rejecting ? (
            <>
              <label className="rq-reason-field">
                <span>Reason shown to the student</span>
                <textarea
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  maxLength={500}
                  rows={2}
                  placeholder="e.g. The scan is unreadable. Please upload a clearer copy."
                  autoFocus
                />
              </label>
              <div className="rq-foot-buttons">
                <button type="button" className="rq-btn rq-btn-outline" onClick={() => setRejecting(false)} disabled={busy !== null}>
                  Back
                </button>
                <button type="button" className="rq-btn rq-btn-danger" onClick={() => void decide('reject')} disabled={busy !== null}>
                  {busy === 'reject' ? 'Rejecting…' : 'Confirm reject'}
                </button>
              </div>
            </>
          ) : (
            <div className="rq-foot-buttons">
              <button type="button" className="rq-btn rq-btn-danger-outline" onClick={() => setRejecting(true)} disabled={busy !== null}>
                Reject
              </button>
              <button
                type="button"
                className="rq-btn rq-btn-primary"
                onClick={() => void decide('approve')}
                disabled={busy !== null || !pdfUrl}
                title={pdfUrl ? undefined : 'The preview has to load before you can approve'}
              >
                {busy === 'approve' ? 'Publishing to Google Drive…' : 'Approve & publish'}
              </button>
            </div>
          )}
        </footer>
      </div>
    </div>
  )
}
