import argparse
from datetime import timedelta
from database import SessionLocal, engine, Base
from app.core.security import hash_password
from app.core.timeutils import utcnow
from app.models.user import User
from app.models.incident import Incident, AttackType, IncidentStatusHistory
from app.models.upload import Upload
from app.models.alert import Alert, AlertMoveHistory
from app.models.setting import Setting
from app.models.ml_model import MLModel, Label
from app.services.seed import seed_reference_data

# Tài khoản tạo sẵn (một vai trò: chuyên viên). Đổi mật khẩu ở đây nếu cần.
USERS = [
    ("analyst01", "Test@1234", "Nguyễn Văn An"),
    ("analyst02", "Test@1234", "Trần Thị Bình"),
]

# (tiêu đề, mô tả, loại tấn công, mức độ, nguồn, chuỗi trạng thái, số ngày trước, lý do hủy)
DEMO_INCIDENTS = [
    ("DDoS vào máy chủ web bán hàng", "Lưu lượng tăng đột biến vào cổng 80/443, trang web phản hồi chậm.",
     "ddos", "high", "ids_ips", ["new", "in_progress"], 2, None),
    ("Quét cổng từ IP lạ vào mạng nội bộ", "IDS ghi nhận nhiều kết nối đến các cổng liên tiếp từ một địa chỉ ngoài.",
     "port_scan", "medium", "ids_ips", ["new"], 1, None),
    ("Dò mật khẩu SSH vào máy chủ file", "Hàng trăm lần đăng nhập SSH thất bại trong 10 phút.",
     "brute_force", "critical", "endpoint", ["new", "in_progress", "resolved"], 6, None),
    ("Email phishing giả mạo ngân hàng", "Nhân viên kế toán báo nhận thư yêu cầu xác minh tài khoản.",
     "phishing", "high", "email", ["new", "in_progress", "resolved", "closed"], 10, None),
    ("Spam hàng loạt tới hộp thư phòng nhân sự", "Nhiều thư quảng cáo có liên kết lạ gửi tới cùng lúc.",
     "spam", "low", "email", ["new", "in_progress", "resolved", "closed"], 13, None),
    ("Nghi ngờ botnet trên máy trạm phòng kế toán", "Máy trạm kết nối định kỳ tới một địa chỉ lạ.",
     "botnet", "high", "endpoint", ["new", "in_progress"], 4, None),
    ("Tấn công SQL Injection trang đăng nhập", "Log web có chuỗi truy vấn bất thường vào biểu mẫu đăng nhập.",
     "web_attack", "critical", "ids_ips", ["new"], 0, None),
    ("Cảnh báo nhầm từ thiết bị IDS", "Thiết bị báo xâm nhập nhưng đã kiểm tra là lưu lượng sao lưu nội bộ.",
     "other", "low", "ids_ips", ["new", "cancelled"], 8, "Báo nhầm, đã xác nhận là lưu lượng sao lưu"),
]


def next_code(db):
    prefix = f"INC-{utcnow().year}-"
    nums = []
    for (c,) in db.query(Incident.code).filter(Incident.code.like(prefix + "%")).all():
        tail = c[len(prefix):]
        if tail.isdigit():
            nums.append(int(tail))
    return f"{prefix}{(max(nums) + 1 if nums else 1):04d}"


def seed_users(db):
    for username, password, full_name in USERS:
        if db.query(User).filter(User.username == username).first():
            print(f"  Bỏ qua {username} (đã có)")
            continue
        db.add(User(username=username, password_hash=hash_password(password), full_name=full_name, role="analyst"))
        print(f"  Đã tạo {username} / {password}")
    db.commit()


def seed_demo(db):
    owner = db.query(User).filter(User.username == USERS[0][0]).first()
    if not owner:
        print("  Chưa có tài khoản, hãy chạy seed không kèm --demo trước")
        return
    made = 0
    for title, desc, attack, severity, source, path, days_ago, cancel_note in DEMO_INCIDENTS:
        if db.query(Incident).filter(Incident.title == title).first():
            continue
        t0 = utcnow() - timedelta(days=days_ago, hours=2)
        inc = Incident(code=next_code(db), title=title, description=desc, attack_type=attack, severity=severity,
                       occurred_at=t0, source=source, status=path[-1], created_by=owner.id,
                       created_at=t0 + timedelta(minutes=10), updated_at=t0 + timedelta(hours=len(path)))
        db.add(inc)
        db.flush()
        old = None
        for i, st in enumerate(path):
            at = t0 + timedelta(hours=i, minutes=10)
            note = "Tạo sự cố" if st == "new" else (cancel_note if st == "cancelled" else None)
            db.add(IncidentStatusHistory(incident_id=inc.id, old_status=old, new_status=st,
                                         changed_by=owner.id, changed_at=at, note=note))
            if st == "resolved":
                inc.resolved_at = at
            if st == "closed":
                inc.closed_at = at
            old = st
        db.commit()
        made += 1
    print(f"  Đã thêm {made} sự cố mẫu (chưa có cảnh báo; cảnh báo sinh ra khi upload file)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="thêm vài sự cố mẫu để xem danh sách và dashboard")
    args = ap.parse_args()

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        print("Danh mục (loại tấn công, nhãn, cấu hình):")
        seed_reference_data(db)
        print("  Xong")
        print("Tài khoản:")
        seed_users(db)
        if args.demo:
            print("Sự cố mẫu:")
            seed_demo(db)
    print("Hoàn tất.")