import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import toast from 'react-hot-toast'
import Badge from './Badge'
import Pagination from './Pagination'
import LoadingSpinner from './LoadingSpinner'
import MoveAlertsModal from './MoveAlertsModal'
import AlertDetailModal from './AlertDetailModal'
import { listAlerts, listIncidentAlerts, bulkVerify, getLabels } from '../api'
import { VERIFICATION, DATA_TYPES, pct, errMsg } from '../utils/format'

const ctl = 'border rounded-lg px-2 py-1.5 text-sm bg-white focus:outline-none focus:border-primary-500'
const PAGE_SIZE = 50
const MAX_BULK = 10000 // API chỉ nhận tối đa 10.000 id mỗi lần

// Dùng cho trang chi tiết sự cố (có incidentId) và trang danh sách cảnh báo chung (không có)
export default function AlertsTable({ incidentId, locked, uploads = [], filterUploadId, onFilterUploadChange, refreshKey, onChanged }) {
  const global = !incidentId
  const [data, setData] = useState(null)
  const [labels, setLabels] = useState([])
  const [page, setPage] = useState(1)
  const [sort, setSort] = useState(global ? { sort_by: 'created_at', order: 'desc' } : { sort_by: 'row_index', order: 'asc' })
  const [filters, setFilters] = useState({ label: '', verification_status: '', source_type: '', scope: '' })
  const [selected, setSelected] = useState(new Set())
  const [showMove, setShowMove] = useState(false)
  const [detailId, setDetailId] = useState(null)
  const [busy, setBusy] = useState(false)

  const params = useCallback(() => ({
    label: filters.label,
    verification_status: filters.verification_status,
    source_type: filters.source_type,
    upload_id: filterUploadId || undefined,
    unassigned: global && filters.scope === 'unassigned' ? 'true' : undefined,
    ...sort,
  }), [filters, sort, filterUploadId, global])

  const fetchPage = useCallback((p, size) => {
    const q = { ...params(), page: p, page_size: size }
    return global ? listAlerts(q) : listIncidentAlerts(incidentId, q)
  }, [params, global, incidentId])

  const load = useCallback(async () => {
    try {
      const res = await fetchPage(page, PAGE_SIZE)
      setData(res.data)
    } catch (err) {
      toast.error(errMsg(err))
    }
  }, [fetchPage, page])

  useEffect(() => { load() }, [load, refreshKey])
  useEffect(() => { getLabels().then(r => setLabels([...new Set(r.data.map(l => l.code))])).catch(() => {}) }, [])

  const changeFilter = (k) => (e) => { setPage(1); setSelected(new Set()); setFilters({ ...filters, [k]: e.target.value }) }

  const toggle = (id) => {
    const next = new Set(selected)
    next.has(id) ? next.delete(id) : next.add(id)
    setSelected(next)
  }

  const pageIds = data?.items.map(a => a.id) || []
  const allOnPage = pageIds.length > 0 && pageIds.every(id => selected.has(id))
  const togglePage = () => {
    const next = new Set(selected)
    pageIds.forEach(id => (allOnPage ? next.delete(id) : next.add(id)))
    setSelected(next)
  }

  // Chọn mọi cảnh báo khớp bộ lọc hiện tại (qua nhiều trang)
  const selectAllMatching = async () => {
    if (data && data.total > MAX_BULK) {
      toast.error(`Có ${data.total.toLocaleString('vi-VN')} cảnh báo khớp, vượt giới hạn ${MAX_BULK.toLocaleString('vi-VN')} mỗi lần. Hãy lọc thêm (nhãn, file, trạng thái) rồi chọn lại.`)
      return
    }
    setBusy(true)
    try {
      const ids = new Set()
      for (let p = 1; ; p++) {
        const res = await fetchPage(p, 500)
        res.data.items.forEach(a => ids.add(a.id))
        if (p >= res.data.pages) break
      }
      setSelected(ids)
    } catch (err) {
      toast.error(errMsg(err))
    } finally {
      setBusy(false)
    }
  }

  const afterChange = () => { setSelected(new Set()); load(); onChanged && onChanged() }

  const doVerify = async (status) => {
    setBusy(true)
    try {
      const res = await bulkVerify({ alert_ids: [...selected], status })
      toast.success(`Đã cập nhật ${res.data.updated} cảnh báo`)
      afterChange()
    } catch (err) {
      toast.error(errMsg(err))
    } finally {
      setBusy(false)
    }
  }

  const colSpan = global ? 9 : 8
  return (
    <div>
      <div className="flex flex-wrap gap-2 items-center mb-3">
        {global && (
          <select className={ctl} value={filters.scope} onChange={changeFilter('scope')}>
            <option value="">Mọi cảnh báo</option>
            <option value="unassigned">Chưa gắn sự cố</option>
          </select>
        )}
        <select className={ctl} value={filters.label} onChange={changeFilter('label')}>
          <option value="">Mọi nhãn</option>
          {labels.map(l => <option key={l} value={l}>{l}</option>)}
        </select>
        <select className={ctl} value={filters.verification_status} onChange={changeFilter('verification_status')}>
          <option value="">Mọi trạng thái xác minh</option>
          {Object.entries(VERIFICATION).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </select>
        <select className={ctl} value={filters.source_type} onChange={changeFilter('source_type')}>
          <option value="">Mọi nguồn</option>
          {Object.entries(DATA_TYPES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        {!global && uploads.length > 0 && (
          <select className={ctl} value={filterUploadId || ''} onChange={e => { setPage(1); setSelected(new Set()); onFilterUploadChange(e.target.value ? Number(e.target.value) : null) }}>
            <option value="">Mọi file</option>
            {uploads.filter(u => u.status === 'completed').map(u => <option key={u.id} value={u.id}>{u.original_filename}</option>)}
          </select>
        )}
        <select className={ctl} value={`${sort.sort_by}:${sort.order}`} onChange={e => { const [s, o] = e.target.value.split(':'); setSort({ sort_by: s, order: o }) }}>
          <option value="row_index:asc">Theo dòng trong file</option>
          <option value="confidence:desc">Confidence giảm dần</option>
          <option value="confidence:asc">Confidence tăng dần</option>
          <option value="created_at:desc">Mới nhất</option>
          <option value="predicted_label:asc">Theo nhãn</option>
        </select>
      </div>

      {selected.size > 0 && (
        <div className="flex flex-wrap items-center gap-2 bg-primary-50 border border-primary-100 rounded-lg px-3 py-2 mb-3 text-sm">
          <b>Đã chọn {selected.size}</b>
          {data && selected.size < data.total && (data.total > MAX_BULK ? (
            <span className="text-gray-500">
              {data.total.toLocaleString('vi-VN')} cảnh báo khớp bộ lọc, vượt giới hạn {MAX_BULK.toLocaleString('vi-VN')} mỗi lần: hãy lọc thêm
            </span>
          ) : (
            <button disabled={busy} onClick={selectAllMatching} className="text-primary-600 hover:underline">
              Chọn tất cả {data.total} cảnh báo khớp bộ lọc
            </button>
          ))}
          {selected.size > MAX_BULK && (
            <span className="text-red-600">Đã chọn quá {MAX_BULK.toLocaleString('vi-VN')}: bỏ bớt trước khi thao tác</span>
          )}
          <span className="flex-1" />
          <button disabled={busy || locked || selected.size > MAX_BULK} onClick={() => doVerify('verified')} className="px-3 py-1 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50">Xác minh</button>
          <button disabled={busy || locked || selected.size > MAX_BULK} onClick={() => doVerify('dismissed')} className="px-3 py-1 bg-yellow-500 text-white rounded-lg hover:bg-yellow-600 disabled:opacity-50">Bỏ qua</button>
          <button disabled={busy || locked || selected.size > MAX_BULK} onClick={() => doVerify('unverified')} className="px-3 py-1 border bg-white rounded-lg hover:bg-gray-50 disabled:opacity-50">Đặt lại</button>
          <button disabled={busy || locked || selected.size > MAX_BULK} onClick={() => setShowMove(true)} className="px-3 py-1 border bg-white rounded-lg hover:bg-gray-50 disabled:opacity-50">Chuyển / Gỡ</button>
          <button onClick={() => setSelected(new Set())} className="px-2 py-1 text-gray-500 hover:text-gray-800">Bỏ chọn</button>
        </div>
      )}

      {!data ? <LoadingSpinner /> : (
        <div className="bg-white border rounded-lg overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-600 text-left">
              <tr>
                <th className="px-3 py-2 w-8"><input type="checkbox" checked={allOnPage} onChange={togglePage} /></th>
                <th className="px-3 py-2">ID</th>
                <th className="px-3 py-2">Nhãn</th>
                <th className="px-3 py-2">Confidence</th>
                <th className="px-3 py-2">Nguồn</th>
                <th className="px-3 py-2">File · dòng</th>
                {global && <th className="px-3 py-2">Sự cố</th>}
                <th className="px-3 py-2">Xác minh</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {data.items.length === 0 && (
                <tr><td colSpan={colSpan} className="px-4 py-8 text-center text-gray-500">Không có cảnh báo nào</td></tr>
              )}
              {data.items.map(a => (
                <tr key={a.id} className={`border-t hover:bg-gray-50 ${selected.has(a.id) ? 'bg-primary-50' : ''}`}>
                  <td className="px-3 py-2"><input type="checkbox" checked={selected.has(a.id)} onChange={() => toggle(a.id)} /></td>
                  <td className="px-3 py-2 text-gray-500">#{a.id}</td>
                  <td className="px-3 py-2 font-medium">{a.predicted_label}</td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-1.5 bg-gray-200 rounded"><div className="h-1.5 bg-primary-500 rounded" style={{ width: `${Math.round(a.confidence * 100)}%` }} /></div>
                      <span className="text-xs text-gray-600">{pct(a.confidence)}</span>
                    </div>
                  </td>
                  <td className="px-3 py-2">{DATA_TYPES[a.source_type]}</td>
                  <td className="px-3 py-2 text-gray-600" title={`Dòng dữ liệu thứ ${a.row_index} trong file gốc`}>
                    {a.upload_filename} · <span className="font-mono">#{a.row_index}</span>
                  </td>
                  {global && (
                    <td className="px-3 py-2">
                      {a.incident_id ? <Link className="text-primary-600" to={`/incidents/${a.incident_id}`}>{a.incident_code}</Link> : <i className="text-gray-400">chưa gắn</i>}
                    </td>
                  )}
                  <td className="px-3 py-2"><Badge info={VERIFICATION[a.verification_status]} /></td>
                  <td className="px-3 py-2 text-right"><button onClick={() => setDetailId(a.id)} className="text-primary-600 hover:underline">Chi tiết</button></td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="px-4 border-t">
            <Pagination page={data.page} pages={data.pages} total={data.total} onChange={setPage} />
          </div>
        </div>
      )}

      <MoveAlertsModal
        open={showMove}
        alertIds={[...selected]}
        currentIncidentId={incidentId}
        onClose={() => setShowMove(false)}
        onDone={() => { setShowMove(false); afterChange() }}
      />
      {detailId && <AlertDetailModal alertId={detailId} onClose={() => setDetailId(null)} onChanged={() => { load(); onChanged && onChanged() }} />}
    </div>
  )
}