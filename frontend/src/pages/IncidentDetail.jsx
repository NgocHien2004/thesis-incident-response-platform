import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import toast from 'react-hot-toast'
import Badge from '../components/Badge'
import LoadingSpinner from '../components/LoadingSpinner'
import ConfirmModal from '../components/ConfirmModal'
import IncidentFormModal from '../components/IncidentFormModal'
import AlertsTable from '../components/AlertsTable'
import UploadPanel from '../components/UploadPanel'
import { useI18n } from '../i18n'
import { getIncident, listUploads, getHistory, changeStatus, deleteIncident } from '../api'
import {
  STATUS, SEVERITY, SOURCES, formatDateTime, errMsg, transitionLabel, needsReason, isTerminal, canUpload,
} from '../utils/format'

function Stat({ label, value, cls = '' }) {
  const { t } = useI18n()
  return (
    <div className="bg-white border rounded-lg px-4 py-3">
      <div className="text-xs text-gray-500">{t(label)}</div>
      <div className={`text-2xl font-bold ${cls}`}>{value}</div>
    </div>
  )
}

export default function IncidentDetail() {
  const { t } = useI18n()
  const { id } = useParams()
  const navigate = useNavigate()
  const [inc, setInc] = useState(null)
  const [uploads, setUploads] = useState([])
  const [history, setHistory] = useState([])
  const [tab, setTab] = useState('alerts')
  const [refreshKey, setRefreshKey] = useState(0)
  const [filterUpload, setFilterUpload] = useState(null)
  const [showEdit, setShowEdit] = useState(false)
  const [transition, setTransition] = useState(null)
  const [showDelete, setShowDelete] = useState(false)
  const prevStatus = useRef({})

  const loadIncident = useCallback(async () => {
    try {
      const res = await getIncident(id)
      setInc(res.data)
    } catch (err) {
      toast.error(errMsg(err, 'Không tải được sự cố'))
      if (err.response?.status === 404) navigate('/incidents')
    }
  }, [id, navigate])

  const loadHistory = useCallback(() => {
    getHistory(id).then(r => setHistory(r.data)).catch(() => {})
  }, [id])

  const refreshUploads = useCallback(async () => {
    try {
      const res = await listUploads(id)
      let finished = false
      res.data.forEach(u => {
        const prev = prevStatus.current[u.id]
        if (prev && prev !== u.status) {
          if (u.status === 'completed') { toast.success(t('{name}: hoàn tất, sinh {n} cảnh báo', { name: u.original_filename, n: u.alert_count })); finished = true }
          if (u.status === 'failed') { toast.error(t('{name}: lỗi. {msg}', { name: u.original_filename, msg: t(u.error_message) }), { duration: 8000 }); finished = true }
        }
        prevStatus.current[u.id] = u.status
      })
      setUploads(res.data)
      if (finished) { loadIncident(); setRefreshKey(k => k + 1) }
    } catch { /* bỏ qua lỗi mạng tạm thời khi thăm dò */ }
  }, [id, loadIncident, t])

  useEffect(() => {
    prevStatus.current = {}
    loadIncident(); refreshUploads(); loadHistory()
  }, [id]) // eslint-disable-line react-hooks/exhaustive-deps

  const hasActive = uploads.some(u => u.status === 'pending' || u.status === 'processing')
  useEffect(() => {
    if (!hasActive) return
    const timer = setInterval(refreshUploads, 1500)
    return () => clearInterval(timer)
  }, [hasActive, refreshUploads])

  if (!inc) return <LoadingSpinner />

  const terminal = isTerminal(inc.status)
  const typeLabel = t(inc.attack_type_name || inc.attack_type)

  const doTransition = async (reason) => {
    try {
      await changeStatus(inc.id, { new_status: transition, note: reason || null })
      toast.success(t('Đã chuyển sang “{status}”', { status: t(STATUS[transition].label) }))
      setTransition(null)
      await loadIncident(); loadHistory()
    } catch (err) {
      toast.error(errMsg(err))
      setTransition(null)
    }
  }

  const doDelete = async () => {
    try {
      await deleteIncident(inc.id)
      toast.success(t('Đã xóa sự cố'))
      navigate('/incidents')
    } catch (err) {
      toast.error(errMsg(err))
      setShowDelete(false)
    }
  }

  const tabs = [
    { key: 'alerts', label: t('Cảnh báo ({n})', { n: inc.alert_count }) },
    { key: 'uploads', label: t('Dữ liệu tải lên ({n})', { n: inc.upload_count }) },
    { key: 'history', label: t('Lịch sử trạng thái') },
  ]

  return (
    <div className="p-6 space-y-5">
      <div>
        <Link to="/incidents" className="text-sm text-gray-500 hover:text-gray-800">{t('← Danh sách sự cố')}</Link>
        <div className="flex flex-wrap items-start justify-between gap-3 mt-2">
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm text-gray-500">{inc.code}</span>
              <Badge info={STATUS[inc.status]} />
              <Badge info={SEVERITY[inc.severity]} />
            </div>
            <h1 className="text-xl font-bold text-gray-900 mt-1">{inc.title}</h1>
          </div>
          <div className="flex flex-wrap gap-2">
            {inc.allowed_transitions.map(to => (
              <button key={to} onClick={() => setTransition(to)}
                className={`px-3 py-2 text-sm rounded-lg ${to === 'cancelled' ? 'border border-red-300 text-red-700 hover:bg-red-50' : 'bg-primary-600 hover:bg-primary-700 text-white'}`}>
                {t(transitionLabel(inc.status, to))}
              </button>
            ))}
            {!terminal && <button onClick={() => setShowEdit(true)} className="px-3 py-2 text-sm border rounded-lg hover:bg-gray-50">{t('Sửa')}</button>}
            {inc.can_delete && <button onClick={() => setShowDelete(true)} className="px-3 py-2 text-sm border border-red-300 text-red-700 rounded-lg hover:bg-red-50">{t('Xóa')}</button>}
          </div>
        </div>
      </div>

      {inc.processing_uploads > 0 && (
        <div className="text-sm bg-blue-50 border border-blue-200 text-blue-800 rounded-lg px-4 py-2">
          {t('Đang xử lý {n} file. Chưa thể chuyển sang Đã xử lý, Đã đóng hoặc Hủy cho đến khi xong.', { n: inc.processing_uploads })}
        </div>
      )}

      <div className="bg-white border rounded-lg p-4 grid grid-cols-2 md:grid-cols-4 gap-x-6 gap-y-3 text-sm">
        <div><div className="text-xs text-gray-500">{t('Loại tấn công')}</div>{typeLabel}</div>
        <div><div className="text-xs text-gray-500">{t('Nguồn')}</div>{t(SOURCES[inc.source] || inc.source)}</div>
        <div><div className="text-xs text-gray-500">{t('Xảy ra lúc')}</div>{formatDateTime(inc.occurred_at)}</div>
        <div><div className="text-xs text-gray-500">{t('Người tạo')}</div>{inc.created_by_name}</div>
        <div><div className="text-xs text-gray-500">{t('Tạo lúc')}</div>{formatDateTime(inc.created_at)}</div>
        <div><div className="text-xs text-gray-500">{t('Đã xử lý lúc')}</div>{formatDateTime(inc.resolved_at)}</div>
        <div><div className="text-xs text-gray-500">{t('Đóng lúc')}</div>{formatDateTime(inc.closed_at)}</div>
        <div className="col-span-2 md:col-span-4"><div className="text-xs text-gray-500">{t('Mô tả')}</div><div className="whitespace-pre-wrap">{inc.description || '—'}</div></div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <Stat label="Tổng cảnh báo" value={inc.alert_count} />
        <Stat label="Chưa xác minh" value={inc.unverified_alerts} cls="text-gray-700" />
        <Stat label="Đã xác minh" value={inc.verified_alerts} cls="text-green-600" />
        <Stat label="Bỏ qua" value={inc.dismissed_alerts} cls="text-yellow-600" />
        <Stat label="File tải lên" value={inc.upload_count} />
      </div>

      <div>
        <div className="flex gap-1 border-b mb-4">
          {tabs.map(tb => (
            <button key={tb.key} onClick={() => setTab(tb.key)}
              className={`px-4 py-2 text-sm -mb-px border-b-2 ${tab === tb.key ? 'border-primary-600 text-primary-600 font-medium' : 'border-transparent text-gray-600 hover:text-gray-900'}`}>
              {tb.label}
            </button>
          ))}
        </div>

        {tab === 'alerts' && (
          <AlertsTable
            incidentId={inc.id}
            locked={terminal}
            uploads={uploads}
            filterUploadId={filterUpload}
            onFilterUploadChange={setFilterUpload}
            refreshKey={refreshKey}
            onChanged={loadIncident}
          />
        )}
        {tab === 'uploads' && (
          <UploadPanel
            incident={inc}
            uploads={uploads}
            canUpload={canUpload(inc.status)}
            onUploaded={(u) => { prevStatus.current[u.id] = u.status; refreshUploads(); loadIncident() }}
            onViewAlerts={(uid) => { setFilterUpload(uid); setTab('alerts') }}
          />
        )}
        {tab === 'history' && (
          <div className="bg-white border rounded-lg divide-y">
            {history.map(h => (
              <div key={h.id} className="px-4 py-3 text-sm flex flex-wrap items-center gap-2">
                <span className="text-gray-500 w-44">{formatDateTime(h.changed_at)}</span>
                {h.old_status ? <Badge info={STATUS[h.old_status]} /> : <span className="text-gray-400">—</span>}
                <span>→</span>
                <Badge info={STATUS[h.new_status]} />
                <span className="text-gray-600">· {h.changed_by_name}</span>
                {h.note && <span className="text-gray-500">· {t(h.note)}</span>}
              </div>
            ))}
          </div>
        )}
      </div>

      <IncidentFormModal open={showEdit} incident={inc} onClose={() => setShowEdit(false)}
        onSaved={() => { setShowEdit(false); loadIncident() }} />
      <ConfirmModal
        open={!!transition}
        title={transition ? t(transitionLabel(inc.status, transition)) : ''}
        message={transition ? t('Chuyển sự cố sang “{status}”?', { status: t(STATUS[transition].label) }) : ''}
        withReason={transition ? needsReason(inc.status, transition) : false}
        danger={transition === 'cancelled'}
        onConfirm={doTransition}
        onClose={() => setTransition(null)}
      />
      <ConfirmModal
        open={showDelete}
        title={t('Xóa sự cố')}
        message={t('Sự cố chưa có cảnh báo nào nên có thể xóa hẳn, kể cả các file đã upload. Không hoàn tác được.')}
        confirmText="Xóa"
        danger
        onConfirm={doDelete}
        onClose={() => setShowDelete(false)}
      />
    </div>
  )
}
