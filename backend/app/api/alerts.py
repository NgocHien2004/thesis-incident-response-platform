from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
from sqlalchemy import func, case
import json, csv, io
from database import get_db
from app.models.alert import Alert, AlertSource, AlertStatus
from app.schemas.alert import AlertCreate, AlertOut, AlertNote
from app.models.asset import Asset
from app.services.scoring import score_alert, score_alert_safe
from app.core.dependencies import get_current_user, require_roles
from app.models.user import RoleEnum, User
from app.services.dedup import process_alert
from app.models.alert_group import AlertGroup
from app.schemas.alert import TriageRequest, AlertTriaged
from datetime import datetime, timezone, timedelta

router = APIRouter(prefix="/alerts", tags=["Alerts"])


def resolve_asset_id(db: Session, row: dict):
    """Gắn cảnh báo nhập từ ngoài vào tài sản: theo affected_asset (id), asset_hostname hoặc asset_ip."""
    aid = row.get("affected_asset")
    if aid not in (None, ""):
        try:
            aid = int(aid)
        except (TypeError, ValueError):
            aid = None
        if aid and db.query(Asset.id).filter(Asset.id == aid).first():
            return aid
    host = str(row.get("asset_hostname") or "").strip().lower()
    ip = str(row.get("asset_ip") or "").strip()
    found = None
    if host:
        found = db.query(Asset).filter(func.lower(Asset.hostname) == host).first()
    if not found and ip:
        found = db.query(Asset).filter(Asset.ip_address == ip).first()
    return found.id if found else None


# Nguồn mà bên gửi được phép khai báo khi nhập tự động. "manual" không nhận vì đó là báo cáo
# của con người, chỉ tạo qua POST /alerts/ (luật an toàn tự đóng loại trừ nguồn này).
DECLARABLE_SOURCES = {AlertSource.ids_ips, AlertSource.endpoint, AlertSource.email}


def resolve_source(row: dict, default: AlertSource) -> AlertSource:
    """Lấy nguồn từ trường source của payload nếu hợp lệ, ngược lại dùng kênh nhập (default)."""
    raw = str(row.get("source") or "").strip().lower()
    try:
        declared = AlertSource(raw)
    except ValueError:
        return default
    return declared if declared in DECLARABLE_SOURCES else default


# Xem danh sách
@router.get("/", response_model=List[AlertOut])
def list_alerts(
    status: str = None,
    zone: Optional[str] = None,
    order: str = "created",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Alert)
    if status:
        query = query.filter(Alert.status == status)
    if zone:
        query = query.filter(Alert.ml_zone == zone)
    if order == "priority":
        # CASE thay cho "ml_priority IS NULL" vì SQL Server không cho dùng biểu thức logic trong ORDER BY
        unscored_last = case((Alert.ml_priority.is_(None), 1), else_=0)
        return query.order_by(unscored_last, Alert.ml_priority.desc(), Alert.created_at.desc()).all()
    return query.order_by(Alert.created_at.desc()).all()

# Xem chi tiết
@router.get("/{alert_id}", response_model=AlertOut)
def get_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(404, "Không tìm thấy cảnh báo")
    return alert

# Tạo thủ công (manual)
@router.post("/", response_model=AlertOut)
def create_alert(
    payload: AlertCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.it_helpdesk, RoleEnum.analyst_soc))
):
    alert = Alert(**payload.model_dump(), created_by=current_user.id)
    db.add(alert)
    db.commit()
    db.refresh(alert)
    alert = process_alert(alert, db)
    score_alert_safe(db, alert)
    return alert

# Webhook — nhận POST từ hệ thống ngoài
@router.post("/webhook", response_model=AlertOut)
def receive_webhook(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.it_helpdesk, RoleEnum.analyst_soc))
):
    alert = Alert(
        title=payload.get("title", "Webhook Alert"),
        description=payload.get("description"),
        source=resolve_source(payload, AlertSource.webhook),
        severity=payload.get("severity", "medium"),
        source_ref=payload.get("source_ref"),
        ioc=payload.get("ioc"),
        affected_asset=resolve_asset_id(db, payload),
        raw_data=json.dumps(payload),
        created_by=current_user.id
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    alert = process_alert(alert, db)
    score_alert_safe(db, alert)
    return alert

# Upload CSV
@router.post("/upload/csv", response_model=List[AlertOut])
def upload_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.it_helpdesk, RoleEnum.analyst_soc))
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(400, "Chỉ chấp nhận file .csv")
    content = file.file.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    alerts = []
    for row in reader:
        alert = Alert(
            title=row.get("title", "CSV Alert"),
            description=row.get("description"),
            source=resolve_source(row, AlertSource.csv_upload),
            severity=row.get("severity", "medium"),
            source_ref=row.get("source_ref"),
            ioc=row.get("ioc"),
            affected_asset=resolve_asset_id(db, row),
            raw_data=json.dumps(row),
            created_by=current_user.id
        )
        db.add(alert)
        alerts.append(alert)
    db.commit()
    for a in alerts:
        db.refresh(a)
        process_alert(a, db)
        score_alert_safe(db, a)
    return alerts

# Upload JSON
@router.post("/upload/json", response_model=List[AlertOut])
def upload_json(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.it_helpdesk, RoleEnum.analyst_soc))
):
    if not file.filename.endswith(".json"):
        raise HTTPException(400, "Chỉ chấp nhận file .json")
    content = json.loads(file.file.read().decode("utf-8-sig"))
    if not isinstance(content, list):
        raise HTTPException(400, "File JSON phải là một array")
    alerts = []
    for row in content:
        alert = Alert(
            title=row.get("title", "JSON Alert"),
            description=row.get("description"),
            source=resolve_source(row, AlertSource.csv_upload),
            severity=row.get("severity", "medium"),
            source_ref=row.get("source_ref"),
            ioc=row.get("ioc"),
            affected_asset=resolve_asset_id(db, row),
            raw_data=json.dumps(row),
            created_by=current_user.id
        )
        db.add(alert)
        alerts.append(alert)
    db.commit()
    for a in alerts:
        db.refresh(a)
        process_alert(a, db)
        score_alert_safe(db, a)
    return alerts

# Chấm điểm và chia vùng ưu tiên bằng AI (có thể chạy lại)
@router.post("/{alert_id}/score", response_model=AlertOut)
def rescore_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.it_helpdesk, RoleEnum.analyst_soc))
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(404, "Không tìm thấy cảnh báo")
    score_alert(db, alert)
    return alert

# Đóng cảnh báo không cần xử lý (ví dụ theo đề xuất tự đóng của AI) — chỉ Analyst
@router.patch("/{alert_id}/close", response_model=AlertOut)
def close_alert(
    alert_id: int,
    payload: AlertNote,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.analyst_soc))
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(404, "Không tìm thấy cảnh báo")
    if not payload.note.strip():
        raise HTTPException(400, "Cần ghi lý do đóng cảnh báo")
    if alert.status not in (AlertStatus.new, AlertStatus.reviewing, AlertStatus.triaged):
        raise HTTPException(400, f"Không thể đóng cảnh báo đang ở trạng thái '{alert.status.value}'")
    alert.status = AlertStatus.closed
    alert.triage_note = ((alert.triage_note + "\n") if alert.triage_note else "") + f"[Đóng] {payload.note.strip()}"
    db.commit()
    db.refresh(alert)
    return alert

# Mở lại cảnh báo đã đóng (kể cả cảnh báo bị luật tự đóng) — chỉ Analyst
@router.patch("/{alert_id}/reopen", response_model=AlertOut)
def reopen_alert(
    alert_id: int,
    payload: AlertNote,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.analyst_soc))
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(404, "Không tìm thấy cảnh báo")
    if not payload.note.strip():
        raise HTTPException(400, "Cần ghi lý do mở lại cảnh báo")
    if alert.status != AlertStatus.closed:
        raise HTTPException(400, "Chỉ mở lại được cảnh báo đã đóng")
    alert.status = AlertStatus.new
    alert.triage_note = ((alert.triage_note + "\n") if alert.triage_note else "") + f"[Mở lại] {payload.note.strip()}"
    db.commit()
    db.refresh(alert)
    return alert

# Đóng false positive
@router.patch("/{alert_id}/false-positive")
def mark_false_positive(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.analyst_soc))
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(404, "Không tìm thấy cảnh báo")
    if alert.status not in (AlertStatus.new, AlertStatus.reviewing, AlertStatus.triaged):
        raise HTTPException(
            400,
            f"Không thể đánh dấu false positive khi cảnh báo đang ở trạng thái '{alert.status.value}'"
        )
    alert.status = AlertStatus.false_positive
    db.commit()
    return {"message": "Đã đánh dấu false positive"}

@router.get("/groups/list")
def list_groups(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    groups = db.query(AlertGroup).order_by(AlertGroup.last_seen.desc()).all()
    return [
        {
            "id": g.id,
            "title": g.title,
            "ioc": g.ioc,
            "affected_asset": g.affected_asset,
            "alert_count": g.alert_count,
            "first_seen": g.first_seen,
            "last_seen": g.last_seen,
        }
        for g in groups
    ]

@router.patch("/{alert_id}/triage", response_model=AlertTriaged)
def triage_alert(
    alert_id: int,
    payload: TriageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        RoleEnum.analyst_soc, RoleEnum.it_helpdesk  # ← thêm it_helpdesk
    ))
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(404, "Không tìm thấy cảnh báo")
    if alert.status not in [AlertStatus.new, AlertStatus.reviewing]:
        raise HTTPException(400, f"Không thể triage alert ở trạng thái '{alert.status}'")

    # Validate confidence
    if not 1 <= payload.triage_confidence <= 100:
        raise HTTPException(400, "Độ tin cậy phải từ 1 đến 100")

    alert.triage_type        = payload.triage_type
    alert.triage_severity    = payload.triage_severity
    alert.triage_confidence  = payload.triage_confidence
    alert.triage_assignee    = payload.triage_assignee
    alert.triage_sla_hours   = payload.triage_sla_hours
    alert.triage_sla_deadline = (
        datetime.now(timezone.utc) + timedelta(hours=payload.triage_sla_hours)
    )
    alert.triage_note        = payload.triage_note
    alert.triaged_by         = current_user.id
    alert.triaged_at         = datetime.now(timezone.utc)
    alert.status             = AlertStatus.triaged

    db.commit()
    db.refresh(alert)
    return alert