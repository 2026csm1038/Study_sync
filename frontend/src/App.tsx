import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { GuestRoute, ProtectedRoute } from './components/RouteGuards'
import { AuthProvider } from './context/AuthContext'
import ForgotPassword from './pages/ForgotPassword'
import Home from './pages/Home'
import Login from './pages/Login'
import ConfirmEmail from './pages/ConfirmEmail'
import ResetPassword from './pages/ResetPassword'
import Signup from './pages/Signup'
import { StudentLayout } from './components/StudentLayout'
import StudentProfile from './pages/student/StudentProfile'
import StudentSearch from './pages/student/StudentSearch'
import UploadPdf from './pages/student/UploadPdf'
import { AdminLayout } from './components/AdminLayout'
import AdminDashboard from './pages/admin/AdminDashboard'
import AdminProfile from './pages/admin/AdminProfile'
import AdminUpload from './pages/admin/AdminUpload'
import ManageCourses from './pages/admin/ManageCourses'
import ManageRequests from './pages/admin/ManageRequests'
import './styles.css'
import './auth.css'

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Home />} />

          {/* only for people who are NOT logged in */}
          <Route element={<GuestRoute />}>
            <Route path="/login" element={<Login />} />
            <Route path="/signup" element={<Signup />} />
            <Route path="/forgot-password" element={<ForgotPassword />} />
          </Route>

          {/* opened from the email link; must work with the temporary recovery session */}
          <Route path="/reset-password" element={<ResetPassword />} />

          <Route path="/confirm-email" element={<ConfirmEmail />} />

          {/* students only: every student page shares the sidebar (StudentLayout) */}
          <Route element={<ProtectedRoute role="student" />}>
            <Route element={<StudentLayout />}>
              <Route path="/student" element={<StudentSearch />} />
              <Route path="/student/upload" element={<UploadPdf />} />
              <Route path="/student/profile" element={<StudentProfile />} />
            </Route>
          </Route>

          {/* admins only: every admin page shares the sidebar (AdminLayout) */}
          <Route element={<ProtectedRoute role="admin" />}>
            <Route element={<AdminLayout />}>
              <Route path="/admin" element={<AdminDashboard />} />
              <Route path="/admin/requests" element={<ManageRequests />} />
              <Route path="/admin/courses" element={<ManageCourses />} />
              <Route path="/admin/upload" element={<AdminUpload />} />
              <Route path="/admin/profile" element={<AdminProfile />} />
            </Route>
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
