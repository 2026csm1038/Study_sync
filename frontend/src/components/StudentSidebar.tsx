import { CircleUser, FileUp, House, LogOut, Search } from 'lucide-react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const LINKS = [
  { to: '/', label: 'Home', icon: House },
  { to: '/student', label: 'Search', icon: Search },
  { to: '/student/upload', label: 'Upload PDF', icon: FileUp },
]

/** Left sidebar shared by every student page (Page 3 Search, Page 4 Upload PDF, Profile). */
export function StudentSidebar() {
  const { profile, signOut } = useAuth() // profile comes from GET /api/auth/me
  const navigate = useNavigate()

  async function handleLogout() {
    await signOut() // POST /api/auth/logout, then clears the saved tokens
    navigate('/login', { replace: true })
  }

  return (
    <aside className="st-sidebar">
      <NavLink to="/" className="st-brand" aria-label="StudySync home">
        <img src="/assets/logo-mark.png" alt="" />
        <span>StudySync</span>
      </NavLink>

      <nav className="st-nav">
        {LINKS.map(({ to, label, icon: Icon }) => (
          <NavLink key={to} to={to} end className="st-nav-link">
            <Icon size={20} aria-hidden="true" />
            <span>{label}</span>
          </NavLink>
        ))}

        <hr className="st-divider" />

        <NavLink to="/student/profile" className="st-nav-link">
          <CircleUser size={20} aria-hidden="true" />
          <span>Profile</span>
        </NavLink>
        <button type="button" className="st-nav-link st-logout" onClick={handleLogout}>
          <LogOut size={20} aria-hidden="true" />
          <span>Logout</span>
        </button>
      </nav>

      <div className="st-user">
        <div className="st-avatar" aria-hidden="true">
          {profile?.full_name?.charAt(0).toUpperCase()}
        </div>
        <div className="st-user-text">
          <strong>{profile?.full_name}</strong>
          <span>{profile?.entry_number}</span>
        </div>
      </div>
    </aside>
  )
}
