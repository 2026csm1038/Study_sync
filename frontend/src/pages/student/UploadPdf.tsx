import { CircleCheck, FileText, X } from 'lucide-react'
import { useEffect, useRef, useState, type ChangeEvent, type DragEvent, type FormEvent } from 'react'
import { api } from '../../lib/api'
import { SHOW_SAMPLE_DATA } from '../../lib/demo'
import '../../upload.css'

/* ------------------------------------------------------------------ types -- */

type Course = { id: string; course_code: string; course_name: string }

/** The four fields on the Page 4 wireframe. */
export type UploadForm = {
  courseId: string
  year: string
  examType: string
  tags: string
}

type FormErrors = Partial<Record<'file' | keyof UploadForm, string>>

/* ---------------------------------------------------------------- options -- */
// Static lists, same as the Page 3 filters. Change them here only.
const YEARS = ['2026', '2025', '2024', '2023']
const EXAM_TYPES = ['Midsem', 'Endsem']
const MAX_BYTES = 2 * 1024 * 1024 // wireframe: "PDF only · max size 2MB"
const EMPTY_FORM: UploadForm = { courseId: '', year: '', examType: '', tags: '' }

const isPdf = (f: File) => f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf')
const sizeLabel = (bytes: number) =>
  bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB`

/* ------------------------------------------------------------------- page -- */

/**
 * Page 4: Upload PDF (student). UI only.
 * Plan: the PDF goes to private Supabase storage as "pending"; it moves to Google Drive only after an admin approves it.
 */
export default function UploadPdf() {
  const fileInput = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [form, setForm] = useState<UploadForm>(EMPTY_FORM)
  const [courses, setCourses] = useState<Course[]>([])
  const [errors, setErrors] = useState<FormErrors>({})
  const [dragging, setDragging] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [showToast, setShowToast] = useState(false)
  const [notice, setNotice] = useState('')

  // Existing endpoint: any logged-in user can list active courses.
  useEffect(() => {
    api<Course[]>('/api/courses')
      .then(setCourses)
      .catch(() => setCourses([]))
  }, [])

  useEffect(() => {
    if (!showToast) return
    const timer = window.setTimeout(() => setShowToast(false), 5000)
    return () => window.clearTimeout(timer)
  }, [showToast])

  function setField(key: keyof UploadForm, value: string) {
    setForm((prev) => ({ ...prev, [key]: value }))
    setErrors((prev) => ({ ...prev, [key]: undefined }))
  }

  function pickFile(picked: File | undefined) {
    if (!picked) return
    if (!isPdf(picked)) {
      setFile(null)
      setErrors((prev) => ({ ...prev, file: 'Only PDF files are allowed.' }))
    } else if (picked.size > MAX_BYTES) {
      setFile(null)
      setErrors((prev) => ({ ...prev, file: 'The file is larger than 2 MB.' }))
    } else {
      setFile(picked)
      setErrors((prev) => ({ ...prev, file: undefined }))
    }
  }

  function removeFile() {
    setFile(null)
    if (fileInput.current) fileInput.current.value = ''
  }

  function onDrop(e: DragEvent<HTMLLabelElement>) {
    e.preventDefault()
    setDragging(false)
    pickFile(e.dataTransfer.files[0])
  }

  function validate(): boolean {
    const next: FormErrors = {}
    if (!file) next.file = errors.file ?? 'Choose a PDF to upload.'
    if (!form.courseId) next.courseId = 'Select a course.'
    if (!form.year) next.year = 'Select a year.'
    if (!form.examType) next.examType = 'Select an exam type.'
    setErrors(next)
    return Object.keys(next).length === 0
  }

  /** TODO (submission endpoint): send `file` + `form` (multipart) to the backend. Resolve true when it succeeds. */
  async function submitResource(): Promise<boolean> {
    return SHOW_SAMPLE_DATA
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setNotice('')
    if (!validate()) return
    setSubmitting(true)
    const ok = await submitResource()
    setSubmitting(false)
    if (ok) {
      setShowToast(true)
      setForm(EMPTY_FORM)
      removeFile()
    } else {
      setNotice('Submission is not connected to the server yet.')
    }
  }

  return (
    <div className="st-page">
      {showToast && (
        <div className="up-toast" role="status">
          <CircleCheck size={22} aria-hidden="true" />
          <div>
            <strong>Paper submitted for review</strong>
            <span>It goes live after admin approval.</span>
          </div>
        </div>
      )}

      <header>
        <h1>Upload Previous Year Paper</h1>
        <p className="st-sub">Upload a PDF for review. It goes live after admin approval.</p>
      </header>

      <form className="up-card" onSubmit={handleSubmit} noValidate>
        <h2>Contribute a resource</h2>

        <label
          className={`up-drop${dragging ? ' up-drop-active' : ''}${errors.file ? ' up-drop-error' : ''}`}
          onDragOver={(e) => {
            e.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
        >
          <input
            ref={fileInput}
            type="file"
            accept="application/pdf,.pdf"
            className="up-file-input"
            onChange={(e: ChangeEvent<HTMLInputElement>) => pickFile(e.target.files?.[0])}
          />
          <strong>+ Drop PDF here or choose file</strong>
          <span>PDF only · max size 2MB</span>
        </label>
        {errors.file && <p className="up-error" role="alert">{errors.file}</p>}

        {file && (
          <div className="up-selected">
            <FileText size={20} aria-hidden="true" />
            <strong>{file.name}</strong>
            <span>{sizeLabel(file.size)}</span>
            <button type="button" onClick={removeFile} aria-label="Remove selected file">
              <X size={18} aria-hidden="true" />
            </button>
          </div>
        )}

        <div className="up-grid">
          <label className="up-field">
            <span>Course</span>
            <select value={form.courseId} onChange={(e) => setField('courseId', e.target.value)}>
              <option value="">Select course</option>
              {courses.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.course_code} · {c.course_name}
                </option>
              ))}
            </select>
            {errors.courseId && <em className="up-error">{errors.courseId}</em>}
          </label>

          <label className="up-field">
            <span>Year</span>
            <select value={form.year} onChange={(e) => setField('year', e.target.value)}>
              <option value="">Select year</option>
              {YEARS.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
            {errors.year && <em className="up-error">{errors.year}</em>}
          </label>

          <label className="up-field">
            <span>Exam Type</span>
            <select value={form.examType} onChange={(e) => setField('examType', e.target.value)}>
              <option value="">Select exam type</option>
              {EXAM_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
            {errors.examType && <em className="up-error">{errors.examType}</em>}
          </label>

          <label className="up-field">
            <span>Topic / Tags</span>
            <input
              type="text"
              value={form.tags}
              onChange={(e) => setField('tags', e.target.value)}
              placeholder="e.g. Trees, Graphs (optional)"
            />
          </label>
        </div>

        {notice && <p className="up-notice" role="status">{notice}</p>}

        <div className="up-actions">
          <button type="submit" className="up-submit" disabled={submitting}>
            Submit for Review
          </button>
        </div>
      </form>
    </div>
  )
}
