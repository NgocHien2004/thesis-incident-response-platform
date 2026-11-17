export const STATUS = {
  new:         { label: 'Mới',        cls: 'bg-gray-100 text-gray-700' },
  in_progress: { label: 'Đang xử lý', cls: 'bg-blue-100 text-blue-700' },
  resolved:    { label: 'Đã xử lý',   cls: 'bg-teal-100 text-teal-700' },
  closed:      { label: 'Đã đóng',    cls: 'bg-green-100 text-green-700' },
  cancelled:   { label: 'Đã hủy',     cls: 'bg-gray-200 text-gray-500 line-through' },
}

export const SEVERITY = {
  low:      { label: 'Thấp',       cls: 'bg-blue-100 text-blue-700 border border-blue-200' },
  medium:   { label: 'Trung bình', cls: 'bg-yellow-100 text-yellow-700 border border-yellow-200' },
  high:     { label: 'Cao',        cls: 'bg-orange-100 text-orange-700 border border-orange-200' },
  critical: { label: 'Nghiêm trọng', cls: 'bg-red-100 text-red-700 border border-red-200' },
}

export const VERIFICATION = {
  unverified: { label: 'Chưa xác minh', cls: 'bg-gray-100 text-gray-600' },
  verified:   { label: 'Đã xác minh',   cls: 'bg-green-100 text-green-700' },
  dismissed:  { label: 'Bỏ qua',        cls: 'bg-yellow-100 text-yellow-700' },
}

export const UPLOAD_STATUS = {
  pending:    { label: 'Chờ xử lý',  cls: 'bg-gray-100 text-gray-600' },
  processing: { label: 'Đang xử lý', cls: 'bg-blue-100 text-blue-700' },
  completed:  { label: 'Hoàn tất',   cls: 'bg-green-100 text-green-700' },
  failed:     { label: 'Lỗi',        cls: 'bg-red-100 text-red-700' },
}

export const DATA_TYPES = { network: 'Luồng mạng', email: 'Email' }

export const SOURCES = {
  ids_ips:  'IDS/IPS',
  email:    'Email báo cáo',
  endpoint: 'Endpoint',
  manual:   'Báo cáo thủ công',
  other:    'Khác',
}

export const TRANSITION_LABEL = {
  in_progress: { new: 'Bắt đầu xử lý', resolved: 'Mở lại xử lý' },
  resolved:    { in_progress: 'Đánh dấu đã xử lý' },
  closed:      { resolved: 'Đóng sự cố' },
  cancelled:   { any: 'Hủy sự cố' },
}

export function transitionLabel(from, to) {
  const t = TRANSITION_LABEL[to] || {}
  return t[from] || t.any || to
}

export const needsReason = (from, to) =>
  to === 'cancelled' || (from === 'resolved' && to === 'in_progress')

export const isTerminal = (status) => status === 'closed' || status === 'cancelled'
export const canUpload = (status) => status === 'new' || status === 'in_progress'

export function formatDateTime(v) {
  if (!v) return '—'
  const d = new Date(v)
  return isNaN(d) ? '—' : d.toLocaleString('vi-VN')
}

// Chuyển ISO sang giá trị cho <input type="datetime-local"> theo giờ máy
export function toLocalInput(v) {
  const d = v ? new Date(v) : new Date()
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export const fromLocalInput = (s) => new Date(s).toISOString()

export function formatBytes(n) {
  if (n == null) return '—'
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

export const pct = (x, digits = 1) => (x == null ? '—' : `${(x * 100).toFixed(digits)}%`)

// Rút gọn thông báo lỗi của backend (chuỗi, danh sách lỗi của FastAPI, hoặc {message, items})
export function errMsg(err, fallback = 'Có lỗi xảy ra') {
  const d = err?.response?.data?.detail
  if (!err?.response) return 'Không kết nối được máy chủ'
  if (typeof d === 'string') return d
  if (Array.isArray(d)) return d.map(x => x.msg).join('; ')
  if (d && d.message) {
    const first = (d.items || []).slice(0, 3).map(i => `#${i.id}: ${i.reason}`).join('; ')
    return first ? `${d.message}. ${first}` : d.message
  }
  return fallback
}