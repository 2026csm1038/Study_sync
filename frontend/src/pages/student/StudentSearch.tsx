import {
  ChevronDown,
  CircleHelp,
  ClipboardList,
  FileCheck,
  FileText,
  Search,
  type LucideIcon,
} from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { api, apiBlob } from '../../lib/api'

/* ------------------------------------------------------------------ types -- */

type Course = { id: string; course_code: string; course_name: string }

type Department = { id: string; name: string; code: string | null }

export type SearchFilters = {
  contentType: string
  courseId: string
  year: string
  semester: string
  examType: string
  department: string
}

/** One row of the results list. Mirrors the `resources` table in the schema slide. */
export type ResourceResult = {
  id: string
  title: string
  resource_type: string
  course_code?: string
  semester?: number | null
  academic_year?: number | null
  exam_type?: string | null
  google_drive_url?: string | null
}

/* -------------------------------------------------------- filter options -- */
// Static lists taken from the wireframe. Change them here only.
const CONTENT_TYPES = ['Midsem', 'Endsem', 'Lab Test', 'Tutorials']
const YEARS = ['2026', '2025', '2024', '2023']
const SEMESTERS = ['1', '2', '3', '4', '5', '6', '7', '8']
const EXAM_TYPES = ['Midsem', 'Endsem', 'Lab Test', 'Tutorials']

const PAGE_SIZE = 50 // papers per request; "Load more" fetches the next 50

const EMPTY_FILTERS: SearchFilters = {
  contentType: '',
  courseId: '',
  year: '',
  semester: '',
  examType: '',
  department: '',
}

const TYPE_STYLE: Record<string, { icon: LucideIcon; className: string }> = {
  Midsem: { icon: FileText, className: 'st-tag-paper' },
  Endsem: { icon: FileCheck, className: 'st-tag-solution' },
  'Lab Test': { icon: ClipboardList, className: 'st-tag-assignment' },
  Tutorials: { icon: CircleHelp, className: 'st-tag-quiz' },
}

/* ------------------------------------------------------------- components -- */

function FilterSelect(props: {
  label: string
  allLabel: string
  value: string
  options: { value: string; label: string }[]
  onChange: (value: string) => void
}) {
  return (
    <label className="st-filter">
      <span>{props.label}</span>
      <div className="st-select">
        <select value={props.value} onChange={(e) => props.onChange(e.target.value)}>
          <option value="">{props.allLabel}</option>
          {props.options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <ChevronDown size={16} aria-hidden="true" />
      </div>
    </label>
  )
}


function ResultRow({ item }: { item: ResourceResult }) {
  const style = TYPE_STYLE[item.resource_type] ?? TYPE_STYLE.Midsem
  const Icon = style.icon
  const [opening, setOpening] = useState(false)

  const meta = [
    item.course_code,
    item.semester ? `Semester ${item.semester}` : null,
    item.academic_year,
    item.exam_type,
  ]
    .filter(Boolean)
    .join(' • ')

  async function handleView() {
    // Open a tab immediately so the browser doesn't block it after the fetch.
    const tab = window.open('about:blank', '_blank')
    if (!tab) {
      alert('Please allow pop-ups for StudySync to view PDFs.')
      return
    }

    tab.opener = null
    setOpening(true)

    let objectUrl: string | undefined

    try {
      const blob = await apiBlob(
        `/api/resources/${encodeURIComponent(item.id)}/view`
      )

      objectUrl = URL.createObjectURL(blob)
      tab.location.href = objectUrl

      // Keep the blob URL available while the PDF loads.
      window.setTimeout(() => {
        if (objectUrl) URL.revokeObjectURL(objectUrl)
      }, 60_000)
    } catch (error) {
      tab.close()
      console.error('Could not open resource:', error)
      alert(error instanceof Error ? error.message : 'Could not open this PDF.')
    } finally {
      setOpening(false)
    }
  }

  return (
    <li className="st-result">
      <div className={`st-result-icon ${style.className}`}>
        <Icon size={22} aria-hidden="true" />
      </div>

      <div className="st-result-text">
        <strong>{item.title}</strong>
        <span>{meta}</span>
      </div>

      <span className={`st-chip ${style.className}`}>
        {item.resource_type}
      </span>

      <button
        type="button"
        className="st-view"
        disabled={opening}
        onClick={handleView}
      >
        {opening ? 'Opening…' : 'View'}
      </button>
    </li>
  )
}

/* ------------------------------------------------------------------- page -- */

/**
 * Page 3: Student Search.
 * Opens with the newest papers already listed. The list refreshes as soon as a dropdown changes
 * or Search is pressed, and "Load more" adds the next 50.
 */
export default function StudentSearch() {
  const [query, setQuery] = useState('') // what is typed in the box
  const [appliedQuery, setAppliedQuery] = useState('') // the text the list is currently filtered by
  const [filters, setFilters] = useState<SearchFilters>(EMPTY_FILTERS)
  const [courses, setCourses] = useState<Course[]>([])
  const [departments, setDepartments] = useState<Department[]>([])
  const [results, setResults] = useState<ResourceResult[]>([])
  const [hasMore, setHasMore] = useState(false)
  const [isSearching, setIsSearching] = useState(true)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)
  const latestRequest = useRef(0)

  // Existing endpoint: any logged-in user can list active courses.
  useEffect(() => {
    api<Course[]>('/api/courses')
      .then(setCourses)
      .catch(() => setCourses([]))

    // Existing endpoint: any logged-in user can list departments.
    api<Department[]>('/api/departments')
      .then(setDepartments)
      .catch(() => setDepartments([]))
  }, [])

  function setFilter(key: keyof SearchFilters, value: string) {
    setFilters((prev) => ({ ...prev, [key]: value }))
  }

  /** Fetch one page. offset 0 replaces the list; a later offset adds to it. */
  async function loadPage(offset: number, text: string, current: SearchFilters) {
    const requestId = ++latestRequest.current
    if (offset === 0) {
      setIsSearching(true)
      setSearchError(null)
    } else {
      setIsLoadingMore(true)
    }

    // Only the boxes that are filled in are sent; the backend combines them with AND.
    const params = new URLSearchParams()
    if (text) params.set('q', text)
    if (current.contentType) params.set('content_type', current.contentType)
    if (current.courseId) params.set('course_id', current.courseId)
    if (current.year) params.set('exam_year', current.year)
    if (current.semester) params.set('semester', current.semester)
    if (current.examType) params.set('exam_type', current.examType)
    if (current.department) params.set('department_id', current.department)
    params.set('limit', String(PAGE_SIZE))
    if (offset) params.set('offset', String(offset))

    try {
      const data = await api<ResourceResult[]>(`/api/resources?${params.toString()}`)
      if (requestId !== latestRequest.current) return // a newer search started; drop this answer
      setResults((prev) => {
        if (offset === 0) return data
        const seen = new Set(prev.map((item) => item.id)) // new uploads can shift the pages
        return [...prev, ...data.filter((item) => !seen.has(item.id))]
      })
      setHasMore(data.length === PAGE_SIZE)
    } catch (error) {
      if (requestId !== latestRequest.current) return
      console.error('Resource search failed:', error)
      if (offset === 0) {
        setResults([])
        setHasMore(false)
      }
      setSearchError(error instanceof Error ? error.message : 'Search failed. Please try again.')
    } finally {
      if (requestId === latestRequest.current) {
        setIsSearching(false)
        setIsLoadingMore(false)
      }
    }
  }

  // On open, and whenever a dropdown or the applied search text changes: show the first page.
  useEffect(() => {
    void loadPage(0, appliedQuery, filters)
  }, [filters, appliedQuery]) // eslint-disable-line react-hooks/exhaustive-deps

  function handleSearch(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const text = query.trim()
    if (text === appliedQuery) void loadPage(0, text, filters) // same text: search again
    else setAppliedQuery(text) // new text: the effect above reloads the list
  }

  const asOptions = (values: string[], prefix = '') =>
    values.map((v) => ({ value: v, label: prefix + v }))

  const isFiltering = Boolean(appliedQuery) || Object.values(filters).some(Boolean)

  return (
    <div className="st-page">
      <header>
        <h1>Search StudySync</h1>
        <p className="st-sub">Find the academic resource you need.</p>
      </header>

      <form className="st-searchbar" onSubmit={handleSearch}>
        <div className="st-input">
          <Search size={20} aria-hidden="true" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by course, year or topic, e.g. DSA Midsem 2024"
            aria-label="Search resources"
          />
        </div>
        <button type="submit" className="st-search-btn">
          Search
        </button>
      </form>

      <section className="st-filters" aria-label="Filters">
        <FilterSelect
          label="Content Type"
          allLabel="All Content"
          value={filters.contentType}
          options={asOptions(CONTENT_TYPES)}
          onChange={(v) => setFilter('contentType', v)}
        />
        <FilterSelect
          label="Course"
          allLabel="All Courses"
          value={filters.courseId}
          options={courses.map((c) => ({ value: c.id, label: `${c.course_code} · ${c.course_name}` }))}
          onChange={(v) => setFilter('courseId', v)}
        />
        <FilterSelect
          label="Year"
          allLabel="All Years"
          value={filters.year}
          options={asOptions(YEARS)}
          onChange={(v) => setFilter('year', v)}
        />
        <FilterSelect
          label="Semester"
          allLabel="All Semesters"
          value={filters.semester}
          options={asOptions(SEMESTERS, 'Sem-')}
          onChange={(v) => setFilter('semester', v)}
        />
        <FilterSelect
          label="Exam Type"
          allLabel="All Exam Types"
          value={filters.examType}
          options={asOptions(EXAM_TYPES)}
          onChange={(v) => setFilter('examType', v)}
        />
        <FilterSelect
          label="Department"
          allLabel="All Departments"
          value={filters.department}
          options={departments.map((d) => ({ value: d.id, label: d.code ?? d.name }))}
          onChange={(v) => setFilter('department', v)}
        />
      </section>

      <section className="st-results" aria-live="polite" aria-busy={isSearching}>
        {searchError ? (
          <p className="st-empty" role="alert">
            {searchError}
          </p>
        ) : isSearching && results.length === 0 ? (
          <p className="st-empty" role="status">
            Loading resources…
          </p>
        ) : results.length === 0 ? (
          <p className="st-empty">
            {isFiltering
              ? 'No resources found. Try another search term or different filters.'
              : 'No resources have been published yet.'}
          </p>
        ) : (
          <>
            <p className="st-count">
              Showing {results.length} results
              {appliedQuery ? ` for '${appliedQuery}'` : ''}
            </p>
            <ul className={`st-result-list${isSearching ? ' st-busy' : ''}`}>
              {results.map((item) => (
                <ResultRow key={item.id} item={item} />
              ))}
            </ul>
            {hasMore && (
              <button
                type="button"
                className="st-more"
                disabled={isLoadingMore}
                onClick={() => void loadPage(results.length, appliedQuery, filters)}
              >
                {isLoadingMore ? 'Loading…' : 'Load more'}
              </button>
            )}
          </>
        )}
      </section>
    </div>
  )
}
