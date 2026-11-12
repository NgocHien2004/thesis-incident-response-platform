from sqlalchemy.orm import Session
from app.models.incident import AttackType
from app.models.ml_model import Label
from app.models.setting import Setting
from app.models.upload import Upload
from app.core.timeutils import utcnow
from app.core.constants import DEFAULT_SETTINGS, DEFAULT_ATTACK_TYPES, DEFAULT_LABELS

def seed_reference_data(db: Session):
    # Chỉ thêm cái còn thiếu, không ghi đè thay đổi của người dùng
    have = {r[0] for r in db.query(AttackType.code).all()}
    for code, name in DEFAULT_ATTACK_TYPES:
        if code not in have:
            db.add(AttackType(code=code, name_vi=name, is_active=True))
    have = {(r[0], r[1]) for r in db.query(Label.data_type, Label.code).all()}
    for data_type, code, name, dangerous in DEFAULT_LABELS:
        if (data_type, code) not in have:
            db.add(Label(data_type=data_type, code=code, name_vi=name, is_dangerous=dangerous, is_active=True))
    have = {r[0] for r in db.query(Setting.key).all()}
    for key, (value, desc) in DEFAULT_SETTINGS.items():
        if key not in have:
            db.add(Setting(key=key, value=value, description=desc))
    db.commit()

def fail_interrupted_uploads(db: Session) -> int:
    # File đang xử lý mà máy chủ tắt giữa chừng thì không bao giờ xong: đánh dấu lỗi
    rows = db.query(Upload).filter(Upload.status.in_(("pending", "processing"))).all()
    for u in rows:
        u.status = "failed"
        u.error_message = "Bị gián đoạn do máy chủ khởi động lại, không có cảnh báo nào được tạo. Hãy upload lại."
        u.processed_at = utcnow()
    db.commit()
    return len(rows)
