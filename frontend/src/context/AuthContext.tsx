import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import type { Session } from '@supabase/supabase-js'
import { isSupabaseConfigured, supabase } from '../lib/supabase'

export type Role = 'student' | 'admin'

export type Profile = {
  id: string
  full_name: string
  entry_number: string | null
  email: string | null
  role: Role
}

type SignUpInput = {
  fullName: string
  entryNumber: string
  email: string
  password: string
}

type SignUpResult = {
  /** true when Supabase email confirmation is on: the user must click the email link first */
  needsEmailConfirmation: boolean
  profile: Profile | null
}

type AuthContextValue = {
  configured: boolean
  loading: boolean
  session: Session | null
  profile: Profile | null
  signIn: (identifier: string, password: string) => Promise<Profile>
  signUp: (input: SignUpInput) => Promise<SignUpResult>
  signOut: () => Promise<void>
  sendPasswordReset: (email: string) => Promise<void>
  updatePassword: (password: string) => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function homePathFor(role: Role): string {
  return role === 'admin' ? '/admin' : '/student'
}

const NOT_CONFIGURED =
  'Supabase is not configured. Add VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY to frontend/.env and restart npm run dev.'
const INVALID_LOGIN = 'Invalid entry number / email or password.'

function requireClient() {
  if (!supabase) throw new Error(NOT_CONFIGURED)
  return supabase
}

async function fetchProfile(userId: string): Promise<Profile | null> {
  if (!supabase) return null
  const { data, error } = await supabase
    .from('profiles')
    .select('id, full_name, entry_number, email, role')
    .eq('id', userId)
    .single()
  if (error || !data) return null
  return data as Profile
}

function loginErrorMessage(message: string): string {
  if (/email not confirmed/i.test(message)) {
    return 'Please confirm your email first. Check your inbox for the confirmation link.'
  }
  if (/rate limit|too many/i.test(message)) {
    return 'Too many attempts. Please wait a minute and try again.'
  }
  return INVALID_LOGIN
}

function signUpErrorMessage(message: string): string {
  if (/database error/i.test(message)) {
    // the profiles table rejected a duplicate entry number or email
    return 'This entry number or email is already registered.'
  }
  if (/already registered/i.test(message)) return 'An account with this email already exists.'
  return message
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [profile, setProfile] = useState<Profile | null>(null)
  const [loading, setLoading] = useState<boolean>(isSupabaseConfigured)

  // 1. Track the Supabase session (restores it after a page refresh).
  useEffect(() => {
    if (!supabase) return
    let active = true

    supabase.auth.getSession().then(({ data }) => {
      if (!active) return
      setSession(data.session)
      if (!data.session) setLoading(false)
    })

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession)
      if (!nextSession) {
        setProfile(null)
        setLoading(false)
      }
    })

    return () => {
      active = false
      subscription.unsubscribe()
    }
  }, [])

  // 2. Whenever the signed-in user changes, load their profile (name, role).
  const userId = session?.user.id
  useEffect(() => {
    if (!userId) return
    let active = true
    setLoading(true)
    fetchProfile(userId).then((p) => {
      if (!active) return
      setProfile(p)
      setLoading(false)
    })
    return () => {
      active = false
    }
  }, [userId])

  const signIn = useCallback(async (identifier: string, password: string) => {
    const client = requireClient()
    const id = identifier.trim()

    if (id.includes('@')) {
      // Email login: straight to Supabase Auth.
      const { error } = await client.auth.signInWithPassword({
        email: id.toLowerCase(),
        password,
      })
      if (error) throw new Error(loginErrorMessage(error.message))
    } else {
      // Entry-number login: the backend finds the email, signs in, and returns tokens.
      let res: Response
      try {
        res = await fetch('/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ identifier: id, password }),
        })
      } catch {
        throw new Error('Cannot reach the server. Is the backend running on port 8000?')
      }
      if (res.status === 401) throw new Error(INVALID_LOGIN)
      if (!res.ok) throw new Error('Login failed. Please try again in a moment.')

      const tokens = await res.json()
      const { error } = await client.auth.setSession({
        access_token: tokens.access_token,
        refresh_token: tokens.refresh_token,
      })
      if (error) throw new Error(INVALID_LOGIN)
    }

    const {
      data: { session: newSession },
    } = await client.auth.getSession()
    if (!newSession) throw new Error(INVALID_LOGIN)

    const loaded = await fetchProfile(newSession.user.id)
    if (!loaded) {
      await client.auth.signOut()
      throw new Error('Your account has no profile yet. Please contact an admin.')
    }
    setProfile(loaded)
    return loaded
  }, [])

  const signUp = useCallback(async (input: SignUpInput): Promise<SignUpResult> => {
    const client = requireClient()
    const { data, error } = await client.auth.signUp({
      email: input.email.trim().toLowerCase(),
      password: input.password,
      options: {
        // read by the database trigger that creates the profile row
        data: {
          full_name: input.fullName.trim(),
          entry_number: input.entryNumber.trim().toUpperCase(),
        },
        emailRedirectTo: `${window.location.origin}/login`,
      },
    })
    if (error) throw new Error(signUpErrorMessage(error.message))

    // With "confirm email" on, an already-registered email returns a fake user with no identities.
    if (data.user && data.user.identities && data.user.identities.length === 0) {
      throw new Error('An account with this email already exists.')
    }

    if (!data.session || !data.user) {
      return { needsEmailConfirmation: true, profile: null }
    }

    const loaded = await fetchProfile(data.user.id)
    setProfile(loaded)
    return { needsEmailConfirmation: false, profile: loaded }
  }, [])

  const signOut = useCallback(async () => {
    if (supabase) await supabase.auth.signOut()
    setProfile(null)
  }, [])

  const sendPasswordReset = useCallback(async (email: string) => {
    const client = requireClient()
    const { error } = await client.auth.resetPasswordForEmail(email.trim().toLowerCase(), {
      redirectTo: `${window.location.origin}/reset-password`,
    })
    if (error && /rate limit|too many/i.test(error.message)) {
      throw new Error('Too many requests. Please wait a minute and try again.')
    }
    // Any other error is ignored on purpose, so the page never reveals which emails exist.
  }, [])

  const updatePassword = useCallback(async (password: string) => {
    const client = requireClient()
    const { error } = await client.auth.updateUser({ password })
    if (error) throw new Error(error.message)
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      configured: isSupabaseConfigured,
      loading,
      session,
      profile,
      signIn,
      signUp,
      signOut,
      sendPasswordReset,
      updatePassword,
    }),
    [loading, session, profile, signIn, signUp, signOut, sendPasswordReset, updatePassword],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
