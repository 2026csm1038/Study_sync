import {
  CircleCheck,
  CircleHelp,
  CircleX,
  ClipboardList,
  CloudUpload,
  FileCheck,
  FileText,
  GraduationCap,
  Users,
  type LucideIcon,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../../lib/api'
import { SHOW_SAMPLE_DATA } from '../../lib/demo'

/* ------------------------------------------------------------------ types -- */

type ActivityKind = 'uploaded' | 'approved' | 'rejected' | 'course_added'

type Activity = { id: string; kind: ActivityKind; text: string; actor: string | null; at: string }

/** The response of GET /api/admin/dashboard. */
export type DashboardData = {
  total_students: number
  total_courses: number
  total_resources: number
  resources_by_type: Record<string, number>
  recent_activity: Activity[]
}

/* ------------------------------------------------------------------- data -- */

// The four paper types the database knows (same list as the Page 3 filters).
const TYPES: { label: string; color: string; icon: LucideIcon }[] = [
  { label: 'Midsem', color: '#5c4ee5', icon: FileText },
  { label: 'Endsem', color: '#3b82f6', icon: FileCheck },
  { label: 'Lab Test', color: '#34c38f', icon: ClipboardList },
  { label: 'Tutorials', color: '#f59e0b', icon: CircleHelp },
]

const ACTIVITY_ICON: Record<ActivityKind, { icon: LucideIcon; className: string }> = {
  uploaded: { icon: FileText, className: '' },
  approved: { icon: CircleCheck, className: 'ad-act-approved' },
  rejected: { icon: CircleX, className: 'ad-act-rejected' },
  course_added: { icon: GraduationCap, className: '' },
}

// Sample numbers for screenshots only. Shown when SHOW_SAMPLE_DATA is true (lib/demo.ts).
const SAMPLE: DashboardData = {
  total_students: 324,
  total_courses: 18,
  total_resources: 415,
  resources_by_type: { Midsem: 150, Endsem: 180, 'Lab Test': 40, Tutorials: 45 },
  recent_activity: [
    { id: '1', kind: 'uploaded', text: 'CSE201 Midsem 2026 submitted for review', actor: 'Vanshika Aggarwal', at: new Date().toISOString() },
    { id: '2', kind: 'approved', text: 'CSE203 Endsem 2025 approved', actor: 'Admin', at: new Date(Date.now() - 26 * 3600e3).toISOString() },
    { id: '3', kind: 'rejected', text: 'CSE204 Lab Test 2025 rejected', actor: 'Admin', at: '2025-05-12T10:00:00Z' },
    { id: '4', kind: 'course_added', text: 'New course added: MAT201', actor: null, at: '2025-05-11T10:00:00Z' },
    { id: '5', kind: 'uploaded', text: 'CSE202 Tutorials 2025 submitted for review', actor: 'Niharika Girdhar', at: '2025-05-10T10:00:00Z' },
  ],
}

const VISIBLE_ACTIVITY = 4

const fmt = (n: number | null) => (n === null ? '—' : n.toLocaleString('en-IN'))

/** "10:24 AM" today, "Yesterday, 4:18 PM", otherwise "May 12, 2025". */
function formatWhen(iso: string): string {
  const date = new Date(iso)
  const time = date.toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit' })
  const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
  const days = Math.round((startOfDay(new Date()) - startOfDay(date)) / 86_400_000)
  if (days === 0) return time
  if (days === 1) return `Yesterday, ${time}`
  return date.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
}

/* ------------------------------------------------------------------- page -- */

/** Page 5: Admin Dashboard. Loads everything from GET /api/admin/dashboard. */
export default function AdminDashboard() {
  const [data, setData] = useState<DashboardData | null>(SHOW_SAMPLE_DATA ? SAMPLE : null)
  const [error, setError] = useState('')
  const [visible, setVisible] = useState(VISIBLE_ACTIVITY)

  useEffect(() => {
    if (SHOW_SAMPLE_DATA) return
    api<DashboardData>('/api/admin/dashboard')
      .then(setData)
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load the dashboard.'))
  }, [])

  const stats: { label: string; value: number | null; icon: LucideIcon }[] = [
    { label: 'Total Students', value: data?.total_students ?? null, icon: Users },
    { label: 'Total Courses', value: data?.total_courses ?? null, icon: GraduationCap },
    ...TYPES.map((t) => ({ label: t.label, value: data ? (data.resources_by_type[t.label] ?? 0) : null, icon: t.icon })),
  ]

  const segments = TYPES.map((t) => ({
    label: t.label,
    color: t.color,
    value: data ? (data.resources_by_type[t.label] ?? 0) : null,
  }))
  const total = segments.reduce((sum, s) => sum + (s.value ?? 0), 0)
  let running = 0
  const ring =
    total > 0
      ? segments
          .map((s) => {
            const start = (running / total) * 100
            running += s.value ?? 0
            return `${s.color} ${start}% ${(running / total) * 100}%`
          })
          .join(', ')
      : '#e6e8f2 0% 100%'

  const activity = data?.recent_activity ?? []

  return (
    <div className="st-page">
      <header>
        <h1>Admin Dashboard</h1>
        <p className="st-sub">Manage StudySync academic resources and platform content.</p>
      </header>

      {error && <p className="ad-error" role="alert">{error}</p>}

      <section className="ad-stats" aria-label="Platform totals">
        {stats.map(({ label, value, icon: Icon }) => (
          <div key={label} className="ad-stat">
            <div className="ad-stat-icon">
              <Icon size={22} aria-hidden="true" />
            </div>
            <div>
              <strong>{fmt(value)}</strong>
              <span>{label}</span>
            </div>
          </div>
        ))}
      </section>

      <section aria-label="Quick actions">
        <h2 className="ad-section-title">Quick Actions</h2>
        <div className="ad-actions">
          <Link to="/admin/upload" className="ad-btn ad-btn-primary">
            <CloudUpload size={18} aria-hidden="true" />
            Upload New Paper
          </Link>
          <Link to="/admin/courses" className="ad-btn ad-btn-outline">
            <GraduationCap size={18} aria-hidden="true" />
            Manage Courses
          </Link>
        </div>
      </section>

      <div className="ad-panels">
        <section className="ad-panel" aria-label="Recent activity">
          <h2>Recent Activity</h2>
          {activity.length === 0 ? (
            <p className="ad-empty">{data ? 'No recent activity yet.' : error ? 'Not available.' : 'Loading…'}</p>
          ) : (
            <>
              <ul className="ad-activity">
                {activity.slice(0, visible).map((item) => {
                  const { icon: Icon, className } = ACTIVITY_ICON[item.kind]
                  return (
                    <li key={item.id}>
                      <div className={`ad-activity-icon ${className}`}>
                        <Icon size={18} aria-hidden="true" />
                      </div>
                      <div className="ad-activity-text">
                        <strong>{item.text}</strong>
                        {item.actor && <small>by {item.actor}</small>}
                      </div>
                      <span>{formatWhen(item.at)}</span>
                    </li>
                  )
                })}
              </ul>
              {activity.length > visible && (
                <button type="button" className="ad-more" onClick={() => setVisible(activity.length)}>
                  show more
                </button>
              )}
            </>
          )}
        </section>

        <section className="ad-panel" aria-label="Resource overview">
          <h2>Resource Overview</h2>
          <div className="ad-overview">
            <div
              className="ad-donut"
              style={{ background: `conic-gradient(${ring})` }}
              role="img"
              aria-label="Share of approved papers by type"
            />
            <ul className="ad-legend">
              {segments.map((s) => (
                <li key={s.label}>
                  <i style={{ background: s.color }} aria-hidden="true" />
                  <span>{s.label}</span>
                  <strong>{fmt(s.value)}</strong>
                  {total > 0 && s.value !== null && <em>{Math.round((s.value / total) * 100)}%</em>}
                </li>
              ))}
            </ul>
          </div>
          {data && total === 0 && <p className="ad-empty">No approved resources yet.</p>}
        </section>
      </div>
    </div>
  )
}
