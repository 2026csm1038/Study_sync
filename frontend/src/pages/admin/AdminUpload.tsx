import { CircleCheck, FileText, X } from 'lucide-react'
import { useEffect, useRef, useState, type ChangeEvent, type DragEvent, type FormEvent } from 'react'
import { api, ApiError } from '../../lib/api'
import '../../upload.css'

type Course = { id: string; course_code: string; course_name: string }
type Department = { id: string; name: string; code: string | null }

type UploadForm = {
  courseId: string
  courseCode: string
  courseName: string
  departmentId: string
  semester: string
  year: string
  examType: string
  tags: string
}

type FormErrors = Partial<Record<'file' | keyof UploadForm, string>>

const NEW_COURSE = '__new__'
const SEMESTERS = Array.from({ length: 12 }, (_, i) => String(i + 1))
const YEARS = ['2026', '2025', '2024', '2023']
const EXAM_TYPES = ['Midsem', 'Endsem', 'Lab Test', 'Tutorials']
const MAX_BYTES = 2 * 1024 * 1024

const EMPTY_FORM: UploadForm = {
  courseId: '',
  courseCode: '',
  courseName: '',
  departmentId: '',
  semester: '',
  year: '',
  examType: '',
  tags: '',
}

const isPdf = (file: File) =>
  file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')

const sizeLabel = (bytes: number) =>
  bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} KB`
    : `${(bytes / (1024 * 1024)).toFixed(1)} MB`

export default function AdminUpload() {
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
  const [duplicate, setDuplicate] = useState('')

  useEffect(() => {
    let cancelled = false
    Promise.all([
      api<Course[]>('/api/courses'),
      api<Department[]>('/api/departments'),
    ]).then(([courseRows, departmentRows]) => {
      if (cancelled) return
      setCourses(courseRows)
      setDepartments(departmentRows)
    }).catch((error: unknown) => {
      if (!cancelled) {
        setNotice(error instanceof Error ? error.message : 'Could not load courses and departments.')
      }
    })
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    if (!showToast) return
    const timer = window.setTimeout(() => setShowToast(false), 5000)
    return () => window.clearTimeout(timer)
  }, [showToast])

  function setField(key: keyof UploadForm, value: string) {
    setForm((current) => ({ ...current, [key]: value }))
    setErrors((current) => ({ ...current, [key]: undefined }))
  }

  function pickFile(picked?: File) {
    if (!picked) return
    if (!isPdf(picked)) {
      setFile(null)
      setErrors((current) => ({ ...current, file: 'Only PDF files are allowed.' }))
    } else if (picked.size > MAX_BYTES) {
      setFile(null)
      setErrors((current) => ({ ...current, file: 'The file is larger than 2 MB.' }))
    } else {
      setFile(picked)
      setErrors((current) => ({ ...current, file: undefined }))
    }
  }

  function removeFile() {
    setFile(null)
    if (fileInput.current) fileInput.current.value = ''
  }

  function onDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault()
    setDragging(false)
    pickFile(event.dataTransfer.files[0])
  }

  function validate() {
    const next: FormErrors = {}
    if (!file) next.file = errors.file ?? 'Choose a PDF to upload.'
    if (!form.courseId) next.courseId = 'Select a course.'
    if (form.courseId === NEW_COURSE) {
      if (!/^[A-Za-z0-9-]{3,30}$/.test(form.courseCode.trim())) {
        next.courseCode = 'Letters, digits and hyphens only, e.g. CSE301.'
      }
      if (form.courseName.trim().length < 2) next.courseName = 'Enter the course name.'
      if (!form.departmentId) next.departmentId = 'Select a department.'
      if (!form.semester) next.semester = 'Select a semester.'
    }
    if (!form.year) next.year = 'Select a year.'
    if (!form.examType) next.examType = 'Select an exam type.'
    setErrors(next)
    return Object.keys(next).length === 0
  }

  async function uploadToCourse(pdf: File, courseId: string) {
    const data = new FormData()
    data.append('file', pdf)
    data.append('course_id', courseId)
    data.append('exam_year', form.year)
    data.append('exam_type', form.examType)
    if (form.tags.trim()) data.append('tags', form.tags.trim())
    return api<{ status: string }>('/api/submissions', { method: 'POST', body: data })
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setNotice('')
    setDuplicate('')
    setShowToast(false)
    if (!validate() || !file) return

    setSubmitting(true)
    try {
      let courseId = form.courseId

      // Admin-created courses are saved directly through the existing admin course API.
      // The subsequent resource upload references that course, so it is published immediately
      // by the same /api/submissions endpoint used by student uploads.
      if (courseId === NEW_COURSE) {
        const created = await api<Course>('/api/courses', {
          method: 'POST',
          body: {
            course_code: form.courseCode.trim(),
            course_name: form.courseName.trim(),
            department_id: form.departmentId,
            semester: Number(form.semester),
            is_active: true,
          },
        })
        courseId = created.id
        setCourses((current) => [...current, created])
        setForm((current) => ({ ...current, courseId: created.id }))
      }

      await uploadToCourse(file, courseId)
      setForm(EMPTY_FORM)
      removeFile()
      setShowToast(true)
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        setDuplicate(error.message)
      } else {
        setNotice(error instanceof Error ? error.message : 'Could not upload the paper. Please try again.')
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
            <span>The resource is now available in StudySync.</span>
          </div>
        </div>
      )}

      <header>
        <h1>Upload PDF</h1>
        <p className="st-sub">
          Upload a resource directly to StudySync. New courses added here are created immediately without admin review.
        </p>
      </header>

      <form className="up-card" onSubmit={handleSubmit} noValidate>
        <h2>Upload a resource</h2>

        <label
          className={`up-drop${dragging ? ' up-drop-active' : ''}${errors.file ? ' up-drop-error' : ''}`}
          onDragOver={(event) => {
            event.preventDefault()
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
            onChange={(event: ChangeEvent<HTMLInputElement>) => pickFile(event.target.files?.[0])}
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
            <select value={form.courseId} onChange={(event) => setField('courseId', event.target.value)}>
              <option value="">Select course</option>
              {courses.map((course) => (
                <option key={course.id} value={course.id}>
                  {course.course_code} · {course.course_name}
                </option>
              ))}
              <option value={NEW_COURSE}>+ Add a new course</option>
            </select>
            {errors.courseId && <em className="up-error">{errors.courseId}</em>}
          </label>

          {form.courseId === NEW_COURSE && (
            <>
              <label className="up-field">
                <span>Course Code</span>
                <input value={form.courseCode} onChange={(event) => setField('courseCode', event.target.value)} placeholder="e.g. CSE301" />
                {errors.courseCode && <em className="up-error">{errors.courseCode}</em>}
              </label>
              <label className="up-field">
                <span>Course Name</span>
                <input value={form.courseName} onChange={(event) => setField('courseName', event.target.value)} placeholder="e.g. Compilers" />
                {errors.courseName && <em className="up-error">{errors.courseName}</em>}
              </label>
              <label className="up-field">
                <span>Department</span>
                <select value={form.departmentId} onChange={(event) => setField('departmentId', event.target.value)}>
                  <option value="">Select department</option>
                  {departments.map((department) => (
                    <option key={department.id} value={department.id}>
                      {department.name}
                    </option>
                  ))}
                </select>
                {errors.departmentId && <em className="up-error">{errors.departmentId}</em>}
              </label>
              <label className="up-field">
                <span>Semester</span>
                <select value={form.semester} onChange={(event) => setField('semester', event.target.value)}>
                  <option value="">Select semester</option>
                  {SEMESTERS.map((semester) => <option key={semester} value={semester}>Semester {semester}</option>)}
                </select>
                {errors.semester && <em className="up-error">{errors.semester}</em>}
              </label>
            </>
          )}

          <label className="up-field">
            <span>Year</span>
            <select value={form.year} onChange={(event) => setField('year', event.target.value)}>
              <option value="">Select year</option>
              {YEARS.map((year) => <option key={year} value={year}>{year}</option>)}
            </select>
            {errors.year && <em className="up-error">{errors.year}</em>}
          </label>

          <label className="up-field">
            <span>Exam Type</span>
            <select value={form.examType} onChange={(event) => setField('examType', event.target.value)}>
              <option value="">Select exam type</option>
              {EXAM_TYPES.map((type) => <option key={type} value={type}>{type}</option>)}
            </select>
            {errors.examType && <em className="up-error">{errors.examType}</em>}
          </label>

          <label className="up-field">
            <span>Topic / Tags</span>
            <input value={form.tags} onChange={(event) => setField('tags', event.target.value)} placeholder="e.g. Trees, Graphs (optional)" />
          </label>
        </div>

        {duplicate && (
          <div className="up-rejected" role="alert">
            <strong>Duplicate upload</strong>
            <span>{duplicate}</span>
          </div>
        )}
        {notice && <p className="up-notice" role="alert">{notice}</p>}

        <div className="up-actions">
          <button type="submit" className="up-submit" disabled={submitting}>
            {submitting ? 'Uploading…' : 'Upload PDF'}
          </button>
        </div>
      </form>
    </div>
  )
}
