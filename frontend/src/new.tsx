import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { GuestRoute, ProtectedRoute } from './components/RouteGuards'
import { AuthProvider } from './context/AuthContext'
import AdminHome from './pages/AdminHome'
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
          {/* opened from the confirmation email, usually before the student has ever logged in */}
          <Route path="/confirm-email" element={<ConfirmEmail />} />

          {/* students only: every student page shares the sidebar (StudentLayout) */}
          <Route element={<ProtectedRoute role="student" />}>
            <Route element={<StudentLayout />}>
              <Route path="/student" element={<StudentSearch />} />
              <Route path="/student/upload" element={<UploadPdf />} />
              <Route path="/student/profile" element={<StudentProfile />} />
            </Route>
          </Route>

          {/* admins only: replace AdminHome with the Admin Dashboard */}
          <Route element={<ProtectedRoute role="admin" />}>
            <Route path="/admin" element={<AdminHome />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
