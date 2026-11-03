import { AlertTriangle, ChevronDown, ChevronUp, GraduationCap, Trash2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { api } from '../../lib/api'

type Flag = {
  id: string
  resource_id: string
  reporter_id: string
  reason: string
  details: string | null
  status: 'open' | 'resolved' | 'dismissed'
  created_at: string
  /** 1 for a student's report, 5 for a professor's (set by the server). */
  weight: number
  resource: { original_filename?: string; exam_year?: number; exam_type?: string }
  reporter: { full_name?: string; email?: string; role?: string }
}

type ResourceGroup = {
  resource_id: string
  resource: Flag['resource']
  flags: Flag[]
  openCount: number
  /** Sum of the weights of the OPEN reports: this is the priority score. */
  score: number
  facultyFlagged: boolean
  latest: string
}

const REASONS: Record<string, string> = {
  incorrect_content: 'Incorrect content',
  duplicate: 'Duplicate',
  poor_quality: 'Poor quality',
  inappropriate: 'Inappropriate',
  other: 'Other',
}

const isFaculty = (flag: Flag) => flag.reporter.role === 'professor' || flag.reporter.role === 'admin'

/** Score at or above this is shown as High priority. A single professor report (5) is enough. */
const HIGH_PRIORITY = 5

function priorityOf(score: number): 'high' | 'medium' | 'low' {
  if (score >= HIGH_PRIORITY) return 'high'
  return score >= 3 ? 'medium' : 'low'
}

const PRIORITY_LABEL = { high: 'High priority', medium: 'Medium priority', low: 'Low priority' }

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}

export default function ManageFlags() {
  const [flags, setFlags] = useState<Flag[]>([])
  const [filter, setFilter] = useState('open')
  const [expanded, setExpanded] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  async function load() {
    try {
      const query = filter ? `?status=${filter}` : ''
      setFlags(await api<Flag[]>(`/api/resource-flags${query}`))
      setError('')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load reports.')
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => {
    setLoading(true)
    void load()
  }, [filter])

  // One row per resource, the most urgent first: highest score, then the most recently reported.
  const groups = useMemo<ResourceGroup[]>(() => {
    const grouped = new Map<string, ResourceGroup>()
    for (const flag of flags) {
      let group = grouped.get(flag.resource_id)
      if (!group) {
        group = {
          resource_id: flag.resource_id,
          resource: flag.resource ?? {},
          flags: [],
          openCount: 0,
          score: 0,
          facultyFlagged: false,
          latest: '',
        }
        grouped.set(flag.resource_id, group)
      }
      group.flags.push(flag)
      if (flag.status === 'open') {
        group.openCount += 1
        group.score += flag.weight ?? 1
        if (isFaculty(flag)) group.facultyFlagged = true
      }
      if (flag.created_at > group.latest) group.latest = flag.created_at
    }
    return Array.from(grouped.values()).sort(
      (a, b) => b.score - a.score || b.latest.localeCompare(a.latest),
    )
  }, [flags])

  const highPriority = groups.filter((g) => priorityOf(g.score) === 'high').length
  const facultyCount = groups.filter((g) => g.facultyFlagged).length
  const openReports = groups.reduce((n, g) => n + g.openCount, 0)

  async function update(id: string, status: 'resolved' | 'dismissed') {
    setBusy(id)
    try {
      await api(`/api/resource-flags/${id}`, { method: 'PATCH', body: { status } })
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Update failed.')
    } finally {
      setBusy(null)
    }
  }

  async function remove(group: ResourceGroup) {
    const filename = group.resource.original_filename ?? 'this resource'
    if (!window.confirm(`Permanently delete “${filename}” from StudySync and Google Drive?`)) return
    setBusy(group.resource_id)
    try {
      await api(`/api/resource-flags/resources/${group.resource_id}`, { method: 'DELETE' })
      if (expanded === group.resource_id) setExpanded(null)
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not delete resource.')
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="st-page">
      <header className="fl-header">
        <div>
          <h1>Resource Reports</h1>
          <p className="st-sub">
            Flagged resources, most urgent first. A student's report counts 1 point; a professor's
            report counts 5.
          </p>
        </div>
        <label className="fl-filter">
          <span>Status</span>
          <select
            value={filter}
            onChange={(e) => {
              setFilter(e.target.value)
              setExpanded(null)
            }}
          >
            <option value="open">Open</option>
            <option value="resolved">Resolved</option>
            <option value="dismissed">Dismissed</option>
            <option value="">All</option>
          </select>
        </label>
      </header>

      <section className="fl-stats" aria-label="Report summary">
        <div className="fl-stat">
          <strong>{groups.length}</strong>
          <span>Flagged resources</span>
        </div>
        <div className="fl-stat fl-stat-high">
          <strong>{highPriority}</strong>
          <span>High priority</span>
        </div>
        <div className="fl-stat">
          <strong>{facultyCount}</strong>
          <span>Reported by faculty</span>
        </div>
        <div className="fl-stat">
          <strong>{openReports}</strong>
          <span>Open reports</span>
        </div>
      </section>

      {error && (
        <p role="alert" className="ad-error">
          {error}
        </p>
      )}

      {loading ? (
        <p className="st-empty">Loading reports…</p>
      ) : groups.length === 0 ? (
        <div className="fl-empty">
          <AlertTriangle size={28} aria-hidden="true" />
          <strong>No reports here</strong>
          <span>Nothing has been flagged in this category.</span>
        </div>
      ) : (
        <ul className="fl-list">
          {groups.map((group) => {
            const isExpanded = expanded === group.resource_id
            const level = priorityOf(group.score)
            return (
              <li className={`fl-card fl-card-${filter === 'open' || filter === '' ? level : 'low'}`} key={group.resource_id}>
                <div className="fl-row">
                  <div className="fl-score" title="Priority score: sum of open report weights">
                    <strong>{group.score}</strong>
                    <span>score</span>
                  </div>

                  <div className="fl-main">
                    <div className="fl-title">
                      <h2>{group.resource.original_filename ?? 'Resource'}</h2>
                      {group.openCount > 0 && (
                        <span className={`fl-badge fl-badge-${level}`}>{PRIORITY_LABEL[level]}</span>
                      )}
                      {group.facultyFlagged && (
                        <span className="fl-badge fl-badge-faculty">
                          <GraduationCap size={13} aria-hidden="true" /> Faculty flagged
                        </span>
                      )}
                    </div>
                    <p className="fl-meta">
                      {[group.resource.exam_type, group.resource.exam_year].filter(Boolean).join(' · ') || '—'}
                      <span aria-hidden="true"> · </span>
                      {group.flags.length} {group.flags.length === 1 ? 'report' : 'reports'}
                      <span aria-hidden="true"> · </span>
                      {group.openCount} open
                      <span aria-hidden="true"> · </span>
                      last reported {formatDate(group.latest)}
                    </p>
                  </div>

                  <div className="fl-actions">
                    <button
                      type="button"
                      className="fl-btn"
                      aria-expanded={isExpanded}
                      onClick={() => setExpanded(isExpanded ? null : group.resource_id)}
                    >
                      {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                      {isExpanded ? 'Hide reports' : 'View reports'}
                    </button>
                    <button
                      type="button"
                      className="fl-btn fl-btn-danger"
                      disabled={busy === group.resource_id}
                      onClick={() => void remove(group)}
                    >
                      <Trash2 size={16} /> Delete
                    </button>
                  </div>
                </div>

                {isExpanded && (
                  <div className="fl-reports">
                    {[...group.flags]
                      .sort((a, b) => (b.weight ?? 1) - (a.weight ?? 1) || b.created_at.localeCompare(a.created_at))
                      .map((flag) => (
                        <div className="fl-report" key={flag.id}>
                          <div className="fl-report-info">
                            <div className="fl-reporter">
                              <strong>{flag.reporter.full_name ?? flag.reporter.email ?? 'Unknown user'}</strong>
                              {isFaculty(flag) ? (
                                <span className="fl-role fl-role-faculty">Professor · +{flag.weight}</span>
                              ) : (
                                <span className="fl-role">Student · +{flag.weight ?? 1}</span>
                              )}
                            </div>
                            {flag.reporter.email && flag.reporter.full_name && (
                              <small>{flag.reporter.email}</small>
                            )}
                            <div className="fl-reason">
                              <span className="fl-chip">{REASONS[flag.reason] ?? flag.reason}</span>
                              <small>{formatDate(flag.created_at)}</small>
                            </div>
                            {flag.details && <p className="fl-details">“{flag.details}”</p>}
                          </div>
                          <div className="fl-report-actions">
                            {flag.status === 'open' ? (
                              <>
                                <button
                                  type="button"
                                  className="fl-btn"
                                  disabled={busy === flag.id}
                                  onClick={() => void update(flag.id, 'resolved')}
                                >
                                  Mark resolved
                                </button>
                                <button
                                  type="button"
                                  className="fl-btn"
                                  disabled={busy === flag.id}
                                  onClick={() => void update(flag.id, 'dismissed')}
                                >
                                  Dismiss
                                </button>
                              </>
                            ) : (
                              <span className={`fl-status fl-status-${flag.status}`}>{flag.status}</span>
                            )}
                          </div>
                        </div>
                      ))}
                  </div>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
