import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

/** Placeholder so login has somewhere to land. Replace with Page 3 (Student Search). */
export default function StudentHome() {
  const { profile, signOut } = useAuth()
  const navigate = useNavigate()

  async function handleLogout() {
    await signOut()
    navigate('/login', { replace: true })
  }

  return (
    <div className="auth-fullpage">
      <h1>Welcome, {profile?.full_name}</h1>
      <p>You are logged in as a student ({profile?.entry_number}).</p>
      <p>The Student Search page (Page 3) will replace this placeholder.</p>
      <button className="auth-link-button" onClick={handleLogout}>
        Logout
      </button>
    </div>
  )
}
