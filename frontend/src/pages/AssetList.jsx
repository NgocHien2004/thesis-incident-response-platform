import { useEffect, useMemo, useState } from 'react'
import { getAssets, createAsset, updateAsset, deleteAsset } from '../api/assets'
import Badge from '../components/Badge'
import Modal from '../components/Modal'
import LoadingSpinner from '../components/LoadingSpinner'
import toast from 'react-hot-toast'
import { useAuth } from '../context/AuthContext'

const ASSET_TYPES = [
  { value: 'server',      label: 'Máy chủ' },
  { value: 'application', label: 'Ứng dụng' },
  { value: 'account',     label: 'Tài khoản' },
  { value: 'network',     label: 'Thiết bị mạng' },
  { value: 'other',       label: 'Khác' },
]
const CRITICALITIES = [
  { value: 'critical', label: 'Rất quan trọng' },
  { value: 'high',     label: 'Cao' },
  { value: 'medium',   label: 'Trung bình' },
  { value: 'low',      label: 'Thấp' },
]
const typeLabel = (v) => ASSET_TYPES.find(t => t.value === v)?.label || v
const critLabel = (v) => CRITICALITIES.find(c => c.value === v)?.label || v
const critOrder = { critical: 0, high: 1, medium: 2, low: 3 }

const EMPTY_FORM = {
  name: '', asset_type: 'server', criticality: 'medium', owner: '',
  hostname: '', ip_address: '', description: '', data_processed: '', dependencies: '',
}

// Lấy thông báo lỗi dễ đọc từ response của FastAPI (detail có thể là string hoặc mảng 422)
const errMsg = (err, fallback) => {
  const d = err.response?.data?.detail
  if (typeof d === 'string') return d
  if (Array.isArray(d) && d.length) return d.map(x => x.msg).join('; ')
  if (err.response?.status === 403) return 'Bạn không có quyền thực hiện thao tác này'
  return fallback
}

const inputCls =
  'w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary-400'

export default function AssetList() {
  const { user } = useAuth()
  const [assets, setAssets]     = useState([])
  const [loading, setLoading]   = useState(true)
  const [search, setSearch]     = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [critFilter, setCritFilter] = useState('')

  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing]   = useState(null)   // asset đang sửa, null = tạo mới
  const [form, setForm]         = useState(EMPTY_FORM)
  const [saving, setSaving]     = useState(false)

  const [toDelete, setToDelete] = useState(null)
  const [deleting, setDeleting] = useState(false)
  const [detail, setDetail]     = useState(null)

  // Phân quyền khớp với backend: tạo/sửa = IT + Analyst, xóa = Analyst
  const canWrite  = ['analyst_soc', 'it_helpdesk'].includes(user?.role)
  const canDelete = user?.role === 'analyst_soc'

  const load = () => {
    setLoading(true)
    getAssets()
      .then(r => setAssets(r.data))
      .catch(err => toast.error(errMsg(err, 'Không tải được danh sách tài sản')))
      .finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    return assets
      .filter(a => !typeFilter || a.asset_type === typeFilter)
      .filter(a => !critFilter || a.criticality === critFilter)
      .filter(a => !q || [a.name, a.owner, a.hostname, a.ip_address]
        .some(v => v && v.toLowerCase().includes(q)))
      .sort((a, b) =>
        (critOrder[a.criticality] ?? 9) - (critOrder[b.criticality] ?? 9) ||
        a.name.localeCompare(b.name, 'vi'))
  }, [assets, search, typeFilter, critFilter])

  const counts = useMemo(() => {
    const c = { critical: 0, high: 0, medium: 0, low: 0 }
    assets.forEach(a => { if (c[a.criticality] !== undefined) c[a.criticality]++ })
    return c
  }, [assets])

  const openCreate = () => {
    setEditing(null)
    setForm(EMPTY_FORM)
    setShowForm(true)
  }

  const openEdit = (a) => {
    setEditing(a)
    setForm({
      name: a.name || '', asset_type: a.asset_type, criticality: a.criticality,
      owner: a.owner || '', hostname: a.hostname || '', ip_address: a.ip_address || '',
      description: a.description || '', data_processed: a.data_processed || '',
      dependencies: a.dependencies || '',
    })
    setDetail(null)
    setShowForm(true)
  }

  const closeForm = () => { setShowForm(false); setEditing(null) }

  const handleSave = async (e) => {
    e.preventDefault()
    setSaving(true)
    // Chuỗi rỗng -> null để backend không lưu "" cho các trường tùy chọn
    const payload = Object.fromEntries(
      Object.entries(form).map(([k, v]) => [k, typeof v === 'string' && v.trim() === '' ? null : v])
    )
    try {
      if (editing) {
        await updateAsset(editing.id, payload)
        toast.success('Đã cập nhật tài sản')
      } else {
        await createAsset(payload)
        toast.success('Đã thêm tài sản')
      }
      closeForm()
      load()
    } catch (err) {
      toast.error(errMsg(err, editing ? 'Cập nhật thất bại' : 'Thêm tài sản thất bại'))
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    setDeleting(true)
    try {
      await deleteAsset(toDelete.id)
      toast.success('Đã xóa tài sản')
      setToDelete(null)
      load()
    } catch (err) {
      // Backend có thể từ chối nếu tài sản đang được alert/incident tham chiếu
      toast.error(errMsg(err, 'Không thể xóa tài sản này (có thể đang được tham chiếu)'))
    } finally {
      setDeleting(false)
    }
  }

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  return (
    <div className="p-6 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-gray-900">Tài sản</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {filtered.length}/{assets.length} tài sản
            {assets.length > 0 && (
              <span className="ml-2 text-xs text-gray-400">
                · {counts.critical} rất quan trọng · {counts.high} cao
              </span>
            )}
          </p>
        </div>
        {canWrite && (
          <button
            onClick={openCreate}
            className="bg-primary-600 hover:bg-primary-700 text-white text-sm px-4 py-2 rounded-lg transition-colors"
          >
            + Thêm tài sản
          </button>
        )}
      </div>

      {/* Bộ lọc */}
      <div className="flex gap-2 flex-wrap items-center">
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Tìm theo tên, chủ sở hữu, hostname, IP..."
          className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm w-72 focus:outline-none focus:border-primary-400"
        />
        <select
          value={typeFilter}
          onChange={e => setTypeFilter(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:border-primary-400"
        >
          <option value="">Mọi loại</option>
          {ASSET_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
        </select>
        <select
          value={critFilter}
          onChange={e => setCritFilter(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:border-primary-400"
        >
          <option value="">Mọi mức quan trọng</option>
          {CRITICALITIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
        </select>
        {(search || typeFilter || critFilter) && (
          <button
            onClick={() => { setSearch(''); setTypeFilter(''); setCritFilter('') }}
            className="text-xs text-gray-500 hover:text-gray-700 underline"
          >
            Xóa bộ lọc
          </button>
        )}
      </div>

      {/* Bảng */}
      {loading ? <LoadingSpinner /> : (
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 w-10">#</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500">Tên tài sản</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500">Loại</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500">Mức quan trọng</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500">Chủ sở hữu</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500">IP / Hostname</th>
                {(canWrite || canDelete) && (
                  <th className="px-4 py-3 w-28" />
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-12 text-gray-400">
                    {assets.length === 0 ? 'Chưa có tài sản nào' : 'Không có tài sản khớp bộ lọc'}
                  </td>
                </tr>
              ) : filtered.map(a => (
                <tr key={a.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 text-gray-400 text-xs">{a.id}</td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => setDetail(a)}
                      className="text-gray-900 hover:text-primary-600 font-medium hover:underline text-left"
                    >
                      {a.name}
                    </button>
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-xs">{typeLabel(a.asset_type)}</td>
                  <td className="px-4 py-3">
                    <Badge label={critLabel(a.criticality)} type={a.criticality} />
                  </td>
                  <td className="px-4 py-3 text-gray-600 text-xs">{a.owner || '—'}</td>
                  <td className="px-4 py-3 text-gray-500 text-xs font-mono">
                    {a.ip_address || a.hostname || '—'}
                  </td>
                  {(canWrite || canDelete) && (
                    <td className="px-4 py-3 text-right whitespace-nowrap">
                      {canWrite && (
                        <button
                          onClick={() => openEdit(a)}
                          className="text-xs text-primary-600 hover:underline mr-3"
                        >
                          Sửa
                        </button>
                      )}
                      {canDelete && (
                        <button
                          onClick={() => setToDelete(a)}
                          className="text-xs text-red-500 hover:underline"
                        >
                          Xóa
                        </button>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Modal chi tiết */}
      <Modal open={!!detail} onClose={() => setDetail(null)} title={detail?.name || ''}>
        {detail && (
          <div className="space-y-3 text-sm">
            <div className="flex gap-2">
              <Badge label={critLabel(detail.criticality)} type={detail.criticality} />
              <span className="text-xs text-gray-500 self-center">{typeLabel(detail.asset_type)}</span>
            </div>
            {[
              ['Chủ sở hữu', detail.owner],
              ['Hostname', detail.hostname],
              ['Địa chỉ IP', detail.ip_address],
              ['Mô tả', detail.description],
              ['Dữ liệu xử lý', detail.data_processed],
              ['Phụ thuộc', detail.dependencies],
              ['Tạo lúc', detail.created_at && new Date(detail.created_at).toLocaleString('vi-VN')],
              ['Cập nhật', detail.updated_at && new Date(detail.updated_at).toLocaleString('vi-VN')],
            ].map(([label, value]) => (
              <div key={label} className="grid grid-cols-3 gap-2">
                <span className="text-xs text-gray-500">{label}</span>
                <span className="col-span-2 text-gray-800 whitespace-pre-wrap break-words">
                  {value || '—'}
                </span>
              </div>
            ))}
            {canWrite && (
              <div className="pt-2">
                <button
                  onClick={() => openEdit(detail)}
                  className="w-full border border-gray-200 text-gray-700 rounded-lg py-2 text-sm hover:bg-gray-50"
                >
                  Sửa tài sản
                </button>
              </div>
            )}
          </div>
        )}
      </Modal>

      {/* Modal tạo / sửa */}
      <Modal
        open={showForm}
        onClose={closeForm}
        title={editing ? `Sửa tài sản #${editing.id}` : 'Thêm tài sản mới'}
      >
        <form onSubmit={handleSave} className="space-y-4">
          <div>
            <label className="block text-xs text-gray-600 mb-1">Tên tài sản *</label>
            <input value={form.name} onChange={set('name')} className={inputCls} required />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-600 mb-1">Loại *</label>
              <select value={form.asset_type} onChange={set('asset_type')} className={inputCls}>
                {ASSET_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">Mức quan trọng *</label>
              <select value={form.criticality} onChange={set('criticality')} className={inputCls}>
                {CRITICALITIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">Chủ sở hữu</label>
            <input
              value={form.owner}
              onChange={set('owner')}
              className={inputCls}
              placeholder="Phòng Công nghệ thông tin"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-600 mb-1">Hostname</label>
              <input value={form.hostname} onChange={set('hostname')} className={inputCls} placeholder="mail-01" />
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">Địa chỉ IP</label>
              <input value={form.ip_address} onChange={set('ip_address')} className={inputCls} placeholder="10.0.0.10" />
            </div>
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">Mô tả</label>
            <textarea
              value={form.description}
              onChange={set('description')}
              rows={2}
              className={`${inputCls} resize-none`}
            />
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">Dữ liệu xử lý</label>
            <input
              value={form.data_processed}
              onChange={set('data_processed')}
              className={inputCls}
              placeholder="Thư điện tử nhân viên, dữ liệu khách hàng..."
            />
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">Phụ thuộc</label>
            <input
              value={form.dependencies}
              onChange={set('dependencies')}
              className={inputCls}
              placeholder="Active Directory, DNS..."
            />
          </div>
          <div className="flex gap-2 pt-2">
            <button
              type="button"
              onClick={closeForm}
              className="flex-1 border border-gray-200 text-gray-600 rounded-lg py-2 text-sm hover:bg-gray-50"
            >
              Hủy
            </button>
            <button
              type="submit"
              disabled={saving}
              className="flex-1 bg-primary-600 text-white rounded-lg py-2 text-sm hover:bg-primary-700 disabled:opacity-50"
            >
              {saving ? 'Đang lưu...' : editing ? 'Lưu thay đổi' : 'Thêm tài sản'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Modal xác nhận xóa */}
      <Modal open={!!toDelete} onClose={() => setToDelete(null)} title="Xóa tài sản">
        <div className="space-y-4">
          <p className="text-sm text-gray-700">
            Bạn có chắc muốn xóa tài sản <strong>{toDelete?.name}</strong>? Thao tác này không thể hoàn tác.
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => setToDelete(null)}
              className="flex-1 border border-gray-200 text-gray-600 rounded-lg py-2 text-sm hover:bg-gray-50"
            >
              Hủy
            </button>
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="flex-1 bg-red-600 text-white rounded-lg py-2 text-sm hover:bg-red-700 disabled:opacity-50"
            >
              {deleting ? 'Đang xóa...' : 'Xóa'}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  )
}