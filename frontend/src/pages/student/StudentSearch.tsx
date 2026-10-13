import {
  ChevronDown,
  CircleHelp,
  ClipboardList,
  FileCheck,
  FileText,
  Search,
  type LucideIcon,
} from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { api } from '../../lib/api'

/* ------------------------------------------------------------------ types -- */

type Course = { id: string; course_code: string; course_name: string }

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
const CONTENT_TYPES = ['Previous year paper', 'Solution', 'Assignment', 'Quiz']
const YEARS = ['2026', '2025', '2024', '2023']
const SEMESTERS = ['1', '2', '3', '4', '5', '6', '7', '8']
const EXAM_TYPES = ['Midsem', 'Endsem']
const DEPARTMENTS = ['CSE', 'Bio-Medical', 'EEE']

const EMPTY_FILTERS: SearchFilters = {
  contentType: '',
  courseId: '',
  year: '',
  semester: '',
  examType: '',
  department: '',
}

const TYPE_STYLE: Record<string, { icon: LucideIcon; className: string }> = {
  'Previous year paper': { icon: FileText, className: 'st-tag-paper' },
  Solution: { icon: FileCheck, className: 'st-tag-solution' },
  Assignment: { icon: ClipboardList, className: 'st-tag-assignment' },
  Quiz: { icon: CircleHelp, className: 'st-tag-quiz' },
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
  const style = TYPE_STYLE[item.resource_type] ?? TYPE_STYLE['Previous year paper']
  const Icon = style.icon
  const meta = [
    item.course_code,
    item.semester ? `Semester ${item.semester}` : null,
    item.academic_year,
    item.exam_type,
  ]
    .filter(Boolean)
    .join(' • ')

  return (
    <li className="st-result">
      <div className={`st-result-icon ${style.className}`}>
        <Icon size={22} aria-hidden="true" />
      </div>
      <div className="st-result-text">
        <strong>{item.title}</strong>
        <span>{meta}</span>
      </div>
      <span className={`st-chip ${style.className}`}>{item.resource_type}</span>
      <button
        type="button"
        className="st-view"
        disabled={!item.google_drive_url}
        onClick={() => window.open(item.google_drive_url ?? '', '_blank', 'noopener')}
      >
        View
      </button>
    </li>
  )
}

/* ------------------------------------------------------------------- page -- */

/** Page 3: Student Search. UI only; the search engine is plugged in at handleSearch(). */
export default function StudentSearch() {
  const [query, setQuery] = useState('')
  const [filters, setFilters] = useState<SearchFilters>(EMPTY_FILTERS)
  const [courses, setCourses] = useState<Course[]>([])
  const [results, setResults] = useState<ResourceResult[]>([])
  const [searchedFor, setSearchedFor] = useState<string | null>(null)

  // Existing endpoint: any logged-in user can list active courses.
  useEffect(() => {
    api<Course[]>('/api/courses')
      .then(setCourses)
      .catch(() => setCourses([]))
  }, [])

  function setFilter(key: keyof SearchFilters, value: string) {
    setFilters((prev) => ({ ...prev, [key]: value }))
  }

  function handleSearch(e: FormEvent) {
    e.preventDefault()
    setSearchedFor(query.trim())
    // TODO (search engine): call the search endpoint with `query` and `filters`,
    // then call setResults(<response>) with items shaped like ResourceResult.
    setResults([])
  }

  const asOptions = (values: string[], prefix = '') =>
    values.map((v) => ({ value: v, label: prefix + v }))

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
          options={asOptions(DEPARTMENTS)}
          onChange={(v) => setFilter('department', v)}
        />
      </section>

      <section className="st-results" aria-live="polite">
        {searchedFor === null ? (
          <p className="st-empty">Search for a course, year or topic to see resources here.</p>
        ) : (
          <>
            <p className="st-count">
              Showing {results.length} results{searchedFor ? ` for '${searchedFor}'` : ''}
            </p>
            {results.length > 0 && (
              <ul className="st-result-list">
                {results.map((item) => (
                  <ResultRow key={item.id} item={item} />
                ))}
              </ul>
            )}
          </>
        )}
      </section>
    </div>
  )
}
