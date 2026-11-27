import { useEffect, useMemo, useState } from 'react'
import { api } from '../../lib/api'
import '../../upload.css'

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
  status: string
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

const tagsOf = (f: MyFlag) => (f.tags ?? '').split(',').map((t) => t.trim()).filter(Boolean)

export default function StudentProfile() {
  const [courses, setCourses] = useState<Course[]>([])
  const [mine, setMine] = useState<Mine[]>([])
  const [flags, setFlags] = useState<MyFlag[]>([])
  const [tag, setTag] = useState('')

  useEffect(() => {
    api<Course[]>('/api/courses').then(setCourses).catch(() => setCourses([]))
    api<Mine[]>('/api/submissions/mine').then(setMine).catch(() => undefined)
    api<MyFlag[]>('/api/resource-flags/mine').then(setFlags).catch(() => setFlags([]))
  }, [])

  const allTags = useMemo(() => Array.from(new Set(flags.flatMap(tagsOf))), [flags])
  const shown = tag ? flags.filter((f) => tagsOf(f).includes(tag)) : flags

  return (
    <div className="st-page">
      <header>
        <h1>Profile</h1>
      </header>

      <div className="up-columns">
      {mine.length > 0 && (
        <section className="up-card up-mine" aria-label="Your uploads">
          <h2>Your uploads</h2>
          <ul className="up-scroll">
            {mine.filter((m) => m.status !== 'deleted').map((m) => {
              const code = m.new_course?.code ?? courses.find((c) => c.id === m.course_id)?.course_code ?? 'Course'
              const label = { pending: 'Waiting for admin approval', approved: 'Published', rejected: 'Rejected' }[m.status as 'pending' | 'approved' | 'rejected']
              return (
                <li key={m.id}>
                  <div>
                    <strong>{code} · {m.exam_type} {m.exam_year}</strong>
                    <span>{m.original_filename}</span>
                    {m.status === 'rejected' && m.rejection_reason && <em>Reason: {m.rejection_reason}</em>}
                  </div>
                  <span className={`up-pill up-pill-${m.status}`}>{label}</span>
                </li>
              )
            })}
          </ul>
        </section>
      )}

      <section className="up-card up-mine" aria-label="Flagged items">
        <h2>Flagged items</h2>
        {allTags.length > 0 && (
          <div className="up-tagbar">
            <button type="button" className={!tag ? 'on' : ''} onClick={() => setTag('')}>All</button>
            {allTags.map((t) => (
              <button type="button" key={t} className={tag === t ? 'on' : ''} onClick={() => setTag(t)}>{t}</button>
            ))}
          </div>
        )}
        {shown.length === 0 ? (
          <p className="up-flag-empty">No flagged items.</p>
        ) : (
          <ul className="up-scroll">
            {shown.map((f) => (
              <li key={f.id}>
                <div>
                  <strong>{f.course_code ?? 'Course'} · {f.exam_type} {f.exam_year}</strong>
                  <span>{f.original_filename}</span>
                  {tagsOf(f).length > 0 && <span>Tags: {tagsOf(f).join(', ')}</span>}
                  <em>Reason: {REASON_LABEL[f.reason] ?? f.reason}{f.details ? ` – ${f.details}` : ''}</em>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
      </div>
    </div>
  )
}
