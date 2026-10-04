export default function LoadingSpinner({ text = 'Đang tải...' }) {
  return (
    <div className="flex items-center justify-center py-12">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mr-3"/>
      <span className="text-gray-500">{text}</span>
    </div>
  )
}