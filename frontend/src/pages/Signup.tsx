import { MailCheck } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { AuthLayout } from '../components/AuthLayout'
import { PasswordField, TextField } from '../components/FormFields'
import { homePathFor, useAuth } from '../context/AuthContext'
import { isValidEmail, isValidEntryNumber, validatePassword } from '../lib/validation'

type Errors = Partial<
  Record<'fullName' | 'entryNumber' | 'email' | 'password' | 'confirmPassword', string>
>

export default function Signup() {
  const { signUp, configured } = useAuth()
  const navigate = useNavigate()

  const [fullName, setFullName] = useState('')
  const [entryNumber, setEntryNumber] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [errors, setErrors] = useState<Errors>({})
  const [formError, setFormError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [confirmationSentTo, setConfirmationSentTo] = useState('')

  function validate(): Errors {
    const next: Errors = {}
    if (fullName.trim().length < 2) next.fullName = 'Enter your full name.'
    if (!isValidEntryNumber(entryNumber)) {
      next.entryNumber = 'Enter a valid entry number, for example 2026CSM1038.'
    }
    if (!isValidEmail(email)) next.email = 'Enter a valid email address.'
    const passwordProblem = validatePassword(password)
    if (passwordProblem) next.password = passwordProblem
    if (confirmPassword !== password) next.confirmPassword = 'Passwords do not match.'
    return next
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setFormError('')

    const nextErrors = validate()
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length > 0) return

    setSubmitting(true)
    try {
      const result = await signUp({ fullName, entryNumber, email, password })
      if (result.needsEmailConfirmation) {
        setConfirmationSentTo(email.trim().toLowerCase())
      } else if (result.profile) {
        navigate(homePathFor(result.profile.role), { replace: true })
      } else {
        navigate('/login', { replace: true })
      }
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Something went wrong.')
    } finally {
      setSubmitting(false)
    }
  }

  if (confirmationSentTo) {
    return (
      <AuthLayout>
        <div className="auth-success">
          <MailCheck size={44} strokeWidth={1.6} aria-hidden="true" />
          <h2 className="auth-title">Check your email</h2>
          <p className="auth-subtitle">
            We sent a confirmation link to <strong>{confirmationSentTo}</strong>. Open it, then log
            in.
          </p>
          <Link className="auth-submit auth-submit--link" to="/login">
            Go to Login
          </Link>
        </div>
      </AuthLayout>
    )
  }

  return (
    <AuthLayout>
      <h2 className="auth-title">Create your account</h2>
      <p className="auth-subtitle">Sign up to access academic resources.</p>

      {!configured && (
        <div className="auth-banner auth-banner--error">
          Supabase is not configured yet. Add your keys to <code>frontend/.env</code>.
        </div>
      )}
      {formError && (
        <div className="auth-banner auth-banner--error" role="alert">
          {formError}
        </div>
      )}

      <form onSubmit={handleSubmit} noValidate>
        <TextField
          id="fullName"
          label="Full Name"
          value={fullName}
          onChange={setFullName}
          error={errors.fullName}
          autoComplete="name"
          disabled={submitting}
        />
        <TextField
          id="entryNumber"
          label="Entry Number"
          value={entryNumber}
          onChange={setEntryNumber}
          error={errors.entryNumber}
          placeholder="2026CSM1038"
          autoComplete="off"
          disabled={submitting}
        />
        <TextField
          id="email"
          label="Email"
          type="email"
          value={email}
          onChange={setEmail}
          error={errors.email}
          autoComplete="email"
          disabled={submitting}
        />
        <PasswordField
          id="password"
          label="Password"
          value={password}
          onChange={setPassword}
          error={errors.password}
          autoComplete="new-password"
          disabled={submitting}
        />
        <PasswordField
          id="confirmPassword"
          label="Confirm Password"
          value={confirmPassword}
          onChange={setConfirmPassword}
          error={errors.confirmPassword}
          autoComplete="new-password"
          disabled={submitting}
        />

        <button className="auth-submit" type="submit" disabled={submitting || !configured}>
          {submitting ? 'Creating account…' : 'Sign Up'}
        </button>
      </form>

      <p className="auth-switch">
        Already have an account? <Link to="/login">Login</Link>
      </p>
    </AuthLayout>
  )
}
