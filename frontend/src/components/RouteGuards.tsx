import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { homePathFor, useAuth, type Role } from '../context/AuthContext'

function FullPageMessage({ children }: { children: React.ReactNode }) {
  return <div className="auth-fullpage">{children}</div>
}

/** Wrap pages that need a logged-in user of a specific role. */
export function ProtectedRoute({ role }: { role: Role }) {
  const { loading, session, profile, signOut } = useAuth()
  const location = useLocation()

  if (loading) return <FullPageMessage>Loading…</FullPageMessage>
  if (!session) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (!profile) {
    return (
      <FullPageMessage>
        <p>We couldn't load your profile.</p>
        <button className="auth-link-button" onClick={() => void signOut()}>
          Log out and try again
        </button>
      </FullPageMessage>
    )
  }
  if (profile.role !== role) return <Navigate to={homePathFor(profile.role)} replace />
  return <Outlet />
}

/** Wrap login / signup: people who are already logged in get sent to their dashboard. */
export function GuestRoute() {
  const { loading, session, profile } = useAuth()

  if (loading) return <FullPageMessage>Loading…</FullPageMessage>
  if (session && profile) return <Navigate to={homePathFor(profile.role)} replace />
  return <Outlet />
}
