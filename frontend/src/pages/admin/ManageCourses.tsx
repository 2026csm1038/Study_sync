import { useMemo, useEffect, useState, type FormEvent } from 'react'
import {
  BookOpen,
  Check,
  ChevronDown,
  GraduationCap,
  Pencil,
  Plus,
  Search,
  Trash2,
  X,
} from 'lucide-react'
import { api, ApiError } from '../../lib/api'

type Course = {
  id: string
  course_code: string
  course_name: string
  department_id: string
  semester: number
  description: string | null
  is_active: boolean
  created_at: string | null
  updated_at: string | null
}

type Department = {
  id: string
  name: string
  code: string | null
}

type CourseForm = {
  course_code: string
  course_name: string
  department_id: string
  semester: string
  is_active: boolean
}

type ModalState =
  | { type: 'add' }
  | { type: 'edit'; course: Course }
  | { type: 'delete'; course: Course }
  | null

const EMPTY_FORM: CourseForm = {
  course_code: '',
  course_name: '',
  department_id: '',
  semester: '',
  is_active: true,
}

const errorMessage = (error: unknown) =>
  error instanceof ApiError ? error.message : 'Could not load courses. Please try again.'

export default function ManageCourses() {
  const [courses, setCourses] = useState<Course[]>([])
  const [departments, setDepartments] = useState<Department[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [modal, setModal] = useState<ModalState>(null)
  const [form, setForm] = useState<CourseForm>(EMPTY_FORM)
  const [search, setSearch] = useState('')
  const [departmentFilter, setDepartmentFilter] = useState('')
  const [semesterFilter, setSemesterFilter] = useState('')
  const [toast, setToast] = useState('')

  useEffect(() => {
    let cancelled = false

    async function loadPageData() {
      setLoading(true)
      setError('')
      try {
        // Existing read-only endpoints. include_inactive=true is permitted for admins.
        const [courseRows, departmentRows] = await Promise.all([
          api<Course[]>('/api/courses?include_inactive=true'),
          api<Department[]>('/api/departments'),
        ])
        if (!cancelled) {
          setCourses(courseRows)
          setDepartments(departmentRows)
        }
      } catch (err) {
        if (!cancelled) setError(errorMessage(err))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void loadPageData()
    return () => { cancelled = true }
  }, [])

  const departmentById = useMemo(
    () => new Map(departments.map((department) => [department.id, department])),
    [departments],
  )

  const filteredCourses = useMemo(() => {
    const term = search.trim().toLowerCase()
    return courses.filter((course) => {
      const department = departmentById.get(course.department_id)
      const matchesSearch = !term || [
        course.course_code,
        course.course_name,
        department?.name ?? '',
        department?.code ?? '',
      ].some((value) => value.toLowerCase().includes(term))

      return matchesSearch &&
        (!departmentFilter || course.department_id === departmentFilter) &&
        (!semesterFilter || String(course.semester) === semesterFilter)
    })
  }, [courses, departmentById, search, departmentFilter, semesterFilter])

  const activeCount = courses.filter((course) => course.is_active).length

  function notify(message: string) {
    setToast(message)
    window.setTimeout(() => setToast(''), 3000)
  }

  function openAdd() {
    setForm(EMPTY_FORM)
    setModal({ type: 'add' })
  }

  function openEdit(course: Course) {
    setForm({
      course_code: course.course_code,
      course_name: course.course_name,
      department_id: course.department_id,
      semester: String(course.semester),
      is_active: course.is_active,
    })
    setModal({ type: 'edit', course })
  }

  function closeModal() {
    setModal(null)
  }

  // UI-only: Add/Edit/Delete do not call the backend and do not persist to Supabase.
  function saveCourse(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (modal?.type === 'add') {
      const nextCourse: Course = {
        id: `ui-${Date.now()}`,
        course_code: form.course_code.trim().toUpperCase(),
        course_name: form.course_name.trim(),
        department_id: form.department_id,
        semester: Number(form.semester),
        description: null,
        is_active: form.is_active,
        created_at: null,
        updated_at: null,
      }
      setCourses((current) => [...current, nextCourse])
      notify('Course added')
    } else if (modal?.type === 'edit') {
      setCourses((current) => current.map((course) =>
        course.id === modal.course.id
          ? {
              ...course,
              course_code: form.course_code.trim().toUpperCase(),
              course_name: form.course_name.trim(),
              department_id: form.department_id,
              semester: Number(form.semester),
              is_active: form.is_active,
            }
          : course,
      ))
      notify('Course updated')
    }
    closeModal()
  }

  function deleteCourse() {
    if (modal?.type !== 'delete') return
    setCourses((current) => current.filter((course) => course.id !== modal.course.id))
    notify('Course removed')
    closeModal()
  }

  return (
    <div className="st-page mc-page">
      {toast && (
        <div className="mc-toast" role="status">
          <Check size={18} aria-hidden="true" />
          <span>{toast}</span>
        </div>
      )}

      <header className="mc-header">
        <div>
          <h1>Manage Courses</h1>
          <p className="st-sub">Manage the courses available on StudySync.</p>
        </div>
        <button type="button" className="ad-btn ad-btn-primary mc-add-button" onClick={openAdd}>
          <Plus size={17} aria-hidden="true" />
          Add Course
        </button>
      </header>

      <section className="mc-toolbar" aria-label="Filter courses">
        <label className="mc-search">
          <Search size={18} aria-hidden="true" />
          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search courses..."
            aria-label="Search courses"
          />
        </label>
        <label className="mc-select">
          <span className="sr-only">Department</span>
          <select value={departmentFilter} onChange={(event) => setDepartmentFilter(event.target.value)}>
            <option value="">All Departments</option>
            {departments.map((department) => (
             <option key={department.id} value={department.id}>
              {department.code}
            </option>
            ))}
          </select>
          <ChevronDown size={16} aria-hidden="true" />
        </label>
        <label className="mc-select">
          <span className="sr-only">Semester</span>
          <select value={semesterFilter} onChange={(event) => setSemesterFilter(event.target.value)}>
            <option value="">All Semesters</option>
            {Array.from({ length: 12 }, (_, index) => String(index + 1)).map((semester) => (
              <option key={semester} value={semester}>Semester {semester}</option>
            ))}
          </select>
          <ChevronDown size={16} aria-hidden="true" />
        </label>
        <div className="mc-toolbar-count">
          <strong>{filteredCourses.length}</strong>
          <span>courses</span>
        </div>
      </section>

      <section className="mc-table-card" aria-label="All courses">
        <div className="mc-table-heading">
          <div>
            <h2>All Courses</h2>
            <p>{activeCount} active · {courses.length - activeCount} inactive</p>
          </div>
          <span className="mc-total-pill">{courses.length} total</span>
        </div>

        {loading ? (
          <div className="mc-empty" role="status">
            <BookOpen size={28} aria-hidden="true" />
            <strong>Loading courses…</strong>
            <span>Fetching the course catalogue.</span>
          </div>
        ) : error ? (
          <div className="mc-load-error" role="alert">
            <strong>Unable to load courses</strong>
            <span>{error}</span>
            <button type="button" className="mc-retry-button" onClick={() => window.location.reload()}>Try again</button>
          </div>
        ) : filteredCourses.length === 0 ? (
          <div className="mc-empty">
            <BookOpen size={28} aria-hidden="true" />
            <strong>{courses.length === 0 ? 'No courses available' : 'No courses found'}</strong>
            <span>{courses.length === 0 ? 'Courses added to the catalogue will appear here.' : 'Try changing your search or filters.'}</span>
          </div>
        ) : (
          <div className="mc-table-scroll">
            <table className="mc-table">
              <thead>
                <tr>
                  <th>Course Code</th>
                  <th>Course Name</th>
                  <th>Department</th>
                  <th>Semester</th>
                  <th>Status</th>
                  <th className="mc-actions-heading">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredCourses.map((course) => (
                  <tr key={course.id}>
                    <td><strong className="mc-course-code">{course.course_code}</strong></td>
                    <td><strong className="mc-course-name">{course.course_name}</strong></td>
                    <td>{departmentById.get(course.department_id)?.code ?? departmentById.get(course.department_id)?.name ?? '—'}</td>
                    <td>{course.semester}</td>
                    <td>
                      <span className={`mc-status ${course.is_active ? 'mc-status-active' : 'mc-status-inactive'}`}>
                        {course.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td>
                      <div className="mc-row-actions">
                        <button type="button" className="mc-icon-action mc-edit-action" onClick={() => openEdit(course)} aria-label={`Edit ${course.course_code}`} title="Edit course">
                          <Pencil size={15} aria-hidden="true" />
                          <span>Edit</span>
                        </button>
                        <button type="button" className="mc-icon-action mc-delete-action" onClick={() => setModal({ type: 'delete', course })} aria-label={`Delete ${course.course_code}`} title="Delete course">
                          <Trash2 size={15} aria-hidden="true" />
                          <span>Delete</span>
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {modal && (
        <div className="mc-overlay" onMouseDown={(event) => {
          if (event.target === event.currentTarget) closeModal()
        }}>
          {modal.type === 'delete' ? (
            <section className="mc-dialog mc-delete-dialog" role="dialog" aria-modal="true" aria-labelledby="mc-delete-title">
              <div className="mc-dialog-icon mc-delete-dialog-icon"><Trash2 size={22} aria-hidden="true" /></div>
              <button type="button" className="mc-dialog-close" onClick={closeModal} aria-label="Close dialog"><X size={19} /></button>
              <h2 id="mc-delete-title">Delete course?</h2>
              <p>Are you sure you want to delete <strong>{modal.course.course_code} — {modal.course.course_name}</strong>? This action cannot be undone.</p>
              <div className="mc-dialog-actions">
                <button type="button" className="mc-modal-button mc-modal-secondary" onClick={closeModal}>Cancel</button>
                <button type="button" className="mc-modal-button mc-modal-danger" onClick={deleteCourse}>
                  <Trash2 size={16} aria-hidden="true" /> Delete Course
                </button>
              </div>
            </section>
          ) : (
            <section className="mc-dialog" role="dialog" aria-modal="true" aria-labelledby="mc-form-title">
              <div className="mc-dialog-header">
                <div className="mc-dialog-heading-icon"><GraduationCap size={21} aria-hidden="true" /></div>
                <div>
                  <h2 id="mc-form-title">{modal.type === 'add' ? 'Add New Course' : 'Edit Course'}</h2>
                  <p>{modal.type === 'add' ? 'Add a new course to the StudySync academic catalog.' : 'Update the details of this course.'}</p>
                </div>
                <button type="button" className="mc-dialog-close" onClick={closeModal} aria-label="Close dialog"><X size={19} /></button>
              </div>

              <form className="mc-course-form" onSubmit={saveCourse}>
                <label className="mc-field">
                  <span>Course Code</span>
                  <input required value={form.course_code} onChange={(event) => setForm({ ...form, course_code: event.target.value.toUpperCase() })} placeholder="e.g. CSE205" />
                </label>
                <label className="mc-field">
                  <span>Course Name</span>
                  <input required value={form.course_name} onChange={(event) => setForm({ ...form, course_name: event.target.value })} placeholder="e.g. Computer Organization" />
                </label>
                <label className="mc-field">
                  <span>Department</span>
                  <select required value={form.department_id} onChange={(event) => setForm({ ...form, department_id: event.target.value })}>
                    <option value="">Select department</option>
                    {departments.map((department) => (
                <option key={department.id} value={department.id}>
                  {department.code}
                </option>
                    ))}
                  </select>
                </label>
                <label className="mc-field">
                  <span>Semester</span>
                  <select required value={form.semester} onChange={(event) => setForm({ ...form, semester: event.target.value })}>
                    <option value="">Select semester</option>
                    {Array.from({ length: 12 }, (_, index) => String(index + 1)).map((semester) => (
                      <option key={semester} value={semester}>Semester {semester}</option>
                    ))}
                  </select>
                </label>
                <div className="mc-status-field">
                  <span>Status</span>
                  <label className="mc-switch">
                    <input type="checkbox" checked={form.is_active} onChange={(event) => setForm({ ...form, is_active: event.target.checked })} />
                    <span className="mc-switch-track" aria-hidden="true"><span /></span>
                    <strong>{form.is_active ? 'Active' : 'Inactive'}</strong>
                  </label>
                </div>
                <div className="mc-dialog-actions">
                  <button type="button" className="mc-modal-button mc-modal-secondary" onClick={closeModal}>Cancel</button>
                  <button type="submit" className="mc-modal-button mc-modal-primary">
                    {modal.type === 'add' ? <Plus size={16} aria-hidden="true" /> : <Check size={16} aria-hidden="true" />}
                    {modal.type === 'add' ? 'Add Course' : 'Save Changes'}
                  </button>
                </div>
              </form>
            </section>
          )}
        </div>
      )}
    </div>
  )
}
