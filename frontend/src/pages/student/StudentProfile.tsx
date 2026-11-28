import { useEffect, useMemo, useState } from 'react'
import { BookOpen, Flag, GraduationCap, Mail, UserRound } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { api } from '../../lib/api'
import '../../upload.css'
import '../../profile.css'

type Course = { id: string; course_code: string; course_name: string }

type Mine = {
  id: string
  course_id: string | null
  new_course: { code: string; name: string } | null
  exam_type: string
  exam_year: number
  original_filename: string
  status: 'pending' | 'approved' | 'rejected' | 'deleted'
  rejection_reason: string | null
}

type MyFlag = {
  id: string
  reason: string
  details: string | null
  status: 'open' | 'resolved' | 'dismissed' | string
  created_at?: string
  original_filename: string | null
  course_code: string | null
  exam_type: string | null
  exam_year: number | null
  tags: string | null
}

const REASON_LABEL: Record<string, string> = {
  incorrect_content: 'Incorrect content',
  duplicate: 'Duplicate',
  poor_quality: 'Poor quality',
  inappropriate: 'Inappropriate',
  other: 'Other',
}

const UPLOAD_STATUS: Record<Mine['status'], string> = {
  pending: 'Pending review',
  approved: 'Published',
  rejected: 'Rejected',
  deleted: 'Removed',
}

const FLAG_STATUS: Record<string, string> = {
  open: 'Under review',
  resolved: 'Resolved',
  dismissed: 'Dismissed',
}

const tagsOf = (f: MyFlag) => (f.tags ?? '').split(',').map((t) => t.trim()).filter(Boolean)
const dateLabel = (value?: string) => value
  ? new Date(value).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
  : ''

export default function StudentProfile() {
  const { profile } = useAuth()
  const [courses, setCourses] = useState<Course[]>([])
  const [mine, setMine] = useState<Mine[]>([])
  const [flags, setFlags] = useState<MyFlag[]>([])
  const [activeTab, setActiveTab] = useState<'uploads' | 'reports'>('uploads')
  const [tag, setTag] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    Promise.allSettled([
      api<Course[]>('/api/courses'),
      api<Mine[]>('/api/submissions/mine'),
      api<MyFlag[]>('/api/resource-flags/mine'),
    ]).then(([courseResult, uploadResult, flagResult]) => {
      if (!active) return
      if (courseResult.status === 'fulfilled') setCourses(courseResult.value)
      if (uploadResult.status === 'fulfilled') setMine(uploadResult.value)
      else setError(uploadResult.reason instanceof Error ? uploadResult.reason.message : 'Could not load uploaded resources.')
      if (flagResult.status === 'fulfilled') setFlags(flagResult.value)
      else setError((current) => current || (flagResult.reason instanceof Error ? flagResult.reason.message : 'Could not load reported resources.'))
    }).finally(() => {
      if (active) setLoading(false)
    })
    return () => { active = false }
  }, [])

  const allTags = useMemo(() => Array.from(new Set(flags.flatMap(tagsOf))), [flags])
  const shownFlags = tag ? flags.filter((f) => tagsOf(f).includes(tag)) : flags
  const initials = (profile?.full_name ?? 'U').trim().split(/\s+/).slice(0, 2).map((part) => part[0]).join('').toUpperCase()
  const isStudent = profile?.role === 'student'
  const uploadCount = mine.length
  const publishedCount = mine.filter((item) => item.status === 'approved').length

  return (
    <div className="st-page sp-page">
      <header className="sp-page-heading">
        <div>
          <p className="sp-eyebrow">STUDYSYNC ACCOUNT</p>
          <h1>My Profile</h1>
          <p className="st-sub">Your academic identity and activity in the StudySync community.</p>
        </div>
      </header>

      <section className="sp-identity" aria-label="Personal details">
        <div className="sp-avatar">{initials || <UserRound size={30} />}</div>
        <div className="sp-identity-main">
          <h2>{profile?.full_name ?? 'Your profile'}</h2>
          <span className={`sp-role sp-role-${profile?.role ?? 'user'}`}>
            <GraduationCap size={14} /> {profile?.role === 'professor' ? 'Professor' : profile?.role === 'student' ? 'Student' : 'User'}
          </span>
        </div>
        <div className="sp-details">
          <div><Mail size={16} /><span>{profile?.email || 'Email not available'}</span></div>
          {isStudent && <div><UserRound size={16} /><span>Entry number: {profile?.entry_number || 'Not provided'}</span></div>}
        </div>
      </section>

      <section className="sp-stats" aria-label="Activity summary">
        <article className="sp-stat-card">
          <span className="sp-stat-icon sp-stat-purple"><BookOpen size={19} /></span>
          <div><strong>{uploadCount}</strong><span>Resources uploaded</span></div>
        </article>
        <article className="sp-stat-card">
          <span className="sp-stat-icon sp-stat-green"><GraduationCap size={19} /></span>
          <div><strong>{publishedCount}</strong><span>Published resources</span></div>
        </article>
        <article className="sp-stat-card">
          <span className="sp-stat-icon sp-stat-orange"><Flag size={19} /></span>
          <div><strong>{flags.length}</strong><span>Resources reported</span></div>
        </article>
      </section>

      <section className="sp-activity" aria-label="Your activity">
        <div className="sp-activity-heading">
          <div>
            <h2>Your activity</h2>
            <p>Track the resources you have shared and reported.</p>
          </div>
          <div className="sp-tabs" role="tablist" aria-label="Profile activity">
            <button type="button" role="tab" aria-selected={activeTab === 'uploads'} className={activeTab === 'uploads' ? 'active' : ''} onClick={() => setActiveTab('uploads')}>
              Uploaded <span>{mine.length}</span>
            </button>
            <button type="button" role="tab" aria-selected={activeTab === 'reports'} className={activeTab === 'reports' ? 'active' : ''} onClick={() => setActiveTab('reports')}>
              Reported <span>{flags.length}</span>
            </button>
          </div>
        </div>

        {error && <p className="sp-error" role="alert">{error}</p>}
        {loading ? <div className="sp-loading">Loading your activity…</div> : activeTab === 'uploads' ? (
          mine.length === 0 ? (
            <div className="sp-empty-state"><BookOpen size={28} /><strong>No uploads yet</strong><span>Resources you upload will appear here with their publication status.</span></div>
          ) : (
            <ul className="sp-activity-list">
              {mine.map((item) => {
                const course = courses.find((c) => c.id === item.course_id)
                const code = item.new_course?.code ?? course?.course_code ?? 'Course'
                const name = item.new_course?.name ?? course?.course_name
                return <li key={item.id} className="sp-activity-item">
                  <span className="sp-item-icon"><BookOpen size={19} /></span>
                  <div className="sp-item-main">
                    <strong>{code} · {item.exam_type} {item.exam_year}</strong>
                    <span>{item.original_filename}</span>
                    {name && <small>{name}</small>}
                    {item.status === 'rejected' && item.rejection_reason && <em>Reason: {item.rejection_reason}</em>}
                  </div>
                  <span className={`sp-status sp-status-${item.status}`}>{UPLOAD_STATUS[item.status]}</span>
                </li>
              })}
            </ul>
          )
        ) : (
          <>
            {allTags.length > 0 && <div className="sp-tag-filter" aria-label="Filter reported resources by tag">
              <button type="button" className={!tag ? 'active' : ''} onClick={() => setTag('')}>All tags</button>
              {allTags.map((value) => <button type="button" key={value} className={tag === value ? 'active' : ''} onClick={() => setTag(value)}>{value}</button>)}
            </div>}
            {shownFlags.length === 0 ? (
              <div className="sp-empty-state"><Flag size={28} /><strong>No reports yet</strong><span>Resources you report will appear here so you can follow their status.</span></div>
            ) : (
              <ul className="sp-activity-list">
                {shownFlags.map((flag) => <li key={flag.id} className="sp-activity-item">
                  <span className="sp-item-icon sp-item-icon-flag"><Flag size={19} /></span>
                  <div className="sp-item-main">
                    <strong>{flag.course_code ?? 'Course'} · {flag.exam_type ?? 'Resource'} {flag.exam_year ?? ''}</strong>
                    <span>{flag.original_filename ?? 'Resource details unavailable'}</span>
                    <small>Reason: {REASON_LABEL[flag.reason] ?? flag.reason}{flag.details ? ` · ${flag.details}` : ''}</small>
                    {tagsOf(flag).length > 0 && <small>Tags: {tagsOf(flag).join(', ')}</small>}
                    {dateLabel(flag.created_at) && <small>Reported on {dateLabel(flag.created_at)}</small>}
                  </div>
                  <span className={`sp-status sp-status-${flag.status}`}>{FLAG_STATUS[flag.status] ?? flag.status}</span>
                </li>)}
              </ul>
            )}
          </>
        )}
      </section>
    </div>
  )
}
