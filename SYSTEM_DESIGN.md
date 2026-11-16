# Thiết kế hệ thống

Hệ thống quản lý sự cố an ninh mạng tích hợp AI phân loại cảnh báo từ dữ liệu đa nguồn (luồng mạng và email), dành cho tổ chức vừa và nhỏ. Cấu trúc cơ sở dữ liệu ở `DATABASE.md`. Cập nhật 16/11/2026.

## 1. Tổng quan

### 1.1 Luồng nghiệp vụ

```
Tạo sự cố (Mới)
   ↓ upload file vào sự cố (nguồn: luồng mạng hoặc email)
Kiểm tra định dạng, cột, kích thước, trùng hash  → lỗi 4xx, không để lại bản ghi
   ↓ xử lý nền theo lô
Dịch vụ AI phân loại từng dòng → nhãn + confidence
   ↓ nhãn thuộc lớp nguy hiểm VÀ confidence ≥ ngưỡng
Cảnh báo, tự gắn vào sự cố  (một giao dịch cuối; lỗi → file "failed", 0 cảnh báo)
   ↓ chuyên viên xem dòng gốc
Đã xác minh / Bỏ qua / Chuyển sang sự cố khác / Gỡ khỏi sự cố
   ↓
Chuyển trạng thái sự cố: Mới → Đang xử lý → Đã xử lý → Đã đóng (hoặc Đã hủy)
   ↓
Dashboard (sự cố theo trạng thái và loại tấn công, cảnh báo theo nhãn, tỉ lệ bỏ qua)
```

### 1.2 Phạm vi

Trong phạm vi: một vai trò chuyên viên; quản lý sự cố và lịch sử trạng thái; upload CSV/JSON (luồng mạng, email) và `.eml`/`.zip` (chỉ email); phân loại theo lô; sinh, xác minh, chuyển, gỡ cảnh báo; cấu hình ngưỡng và lớp nguy hiểm; dashboard.

Ngoài phạm vi (không cài đặt): quản lý tài sản, bằng chứng và chain of custody, containment, recovery, thông báo, postmortem, playbook, SLA, nhật ký kiểm toán chuỗi băm, ánh xạ ATT&CK, chính sách ba vùng (tự đóng, xem, khẩn), phân quyền nhiều vai trò, nhập pcap thô và `.msg`. Đề tài 10 gốc có các phần này; phiên bản luận văn không làm. Giảng viên chỉ yêu cầu một ngưỡng confidence để sinh cảnh báo.

`.eml` và `.zip` là phần mở rộng ngoài danh sách yêu cầu của giảng viên (giảng viên chỉ nêu CSV/JSON).

### 1.3 Công nghệ

| Tầng | Công nghệ | Cổng |
|---|---|---|
| Frontend | React 19, Vite 8, Tailwind CSS 3, axios, recharts, react-hot-toast | 5173 |
| Backend | Python FastAPI, SQLAlchemy 2, pydantic | 8000 |
| Cơ sở dữ liệu | Microsoft SQL Server (ODBC Driver 17) | |
| Dịch vụ AI | FastAPI riêng (`ml/serve.py`), scikit-learn | 8001 |
| Mô hình | Random Forest nhiều lớp (luồng mạng), TF-IDF + Linear SVM hiệu chỉnh (email) | |
| Xác thực | JWT access token (mặc định 60 phút) + bcrypt | |

```
Trình duyệt ──HTTP──▶ Backend :8000 ──SQL──▶ SQL Server
   (React)               │   └── upload_store/ (file gốc đã upload)
                         └──HTTP──▶ Dịch vụ AI :8001 ──▶ models/*.pkl
```

Backend gọi dịch vụ AI qua `AI_SERVICE_URL` (mặc định `http://127.0.0.1:8001`). Dịch vụ AI chỉ nạp mô hình lúc khởi động, nên phải khởi động lại sau mỗi lần huấn luyện.

### 1.4 Cấu trúc thư mục chính

```
backend/   main.py, database.py, seed.py, app/{api,core,models,schemas,services}
frontend/  src/{pages,components,api,context,utils}
ml/        preprocess.py, train_multiclass.py, train_email.py, email_features.py,
           serve.py, make_network_samples.py, results/, models/, data/
tests/     test_incident_alert_flow.py, fake_ai_service.py, test_eml_parsing.py
```

## 2. Tài khoản và xác thực

Chỉ có một vai trò `analyst`; mọi tài khoản đăng nhập được đều có đầy đủ quyền.

- Mật khẩu băm bcrypt. Tên đăng nhập tối thiểu 3 ký tự, mật khẩu tối thiểu 6 ký tự.
- `POST /auth/login` trả `access_token` và `refresh_token`. **Chỉ access token được dùng**; hệ thống chưa có endpoint làm mới token. Khi token hết hạn (mặc định 60 phút, đổi bằng `ACCESS_TOKEN_EXPIRE_MINUTES`) hoặc gặp 401, frontend xóa phiên và chuyển về trang đăng nhập.
- `POST /auth/register`: tài khoản đầu tiên tạo tự do để khởi tạo hệ thống; sau đó phải đăng nhập mới cấp được tài khoản mới. `seed.py` tạo sẵn `analyst01` và `analyst02`.
- Không khóa tài khoản sau đăng nhập sai và không có nhật ký kiểm toán chuỗi băm (khác bản thiết kế đầu). Lịch sử thay đổi được lưu bằng `incident_status_history` và `alert_move_history`.
- `SECRET_KEY` đọc từ `backend/.env`; thiếu thì không ký được token.

## 3. Sự cố

### 3.1 Dữ liệu

Tiêu đề, mô tả, loại tấn công (`attack_types`), mức độ (`low, medium, high, critical`), thời gian xảy ra, nguồn (`ids_ips, email, endpoint, manual, other`), trạng thái, người tạo, các mốc `resolved_at`, `closed_at`. Mã sự cố dạng `INC-2026-0001`, duy nhất; khi tạo, nếu trùng mã do hai yêu cầu đồng thời thì thử lại tối đa 3 lần.

Lưu ý: "nguồn" của sự cố khác với "nguồn dữ liệu" của file upload (`network`/`email`).

### 3.2 Máy trạng thái

| Từ | Sang | Ghi chú |
|---|---|---|
| `new` (Mới) | `in_progress`, `cancelled` | Hủy bắt buộc lý do |
| `in_progress` (Đang xử lý) | `resolved`, `cancelled` | Hủy bắt buộc lý do |
| `resolved` (Đã xử lý) | `closed`, `in_progress`, `cancelled` | Mở lại và hủy bắt buộc lý do |
| `closed` (Đã đóng) | không | Trạng thái cuối |
| `cancelled` (Đã hủy) | không | Trạng thái cuối |

- Lý do tối thiểu 3 ký tự.
- Khi còn file đang xử lý (`pending`/`processing`), không chuyển sang `resolved`, `closed`, `cancelled` và không xóa sự cố (409); giao diện cũng ẩn các nút này.
- Sự cố đã đóng hoặc đã hủy không sửa được. Mỗi lần chuyển ghi một dòng `incident_status_history` kèm người đổi, thời điểm, lý do. Mở lại từ `resolved` xóa `resolved_at`.
- **Xóa:** chỉ khi không có cảnh báo nào thuộc sự cố và không có cảnh báo nào truy vết về file của sự cố (kể cả cảnh báo đã được chuyển đi nơi khác). Xóa thì xóa luôn file đã upload. Ngược lại dùng Hủy hoặc Đóng.

### 3.3 Danh sách và lọc

Phân trang (`page`, `page_size` ≤ 200), sắp xếp theo `id, code, title, severity, status, attack_type, occurred_at, created_at, updated_at` (mức độ sắp theo độ nghiêm trọng chứ không theo chữ cái), lọc theo `q` (mã hoặc tiêu đề), `status` (nhiều giá trị cách nhau bằng dấu phẩy), `attack_type`, `severity`, `date_from`, `date_to` (ngày cuối tính trọn ngày).

Với SQL Server, khi sắp xếp theo `id` không được thêm tiêu chí phụ `id` vào `ORDER BY` (cột lặp gây lỗi 169); mã đã xử lý riêng trường hợp này ở `incidents.py` và `alerts.py`.

## 4. Upload và xử lý

### 4.1 Định dạng chấp nhận

| Nguồn dữ liệu | Định dạng | Yêu cầu |
|---|---|---|
| Luồng mạng | `.csv`, `.json` | Đủ các cột đặc trưng CIC-IDS2017 của mô hình đang dùng (danh sách lấy từ bảng `models.feature_names`); cột thừa như `Label`, `Timestamp` bị bỏ qua |
| Email | `.csv`, `.json` | Đủ các cột `subject, body, sender, urls`; `has_html`, `attachments` tùy chọn |
| Email | `.eml` | Một thư là một dòng |
| Email | `.zip` | Chứa nhiều `.eml`, mỗi thư là một dòng |

`.eml` và `.zip` với nguồn luồng mạng bị từ chối (422).

### 4.2 Kiểm tra trước khi nhận

Toàn bộ file được quét một lần trước khi tạo bản ghi `uploads`; lỗi thì trả 4xx, xóa file tạm và không để lại gì:

1. Sự cố phải ở trạng thái Mới hoặc Đang xử lý (409).
2. Nguồn dữ liệu hợp lệ; đuôi file thuộc `.csv, .json, .eml, .zip` (422).
3. Kích thước tối đa `max_upload_mb` (413, kiểm tra khi đọc từng khối 1 MB, không cần đọc hết file); file rỗng bị từ chối.
4. Trùng hash SHA-256 với file không lỗi trong cùng sự cố → 409 nêu số upload bị trùng. Cùng file ở sự cố khác vẫn nhận kèm `warnings`. File đã lỗi (`failed`) không tính là trùng, nên upload lại được.
5. Phải có mô hình đang dùng cho nguồn đó; thiếu thì 503. Với luồng mạng, nếu mô hình chưa có danh sách cột thì tự đồng bộ từ dịch vụ AI.
6. Cấu trúc và giá trị: CSV/JSON phải UTF-8, số cột mỗi dòng khớp tiêu đề; đủ cột bắt buộc (báo rõ cột thiếu); ô luồng mạng phải là số (báo dòng và cột sai); `Infinity`/`NaN` quy về 0; hai cột trùng tên (`Fwd Header Length`) được đặt `.1`; số dòng không vượt `max_rows`; email phải có `subject` hoặc `body`.

Bước kiểm tra này chỉ dùng thông tin mô hình đã lưu trong cơ sở dữ liệu, không gọi dịch vụ AI; vì vậy upload vẫn được nhận khi dịch vụ AI tắt, và lỗi chỉ lộ ra ở bước xử lý nền (file chuyển `failed`).

### 4.3 Đọc thư `.eml` và `.zip`

- Tiêu đề giải mã RFC 2047; `sender` lấy địa chỉ trong `From`.
- Nội dung lấy từ phần văn bản thuần. Chỉ dùng phần HTML (đã bỏ thẻ, bỏ `script`/`style`) khi chữ HTML dài hơn 1,5 lần bản thuần, vì bản thuần nhiều khi chỉ là dòng giữ chỗ.
- URL gồm cả địa chỉ hiển thị trong nội dung và địa chỉ trong thuộc tính `href` (liên kết ẩn sau chữ hiển thị là dấu hiệu phishing hay gặp); tối đa 50.
- Tệp đính kèm chỉ ghi tên (tối đa 20), không đọc nội dung.
- ZIP: mỗi `.eml` là một dòng, xếp theo tên file (thứ tự này là `row_index`); bỏ qua thư mục, file không phải `.eml`, rác macOS (`__MACOSX/`, `._*`); tên file gốc lưu ở `row_data.source_file`.
- Giới hạn chống ZIP bomb: mỗi thư ≤ 5 MB, tổng dung lượng sau giải nén ≤ 500 MB. ZIP mã hóa hoặc hỏng, thư rỗng hoặc không phải thư: từ chối **cả file** và nêu tên thư lỗi.
- Không hỗ trợ `.msg` của Outlook cổ điển.
- Việc đọc diễn ra ngay trong request kiểm tra; ZIP rất nhiều thư có thể làm request chậm (chưa đo).

### 4.4 Xử lý nền

Sau khi nhận, upload có trạng thái `pending` và trả 202; một tác vụ nền trong tiến trình backend (`BackgroundTasks`) xử lý:

1. Chuyển `processing`, chụp lại cấu hình: ngưỡng của nguồn, `batch_size`, tập nhãn nguy hiểm đang bật, mô hình đang dùng.
2. Đọc từng dòng, gom thành lô `batch_size` dòng, gọi `POST /predict/batch` của dịch vụ AI; sau mỗi lô cập nhật `processed_rows` (frontend thăm dò 1,5 giây để vẽ thanh tiến độ).
3. Nếu phiên bản mô hình đổi giữa chừng thì báo lỗi (yêu cầu upload lại). Nhãn mới chưa có trong bảng `labels` được thêm tự động; mặc định nguy hiểm trừ `BENIGN`, `NON_SPAM`, `HAM`.
4. Ứng viên cảnh báo (nhãn nguy hiểm và `confidence ≥ ngưỡng`) được giữ **trong bộ nhớ**. Xử lý xong cả file mới ghi.
5. **Một giao dịch cuối** ghi toàn bộ cảnh báo (chèn theo khối 1.000), nhãn mới, và hoàn tất file: `alert_count`, `avg_confidence`, `label_distribution`, `threshold_used`, `dangerous_labels_used`, `model_id`, `processed_at`, trạng thái `completed`.
6. Có lỗi ở bất kỳ bước nào (dịch vụ AI hỏng, số dòng xử lý khác số dòng đã kiểm tra...) → `failed` kèm `error_message`, **không có cảnh báo nào được ghi**. Tiến độ các lô đã chạy vẫn giữ để chẩn đoán.
7. Khi backend khởi động, mọi upload còn `pending`/`processing` (do tắt máy chủ giữa chừng) bị đánh `failed`.

Việc lưu ngưỡng, lớp nguy hiểm và phiên bản mô hình theo từng file giúp giải thích về sau vì sao file đó sinh ra số cảnh báo như vậy, kể cả khi cấu hình đã đổi.

## 5. Cảnh báo

### 5.1 Quy tắc sinh

Cảnh báo được sinh cho một dòng khi **cả hai** điều kiện đúng: nhãn dự đoán thuộc lớp nguy hiểm (`labels.is_dangerous` và `is_active`), và `confidence ≥ ngưỡng` (`threshold_network` hoặc `threshold_email`, mặc định 0,80). Cảnh báo tự gắn vào sự cố của file (`auto_linked = true`), lưu nhãn, confidence, số thứ tự dòng trong file gốc (`row_index`, tính từ 1, không kể dòng tiêu đề) và `row_data` (JSON dòng gốc) để xem lại mà không cần mở file. `UNIQUE(upload_id, row_index)` bảo đảm một dòng không sinh hai cảnh báo.

Với luồng mạng, `confidence` là **xác suất của lớp được dự đoán** (xác suất cao nhất trong 15 lớp). Hệ quả: khi hai lớp giống nhau chia xác suất (ví dụ các kiểu tấn công web), confidence của lớp thắng thấp hơn và có thể không đạt ngưỡng dù chắc chắn đó là tấn công. Xem 8.1 (hai quy tắc A và B).

Chỉ các dòng thành cảnh báo mới được lưu kết quả từng dòng. Với các dòng khác, hệ thống chỉ lưu tổng hợp theo file (số mẫu, phân bố nhãn, confidence trung bình), vì một file có thể có hàng trăm nghìn dòng. Hệ quả: không kiểm tra lại được các dòng bị bỏ sót (false negative) từ dữ liệu trong hệ thống. Nếu cần, thêm bảng `predictions(upload_id, row_index, label, confidence)`.

### 5.2 Trạng thái xác minh

`unverified` (Chưa xác minh) ↔ `verified` (Đã xác minh) / `dismissed` (Bỏ qua); có thể đặt lại về `unverified`. Ghi người xác minh, thời điểm, ghi chú. Hệ thống chỉ giữ người và thời điểm xác minh **gần nhất** (không có bảng lịch sử xác minh); đặt lại về `unverified` xóa người xác minh.

Điều kiện: cảnh báo phải đang gắn một sự cố, và sự cố đó không ở trạng thái đã đóng hoặc đã hủy (409).

### 5.3 Thao tác hàng loạt

`POST /alerts/bulk-verify` và `POST /alerts/move` nhận tối đa 10.000 id và **chạy theo kiểu tất cả hoặc không gì cả**: nếu có cảnh báo không hợp lệ (không tồn tại, chưa gắn sự cố, sự cố đã đóng/hủy, đã ở đúng đích...) thì trả 409 kèm danh sách `items` (tối đa 50) và không thay đổi gì.

### 5.4 Chuyển và gỡ

- Chuyển sang sự cố khác: sự cố đích phải ở trạng thái Mới hoặc Đang xử lý.
- Gỡ khỏi sự cố (gắn nhầm): đặt `to_incident_id` rỗng; cảnh báo vào danh sách "Chưa gắn sự cố" và gắn lại được sau.
- Cảnh báo thuộc sự cố đã đóng/hủy không chuyển đi được.
- Mỗi lần chuyển hoặc gỡ ghi `alert_move_history` (từ đâu, đến đâu, ai, khi nào, lý do).

### 5.5 Xem và lọc

Phân trang (`page_size` ≤ 500); lọc theo `label`, `verification_status`, `source_type`, `upload_id`, `min_confidence`, `unassigned`, `incident_id`; sắp xếp theo `id, row_index, confidence, created_at, predicted_label, verification_status, source_type`. Giao diện có "Chọn tất cả N cảnh báo khớp bộ lọc" (lặp qua các trang 500); khi N lớn hơn 10.000 thì thao tác hàng loạt bị API từ chối (xem mục 13).

## 6. Cấu hình

| Khóa | Mặc định | Khoảng hợp lệ | Ý nghĩa |
|---|---|---|---|
| `threshold_network` | 0,80 | 0 đến 1 | Ngưỡng confidence sinh cảnh báo, luồng mạng |
| `threshold_email` | 0,80 | 0 đến 1 | Ngưỡng confidence sinh cảnh báo, email |
| `max_upload_mb` | 50 | 1 đến 500 | Kích thước tối đa một file |
| `max_rows` | 100.000 | 100 đến 1.000.000 | Số dòng tối đa một file |
| `batch_size` | 500 | 10 đến 5.000 | Số dòng gửi mô hình mỗi lô |

Thay đổi chỉ áp dụng cho file upload sau đó. Trang Cấu hình còn cho bật/tắt cờ "Nguy hiểm" và "Đang dùng" của từng nhãn (ví dụ bỏ chọn `BENIGN`, `NON_SPAM`), và nút **Đồng bộ từ dịch vụ AI** để nạp danh sách mô hình, nhãn và cột đầu vào vào bảng `models` và `labels`.

`labels` (nhãn đầu ra của mô hình, mang cờ nguy hiểm) tách khỏi `attack_types` (loại tấn công do người dùng chọn khi tạo sự cố) vì hai thứ khác bản chất: `BENIGN` không phải loại tấn công, còn `DoS Hulk` chi tiết hơn loại của sự cố.

## 7. Dashboard

`GET /dashboard` trả: tổng sự cố và số sự cố theo trạng thái; sự cố theo loại tấn công; tổng cảnh báo, số chưa gắn sự cố, cảnh báo theo nhãn, theo trạng thái xác minh; và

> tỉ lệ bỏ qua = Bỏ qua / (Đã xác minh + Bỏ qua)

Mẫu số bằng 0 thì trả `null` và giao diện hiển thị "chưa có".

## 8. Module AI/ML

Dịch vụ AI (`ml/serve.py`) chỉ có ba endpoint: `GET /` (kiểm tra sống), `GET /info` (mô hình đang chạy, nhãn, cột đầu vào, để backend đồng bộ vào bảng `models`) và `POST /predict/batch` (tối đa 5.000 dòng mỗi lô, trả `{label, confidence}` từng dòng kèm `model_version`).

- Dịch vụ **không khởi động** nếu thiếu `rf_multiclass.pkl`, `network_labels.json`, `scaler.pkl` hoặc `feature_cols.pkl` (không còn mô hình nhị phân dự phòng).
- Mô hình email là tùy chọn: thiếu `email_svm.pkl` thì `/info` báo `loaded=false` (phiên bản `email_svm_none`) và `/predict/batch` cho email trả 503.
- **Phiên bản mô hình** = tiền tố (`rf_multiclass_`, `email_svm_`) cộng 8 ký tự đầu của SHA-256 file `.pkl`. Huấn luyện lại tạo phiên bản mới và một dòng mới trong bảng `models`; nút **Đồng bộ từ dịch vụ AI** đặt các bản cũ thành không dùng.
- Các chức năng ATT&CK, `/classify*` và chính sách ba vùng của bản đầu đã bị loại khỏi hệ thống.

### 8.1 Mô hình luồng mạng

**Dữ liệu.** CIC-IDS2017, 15 nhãn (BENIGN và 14 loại tấn công).

**Loại dòng trùng trước khi chia.** CIC-IDS2017 có nhiều dòng giống hệt nhau. Bản đầu của dự án chia 80/20 ngẫu nhiên không loại trùng; đo lại cho thấy **13,4%** dòng kiểm thử (75.604/565.576) có một dòng giống hệt trong tập huấn luyện, nên điểm số bị thổi phồng. `preprocess.py` hiện loại dòng trùng (mọi cột kể cả nhãn) **trước khi chia**, và chỉ fit `StandardScaler` trên tập huấn luyện.

| | Số dòng |
|---|---|
| Dòng gốc (15 nhãn) | 2.830.743 |
| Sau bỏ ô null/inf | 2.827.876 |
| Sau loại trùng | **2.520.798** (bỏ 307.078 = 10,9%) |
| Huấn luyện / kiểm thử (80/20, phân tầng theo nhãn) | 2.016.638 / 504.160 |

Tỉ lệ dòng bị loại theo lớp: PortScan 42,9%; SSH-Patator 45,4%; FTP-Patator 25,3%; DoS Hulk 24,9%; BENIGN 7,8%; Bot 0,4%; các lớp còn lại gần 0%. Có 1.394 dòng có đặc trưng giống một dòng khác nhưng **nhãn khác** (nhãn nhiễu của bộ dữ liệu, giữ nguyên).

Số mẫu huấn luyện / kiểm thử theo lớp: BENIGN 1.676.045 / 419.012; DDoS 102.411 / 25.603; DoS Hulk 138.277 / 34.569; PortScan 72.555 / 18.139; GoldenEye 8.229 / 2.057; FTP-Patator 4.745 / 1.186; Slowloris 4.308 / 1.077; Slowhttptest 4.182 / 1.046; SSH-Patator 2.575 / 644; Bot 1.558 / 390; Web Brute Force 1.176 / 294; XSS 522 / 130; **Infiltration 29 / 7; SQL Injection 17 / 4; Heartbleed 9 / 2**.

**Mô hình phục vụ.** Random Forest nhiều lớp (`rf_multiclass.pkl`, 100 cây, độ sâu tối đa 20, `class_weight=balanced_subsample`) cùng `network_labels.json`. Đầu vào là các cột đặc trưng chuẩn hóa bằng `scaler.pkl`; đối chiếu tên cột không phân biệt hoa thường và bỏ khoảng trắng đầu/cuối; cột thiếu coi là 0. Confidence là xác suất cao nhất của lớp dự đoán.

**Kết quả trên tập kiểm thử đã loại trùng** (`results/multiclass_report.json`, nhãn theo argmax, chưa áp ngưỡng).

- Accuracy khoảng 0,99 (số chính xác: xem `multiclass_report.json`); Macro F1 0,83.
- Các lớp lớn (PortScan, SSH-Patator, DoS Hulk) đạt precision và recall từ 0,99 đến 1,00, **gần như không đổi** so với lần huấn luyện trên dữ liệu chưa loại trùng dù mất 25 đến 45% dòng, nghĩa là chúng tách được thật chứ không phải nhớ dòng trùng.
- Các lớp nhỏ không đổi vì gần như không có dòng trùng nên điểm yếu là thật:

| Lớp | Precision | Recall | Số mẫu kiểm thử |
|---|---|---|---|
| Bot | **0,14** | 0,99 | 390 |
| Web Attack - Brute Force | 0,81 | 0,69 | 294 |
| Web Attack - XSS | **0,37** | 0,65 | 130 |
| Web Attack - Sql Injection | 0,50 | 0,25 | 4 |
| Infiltration | 1,0 | 1,0 | 7 |
| Heartbleed | 1,0 | 0,5 | 2 |

- Macro F1 0,83 so với 0,789 của bản cũ **không phải cải thiện đã chứng minh**: chênh lệch đến từ Infiltration và SQL Injection, chỉ vài mẫu kiểm thử, và tập kiểm thử hai lần khác nhau nên không so được từng con số. Heartbleed, SQL Injection, Infiltration có 2 đến 7 mẫu nên **không đủ để kết luận theo từng lớp**.
- Bot gần như toàn dương tính giả (precision 0,14); Brute Force và XSS của web attack nhầm lẫn nhau.

**Hai quy tắc sinh cảnh báo cho luồng mạng** (đo trên tập kiểm thử 2017 đã loại trùng, ngưỡng 0,8; 419.012 luồng BENIGN và 85.148 luồng tấn công):

- **Quy tắc A (đang áp dụng):** nhãn argmax khác BENIGN và `confidence` (xác suất lớp cao nhất) ≥ ngưỡng.
- **Quy tắc B (đã đo, chưa áp dụng):** `1 − P(BENIGN) ≥ ngưỡng`, nhãn là lớp tấn công có xác suất cao nhất.

| | A | B |
|---|---|---|
| Cảnh báo giả trên 1.000 luồng BENIGN | 2,35 | 2,40 |
| Tấn công có cảnh báo | 99,13% (84.411/85.148) | 99,72% (84.913/85.148) |
| Web Brute Force: recall (precision) | 0,282 (0,943) | 0,680 (0,823) |
| XSS: recall (precision) | 0,031 (0,800) | 0,638 (0,485) |
| SQL Injection recall (n = 4) | 0 | 0,25 |
| Infiltration recall (n = 7) / Heartbleed (n = 2) | 0,429 / 0,5 | 0,429 / 0,5 |
| Bot: precision / recall | 0,324 / 0,956 | 0,324 / 0,956 |

Quy tắc A bỏ sót tấn công web vì xác suất bị chia cho hai lớp web nên không đạt 0,8; B bắt được nhiều hơn rõ rệt với chi phí thêm khoảng 0,05 cảnh báo giả trên 1.000 luồng BENIGN. Cảnh báo giả của BENIGN chủ yếu là Bot (779 luồng) và PortScan (196 luồng). B làm thay đổi ý nghĩa của "confidence" (thành xác suất là tấn công) và ngưỡng nhỏ hơn 0,5 hoạt động như 0,5; nếu chuyển sang B cần sửa `serve.py` và `make_network_samples.py` và ghi rõ trong tài liệu. Hiện hệ thống dùng A; điểm yếu với web attack được ghi ở mục 13.

**Lựa chọn mô hình.** Đề bài gợi ý Gradient Boosting làm mô hình chính. Hệ thống giữ Random Forest do đã tích hợp và kiểm thử toàn bộ luồng; đây là quyết định thực dụng, chưa có phép so sánh công bằng giữa các họ mô hình trên dữ liệu đã loại trùng (các so sánh nhị phân của bản đầu đã bỏ cùng mô hình nhị phân).

### 8.2 Mô hình email

- **Dữ liệu:** sáu nguồn từ bộ "Phishing Email Dataset" trên Kaggle: CEAS_08, Enron, Ling, SpamAssassin, Nazario, Nigerian Fraud (file `phishing_email.csv` là bản nối của sáu file kia nên bỏ qua). Sau làm sạch và loại trùng nguyên văn: 81.887 thư, 52,1% nhãn spam/phishing. Thư thuộc khoảng 2000 đến 2022.
- **Mô hình:** TF-IDF 1 đến 2 gram trên tiêu đề và nội dung (HTML thô đổi sang chữ), sau đó Linear SVM hiệu chỉnh xác suất (`CalibratedClassifierCV`, sigmoid, 5 lần). Mô hình cuối huấn luyện trên **cả sáu nguồn**.
- **Nhãn và confidence:** `SPAM`/`NON_SPAM`; confidence = max(p, 1 − p) với p là xác suất spam. Vì vậy một thư spam sinh cảnh báo khi p ≥ 0,8 (ngưỡng mặc định).
- **Đặc trưng thực sự dùng:** chữ trong tiêu đề và nội dung. `has_html` và `attachments` được đọc và lưu vào `row_data` nhưng **mô hình không dùng**; các token đánh dấu số URL và tệp đính kèm trong `ml/email_features.py` bị bộ tách từ loại bỏ (vì chứa chữ số) nên không có tác dụng. Đừng mô tả mô hình là "có dùng đặc trưng URL".
- **Cách đánh giá:** "bỏ một nguồn ra": lần lượt bỏ từng nguồn, huấn luyện trên năm nguồn còn lại, đo trên nguồn bị bỏ. Cách này đo khả năng tổng quát sang nguồn chưa thấy, thực tế hơn điểm nội bộ (điểm nội bộ chia ngẫu nhiên đạt khoảng 0,997 nhưng không phản ánh khả năng tổng quát).

| Nguồn bị bỏ | Ngưỡng 0,5: recall / precision | Ngưỡng 0,8: recall / precision | PR-AUC |
|---|---|---|---|
| CEAS_08 | 0,839 / 0,933 | 0,741 / 0,952 | 0,962 |
| Enron | 0,930 / 0,788 | 0,840 / 0,872 | 0,943 |
| Ling | 0,919 / 0,813 | 0,841 / 0,895 | 0,937 |
| SpamAssassin | 0,980 / 0,785 | 0,964 / 0,885 | 0,985 |
| Nigerian Fraud | 0,994 / chỉ spam | 0,984 / chỉ spam | không đo được |
| Nazario | **0,562** / chỉ spam | **0,346** / chỉ spam | không đo được |
| **Gộp (81.887 thư)** | 0,877 / 0,875 | **0,788 / 0,923** | **0,950** |

Nigerian Fraud và Nazario chỉ có thư spam/phishing nên chỉ đo được recall, không đo được báo nhầm.

**Điểm yếu cần nêu rõ:** với phishing kiểu Nazario, recall chỉ 0,562 ở ngưỡng 0,5 và 0,346 ở ngưỡng 0,8; trong số 402 thư có ngày hợp lệ, thư từ năm 2020 (n = 179) chỉ đạt 0,240 và 0,106 (trước 2020, n = 223: 0,556 và 0,336), nghĩa là phishing càng mới càng dễ bị bỏ lọt. Ngoài ra: mô hình còn học đặc điểm của nguồn dữ liệu (các từ như `enron`, `vince`, `opensuse` đứng đầu danh sách nghiêng về thư hợp lệ); chỉ học thư tiếng Anh nên thư tiếng Việt cho kết quả vô nghĩa; dữ liệu thư hợp lệ đều là thư cũ nên không đo được tỉ lệ báo nhầm trên thư ngày nay. Kết quả cho biết khả năng phân biệt spam và phishing trên các nguồn cũ, không chứng minh bắt được phishing hiện đại. Cảnh báo email nên do chuyên viên quyết định và không nên dùng để tự đóng thư.

### 8.3 Giới hạn chung của đánh giá mô hình

- Luồng mạng: chia ngẫu nhiên 80/20 trên CIC-IDS2017 sau khi đã loại dòng trùng nguyên văn. Các luồng gần giống nhau (không trùng hẳn) vẫn có thể nằm ở cả hai tập, nên số liệu có thể cao hơn khi gặp lưu lượng của môi trường khác. Mô hình huấn luyện một lần, một hạt giống.
- Chưa đo lại độ chính xác cho từng lớp ở ngưỡng sinh cảnh báo 0,8 ngoài hai quy tắc A và B ở trên.
- CIC-IDS2017 là dữ liệu lab 2017; không đảm bảo hiệu quả trên hệ thống thật.
- **Thử nghiệm sơ bộ sang CSE-CIC-IDS2018 (không thuộc kết quả chính):** chạy mô hình 2017 trên dữ liệu 2018 (đã ánh xạ cột) gần như không phát hiện được tấn công ở hầu hết các lớp. Một mô hình phân biệt riêng lưu lượng BENIGN của hai bộ đạt AUC xấp xỉ 1,0, với độ quan trọng dàn trải trên nhiều đặc trưng (cổng đích, cửa sổ TCP ban đầu, độ dài header, thời gian giữa các gói...), nên hai bộ có phân bố khác nhau một cách hệ thống và phép so sánh trực tiếp không công bằng. Không kết luận được nguyên nhân (môi trường hay phiên bản công cụ trích đặc trưng). Thử nghiệm này không được giữ lại trong mã nguồn và chỉ dùng để ghi nhận hạn chế: mô hình chỉ được kiểm chứng trên CIC-IDS2017.

## 9. API

Địa chỉ: `http://localhost:8000`; tài liệu tự sinh ở `/docs`. Mọi endpoint (trừ đăng nhập và đăng ký lần đầu) cần header `Authorization: Bearer <token>`.

| Nhóm | Phương thức và đường dẫn | Mô tả |
|---|---|---|
| Xác thực | `POST /auth/login` | Đăng nhập, nhận JWT |
| | `POST /auth/register` | Tạo tài khoản (tài khoản đầu tiên tự do) |
| | `GET /auth/me` | Người dùng hiện tại |
| Sự cố | `POST /incidents` | Tạo (trạng thái Mới) |
| | `GET /incidents` | Danh sách: phân trang, sắp xếp, lọc |
| | `GET /incidents/{id}` | Chi tiết: số cảnh báo theo trạng thái xác minh, file đang xử lý, chuyển trạng thái cho phép, có xóa được không |
| | `PUT /incidents/{id}` | Sửa (chặn khi đã đóng/hủy) |
| | `PATCH /incidents/{id}/status` | Đổi trạng thái (kèm `note` khi cần) |
| | `GET /incidents/{id}/history` | Lịch sử trạng thái |
| | `DELETE /incidents/{id}` | Xóa (chỉ khi chưa có cảnh báo) |
| Upload | `POST /incidents/{id}/uploads` | Upload (form: `data_type`, `file`); trả 202 |
| | `GET /incidents/{id}/uploads` | Danh sách file của sự cố |
| | `GET /uploads/{id}` | Chi tiết và kết quả phân loại của một file |
| Cảnh báo | `GET /incidents/{id}/alerts` | Cảnh báo của sự cố |
| | `GET /alerts` | Mọi cảnh báo; `unassigned=true` cho cảnh báo chưa gắn |
| | `GET /alerts/{id}` | Chi tiết kèm dòng gốc |
| | `GET /alerts/{id}/moves` | Lịch sử chuyển/gỡ |
| | `PATCH /alerts/{id}/verify` | Xác minh một cảnh báo |
| | `POST /alerts/bulk-verify` | Xác minh hàng loạt |
| | `POST /alerts/move` | Chuyển hoặc gỡ hàng loạt |
| Danh mục | `GET /attack-types` | Loại tấn công của sự cố |
| | `GET /labels`, `PUT /labels/{id}` | Nhãn đầu ra mô hình; sửa cờ nguy hiểm, đang dùng, tên |
| | `GET /settings`, `PUT /settings/{key}` | Cấu hình |
| | `GET /models`, `POST /models/sync` | Mô hình; đồng bộ từ dịch vụ AI |
| Dashboard | `GET /dashboard` | Số liệu tổng quan |
| Hệ thống | `GET /`, `GET /health/db` | Kiểm tra backend và kết nối cơ sở dữ liệu |

Mã lỗi chính: 401 chưa đăng nhập; 404 không tìm thấy; 409 xung đột trạng thái (sự cố đã đóng, file trùng, thao tác hàng loạt có phần tử không hợp lệ...); 413 file quá lớn; 422 dữ liệu không hợp lệ; 503 dịch vụ AI chưa sẵn sàng.

## 10. Giao diện

Các trang: Đăng nhập; Dashboard; Danh sách sự cố; Chi tiết sự cố (ba tab: Cảnh báo, Dữ liệu tải lên, Lịch sử trạng thái); Danh sách cảnh báo chung; Cấu hình.

- Tab Dữ liệu tải lên: chọn nguồn, chọn file (hộp chọn file chỉ cho `.eml`/`.zip` khi nguồn là Email), hướng dẫn định dạng, thẻ kết quả cho từng file (tổng mẫu, confidence trung bình, phân bố nhãn, ngưỡng và lớp nguy hiểm đã áp dụng, số cảnh báo).
- Khi có file đang xử lý, giao diện thăm dò mỗi 1,5 giây, hiện thanh tiến độ và thông báo (toast) khi xong hoặc lỗi.
- Thời gian lưu UTC không múi giờ; frontend thêm hậu tố `Z` để trình duyệt hiển thị theo giờ máy.
- `AlertDetailModal` chưa hiển thị `attachments` và `source_file` của thư.

## 11. Cách chạy

```powershell
# Dịch vụ AI (chạy trong thư mục ml; khởi động lại sau mỗi lần huấn luyện)
cd ml
uvicorn serve:app --port 8001

# Backend
cd backend
pip install -r requirements.txt
python seed.py --demo
uvicorn main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

- `backend/.env`: `DB_SERVER`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `SECRET_KEY`; tùy chọn `AI_SERVICE_URL`, `UPLOAD_STORAGE_DIR`, `ACCESS_TOKEN_EXPIRE_MINUTES`.
- `seed.py --demo` tạo bảng, danh mục, nhãn, cấu hình, hai tài khoản và 8 sự cố mẫu (chưa có cảnh báo; cảnh báo sinh khi upload file). Ứng dụng cũng tự tạo bảng khi khởi động; `create_all` không sửa bảng đã có, nên khi đổi cấu trúc phải dùng database mới hoặc `reset_table.sql` (cẩn thận: file này cứng `USE thesis_db;` và xóa **toàn bộ** bảng).
- Sau khi dịch vụ AI chạy: Cấu hình → **Đồng bộ từ dịch vụ AI**.
- Dùng `127.0.0.1` thay cho `localhost` khi backend gọi dịch vụ AI trên Windows. CORS của backend chỉ cho `http://localhost:5173`; địa chỉ backend ở frontend cố định `http://localhost:8000` (`frontend/src/api/client.js`).
- Thứ tự huấn luyện trong `ml/`: `preprocess.py` → `train_multiclass.py` → `train_email.py` → `serve.py`. Dữ liệu CIC-IDS2017 để ở `ml/data/ids/raw`; CSV email Kaggle ở `ml/data/email/kaggle`. Trước khi chạy lại `preprocess.py`, xóa thư mục `ml/data/ids/processed` để không lẫn file cũ.
- `ml/make_network_samples.py` tạo các file mẫu `mau_nhieu_canh_bao.csv`, `mau_nho.json`, `mau_duoi_nguong.csv` bằng mô hình hiện tại và quy tắc A; phải chạy lại sau mỗi lần huấn luyện hoặc đổi quy tắc.

## 12. Kiểm thử

| Bộ kiểm thử | Phạm vi | Cách chạy |
|---|---|---|
| `tests/test_incident_alert_flow.py` | 146 kiểm tra toàn luồng: đăng nhập, cấu hình, sự cố, upload, cảnh báo, xác minh, chuyển/gỡ, dashboard, trạng thái | Backend chạy cổng 8000 cùng `tests/fake_ai_service.py` ở cổng 8001 (tắt dịch vụ AI thật); **cần database trống mỗi lần** |
| `tests/test_eml_parsing.py` | 33 kiểm tra đọc `.eml`, `.zip`, CSV/JSON email | `python tests\test_eml_parsing.py`, không cần backend |

Dịch vụ AI giả trả kết quả xác định và có "bẫy" để thử lỗi giữa chừng (một giá trị `Flow Duration` đặc biệt làm lô lỗi, một giá trị làm chậm 2 giây, chuỗi `boom-crash` trong email làm lỗi). Sau khi chạy test, bật lại dịch vụ AI thật và đồng bộ mô hình.

Bộ test luồng **không idempotent**: mỗi lần chạy để lại sự cố (ví dụ 5 sự cố "Sự cố phân trang") nên chạy lại trên database không sạch sẽ làm hỏng kiểm tra tìm theo tiêu đề. Quy trình: tạo database thử (ví dụ `thesis_test`), đổi `DB_NAME` trong `backend/.env`, chạy `python seed.py`, chạy test, rồi đổi lại.

**Mức độ kiểm chứng:** bộ test luồng đã chạy trên **SQL Server thật** (cùng dịch vụ AI giả). Lần chạy đầu trên SQL Server lộ hai lỗi mà SQLite không bắt được và đã sửa: cột lặp trong `ORDER BY` khi sắp theo `id`, và thiếu `flush()` đúng thứ tự khóa ngoại khi xóa sự cố cùng file upload. Chưa có test tích hợp riêng cho upload `.eml`/`.zip` qua backend (chỉ có test của bộ đọc thư), chưa kiểm thử tự động giao diện, chưa đo hiệu năng với file hàng trăm nghìn dòng.

## 13. Hạn chế đã biết

- **Hệ thống:** một vai trò; không khóa tài khoản sau đăng nhập sai; không có làm mới token; không có nhật ký kiểm toán chống sửa; chống trùng chỉ theo hash trong cùng sự cố; chỉ giữ người xác minh gần nhất (không có lịch sử xác minh).
- **Xử lý nền:** chạy trong tiến trình backend, không có hàng đợi; khởi động lại làm mất tác vụ đang chạy (được đánh `failed`, phải upload lại); ứng viên cảnh báo giữ trong bộ nhớ nên bị giới hạn bởi `max_rows`; ZIP email được đọc đồng bộ trong request.
- **Dữ liệu:** không lưu dự đoán của dòng không thành cảnh báo; không tải lại được file gốc từ giao diện; CSV/JSON bắt buộc UTF-8 (chưa có chế độ Latin-1).
- **Giao diện:** nút "Chọn tất cả N cảnh báo khớp bộ lọc" không dùng được khi N > 10.000 (API giới hạn 10.000 id mỗi lần, trong khi một file có thể sinh tới `max_rows` cảnh báo); lọc theo ngày hiểu ngày không kèm múi giờ là UTC trong khi giao diện hiển thị giờ máy; chưa kiểm thử tự động; `Table.jsx` còn rỗng.
- **Mô hình:** xem 8.1 đến 8.3; đặc biệt là các lớp web attack và Bot của luồng mạng (với quy tắc A, XSS chỉ đạt recall 0,03 ở ngưỡng 0,8), phishing mới trong email, và việc mô hình chỉ được kiểm chứng trên CIC-IDS2017.