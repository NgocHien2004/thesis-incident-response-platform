export default function Pagination({ page, pages, total, onChange }) {
  if (!total) return null
  return (
    <div className="flex items-center justify-between px-1 py-3 text-sm text-gray-600">
      <span>Tổng {total.toLocaleString('vi-VN')} bản ghi</span>
      <div className="flex items-center gap-2">
        <button
          disabled={page <= 1}
          onClick={() => onChange(page - 1)}
          className="px-3 py-1 border rounded disabled:opacity-40 hover:bg-gray-100"
        >
          ← Trước
        </button>
        <span>Trang {page} / {Math.max(pages, 1)}</span>
        <button
          disabled={page >= pages}
          onClick={() => onChange(page + 1)}
          className="px-3 py-1 border rounded disabled:opacity-40 hover:bg-gray-100"
        >
          Sau →
        </button>
      </div>
    </div>
  )
}
