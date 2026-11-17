import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import toast from 'react-hot-toast'
import Modal from './Modal'
import Badge from './Badge'
import { getAlert, getAlertMoves, verifyAlert } from '../api'
import { VERIFICATION, DATA_TYPES, formatDateTime, pct, errMsg } from '../utils/format'

export default function AlertDetailModal({ alertId, onClose, onChanged }) {
  const [alert, setAlert] = useState(null)
  const [moves, setMoves] = useState([])
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    try {
      const [a, m] = await Promise.all([getAlert(alertId), getAlertMoves(alertId)])
      setAlert(a.data); setMoves(m.data); setNote(a.data.note || '')
    } catch (err) {
      toast.error(errMsg(err))
    }
  }, [alertId])

  useEffect(() => { setAlert(null); load() }, [load])

  const verify = async (status) => {
    setBusy(true)
    try {
      await verifyAlert(alertId, { status, note: note.trim() || null })
      toast.success('Đã cập nhật')
      await load()
      onChanged()
    } catch (err) {
      toast.error(errMsg(err))
    } finally {
      setBusy(false)
    }
  }

  const rd = alert?.row_data
  return (
    <Modal open onClose={onClose} title={`Cảnh báo #${alertId}`} wide>
      {!alert ? <div className="py-8 text-center text-gray-500">Đang tải...</div> : (
        <div className="space-y-4 text-sm">
          <div className="grid grid-cols-2 gap-x-6 gap-y-2">
            <div><span className="text-gray-500">Nhãn dự đoán:</span> <b>{alert.predicted_label}</b></div>
            <div><span className="text-gray-500">Confidence:</span> <b>{pct(alert.confidence, 2)}</b></div>
            <div><span className="text-gray-500">Nguồn:</span> {DATA_TYPES[alert.source_type]}</div>
            <div><span className="text-gray-500">Trạng thái:</span> <Badge info={VERIFICATION[alert.verification_status]} /></div>
            <div><span className="text-gray-500">File:</span> {alert.upload_filename}</div>
            <div><span className="text-gray-500">Vị trí trong file:</span> dòng dữ liệu {alert.row_index}</div>
            <div><span className="text-gray-500">Sự cố:</span> {alert.incident_id
              ? <Link className="text-primary-600" to={`/incidents/${alert.incident_id}`}>{alert.incident_code}</Link>
              : <i className="text-gray-500">chưa gắn sự cố</i>}</div>
            <div><span className="text-gray-500">Tạo lúc:</span> {formatDateTime(alert.created_at)}</div>
            {alert.verified_by_name && (
              <div className="col-span-2"><span className="text-gray-500">Xác minh bởi:</span> {alert.verified_by_name} lúc {formatDateTime(alert.verified_at)}</div>
            )}
          </div>

          <div>
            <div className="font-medium text-gray-800 mb-1">Dữ liệu dòng gốc</div>
            {alert.source_type === 'email' && rd ? (
              <div className="border rounded-lg p-3 bg-gray-50 space-y-1">
                <div><span className="text-gray-500">Tiêu đề:</span> {rd.subject}</div>
                <div><span className="text-gray-500">Người gửi:</span> {rd.sender || '—'}</div>
                <div><span className="text-gray-500">URL:</span> {(rd.urls || []).join(', ') || '—'}</div>
                <div><span className="text-gray-500">Tệp đính kèm:</span> {(rd.attachments || []).join(', ') || '—'}</div>
                {rd.source_file && <div><span className="text-gray-500">File thư trong ZIP:</span> {rd.source_file}</div>}
                <pre className="whitespace-pre-wrap text-xs bg-white border rounded p-2 max-h-48 overflow-auto">{rd.body}</pre>
              </div>
            ) : rd ? (
              <div className="border rounded-lg max-h-64 overflow-auto">
                <table className="w-full text-xs">
                  <tbody>
                    {Object.entries(rd).map(([k, v]) => (
                      <tr key={k} className="border-b last:border-0">
                        <td className="px-3 py-1 text-gray-600">{k.trim()}</td>
                        <td className="px-3 py-1 text-right font-mono">{String(v)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : <div className="text-gray-500">Không có dữ liệu</div>}
          </div>

          <div>
            <div className="font-medium text-gray-800 mb-1">Xác minh</div>
            <textarea value={note} onChange={e => setNote(e.target.value)} rows={2} placeholder="Ghi chú"
              className="w-full border rounded-lg px-3 py-2" />
            <div className="flex gap-2 mt-2">
              <button disabled={busy || !alert.incident_id} onClick={() => verify('verified')}
                className="px-3 py-1.5 bg-green-600 hover:bg-green-700 text-white rounded-lg disabled:opacity-50">Đã xác minh</button>
              <button disabled={busy || !alert.incident_id} onClick={() => verify('dismissed')}
                className="px-3 py-1.5 bg-yellow-500 hover:bg-yellow-600 text-white rounded-lg disabled:opacity-50">Bỏ qua</button>
              <button disabled={busy || !alert.incident_id} onClick={() => verify('unverified')}
                className="px-3 py-1.5 border rounded-lg hover:bg-gray-50 disabled:opacity-50">Đặt lại</button>
            </div>
            {!alert.incident_id && <div className="text-xs text-gray-500 mt-1">Cần gắn cảnh báo vào một sự cố trước khi xác minh.</div>}
          </div>

          {moves.length > 0 && (
            <div>
              <div className="font-medium text-gray-800 mb-1">Lịch sử chuyển</div>
              <ul className="border rounded-lg divide-y">
                {moves.map(m => (
                  <li key={m.id} className="px-3 py-2 text-xs">
                    {formatDateTime(m.moved_at)} · {m.moved_by_name} ·{' '}
                    {m.from_incident_id ? `từ sự cố #${m.from_incident_id}` : 'từ chưa gắn'} →{' '}
                    {m.to_incident_id ? `sự cố #${m.to_incident_id}` : 'gỡ khỏi sự cố'}
                    {m.reason && <span className="text-gray-500"> ({m.reason})</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </Modal>
  )
}