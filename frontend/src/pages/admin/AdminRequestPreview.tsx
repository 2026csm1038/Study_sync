import { ArrowLeft, CheckCircle, FileText, XCircle } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, apiBlob, ApiError } from '../../lib/api'
import '../../requests.css'

type Status = 'pending' | 'approved' | 'rejected'
type RequestItem = {
  id: string; status: Status; course_id: string; course_code: string | null; course_name: string | null
  exam_year: number; exam_type: string; tags: string | null; original_filename: string; file_size_bytes: number
  uploaded_by_name: string | null; uploaded_by_entry_number: string | null; created_at: string | null
  reviewed_at: string | null; rejection_reason: string | null
}
const statuses: Status[] = ['pending', 'approved', 'rejected']
const sizeLabel = (bytes: number) => bytes < 1024 * 1024
  ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB`
const dateLabel = (iso: string | null) => iso
  ? new Date(iso).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' }) : '—'
const errorText = (err: unknown) => err instanceof Error ? err.message : 'Something went wrong. Please try again.'

export default function AdminRequestPreview() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const [item, setItem] = useState<RequestItem | null>(null)
  const [pdfUrl, setPdfUrl] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState<'approve' | 'reject' | null>(null)
  const [reason, setReason] = useState('')
  const [showReject, setShowReject] = useState(false)
  const [toast, setToast] = useState('')

  const loadItem = useCallback(async () => {
    setLoading(true); setError('')
    try {
      let found: RequestItem | undefined
      for (const status of statuses) {
        const rows = await api<RequestItem[]>(`/api/admin/submissions?status=${status}`)
        found = rows.find((row) => row.id === id)
        if (found) break
      }
      if (!found) throw new Error('This request could not be found. It may have been removed or reviewed in another session.')
      setItem(found)
    } catch (err) { setError(errorText(err)) }
    finally { setLoading(false) }
  }, [id])

  useEffect(() => { void loadItem() }, [loadItem])
  useEffect(() => {
    if (!item) return
    let cancelled = false
    let objectUrl = ''
    setPdfUrl('')
    if (item.status === 'rejected') return
    const endpoint = item.status === 'pending'
      ? `/api/admin/submissions/${encodeURIComponent(item.id)}/file`
      : `/api/resources/${encodeURIComponent(item.id)}/view`
    apiBlob(endpoint).then((blob) => {
      if (cancelled) return
      objectUrl = URL.createObjectURL(blob); setPdfUrl(objectUrl)
    }).catch((err) => { if (!cancelled) setError(`Could not load PDF preview: ${errorText(err)}`) })
    return () => { cancelled = true; if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [item])

  async function decide(action: 'approve' | 'reject') {
    if (!item) return
    if (action === 'reject' && reason.trim().length < 3) { setError('Enter a rejection reason of at least 3 characters.'); return }
    setBusy(action); setError('')
    try {
      await api(`/api/admin/submissions/${encodeURIComponent(item.id)}/${action}`, {
        method: 'POST', body: action === 'reject' ? { reason: reason.trim() } : undefined,
      })
      setToast(action === 'approve' ? 'Request approved and published to Google Drive.' : 'Request rejected.')
      window.setTimeout(() => navigate('/admin/requests', { replace: true }), 900)
    } catch (err) {
      setError(errorText(err))
      if (err instanceof ApiError && (err.status === 404 || err.status === 409)) void loadItem()
    } finally { setBusy(null) }
  }

  return <div className="st-page rq-detail-page">
    <Link to="/admin/requests" className="rq-back"><ArrowLeft size={18} /> Back to Manage Requests</Link>
    <header className="rq-detail-title"><h1>Preview Request</h1><p className="st-sub">Review the details submitted by the student and inspect the PDF before deciding.</p></header>
    {toast && <p className="rq-success" role="status">{toast}</p>}
    {error && <p className="rq-error" role="alert">{error}</p>}
    {loading ? <div className="rq-card"><p className="rq-empty">Loading request details…</p></div> : item ? <>
      <section className="rq-detail-card" aria-labelledby="rq-info-heading">
        <h2 id="rq-info-heading"><FileText size={19} /> Resource Information</h2>
        <div className="rq-detail-grid">
          <div><span>File name</span><strong>{item.original_filename}</strong></div>
          <div><span>Course name</span><strong>{item.course_name ?? '—'}</strong></div>
          <div><span>Course code</span><strong>{item.course_code ?? '—'}</strong></div>
          <div><span>Resource type</span><strong>{item.exam_type}</strong></div>
          <div><span>Year</span><strong>{item.exam_year}</strong></div>
          <div><span>Topic / Tags</span><strong>{item.tags?.trim() || '—'}</strong></div>
          <div><span>Uploaded by</span><strong>{item.uploaded_by_name ?? '—'}</strong></div>
          <div><span>Entry number</span><strong>{item.uploaded_by_entry_number ?? '—'}</strong></div>
          <div><span>File size</span><strong>{sizeLabel(item.file_size_bytes)}</strong></div>
          <div><span>Submitted on</span><strong>{dateLabel(item.created_at)}</strong></div>
          <div><span>Status</span><strong className={`rq-status rq-status-${item.status}`}>{item.status[0].toUpperCase() + item.status.slice(1)}</strong></div>
          {item.rejection_reason && <div className="rq-detail-wide"><span>Rejection reason</span><strong>{item.rejection_reason}</strong></div>}
        </div>
      </section>
      <section className="rq-detail-card rq-pdf-card" aria-labelledby="rq-pdf-heading">
        <h2 id="rq-pdf-heading"><FileText size={19} /> PDF Preview</h2>
        <div className="rq-pdf-viewer">
          {pdfUrl ? <iframe title={`PDF preview: ${item.original_filename}`} src={pdfUrl} /> : item.status === 'rejected' ?
            <p className="rq-preview-msg">The temporary PDF was removed after rejection, so a preview is no longer available.</p> :
            <p className="rq-preview-msg">Loading PDF preview…</p>}
        </div>
      </section>
      {item.status === 'pending' && <div className="rq-detail-actions">
        {showReject ? <div className="rq-reject-panel">
          <label className="rq-reason-field"><span>Reason shown to the student</span><textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={3} maxLength={500} placeholder="e.g. The scan is unreadable. Please upload a clearer copy." /></label>
          <div className="rq-foot-buttons">
            <button className="rq-btn rq-btn-outline" type="button" disabled={busy !== null} onClick={() => setShowReject(false)}>Cancel</button>
            <button className="rq-btn rq-btn-danger" type="button" disabled={busy !== null} onClick={() => void decide('reject')}>{busy === 'reject' ? 'Rejecting…' : 'Confirm reject'}</button>
          </div>
        </div> : <>
          <button className="rq-btn rq-btn-danger-outline" type="button" disabled={busy !== null} onClick={() => setShowReject(true)}><XCircle size={17} /> Reject</button>
          <button className="rq-btn rq-btn-primary" type="button" disabled={busy !== null || !pdfUrl} onClick={() => void decide('approve')}><CheckCircle size={17} /> {busy === 'approve' ? 'Publishing…' : 'Approve & publish'}</button>
        </>}
      </div>}
    </> : null}
  </div>
}
