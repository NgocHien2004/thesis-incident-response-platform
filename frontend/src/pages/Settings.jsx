import { useCallback, useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { getSettings, updateSetting, getLabels, updateLabel, getModels, syncModels, getAiHealth } from '../api'
import Card from '../components/Card'
import LoadingSpinner from '../components/LoadingSpinner'
import { useI18n } from '../i18n'
import { DATA_TYPES, errMsg } from '../utils/format'

const SETTING_NAMES = {
  threshold_network: 'Ngưỡng confidence, luồng mạng',
  threshold_email:   'Ngưỡng confidence, email',
  max_upload_mb:     'Kích thước file tối đa (MB)',
  max_rows:          'Số dòng tối đa mỗi file',
  batch_size:        'Số dòng mỗi lô gửi cho mô hình',
}

function SettingRow({ s, onSaved }) {
  const { t } = useI18n()
  const [value, setValue] = useState(s.value)
  const [busy, setBusy] = useState(false)
  useEffect(() => setValue(s.value), [s.value])

  const save = async () => {
    setBusy(true)
    try {
      await updateSetting(s.key, value)
      toast.success(t('Đã lưu'))
      onSaved()
    } catch (err) {
      toast.error(errMsg(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-3 py-2 border-b last:border-0">
      <div className="flex-1 min-w-48">
        <div className="text-sm font-medium text-gray-800">{SETTING_NAMES[s.key] ? t(SETTING_NAMES[s.key]) : s.key}</div>
        <div className="text-xs text-gray-500">{t(s.description)}</div>
      </div>
      <input value={value} onChange={e => setValue(e.target.value)} className="w-28 border rounded-lg px-3 py-1.5 text-sm" />
      <button disabled={busy || value === s.value} onClick={save}
        className="px-3 py-1.5 text-sm bg-primary-600 hover:bg-primary-700 text-white rounded-lg disabled:opacity-40">{t('Lưu')}</button>
    </div>
  )
}

export default function Settings() {
  const { t } = useI18n()
  const [settings, setSettings] = useState(null)
  const [labels, setLabels] = useState([])
  const [models, setModels] = useState([])
  const [syncing, setSyncing] = useState(false)
  const [aiOnline, setAiOnline] = useState(null) // null: chưa biết

  const load = useCallback(async () => {
    try {
      const [s, l, m, h] = await Promise.all([
        getSettings(), getLabels(), getModels(),
        getAiHealth().then(r => r.data.online).catch(() => null),
      ])
      setSettings(s.data); setLabels(l.data); setModels(m.data); setAiOnline(h)
    } catch (err) {
      toast.error(errMsg(err))
    }
  }, [])

  useEffect(() => { load() }, [load])

  const toggleLabel = async (l, field) => {
    try {
      await updateLabel(l.id, { [field]: !l[field] })
      setLabels(labels.map(x => (x.id === l.id ? { ...x, [field]: !l[field] } : x)))
    } catch (err) {
      toast.error(errMsg(err))
    }
  }

  const sync = async () => {
    setSyncing(true)
    try {
      await syncModels()
      toast.success(t('Đã đồng bộ mô hình từ dịch vụ AI'))
      load()
    } catch (err) {
      if (err.response?.status === 503) setAiOnline(false)
      toast.error(errMsg(err))
    } finally {
      setSyncing(false)
    }
  }

  if (!settings) return <LoadingSpinner />

  // Chỉ hiện mô hình đang dùng; bản cũ (kể cả mô hình giả của bộ test) vẫn nằm trong CSDL vì các file đã upload tham chiếu tới
  const activeModels = models.filter(m => m.is_active)

  return (
    <div className="p-6 space-y-6 max-w-5xl">
      <h1 className="text-xl font-bold text-gray-900">{t('Cấu hình')}</h1>

      <Card title={t('Ngưỡng sinh cảnh báo và giới hạn upload')}>
        <p className="text-xs text-gray-500 mb-2">
          {t('Cảnh báo chỉ được sinh khi nhãn dự đoán thuộc lớp nguy hiểm và confidence đạt ngưỡng. Thay đổi chỉ áp dụng cho file upload sau này; mỗi file lưu lại ngưỡng đã dùng.')}
        </p>
        {settings.map(s => <SettingRow key={s.key} s={s} onSaved={load} />)}
      </Card>

      <Card title={t('Lớp nguy hiểm (nhãn đầu ra của mô hình)')}>
        <p className="text-xs text-gray-500 mb-3">{t('Bỏ chọn “Nguy hiểm” cho những nhãn không cần sinh cảnh báo (ví dụ BENIGN, NON_SPAM).')}</p>
        {Object.keys(DATA_TYPES).map(dt => (
          <div key={dt} className="mb-4 last:mb-0">
            <div className="text-sm font-medium text-gray-800 mb-1">{t(DATA_TYPES[dt])}</div>
            <div className="border rounded-lg divide-y">
              {labels.filter(l => l.data_type === dt).map(l => (
                <div key={l.id} className="flex items-center gap-4 px-3 py-1.5 text-sm">
                  <span className="flex-1">{l.code} <span className="text-gray-400 text-xs">{l.name_vi !== l.code ? `· ${t(l.name_vi)}` : ''}</span></span>
                  <label className="flex items-center gap-1"><input type="checkbox" checked={l.is_dangerous} onChange={() => toggleLabel(l, 'is_dangerous')} /> {t('Nguy hiểm')}</label>
                  <label className="flex items-center gap-1 text-gray-500"><input type="checkbox" checked={l.is_active} onChange={() => toggleLabel(l, 'is_active')} /> {t('Đang dùng')}</label>
                </div>
              ))}
            </div>
          </div>
        ))}
      </Card>

      <Card title={t('Mô hình')} action={
        <button onClick={sync} disabled={syncing} className="px-3 py-1.5 text-sm border rounded-lg hover:bg-gray-50 disabled:opacity-50">
          {syncing ? t('Đang đồng bộ...') : t('Đồng bộ từ dịch vụ AI')}
        </button>
      }>
        {aiOnline === false && (
          <div className="text-sm text-yellow-800 bg-yellow-50 border border-yellow-200 rounded-lg px-3 py-2 mb-3">
            {t('Dịch vụ AI không phản hồi. Vui lòng kiểm tra lại.')}
          </div>
        )}
        {activeModels.length === 0 ? <div className="text-sm text-gray-500">{t('Chưa có mô hình. Bấm “Đồng bộ” khi dịch vụ AI đang chạy.')}</div> : (
          <div className="overflow-x-auto"><table className="w-full text-sm">
            <thead className="text-left text-gray-600"><tr><th className="py-1">{t('Tên')}</th><th>{t('Phiên bản')}</th><th>{t('Nguồn')}</th><th>{t('Trạng thái')}</th></tr></thead>
            <tbody>
              {activeModels.map(m => (
                <tr key={m.id} className="border-t">
                  <td className="py-1.5">{m.name}</td>
                  <td>{m.version}</td>
                  <td>{t(DATA_TYPES[m.task_type])}</td>
                  <td>{!m.is_active ? <span className="text-gray-400">{t('Không dùng')}</span>
                    : aiOnline === false ? <span className="text-red-600" title={t('Dịch vụ AI không phản hồi')}>{t('Không khả dụng')}</span>
                    : <span className="text-green-600">{t('Đang dùng')}</span>}</td>
                </tr>
              ))}
            </tbody>
          </table></div>
        )}
      </Card>
    </div>
  )
}
