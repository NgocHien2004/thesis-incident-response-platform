import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { AuthProvider, useAuth } from './context/AuthContext'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import AlertList from './pages/AlertList'
import AlertDetail from './pages/AlertDetail'
import IncidentList from './pages/IncidentList'
import IncidentDetail from './pages/incidents/IncidentDetail'
import AssetList from './pages/AssetList'
import AuditLog from './pages/AuditLog'
import Accounts from './pages/Accounts'

function PrivateRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return null
  if (!user) return <Navigate to="/login" replace />
  return <Layout>{children}</Layout>
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Toaster position="top-right" />
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
          <Route path="/alerts" element={<PrivateRoute><AlertList /></PrivateRoute>} />
          <Route path="/alerts/:id" element={<PrivateRoute><AlertDetail /></PrivateRoute>} />
          <Route path="/incidents" element={<PrivateRoute><IncidentList /></PrivateRoute>} />
          <Route path="/incidents/:id" element={<PrivateRoute><IncidentDetail /></PrivateRoute>} />
          <Route path="/assets" element={<PrivateRoute><AssetList /></PrivateRoute>} />
          <Route path="/audit" element={<PrivateRoute><AuditLog /></PrivateRoute>} />
          <Route path="/accounts" element={<PrivateRoute><Accounts /></PrivateRoute>} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}