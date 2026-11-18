import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { listIncidents, getAttackTypes } from '../api'
import Badge from '../components/Badge'
import Pagination from '../components/Pagination'
import LoadingSpinner from '../components/LoadingSpinner'
import IncidentFormModal from '../components/IncidentFormModal'
import { useI18n } from '../i18n'
import { STATUS, SEVERITY, formatDate, errMsg } from '../utils/format'

const SORTS = [
  { value: 'created_at', label: 'Ngày tạo' },
  { value: 'occurred_at', label: 'Thời gian xảy ra' },
  { value: 'severity', label: 'Mức độ' },
  { value: 'status', label: 'Trạng thái' },
  { value: 'code', label: 'Mã' },
]

const ctl = 'border rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:border-primary-500'

export default function IncidentList() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [types, setTypes] = useState([])
  const [q, setQ] = useState('')
  const [filters, setFilters] = useState({ status: '', attack_type: '', date_from: '', date_to: '' })
  const [sort, setSort] = useState({ sort_by: 'created_at', order: 'desc' })
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [showForm, setShowForm] = useState(false)

  const load = useCallback(async () => {
    try {
      const range = {
        date_from: filters.date_from ? new Date(`${filters.date_from}T00:00:00`).toISOString() : '',
        date_to: filters.date_to ? new Date(`${filters.date_to}T23:59:59.999`).toISOString() : '',
      }
      const res = await listIncidents({ page, page_size: 15, q: search, ...filters, ...range, ...sort })
      setData(res.data)
    } catch (err) {
      toast.error(errMsg(err))
    }
  }, [page, search, filters, sort])

  useEffect(() => { load() }, [load])

  // Tìm khi gõ: đợi 300ms sau lần gõ cuối rồi mới gọi API
  useEffect(() => {
    const timer = setTimeout(() => { setPage(1); setSearch(q.trim()) }, 300)
    return () => clearTimeout(timer)
  }, [q])
  useEffect(() => { getAttackTypes().then(r => setTypes(r.data)).catch(() => {}) }, [])

  const setFilter = (k) => (e) => { setPage(1); setFilters({ ...filters, [k]: e.target.value }) }
  const typeName = (code) => t(types.find(a => a.code === code)?.name_vi || code)

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-bold text-gray-900">{t('Sự cố')}</h1>
        <button onClick={() => setShowForm(true)} className="px-4 py-2 text-sm bg-primary-600 hover:bg-primary-700 text-white rounded-lg">
          {t('+ Tạo sự cố')}
        </button>
      </div>

      <div className="bg-white border rounded-lg p-4 mb-4 flex flex-wrap gap-3 items-end">
        <input className={`${ctl} w-64`} placeholder={t('Tìm theo mã hoặc tiêu đề')} value={q} onChange={e => setQ(e.target.value)} />
        <select className={ctl} value={filters.status} onChange={setFilter('status')}>
          <option value="">{t('Mọi trạng thái')}</option>
          {Object.entries(STATUS).map(([k, v]) => <option key={k} value={k}>{t(v.label)}</option>)}
        </select>
        <select className={ctl} value={filters.attack_type} onChange={setFilter('attack_type')}>
          <option value="">{t('Mọi loại tấn công')}</option>
          {types.map(a => <option key={a.code} value={a.code}>{t(a.name_vi)}</option>)}
        </select>
        <label className="text-xs text-gray-500">{t('Từ ngày')}
          <input type="date" className={`${ctl} block`} value={filters.date_from} onChange={setFilter('date_from')} />
        </label>
        <label className="text-xs text-gray-500">{t('Đến ngày')}
          <input type="date" className={`${ctl} block`} value={filters.date_to} onChange={setFilter('date_to')} />
        </label>
        <label className="text-xs text-gray-500">{t('Sắp xếp')}
          <div className="flex gap-1">
            <select className={ctl} value={sort.sort_by} onChange={e => setSort({ ...sort, sort_by: e.target.value })}>
              {SORTS.map(s => <option key={s.value} value={s.value}>{t(s.label)}</option>)}
            </select>
            <button
              className="px-3 border rounded-lg bg-white hover:bg-gray-50 text-sm"
              title={sort.order === 'asc' ? t('Tăng dần') : t('Giảm dần')}
              onClick={() => setSort({ ...sort, order: sort.order === 'asc' ? 'desc' : 'asc' })}
            >
              {sort.order === 'asc' ? '↑' : '↓'}
            </button>
          </div>
        </label>
      </div>

      {!data ? <LoadingSpinner /> : (
        <div className="bg-white border rounded-lg overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-600 text-left">
              <tr>
                <th className="px-4 py-2">{t('Mã')}</th>
                <th className="px-4 py-2">{t('Tiêu đề')}</th>
                <th className="px-4 py-2">{t('Loại tấn công')}</th>
                <th className="px-4 py-2">{t('Mức độ')}</th>
                <th className="px-4 py-2">{t('Trạng thái')}</th>
                <th className="px-4 py-2 text-right">{t('Cảnh báo')}</th>
                <th className="px-4 py-2">{t('Xảy ra lúc')}</th>
                <th className="px-4 py-2">{t('Tạo lúc')}</th>
              </tr>
            </thead>
            <tbody>
              {data.items.length === 0 && (
                <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-500">{t('Không có sự cố nào')}</td></tr>
              )}
              {data.items.map(i => (
                <tr key={i.id} className="border-t hover:bg-gray-50 cursor-pointer" onClick={() => navigate(`/incidents/${i.id}`)}>
                  <td className="px-4 py-2 font-mono text-xs"><Link className="text-primary-600" to={`/incidents/${i.id}`} onClick={e => e.stopPropagation()}>{i.code}</Link></td>
                  <td className="px-4 py-2 font-medium text-gray-900">{i.title}</td>
                  <td className="px-4 py-2">{typeName(i.attack_type)}</td>
                  <td className="px-4 py-2"><Badge info={SEVERITY[i.severity]} /></td>
                  <td className="px-4 py-2"><Badge info={STATUS[i.status]} /></td>
                  <td className="px-4 py-2 text-right">{i.alert_count}</td>
                  <td className="px-4 py-2 text-gray-600">{formatDate(i.occurred_at)}</td>
                  <td className="px-4 py-2 text-gray-600">{formatDate(i.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="px-4 border-t">
            <Pagination page={data.page} pages={data.pages} total={data.total} onChange={setPage} />
          </div>
        </div>
      )}

      <IncidentFormModal
        open={showForm}
        onClose={() => setShowForm(false)}
        onSaved={(inc) => { setShowForm(false); navigate(`/incidents/${inc.id}`) }}
      />
    </div>
  )
}