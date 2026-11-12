import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import Modal from './Modal'
import { listIncidents, moveAlerts } from '../api'
import { errMsg } from '../utils/format'

// Chuyển cảnh báo sang sự cố khác, hoặc gỡ khỏi sự cố (không chọn sự cố đích)
export default function MoveAlertsModal({ open, alertIds, currentIncidentId, onClose, onDone }) {
  const [targets, setTargets] = useState([])
  const [mode, setMode] = useState('move')
  const [target, setTarget] = useState('')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!open) return
    setMode('move'); setTarget(''); setReason('')
    listIncidents({ status: 'new,in_progress', page_size: 200, sort_by: 'created_at', order: 'desc' })
      .then(r => setTargets(r.data.items.filter(i => i.id !== currentIncidentId)))
      .catch(() => {})
  }, [open, currentIncidentId])

  const submit = async () => {
    setBusy(true)
    try {
      await moveAlerts({
        alert_ids: alertIds,
        to_incident_id: mode === 'move' ? Number(target) : null,
        reason: reason.trim() || null,
      })
      toast.success(mode === 'move' ? `Đã chuyển ${alertIds.length} cảnh báo` : `Đã gỡ ${alertIds.length} cảnh báo khỏi sự cố`)
      onDone()
    } catch (err) {
      toast.error(errMsg(err))
    } finally {
      setBusy(false)
    }
  }

  const invalid = mode === 'move' && !target
  return (
    <Modal open={open} onClose={onClose} title={`Chuyển hoặc gỡ ${alertIds.length} cảnh báo`}>
      <div className="space-y-3 text-sm">
        <label className="flex items-start gap-2">
          <input type="radio" checked={mode === 'move'} onChange={() => setMode('move')} className="mt-1" />
          <div className="flex-1">
            <div className="font-medium">Chuyển sang sự cố khác</div>
            <select disabled={mode !== 'move'} value={target} onChange={e => setTarget(e.target.value)}
              className="mt-1 w-full border rounded-lg px-3 py-2 disabled:bg-gray-100">
              <option value="">— Chọn sự cố đích (Mới hoặc Đang xử lý) —</option>
              {targets.map(i => <option key={i.id} value={i.id}>{i.code} · {i.title}</option>)}
            </select>
          </div>
        </label>
        <label className="flex items-start gap-2">
          <input type="radio" checked={mode === 'remove'} onChange={() => setMode('remove')} className="mt-1" />
          <div>
            <div className="font-medium">Gỡ khỏi sự cố (gắn nhầm)</div>
            <div className="text-gray-500 text-xs">Cảnh báo chuyển sang danh sách “Chưa gắn sự cố” và có thể gắn lại sau.</div>
          </div>
        </label>
        <textarea value={reason} onChange={e => setReason(e.target.value)} rows={2} placeholder="Lý do (không bắt buộc)"
          className="w-full border rounded-lg px-3 py-2" />
      </div>
      <div className="flex justify-end gap-2 mt-4">
        <button onClick={onClose} className="px-4 py-2 text-sm border rounded-lg hover:bg-gray-50">Hủy bỏ</button>
        <button onClick={submit} disabled={busy || invalid}
          className="px-4 py-2 text-sm bg-primary-600 hover:bg-primary-700 text-white rounded-lg disabled:opacity-50">
          {busy ? 'Đang xử lý...' : 'Thực hiện'}
        </button>
      </div>
    </Modal>
  )
}
