export default function Card({ title, children, action }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
      {title && (
        <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100">
          <h3 className="text-sm font-semibold text-gray-800">{title}</h3>
          {action}
        </div>
      )}
      <div className="p-5">{children}</div>
    </div>
  )
}