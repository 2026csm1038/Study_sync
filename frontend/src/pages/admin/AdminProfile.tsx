import { FileText } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '../../lib/api'
import '../../requests.css'

type Activity = {
  id: string
  status: 'approved' | 'rejected'
  department_name: string | null
  semester: number | null
  course_code: string | null
  course_name: string | null
  exam_year: number
  exam_type: string
  tags: string | null
  original_filename: string
  uploaded_by_name: string | null
  uploaded_by_entry_number: string | null
  reviewed_at: string | null
  rejection_reason: string | null
}

const dateLabel = (iso: string | null) => iso
  ? new Date(iso).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })
  : '—'

function Section({ title, action, rows }: { title: string; action: 'approved' | 'rejected'; rows: Activity[] }) {
  return <>
    <h2>{title} ({rows.length})</h2>
    <div className="rq-card">
      {rows.length === 0 ? <p className="rq-empty">No {action} requests yet.</p> :
        <div className="rq-scroll"><table className="rq-table">
          <thead><tr><th>Request</th><th>Course / Department</th><th>Exam</th><th>Uploaded by</th><th>Action</th><th>{action === 'rejected' ? 'Reason' : 'Date'}</th></tr></thead>
          <tbody>{rows.map((r) => <tr key={r.id}>
            <td><div className="rq-file"><FileText size={20} aria-hidden="true" /><div><strong>{r.original_filename}</strong>
              {r.tags && <span>{r.tags}</span>}</div></div></td>
            <td><strong>{r.course_code ?? '—'}</strong><span className="rq-sub">{r.course_name}</span>
              {r.department_name && <span className="rq-sub">{r.department_name}{r.semester ? ` · Sem ${r.semester}` : ''}</span>}</td>
            <td>{r.exam_type} {r.exam_year}</td>
            <td><strong>{r.uploaded_by_name ?? '—'}</strong><span className="rq-sub">{r.uploaded_by_entry_number}</span></td>
            <td><span className={`rq-status rq-status-${r.status}`}>{r.status}</span><span className="rq-sub">{dateLabel(r.reviewed_at)}</span></td>
            <td>{action === 'rejected' ? <span className="rq-reason" title={r.rejection_reason ?? ''}>{r.rejection_reason}</span> : dateLabel(r.reviewed_at)}</td>
          </tr>)}</tbody>
        </table></div>}
    </div>
  </>
}

export default function AdminProfile() {
  const [items, setItems] = useState<Activity[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    api<Activity[]>('/api/admin/submissions/my-activity')
      .then(setItems)
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load your activity.'))
      .finally(() => setLoading(false))
  }, [])

  return <div className="st-page">
    <header>
      <h1>Profile</h1>
      <p className="st-sub">A read-only record of the new course requests you have reviewed.</p>
    </header>
    {error && <p className="rq-error" role="alert">{error}</p>}
    {loading ? <p className="rq-empty">Loading…</p> : <>
      <Section title="Approved requests" action="approved" rows={items.filter((i) => i.status === 'approved')} />
      <Section title="Rejected requests" action="rejected" rows={items.filter((i) => i.status === 'rejected')} />
    </>}
  </div>
}
