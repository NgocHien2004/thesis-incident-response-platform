import { useState } from 'react'
import { Link } from 'react-router-dom'
import toast from 'react-hot-toast'
import Card from './Card'
import Badge from './Badge'
import ZoneBadge from './ZoneBadge'
import { scoreAlert, closeAlert, reopenAlert } from '../api/alerts'

const CRIT_LABEL = { critical: 'nghiêm trọng', high: 'cao', medium: 'trung bình', low: 'thấp' }

export default function ScorePanel({ alert, isAnalyst, canScore, onChanged }) {
  const [busy, setBusy] = useState(false)
  const m = alert.ml_result

  const run = async (fn, okMsg) => {
    setBusy(true)
    try {
      await fn()
      toast.success(okMsg)
      onChanged()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Thất bại')
    } finally { setBusy(false) }
  }

  const rescore = () => run(() => scoreAlert(alert.id), 'Đã chấm điểm')
  const close = () => {
    const note = prompt('Lý do đóng cảnh báo:', 'Theo đề xuất tự đóng của AI, đã rà soát')
    if (!note || !note.trim()) return
    run(() => closeAlert(alert.id, note), 'Đã đóng cảnh báo')
  }
  const reopen = () => {
    const note = prompt('Lý do mở lại cảnh báo:')
    if (!note || !note.trim()) return
    run(() => reopenAlert(alert.id, note), 'Đã mở lại cảnh báo')
  }

  const canClose = isAnalyst && alert.ml_zone === 'auto_close' && ['new', 'reviewing', 'triaged'].includes(alert.status) && !alert.incident_id
  const canReopen = isAnalyst && alert.status === 'closed'

  const actions = (
    <div className="flex gap-2">
      {canClose && (
        <button onClick={close} disabled={busy}
          className="text-xs px-3 py-1 bg-gray-100 text-gray-700 rounded hover:bg-gray-200 disabled:opacity-50">Đóng theo đề xuất</button>
      )}
      {canReopen && (
        <button onClick={reopen} disabled={busy}
          className="text-xs px-3 py-1 bg-yellow-100 text-yellow-800 rounded hover:bg-yellow-200 disabled:opacity-50">Mở lại</button>
      )}
      {canScore && (
        <button onClick={rescore} disabled={busy}
          className="text-xs px-3 py-1 bg-indigo-50 text-indigo-700 rounded border border-indigo-200 hover:bg-indigo-100 disabled:opacity-50">
          {m ? 'Chấm điểm lại' : 'Chấm điểm'}
        </button>
      )}
    </div>
  )

  if (!m) {
    return (
      <Card title="Điểm ưu tiên AI" action={actions}>
        <p className="text-sm text-gray-500">Cảnh báo này chưa được chấm điểm.</p>
      </Card>
    )
  }

  const maxScore = Math.max(...(m.top_features || []).map(f => f.score), 0.0001)
  const pct = (x) => `${Math.round(x * 1000) / 10}%`

  return (
    <Card title="Điểm ưu tiên AI" action={actions}>
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-4">
          <div className="text-3xl font-semibold text-gray-900 tabular-nums">{m.priority}<span className="text-sm text-gray-400"> / 100</span></div>
          <ZoneBadge zone={m.zone} />
          <span className="text-xs bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded">Do AI tạo, cần Analyst xác nhận</span>
        </div>
        <p className="text-sm text-gray-700">{m.zone_reason}</p>
        {m.ai_error && <p className="text-xs text-yellow-700 bg-yellow-50 rounded px-2 py-1">{m.ai_error}; điểm dùng xác suất suy từ mức độ khai báo.</p>}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
          <div className="border border-gray-100 rounded-lg p-3">
            <div className="text-xs text-gray-400 mb-1">Xác suất độc hại</div>
            <div className="font-medium text-gray-800">{pct(m.probability)}</div>
            <div className="text-xs text-gray-500 mt-1">
              {m.probability_source === 'rf'
                ? `Mô hình Random Forest (${m.model})`
                : `Suy từ mức độ khai báo (${m.components.declared_severity}); chưa có đặc trưng luồng mạng để dùng mô hình`}
            </div>
          </div>
          <div className="border border-gray-100 rounded-lg p-3">
            <div className="text-xs text-gray-400 mb-1">Tài sản bị ảnh hưởng</div>
            <div className="font-medium text-gray-800">
              {m.components.asset.name || 'Chưa xác định'}
            </div>
            <div className="text-xs text-gray-500 mt-1">
              {m.components.asset.criticality ? `Mức ${CRIT_LABEL[m.components.asset.criticality]}` : 'Tính như mức trung bình'}, hệ số {m.components.asset.weight}
            </div>
          </div>
          <div className="border border-gray-100 rounded-lg p-3">
            <div className="text-xs text-gray-400 mb-1">Độ tin cậy nguồn</div>
            <div className="font-medium text-gray-800">{m.components.source.name}</div>
            <div className="text-xs text-gray-500 mt-1">Hệ số {m.components.source.reliability}</div>
          </div>
        </div>
        <p className="text-xs text-gray-400">
          Điểm = 100 × xác suất × ({m.formula.base} + {m.formula.asset} × hệ số tài sản + {m.formula.source} × hệ số nguồn).
          Khẩn khi điểm từ {m.formula.urgent_priority}, hoặc xác suất từ {m.formula.urgent_probability} trên tài sản mức cao trở lên.
        </p>

        <div>
          <div className="text-xs font-semibold text-gray-500 mb-1">Luật an toàn để đề xuất tự đóng</div>
          <ul className="space-y-1">
            {m.rules.map(r => (
              <li key={r.rule} className="flex items-start gap-2 text-xs text-gray-600">
                <span className={r.passed ? 'text-green-600' : 'text-gray-300'}>{r.passed ? '✓' : '✗'}</span>
                <span>{r.rule}</span>
              </li>
            ))}
          </ul>
        </div>

        {m.top_features?.length > 0 && (
          <div>
            <div className="text-xs font-semibold text-gray-500 mb-1">Đặc trưng nổi bật của luồng (độ quan trọng × độ lệch chuẩn hóa)</div>
            <div className="space-y-1">
              {m.top_features.map(f => (
                <div key={f.name} className="flex items-center gap-2 text-xs">
                  <span className="w-48 truncate text-gray-700" title={f.name}>{f.name}</span>
                  <div className="flex-1 bg-gray-100 rounded h-2">
                    <div className="bg-indigo-400 h-2 rounded" style={{ width: `${Math.max(4, (f.score / maxScore) * 100)}%` }} />
                  </div>
                  <span className="w-24 text-right font-mono text-gray-500">{f.value}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {m.similar_alerts?.length > 0 && (
          <div>
            <div className="text-xs font-semibold text-gray-500 mb-1">Cảnh báo tương tự</div>
            <ul className="space-y-1">
              {m.similar_alerts.map(s => (
                <li key={s.id} className="flex flex-wrap items-center gap-2 text-xs">
                  <Link to={`/alerts/${s.id}`} className="text-primary-600 hover:underline">#{s.id} {s.title}</Link>
                  <span className="text-gray-400">{Math.round(s.similarity * 100)}%</span>
                  <Badge label={s.status} type={s.status} />
                  {s.same_group && <span className="text-gray-400">cùng nhóm</span>}
                  {s.incident_id && <Link to={`/incidents/${s.incident_id}`} className="text-purple-600 hover:underline">INC#{s.incident_id}</Link>}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </Card>
  )
}
