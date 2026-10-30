import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getAlerts, createAlert, uploadCSV } from '../api/alerts'
import Badge from '../components/Badge'
import ZoneBadge, { ZONE_OPTIONS } from '../components/ZoneBadge'
import Modal from '../components/Modal'
import LoadingSpinner from '../components/LoadingSpinner'
import toast from 'react-hot-toast'
import { useAuth } from '../context/AuthContext'

const STATUSES = ['', 'new', 'reviewing', 'triaged', 'escalated', 'false_positive', 'closed']
const SOURCES  = ['ids_ips', 'email', 'endpoint', 'manual', 'webhook', 'csv_upload']
const SEVERITIES = ['critical', 'high', 'medium', 'low', 'info']

export default function AlertList() {
  const { user } = useAuth()
  const [alerts, setAlerts]     = useState([])
  const [loading, setLoading]   = useState(true)
  const [status, setStatus]     = useState('')
  const [zone, setZone]         = useState('')
  const [byPriority, setByPriority] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  const [creating, setCreating] = useState(false)
  const [form, setForm]         = useState({
    title: '', description: '', source: 'manual',
    severity: 'medium', ioc: '', affected_asset: ''
  })

  const canWrite = ['analyst_soc', 'it_helpdesk'].includes(user?.role)

  const load = () => {
    setLoading(true)
    getAlerts(status || undefined, { zone: zone || undefined, order: byPriority ? 'priority' : undefined })
      .then(r => setAlerts(r.data))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [status, zone, byPriority])

  const handleCreate = async (e) => {
    e.preventDefault()
    setCreating(true)
    try {
      await createAlert({
        ...form,
        affected_asset: form.affected_asset ? parseInt(form.affected_asset) : null
      })
      toast.success('Tạo cảnh báo thành công')
      setShowCreate(false)
      setForm({ title: '', description: '', source: 'manual', severity: 'medium', ioc: '', affected_asset: '' })
      load()
    } catch {
      toast.error('Tạo cảnh báo thất bại')
    } finally {
      setCreating(false)
    }
  }

  const handleUploadCSV = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    try {
      const res = await uploadCSV(file)
      toast.success(`Đã nhập ${res.data.length} cảnh báo từ CSV`)
      load()
    } catch {
      toast.error('Upload CSV thất bại')
    }
    e.target.value = ''
  }

  const severityOrder = { critical: 0, high: 1, medium: 2, low: 3, info: 4 }
  const sorted = byPriority ? alerts : [...alerts].sort((a, b) =>
    (severityOrder[a.severity] ?? 5) - (severityOrder[b.severity] ?? 5)
  )

  return (
    <div className="p-6 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-gray-900">Cảnh báo</h1>
          <p className="text-sm text-gray-500 mt-0.5">{alerts.length} cảnh báo</p>
        </div>
        {canWrite && (
          <div className="flex gap-2">
            <label className="cursor-pointer bg-white border border-gray-200 hover:bg-gray-50 text-gray-700 text-sm px-3 py-2 rounded-lg transition-colors">
              📂 Upload CSV
              <input type="file" accept=".csv" className="hidden" onChange={handleUploadCSV} />
            </label>
            <button
              onClick={() => setShowCreate(true)}
              className="bg-primary-600 hover:bg-primary-700 text-white text-sm px-4 py-2 rounded-lg transition-colors"
            >
              + Tạo cảnh báo
            </button>
          </div>
        )}
      </div>

      {/* Filter */}
      <div className="flex gap-2 flex-wrap">
        {STATUSES.map(s => (
          <button
            key={s}
            onClick={() => setStatus(s)}
            className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
              status === s
                ? 'bg-primary-600 text-white border-primary-600'
                : 'bg-white text-gray-600 border-gray-200 hover:border-primary-300'
            }`}
          >
            {s || 'Tất cả'}
          </button>
        ))}
      </div>

      <div className="flex gap-2 flex-wrap items-center">
        {ZONE_OPTIONS.map(([k, label]) => (
          <button key={k} onClick={() => setZone(k)}
            className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
              zone === k ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-white text-gray-600 border-gray-200 hover:border-indigo-300'
            }`}>{label}</button>
        ))}
        <label className="ml-auto flex items-center gap-2 text-xs text-gray-600">
          <input type="checkbox" checked={byPriority} onChange={e => setByPriority(e.target.checked)} className="rounded border-gray-300" />
          Xếp theo điểm ưu tiên AI
        </label>
      </div>

      {/* Table */}
      {loading ? <LoadingSpinner /> : (
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 w-10">#</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500">Tiêu đề</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500">Mức độ</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500">Ưu tiên AI</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500">Trạng thái</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500">Nguồn</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500">IOC</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500">Thời gian</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {sorted.length === 0 ? (
                <tr>
                  <td colSpan={8} className="text-center py-12 text-gray-400">
                    Không có cảnh báo nào
                  </td>
                </tr>
              ) : sorted.map(a => (
                <tr key={a.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 text-gray-400 text-xs">{a.id}</td>
                  <td className="px-4 py-3">
                    <Link
                      to={`/alerts/${a.id}`}
                      className="text-gray-900 hover:text-primary-600 font-medium hover:underline"
                    >
                      {a.title}
                    </Link>
                    {a.incident_id && (
                      <span className="ml-2 text-xs text-purple-500">→ INC#{a.incident_id}</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <Badge label={a.severity} type={a.severity} />
                  </td>
                  <td className="px-4 py-3">
                    <ZoneBadge zone={a.ml_zone} score={a.ml_priority} />
                  </td>
                  <td className="px-4 py-3">
                    <Badge label={a.status} type={a.status} />
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-xs">{a.source}</td>
                  <td className="px-4 py-3 text-gray-500 text-xs font-mono">
                    {a.ioc ? a.ioc.split(',')[0] : '—'}
                  </td>
                  <td className="px-4 py-3 text-gray-400 text-xs">
                    {new Date(a.created_at).toLocaleString('vi-VN')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Modal tạo alert */}
      <Modal open={showCreate} onClose={() => setShowCreate(false)} title="Tạo cảnh báo mới">
        <form onSubmit={handleCreate} className="space-y-4">
          <div>
            <label className="block text-xs text-gray-600 mb-1">Tiêu đề *</label>
            <input
              value={form.title}
              onChange={e => setForm({...form, title: e.target.value})}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-400"
              required
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-600 mb-1">Nguồn</label>
              <select
                value={form.source}
                onChange={e => setForm({...form, source: e.target.value})}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-400"
              >
                {SOURCES.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">Mức độ</label>
              <select
                value={form.severity}
                onChange={e => setForm({...form, severity: e.target.value})}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-400"
              >
                {SEVERITIES.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">Mô tả</label>
            <textarea
              value={form.description}
              onChange={e => setForm({...form, description: e.target.value})}
              rows={3}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-400 resize-none"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-600 mb-1">IOC</label>
              <input
                value={form.ioc}
                onChange={e => setForm({...form, ioc: e.target.value})}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-400"
                placeholder="1.2.3.4, domain.com"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">Asset ID</label>
              <input
                type="number"
                value={form.affected_asset}
                onChange={e => setForm({...form, affected_asset: e.target.value})}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-400"
              />
            </div>
          </div>
          <div className="flex gap-2 pt-2">
            <button
              type="button"
              onClick={() => setShowCreate(false)}
              className="flex-1 border border-gray-200 text-gray-600 rounded-lg py-2 text-sm hover:bg-gray-50"
            >
              Hủy
            </button>
            <button
              type="submit"
              disabled={creating}
              className="flex-1 bg-primary-600 text-white rounded-lg py-2 text-sm hover:bg-primary-700 disabled:opacity-50"
            >
              {creating ? 'Đang tạo...' : 'Tạo cảnh báo'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  )
}