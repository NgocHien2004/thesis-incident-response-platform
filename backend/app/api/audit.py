import csv
import io
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from database import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.core.audit import verify_chain, label_for
from app.core.dependencies import require_analyst

router = APIRouter(prefix="/audit", tags=["Audit"])


def _filtered(db, incident_id, username, action, entity_type, since, until):
    q = db.query(AuditLog)
    if incident_id is not None:
        q = q.filter(AuditLog.incident_id == incident_id)
    if username:
        q = q.filter(AuditLog.username == username)
    if action:
        q = q.filter(AuditLog.action.like(action + "%"))
    if entity_type:
        q = q.filter(AuditLog.entity_type == entity_type)
    if since:
        q = q.filter(AuditLog.at >= since)
    if until:
        q = q.filter(AuditLog.at <= until)
    return q


def _item(r):
    detail = json.loads(r.detail) if r.detail else {}
    return {
        "id": r.id, "at": r.at, "user_id": r.user_id, "username": r.username, "role": r.role,
        "action": r.action, "label": label_for(r.action, detail),
        "entity_type": r.entity_type, "entity_id": r.entity_id,
        "incident_id": r.incident_id, "detail": detail,
    }


@router.get("/")
def list_audit(
    incident_id: Optional[int] = None,
    username: Optional[str] = None,
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_analyst),
):
    q = _filtered(db, incident_id, username, action, entity_type, since, until)
    total = q.count()
    rows = q.order_by(AuditLog.id.desc()).offset(max(offset, 0)).limit(min(max(limit, 1), 500)).all()
    return {"total": total, "items": [_item(r) for r in rows]}


@router.get("/verify")
def verify_audit(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_analyst),
):
    return verify_chain(db)


@router.get("/export.csv")
def export_audit(
    incident_id: Optional[int] = None,
    username: Optional[str] = None,
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_analyst),
):
    rows = _filtered(db, incident_id, username, action, entity_type, since, until) \
        .order_by(AuditLog.id.asc()).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "thoi_gian_utc", "nguoi_dung", "vai_tro", "hanh_dong", "doi_tuong",
                     "ma_doi_tuong", "incident", "chi_tiet", "row_hash"])
    for r in rows:
        writer.writerow([r.id, r.at.isoformat(), r.username, r.role, r.action, r.entity_type,
                         r.entity_id, r.incident_id, r.detail or "", r.row_hash])
    data = "\ufeff" + buf.getvalue()
    return StreamingResponse(
        iter([data.encode("utf-8")]), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=audit_log.csv"},
    )
