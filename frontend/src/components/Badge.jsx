import { useI18n } from '../i18n'

export default function Badge({ info, label }) {
  const { t } = useI18n()
  const cls = info?.cls || 'bg-gray-100 text-gray-600'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium whitespace-nowrap ${cls}`}>
      {t(info?.label || label, { ctx: info?.ctx })}
    </span>
  )
}
