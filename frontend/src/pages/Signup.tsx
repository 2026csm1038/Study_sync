import { MailCheck } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { AuthLayout } from '../components/AuthLayout'
import { PasswordField, SelectField, TextField } from '../components/FormFields'
import { homePathFor, useAuth, type SignupRole } from '../context/AuthContext'
import { isValidEmail, isValidEntryNumber, looksLikeStudentEmail, validatePassword } from '../lib/validation'

type Errors = Partial<
  Record<'fullName' | 'entryNumber' | 'email' | 'password' | 'confirmPassword', string>
>

export default function Signup() {
  const { signUp } = useAuth()
  const navigate = useNavigate()

  const [role, setRole] = useState<SignupRole>('student')
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
    if (role === 'student' && !isValidEntryNumber(entryNumber)) {
      next.entryNumber = 'Enter a valid entry number, for example 2026CSM1038.'
    }
    if (!isValidEmail(email)) next.email = 'Enter a valid email address.'
    else if (role === 'professor' && looksLikeStudentEmail(email)) {
      next.email = 'This looks like a student email address. Use your faculty email.'
    }
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
      const result = await signUp({ role, fullName, entryNumber, email, password })
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
            We sent a confirmation link to <strong>{confirmationSentTo}</strong>. Your account is
            created once you open it, then you can log in.
          </p>
          <p className="auth-switch">
            Didn't get it? <Link to="/confirm-email">Send a new link</Link>
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

      {formError && (
        <div className="auth-banner auth-banner--error" role="alert">
          {formError}
        </div>
      )}

      <form onSubmit={handleSubmit} noValidate>
        <SelectField
          id="role"
          label="I am a"
          value={role}
          onChange={(v) => setRole(v as SignupRole)}
          options={[
            { value: 'student', label: 'Student' },
            { value: 'professor', label: 'Professor / Faculty' },
          ]}
          disabled={submitting}
        />
        <TextField
          id="fullName"
          label="Full Name"
          value={fullName}
          onChange={setFullName}
          error={errors.fullName}
          autoComplete="name"
          disabled={submitting}
        />
        {role === 'student' && (
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
        )}
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

        <button className="auth-submit" type="submit" disabled={submitting}>
          {submitting ? 'Creating account…' : 'Sign Up'}
        </button>
      </form>

      <p className="auth-switch">
        Already have an account? <Link to="/login">Login</Link>
      </p>
    </AuthLayout>
  )
}
