import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getDashboard, getSLA } from '../api/dashboard'
import LoadingSpinner from '../components/LoadingSpinner'
import Badge from '../components/Badge'

function MetricCard({ label, value, unit, color, sub }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <div className="text-xs text-gray-500 font-medium mb-1">{label}</div>
      <div className={`text-2xl font-bold ${color || 'text-gray-900'}`}>
        {value ?? <span className="text-gray-300 text-lg">—</span>}
        {value != null && unit && <span className="text-sm font-normal text-gray-400 ml-1">{unit}</span>}
      </div>
      {sub && <div className="text-xs text-gray-400 mt-1">{sub}</div>}
    </div>
  )
}

function StatusBar({ label, count, total, color }) {
  const pct = total > 0 ? Math.round(count / total * 100) : 0
  return (
    <div className="mb-3">
      <div className="flex justify-between text-xs mb-1">
        <span className="text-gray-600">{label}</span>
        <span className="text-gray-500">{count} ({pct}%)</span>
      </div>
      <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [sla, setSla] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([getDashboard(), getSLA()])
      .then(([d, s]) => {
        setData(d.data)
        setSla(s.data)
      })
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <LoadingSpinner />

  const { incidents, metrics, alerts } = data || {}
  const total = incidents?.total || 0

  const severityColors = {
    critical: 'bg-red-500',
    high:     'bg-orange-400',
    medium:   'bg-yellow-400',
    low:      'bg-blue-400',
  }

  const statusColors = {
    open:          'bg-blue-500',
    investigating: 'bg-purple-500',
    contained:     'bg-yellow-500',
    recovering:    'bg-teal-500',
    closed:        'bg-green-500',
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-lg font-semibold text-gray-900">Dashboard</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          Cập nhật lúc {new Date(data?.generated_at).toLocaleString('vi-VN')}
        </p>
      </div>

      {/* 6 chỉ số chính */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <MetricCard
          label="MTTD"
          value={metrics?.mttd_minutes != null ? Math.abs(metrics.mttd_minutes) : null}
          unit="phút"
          color="text-blue-600"
          sub="Thời gian phát hiện TB"
        />
        <MetricCard
          label="MTTA"
          value={metrics?.mtta_minutes != null ? Math.abs(metrics.mtta_minutes) : null}
          unit="phút"
          color="text-purple-600"
          sub="Thời gian phản ứng TB"
        />
        <MetricCard
          label="MTTR"
          value={metrics?.mttr_minutes != null ? Math.round(metrics.mttr_minutes) : null}
          unit="phút"
          color="text-green-600"
          sub="Thời gian xử lý TB"
        />
        <MetricCard
          label="Vụ đang mở"
          value={incidents?.open}
          color={incidents?.open > 0 ? 'text-red-600' : 'text-green-600'}
          sub="incidents chưa đóng"
        />
        <MetricCard
          label="SLA vi phạm"
          value={metrics?.sla_breached_alerts}
          color={metrics?.sla_breached_alerts > 0 ? 'text-red-600' : 'text-green-600'}
          sub="cảnh báo quá hạn"
        />
        <MetricCard
          label="Action items"
          value={metrics?.action_item_completion_pct != null
            ? `${metrics.action_item_completion_pct}%`
            : null}
          color="text-teal-600"
          sub="hoàn thành postmortem"
        />
      </div>

      {/* Row 2 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">

        {/* Incidents theo trạng thái */}
        <div className="bg-white rounded-lg border border-gray-200 p-5">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-sm font-semibold text-gray-800">Incidents theo trạng thái</h3>
            <span className="text-xs text-gray-400">{total} tổng</span>
          </div>
          {Object.entries(incidents?.by_status || {}).map(([status, count]) => (
            <StatusBar
              key={status}
              label={status}
              count={count}
              total={total}
              color={statusColors[status] || 'bg-gray-400'}
            />
          ))}
          <Link to="/incidents" className="text-xs text-primary-600 hover:underline mt-2 block">
            Xem tất cả →
          </Link>
        </div>

        {/* Incidents mở theo mức độ */}
        <div className="bg-white rounded-lg border border-gray-200 p-5">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-sm font-semibold text-gray-800">Incidents mở theo mức độ</h3>
            <span className="text-xs text-gray-400">{incidents?.open} mở</span>
          </div>
          {Object.entries(incidents?.open_by_severity || {}).map(([sev, count]) => (
            <StatusBar
              key={sev}
              label={sev}
              count={count}
              total={incidents?.open || 1}
              color={severityColors[sev] || 'bg-gray-400'}
            />
          ))}
        </div>

        {/* Alerts theo trạng thái */}
        <div className="bg-white rounded-lg border border-gray-200 p-5">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-sm font-semibold text-gray-800">Cảnh báo</h3>
            <span className="text-xs text-gray-400">{alerts?.total} tổng</span>
          </div>
          {Object.entries(alerts?.by_status || {}).map(([status, count]) => (
            <StatusBar
              key={status}
              label={status}
              count={count}
              total={alerts?.total || 1}
              color="bg-indigo-400"
            />
          ))}
          <Link to="/alerts" className="text-xs text-primary-600 hover:underline mt-2 block">
            Xem tất cả →
          </Link>
        </div>
      </div>

      {/* SLA breached alerts */}
      {sla.length > 0 && (
        <div className="bg-white rounded-lg border border-red-200 p-5">
          <h3 className="text-sm font-semibold text-red-700 mb-3">
            ⚠️ Cảnh báo vi phạm SLA ({sla.length})
          </h3>
          <div className="space-y-2">
            {sla.slice(0, 5).map(item => (
              <div key={item.alert_id} className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <Badge label={item.severity} type={item.severity} />
                  <Link
                    to={`/alerts/${item.alert_id}`}
                    className="text-gray-700 hover:text-primary-600 hover:underline"
                  >
                    {item.title}
                  </Link>
                </div>
                <div className="flex items-center gap-2">
                  <Badge
                    label={item.status === 'breached' ? 'Quá hạn' : 'Sắp hết hạn'}
                    type={item.status === 'breached' ? 'critical' : 'warning'}
                  />
                  <span className="text-xs text-gray-400">
                    {item.remaining_minutes < 0
                      ? `${Math.abs(Math.round(item.remaining_minutes))} phút trước`
                      : `còn ${Math.round(item.remaining_minutes)} phút`}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}