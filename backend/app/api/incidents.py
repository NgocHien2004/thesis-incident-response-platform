from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from database import get_db
from app.core.dependencies import get_current_user
from app.core.paging import apply_page, page_response
from app.core.timeutils import utcnow
from app.core.constants import (INCIDENT_STATUSES, INCIDENT_TRANSITIONS, SEVERITIES, INCIDENT_SOURCES,
                                BLOCKED_WHILE_PROCESSING, NOTE_REQUIRED)
from app.models.user import User
from app.models.incident import Incident, AttackType, IncidentStatusHistory
from app.models.alert import Alert
from app.models.upload import Upload
from app.schemas.incident import (IncidentCreate, IncidentUpdate, StatusChange, IncidentOut,
                                  IncidentDetail, HistoryOut)

router = APIRouter(prefix="/incidents", tags=["Incidents"])

SORTABLE = {"id", "code", "title", "severity", "status", "attack_type", "occurred_at", "created_at", "updated_at"}
SEVERITY_RANK = case({"low": 1, "medium": 2, "high": 3, "critical": 4}, value=Incident.severity, else_=0)

def to_utc_naive(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt

def parse_date(value: Optional[str], end_of_day: bool = False) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        raise HTTPException(422, f"Ngày giờ không hợp lệ: {value}")
    dt = to_utc_naive(dt)
    if end_of_day and len(value) == 10:
        dt += timedelta(days=1) - timedelta(microseconds=1)
    return dt

def get_incident_or_404(db: Session, incident_id: int) -> Incident:
    inc = db.get(Incident, incident_id)
    if not inc:
        raise HTTPException(404, "Không tìm thấy sự cố")
    return inc

def check_fields(db: Session, attack_type=None, severity=None, source=None):
    if attack_type is not None:
        at = db.get(AttackType, attack_type)
        if not at or not at.is_active:
            raise HTTPException(422, "Loại tấn công không tồn tại hoặc đã ngừng dùng")
    if severity is not None and severity not in SEVERITIES:
        raise HTTPException(422, "Mức độ phải là một trong: " + ", ".join(SEVERITIES))
    if source is not None and source not in INCIDENT_SOURCES:
        raise HTTPException(422, "Nguồn phải là một trong: " + ", ".join(INCIDENT_SOURCES))

def next_code(db: Session) -> str:
    prefix = f"INC-{utcnow().year}-"
    nums = []
    for (c,) in db.query(Incident.code).filter(Incident.code.like(prefix + "%")).all():
        tail = c[len(prefix):]
        if tail.isdigit():
            nums.append(int(tail))
    return f"{prefix}{(max(nums) + 1 if nums else 1):04d}"

def _counts(db: Session, ids: list) -> tuple:
    a, u = {}, {}
    if ids:
        a = dict(db.query(Alert.incident_id, func.count(Alert.id)).filter(Alert.incident_id.in_(ids))
                 .group_by(Alert.incident_id).all())
        u = dict(db.query(Upload.incident_id, func.count(Upload.id)).filter(Upload.incident_id.in_(ids))
                 .group_by(Upload.incident_id).all())
    return a, u

def _out(inc: Incident, names: dict, type_names: dict, a: dict, u: dict) -> dict:
    return {
        "id": inc.id, "code": inc.code, "title": inc.title, "description": inc.description,
        "attack_type": inc.attack_type, "attack_type_name": type_names.get(inc.attack_type),
        "severity": inc.severity, "occurred_at": inc.occurred_at, "source": inc.source,
        "status": inc.status, "created_by": inc.created_by, "created_by_name": names.get(inc.created_by),
        "created_at": inc.created_at, "updated_at": inc.updated_at,
        "resolved_at": inc.resolved_at, "closed_at": inc.closed_at,
        "alert_count": a.get(inc.id, 0), "upload_count": u.get(inc.id, 0),
    }

def _maps(db: Session, incs: list) -> tuple:
    uids = {i.created_by for i in incs}
    names = {r.id: r.full_name for r in db.query(User).filter(User.id.in_(uids))} if uids else {}
    type_names = {r.code: r.name_vi for r in db.query(AttackType).all()}
    return names, type_names

def has_alerts(db: Session, incident_id: int) -> bool:
    if db.query(Alert.id).filter(Alert.incident_id == incident_id).first():
        return True
    # Cảnh báo sinh từ file của sự cố này nhưng đã được chuyển đi nơi khác
    return db.query(Alert.id).join(Upload, Upload.id == Alert.upload_id).filter(Upload.incident_id == incident_id).first() is not None

def processing_count(db: Session, incident_id: int) -> int:
    return db.query(Upload).filter(Upload.incident_id == incident_id,
                                   Upload.status.in_(("pending", "processing"))).count()

@router.post("", response_model=IncidentOut, status_code=201)
def create_incident(payload: IncidentCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    check_fields(db, payload.attack_type, payload.severity, payload.source)
    for attempt in range(3):
        inc = Incident(code=next_code(db), title=payload.title.strip(), description=payload.description,
                       attack_type=payload.attack_type, severity=payload.severity,
                       occurred_at=to_utc_naive(payload.occurred_at), source=payload.source,
                       status="new", created_by=user.id)
        db.add(inc)
        try:
            db.flush()
            break
        except IntegrityError:
            db.rollback()
            if attempt == 2:
                raise HTTPException(409, "Không sinh được mã sự cố, thử lại")
    db.add(IncidentStatusHistory(incident_id=inc.id, old_status=None, new_status="new",
                                 changed_by=user.id, note="Tạo sự cố"))
    db.commit()
    db.refresh(inc)
    names, type_names = _maps(db, [inc])
    return _out(inc, names, type_names, {}, {})

@router.get("")
def list_incidents(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
    sort_by: str = "created_at", order: str = Query("desc", pattern="^(asc|desc)$"),
    q: Optional[str] = None, status: Optional[str] = None, attack_type: Optional[str] = None,
    severity: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    if sort_by not in SORTABLE:
        raise HTTPException(422, "sort_by không hợp lệ")
    query = db.query(Incident)
    if q and q.strip():
        term = q.strip()
        query = query.filter(Incident.code.icontains(term, autoescape=True) | Incident.title.icontains(term, autoescape=True))
    if status:
        statuses = [s for s in status.split(",") if s]
        if any(s not in INCIDENT_STATUSES for s in statuses):
            raise HTTPException(422, "Trạng thái không hợp lệ")
        query = query.filter(Incident.status.in_(statuses))
    if attack_type:
        query = query.filter(Incident.attack_type == attack_type)
    if severity:
        query = query.filter(Incident.severity == severity)
    d_from, d_to = parse_date(date_from), parse_date(date_to, end_of_day=True)
    if d_from:
        query = query.filter(Incident.occurred_at >= d_from)
    if d_to:
        query = query.filter(Incident.occurred_at <= d_to)
    col = SEVERITY_RANK if sort_by == "severity" else getattr(Incident, sort_by)
    direction = col.asc() if order == "asc" else col.desc()
    rows, total = apply_page(query, [direction, Incident.id.desc()], page, page_size)
    names, type_names = _maps(db, rows)
    a, u = _counts(db, [r.id for r in rows])
    return page_response([_out(r, names, type_names, a, u) for r in rows], total, page, page_size)

@router.get("/{incident_id}", response_model=IncidentDetail)
def get_incident(incident_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    inc = get_incident_or_404(db, incident_id)
    names, type_names = _maps(db, [inc])
    a, u = _counts(db, [inc.id])
    data = _out(inc, names, type_names, a, u)
    by_status = dict(db.query(Alert.verification_status, func.count(Alert.id))
                     .filter(Alert.incident_id == inc.id).group_by(Alert.verification_status).all())
    proc = processing_count(db, inc.id)
    allowed = sorted(INCIDENT_TRANSITIONS[inc.status])
    if proc:
        allowed = [s for s in allowed if s not in BLOCKED_WHILE_PROCESSING]
    data.update({
        "unverified_alerts": by_status.get("unverified", 0), "verified_alerts": by_status.get("verified", 0),
        "dismissed_alerts": by_status.get("dismissed", 0), "processing_uploads": proc,
        "allowed_transitions": allowed, "can_delete": not has_alerts(db, inc.id),
    })
    return data

@router.put("/{incident_id}", response_model=IncidentOut)
def update_incident(incident_id: int, payload: IncidentUpdate, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    inc = get_incident_or_404(db, incident_id)
    if inc.status in ("closed", "cancelled"):
        raise HTTPException(409, "Sự cố đã đóng hoặc đã hủy, không sửa được")
    data = payload.model_dump(exclude_unset=True)
    if "attack_type" in data and data["attack_type"] == inc.attack_type:
        data.pop("attack_type")
    check_fields(db, data.get("attack_type"), data.get("severity"), data.get("source"))
    for field in ("title", "attack_type", "severity", "source", "description"):
        if field in data:
            if field in ("title", "attack_type", "severity", "source") and data[field] is None:
                raise HTTPException(422, f"{field} không được để trống")
            setattr(inc, field, data[field].strip() if field == "title" else data[field])
    if "occurred_at" in data:
        if data["occurred_at"] is None:
            raise HTTPException(422, "occurred_at không được để trống")
        inc.occurred_at = to_utc_naive(data["occurred_at"])
    inc.updated_at = utcnow()
    db.commit()
    db.refresh(inc)
    names, type_names = _maps(db, [inc])
    a, u = _counts(db, [inc.id])
    return _out(inc, names, type_names, a, u)

@router.patch("/{incident_id}/status", response_model=IncidentOut)
def change_status(incident_id: int, payload: StatusChange, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    inc = get_incident_or_404(db, incident_id)
    new, old = payload.new_status, inc.status
    if new not in INCIDENT_STATUSES:
        raise HTTPException(422, "Trạng thái không hợp lệ")
    if new not in INCIDENT_TRANSITIONS[old]:
        allowed = ", ".join(sorted(INCIDENT_TRANSITIONS[old])) or "không có"
        raise HTTPException(409, f"Không chuyển được từ {old} sang {new}. Cho phép: {allowed}")
    note = (payload.note or "").strip()
    if (old, new) in NOTE_REQUIRED and len(note) < 3:
        raise HTTPException(422, "Cần ghi lý do khi hủy hoặc mở lại sự cố")
    if new in BLOCKED_WHILE_PROCESSING and processing_count(db, inc.id):
        raise HTTPException(409, "Còn file đang xử lý, hãy đợi xong rồi mới chuyển trạng thái")
    now = utcnow()
    inc.status = new
    inc.updated_at = now
    if new == "resolved":
        inc.resolved_at = now
    elif new == "closed":
        inc.closed_at = now
    elif new == "in_progress" and old == "resolved":
        inc.resolved_at = None
    db.add(IncidentStatusHistory(incident_id=inc.id, old_status=old, new_status=new,
                                 changed_by=user.id, changed_at=now, note=note or None))
    db.commit()
    db.refresh(inc)
    names, type_names = _maps(db, [inc])
    a, u = _counts(db, [inc.id])
    return _out(inc, names, type_names, a, u)

@router.get("/{incident_id}/history", response_model=list[HistoryOut])
def status_history(incident_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_incident_or_404(db, incident_id)
    rows = (db.query(IncidentStatusHistory, User.full_name)
            .outerjoin(User, User.id == IncidentStatusHistory.changed_by)
            .filter(IncidentStatusHistory.incident_id == incident_id)
            .order_by(IncidentStatusHistory.changed_at.asc(), IncidentStatusHistory.id.asc()).all())
    return [{"id": h.id, "incident_id": h.incident_id, "old_status": h.old_status, "new_status": h.new_status,
             "changed_by": h.changed_by, "changed_by_name": n, "changed_at": h.changed_at, "note": h.note}
            for h, n in rows]

@router.delete("/{incident_id}", status_code=204)
def delete_incident(incident_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    inc = get_incident_or_404(db, incident_id)
    if has_alerts(db, inc.id):
        raise HTTPException(409, "Sự cố đã có cảnh báo, không xóa được. Hãy hủy hoặc đóng sự cố")
    if processing_count(db, inc.id):
        raise HTTPException(409, "Còn file đang xử lý, hãy đợi xong rồi mới xóa")
    from app.api.uploads import delete_upload_files
    delete_upload_files(db, inc.id)
    db.query(IncidentStatusHistory).filter(IncidentStatusHistory.incident_id == inc.id).delete()
    db.delete(inc)
    db.commit()
