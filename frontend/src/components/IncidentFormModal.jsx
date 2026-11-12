import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import Modal from './Modal'
import { createIncident, updateIncident, getAttackTypes } from '../api'
import { SEVERITY, SOURCES, errMsg, toLocalInput, fromLocalInput } from '../utils/format'

const empty = () => ({
  title: '', description: '', attack_type: 'ddos', severity: 'medium',
  occurred_at: toLocalInput(), source: 'ids_ips',
})

const field = 'w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-500'

// incident = null: tạo mới; có dữ liệu: sửa
export default function IncidentFormModal({ open, incident, onClose, onSaved }) {
  const [form, setForm] = useState(empty())
  const [types, setTypes] = useState([])
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!open) return
    getAttackTypes().then(r => setTypes(r.data.filter(t => t.is_active))).catch(() => {})
    setForm(incident ? {
      title: incident.title, description: incident.description || '',
      attack_type: incident.attack_type, severity: incident.severity,
      occurred_at: toLocalInput(incident.occurred_at), source: incident.source,
    } : empty())
  }, [open, incident])

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    const payload = { ...form, occurred_at: fromLocalInput(form.occurred_at), description: form.description || null }
    try {
      const res = incident ? await updateIncident(incident.id, payload) : await createIncident(payload)
      toast.success(incident ? 'Đã lưu thay đổi' : `Đã tạo sự cố ${res.data.code}`)
      onSaved(res.data)
    } catch (err) {
      toast.error(errMsg(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title={incident ? `Sửa sự cố ${incident.code}` : 'Tạo sự cố mới'}>
      <form onSubmit={submit} className="space-y-3">
        <div>
          <label className="block text-sm text-gray-600 mb-1">Tiêu đề *</label>
          <input className={field} value={form.title} onChange={set('title')} required minLength={3} maxLength={200} />
        </div>
        <div>
          <label className="block text-sm text-gray-600 mb-1">Mô tả</label>
          <textarea className={field} rows={3} value={form.description} onChange={set('description')} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm text-gray-600 mb-1">Loại tấn công *</label>
            <select className={field} value={form.attack_type} onChange={set('attack_type')}>
              {types.map(t => <option key={t.code} value={t.code}>{t.name_vi}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm text-gray-600 mb-1">Mức độ *</label>
            <select className={field} value={form.severity} onChange={set('severity')}>
              {Object.entries(SEVERITY).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm text-gray-600 mb-1">Thời gian xảy ra *</label>
            <input type="datetime-local" className={field} value={form.occurred_at} onChange={set('occurred_at')} required />
          </div>
          <div>
            <label className="block text-sm text-gray-600 mb-1">Nguồn *</label>
            <select className={field} value={form.source} onChange={set('source')}>
              {Object.entries(SOURCES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
        </div>
        {!incident && <p className="text-xs text-gray-500">Trạng thái mặc định: Mới.</p>}
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" onClick={onClose} className="px-4 py-2 text-sm border rounded-lg hover:bg-gray-50">Hủy bỏ</button>
          <button disabled={busy} className="px-4 py-2 text-sm bg-primary-600 hover:bg-primary-700 text-white rounded-lg disabled:opacity-50">
            {busy ? 'Đang lưu...' : 'Lưu'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
