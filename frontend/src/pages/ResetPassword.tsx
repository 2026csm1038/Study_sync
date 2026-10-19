import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { AuthLayout } from '../components/AuthLayout'
import { PasswordField } from '../components/FormFields'
import { useAuth, type ResetLink } from '../context/AuthContext'
import { clearAuthLinkFromUrl, describeLinkError, readAuthLink, type AuthLink } from '../lib/authLink'
import { validatePassword } from '../lib/validation'

/**
 * Opened from the link in the reset email. Two link shapes are supported:
 *   /reset-password?token_hash=...&type=recovery        (our custom email template)
 *   /reset-password#access_token=...&type=recovery      (Supabase's default template)
 * The token is sent to the backend together with the new password.
 */
export default function ResetPassword() {
  const { resetPassword } = useAuth()
  const navigate = useNavigate()

  // read once, then remove the token from the address bar
  const [link] = useState<AuthLink>(() => readAuthLink())
  useEffect(() => clearAuthLinkFromUrl(), [])
  const resetLink: ResetLink | null = link.errorCode
    ? null
    : link.tokenHash
      ? { token_hash: link.tokenHash }
      : link.accessToken && link.type === 'recovery'
        ? { access_token: link.accessToken }
        : null

  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [errors, setErrors] = useState<{ password?: string; confirmPassword?: string }>({})
  const [formError, setFormError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setFormError('')
    if (!resetLink) return

    const next: typeof errors = {}
    const problem = validatePassword(password)
    if (problem) next.password = problem
    if (confirmPassword !== password) next.confirmPassword = 'Passwords do not match.'
    setErrors(next)
    if (Object.keys(next).length > 0) return

    setSubmitting(true)
    try {
      await resetPassword(resetLink, password)
      navigate('/login', {
        replace: true,
        state: { notice: 'Password updated. Please log in with your new password.' },
      })
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Something went wrong.')
    } finally {
      setSubmitting(false)
    }
  }

  if (!resetLink) {
    return (
      <AuthLayout>
        <h2 className="auth-title">Link expired</h2>
        <p className="auth-subtitle">
          {link.errorCode
            ? describeLinkError(link).replace(' below', '')
            : 'This reset link is invalid or has expired. Request a new one to continue.'}
        </p>
        <Link className="auth-submit auth-submit--link" to="/forgot-password">
          Request a new link
        </Link>
      </AuthLayout>
    )
  }

  return (
    <AuthLayout>
      <h2 className="auth-title">Set a new password</h2>
      <p className="auth-subtitle">Choose a password you haven't used before.</p>

      {formError && (
        <div className="auth-banner auth-banner--error" role="alert">
          {formError}{' '}
          <Link to="/forgot-password">Request a new link</Link>
        </div>
      )}

      <form onSubmit={handleSubmit} noValidate>
        <PasswordField
          id="password"
          label="New Password"
          value={password}
          onChange={setPassword}
          error={errors.password}
          autoComplete="new-password"
          disabled={submitting}
        />
        <PasswordField
          id="confirmPassword"
          label="Confirm New Password"
          value={confirmPassword}
          onChange={setConfirmPassword}
          error={errors.confirmPassword}
          autoComplete="new-password"
          disabled={submitting}
        />
        <button className="auth-submit" type="submit" disabled={submitting}>
          {submitting ? 'Saving…' : 'Update password'}
        </button>
      </form>
    </AuthLayout>
  )
}
