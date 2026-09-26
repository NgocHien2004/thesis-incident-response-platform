from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta, timezone
from app.models.alert import Alert
from app.models.alert_group import AlertGroup

# Cửa sổ thời gian gom nhóm: 1 giờ
DEDUP_WINDOW_MINUTES = 60

def normalize_alert(alert: Alert) -> Alert:
    """Chuẩn hóa các trường của alert về định dạng chung."""
    if alert.title:
        alert.title = alert.title.strip()
    if alert.ioc:
        # Chuẩn hóa IOC: lowercase, bỏ khoảng trắng thừa
        iocs = [i.strip().lower() for i in alert.ioc.split(",") if i.strip()]
        alert.ioc = ",".join(sorted(set(iocs)))  # loại trùng, sắp xếp
    return alert

def find_or_create_group(alert: Alert, db: Session) -> AlertGroup:
    """
    Tìm nhóm phù hợp trong cửa sổ thời gian.
    Tiêu chí gom nhóm: cùng IOC VÀ cùng tài sản bị ảnh hưởng.
    """
    window_start = datetime.now(timezone.utc) - timedelta(minutes=DEDUP_WINDOW_MINUTES)

    existing_group = None

    if alert.ioc and alert.affected_asset:
        existing_group = db.query(AlertGroup).filter(
            AlertGroup.ioc == alert.ioc,
            AlertGroup.affected_asset == alert.affected_asset,
            AlertGroup.last_seen >= window_start
        ).first()
    elif alert.ioc:
        existing_group = db.query(AlertGroup).filter(
            AlertGroup.ioc == alert.ioc,
            AlertGroup.last_seen >= window_start
        ).first()

    if existing_group:
        existing_group.alert_count += 1
        existing_group.last_seen = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing_group)
        return existing_group

    # Chưa có nhóm → tạo mới
    new_group = AlertGroup(
        title=alert.title,
        ioc=alert.ioc,
        affected_asset=alert.affected_asset,
        alert_count=1,
        first_seen=datetime.now(timezone.utc),
        last_seen=datetime.now(timezone.utc),
    )
    db.add(new_group)
    db.commit()
    db.refresh(new_group)
    return new_group

def process_alert(alert: Alert, db: Session) -> Alert:
    """Chuẩn hóa + gom nhóm cho 1 alert."""
    alert = normalize_alert(alert)
    group = find_or_create_group(alert, db)
    alert.group_id = group.id
    db.commit()
    db.refresh(alert)
    return alert