import { useCallback, useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import toast from 'react-hot-toast'
import Badge from '../components/Badge'
import Pagination from '../components/Pagination'
import LoadingSpinner from '../components/LoadingSpinner'
import { useI18n, num } from '../i18n'
import { listAllUploads } from '../api'
import { DATA_TYPES, UPLOAD_STATUS, formatBytes, formatDateTime, errMsg } from '../utils/format'

const ctl = 'border rounded-lg px-2 py-1.5 text-sm bg-white focus:outline-none focus:border-primary-500'
const PAGE_SIZE = 20

// Trang Cảnh báo: danh sách file đã upload (kể cả file chỉ có dòng bình thường, không sinh cảnh báo nào).
// Chọn một file để xem, lọc và xác minh cảnh báo của file đó.
export default function AlertList() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const location = useLocation()
  const [sp, setSp] = useSearchParams()
  const q = sp.get('q') || ''
  const dataType = sp.get('type') || ''
  const sort = sp.get('sort') || 'newest'
  const page = Number(sp.get('page')) || 1
  const [text, setText] = useState(q)
  const [data, setData] = useState(null)
  const [tick, setTick] = useState(0)

  // Bộ lọc nằm trên URL để quay lại từ trang chi tiết file vẫn giữ nguyên tìm kiếm và trang
  const update = useCallback((patch) => {
    const next = new URLSearchParams(sp)
    Object.entries({ page: '', ...patch }).forEach(([k, v]) => (v ? next.set(k, v) : next.delete(k)))
    setSp(next, { replace: true })
  }, [sp, setSp])

  useEffect(() => {
    if (text.trim() === q) return undefined
    const id = setTimeout(() => update({ q: text.trim() }), 300)
    return () => clearTimeout(id)
  }, [text, q, update])

  useEffect(() => {
    let alive = true
    listAllUploads({ q, data_type: dataType, sort, page, page_size: PAGE_SIZE })
      .then(res => { if (alive) setData(res.data) })
      .catch(err => { if (alive) toast.error(errMsg(err)) })
    return () => { alive = false }
  }, [q, dataType, sort, page, tick])

  // File đang xử lý thì tự làm mới để thấy kết quả
  const processing = data?.items.some(u => u.status === 'pending' || u.status === 'processing')
  useEffect(() => {
    if (!processing) return undefined
    const id = setInterval(() => setTick(n => n + 1), 3000)
    return () => clearInterval(id)
  }, [processing])

  const filtered = !!(q || dataType)
  const open = (u) => navigate(`/alerts/files/${u.id}`, { state: { from: `${location.pathname}${location.search}` } })

  return (
    <div className="p-6">
      <h1 className="text-xl font-bold text-gray-900 mb-1">{t('Cảnh báo')}</h1>
      <p className="text-sm text-gray-500 mb-4">
        {t('Chọn một file đã upload để xem cảnh báo sinh ra từ file đó.')}
      </p>

      <div className="flex flex-wrap gap-2 items-center mb-3">
        <input
          value={text}
          onChange={e => setText(e.target.value)}
          placeholder={t('Tìm theo tên file, mã #, mã sự cố…')}
          className={`${ctl} w-64`}
        />
        <select className={ctl} value={dataType} onChange={e => update({ type: e.target.value })}>
          <option value="">{t('Mọi nguồn')}</option>
          {Object.entries(DATA_TYPES).map(([k, v]) => <option key={k} value={k}>{t(v)}</option>)}
        </select>
        <select className={ctl} value={sort} onChange={e => update({ sort: e.target.value === 'newest' ? '' : e.target.value })}>
          <option value="newest">{t('Mới nhất')}</option>
          <option value="oldest">{t('Cũ nhất')}</option>
          <option value="name">{t('Tên file A → Z')}</option>
          <option value="alerts">{t('Nhiều cảnh báo nhất')}</option>
        </select>
        {filtered && (
          <button onClick={() => { setText(''); setSp({}, { replace: true }) }} className="text-sm text-gray-500 hover:text-gray-800">
            {t('Xóa bộ lọc')}
          </button>
        )}
      </div>

      {!data ? <LoadingSpinner /> : (
        <div className="bg-white border rounded-lg overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-600 text-left">
              <tr>
                <th className="px-3 py-2">{t('File')}</th>
                <th className="px-3 py-2">{t('Sự cố', { ctx: 'col' })}</th>
                <th className="px-3 py-2">{t('Nguồn')}</th>
                <th className="px-3 py-2 text-right">{t('Số dòng')}</th>
                <th className="px-3 py-2">{t('Cảnh báo')}</th>
                <th className="px-3 py-2 text-right">{t('Bình thường')}</th>
                <th className="px-3 py-2">{t('Upload')}</th>
              </tr>
            </thead>
            <tbody>
              {data.items.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-gray-500">
                    {filtered ? t('Không có file nào khớp bộ lọc') : t('Chưa có file nào được upload')}
                  </td>
                </tr>
              )}
              {data.items.map(u => (
                <tr key={u.id} className="border-t hover:bg-gray-50 cursor-pointer" onClick={() => open(u)}>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium text-gray-900 break-all">{u.original_filename}</span>
                      <span className="font-mono text-xs text-gray-400">#{u.id}</span>
                      {u.status !== 'completed' && <Badge info={UPLOAD_STATUS[u.status]} />}
                      {u.name_count > 1 && (
                        <span
                          className="text-[11px] px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-200"
                          title={t('Có {n} file cùng tên này; phân biệt bằng mã #, sự cố và thời gian upload', { n: u.name_count })}
                        >
                          {t('Trùng tên ×{n}', { n: u.name_count })}
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-gray-500">{formatBytes(u.file_size_bytes)}</div>
                  </td>
                  <td className="px-3 py-2" onClick={e => e.stopPropagation()}>
                    <Link className="text-primary-600" to={`/incidents/${u.incident_id}`}>{u.incident_code}</Link>
                  </td>
                  <td className="px-3 py-2">{t(DATA_TYPES[u.data_type])}</td>
                  <td className="px-3 py-2 text-right">{u.row_count == null ? '—' : num(u.row_count)}</td>
                  <td className="px-3 py-2">
                    <div className="font-medium">{num(u.alert_count)}</div>
                    {u.alert_count > 0 && (
                      <div className="text-xs text-gray-500">
                        {[
                          u.unverified_count > 0 && t('{n} chưa xác minh', { n: num(u.unverified_count) }),
                          u.verified_count > 0 && t('{n} đã xác minh', { n: num(u.verified_count) }),
                          u.dismissed_count > 0 && t('{n} bỏ qua', { n: num(u.dismissed_count) }),
                        ].filter(Boolean).join(' · ')}
                      </div>
                    )}
                  </td>
                  <td className="px-3 py-2 text-right">{u.status === 'completed' ? num(u.benign_count) : '—'}</td>
                  <td className="px-3 py-2 text-xs text-gray-500">
                    <div>{u.uploaded_by_name}</div>
                    <div>{formatDateTime(u.uploaded_at)}</div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="px-4 border-t">
            <Pagination page={data.page} pages={data.pages} total={data.total} onChange={p => update({ page: p > 1 ? String(p) : '' })} />
          </div>
        </div>
      )}
    </div>
  )
}