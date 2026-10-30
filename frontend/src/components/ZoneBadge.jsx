const ZONES = {
  urgent:     { label: 'Khẩn',         cls: 'bg-red-100 text-red-700' },
  review:     { label: 'Cần xem',      cls: 'bg-yellow-100 text-yellow-800' },
  auto_close: { label: 'Đề xuất đóng', cls: 'bg-gray-100 text-gray-600' },
}

export const ZONE_OPTIONS = [['', 'Mọi vùng'], ['urgent', 'Khẩn'], ['review', 'Cần xem'], ['auto_close', 'Đề xuất đóng']]

export default function ZoneBadge({ zone, score }) {
  const z = ZONES[zone]
  if (!z) return <span className="text-xs text-gray-300">—</span>
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`text-xs px-2 py-0.5 rounded font-medium ${z.cls}`}>{z.label}</span>
      {score != null && <span className="text-xs text-gray-500 tabular-nums">{score}</span>}
    </span>
  )
}
