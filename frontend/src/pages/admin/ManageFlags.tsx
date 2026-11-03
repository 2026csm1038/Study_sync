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
  resource: { original_filename?: string; exam_year?: number; exam_type?: string }
  reporter: { full_name?: string; email?: string }
}

type ResourceGroup = {
  resource_id: string
  resource: Flag['resource']
  flags: Flag[]
}

const REASONS: Record<string, string> = {
  incorrect_content: 'Incorrect content', duplicate: 'Duplicate',
  poor_quality: 'Poor quality', inappropriate: 'Inappropriate', other: 'Other',
}

export default function ManageFlags() {
  const [flags, setFlags] = useState<Flag[]>([])
  const [filter, setFilter] = useState('open')
  const [expanded, setExpanded] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState<string | null>(null)

  async function load() {
    try {
      const query = filter ? `?status=${filter}` : ''
      setFlags(await api<Flag[]>(`/api/resource-flags${query}`))
      setError('')
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not load reports.') }
  }
  useEffect(() => { void load() }, [filter])

  const groups = useMemo<ResourceGroup[]>(() => {
    const grouped = new Map<string, ResourceGroup>()
    for (const flag of flags) {
      let group = grouped.get(flag.resource_id)
      if (!group) {
        group = { resource_id: flag.resource_id, resource: flag.resource ?? {}, flags: [] }
        grouped.set(flag.resource_id, group)
      }
      group.flags.push(flag)
    }
    return Array.from(grouped.values()).sort((a, b) =>
      (b.flags[0]?.created_at ?? '').localeCompare(a.flags[0]?.created_at ?? '')
    )
  }, [flags])

  async function update(id: string, status: 'resolved' | 'dismissed') {
    setBusy(id)
    try { await api(`/api/resource-flags/${id}`, { method: 'PATCH', body: { status } }); await load() }
    catch (e) { setError(e instanceof Error ? e.message : 'Update failed.') }
    finally { setBusy(null) }
  }

  async function remove(group: ResourceGroup) {
    const filename = group.resource.original_filename ?? 'this resource'
    if (!window.confirm(`Permanently delete “${filename}” from StudySync and Google Drive?`)) return
    setBusy(group.resource_id)
    try {
      await api(`/api/resource-flags/resources/${group.resource_id}`, { method: 'DELETE' })
      if (expanded === group.resource_id) setExpanded(null)
      await load()
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not delete resource.') }
    finally { setBusy(null) }
  }

  return <div className="st-page">
    <h1>Resource Reports</h1>
    <p className="st-sub">Review community reports and take action on flagged resources.</p>
    <label className="flag-filter">Show reports{' '}
      <select value={filter} onChange={e => { setFilter(e.target.value); setExpanded(null) }}>
        <option value="open">Open</option><option value="resolved">Resolved</option>
        <option value="dismissed">Dismissed</option><option value="">All</option>
      </select>
    </label>
    {error && <p role="alert" className="ad-error">{error}</p>}
    {groups.length === 0 ? <p className="st-empty">No reports in this category.</p> :
      <ul className="flag-list">{groups.map(group => {
        const isExpanded = expanded === group.resource_id
        const openCount = group.flags.filter(flag => flag.status === 'open').length
        return <li className="flag-card flag-resource-card" key={group.resource_id}>
          <div className="flag-resource-main">
            <button
              type="button"
              className="flag-resource-toggle"
              aria-expanded={isExpanded}
              onClick={() => setExpanded(isExpanded ? null : group.resource_id)}
            >
              <span className="flag-resource-name">{group.resource.original_filename ?? 'Resource'}</span>
              <span className="flag-count">{group.flags.length} {group.flags.length === 1 ? 'flag' : 'flags'}</span>
              <span className="flag-expand-label">{isExpanded ? 'Hide reporters' : 'View reporters'}</span>
            </button>
            <p>{group.resource.exam_type ?? ''} {group.resource.exam_year ?? ''}</p>
            <small>{openCount} open {openCount === 1 ? 'report' : 'reports'}</small>
            {isExpanded && <div className="flag-reporter-list">
              {group.flags.map(flag => <div className="flag-reporter" key={flag.id}>
                <div className="flag-reporter-info">
                  <strong>{flag.reporter.full_name ?? flag.reporter.email ?? 'Unknown user'}</strong>
                  {flag.reporter.full_name && flag.reporter.email && <small>{flag.reporter.email}</small>}
                  <span><b>Reason:</b> {REASONS[flag.reason] ?? flag.reason}</span>
                  {flag.details && <span><b>Details:</b> {flag.details}</span>}
                  <small>{new Date(flag.created_at).toLocaleString()} · {flag.status}</small>
                </div>
                <div className="flag-actions">
                  {flag.status === 'open' ? <>
                    <button disabled={busy === flag.id} onClick={() => void update(flag.id, 'resolved')}>Mark resolved</button>
                    <button disabled={busy === flag.id} onClick={() => void update(flag.id, 'dismissed')}>Dismiss</button>
                  </> : <span>{flag.status}</span>}
                </div>
              </div>)}
            </div>}
          </div>
          <div className="flag-actions flag-resource-actions">
            <button disabled={busy === group.resource_id} className="flag-delete" onClick={() => void remove(group)}>Delete resource</button>
          </div>
        </li>
      })}</ul>}
  </div>
}
