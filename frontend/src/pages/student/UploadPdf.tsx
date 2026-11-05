import { CircleCheck, FileText, X } from 'lucide-react'
import { useEffect, useRef, useState, type ChangeEvent, type DragEvent, type FormEvent } from 'react'
import { api, ApiError } from '../../lib/api'
import '../../upload.css'

/* ------------------------------------------------------------------ types -- */

type Course = { id: string; course_code: string; course_name: string }

type Department = { id: string; name: string; code: string | null }

/** Value of the course dropdown that means "type a new course instead". */
const NEW_COURSE = '__new__'
const SEMESTERS = Array.from({ length: 12 }, (_, i) => String(i + 1))

/** The fields on the Page 4 wireframe, plus the details of a course typed by the student. */
export type UploadForm = {
  courseId: string
  courseCode: string
  courseName: string
  department: string
  semester: string
  year: string
  examType: string
  tags: string
}

type FormErrors = Partial<Record<'file' | keyof UploadForm, string>>

/* ---------------------------------------------------------------- options -- */
// Static lists, same as the Page 3 filters. Change them here only.
const YEARS = ['2026', '2025', '2024', '2023']
const EXAM_TYPES = ['Midsem', 'Endsem', 'Lab Test', 'Tutorials']
const MAX_BYTES = 2 * 1024 * 1024 // wireframe: "PDF only · max size 2MB"
const EMPTY_FORM: UploadForm = {
  courseId: '',
  courseCode: '',
  courseName: '',
  department: '',
  semester: '',
  year: '',
  examType: '',
  tags: '',
}

const isPdf = (f: File) => f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf')
const sizeLabel = (bytes: number) =>
  bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB`

/* ------------------------------------------------------------------- page -- */

/**
 * Page 4: Upload PDF (student).
 * POST /api/submissions validates the PDF, checks duplicates, uploads it directly to the
 * configured Google Shared Drive, and publishes its metadata immediately.
 */
export default function UploadPdf() {
  const fileInput = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [form, setForm] = useState<UploadForm>(EMPTY_FORM)
  const [courses, setCourses] = useState<Course[]>([])
  const [departments, setDepartments] = useState<Department[]>([])
  const [errors, setErrors] = useState<FormErrors>({})
  const [dragging, setDragging] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [showToast, setShowToast] = useState(false)
  const [notice, setNotice] = useState('')
  const [rejection, setRejection] = useState('')

  // Existing endpoint: any logged-in user can list active courses.
  useEffect(() => {
    api<Course[]>('/api/courses')
      .then(setCourses)
      .catch(() => setCourses([]))
    // used only to suggest names while typing a new course's department
    api<Department[]>('/api/departments')
      .then(setDepartments)
      .catch(() => setDepartments([]))
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
    if (form.courseId === NEW_COURSE) {
      delete next.courseId
      if (!/^[A-Za-z0-9-]{3,30}$/.test(form.courseCode.trim())) {
        next.courseCode = 'Letters, digits and hyphens only, e.g. CSE301.'
      }
      if (form.courseName.trim().length < 2) next.courseName = 'Enter the course name.'
      if (!form.department.trim()) next.department = 'Enter the department.'
      if (!form.semester) next.semester = 'Select a semester.'
    }
    if (!form.year) next.year = 'Select a year.'
    if (!form.examType) next.examType = 'Select an exam type.'
    setErrors(next)
    return Object.keys(next).length === 0
  }

  /** Sends the PDF + details (multipart). Throws an ApiError carrying the server's reason if it is rejected. */
  async function submitResource(pdf: File) {
    const data = new FormData()
    data.append('file', pdf)
    if (form.courseId === NEW_COURSE) {
      // a course that isn't in the list yet: the server adds it (and its department if needed)
      data.append('course_code', form.courseCode.trim())
      data.append('course_name', form.courseName.trim())
      data.append('department', form.department.trim())
      data.append('semester', form.semester)
    } else {
      data.append('course_id', form.courseId)
    }
    data.append('exam_year', form.year)
    data.append('exam_type', form.examType)
    if (form.tags.trim()) data.append('tags', form.tags.trim())
    await api('/api/submissions', { method: 'POST', body: data })
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setNotice('')
    setRejection('')
    if (!validate() || !file) return
    setSubmitting(true)
    try {
      await submitResource(file)
      setShowToast(true)
      if (form.courseId === NEW_COURSE) {
        // refresh so the course that was just added shows up in the list
        api<Course[]>('/api/courses').then(setCourses).catch(() => undefined)
        api<Department[]>('/api/departments').then(setDepartments).catch(() => undefined)
      }
      setForm(EMPTY_FORM)
      removeFile()
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        // duplicate: keep the form as it is so the student can change the details
        setRejection(err.message)
      } else {
        setNotice(err instanceof Error ? err.message : 'Could not submit the paper. Please try again.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="st-page">
      {showToast && (
        <div className="up-toast" role="status">
          <CircleCheck size={22} aria-hidden="true" />
          <div>
            <strong>Paper uploaded successfully</strong>
            <span>Your PDF is now available in StudySync.</span>
          </div>
        </div>
      )}

      <header>
        <h1>Upload Previous Year Paper</h1>
        <p className="st-sub">Upload a PDF directly to StudySync. It becomes available as soon as the upload succeeds.</p>
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
              <option value={NEW_COURSE}>+ My course isn't listed</option>
            </select>
            {errors.courseId && <em className="up-error">{errors.courseId}</em>}
          </label>

          {form.courseId === NEW_COURSE && (
            <>
              <label className="up-field">
                <span>Course Code</span>
                <input
                  type="text"
                  value={form.courseCode}
                  onChange={(e) => setField('courseCode', e.target.value)}
                  placeholder="e.g. CSE301"
                />
                {errors.courseCode && <em className="up-error">{errors.courseCode}</em>}
              </label>
              <label className="up-field">
                <span>Course Name</span>
                <input
                  type="text"
                  value={form.courseName}
                  onChange={(e) => setField('courseName', e.target.value)}
                  placeholder="e.g. Compilers"
                />
                {errors.courseName && <em className="up-error">{errors.courseName}</em>}
              </label>
              <label className="up-field">
                <span>Department</span>
                <input
                  type="text"
                  list="up-departments"
                  value={form.department}
                  onChange={(e) => setField('department', e.target.value)}
                  placeholder="Pick one or type a new one"
                />
                <datalist id="up-departments">
                  {departments.map((d) => (
                    <option key={d.id} value={d.name} />
                  ))}
                </datalist>
                {errors.department && <em className="up-error">{errors.department}</em>}
              </label>
              <label className="up-field">
                <span>Semester</span>
                <select value={form.semester} onChange={(e) => setField('semester', e.target.value)}>
                  <option value="">Select semester</option>
                  {SEMESTERS.map((n) => (
                    <option key={n} value={n}>
                      Semester {n}
                    </option>
                  ))}
                </select>
                {errors.semester && <em className="up-error">{errors.semester}</em>}
              </label>
            </>
          )}

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

        {rejection && (
          <div className="up-rejected" role="alert">
            <strong>Duplicate upload</strong>
            <span>{rejection}</span>
          </div>
        )}
        {notice && <p className="up-notice" role="alert">{notice}</p>}

        <div className="up-actions">
          <button type="submit" className="up-submit" disabled={submitting}>
            Upload PDF
          </button>
        </div>
      </form>
    </div>
  )
}