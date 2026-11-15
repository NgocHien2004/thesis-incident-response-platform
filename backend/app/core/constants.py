INCIDENT_STATUSES = ("new", "in_progress", "resolved", "closed", "cancelled")

INCIDENT_TRANSITIONS = {
    "new":         {"in_progress", "cancelled"},
    "in_progress": {"resolved", "cancelled"},
    "resolved":    {"closed", "in_progress", "cancelled"},
    "closed":      set(),
    "cancelled":   set(),
}

# Trạng thái cho phép upload dữ liệu, gắn/chuyển/xác minh cảnh báo
UPLOADABLE_STATUSES = {"new", "in_progress"}
TERMINAL_STATUSES = {"closed", "cancelled"}
# Chuyển sang các trạng thái này phải đợi file đang xử lý xong
BLOCKED_WHILE_PROCESSING = {"resolved", "closed", "cancelled"}
# Chuyển trạng thái bắt buộc ghi lý do
NOTE_REQUIRED = {("resolved", "in_progress"), ("new", "cancelled"),
                 ("in_progress", "cancelled"), ("resolved", "cancelled")}

SEVERITIES = ("low", "medium", "high", "critical")
INCIDENT_SOURCES = ("ids_ips", "email", "endpoint", "manual", "other")

DATA_TYPES = ("network", "email")
UPLOAD_STATUSES = ("pending", "processing", "completed", "failed")
VERIFICATION_STATUSES = ("unverified", "verified", "dismissed")
# .eml (một thư) và .zip (nhiều file .eml) chỉ dùng cho nguồn email
FILE_FORMATS = {".csv": "csv", ".json": "json", ".eml": "eml", ".zip": "zip"}
EMAIL_ONLY_FORMATS = {"eml", "zip"}

BENIGN_LABELS = {"BENIGN", "NON_SPAM", "HAM"}

DEFAULT_SETTINGS = {
    "threshold_network": ("0.80", "Ngưỡng confidence để sinh cảnh báo từ luồng mạng (0 đến 1)"),
    "threshold_email":   ("0.80", "Ngưỡng confidence để sinh cảnh báo từ email (0 đến 1)"),
    "max_upload_mb":     ("50",   "Kích thước tối đa của một file upload (MB)"),
    "max_rows":          ("100000", "Số dòng dữ liệu tối đa trong một file"),
    "batch_size":        ("500",  "Số dòng gửi cho mô hình mỗi lô"),
}

DEFAULT_ATTACK_TYPES = [
    ("ddos",        "DoS / DDoS"),
    ("brute_force", "Dò mật khẩu (Brute force)"),
    ("port_scan",   "Quét cổng"),
    ("web_attack",  "Tấn công ứng dụng web"),
    ("botnet",      "Botnet"),
    ("infiltration", "Xâm nhập"),
    ("phishing",    "Phishing"),
    ("spam",        "Spam"),
    ("malware",     "Mã độc"),
    ("other",       "Khác"),
]

# Nhãn mặc định (khớp CIC-IDS2017 và mô hình email); nhãn mới từ dịch vụ AI được tự thêm
DEFAULT_LABELS = [
    ("network", "BENIGN", "Lưu lượng bình thường", False),
    ("network", "ATTACK", "Tấn công (mô hình nhị phân)", True),
    ("network", "Bot", "Botnet", True),
    ("network", "DDoS", "DDoS", True),
    ("network", "DoS GoldenEye", "DoS GoldenEye", True),
    ("network", "DoS Hulk", "DoS Hulk", True),
    ("network", "DoS Slowhttptest", "DoS Slowhttptest", True),
    ("network", "DoS slowloris", "DoS Slowloris", True),
    ("network", "FTP-Patator", "Dò mật khẩu FTP", True),
    ("network", "Heartbleed", "Heartbleed", True),
    ("network", "Infiltration", "Xâm nhập", True),
    ("network", "PortScan", "Quét cổng", True),
    ("network", "SSH-Patator", "Dò mật khẩu SSH", True),
    ("network", "Web Attack - Brute Force", "Web: dò mật khẩu", True),
    ("network", "Web Attack - Sql Injection", "Web: SQL Injection", True),
    ("network", "Web Attack - XSS", "Web: XSS", True),
    ("email", "NON_SPAM", "Thư bình thường", False),
    ("email", "SPAM", "Thư rác / lừa đảo", True),
]