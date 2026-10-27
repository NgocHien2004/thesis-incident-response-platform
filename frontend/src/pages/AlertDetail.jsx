import { useEffect, useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { getAlert, triageAlert, markFalsePositive, suggestAI } from '../api/alerts'
import { createIncident, getIncidents } from '../api/incidents'
import { getPlaybooks } from '../api/playbooks'
import { guessPlaybookType } from '../utils/playbook'
import Badge from '../components/Badge'
import Card from '../components/Card'
import Modal from '../components/Modal'
import LoadingSpinner from '../components/LoadingSpinner'
import toast from 'react-hot-toast'
import { useAuth } from '../context/AuthContext'

const SEVERITIES  = ['critical', 'high', 'medium', 'low', 'info']
const TRIAGE_TYPES = ['intrusion', 'phishing', 'malware', 'credential_compromise', 'web_attack', 'dos', 'reconnaissance', 'other']

export default function AlertDetail() {
  const { id }       = useParams()
  const { user }     = useAuth()
  const navigate     = useNavigate()
  const [alert, setAlert]         = useState(null)
  const [loading, setLoading]     = useState(true)
  const [aiSuggest, setAiSuggest] = useState(null)
  const [aiLoading, setAiLoading] = useState(false)
  const [showTriage, setShowTriage]   = useState(false)
  const [showIncident, setShowIncident] = useState(false)
  const [triaging, setTriaging]   = useState(false)
  const [creating, setCreating]   = useState(false)

  const [triageForm, setTriageForm] = useState({
    triage_type: 'intrusion', triage_severity: 'medium',
    triage_confidence: 80, triage_sla_hours: 4, triage_note: ''
  })
  const [incForm, setIncForm] = useState({ title: '', severity: 'high', description: '', playbook_id: '' })
  const [playbooks, setPlaybooks] = useState([])

  const isAnalyst = user?.role === 'analyst_soc'
  const isIT      = user?.role === 'it_helpdesk'

  useEffect(() => {
    getAlert(id)
      .then(r => {
        setAlert(r.data)
        setTriageForm(f => ({
          ...f,
          triage_severity: r.data.severity || 'medium',
          triage_type: r.data.triage_type || 'intrusion',
        }))
        setIncForm(f => ({ ...f, title: r.data.title, severity: r.data.severity || 'high' }))
      })
      .finally(() => setLoading(false))
  }, [id])

  const handleAISuggest = async () => {
    if (!alert) return
    setAiLoading(true)
    try {
      const res = await suggestAI({
        title: alert.title,
        description: alert.description || '',
        ioc: alert.ioc || ''
      })
      setAiSuggest(res.data)
      // Áp dụng AI suggestion vào form triage
      setTriageForm(f => ({
        ...f,
        triage_severity: res.data.severity_suggestion || f.triage_severity,
        triage_type: res.data.attck_techniques?.[0]?.id || f.triage_type,
        triage_note: res.data.summary || f.triage_note,
      }))
      toast.success('AI đã đề xuất — kiểm tra và xác nhận trước khi lưu')
    } catch {
      toast.error('AI service không khả dụng')
    } finally {
      setAiLoading(false)
    }
  }

  const handleTriage = async (e) => {
    e.preventDefault()
    setTriaging(true)
    try {
      const res = await triageAlert(id, {
        ...triageForm,
        triage_confidence: parseInt(triageForm.triage_confidence),
        triage_sla_hours: parseInt(triageForm.triage_sla_hours),
      })
      setAlert(res.data)
      setShowTriage(false)
      toast.success('Triage thành công')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Triage thất bại')
    } finally {
      setTriaging(false)
    }
  }

  const handleFalsePositive = async () => {
    if (!confirm('Đánh dấu false positive?')) return
    try {
      await markFalsePositive(id)
      toast.success('Đã đánh dấu false positive')
      navigate('/alerts')
    } catch {
      toast.error('Thất bại')
    }
  }

  const openIncident = async () => {
    try {
      const pb = await getPlaybooks({ active_only: true })
      setPlaybooks(pb.data)
      const type = guessPlaybookType(alert?.triage_type, alert?.title)
      const match = pb.data.find(p => p.incident_type === type)
      setIncForm(f => ({ ...f, playbook_id: f.playbook_id || (match ? String(match.id) : '') }))
    } catch { /* không có playbook vẫn tạo được incident */ }
    setShowIncident(true)
  }

  const handleCreateIncident = async (e) => {
    e.preventDefault()
    setCreating(true)
    try {
      const res = await createIncident({
        ...incForm,
        playbook_id: incForm.playbook_id ? parseInt(incForm.playbook_id) : null,
        commander_id: parseInt(user?.id),
        alert_ids: [parseInt(id)]
      })
      toast.success(`Đã tạo Incident #${res.data.id}`)
      navigate(`/incidents/${res.data.id}`)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Tạo incident thất bại')
    } finally {
      setCreating(false)
    }
  }

  if (loading) return <LoadingSpinner />
  if (!alert) return <div className="p-6 text-gray-500">Không tìm thấy cảnh báo</div>

  const canTriage   = (isAnalyst || isIT) && ['new', 'reviewing'].includes(alert.status)
  const canEscalate = isAnalyst && alert.status === 'triaged' && !alert.incident_id
  const canFalsePositive = isAnalyst && ['new', 'reviewing', 'triaged'].includes(alert.status) && !alert.incident_id

  return (
    <div className="p-6 space-y-4">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <Link to="/alerts" className="hover:text-primary-600">Cảnh báo</Link>
        <span>/</span>
        <span className="text-gray-900">#{alert.id}</span>
      </div>

      {/* Header */}
      <div className="bg-white rounded-lg border border-gray-200 p-5">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              <Badge label={alert.severity} type={alert.severity} />
              <Badge label={alert.status} type={alert.status} />
              {alert.incident_id && (
                <Link
                  to={`/incidents/${alert.incident_id}`}
                  className="text-xs text-purple-600 hover:underline"
                >
                  → Incident #{alert.incident_id}
                </Link>
              )}
            </div>
            <h1 className="text-lg font-semibold text-gray-900">{alert.title}</h1>
            {alert.description && (
              <p className="text-sm text-gray-600 mt-2">{alert.description}</p>
            )}
          </div>

          {/* Actions */}
          <div className="flex gap-2 flex-shrink-0">
            {isAnalyst && (
              <button
                onClick={handleAISuggest}
                disabled={aiLoading}
                className="text-sm px-3 py-2 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 rounded-lg border border-indigo-200 transition-colors disabled:opacity-50"
              >
                {aiLoading ? '⏳ AI...' : '🤖 AI Suggest'}
              </button>
            )}
            {canTriage && (
              <button
                onClick={() => setShowTriage(true)}
                className="text-sm px-3 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg transition-colors"
              >
                Triage
              </button>
            )}
            {canEscalate && (
              <button
                onClick={openIncident}
                className="text-sm px-3 py-2 bg-orange-500 hover:bg-orange-600 text-white rounded-lg transition-colors"
              >
                Tạo Incident
              </button>
            )}
            {canFalsePositive && (
              <button
                onClick={handleFalsePositive}
                className="text-sm px-3 py-2 bg-white hover:bg-gray-50 text-gray-600 rounded-lg border border-gray-200 transition-colors"
              >
                False Positive
              </button>
            )}
          </div>
        </div>

        {/* Metadata */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4 pt-4 border-t border-gray-100">
          {[
            { label: 'Nguồn', value: alert.source },
            { label: 'IOC', value: alert.ioc || '—', mono: true },
            { label: 'Tài sản', value: alert.affected_asset ? `#${alert.affected_asset}` : '—' },
            { label: 'Thời gian', value: new Date(alert.created_at).toLocaleString('vi-VN') },
          ].map(m => (
            <div key={m.label}>
              <div className="text-xs text-gray-400 mb-0.5">{m.label}</div>
              <div className={`text-sm text-gray-700 ${m.mono ? 'font-mono' : ''}`}>{m.value}</div>
            </div>
          ))}
        </div>
      </div>

      {/* AI Suggestion */}
      {aiSuggest && (
        <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-sm font-semibold text-indigo-800">🤖 AI Đề xuất</span>
            <span className="text-xs bg-indigo-200 text-indigo-700 px-2 py-0.5 rounded">
              Cần Analyst xác nhận
            </span>
          </div>
          <p className="text-sm text-indigo-700 mb-3">{aiSuggest.summary}</p>
          <div className="space-y-2">
            {aiSuggest.attck_techniques?.slice(0, 3).map(t => (
              <div key={t.id} className="flex items-start gap-3 bg-white rounded p-3 border border-indigo-100">
                <div className="text-xs font-mono font-bold text-indigo-600 w-16 flex-shrink-0">{t.id}</div>
                <div className="flex-1">
                  <div className="text-xs font-medium text-gray-800">{t.name}</div>
                  <div className="text-xs text-gray-500 mt-0.5">{t.tactics?.join(', ')}</div>
                </div>
                <div className="text-xs text-gray-400">score: {t.score}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Triage info */}
      {alert.triage_type && (
        <Card title="Thông tin Triage">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: 'Loại', value: alert.triage_type },
              { label: 'Mức độ', value: <Badge label={alert.triage_severity} type={alert.triage_severity} /> },
              { label: 'Độ tin cậy', value: `${alert.triage_confidence}%` },
              { label: 'SLA deadline', value: alert.triage_sla_deadline
                ? new Date(alert.triage_sla_deadline).toLocaleString('vi-VN')
                : '—' },
            ].map(m => (
              <div key={m.label}>
                <div className="text-xs text-gray-400 mb-0.5">{m.label}</div>
                <div className="text-sm text-gray-700">{m.value}</div>
              </div>
            ))}
          </div>
          {alert.triage_note && (
            <div className="mt-3 pt-3 border-t border-gray-100">
              <div className="text-xs text-gray-400 mb-1">Ghi chú</div>
              <p className="text-sm text-gray-700">{alert.triage_note}</p>
            </div>
          )}
        </Card>
      )}

      {/* Modal Triage */}
      <Modal open={showTriage} onClose={() => setShowTriage(false)} title="Triage cảnh báo">
        {aiSuggest && (
          <div className="mb-4 p-3 bg-indigo-50 rounded-lg border border-indigo-100 text-xs text-indigo-700">
            🤖 AI đề xuất đã được điền sẵn — xem lại và chỉnh sửa nếu cần
          </div>
        )}
        <form onSubmit={handleTriage} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-600 mb-1">Loại tấn công</label>
              <select
                value={triageForm.triage_type}
                onChange={e => setTriageForm({...triageForm, triage_type: e.target.value})}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-400"
              >
                {TRIAGE_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">Mức độ</label>
              <select
                value={triageForm.triage_severity}
                onChange={e => setTriageForm({...triageForm, triage_severity: e.target.value})}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-400"
              >
                {SEVERITIES.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-600 mb-1">Độ tin cậy (1-100)</label>
              <input
                type="number" min={1} max={100}
                value={triageForm.triage_confidence}
                onChange={e => setTriageForm({...triageForm, triage_confidence: e.target.value})}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-400"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">SLA (giờ)</label>
              <select
                value={triageForm.triage_sla_hours}
                onChange={e => setTriageForm({...triageForm, triage_sla_hours: e.target.value})}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-400"
              >
                {[1, 4, 8, 24, 48, 72].map(h => (
                  <option key={h} value={h}>{h} giờ</option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">Ghi chú</label>
            <textarea
              value={triageForm.triage_note}
              onChange={e => setTriageForm({...triageForm, triage_note: e.target.value})}
              rows={3}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-400 resize-none"
            />
          </div>
          <div className="flex gap-2">
            <button type="button" onClick={() => setShowTriage(false)}
              className="flex-1 border border-gray-200 text-gray-600 rounded-lg py-2 text-sm hover:bg-gray-50">
              Hủy
            </button>
            <button type="submit" disabled={triaging}
              className="flex-1 bg-primary-600 text-white rounded-lg py-2 text-sm hover:bg-primary-700 disabled:opacity-50">
              {triaging ? 'Đang lưu...' : 'Lưu triage'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Modal tạo Incident */}
      <Modal open={showIncident} onClose={() => setShowIncident(false)} title="Tạo Incident từ cảnh báo này">
        <form onSubmit={handleCreateIncident} className="space-y-4">
          <div>
            <label className="block text-xs text-gray-600 mb-1">Tên incident</label>
            <input
              value={incForm.title}
              onChange={e => setIncForm({...incForm, title: e.target.value})}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-400"
              required
            />
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">Mức độ</label>
            <select
              value={incForm.severity}
              onChange={e => setIncForm({...incForm, severity: e.target.value})}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-400"
            >
              {['critical','high','medium','low'].map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">Playbook (tạo sẵn danh sách công việc)</label>
            <select value={incForm.playbook_id}
              onChange={e => setIncForm({...incForm, playbook_id: e.target.value})}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-400">
              <option value="">Không dùng playbook</option>
              {playbooks.map(p => <option key={p.id} value={p.id}>{p.name} ({p.step_count} bước)</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">Mô tả</label>
            <textarea
              value={incForm.description}
              onChange={e => setIncForm({...incForm, description: e.target.value})}
              rows={3}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-400 resize-none"
            />
          </div>
          <div className="flex gap-2">
            <button type="button" onClick={() => setShowIncident(false)}
              className="flex-1 border border-gray-200 text-gray-600 rounded-lg py-2 text-sm hover:bg-gray-50">
              Hủy
            </button>
            <button type="submit" disabled={creating}
              className="flex-1 bg-orange-500 text-white rounded-lg py-2 text-sm hover:bg-orange-600 disabled:opacity-50">
              {creating ? 'Đang tạo...' : 'Tạo Incident'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  )
}