import { useCallback, useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import toast from 'react-hot-toast'
import Badge from '../components/Badge'
import AlertsTable from '../components/AlertsTable'
import LabelBars from '../components/LabelBars'
import LoadingSpinner from '../components/LoadingSpinner'
import { useI18n, num } from '../i18n'
import { getUpload } from '../api'
import { DATA_TYPES, UPLOAD_STATUS, formatBytes, formatDateTime, pct, errMsg } from '../utils/format'

// Cảnh báo của một file đã upload: thống kê cả file ở trên, bảng cảnh báo (tìm kiếm, lọc, xác minh) ở dưới
export default function AlertFile() {
  const { t } = useI18n()
  const { uploadId } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const back = location.state?.from || '/alerts'
  const [up, setUp] = useState(null)

  const load = useCallback(async () => {
    try {
      const res = await getUpload(uploadId)
      setUp(res.data)
    } catch (err) {
      toast.error(errMsg(err))
      if (err.response?.status === 404) navigate('/alerts', { replace: true })
    }
  }, [uploadId, navigate])

  useEffect(() => { setUp(null); load() }, [load])

  // File đang xử lý thì tự làm mới đến khi xong
  const active = up && (up.status === 'pending' || up.status === 'processing')
  useEffect(() => {
    if (!active) return undefined
    const id = setInterval(load, 3000)
    return () => clearInterval(id)
  }, [active, load])

  if (!up) return <div className="p-6"><LoadingSpinner /></div>

  const done = up.status === 'completed'
  // Dòng không sinh cảnh báo: bình thường (BENIGN...) và dòng nguy hiểm nhưng dưới ngưỡng confidence
  const belowThreshold = Math.max((up.row_count ?? 0) - up.alert_count - up.benign_count, 0)
  const stat = (label, value) => (
    <div><div className="text-xs text-gray-500">{label}</div><b>{value}</b></div>
  )

  return (
    <div className="p-6 space-y-4">
      <div>
        <Link to={back} className="text-sm text-primary-600 hover:underline">{t('← Danh sách file')}</Link>
        <div className="flex flex-wrap items-center gap-2 mt-2">
          <h1 className="text-xl font-bold text-gray-900 break-all">{up.original_filename}</h1>
          <span className="font-mono text-sm text-gray-400">#{up.id}</span>
          {!done && <Badge info={UPLOAD_STATUS[up.status]} />}
        </div>
        <p className="text-sm text-gray-500 mt-1">
          {t(DATA_TYPES[up.data_type])} · {formatBytes(up.file_size_bytes)} · {t('Sự cố', { ctx: 'col' })}{' '}
          <Link className="text-primary-600" to={`/incidents/${up.incident_id}`}>{up.incident_code}</Link>
          {' · '}{t('Upload bởi {name} lúc {time}', { name: up.uploaded_by_name, time: formatDateTime(up.uploaded_at) })}
        </p>
      </div>

      {up.status === 'failed' && (
        <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
          {t(up.error_message)}<div className="text-xs text-red-600 mt-1">{t('Không có cảnh báo nào được tạo từ file này.')}</div>
        </div>
      )}

      {active && (
        <div className="text-sm text-gray-600 bg-blue-50 border border-blue-100 rounded-lg px-3 py-2">
          {t('Đã xử lý {a} / {b} dòng ({p}%)', { a: num(up.processed_rows), b: num(up.row_count ?? 0), p: up.row_count ? Math.round((up.processed_rows / up.row_count) * 100) : 0 })}
        </div>
      )}

      {done && (
        <div className="bg-white border rounded-lg p-4 space-y-3">
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3 text-sm">
            {stat(t('Tổng số mẫu'), num(up.row_count))}
            {stat(t('Cảnh báo sinh ra'), num(up.alert_count))}
            {stat(t('Bình thường'), num(up.benign_count))}
            {stat(t('Dưới ngưỡng'), num(belowThreshold))}
            {stat(t('Confidence trung bình'), pct(up.avg_confidence, 2))}
            {stat(t('Mô hình'), up.model_version || '—')}
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">{t('Phân bố nhãn')}</div>
            <LabelBars dist={up.label_distribution} />
          </div>
          <div className="text-xs text-gray-500 space-y-1">
            <div>{t('Ngưỡng đã áp dụng: {th} · Lớp nguy hiểm: {labels}', { th: pct(up.threshold_used, 0), labels: up.dangerous_labels_used.join(', ') || '—' })}</div>
            <div>{t('Dòng bình thường và dòng dưới ngưỡng không được lưu thành cảnh báo; chỉ có số lượng của chúng ở trên.')}</div>
          </div>
        </div>
      )}

      {done && up.alert_count === 0 ? (
        <div className="text-sm text-gray-600 bg-yellow-50 border border-yellow-200 rounded-lg px-4 py-3">
          {t('File này không sinh cảnh báo nào.')}
        </div>
      ) : done && (
        <AlertsTable filterUploadId={up.id} hideFile onChanged={load} />
      )}
    </div>
  )
}