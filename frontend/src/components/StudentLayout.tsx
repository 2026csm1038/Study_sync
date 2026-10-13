import { Outlet } from 'react-router-dom'
import { StudentSidebar } from './StudentSidebar'
import '../student.css'

/** Sidebar + page area. Every student page is rendered inside <Outlet />. */
export function StudentLayout() {
  return (
    <div className="st-shell">
      <StudentSidebar />
      <main className="st-main">
        <Outlet />
      </main>
    </div>
  )
}
