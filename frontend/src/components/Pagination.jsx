import { useI18n, num } from '../i18n'

export default function Pagination({ page, pages, total, onChange }) {
  const { t } = useI18n()
  if (!total) return null
  return (
    <div className="flex items-center justify-between px-1 py-3 text-sm text-gray-600">
      <span>{t('Tổng {n} bản ghi', { n: num(total) })}</span>
      <div className="flex items-center gap-2">
        <button
          disabled={page <= 1}
          onClick={() => onChange(page - 1)}
          className="px-3 py-1 border rounded disabled:opacity-40 hover:bg-gray-100"
        >
          {t('← Trước')}
        </button>
        <span>{t('Trang {page} / {pages}', { page, pages: Math.max(pages, 1) })}</span>
        <button
          disabled={page >= pages}
          onClick={() => onChange(page + 1)}
          className="px-3 py-1 border rounded disabled:opacity-40 hover:bg-gray-100"
        >
          {t('Sau →')}
        </button>
      </div>
    </div>
  )
}
