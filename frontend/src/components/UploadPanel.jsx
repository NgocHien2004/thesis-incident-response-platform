import { useEffect, useRef, useState } from 'react'
import toast from 'react-hot-toast'
import Badge from './Badge'
import { createUpload, getModels } from '../api'
import { UPLOAD_STATUS, DATA_TYPES, formatBytes, formatDateTime, pct, errMsg } from '../utils/format'

const ctl = 'border rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:border-primary-500'

function FormatHint({ dataType, models }) {
  const [open, setOpen] = useState(false)
  if (dataType === 'email') {
    return (
      <div className="text-xs text-gray-600 bg-gray-50 border rounded-lg p-3">
        File <b>.csv</b> hoặc <b>.json</b> với các cột bắt buộc: <code>subject</code>, <code>body</code>, <code>sender</code>, <code>urls</code>
        (urls cách nhau bằng dấu cách, phẩy hoặc chấm phẩy; trong JSON có thể là mảng). Mỗi dòng là một thư.
      </div>
    )
  }
  const net = models.find(m => m.task_type === 'network' && m.is_active)
  return (
    <div className="text-xs text-gray-600 bg-gray-50 border rounded-lg p-3">
      File <b>.csv</b> hoặc <b>.json</b> có đủ {net?.features ? net.features.length : 'các'} cột đặc trưng CIC-IDS2017
      (cột thừa như Label, Timestamp được bỏ qua; giá trị Infinity/NaN được quy về 0).
      {net?.features && (
        <>
          {' '}<button onClick={() => setOpen(!open)} className="text-primary-600 hover:underline">{open ? 'Ẩn danh sách cột' : 'Xem danh sách cột'}</button>
          {open && <div className="mt-2 font-mono leading-5 max-h-40 overflow-auto">{net.features.map(f => f.trim()).join(' · ')}</div>}
        </>
      )}
      {!net && <div className="text-red-600 mt-1">Chưa kết nối dịch vụ AI hoặc chưa có mô hình luồng mạng.</div>}
    </div>
  )
}

function LabelBars({ dist }) {
  const entries = Object.entries(dist || {}).sort((a, b) => b[1] - a[1])
  const total = entries.reduce((s, [, n]) => s + n, 0)
  if (!total) return null
  return (
    <div className="space-y-1">
      {entries.map(([label, n]) => (
        <div key={label} className="flex items-center gap-2 text-xs">
          <span className="w-40 truncate text-gray-700" title={label}>{label}</span>
          <div className="flex-1 h-2 bg-gray-100 rounded"><div className="h-2 bg-primary-500 rounded" style={{ width: `${(n / total) * 100}%` }} /></div>
          <span className="w-24 text-right text-gray-600">{n.toLocaleString('vi-VN')} ({((n / total) * 100).toFixed(1)}%)</span>
        </div>
      ))}
    </div>
  )
}

export default function UploadPanel({ incident, uploads, canUpload, onUploaded, onViewAlerts }) {
  const [dataType, setDataType] = useState('network')
  const [file, setFile] = useState(null)
  const [busy, setBusy] = useState(false)
  const [models, setModels] = useState([])
  const inputRef = useRef(null)

  useEffect(() => { getModels().then(r => setModels(r.data)).catch(() => {}) }, [])

  const submit = async (e) => {
    e.preventDefault()
    if (!file) return
    setBusy(true)
    try {
      const res = await createUpload(incident.id, dataType, file)
      toast.success('Đã nhận file, đang xử lý')
      ;(res.data.warnings || []).forEach(w => toast(w, { icon: '⚠️' }))
      setFile(null)
      if (inputRef.current) inputRef.current.value = ''
      onUploaded(res.data)
    } catch (err) {
      toast.error(errMsg(err, 'Upload thất bại'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-4">
      {canUpload ? (
        <form onSubmit={submit} className="bg-white border rounded-lg p-4 space-y-3">
          <div className="font-medium text-gray-800">Tải dữ liệu lên để phân loại</div>
          <div className="flex flex-wrap gap-3 items-center">
            <select className={ctl} value={dataType} onChange={e => setDataType(e.target.value)}>
              {Object.entries(DATA_TYPES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
            <input ref={inputRef} type="file" accept=".csv,.json" onChange={e => setFile(e.target.files[0] || null)} className="text-sm" />
            <button disabled={!file || busy} className="px-4 py-2 text-sm bg-primary-600 hover:bg-primary-700 text-white rounded-lg disabled:opacity-50">
              {busy ? 'Đang gửi...' : 'Upload'}
            </button>
          </div>
          <FormatHint dataType={dataType} models={models} />
        </form>
      ) : (
        <div className="text-sm text-gray-600 bg-yellow-50 border border-yellow-200 rounded-lg px-4 py-3">
          Chỉ upload được khi sự cố ở trạng thái Mới hoặc Đang xử lý.
        </div>
      )}

      {uploads.length === 0 && <div className="text-sm text-gray-500 text-center py-6">Chưa có file nào</div>}
      {uploads.map(u => {
        const active = u.status === 'pending' || u.status === 'processing'
        const progress = u.row_count ? Math.round((u.processed_rows / u.row_count) * 100) : 0
        return (
          <div key={u.id} className="bg-white border rounded-lg p-4 space-y-3">
            <div className="flex flex-wrap items-center gap-2 justify-between">
              <div>
                <span className="font-medium text-gray-900">{u.original_filename}</span>
                <span className="text-xs text-gray-500 ml-2">{DATA_TYPES[u.data_type]} · {formatBytes(u.file_size_bytes)} · {u.row_count?.toLocaleString('vi-VN')} dòng</span>
              </div>
              <Badge info={UPLOAD_STATUS[u.status]} />
            </div>
            {active && (
              <div>
                <div className="h-2 bg-gray-100 rounded"><div className="h-2 bg-blue-500 rounded transition-all" style={{ width: `${progress}%` }} /></div>
                <div className="text-xs text-gray-500 mt-1">Đã xử lý {u.processed_rows.toLocaleString('vi-VN')} / {u.row_count?.toLocaleString('vi-VN')} dòng ({progress}%)</div>
              </div>
            )}
            {u.status === 'failed' && (
              <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                {u.error_message}<div className="text-xs text-red-600 mt-1">Không có cảnh báo nào được tạo từ file này.</div>
              </div>
            )}
            {u.status === 'completed' && (
              <>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                  <div><div className="text-xs text-gray-500">Tổng số mẫu</div><b>{u.row_count.toLocaleString('vi-VN')}</b></div>
                  <div><div className="text-xs text-gray-500">Confidence trung bình</div><b>{pct(u.avg_confidence, 2)}</b></div>
                  <div><div className="text-xs text-gray-500">Cảnh báo sinh ra</div><b>{u.alert_count.toLocaleString('vi-VN')}</b></div>
                  <div><div className="text-xs text-gray-500">Mô hình</div><b>{u.model_version}</b></div>
                </div>
                <div>
                  <div className="text-xs text-gray-500 mb-1">Phân bố nhãn</div>
                  <LabelBars dist={u.label_distribution} />
                </div>
                <div className="text-xs text-gray-500">
                  Ngưỡng đã áp dụng: {pct(u.threshold_used, 0)} · Lớp nguy hiểm: {u.dangerous_labels_used.join(', ') || '—'}
                </div>
                {u.alert_count > 0 && (
                  <button onClick={() => onViewAlerts(u.id)} className="text-sm text-primary-600 hover:underline">Xem {u.alert_count} cảnh báo của file này →</button>
                )}
              </>
            )}
            <div className="text-xs text-gray-400">Upload bởi {u.uploaded_by_name} lúc {formatDateTime(u.uploaded_at)}{u.processed_at && ` · xử lý xong ${formatDateTime(u.processed_at)}`}</div>
          </div>
        )
      })}
    </div>
  )
}
