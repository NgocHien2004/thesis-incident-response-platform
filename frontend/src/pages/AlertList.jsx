import AlertsTable from '../components/AlertsTable'

export default function AlertList() {
  return (
    <div className="p-6">
      <h1 className="text-xl font-bold text-gray-900 mb-1">Cảnh báo</h1>
      <p className="text-sm text-gray-500 mb-4">
        Toàn bộ cảnh báo từ các file đã upload. Chọn “Chưa gắn sự cố” để xem các cảnh báo đã gỡ và gắn lại vào một sự cố.
      </p>
      <AlertsTable />
    </div>
  )
}
