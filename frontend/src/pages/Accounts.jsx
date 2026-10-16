import { useState } from 'react'
import { register } from '../api/auth'
import Card from '../components/Card'
import toast from 'react-hot-toast'
import { useAuth } from '../context/AuthContext'

const ROLES = [
  { value: 'it_helpdesk', label: 'IT / Helpdesk', hint: 'Nhập cảnh báo, triage, thu thập bằng chứng, đề xuất và thực hiện containment, khôi phục.' },
  { value: 'analyst_soc', label: 'Analyst / SOC', hint: 'Điều tra và điều phối. Có thể được chỉ định làm commander của một vụ việc.' },
  { value: 'stakeholder', label: 'Stakeholder', hint: 'Chủ hệ thống, lãnh đạo, pháp chế, truyền thông: xem vụ việc, xác nhận khôi phục và thông báo.' },
  { value: 'auditor',     label: 'Auditor',     hint: 'Chỉ đọc. Xem toàn bộ dữ liệu và nhật ký kiểm toán, không thay đổi được gì.' },
]

export default function Accounts() {
  const { user } = useAuth()
  const [form, setForm] = useState({ username: '', email: '', password: '', role: 'it_helpdesk' })
  const [saving, setSaving] = useState(false)
  const [created, setCreated] = useState([])

  if (user?.role !== 'analyst_soc') {
    return <div className="p-6 text-sm text-gray-500">Chỉ Analyst/SOC mới được cấp tài khoản.</div>
  }

  const inputCls = 'w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-400'
  const current = ROLES.find(r => r.value === form.role)

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      await register(form)
      toast.success(`Đã tạo tài khoản ${form.username}`)
      setCreated([{ username: form.username, role: current.label }, ...created])
      setForm({ username: '', email: '', password: '', role: form.role })
    } catch (err) {
      const d = err.response?.data?.detail
      toast.error(typeof d === 'string' ? d : Array.isArray(d) ? d.map(x => x.msg).join('; ') : 'Tạo tài khoản thất bại')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="p-6 space-y-4 max-w-2xl">
      <div>
        <h1 className="text-lg font-semibold text-gray-900">Cấp tài khoản</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          Chỉ Analyst/SOC được cấp tài khoản và phân vai trò. Mọi lần cấp đều được ghi vào nhật ký kiểm toán.
        </p>
      </div>
      <Card>
        <form onSubmit={submit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-600 mb-1">Tên đăng nhập *</label>
              <input className={inputCls} required value={form.username}
                onChange={e => setForm({ ...form, username: e.target.value })}/>
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">Email *</label>
              <input className={inputCls} type="email" required value={form.email}
                onChange={e => setForm({ ...form, email: e.target.value })}/>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-600 mb-1">Mật khẩu tạm *</label>
              <input className={inputCls} type="password" required value={form.password}
                onChange={e => setForm({ ...form, password: e.target.value })}/>
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">Vai trò *</label>
              <select className={`${inputCls} bg-white`} value={form.role}
                onChange={e => setForm({ ...form, role: e.target.value })}>
                {ROLES.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
              </select>
            </div>
          </div>
          <p className="text-xs text-gray-500 bg-gray-50 rounded-lg px-3 py-2">{current.hint}</p>
          <button type="submit" disabled={saving}
            className="bg-primary-600 hover:bg-primary-700 text-white text-sm px-4 py-2 rounded-lg disabled:opacity-50">
            {saving ? 'Đang tạo...' : 'Tạo tài khoản'}
          </button>
        </form>
      </Card>
      {created.length > 0 && (
        <Card title="Đã tạo trong phiên này">
          <ul className="text-sm text-gray-700 space-y-1">
            {created.map((c, i) => <li key={i}>{c.username} <span className="text-gray-400">· {c.role}</span></li>)}
          </ul>
        </Card>
      )}
    </div>
  )
}
