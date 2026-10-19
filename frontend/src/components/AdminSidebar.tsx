import { CircleUser, FileText, FileUp, GraduationCap, House, LogOut } from 'lucide-react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const LINKS = [
  { to: '/admin', label: 'Dashboard', icon: House },
  { to: '/admin/requests', label: 'Manage Request', icon: FileText },
  { to: '/admin/courses', label: 'Manage Courses', icon: GraduationCap },
  { to: '/admin/upload', label: 'Upload PDF', icon: FileUp },
]

/** Left sidebar shared by every admin page (Dashboard, Manage Request, Manage Courses, Upload PDF, Profile). */
export function AdminSidebar() {
  const { profile, signOut } = useAuth() // profile comes from GET /api/auth/me
  const navigate = useNavigate()

  async function handleLogout() {
    await signOut() // POST /api/auth/logout, then clears the saved tokens
    navigate('/login', { replace: true })
  }

  return (
    <aside className="st-sidebar">
      <NavLink to="/admin" className="st-brand" aria-label="StudySync admin dashboard">
        <img src="/assets/logo-mark.png" alt=""  />
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

        <NavLink to="/admin/profile" className="st-nav-link">
          <CircleUser size={20} aria-hidden="true" />
          <span>Profile</span>
        </NavLink>
        <button type="button" className="st-nav-link st-logout" onClick={handleLogout}>
          <LogOut size={20} aria-hidden="true" />
          <span>logout</span>
        </button>
      </nav>

      <div className="st-user">
        <div className="st-avatar" aria-hidden="true">
          {profile?.full_name?.charAt(0).toUpperCase()}
        </div>
        <div className="st-user-text">
          <strong>{profile?.full_name}</strong>
          <span>Admin</span>
        </div>
      </div>
    </aside>
  )
}
