import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import toast from 'react-hot-toast'

export default function Login() {
  const [form, setForm] = useState({ username: '', password: '' })
  const [loading, setLoading] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      await login(form.username, form.password)
      toast.success('Đăng nhập thành công')
      navigate('/')
    } catch {
      toast.error('Sai tên đăng nhập hoặc mật khẩu')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-900 flex items-center justify-center">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="text-4xl mb-3">🛡️</div>
          <h1 className="text-white text-2xl font-bold">IR Platform</h1>
          <p className="text-gray-400 text-sm mt-1">Hệ thống quản lý sự cố an ninh mạng</p>
        </div>

        {/* Form */}
        <div className="bg-gray-800 rounded-xl p-8 shadow-xl border border-gray-700">
          <h2 className="text-white text-lg font-semibold mb-6">Đăng nhập</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Tên đăng nhập</label>
              <input
                type="text"
                value={form.username}
                onChange={e => setForm({...form, username: e.target.value})}
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:border-primary-500 placeholder-gray-500"
                placeholder="analyst01"
                required
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Mật khẩu</label>
              <input
                type="password"
                value={form.password}
                onChange={e => setForm({...form, password: e.target.value})}
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:border-primary-500 placeholder-gray-500"
                placeholder="••••••••"
                required
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-primary-600 hover:bg-primary-700 disabled:opacity-50 text-white rounded-lg py-2.5 text-sm font-medium transition-colors mt-2"
            >
              {loading ? 'Đang đăng nhập...' : 'Đăng nhập'}
            </button>
          </form>

          {/* Quick login hints */}
          <div className="mt-6 pt-4 border-t border-gray-700">
            <p className="text-xs text-gray-500 mb-2">Tài khoản test:</p>
            <div className="space-y-1">
              {[
                { user: 'analyst01', role: 'Analyst/SOC (commander)', color: 'text-purple-400' },
                { user: 'analyst02', role: 'Analyst/SOC', color: 'text-purple-400' },
                { user: 'it01',      role: 'IT/Helpdesk', color: 'text-blue-400' },
                { user: 'stakeholder01', role: 'Stakeholder', color: 'text-green-400' },
                { user: 'auditor01', role: 'Auditor (chỉ đọc)', color: 'text-amber-400' },
              ].map(u => (
                <button
                  key={u.user}
                  onClick={() => setForm({ username: u.user, password: 'Test@1234' })}
                  className="w-full text-left text-xs px-3 py-1.5 rounded hover:bg-gray-700 transition-colors flex justify-between"
                >
                  <span className="text-gray-300">{u.user}</span>
                  <span className={u.color}>{u.role}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}