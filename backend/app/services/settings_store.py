import math
from sqlalchemy.orm import Session
from app.models.setting import Setting
from app.core.constants import DEFAULT_SETTINGS

def get_setting(db: Session, key: str) -> str:
    row = db.get(Setting, key)
    return row.value if row else DEFAULT_SETTINGS[key][0]

def get_float(db: Session, key: str) -> float:
    return float(get_setting(db, key))

def get_int(db: Session, key: str) -> int:
    return int(float(get_setting(db, key)))

SETTING_RULES = {
    "threshold_network": (float, 0.0, 1.0),
    "threshold_email":   (float, 0.0, 1.0),
    "max_upload_mb":     (int, 1, 500),
    "max_rows":          (int, 100, 1_000_000),
    "batch_size":        (int, 10, 5000),
}

def validate_setting(key: str, raw: str) -> str:
    if key not in SETTING_RULES:
        raise ValueError("Khóa cấu hình không tồn tại")
    kind, lo, hi = SETTING_RULES[key]
    msg = f"Giá trị phải là số trong khoảng {lo} đến {hi}"
    try:
        num = float(raw)
    except (ValueError, TypeError):
        raise ValueError(msg)
    if not math.isfinite(num) or not (lo <= num <= hi):
        raise ValueError(msg)
    if kind is int:
        if num != int(num):
            raise ValueError(msg)
        return str(int(num))
    return str(num)
