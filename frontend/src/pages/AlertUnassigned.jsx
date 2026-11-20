import { Link } from 'react-router-dom'
import AlertsTable from '../components/AlertsTable'
import { useI18n } from '../i18n'

// Cảnh báo đã gỡ khỏi sự cố (không còn thuộc sự cố nào), gom từ mọi file
export default function AlertUnassigned() {
  const { t } = useI18n()
  return (
    <div className="p-6">
      <Link to="/alerts" className="text-sm text-primary-600 hover:underline">{t('← Danh sách file')}</Link>
      <h1 className="text-xl font-bold text-gray-900 mt-2 mb-1">{t('Cảnh báo chưa gắn sự cố')}</h1>
      <p className="text-sm text-gray-500 mb-4">{t('Các cảnh báo đã gỡ khỏi sự cố, từ mọi file. Chuyển chúng vào một sự cố để xác minh.')}</p>
      <AlertsTable defaultScope="unassigned" />
    </div>
  )
}