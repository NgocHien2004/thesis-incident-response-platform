import AlertsTable from '../components/AlertsTable'
import { useI18n } from '../i18n'

export default function AlertList() {
  const { t } = useI18n()
  return (
    <div className="p-6">
      <h1 className="text-xl font-bold text-gray-900 mb-1">{t('Cảnh báo')}</h1>
      <p className="text-sm text-gray-500 mb-4">
        {t('Toàn bộ cảnh báo từ các file đã upload.')}
      </p>
      <AlertsTable />
    </div>
  )
}