import { useEffect, useState } from 'react'
import { getPlaybooks, getPlaybook, createPlaybook, updatePlaybook } from '../api/playbooks'
import { PHASES, ROLE_LABEL, PLAYBOOK_TYPES } from '../utils/playbook'
import LoadingSpinner from '../components/LoadingSpinner'
import Card from '../components/Card'
import toast from 'react-hot-toast'
import { useAuth } from '../context/AuthContext'

const input = 'w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-400'
const phaseLabel = Object.fromEntries(PHASES)
const emptyStep = () => ({ title: '', description: '', phase: 'analysis', owner_role: '', due_hours: '', is_required: true, reference: '' })
const emptyForm = () => ({
  name: '', incident_type: 'other', description: '', source: '', is_active: true, steps: [emptyStep()],
})

export default function Playbooks() {
  const { user } = useAuth()
  const isAnalyst = user?.role === 'analyst_soc'
  const [list, setList]       = useState([])
  const [loading, setLoading] = useState(true)
  const [open, setOpen]       = useState(null)      // playbook đang xem
  const [editing, setEditing] = useState(null)      // null | 'new' | id
  const [form, setForm]       = useState(emptyForm())
  const [saving, setSaving]   = useState(false)

  const load = () => {
    setLoading(true)
    getPlaybooks().then(r => setList(r.data)).finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  const view = async (id) => {
    if (open?.id === id) { setOpen(null); return }
    const r = await getPlaybook(id)
    setOpen(r.data)
  }

  const startNew = () => { setForm(emptyForm()); setEditing('new') }
  const startEdit = async (id) => {
    const r = await getPlaybook(id)
    const p = r.data
    setForm({
      name: p.name, incident_type: p.incident_type, description: p.description || '', source: p.source || '',
      is_active: p.is_active,
      steps: p.steps.map(s => ({
        title: s.title, description: s.description || '', phase: s.phase, owner_role: s.owner_role || '',
        due_hours: s.due_hours ?? '', is_required: s.is_required, reference: s.reference || '',
      })),
    })
    setEditing(id)
  }

  const setStep = (i, patch) => setForm(f => ({ ...f, steps: f.steps.map((s, k) => (k === i ? { ...s, ...patch } : s)) }))
  const moveStep = (i, d) => setForm(f => {
    const j = i + d
    if (j < 0 || j >= f.steps.length) return f
    const steps = [...f.steps];
    [steps[i], steps[j]] = [steps[j], steps[i]]
    return { ...f, steps }
  })
  const removeStep = (i) => setForm(f => ({ ...f, steps: f.steps.filter((_, k) => k !== i) }))

  const save = async (e) => {
    e.preventDefault()
    if (form.steps.length === 0) { toast.error('Playbook cần ít nhất 1 bước'); return }
    const body = {
      name: form.name, incident_type: form.incident_type,
      description: form.description || null, source: form.source || null,
      steps: form.steps.map(s => ({
        title: s.title, description: s.description || null, phase: s.phase,
        owner_role: s.owner_role || null,
        due_hours: s.due_hours !== '' ? parseInt(s.due_hours) : null,
        is_required: s.is_required,
        reference: s.reference.trim() || null,
      })),
    }
    setSaving(true)
    try {
      if (editing === 'new') await createPlaybook(body)
      else await updatePlaybook(editing, { ...body, is_active: form.is_active })
      toast.success('Đã lưu playbook')
      setEditing(null)
      setOpen(null)
      load()
    } catch (err) {
      const d = err.response?.data?.detail
      toast.error(typeof d === 'string' ? d : 'Lưu thất bại, kiểm tra các trường bắt buộc')
    } finally { setSaving(false) }
  }

  if (loading) return <LoadingSpinner />

  if (editing) {
    return (
      <form onSubmit={save} className="p-6 space-y-4 max-w-4xl">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-semibold text-gray-900">{editing === 'new' ? 'Tạo playbook' : 'Chỉnh sửa playbook'}</h1>
          <button type="button" onClick={() => setEditing(null)} className="text-sm text-gray-500 hover:text-gray-700">← Quay lại</button>
        </div>

        <Card>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-600 mb-1">Tên playbook *</label>
              <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} className={input} required />
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">Loại sự cố</label>
              <select value={form.incident_type} onChange={e => setForm({ ...form, incident_type: e.target.value })} className={input}>
                {Object.entries(PLAYBOOK_TYPES).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
              </select>
            </div>
            <div className="md:col-span-2">
              <label className="block text-xs text-gray-600 mb-1">Mô tả</label>
              <textarea value={form.description} onChange={e => setForm({ ...form, description: e.target.value })}
                rows={2} className={`${input} resize-none`} />
            </div>
            <div className="md:col-span-2">
              <label className="block text-xs text-gray-600 mb-1">Tài liệu tham chiếu</label>
              <input value={form.source} onChange={e => setForm({ ...form, source: e.target.value })} className={input} />
            </div>
            {editing !== 'new' && (
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input type="checkbox" checked={form.is_active}
                  onChange={e => setForm({ ...form, is_active: e.target.checked })} className="rounded border-gray-300" />
                Đang sử dụng (bỏ chọn để ngừng dùng, công việc đã tạo không bị ảnh hưởng)
              </label>
            )}
          </div>
        </Card>

        <Card title={`Các bước (${form.steps.length})`}
          action={<button type="button" onClick={() => setForm(f => ({ ...f, steps: [...f.steps, emptyStep()] }))}
            className="text-xs px-3 py-1 bg-primary-600 text-white rounded hover:bg-primary-700">+ Thêm bước</button>}>
          <div className="space-y-3">
            {form.steps.map((s, i) => (
              <div key={i} className="border border-gray-200 rounded-lg p-3 space-y-2">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-400 w-6">{i + 1}.</span>
                  <input value={s.title} onChange={e => setStep(i, { title: e.target.value })}
                    placeholder="Tên bước *" className={input} required />
                  <button type="button" onClick={() => moveStep(i, -1)} className="text-gray-400 hover:text-gray-700 px-1" title="Lên">↑</button>
                  <button type="button" onClick={() => moveStep(i, 1)} className="text-gray-400 hover:text-gray-700 px-1" title="Xuống">↓</button>
                  <button type="button" onClick={() => removeStep(i)} className="text-red-400 hover:text-red-600 px-1" title="Xóa">✕</button>
                </div>
                <textarea value={s.description} onChange={e => setStep(i, { description: e.target.value })}
                  placeholder="Mô tả cách thực hiện" rows={2} className={`${input} resize-none`} />
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2 items-end">
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Giai đoạn</label>
                    <select value={s.phase} onChange={e => setStep(i, { phase: e.target.value })} className={input}>
                      {PHASES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Vai trò thường làm</label>
                    <select value={s.owner_role} onChange={e => setStep(i, { owner_role: e.target.value })} className={input}>
                      <option value="">Không rõ</option>
                      {Object.entries(ROLE_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Hạn (giờ từ lúc tạo vụ)</label>
                    <input type="number" min="0" value={s.due_hours}
                      onChange={e => setStep(i, { due_hours: e.target.value })} className={input} />
                  </div>
                  <label className="flex items-center gap-2 text-sm text-gray-700 pb-2">
                    <input type="checkbox" checked={s.is_required}
                      onChange={e => setStep(i, { is_required: e.target.checked })} className="rounded border-gray-300" />
                    Bắt buộc
                  </label>
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Mã mục trong tài liệu nguồn (không bắt buộc)</label>
                  <input value={s.reference} onChange={e => setStep(i, { reference: e.target.value })}
                    maxLength={100} placeholder="Ví dụ: CISA B 3a–3b" className={input} />
                </div>
              </div>
            ))}
          </div>
        </Card>

        <div className="flex gap-2">
          <button type="button" onClick={() => setEditing(null)}
            className="px-5 border border-gray-200 text-gray-600 rounded-lg py-2 text-sm hover:bg-gray-50">Hủy</button>
          <button type="submit" disabled={saving}
            className="px-5 bg-primary-600 text-white rounded-lg py-2 text-sm hover:bg-primary-700 disabled:opacity-50">
            {saving ? 'Đang lưu...' : 'Lưu playbook'}
          </button>
        </div>
      </form>
    )
  }

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-lg font-semibold text-gray-900">Playbook</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Mẫu quy trình theo loại sự cố. Khi áp dụng cho một vụ, mỗi bước trở thành một công việc có người phụ trách và hạn.
          </p>
        </div>
        {isAnalyst && (
          <button onClick={startNew} className="text-sm px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700">
            + Tạo playbook
          </button>
        )}
      </div>

      {list.length === 0 ? (
        <Card><p className="text-sm text-gray-500">Chưa có playbook nào.</p></Card>
      ) : list.map(p => (
        <div key={p.id} className={`bg-white rounded-lg border shadow-sm ${p.is_active ? 'border-gray-200' : 'border-gray-200 opacity-60'}`}>
          <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
            <button onClick={() => view(p.id)} className="text-left min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-semibold text-gray-800">{p.name}</span>
                <span className="text-xs bg-primary-50 text-primary-700 px-2 py-0.5 rounded">{PLAYBOOK_TYPES[p.incident_type]}</span>
                {!p.is_active && <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded">Ngừng sử dụng</span>}
              </div>
              {p.description && <p className="text-xs text-gray-500 mt-1">{p.description}</p>}
              <p className="text-xs text-gray-400 mt-1">{p.step_count} bước, {p.required_count} bắt buộc</p>
            </button>
            {isAnalyst && (
              <button onClick={() => startEdit(p.id)}
                className="text-xs px-3 py-1 border border-gray-200 text-gray-600 rounded hover:bg-gray-50">Chỉnh sửa</button>
            )}
          </div>

          {open?.id === p.id && (
            <div className="border-t border-gray-100 px-5 py-4 space-y-3">
              <ol className="space-y-2">
                {open.steps.map(s => (
                  <li key={s.id} className="flex gap-3 text-sm">
                    <span className="text-xs text-gray-400 w-5 pt-0.5">{s.step_order}.</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium text-gray-800">{s.title}</span>
                        {s.is_required && <span className="text-xs bg-orange-100 text-orange-700 px-2 py-0.5 rounded">Bắt buộc</span>}
                      </div>
                      {s.description && <p className="text-xs text-gray-500 mt-0.5">{s.description}</p>}
                      <p className="text-xs text-gray-400 mt-0.5">
                        {phaseLabel[s.phase]} · {s.owner_role ? ROLE_LABEL[s.owner_role] : 'Chưa rõ vai trò'} ·{' '}
                        {s.due_hours != null ? `trong ${s.due_hours} giờ` : 'không đặt hạn'}
                        {s.reference && <span className="ml-2 px-1.5 py-0.5 rounded bg-gray-100 text-gray-500">{s.reference}</span>}
                      </p>
                    </div>
                  </li>
                ))}
              </ol>
              {open.source && <p className="text-xs text-gray-400">Tham chiếu: {open.source}</p>}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
