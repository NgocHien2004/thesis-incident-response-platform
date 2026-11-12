import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from database import get_db
from app.core.dependencies import get_current_user
from app.core.paging import apply_page, page_response, chunks
from app.core.timeutils import utcnow
from app.core.constants import VERIFICATION_STATUSES, UPLOADABLE_STATUSES, TERMINAL_STATUSES, DATA_TYPES
from app.models.user import User
from app.models.incident import Incident
from app.models.alert import Alert, AlertMoveHistory
from app.models.upload import Upload
from app.schemas.alert import VerifyRequest, BulkVerifyRequest, MoveRequest, MoveOut
from app.api.incidents import get_incident_or_404

router = APIRouter(tags=["Alerts"])

SORTABLE = {"id", "row_index", "confidence", "created_at", "predicted_label", "verification_status", "source_type"}

def alert_dict(a: Alert, filename, code, verifier) -> dict:
    return {
        "id": a.id, "incident_id": a.incident_id, "incident_code": code, "upload_id": a.upload_id,
        "upload_filename": filename, "row_index": a.row_index, "predicted_label": a.predicted_label,
        "confidence": a.confidence, "source_type": a.source_type, "auto_linked": a.auto_linked,
        "linked_at": a.linked_at, "verification_status": a.verification_status,
        "verified_by": a.verified_by, "verified_by_name": verifier, "verified_at": a.verified_at,
        "note": a.note, "created_at": a.created_at,
    }

def base_query(db: Session):
    return (db.query(Alert, Upload.original_filename, Incident.code, User.full_name)
            .join(Upload, Upload.id == Alert.upload_id)
            .outerjoin(Incident, Incident.id == Alert.incident_id)
            .outerjoin(User, User.id == Alert.verified_by))

def list_alerts(db, incident_id, unassigned, page, page_size, sort_by, order, label, verification_status,
                source_type, upload_id, min_confidence):
    if sort_by not in SORTABLE:
        raise HTTPException(422, "sort_by không hợp lệ")
    if verification_status and verification_status not in VERIFICATION_STATUSES:
        raise HTTPException(422, "Trạng thái xác minh không hợp lệ")
    if source_type and source_type not in DATA_TYPES:
        raise HTTPException(422, "Nguồn không hợp lệ")
    q = base_query(db)
    if incident_id is not None:
        q = q.filter(Alert.incident_id == incident_id)
    if unassigned:
        q = q.filter(Alert.incident_id.is_(None))
    if label:
        q = q.filter(Alert.predicted_label == label)
    if verification_status:
        q = q.filter(Alert.verification_status == verification_status)
    if source_type:
        q = q.filter(Alert.source_type == source_type)
    if upload_id is not None:
        q = q.filter(Alert.upload_id == upload_id)
    if min_confidence is not None:
        q = q.filter(Alert.confidence >= min_confidence)
    col = getattr(Alert, sort_by)
    rows, total = apply_page(q, [col.asc() if order == "asc" else col.desc(), Alert.id.asc()], page, page_size)
    items = [alert_dict(a, f, c, v) for a, f, c, v in rows]
    return page_response(items, total, page, page_size)

@router.get("/incidents/{incident_id}/alerts")
def incident_alerts(
    incident_id: int, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=500),
    sort_by: str = "row_index", order: str = Query("asc", pattern="^(asc|desc)$"),
    label: Optional[str] = None, verification_status: Optional[str] = None, source_type: Optional[str] = None,
    upload_id: Optional[int] = None, min_confidence: Optional[float] = Query(None, ge=0, le=1),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    get_incident_or_404(db, incident_id)
    return list_alerts(db, incident_id, False, page, page_size, sort_by, order, label, verification_status,
                       source_type, upload_id, min_confidence)

@router.get("/alerts")
def all_alerts(
    unassigned: bool = False, incident_id: Optional[int] = None,
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=500),
    sort_by: str = "created_at", order: str = Query("desc", pattern="^(asc|desc)$"),
    label: Optional[str] = None, verification_status: Optional[str] = None, source_type: Optional[str] = None,
    upload_id: Optional[int] = None, min_confidence: Optional[float] = Query(None, ge=0, le=1),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    return list_alerts(db, incident_id, unassigned, page, page_size, sort_by, order, label, verification_status,
                       source_type, upload_id, min_confidence)

@router.get("/alerts/{alert_id}")
def get_alert(alert_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = base_query(db).filter(Alert.id == alert_id).first()
    if not row:
        raise HTTPException(404, "Không tìm thấy cảnh báo")
    a, f, c, v = row
    data = alert_dict(a, f, c, v)
    data["row_data"] = json.loads(a.row_data) if a.row_data else None
    return data

@router.get("/alerts/{alert_id}/moves", response_model=list[MoveOut])
def alert_moves(alert_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not db.get(Alert, alert_id):
        raise HTTPException(404, "Không tìm thấy cảnh báo")
    rows = (db.query(AlertMoveHistory, User.full_name).outerjoin(User, User.id == AlertMoveHistory.moved_by)
            .filter(AlertMoveHistory.alert_id == alert_id)
            .order_by(AlertMoveHistory.moved_at.asc(), AlertMoveHistory.id.asc()).all())
    return [{"id": m.id, "alert_id": m.alert_id, "from_incident_id": m.from_incident_id,
             "to_incident_id": m.to_incident_id, "moved_by": m.moved_by, "moved_by_name": n,
             "moved_at": m.moved_at, "reason": m.reason} for m, n in rows]

def load_alerts(db: Session, ids: list) -> dict:
    found = {}
    for part in chunks(ids, 500):
        for a in db.query(Alert).filter(Alert.id.in_(part)).all():
            found[a.id] = a
    missing = [i for i in ids if i not in found]
    if missing:
        raise HTTPException(404, f"Không tìm thấy cảnh báo: {missing[:20]}")
    return found

def incident_status_map(db: Session, alerts) -> dict:
    ids = {a.incident_id for a in alerts if a.incident_id is not None}
    out = {}
    for part in chunks(ids, 500):
        for i in db.query(Incident).filter(Incident.id.in_(part)).all():
            out[i.id] = i
    return out

def reject(problems: list):
    raise HTTPException(409, {"message": f"{len(problems)} cảnh báo không thực hiện được; không có thay đổi nào được lưu",
                              "items": problems[:50]})

def apply_verify(db: Session, ids: list, status: str, note, user: User) -> int:
    if status not in VERIFICATION_STATUSES:
        raise HTTPException(422, "Trạng thái xác minh phải là verified, dismissed hoặc unverified")
    ids = list(dict.fromkeys(ids))
    found = load_alerts(db, ids)
    incs = incident_status_map(db, found.values())
    problems = []
    for i in ids:
        a = found[i]
        if a.incident_id is None:
            problems.append({"id": i, "reason": "Cảnh báo chưa gắn sự cố, hãy chuyển vào một sự cố trước"})
        elif incs[a.incident_id].status in TERMINAL_STATUSES:
            problems.append({"id": i, "reason": f"Sự cố {incs[a.incident_id].code} đã đóng hoặc đã hủy"})
    if problems:
        reject(problems)
    now = utcnow()
    for i in ids:
        a = found[i]
        a.verification_status = status
        a.verified_by = None if status == "unverified" else user.id
        a.verified_at = None if status == "unverified" else now
        if note is not None:
            a.note = note
    db.commit()
    return len(ids)

@router.patch("/alerts/{alert_id}/verify")
def verify_alert(alert_id: int, payload: VerifyRequest, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    apply_verify(db, [alert_id], payload.status, payload.note, user)
    return get_alert(alert_id, db, user)

@router.post("/alerts/bulk-verify")
def bulk_verify(payload: BulkVerifyRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    n = apply_verify(db, payload.alert_ids, payload.status, payload.note, user)
    return {"updated": n, "status": payload.status}

@router.post("/alerts/move")
def move_alerts(payload: MoveRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ids = list(dict.fromkeys(payload.alert_ids))
    target = None
    if payload.to_incident_id is not None:
        target = get_incident_or_404(db, payload.to_incident_id)
        if target.status not in UPLOADABLE_STATUSES:
            raise HTTPException(409, f"Sự cố đích {target.code} không nhận thêm cảnh báo (cần ở trạng thái Mới hoặc Đang xử lý)")
    found = load_alerts(db, ids)
    incs = incident_status_map(db, found.values())
    problems = []
    for i in ids:
        a = found[i]
        if a.incident_id == payload.to_incident_id:
            problems.append({"id": i, "reason": "Cảnh báo đã ở đúng vị trí này" if target else "Cảnh báo chưa gắn sự cố nào"})
        elif a.incident_id is not None and incs[a.incident_id].status in TERMINAL_STATUSES:
            problems.append({"id": i, "reason": f"Sự cố {incs[a.incident_id].code} đã đóng hoặc đã hủy"})
    if problems:
        reject(problems)
    now = utcnow()
    for i in ids:
        a = found[i]
        db.add(AlertMoveHistory(alert_id=a.id, from_incident_id=a.incident_id,
                                to_incident_id=payload.to_incident_id, moved_by=user.id,
                                moved_at=now, reason=(payload.reason or "").strip() or None))
        a.incident_id = payload.to_incident_id
        a.auto_linked = False
        a.linked_at = now if target else None
    db.commit()
    return {"moved": len(ids), "to_incident_id": payload.to_incident_id}
