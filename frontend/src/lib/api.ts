/**
 * The ONLY way the React app talks to the backend (and, through it, to Supabase).
 *
 *   const courses = await api<Course[]>('/api/courses')                    // logged-in call
 *   await api('/api/auth/login', { method: 'POST', body: {...}, auth: false })
 *
 * It adds the login token to every request and, if the token has expired,
 * quietly gets a new one and retries once. Teammates: use this for all your calls.
 */

// In development the Vite proxy forwards /api to port 8000, so this stays empty.
// For deployment set VITE_API_URL=https://your-backend.example.com
const API_BASE = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')

const ACCESS_KEY = 'studysync.access_token'
const REFRESH_KEY = 'studysync.refresh_token'

export const SESSION_EXPIRED_EVENT = 'studysync:session-expired'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** Login tokens, kept in the browser so a page refresh doesn't log people out. */
export const tokenStore = {
  get access(): string | null {
    try {
      return localStorage.getItem(ACCESS_KEY)
    } catch {
      return null
    }
  },
  get refresh(): string | null {
    try {
      return localStorage.getItem(REFRESH_KEY)
    } catch {
      return null
    }
  },
  set(access: string, refresh: string) {
    try {
      localStorage.setItem(ACCESS_KEY, access)
      localStorage.setItem(REFRESH_KEY, refresh)
    } catch {
      /* storage blocked: the user simply has to log in again after a refresh */
    }
  },
  clear() {
    try {
      localStorage.removeItem(ACCESS_KEY)
      localStorage.removeItem(REFRESH_KEY)
    } catch {
      /* ignore */
    }
  },
}

type RequestOptions = {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  body?: unknown
  /** Send the login token. Defaults to true. Use false for login, signup, etc. */
  auth?: boolean
}

/** FastAPI errors come as {detail: "text"} or, for bad input, {detail: [{msg: ...}]}. */
function messageFromBody(body: unknown, fallback: string): string {
  const detail = (body as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length > 0) {
    const msg = (detail[0] as { msg?: string }).msg
    if (msg) return msg.replace(/^Value error, /, '')
  }
  return fallback
}

async function send(path: string, { method = 'GET', body }: RequestOptions, token: string | null) {
  const headers: Record<string, string> = {}
  // FormData (file uploads) sets its own Content-Type, including the multipart boundary
  const isForm = body instanceof FormData
  if (body !== undefined && !isForm) headers['Content-Type'] = 'application/json'
  if (token) headers.Authorization = `Bearer ${token}`

  try {
    return await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
    })
  } catch {
    throw new ApiError(0, 'Cannot reach the server. Is the backend running on port 8000?')
  }
}

// If several requests fail at the same moment, refresh only once
// (a refresh token can be used a single time).
let refreshInFlight: Promise<boolean> | null = null

function refreshTokens(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      const refresh = tokenStore.refresh
      if (!refresh) return false
      try {
        const res = await send('/api/auth/refresh', { method: 'POST', body: { refresh_token: refresh } }, null)
        if (!res.ok) return false
        const data = await res.json()
        tokenStore.set(data.access_token, data.refresh_token)
        return true
      } catch {
        return false
      }
    })().finally(() => {
      refreshInFlight = null
    })
  }
  return refreshInFlight
}

export async function api<T = unknown>(path: string, options: RequestOptions = {}): Promise<T> {
  const useAuth = options.auth !== false

  let res = await send(path, options, useAuth ? tokenStore.access : null)

  if (res.status === 401 && useAuth && tokenStore.refresh) {
    if (await refreshTokens()) {
      res = await send(path, options, tokenStore.access)
    }
  }

  if (res.status === 401 && useAuth) {
    // the session is really over
    tokenStore.clear()
    window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT))
  }

  let data: unknown = null
  try {
    data = await res.json()
  } catch {
    /* empty or non-JSON body */
  }

  if (!res.ok) {
    throw new ApiError(res.status, messageFromBody(data, 'Something went wrong. Please try again.'))
  }
  return data as T
}
