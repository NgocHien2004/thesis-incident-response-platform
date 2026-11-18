import { useI18n } from '../i18n'

export default function LoadingSpinner({ text = 'Đang tải...' }) {
  const { t } = useI18n()
  return (
    <div className="flex items-center justify-center py-12">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mr-3"/>
      <span className="text-gray-500">{t(text)}</span>
    </div>
  )
}
