import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { AuthLayout } from '../components/AuthLayout'
import { TextField } from '../components/FormFields'
import { useAuth } from '../context/AuthContext'
import { isValidEmail } from '../lib/validation'

export default function ForgotPassword() {
  const { sendPasswordReset } = useAuth()
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [formError, setFormError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [sent, setSent] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setFormError('')

    if (!isValidEmail(email)) {
      setError('Enter the email address of your account.')
      return
    }
    setError('')

    setSubmitting(true)
    try {
      await sendPasswordReset(email)
      setSent(true)
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Something went wrong.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthLayout>
      <h2 className="auth-title">Forgot password?</h2>

      {sent ? (
        <>
          <div className="auth-banner auth-banner--success">
            If an account exists for <strong>{email.trim()}</strong>, a reset link is on its way.
            Check your inbox and spam folder.
          </div>
          <p className="auth-switch">
            <Link to="/login">Back to Login</Link>
          </p>
        </>
      ) : (
        <>
          <p className="auth-subtitle">Enter your email and we'll send you a reset link.</p>
          {formError && (
            <div className="auth-banner auth-banner--error" role="alert">
              {formError}
            </div>
          )}
          <form onSubmit={handleSubmit} noValidate>
            <TextField
              id="email"
              label="Email"
              type="email"
              value={email}
              onChange={setEmail}
              error={error}
              autoComplete="email"
              disabled={submitting}
            />
            <button className="auth-submit" type="submit" disabled={submitting}>
              {submitting ? 'Sending…' : 'Send reset link'}
            </button>
          </form>
          <p className="auth-switch">
            <Link to="/login">Back to Login</Link>
          </p>
        </>
      )}
    </AuthLayout>
  )
}
