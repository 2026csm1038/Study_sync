import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

/** Placeholder so admin login has somewhere to land. Replace with Page 5 (Admin Dashboard). */
export default function AdminHome() {
  const { profile, signOut } = useAuth()
  const navigate = useNavigate()

  async function handleLogout() {
    await signOut()
    navigate('/login', { replace: true })
  }

  return (
    <div className="auth-fullpage">
      <h1>Admin Dashboard</h1>
      <p>Logged in as {profile?.full_name} (admin).</p>
      <p>The Admin Dashboard (Page 5) will replace this placeholder.</p>
      <button className="auth-link-button" onClick={handleLogout}>
        Logout
      </button>
    </div>
  )
}
