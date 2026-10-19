import { Outlet } from 'react-router-dom'
import { AdminSidebar } from './AdminSidebar'
import '../student.css' // shared shell + sidebar styles (st- classes)
import '../admin.css'

/** Sidebar + page area. Every admin page is rendered inside <Outlet />. */
export function AdminLayout() {
  return (
    <div className="st-shell">
      <AdminSidebar />
      <main className="st-main">
        <Outlet />
      </main>
    </div>
  )
}
