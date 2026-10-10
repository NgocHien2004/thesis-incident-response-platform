import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getIncidents, createIncident } from '../api/incidents'
import { getAlerts } from '../api/alerts'
import Badge from '../components/Badge'
import Modal from '../components/Modal'
import LoadingSpinner from '../components/LoadingSpinner'
import toast from 'react-hot-toast'
import { useAuth } from '../context/AuthContext'

const STATUSES = ['', 'open', 'investigating', 'contained', 'recovering', 'closed']

export default function IncidentList() {
  const { user } = useAuth()
  const [incidents, setIncidents] = useState([])
  const [loading, setLoading]     = useState(true)
  const [status, setStatus]       = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [creating, setCreating]   = useState(false)
  const [triagedAlerts, setTriagedAlerts] = useState([])
  const [form, setForm] = useState({
    title: '', severity: 'high', description: '', alert_ids: []
  })

  const isAnalyst = user?.role === 'analyst_soc'

  const load = () => {
    setLoading(true)
    getIncidents(status || undefined)
      .then(r => setIncidents(r.data))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [status])

  const openCreate = async () => {
    const res = await getAlerts('triaged')
    setTriagedAlerts(res.data)
    setShowCreate(true)
  }

  const toggleAlert = (id) => {
    setForm(f => ({
      ...f,
      alert_ids: f.alert_ids.includes(id)
        ? f.alert_ids.filter(a => a !== id)
        : [...f.alert_ids, id]
    }))
  }

  const handleCreate = async (e) => {
    e.preventDefault()
    if (form.alert_ids.length === 0) {
      toast.error('Chọn ít nhất 1 alert')
      return
    }
    setCreating(true)
    try {
      await createIncident({
        ...form,
        commander_id: parseInt(user?.id),
      })
      toast.success('Tạo incident thành công')
      setShowCreate(false)
      setForm({ title: '', severity: 'high', description: '', alert_ids: [] })
      load()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Tạo thất bại')
    } finally {
      setCreating(false)
    }
  }

  const severityOrder = { critical: 0, high: 1, medium: 2, low: 3 }

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-gray-900">Incidents</h1>
          <p className="text-sm text-gray-500 mt-0.5">{incidents.length} sự cố</p>
        </div>
        {isAnalyst && (
          <button
            onClick={openCreate}
            className="bg-primary-600 hover:bg-primary-700 text-white text-sm px-4 py-2 rounded-lg"
          >
            + Tạo incident
          </button>
        )}
      </div>

      {/* Filter */}
      <div className="flex gap-2 flex-wrap">
        {STATUSES.map(s => (
          <button key={s} onClick={() => setStatus(s)}
            className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
              status === s
                ? 'bg-primary-600 text-white border-primary-600'
                : 'bg-white text-gray-600 border-gray-200 hover:border-primary-300'
            }`}>
            {s || 'Tất cả'}
          </button>
        ))}
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
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500">Trạng thái</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500">Commander</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500">Phát hiện</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500">Đóng lúc</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {incidents.length === 0 ? (
                <tr><td colSpan={7} className="text-center py-12 text-gray-400">Không có incident nào</td></tr>
              ) : [...incidents]
                .sort((a,b) => (severityOrder[a.severity]??5)-(severityOrder[b.severity]??5))
                .map(inc => (
                <tr key={inc.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 text-gray-400 text-xs">{inc.id}</td>
                  <td className="px-4 py-3">
                    <Link to={`/incidents/${inc.id}`}
                      className="text-gray-900 hover:text-primary-600 font-medium hover:underline">
                      {inc.title}
                    </Link>
                  </td>
                  <td className="px-4 py-3"><Badge label={inc.severity} type={inc.severity}/></td>
                  <td className="px-4 py-3"><Badge label={inc.status} type={inc.status}/></td>
                  <td className="px-4 py-3 text-gray-500 text-xs">#{inc.commander_id || '—'}</td>
                  <td className="px-4 py-3 text-gray-400 text-xs">
                    {inc.detected_at ? new Date(inc.detected_at).toLocaleString('vi-VN') : '—'}
                  </td>
                  <td className="px-4 py-3 text-gray-400 text-xs">
                    {inc.resolved_at ? new Date(inc.resolved_at).toLocaleString('vi-VN') : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Modal tạo incident */}
      <Modal open={showCreate} onClose={() => setShowCreate(false)} title="Tạo Incident mới">
        <form onSubmit={handleCreate} className="space-y-4">
          <div>
            <label className="block text-xs text-gray-600 mb-1">Tên incident *</label>
            <input value={form.title}
              onChange={e => setForm({...form, title: e.target.value})}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-400"
              required />
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">Mức độ</label>
            <select value={form.severity}
              onChange={e => setForm({...form, severity: e.target.value})}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-400">
              {['critical','high','medium','low'].map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">Mô tả</label>
            <textarea value={form.description}
              onChange={e => setForm({...form, description: e.target.value})}
              rows={2} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-400 resize-none"/>
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-2">
              Chọn alert đã triage ({form.alert_ids.length} đã chọn)
            </label>
            <div className="max-h-48 overflow-y-auto border border-gray-200 rounded-lg divide-y divide-gray-100">
              {triagedAlerts.length === 0 ? (
                <p className="text-xs text-gray-400 p-3">Không có alert nào đã triage</p>
              ) : triagedAlerts.map(a => (
                <label key={a.id} className="flex items-center gap-3 px-3 py-2 hover:bg-gray-50 cursor-pointer">
                  <input type="checkbox"
                    checked={form.alert_ids.includes(a.id)}
                    onChange={() => toggleAlert(a.id)}
                    className="rounded border-gray-300"/>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-medium text-gray-800 truncate">{a.title}</div>
                    <div className="text-xs text-gray-400">#{a.id} · {a.severity}</div>
                  </div>
                  <Badge label={a.severity} type={a.severity}/>
                </label>
              ))}
            </div>
          </div>
          <div className="flex gap-2">
            <button type="button" onClick={() => setShowCreate(false)}
              className="flex-1 border border-gray-200 text-gray-600 rounded-lg py-2 text-sm hover:bg-gray-50">
              Hủy
            </button>
            <button type="submit" disabled={creating}
              className="flex-1 bg-primary-600 text-white rounded-lg py-2 text-sm hover:bg-primary-700 disabled:opacity-50">
              {creating ? 'Đang tạo...' : 'Tạo incident'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  )
}