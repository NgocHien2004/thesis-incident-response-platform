from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
import json, csv, io
from database import get_db
from app.models.alert import Alert, AlertSource, AlertStatus
from app.schemas.alert import AlertCreate, AlertOut
from app.core.dependencies import get_current_user, require_roles
from app.models.user import RoleEnum, User
from app.services.dedup import process_alert
from app.models.alert_group import AlertGroup


router = APIRouter(prefix="/alerts", tags=["Alerts"])

# Xem danh sách
@router.get("/", response_model=List[AlertOut])
def list_alerts(
    status: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Alert)
    if status:
        query = query.filter(Alert.status == status)
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
        source=AlertSource.webhook,
        severity=payload.get("severity", "medium"),
        source_ref=payload.get("source_ref"),
        ioc=payload.get("ioc"),
        raw_data=json.dumps(payload),
        created_by=current_user.id
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    alert = process_alert(alert, db)
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
    content = file.file.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))
    alerts = []
    for row in reader:
        alert = Alert(
            title=row.get("title", "CSV Alert"),
            description=row.get("description"),
            source=AlertSource.csv_upload,
            severity=row.get("severity", "medium"),
            source_ref=row.get("source_ref"),
            ioc=row.get("ioc"),
            raw_data=json.dumps(row),
            created_by=current_user.id
        )
        db.add(alert)
        alerts.append(alert)
    db.commit()
    for a in alerts:
        db.refresh(a)
        alert = process_alert(alert, db)
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
    content = json.loads(file.file.read().decode("utf-8"))
    if not isinstance(content, list):
        raise HTTPException(400, "File JSON phải là một array")
    alerts = []
    for row in content:
        alert = Alert(
            title=row.get("title", "JSON Alert"),
            description=row.get("description"),
            source=AlertSource.csv_upload,
            severity=row.get("severity", "medium"),
            source_ref=row.get("source_ref"),
            ioc=row.get("ioc"),
            raw_data=json.dumps(row),
            created_by=current_user.id
        )
        db.add(alert)
        alerts.append(alert)
    db.commit()
    for a in alerts:
        db.refresh(a)
        alert = process_alert(alert, db)
    return alerts

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