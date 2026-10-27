import { CircleCheck, FileText, Search } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../../lib/api'
import '../../requests.css'

type Status = 'pending' | 'approved' | 'rejected'
type RequestItem = {
  id: string
  status: Status
  course_id: string
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
const sizeLabel = (bytes: number) => bytes < 1024 * 1024
  ? `${Math.max(1, Math.round(bytes / 1024))} KB`
  : `${(bytes / (1024 * 1024)).toFixed(1)} MB`
const dateLabel = (iso: string | null) => iso
  ? new Date(iso).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })
  : '—'
const errorText = (err: unknown) => err instanceof Error ? err.message : 'Something went wrong. Please try again.'

export default function ManageRequests() {
  const navigate = useNavigate()
  const [tab, setTab] = useState<Status>('pending')
  const [items, setItems] = useState<RequestItem[]>([])
  const [pendingCount, setPendingCount] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [toast, setToast] = useState('')

  const load = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const rows = await api<RequestItem[]>(`/api/admin/submissions?status=${tab}`)
      setItems(rows)
      if (tab === 'pending') setPendingCount(rows.length)
    } catch (err) {
      setItems([]); setError(errorText(err))
    } finally { setLoading(false) }
  }, [tab])

  useEffect(() => { void load() }, [load])
  useEffect(() => {
    if (tab === 'pending') return
    api<RequestItem[]>('/api/admin/submissions?status=pending')
      .then((rows) => setPendingCount(rows.length)).catch(() => undefined)
  }, [tab])
  useEffect(() => {
    if (!toast) return
    const timer = window.setTimeout(() => setToast(''), 4500)
    return () => window.clearTimeout(timer)
  }, [toast])

  const filteredItems = useMemo(() => {
    const term = search.trim().toLocaleLowerCase()
    if (!term) return items
    return items.filter((item) => [
      item.original_filename, item.course_code, item.course_name, item.exam_type,
      String(item.exam_year), item.tags, item.uploaded_by_name,
      item.uploaded_by_entry_number, item.rejection_reason,
    ].some((value) => String(value ?? '').toLocaleLowerCase().includes(term)))
  }, [items, search])

  return <div className="st-page">
    {toast && <div className="rq-toast" role="status"><CircleCheck size={22} aria-hidden="true" /><strong>{toast}</strong></div>}
    <header>
      <h1>Manage Request</h1>
      <p className="st-sub">Review the papers students have uploaded. Approved papers become visible to every student.</p>
    </header>

    <div className="rq-tabs" role="tablist" aria-label="Request status">
      {TABS.map(({ status, label }) => <button key={status} type="button" role="tab"
        aria-selected={tab === status} className={`rq-tab${tab === status ? ' rq-tab-active' : ''}`}
        onClick={() => setTab(status)}>
        {label}{status === 'pending' && pendingCount ? <span className="rq-badge">{pendingCount}</span> : null}
      </button>)}
    </div>

    <label className="rq-search" htmlFor="rq-search-input">
      <Search size={19} aria-hidden="true" />
      <input id="rq-search-input" type="search" value={search} onChange={(e) => setSearch(e.target.value)}
        placeholder="Search by file name, course, type, year, tags or student…" />
    </label>

    {error && <p className="rq-error" role="alert">{error}</p>}
    <div className="rq-card">
      {loading ? <p className="rq-empty">Loading…</p> : filteredItems.length === 0 ?
        <p className="rq-empty">{items.length === 0 ? (tab === 'pending' ? 'No requests are waiting for review.' : `No ${tab} requests yet.`) : 'No requests match your search.'}</p> :
        <div className="rq-scroll"><table className="rq-table">
          <thead><tr><th>Paper</th><th>Course</th><th>Exam</th><th>Uploaded by</th><th>Submitted</th><th aria-label="Action" /></tr></thead>
          <tbody>{filteredItems.map((item) => <tr key={item.id}>
            <td><div className="rq-file"><FileText size={20} aria-hidden="true" /><div><strong>{item.original_filename}</strong>
              <span>{sizeLabel(item.file_size_bytes)}{item.tags ? ` · ${item.tags}` : ''}</span></div></div></td>
            <td><strong>{item.course_code ?? '—'}</strong><span className="rq-sub">{item.course_name}</span></td>
            <td>{item.exam_type} {item.exam_year}</td>
            <td><strong>{item.uploaded_by_name ?? '—'}</strong><span className="rq-sub">{item.uploaded_by_entry_number}</span></td>
            <td>{dateLabel(item.created_at)}</td>
            <td className="rq-action">{item.status === 'pending' && <button type="button" className="rq-btn rq-btn-primary" onClick={() => navigate(`/admin/requests/${item.id}`)}>Review</button>}
              {item.status === 'approved' && <button type="button" className="rq-btn rq-btn-outline" onClick={() => navigate(`/admin/requests/${item.id}`)}>Open</button>}
              {item.status === 'rejected' && <span className="rq-reason" title={item.rejection_reason ?? ''}>{item.rejection_reason}</span>}</td>
          </tr>)}</tbody>
        </table></div>}
    </div>
  </div>
}
