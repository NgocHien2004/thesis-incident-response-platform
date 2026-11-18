import { useEffect, useRef, useState } from 'react'
import toast from 'react-hot-toast'
import Badge from './Badge'
import { createUpload, getModels } from '../api'
import { useI18n, num, rich } from '../i18n'
import { UPLOAD_STATUS, DATA_TYPES, formatBytes, formatDateTime, pct, errMsg } from '../utils/format'

const ctl = 'border rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:border-primary-500'

function FormatHint({ dataType, models }) {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)
  if (dataType === 'email') {
    return (
      <div className="text-xs text-gray-600 bg-gray-50 border rounded-lg p-3 space-y-1">
        <div>
          {rich(t('File <b>.csv</b> hoặc <b>.json</b> với các cột bắt buộc: <code>subject</code>, <code>body</code>, <code>sender</code>, <code>urls</code> (urls cách nhau bằng dấu cách, phẩy hoặc chấm phẩy; trong JSON có thể là mảng). Mỗi dòng là một thư.'))}
        </div>
        <div>
          {rich(t('Hoặc file thư <b>.eml</b> (một thư), hoặc file <b>.zip</b> chứa nhiều file <b>.eml</b> (tải thư về từ Gmail, Outlook...). Hệ thống tự đọc tiêu đề, người gửi, nội dung và liên kết; tệp đính kèm chỉ ghi tên, không lưu nội dung.'))}
        </div>
      </div>
    )
  }
  const net = models.find(m => m.task_type === 'network' && m.is_active)
  return (
    <div className="text-xs text-gray-600 bg-gray-50 border rounded-lg p-3">
      {net?.features
        ? rich(t('File <b>.csv</b> hoặc <b>.json</b> có đủ {n} cột đặc trưng CIC-IDS2017 (cột thừa như Label, Timestamp được bỏ qua; giá trị Infinity/NaN được quy về 0).', { n: net.features.length }))
        : rich(t('File <b>.csv</b> hoặc <b>.json</b> có đủ các cột đặc trưng CIC-IDS2017 (cột thừa như Label, Timestamp được bỏ qua; giá trị Infinity/NaN được quy về 0).'))}
      {net?.features && (
        <>
          {' '}<button onClick={() => setOpen(!open)} className="text-primary-600 hover:underline">{open ? t('Ẩn danh sách cột') : t('Xem danh sách cột')}</button>
          {open && <div className="mt-2 font-mono leading-5 max-h-40 overflow-auto">{net.features.map(f => f.trim()).join(' · ')}</div>}
        </>
      )}
      {!net && <div className="text-red-600 mt-1">{t('Chưa kết nối dịch vụ AI hoặc chưa có mô hình luồng mạng.')}</div>}
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
          <span className="w-24 text-right text-gray-600">{num(n)} ({((n / total) * 100).toFixed(1)}%)</span>
        </div>
      ))}
    </div>
  )
}

export default function UploadPanel({ incident, uploads, canUpload, onUploaded, onViewAlerts }) {
  const { t } = useI18n()
  const [dataType, setDataType] = useState('network')
  const [file, setFile] = useState(null)
  const [busy, setBusy] = useState(false)
  const [models, setModels] = useState([])
  const inputRef = useRef(null)

  useEffect(() => { getModels().then(r => setModels(r.data)).catch(() => {}) }, [])

  // Đổi nguồn thì bỏ file đang chọn, vì .eml và .zip chỉ hợp lệ với nguồn Email
  const changeDataType = (value) => {
    setDataType(value)
    setFile(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  const submit = async (e) => {
    e.preventDefault()
    if (!file) return
    setBusy(true)
    try {
      const res = await createUpload(incident.id, dataType, file)
      toast.success(t('Đã nhận file, đang xử lý'))
      ;(res.data.warnings || []).forEach(w => toast(t(w), { icon: '⚠️' }))
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
          <div className="font-medium text-gray-800">{t('Tải dữ liệu lên để phân loại')}</div>
          <div className="flex flex-wrap gap-3 items-center">
            <select className={ctl} value={dataType} onChange={e => changeDataType(e.target.value)}>
              {Object.entries(DATA_TYPES).map(([k, v]) => <option key={k} value={k}>{t(v)}</option>)}
            </select>
            <input ref={inputRef} type="file" accept={dataType === 'email' ? '.csv,.json,.eml,.zip' : '.csv,.json'}
              onChange={e => setFile(e.target.files[0] || null)} className="text-sm" />
            <button disabled={!file || busy} className="px-4 py-2 text-sm bg-primary-600 hover:bg-primary-700 text-white rounded-lg disabled:opacity-50">
              {busy ? t('Đang gửi...') : 'Upload'}
            </button>
          </div>
          <FormatHint dataType={dataType} models={models} />
        </form>
      ) : (
        <div className="text-sm text-gray-600 bg-yellow-50 border border-yellow-200 rounded-lg px-4 py-3">
          {t('Chỉ upload được khi sự cố ở trạng thái Mới hoặc Đang xử lý.')}
        </div>
      )}

      {uploads.length === 0 && <div className="text-sm text-gray-500 text-center py-6">{t('Chưa có file nào')}</div>}
      {uploads.map(u => {
        const active = u.status === 'pending' || u.status === 'processing'
        const progress = u.row_count ? Math.round((u.processed_rows / u.row_count) * 100) : 0
        return (
          <div key={u.id} className="bg-white border rounded-lg p-4 space-y-3">
            <div className="flex flex-wrap items-center gap-2 justify-between">
              <div>
                <span className="font-medium text-gray-900">{u.original_filename}</span>
                <span className="text-xs text-gray-500 ml-2">{t(DATA_TYPES[u.data_type])} · {formatBytes(u.file_size_bytes)} · {t('{n} dòng', { n: num(u.row_count ?? 0) })}</span>
              </div>
              <Badge info={UPLOAD_STATUS[u.status]} />
            </div>
            {active && (
              <div>
                <div className="h-2 bg-gray-100 rounded"><div className="h-2 bg-blue-500 rounded transition-all" style={{ width: `${progress}%` }} /></div>
                <div className="text-xs text-gray-500 mt-1">{t('Đã xử lý {a} / {b} dòng ({p}%)', { a: num(u.processed_rows), b: num(u.row_count ?? 0), p: progress })}</div>
              </div>
            )}
            {u.status === 'failed' && (
              <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                {t(u.error_message)}<div className="text-xs text-red-600 mt-1">{t('Không có cảnh báo nào được tạo từ file này.')}</div>
              </div>
            )}
            {u.status === 'completed' && (
              <>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                  <div><div className="text-xs text-gray-500">{t('Tổng số mẫu')}</div><b>{num(u.row_count)}</b></div>
                  <div><div className="text-xs text-gray-500">{t('Confidence trung bình')}</div><b>{pct(u.avg_confidence, 2)}</b></div>
                  <div><div className="text-xs text-gray-500">{t('Cảnh báo sinh ra')}</div><b>{num(u.alert_count)}</b></div>
                  <div><div className="text-xs text-gray-500">{t('Mô hình')}</div><b>{u.model_version}</b></div>
                </div>
                <div>
                  <div className="text-xs text-gray-500 mb-1">{t('Phân bố nhãn')}</div>
                  <LabelBars dist={u.label_distribution} />
                </div>
                <div className="text-xs text-gray-500">
                  {t('Ngưỡng đã áp dụng: {th} · Lớp nguy hiểm: {labels}', { th: pct(u.threshold_used, 0), labels: u.dangerous_labels_used.join(', ') || '—' })}
                </div>
                {u.alert_count > 0 && (
                  <button onClick={() => onViewAlerts(u.id)} className="text-sm text-primary-600 hover:underline">{t('Xem {n} cảnh báo của file này →', { n: u.alert_count })}</button>
                )}
              </>
            )}
            <div className="text-xs text-gray-400">
              {t('Upload bởi {name} lúc {time}', { name: u.uploaded_by_name, time: formatDateTime(u.uploaded_at) })}
              {u.processed_at && ` · ${t('xử lý xong {time}', { time: formatDateTime(u.processed_at) })}`}
            </div>
          </div>
        )
      })}
    </div>
  )
}
