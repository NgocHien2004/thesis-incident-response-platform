import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const navItems = [
  { path: '/',          label: 'Dashboard',  icon: '📊' },
  { path: '/alerts',    label: 'Cảnh báo',   icon: '🚨' },
  { path: '/incidents', label: 'Sự cố',      icon: '🔥' },
  { path: '/assets',    label: 'Tài sản',    icon: '🖥️' },
  { path: '/playbooks', label: 'Playbook',   icon: '📘', roles: ['analyst_soc', 'it_helpdesk'] },
  { path: '/audit',     label: 'Nhật ký',    icon: '🧾', roles: ['analyst_soc'] },
  { path: '/accounts',  label: 'Tài khoản',  icon: '👤', roles: ['analyst_soc'] },
]

const roleColors = {
  analyst_soc:  'bg-purple-100 text-purple-700',
  it_helpdesk:  'bg-blue-100 text-blue-700',
  stakeholder:  'bg-green-100 text-green-700',
}

export default function Layout({ children }) {
  const { user, logout } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <aside className="w-56 bg-gray-900 flex flex-col">
        <div className="px-5 py-4 border-b border-gray-700">
          <div className="text-white font-bold text-sm">🛡️ IR Platform</div>
          <div className="text-gray-400 text-xs mt-0.5">Incident Response</div>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.filter(item => !item.roles || item.roles.includes(user?.role)).map(item => (
            <Link
              key={item.path}
              to={item.path}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                location.pathname === item.path
                  ? 'bg-primary-600 text-white'
                  : 'text-gray-300 hover:bg-gray-700'
              }`}
            >
              <span>{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          ))}
        </nav>
        <div className="px-4 py-4 border-t border-gray-700">
          <div className="text-xs text-gray-400 mb-1">{user?.username}</div>
          <span className={`text-xs px-2 py-0.5 rounded font-medium ${roleColors[user?.role] || 'bg-gray-700 text-gray-300'}`}>
            {user?.role?.replace('_', ' ')}
          </span>
          <button
            onClick={handleLogout}
            className="mt-3 w-full text-xs text-gray-400 hover:text-white text-left"
          >
            Đăng xuất →
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-auto">
        {children}
      </main>
    </div>
  )
}