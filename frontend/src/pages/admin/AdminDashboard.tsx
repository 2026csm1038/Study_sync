import {
  CircleHelp,
  ClipboardList,
  CloudUpload,
  FileText,
  GraduationCap,
  Users,
  type LucideIcon,
} from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { SHOW_SAMPLE_DATA } from '../../lib/demo'

/* ------------------------------------------------------------------ types -- */

type ActivityKind = 'paper' | 'assignment' | 'quiz' | 'course'

type Activity = { id: string; text: string; time: string; kind: ActivityKind }

/** Everything the dashboard shows. null = not available yet. */
export type DashboardData = {
  totalStudents: number | null
  totalCourses: number | null
  previousPapers: number | null
  quizzes: number | null
  assignments: number | null
  recent: Activity[]
}

/* ------------------------------------------------------------------- data -- */

const EMPTY: DashboardData = {
  totalStudents: null,
  totalCourses: null,
  previousPapers: null,
  quizzes: null,
  assignments: null,
  recent: [],
}

// Sample numbers from the Page 5 wireframe. Shown only when SHOW_SAMPLE_DATA is true (lib/demo.ts).
const SAMPLE: DashboardData = {
  totalStudents: 324,
  totalCourses: 18,
  previousPapers: 246,
  quizzes: 57,
  assignments: 112,
  recent: [
    { id: '1', kind: 'paper', text: 'DSA Midsem 2026 uploaded', time: '10:24 AM' },
    { id: '2', kind: 'assignment', text: 'DBMS Assignment 3 uploaded', time: 'Yesterday, 4:18 PM' },
    { id: '3', kind: 'paper', text: 'CN Endsem 2025 uploaded', time: 'May 12, 2025' },
    { id: '4', kind: 'course', text: 'New course added', time: 'May 11, 2025' },
    { id: '5', kind: 'quiz', text: 'Operating Systems Quiz 5 uploaded', time: 'May 10, 2025' },
    { id: '6', kind: 'paper', text: 'DBMS Midsem 2025 uploaded', time: 'May 9, 2025' },
  ],
}

const ACTIVITY_ICON: Record<ActivityKind, LucideIcon> = {
  paper: FileText,
  assignment: ClipboardList,
  quiz: CircleHelp,
  course: GraduationCap,
}

const VISIBLE_ACTIVITY = 4

const fmt = (n: number | null) => (n === null ? '—' : n.toLocaleString('en-IN'))

/* ------------------------------------------------------------------- page -- */

/** Page 5: Admin Dashboard. UI only; the stats and activity endpoints plug in at `data` below. */
export default function AdminDashboard() {
  // TODO (admin stats endpoint): replace this constant with state filled from the backend.
  const data: DashboardData = SHOW_SAMPLE_DATA ? SAMPLE : EMPTY
  const [visible, setVisible] = useState(VISIBLE_ACTIVITY)

  const stats: { label: string; value: number | null; icon: LucideIcon }[] = [
    { label: 'Total Students', value: data.totalStudents, icon: Users },
    { label: 'Total Courses', value: data.totalCourses, icon: GraduationCap },
    { label: 'Previous Papers', value: data.previousPapers, icon: FileText },
    { label: 'Quizzes', value: data.quizzes, icon: CircleHelp },
    { label: 'Assignments', value: data.assignments, icon: ClipboardList },
  ]

  const segments = [
    { label: 'Previous Papers', value: data.previousPapers, color: '#5c4ee5' },
    { label: 'Assignments', value: data.assignments, color: '#3b82f6' },
    { label: 'Quizzes', value: data.quizzes, color: '#34c38f' },
  ]
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

  return (
    <div className="st-page">
      <header>
        <h1>Admin Dashboard</h1>
        <p className="st-sub">Manage StudySync academic resources and platform content.</p>
      </header>

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
          {data.recent.length === 0 ? (
            <p className="ad-empty">No recent activity yet.</p>
          ) : (
            <>
              <ul className="ad-activity">
                {data.recent.slice(0, visible).map((item) => {
                  const Icon = ACTIVITY_ICON[item.kind]
                  return (
                    <li key={item.id}>
                      <div className="ad-activity-icon">
                        <Icon size={18} aria-hidden="true" />
                      </div>
                      <strong>{item.text}</strong>
                      <span>{item.time}</span>
                    </li>
                  )
                })}
              </ul>
              {data.recent.length > visible && (
                <button type="button" className="ad-more" onClick={() => setVisible(data.recent.length)}>
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
              aria-label="Share of previous papers, assignments and quizzes"
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
          {total === 0 && <p className="ad-empty">No resources yet.</p>}
        </section>
      </div>
    </div>
  )
}
