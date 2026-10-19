/**
 * Reads the link from a Supabase email (confirm signup / reset password).
 *
 * Our custom email templates produce  /page?token_hash=...&type=...  (a query string).
 * Supabase's DEFAULT templates verify the link on Supabase first, then redirect here with the
 * result in the URL fragment:  /page#access_token=...&type=recovery
 *   or, if the link was already used / timed out:  /page#error=access_denied&error_code=otp_expired
 * Both shapes are handled so the pages work whichever template is configured.
 */
export type AuthLink = {
  tokenHash: string | null
  accessToken: string | null
  type: string | null
  /** set when Supabase says the link is bad, e.g. 'otp_expired' */
  errorCode: string | null
  errorDescription: string | null
}

export function readAuthLink(): AuthLink {
  const query = new URLSearchParams(window.location.search)
  const hash = new URLSearchParams(window.location.hash.replace(/^#/, ''))
  const pick = (key: string) => query.get(key) ?? hash.get(key)
  return {
    tokenHash: query.get('token_hash'),
    accessToken: hash.get('access_token'),
    type: pick('type'),
    errorCode: pick('error_code') ?? (hash.get('error') ? 'access_denied' : null),
    errorDescription: pick('error_description'),
  }
}

/** Remove tokens from the address bar (and browser history) once they have been read. */
export function clearAuthLinkFromUrl(): void {
  window.history.replaceState(null, '', window.location.pathname)
}

export function describeLinkError(link: AuthLink): string {
  if (link.errorCode === 'otp_expired') {
    return 'This link has expired or was already used. Some email apps open links automatically, which uses them up. Request a new one below.'
  }
  return link.errorDescription?.replace(/\+/g, ' ') || 'This link is invalid. Request a new one below.'
}
