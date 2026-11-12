import { useState } from 'react'
import Modal from './Modal'

// Hộp xác nhận; withReason=true thì bắt buộc nhập lý do (ít nhất 3 ký tự)
export default function ConfirmModal({ open, title, message, confirmText = 'Xác nhận', danger, withReason, onConfirm, onClose }) {
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async () => {
    setBusy(true)
    try {
      await onConfirm(reason.trim())
      setReason('')
    } finally {
      setBusy(false)
    }
  }

  const invalid = withReason && reason.trim().length < 3
  return (
    <Modal open={open} onClose={onClose} title={title}>
      {message && <p className="text-sm text-gray-700 mb-3">{message}</p>}
      {withReason && (
        <textarea
          value={reason}
          onChange={e => setReason(e.target.value)}
          rows={3}
          placeholder="Lý do (bắt buộc)"
          className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-500"
        />
      )}
      <div className="flex justify-end gap-2 mt-4">
        <button onClick={onClose} className="px-4 py-2 text-sm border rounded-lg hover:bg-gray-50">Hủy bỏ</button>
        <button
          onClick={submit}
          disabled={busy || invalid}
          className={`px-4 py-2 text-sm text-white rounded-lg disabled:opacity-50 ${danger ? 'bg-red-600 hover:bg-red-700' : 'bg-primary-600 hover:bg-primary-700'}`}
        >
          {busy ? 'Đang xử lý...' : confirmText}
        </button>
      </div>
    </Modal>
  )
}
