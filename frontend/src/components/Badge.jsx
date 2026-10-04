const colors = {
  critical: 'bg-red-100 text-red-700 border border-red-200',
  high:     'bg-orange-100 text-orange-700 border border-orange-200',
  medium:   'bg-yellow-100 text-yellow-700 border border-yellow-200',
  low:      'bg-blue-100 text-blue-700 border border-blue-200',
  info:     'bg-gray-100 text-gray-600 border border-gray-200',
  open:         'bg-blue-100 text-blue-700',
  investigating:'bg-purple-100 text-purple-700',
  contained:    'bg-yellow-100 text-yellow-700',
  recovering:   'bg-teal-100 text-teal-700',
  closed:       'bg-green-100 text-green-700',
  new:          'bg-gray-100 text-gray-600',
  triaged:      'bg-blue-100 text-blue-700',
  escalated:    'bg-orange-100 text-orange-700',
  false_positive:'bg-gray-100 text-gray-500 line-through',
  proposed:  'bg-yellow-100 text-yellow-700',
  approved:  'bg-green-100 text-green-700',
  rejected:  'bg-red-100 text-red-700',
  executed:  'bg-blue-100 text-blue-700',
}

export default function Badge({ label, type }) {
  const cls = colors[type] || colors[label?.toLowerCase()] || 'bg-gray-100 text-gray-600'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {label}
    </span>
  )
}