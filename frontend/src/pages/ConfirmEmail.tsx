import { MailCheck, MailWarning } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { AuthLayout } from '../components/AuthLayout'
import { TextField } from '../components/FormFields'
import { useAuth } from '../context/AuthContext'
import { clearAuthLinkFromUrl, describeLinkError, readAuthLink, type AuthLink } from '../lib/authLink'
import { isValidEmail } from '../lib/validation'

/**
 * Opened from the link in the confirmation email: /confirm-email?token_hash=...&type=signup
 * The student's profile is only created once this confirmation succeeds.
 * The token is used when the button is clicked (not on page load), so email scanners that
 * pre-open links can't use it up.
 */
export default function ConfirmEmail() {
  const { confirmEmail, resendConfirmation } = useAuth()
  const navigate = useNavigate()

  // read once; then remove tokens from the address bar
  const [link] = useState<AuthLink>(() => readAuthLink())
  useEffect(() => clearAuthLinkFromUrl(), [])

  // Supabase's default template already confirmed the email before redirecting here
  const alreadyConfirmed = !link.tokenHash && !link.errorCode && Boolean(link.accessToken) && link.type === 'signup'

  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(link.errorCode ? describeLinkError(link) : '')
  const [email, setEmail] = useState('')
  const [emailError, setEmailError] = useState('')
  const [resent, setResent] = useState(false)

  async function handleConfirm() {
    if (!link.tokenHash) return
    setBusy(true)
    setError('')
    try {
      await confirmEmail(link.tokenHash)
      navigate('/login', { replace: true, state: { notice: 'Email confirmed. You can log in now.' } })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  async function handleResend(e: FormEvent) {
    e.preventDefault()
    if (!isValidEmail(email)) {
      setEmailError('Enter the email address you signed up with.')
      return
    }
    setEmailError('')
    setBusy(true)
    setError('')
    try {
      await resendConfirmation(email)
      setResent(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  if (alreadyConfirmed) {
    return (
      <AuthLayout>
        <div className="auth-success">
          <MailCheck size={44} strokeWidth={1.6} aria-hidden="true" />
          <h2 className="auth-title">Email confirmed</h2>
          <p className="auth-subtitle">Your account is ready. Log in to continue.</p>
          <Link className="auth-submit auth-submit--link" to="/login">
            Go to Login
          </Link>
        </div>
      </AuthLayout>
    )
  }

  if (link.tokenHash && !error) {
    return (
      <AuthLayout>
        <div className="auth-success">
          <MailCheck size={44} strokeWidth={1.6} aria-hidden="true" />
          <h2 className="auth-title">Confirm your email</h2>
          <p className="auth-subtitle">
            One last step: confirm your email address to finish creating your StudySync account.
          </p>
          <button className="auth-submit" type="button" onClick={handleConfirm} disabled={busy}>
            {busy ? 'Confirming…' : 'Confirm my email'}
          </button>
        </div>
      </AuthLayout>
    )
  }

  // no valid link, or the link failed: let them ask for a new one
  return (
    <AuthLayout>
      <div className="auth-success">
        <MailWarning size={44} strokeWidth={1.6} aria-hidden="true" />
        <h2 className="auth-title">{error ? 'Link problem' : 'Confirm your email'}</h2>
      </div>

      {error && (
        <div className="auth-banner auth-banner--error" role="alert">
          {error}
        </div>
      )}

      {resent ? (
        <div className="auth-banner auth-banner--success">
          If <strong>{email.trim()}</strong> is waiting for confirmation, a new link is on its way.
          Use the newest email only.
        </div>
      ) : (
        <>
          <p className="auth-subtitle">Enter your email and we'll send a new confirmation link.</p>
          <form onSubmit={handleResend} noValidate>
            <TextField
              id="email"
              label="Email"
              type="email"
              value={email}
              onChange={setEmail}
              error={emailError}
              autoComplete="email"
              disabled={busy}
            />
            <button className="auth-submit" type="submit" disabled={busy}>
              {busy ? 'Sending…' : 'Send new link'}
            </button>
          </form>
        </>
      )}
      <p className="auth-switch">
        <Link to="/login">Back to Login</Link>
      </p>
    </AuthLayout>
  )
}
