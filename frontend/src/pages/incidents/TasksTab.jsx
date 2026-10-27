import { useEffect, useState } from 'react'
import { getTasks, getTaskSummary, getTaskAssignees, applyPlaybook, createTask,
  updateTask, deleteTask } from '../../api/incidents'
import { getPlaybooks } from '../../api/playbooks'
import { PHASES, ROLE_LABEL, PLAYBOOK_TYPES, parseUtc } from '../../utils/playbook'
import Badge from '../../components/Badge'
import Card from '../../components/Card'
import Modal from '../../components/Modal'
import toast from 'react-hot-toast'

const STATUS_LABEL = { todo: 'Chưa làm', in_progress: 'Đang làm', done: 'Đã xong', skipped: 'Đã bỏ qua' }
const input = 'w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-400'

export default function TasksTab({ incId, isAnalyst, isIT, myId, isCommander, closed }) {
  const [tasks, setTasks]       = useState([])
  const [summary, setSummary]   = useState(null)
  const [assignees, setAssignees] = useState([])
  const [playbooks, setPlaybooks] = useState([])
  const [showApply, setShowApply] = useState(false)
  const [showAdd, setShowAdd]   = useState(false)
  const [pbId, setPbId]         = useState('')
  const [busy, setBusy]         = useState(false)
  const [form, setForm] = useState({
    title: '', description: '', phase: 'analysis', owner_role: '', assignee_id: '', due_hours: '', is_required: false,
  })

  const load = () => {
    getTasks(incId).then(r => setTasks(r.data))
    getTaskSummary(incId).then(r => setSummary(r.data))
  }
  useEffect(() => { load() }, [incId])
  useEffect(() => {
    if (!isAnalyst) return
    getTaskAssignees(incId).then(r => setAssignees(r.data)).catch(() => {})
  }, [incId, isAnalyst])

  const nameOf = (id) => {
    if (!id) return null
    if (id === myId) return 'bạn'
    return assignees.find(a => a.id === id)?.username || `#${id}`
  }

  const openApply = async () => {
    const res = await getPlaybooks({ active_only: true })
    setPlaybooks(res.data)
    setPbId(res.data[0]?.id ? String(res.data[0].id) : '')
    setShowApply(true)
  }

  const handleApply = async (e) => {
    e.preventDefault()
    if (!pbId) return
    setBusy(true)
    try {
      const res = await applyPlaybook(incId, parseInt(pbId))
      const { created, already_present } = res.data
      toast.success(created ? `Đã thêm ${created} công việc` : `Playbook đã được áp dụng trước đó (${already_present} công việc)`)
      setShowApply(false)
      load()
    } catch (err) { toast.error(err.response?.data?.detail || 'Thất bại') }
    finally { setBusy(false) }
  }

  const handleAdd = async (e) => {
    e.preventDefault()
    setBusy(true)
    try {
      await createTask(incId, {
        title: form.title, description: form.description || null, phase: form.phase,
        owner_role: form.owner_role || null,
        assignee_id: form.assignee_id ? parseInt(form.assignee_id) : null,
        due_hours: form.due_hours !== '' ? parseInt(form.due_hours) : null,
        is_required: form.is_required,
      })
      toast.success('Đã thêm công việc')
      setShowAdd(false)
      setForm({ title: '', description: '', phase: 'analysis', owner_role: '', assignee_id: '', due_hours: '', is_required: false })
      load()
    } catch (err) {
      const d = err.response?.data?.detail
      toast.error(typeof d === 'string' ? d : 'Thất bại')
    } finally { setBusy(false) }
  }

  const change = async (task, status, needNote) => {
    let note
    if (needNote) {
      note = prompt(needNote)
      if (!note || !note.trim()) return
    }
    try {
      await updateTask(incId, task.id, note ? { status, note } : { status })
      load()
    } catch (err) { toast.error(err.response?.data?.detail || 'Thất bại') }
  }

  const assign = async (task, value) => {
    try {
      await updateTask(incId, task.id, { assignee_id: value ? parseInt(value) : null })
      load()
    } catch (err) { toast.error(err.response?.data?.detail || 'Thất bại') }
  }

  const remove = async (task) => {
    if (!confirm('Xóa công việc này?')) return
    try {
      await deleteTask(incId, task.id)
      load()
    } catch (err) { toast.error(err.response?.data?.detail || 'Thất bại') }
  }

  // IT chỉ làm được việc giao cho mình hoặc việc chưa giao thuộc IT
  const canAct = (t) => !closed && (isAnalyst || (isIT && (t.assignee_id === myId ||
    (t.assignee_id == null && t.owner_role === 'it_helpdesk'))))

  const grouped = PHASES.map(([key, label]) => [key, label, tasks.filter(t => t.phase === key)]).filter(g => g[2].length)

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        {summary && summary.total > 0 ? (
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="px-2 py-1 rounded bg-gray-100 text-gray-700">{summary.total} công việc</span>
            <span className="px-2 py-1 rounded bg-green-100 text-green-700">{summary.completion_pct}% đã xử lý</span>
            <span className={`px-2 py-1 rounded ${summary.open_required ? 'bg-yellow-100 text-yellow-800' : 'bg-green-100 text-green-700'}`}>
              {summary.open_required} bắt buộc chưa xong
            </span>
            {summary.overdue > 0 && <span className="px-2 py-1 rounded bg-red-100 text-red-700">{summary.overdue} quá hạn</span>}
          </div>
        ) : <div />}
        {isAnalyst && !closed && (
          <div className="flex gap-2">
            <button onClick={openApply}
              className="text-sm px-4 py-2 border border-primary-200 text-primary-700 rounded-lg hover:bg-primary-50">
              Áp dụng playbook
            </button>
            <button onClick={() => setShowAdd(true)}
              className="text-sm px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700">
              + Công việc
            </button>
          </div>
        )}
      </div>

      {tasks.length === 0 ? (
        <Card>
          <p className="text-sm text-gray-500">
            Chưa có công việc nào. {isAnalyst && !closed ? 'Áp dụng một playbook để tạo danh sách việc theo loại sự cố, hoặc thêm công việc thủ công.' : ''}
          </p>
        </Card>
      ) : grouped.map(([key, label, list]) => (
        <Card key={key} title={`${label} (${list.filter(t => t.status === 'done' || t.status === 'skipped').length}/${list.length})`}>
          <div className="divide-y divide-gray-100">
            {list.map(t => (
              <div key={t.id} className="py-3 first:pt-0 last:pb-0">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge label={STATUS_LABEL[t.status]} type={t.status} />
                      <span className={`text-sm font-medium ${t.status === 'skipped' ? 'text-gray-400 line-through' : 'text-gray-800'}`}>{t.title}</span>
                      {t.is_required && <span className="text-xs bg-orange-100 text-orange-700 px-2 py-0.5 rounded">Bắt buộc</span>}
                      {t.is_overdue && <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded">Quá hạn</span>}
                      {!t.playbook_id && <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded">Thủ công</span>}
                    </div>
                    {t.description && <p className="text-xs text-gray-500 mt-1">{t.description}</p>}
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2 text-xs text-gray-500">
                      <span>Vai trò: {t.owner_role ? ROLE_LABEL[t.owner_role] : '—'}</span>
                      <span>
                        Người làm:{' '}
                        {isAnalyst && !closed ? (
                          <select value={t.assignee_id || ''} onChange={e => assign(t, e.target.value)}
                            className="border border-gray-200 rounded px-1 py-0.5 text-xs">
                            <option value="">Chưa giao</option>
                            {assignees.map(a => <option key={a.id} value={a.id}>{a.username}</option>)}
                          </select>
                        ) : (nameOf(t.assignee_id) || 'Chưa giao')}
                      </span>
                      <span className={t.is_overdue ? 'text-red-600 font-medium' : ''}>
                        Hạn: {t.due_at ? parseUtc(t.due_at).toLocaleString('vi-VN') : '—'}
                      </span>
                      {t.completed_at && <span>Xử lý lúc: {parseUtc(t.completed_at).toLocaleString('vi-VN')}</span>}
                    </div>
                    {t.note && <p className="text-xs text-gray-600 bg-gray-50 px-2 py-1 rounded mt-2">{t.note}</p>}
                  </div>

                  {canAct(t) && (
                    <div className="flex flex-wrap gap-2">
                      {t.status === 'todo' && (
                        <button onClick={() => change(t, 'in_progress')}
                          className="text-xs px-3 py-1 bg-blue-100 text-blue-700 rounded hover:bg-blue-200">Bắt đầu</button>
                      )}
                      {(t.status === 'todo' || t.status === 'in_progress') && (
                        <button onClick={() => change(t, 'done')}
                          className="text-xs px-3 py-1 bg-green-100 text-green-700 rounded hover:bg-green-200">✓ Xong</button>
                      )}
                      {t.status === 'in_progress' && (
                        <button onClick={() => change(t, 'todo')}
                          className="text-xs px-3 py-1 bg-gray-100 text-gray-600 rounded hover:bg-gray-200">Trả lại</button>
                      )}
                      {isAnalyst && (t.status === 'todo' || t.status === 'in_progress') && (!t.is_required || isCommander) && (
                        <button onClick={() => change(t, 'skipped', 'Lý do bỏ qua công việc:')}
                          className="text-xs px-3 py-1 bg-yellow-100 text-yellow-800 rounded hover:bg-yellow-200">Bỏ qua</button>
                      )}
                      {isAnalyst && t.status === 'done' && (
                        <button onClick={() => change(t, 'in_progress', 'Lý do mở lại công việc:')}
                          className="text-xs px-3 py-1 bg-gray-100 text-gray-600 rounded hover:bg-gray-200">Mở lại</button>
                      )}
                      {isAnalyst && t.status === 'skipped' && (!t.is_required || isCommander) && (
                        <button onClick={() => change(t, 'todo')}
                          className="text-xs px-3 py-1 bg-gray-100 text-gray-600 rounded hover:bg-gray-200">Mở lại</button>
                      )}
                      {isAnalyst && !t.playbook_id && t.status !== 'done' && (
                        <button onClick={() => remove(t)}
                          className="text-xs px-3 py-1 bg-red-50 text-red-600 rounded hover:bg-red-100">Xóa</button>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Card>
      ))}

      <Modal open={showApply} onClose={() => setShowApply(false)} title="Áp dụng playbook">
        <form onSubmit={handleApply} className="space-y-3">
          {playbooks.length === 0 ? (
            <p className="text-sm text-gray-500">Chưa có playbook nào đang sử dụng.</p>
          ) : (
            <>
              <div>
                <label className="block text-xs text-gray-600 mb-1">Chọn playbook</label>
                <select value={pbId} onChange={e => setPbId(e.target.value)} className={input}>
                  {playbooks.map(p => (
                    <option key={p.id} value={p.id}>{p.name} ({PLAYBOOK_TYPES[p.incident_type]}, {p.step_count} bước)</option>
                  ))}
                </select>
              </div>
              <p className="text-xs text-gray-500">
                Hệ thống tạo công việc cho từng bước. Bước đã có sẵn trong vụ này sẽ không bị tạo trùng.
                Công việc bắt buộc phải xong hoặc được commander bỏ qua kèm lý do thì mới đóng được vụ.
              </p>
            </>
          )}
          <div className="flex gap-2">
            <button type="button" onClick={() => setShowApply(false)}
              className="flex-1 border border-gray-200 text-gray-600 rounded-lg py-2 text-sm">Hủy</button>
            <button type="submit" disabled={busy || !pbId}
              className="flex-1 bg-primary-600 text-white rounded-lg py-2 text-sm disabled:opacity-50">
              {busy ? 'Đang áp dụng...' : 'Áp dụng'}
            </button>
          </div>
        </form>
      </Modal>

      <Modal open={showAdd} onClose={() => setShowAdd(false)} title="Thêm công việc">
        <form onSubmit={handleAdd} className="space-y-3">
          <div>
            <label className="block text-xs text-gray-600 mb-1">Tên công việc *</label>
            <input value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} className={input} required />
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">Mô tả</label>
            <textarea value={form.description} onChange={e => setForm({ ...form, description: e.target.value })}
              rows={2} className={`${input} resize-none`} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-600 mb-1">Giai đoạn</label>
              <select value={form.phase} onChange={e => setForm({ ...form, phase: e.target.value })} className={input}>
                {PHASES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">Vai trò thường làm</label>
              <select value={form.owner_role} onChange={e => setForm({ ...form, owner_role: e.target.value })} className={input}>
                <option value="">Không rõ</option>
                {Object.entries(ROLE_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">Giao cho</label>
              <select value={form.assignee_id} onChange={e => setForm({ ...form, assignee_id: e.target.value })} className={input}>
                <option value="">Chưa giao</option>
                {assignees.map(a => <option key={a.id} value={a.id}>{a.username}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">Hạn (số giờ từ bây giờ)</label>
              <input type="number" min="0" value={form.due_hours}
                onChange={e => setForm({ ...form, due_hours: e.target.value })} className={input} />
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input type="checkbox" checked={form.is_required}
              onChange={e => setForm({ ...form, is_required: e.target.checked })} className="rounded border-gray-300" />
            Bắt buộc phải xong mới đóng được vụ
          </label>
          <div className="flex gap-2">
            <button type="button" onClick={() => setShowAdd(false)}
              className="flex-1 border border-gray-200 text-gray-600 rounded-lg py-2 text-sm">Hủy</button>
            <button type="submit" disabled={busy}
              className="flex-1 bg-primary-600 text-white rounded-lg py-2 text-sm disabled:opacity-50">
              {busy ? 'Đang lưu...' : 'Thêm'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
