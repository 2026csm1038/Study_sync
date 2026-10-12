import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { api, ApiError, SESSION_EXPIRED_EVENT, tokenStore } from '../lib/api'

export type Role = 'student' | 'admin'

export type Profile = {
  id: string
  email: string | null
  full_name: string
  entry_number: string | null
  role: Role
}

type SessionResponse = {
  access_token: string
  refresh_token: string
  expires_in: number | null
  profile: Profile
}

type SignUpInput = {
  fullName: string
  entryNumber: string
  email: string
  password: string
}

type SignUpResult = {
  /** true when email confirmation is on: the student must click the link in their inbox first */
  needsEmailConfirmation: boolean
  profile: Profile | null
}

type AuthContextValue = {
  loading: boolean
  profile: Profile | null
  signIn: (identifier: string, password: string) => Promise<Profile>
  signUp: (input: SignUpInput) => Promise<SignUpResult>
  signOut: () => Promise<void>
  sendPasswordReset: (email: string) => Promise<void>
  resetPassword: (tokenHash: string, password: string) => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function homePathFor(role: Role): string {
  return role === 'admin' ? '/admin' : '/student'
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [profile, setProfile] = useState<Profile | null>(null)
  // If there is no saved token there is nothing to restore, so we are not "loading".
  const [loading, setLoading] = useState<boolean>(() => tokenStore.access !== null)

  // Restore the session after a page refresh: ask the backend who the saved token belongs to.
  useEffect(() => {
    if (tokenStore.access === null) return
    let active = true
    api<Profile>('/api/auth/me')
      .then((me) => {
        if (active) setProfile(me)
      })
      .catch((err) => {
        // an expired session was already cleaned up by api(); a network error keeps the token
        if (active && err instanceof ApiError && err.status === 401) setProfile(null)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  // api() announces when a refresh fails, so every page drops back to logged-out together.
  useEffect(() => {
    const onExpired = () => setProfile(null)
    window.addEventListener(SESSION_EXPIRED_EVENT, onExpired)
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, onExpired)
  }, [])

  const signIn = useCallback(async (identifier: string, password: string) => {
    const session = await api<SessionResponse>('/api/auth/login', {
      method: 'POST',
      body: { identifier: identifier.trim(), password },
      auth: false,
    })
    tokenStore.set(session.access_token, session.refresh_token)
    setProfile(session.profile)
    return session.profile
  }, [])

  const signUp = useCallback(async (input: SignUpInput): Promise<SignUpResult> => {
    const result = await api<{ needs_email_confirmation: boolean; session: SessionResponse | null }>(
      '/api/auth/signup',
      {
        method: 'POST',
        body: {
          full_name: input.fullName,
          entry_number: input.entryNumber,
          email: input.email,
          password: input.password,
        },
        auth: false,
      },
    )
    if (result.needs_email_confirmation || !result.session) {
      return { needsEmailConfirmation: true, profile: null }
    }
    tokenStore.set(result.session.access_token, result.session.refresh_token)
    setProfile(result.session.profile)
    return { needsEmailConfirmation: false, profile: result.session.profile }
  }, [])

  const signOut = useCallback(async () => {
    try {
      await api('/api/auth/logout', { method: 'POST' })
    } catch {
      /* log out locally even if the server can't be reached */
    }
    tokenStore.clear()
    setProfile(null)
  }, [])

  const sendPasswordReset = useCallback(async (email: string) => {
    await api('/api/auth/forgot-password', { method: 'POST', body: { email }, auth: false })
  }, [])

  const resetPassword = useCallback(async (tokenHash: string, password: string) => {
    await api('/api/auth/reset-password', {
      method: 'POST',
      body: { token_hash: tokenHash, password },
      auth: false,
    })
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({ loading, profile, signIn, signUp, signOut, sendPasswordReset, resetPassword }),
    [loading, profile, signIn, signUp, signOut, sendPasswordReset, resetPassword],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
