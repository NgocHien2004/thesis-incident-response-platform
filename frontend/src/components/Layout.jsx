import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const navItems = [
  { path: '/',          label: 'Dashboard', icon: '📊' },
  { path: '/incidents', label: 'Sự cố',     icon: '🔥' },
  { path: '/alerts',    label: 'Cảnh báo',  icon: '🚨' },
  { path: '/settings',  label: 'Cấu hình',  icon: '⚙️' },
]

export default function Layout({ children }) {
  const { user, logout } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()

  const active = (path) =>
    path === '/' ? location.pathname === '/' : location.pathname.startsWith(path)

  return (
    <div className="flex h-screen bg-gray-50">
      <aside className="w-56 bg-gray-900 flex flex-col">
        <div className="px-5 py-4 border-b border-gray-700">
          <div className="text-white font-bold text-sm">🛡️ Quản lý sự cố</div>
          <div className="text-gray-400 text-xs mt-0.5">AI phân loại cảnh báo</div>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map(item => (
            <Link
              key={item.path}
              to={item.path}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                active(item.path) ? 'bg-primary-600 text-white' : 'text-gray-300 hover:bg-gray-700'
              }`}
            >
              <span>{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          ))}
        </nav>
        <div className="px-4 py-4 border-t border-gray-700">
          <div className="text-sm text-gray-200">{user?.full_name}</div>
          <div className="text-xs text-gray-400">{user?.username}</div>
          <button
            onClick={() => { logout(); navigate('/login') }}
            className="mt-3 w-full text-xs text-gray-400 hover:text-white text-left"
          >
            Đăng xuất →
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-auto">{children}</main>
    </div>
  )
}
