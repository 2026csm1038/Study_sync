import { useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { api } from './api'

/** The response of GET /api/admin/reports/summary. */
export type ReportSummary = {
  open_flags: number
  flagged_resources: number
  needs_attention: number // resources whose open flags weigh `threshold` or more
  threshold: number
}

/** Report numbers for the admin. Reloads when the admin opens another page, and every minute. */
export function useReportSummary(): ReportSummary | null {
  const [summary, setSummary] = useState<ReportSummary | null>(null)
  const { pathname } = useLocation()

  useEffect(() => {
    let active = true
    const load = () =>
      api<ReportSummary>('/api/admin/reports/summary')
        .then((data) => {
          if (active) setSummary(data)
        })
        .catch(() => {})
    load()
    const timer = window.setInterval(load, 60_000)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [pathname])

  return summary
}
