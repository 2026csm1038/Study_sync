import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { AuthLayout } from '../components/AuthLayout'
import { PasswordField, TextField } from '../components/FormFields'
import { ApiError } from '../lib/api'
import { homePathFor, useAuth } from '../context/AuthContext'

type LocationState = { from?: string; notice?: string } | null

export default function Login() {
  const { signIn } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const state = location.state as LocationState

  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState<{ identifier?: string; password?: string }>({})
  const [formError, setFormError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [needsConfirm, setNeedsConfirm] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setFormError('')
    setNeedsConfirm(false)

    const nextErrors: typeof errors = {}
    if (!identifier.trim()) nextErrors.identifier = 'Enter your entry number or email.'
    if (!password) nextErrors.password = 'Enter your password.'
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length > 0) return

    setSubmitting(true)
    try {
      const profile = await signIn(identifier, password)
      const home = homePathFor(profile.role)
      // go back to the page they originally wanted, if it belongs to their role
      const target = state?.from && state.from.startsWith(home) ? state.from : home
      navigate(target, { replace: true })
    } catch (err) {
      setNeedsConfirm(err instanceof ApiError && err.status === 403)
      setFormError(err instanceof Error ? err.message : 'Something went wrong.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthLayout>
      <h2 className="auth-title">Welcome to StudySync</h2>
      <p className="auth-subtitle">Login to access academic resources.</p>

      {state?.notice && <div className="auth-banner auth-banner--success">{state.notice}</div>}
      {formError && (
        <div className="auth-banner auth-banner--error" role="alert">
          {formError}{' '}
          {needsConfirm && <Link to="/confirm-email">Send a new confirmation link</Link>}
        </div>
      )}

      <form onSubmit={handleSubmit} noValidate>
        <TextField
          id="identifier"
          label="Entry Number / Email"
          value={identifier}
          onChange={setIdentifier}
          error={errors.identifier}
          autoComplete="username"
          disabled={submitting}
        />
        <PasswordField
          id="password"
          label="Password"
          value={password}
          onChange={setPassword}
          error={errors.password}
          autoComplete="current-password"
          disabled={submitting}
        />

        <button className="auth-submit" type="submit" disabled={submitting}>
          {submitting ? 'Logging in…' : 'Login'}
        </button>
      </form>

      <div className="auth-forgot">
        <Link to="/forgot-password">Forgot password?</Link>
      </div>

      <p className="auth-switch">
        Don't have an account? <Link to="/signup">Sign Up</Link>
      </p>
    </AuthLayout>
  )
}
