# Cơ sở dữ liệu (phiên bản incident-first)

Luồng: tạo sự cố, upload file luồng mạng/email vào sự cố, mô hình phân loại từng dòng, dòng vượt ngưỡng và thuộc lớp nguy hiểm sinh cảnh báo gắn vào sự cố, chuyên viên xác minh.

## Các bảng

| Bảng | Vai trò | Ghi chú |
|---|---|---|
| `users` | Tài khoản chuyên viên | Một vai trò (`analyst`), không khóa tài khoản sau đăng nhập sai |
| `attack_types` | Danh mục loại tấn công của **sự cố** | Người dùng chọn trên form |
| `incidents` | Sự cố | `code` duy nhất dạng `INC-2026-0001`; trạng thái `new, in_progress, resolved, closed, cancelled` |
| `incident_status_history` | Lịch sử chuyển trạng thái | Có lý do (bắt buộc khi hủy hoặc mở lại) |
| `uploads` | File đã upload | Hash SHA-256, số dòng, tiến độ, trạng thái, phiên bản mô hình, ngưỡng và lớp nguy hiểm đã áp dụng, phân bố nhãn, confidence trung bình |
| `alerts` | Cảnh báo | `incident_id` cho phép rỗng (đã gỡ khỏi sự cố); `UNIQUE(upload_id,row_index)`; `row_data` giữ nội dung dòng gốc |
| `alert_move_history` | Lịch sử gỡ/chuyển cảnh báo | `to_incident_id` rỗng nghĩa là gỡ |
| `labels` | Nhãn **đầu ra của mô hình**, kèm `is_dangerous` | Khác với `attack_types`; nhãn mới từ dịch vụ AI tự được thêm |
| `models` | Mô hình đang dùng | Đồng bộ từ dịch vụ AI (`POST /models/sync`); lưu cả danh sách cột đầu vào |
| `settings` | Cấu hình | `threshold_network`, `threshold_email`, `max_upload_mb`, `max_rows`, `batch_size` |

## Quy ước

- `alerts.row_index`: số thứ tự dòng dữ liệu trong file gốc, tính từ 1 (không tính dòng tiêu đề; với file CSV, dòng trong trình soạn thảo là `row_index + 1`; với JSON là vị trí trong mảng).
- `confidence`: xác suất của nhãn được dự đoán (0 đến 1). Cảnh báo chỉ sinh khi nhãn nguy hiểm **và** `confidence >= ngưỡng`.
- Sinh cảnh báo nguyên tử: kết quả của các lô được gom trong bộ nhớ, chỉ ghi vào `alerts` bằng một giao dịch khi cả file xử lý xong. File lỗi để lại `uploads.status = failed` và không có cảnh báo nào.
- Chống trùng: cùng `file_hash` trong cùng sự cố bị chặn (trừ bản đã lỗi). Cùng file ở sự cố khác vẫn nhận kèm cảnh báo.
- Xóa sự cố chỉ khi không có cảnh báo nào thuộc về nó hoặc truy vết về file của nó; nếu không thì dùng Hủy/Đóng.
- Thời gian lưu theo UTC, không kèm múi giờ.
- `schema_mssql.sql` sinh từ model, chỉ để tham khảo; ứng dụng tự tạo bảng khi khởi động. Dùng **một database mới** (ví dụ `thesis_incident_v2`), vì tên các bảng `users`, `incidents`, `alerts` trùng bản cũ nhưng khác cấu trúc.
