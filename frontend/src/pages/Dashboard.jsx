import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import toast from 'react-hot-toast'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts'
import { getDashboard } from '../api'
import Card from '../components/Card'
import LoadingSpinner from '../components/LoadingSpinner'
import { useI18n } from '../i18n'
import { STATUS, VERIFICATION, errMsg, pct } from '../utils/format'

const PIE_COLORS = { unverified: '#9ca3af', verified: '#10b981', dismissed: '#f59e0b' }
const BAR_COLOR = '#6366f1'

function Stat({ label, value, to, cls = '' }) {
  const body = (
    <div className="bg-white border rounded-lg px-4 py-3 hover:shadow-sm transition-shadow">
      <div className="text-xs text-gray-500">{label}</div>
      <div className={`text-2xl font-bold ${cls}`}>{value}</div>
    </div>
  )
  return to ? <Link to={to}>{body}</Link> : body
}

export default function Dashboard() {
  const { t } = useI18n()
  const [d, setD] = useState(null)

  useEffect(() => {
    getDashboard().then(r => setD(r.data)).catch(err => toast.error(errMsg(err)))
  }, [])

  if (!d) return <LoadingSpinner />

  const verification = Object.entries(d.alerts_by_verification).map(([k, v]) => ({ key: k, name: t(VERIFICATION[k].label), value: v }))
  const attackTypes = d.incidents_by_attack_type.map(x => ({ ...x, name: t(x.name_vi) }))
  const decided = d.alerts_by_verification.verified + d.alerts_by_verification.dismissed

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-xl font-bold text-gray-900">{t('Tổng quan')}</h1>

      <div>
        <div className="text-sm font-medium text-gray-700 mb-2">{t('Sự cố theo trạng thái (tổng {n})', { n: d.incidents_total })}</div>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {Object.entries(d.incidents_by_status).map(([k, n]) => (
            <Stat key={k} label={t(STATUS[k].label)} value={n} to={`/incidents`} />
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card title={t('Sự cố theo loại tấn công')}>
          {attackTypes.length === 0 ? <div className="text-sm text-gray-500 py-8 text-center">{t('Chưa có dữ liệu')}</div> : (
            <ResponsiveContainer width="100%" height={Math.max(220, attackTypes.length * 36)}>
              <BarChart data={attackTypes} layout="vertical" margin={{ left: 20 }}>
                <XAxis type="number" allowDecimals={false} />
                <YAxis type="category" dataKey="name" width={150} tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="count" name={t('Số sự cố')} fill={BAR_COLOR} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>

        <Card title={t('Cảnh báo theo nhãn (tổng {n})', { n: d.alerts_total })}>
          {d.alerts_by_label.length === 0 ? <div className="text-sm text-gray-500 py-8 text-center">{t('Chưa có cảnh báo')}</div> : (
            <ResponsiveContainer width="100%" height={Math.max(220, d.alerts_by_label.length * 36)}>
              <BarChart data={d.alerts_by_label} layout="vertical" margin={{ left: 20 }}>
                <XAxis type="number" allowDecimals={false} />
                <YAxis type="category" dataKey="label" width={170} tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="count" name={t('Số cảnh báo')} fill="#ef4444" />
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>

        <Card title={t('Trạng thái xác minh cảnh báo')}>
          {d.alerts_total === 0 ? <div className="text-sm text-gray-500 py-8 text-center">{t('Chưa có cảnh báo')}</div> : (
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie data={verification} dataKey="value" nameKey="name" outerRadius={85} label={({ value }) => value}>
                  {verification.map(v => <Cell key={v.key} fill={PIE_COLORS[v.key]} />)}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          )}
        </Card>

        <Card title={t('Tỉ lệ bỏ qua (false positive)')}>
          <div className="py-4 text-center">
            <div className="text-4xl font-bold text-yellow-600">{pct(d.false_positive_rate)}</div>
            <div className="text-sm text-gray-600 mt-2">
              {t('= Bỏ qua / (Đã xác minh + Bỏ qua)')}<br />
              = {d.alerts_by_verification.dismissed} / {decided}
            </div>
            {d.false_positive_rate === null && <div className="text-xs text-gray-500 mt-2">{t('Chưa có cảnh báo nào được xác minh hoặc bỏ qua.')}</div>}
          </div>
          {d.alerts_unassigned > 0 && (
            <div className="text-sm bg-yellow-50 border border-yellow-200 rounded-lg px-3 py-2 mt-2">
              {t('Có {n} cảnh báo chưa gắn sự cố.', { n: d.alerts_unassigned })} <Link to="/alerts/unassigned" className="text-primary-600">{t('Xem')}</Link>
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}