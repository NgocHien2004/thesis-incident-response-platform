import { num } from '../i18n'

// Phân bố nhãn của một file: thanh ngang theo số mẫu (có cả nhãn bình thường như BENIGN)
export default function LabelBars({ dist }) {
  const entries = Object.entries(dist || {}).sort((a, b) => b[1] - a[1])
  const total = entries.reduce((s, [, n]) => s + n, 0)
  if (!total) return null
  return (
    <div className="space-y-1">
      {entries.map(([label, n]) => (
        <div key={label} className="flex items-center gap-2 text-xs">
          <span className="w-40 truncate text-gray-700" title={label}>{label}</span>
          <div className="flex-1 h-2 bg-gray-100 rounded"><div className="h-2 bg-primary-500 rounded" style={{ width: `${(n / total) * 100}%` }} /></div>
          <span className="w-24 text-right text-gray-600">{num(n)} ({((n / total) * 100).toFixed(1)}%)</span>
        </div>
      ))}
    </div>
  )
}