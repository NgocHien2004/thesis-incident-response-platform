import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { AuthProvider, useAuth } from './context/AuthContext'
import Layout from './components/Layout'
import Login from './pages/Login'
import LoadingSpinner from './components/LoadingSpinner'
import IncidentList from './pages/IncidentList'
import IncidentDetail from './pages/IncidentDetail'
import AlertList from './pages/AlertList'
import Settings from './pages/Settings'

// Dashboard chứa recharts (nặng), chỉ nạp khi cần
const Dashboard = lazy(() => import('./pages/Dashboard'))

function PrivateRoute({ children }) {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />
  return <Layout><Suspense fallback={<LoadingSpinner />}>{children}</Suspense></Layout>
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Toaster position="top-right" />
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
          <Route path="/incidents" element={<PrivateRoute><IncidentList /></PrivateRoute>} />
          <Route path="/incidents/:id" element={<PrivateRoute><IncidentDetail /></PrivateRoute>} />
          <Route path="/alerts" element={<PrivateRoute><AlertList /></PrivateRoute>} />
          <Route path="/settings" element={<PrivateRoute><Settings /></PrivateRoute>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}