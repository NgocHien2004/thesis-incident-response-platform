import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getAudit, verifyAudit, downloadAuditCsv } from '../api/audit'
import LoadingSpinner from '../components/LoadingSpinner'
import toast from 'react-hot-toast'
import { useAuth } from '../context/AuthContext'

const ROLE_LABEL = {
  analyst_soc: 'Analyst', it_helpdesk: 'IT', stakeholder: 'Stakeholder',
}
const ENTITIES = ['asset', 'alert', 'incident', 'evidence', 'custody', 'impact',
  'containment', 'recovery', 'communication', 'postmortem', 'auth', 'user']
const PAGE = 50

export default function AuditLog() {
  const { user } = useAuth()
  const allowed = user?.role === 'analyst_soc'

  const [data, setData]       = useState({ total: 0, items: [] })
  const [loading, setLoading] = useState(true)
  const [offset, setOffset]   = useState(0)
  const [open, setOpen]       = useState(null)
  const [chain, setChain]     = useState(null)
  const [filters, setFilters] = useState({ username: '', entity_type: '', action: '', incident_id: '' })

  const params = () => Object.fromEntries(
    Object.entries({ ...filters, limit: PAGE, offset }).filter(([, v]) => v !== '' && v !== null)
  )

  const load = () => {
    setLoading(true)
    getAudit(params())
      .then(r => setData(r.data))
      .catch(err => toast.error(err.response?.data?.detail || 'Không tải được nhật ký'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { if (allowed) load() }, [offset])  // eslint-disable-line

  const applyFilters = (e) => { e.preventDefault(); if (offset === 0) load(); else setOffset(0) }

  const handleVerify = async () => {
    try {
      const r = await verifyAudit()
      setChain(r.data)
      if (r.data.ok) toast.success(`Chuỗi băm nguyên vẹn (${r.data.total} bản ghi)`)
      else toast.error(`Chuỗi băm bị phá vỡ tại bản ghi #${r.data.first_bad_id}`)
    } catch { toast.error('Không kiểm tra được') }
  }

  const handleExport = () => {
    const { limit, offset: _o, ...rest } = params()
    downloadAuditCsv(rest).catch(() => toast.error('Xuất CSV thất bại'))
  }

  if (!allowed) {
    return <div className="p-6 text-sm text-gray-500">Chỉ Analyst/SOC mới xem được nhật ký kiểm toán.</div>
  }

  const inputCls = 'border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-primary-400'
  const to = Math.min(offset + PAGE, data.total)

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold text-gray-900">Nhật ký kiểm toán</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Ghi tự động mọi thay đổi dữ liệu và đăng nhập: ai làm gì, lúc nào. Chỉ thêm vào, không sửa hoặc xóa.
          </p>
        </div>
        <div className="flex gap-2 flex-shrink-0">
          <button onClick={handleVerify}
            className="text-sm px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50">
            Kiểm tra toàn vẹn
          </button>
          <button onClick={handleExport}
            className="text-sm px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg">
            Xuất CSV
          </button>
        </div>
      </div>

      {chain && (
        <div className={`text-sm px-4 py-2 rounded-lg border ${
          chain.ok ? 'bg-green-50 border-green-200 text-green-700' : 'bg-red-50 border-red-200 text-red-700'}`}>
          {chain.ok
            ? `Chuỗi băm nguyên vẹn: ${chain.total} bản ghi không bị chỉnh sửa.`
            : `Phát hiện bản ghi bị chỉnh sửa hoặc xóa, bắt đầu từ #${chain.first_bad_id}.`}
        </div>
      )}

      <form onSubmit={applyFilters} className="flex gap-2 flex-wrap items-center">
        <input className={inputCls} placeholder="Người dùng" value={filters.username}
          onChange={e => setFilters({ ...filters, username: e.target.value })}/>
        <select className={`${inputCls} bg-white`} value={filters.entity_type}
          onChange={e => setFilters({ ...filters, entity_type: e.target.value })}>
          <option value="">Mọi đối tượng</option>
          {ENTITIES.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <input className={inputCls} placeholder="Hành động (vd: containment)" value={filters.action}
          onChange={e => setFilters({ ...filters, action: e.target.value })}/>
        <input className={`${inputCls} w-28`} placeholder="Incident #" value={filters.incident_id}
          onChange={e => setFilters({ ...filters, incident_id: e.target.value.replace(/\D/g, '') })}/>
        <button type="submit" className="text-sm px-4 py-1.5 bg-gray-800 text-white rounded-lg">Lọc</button>
      </form>

      {loading ? <LoadingSpinner/> : (
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200 text-left">
                <th className="px-4 py-3 text-xs font-semibold text-gray-500">Thời gian</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500">Người dùng</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500">Hành động</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500">Đối tượng</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500">Incident</th>
                <th className="px-4 py-3 w-16"/>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {data.items.length === 0 ? (
                <tr><td colSpan={6} className="text-center py-10 text-gray-400">Không có bản ghi</td></tr>
              ) : data.items.map(r => (
                <>
                  <tr key={r.id} className="hover:bg-gray-50">
                    <td className="px-4 py-2.5 text-xs text-gray-500 font-mono whitespace-nowrap">
                      {new Date(r.at).toLocaleString('vi-VN')}
                    </td>
                    <td className="px-4 py-2.5 text-gray-800">
                      {r.username || 'system'}
                      {r.role && <span className="ml-2 text-xs text-gray-400">{ROLE_LABEL[r.role] || r.role}</span>}
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="text-gray-800">{r.label}</div>
                      <div className="text-xs text-gray-400 font-mono">{r.action}</div>
                    </td>
                    <td className="px-4 py-2.5 text-xs text-gray-600">
                      {r.entity_type}{r.entity_id ? ` #${r.entity_id}` : ''}
                    </td>
                    <td className="px-4 py-2.5 text-xs">
                      {r.incident_id
                        ? <Link to={`/incidents/${r.incident_id}`} className="text-primary-600 hover:underline">#{r.incident_id}</Link>
                        : <span className="text-gray-300">—</span>}
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      {Object.keys(r.detail || {}).length > 0 && (
                        <button onClick={() => setOpen(open === r.id ? null : r.id)}
                          className="text-xs text-primary-600 hover:underline">
                          {open === r.id ? 'Ẩn' : 'Chi tiết'}
                        </button>
                      )}
                    </td>
                  </tr>
                  {open === r.id && (
                    <tr key={`${r.id}-d`} className="bg-gray-50">
                      <td colSpan={6} className="px-4 py-3">
                        <pre className="text-xs text-gray-700 whitespace-pre-wrap break-words">
                          {JSON.stringify(r.detail, null, 2)}
                        </pre>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex items-center justify-between text-sm text-gray-500">
        <span>{data.total === 0 ? '0 bản ghi' : `${offset + 1}–${to} / ${data.total} bản ghi`}</span>
        <div className="flex gap-2">
          <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}
            className="px-3 py-1 border border-gray-200 rounded-lg disabled:opacity-40">← Trước</button>
          <button disabled={to >= data.total} onClick={() => setOffset(offset + PAGE)}
            className="px-3 py-1 border border-gray-200 rounded-lg disabled:opacity-40">Sau →</button>
        </div>
      </div>
    </div>
  )
}
