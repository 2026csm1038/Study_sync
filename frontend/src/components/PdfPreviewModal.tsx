import { ExternalLink, Flag, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { apiBlob } from '../lib/api'

type Props = {
  resourceId: string
  title: string
  subtitle: string
  onClose: () => void
  onReport: () => void // opens the report dialog (it sits on top of this preview)
}

/** In-page PDF preview for the Search page. Loads the file through GET /api/resources/{id}/view. */
export function PdfPreviewModal({ resourceId, title, subtitle, onClose, onReport }: Props) {
  const [url, setUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let objectUrl: string | undefined
    let cancelled = false
    apiBlob(`/api/resources/${encodeURIComponent(resourceId)}/view`)
      .then((blob) => {
        if (cancelled) return
        objectUrl = URL.createObjectURL(blob)
        setUrl(objectUrl)
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Could not load this PDF.')
      })
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [resourceId])

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      // Escape closes the report dialog first (if it is open), then the preview.
      if (e.key === 'Escape' && !document.querySelector('.st-report-overlay')) onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="st-preview-overlay" onClick={onClose}>
      <div className="st-preview-modal" role="dialog" aria-modal="true" aria-label={`Preview of ${title}`} onClick={(e) => e.stopPropagation()}>
        <div className="st-preview-header">
          <div className="st-preview-title">
            <strong>{title}</strong>
            <span>{subtitle}</span>
          </div>
          <button type="button" className="st-preview-btn st-preview-btn-flag" onClick={onReport}>
            <Flag size={16} aria-hidden="true" /> Report
          </button>
          <a
            className="st-preview-btn"
            href={url ?? undefined}
            target="_blank"
            rel="noopener noreferrer"
            aria-disabled={!url}
          >
            <ExternalLink size={16} aria-hidden="true" /> Open in new tab
          </a>
          <button type="button" className="st-preview-btn" onClick={onClose} aria-label="Close preview">
            <X size={18} aria-hidden="true" />
          </button>
        </div>
        <div className="st-preview-body">
          {url && <iframe src={url} title={`Preview of ${title}`} />}
          {!url && <p className="st-preview-status">{error ?? 'Loading preview…'}</p>}
        </div>
      </div>
    </div>
  )
}
