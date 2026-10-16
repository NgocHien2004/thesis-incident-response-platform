import enum
import json
import hashlib
from datetime import datetime

from sqlalchemy import event, inspect, select, insert
from sqlalchemy.orm import Session

from app.core.timeutils import utcnow
from app.models.audit_log import AuditLog
from app.models.asset import Asset
from app.models.alert import Alert
from app.models.incident import Incident
from app.models.evidence import Evidence, ChainOfCustody
from app.models.impact import ImpactAnalysis
from app.models.containment import Containment
from app.models.recovery import RecoveryAction
from app.models.communication import Communication
from app.models.postmortem import Postmortem

GENESIS = "0" * 64

TRACKED = {
    Asset: "asset",
    Alert: "alert",
    Incident: "incident",
    Evidence: "evidence",
    ChainOfCustody: "custody",
    ImpactAnalysis: "impact",
    Containment: "containment",
    RecoveryAction: "recovery",
    Communication: "communication",
    Postmortem: "postmortem",
}

# Các cột do hệ thống tự cập nhật, không đáng ghi nhật ký
NOISE = {
    "*": {"updated_at", "created_at"},
    "alert": {"group_id", "ioc", "title"},
}
SKIP_ON_CREATE = {"id", "created_at", "updated_at", "content", "raw_data", "description"}


def _clip(value, limit=160):
    if isinstance(value, enum.Enum):
        value = value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray)):
        return None
    if isinstance(value, str) and len(value) > limit:
        return value[:limit] + "…"
    return value


def _canonical(row):
    return "|".join([
        row["prev_hash"],
        row["at"].strftime("%Y-%m-%dT%H:%M:%S"),
        str(row["user_id"] or ""),
        row["username"] or "",
        row["role"] or "",
        row["action"],
        row["entity_type"],
        str(row["entity_id"] or ""),
        str(row["incident_id"] or ""),
        row["detail"] or "",
    ])


def compute_hash(row):
    return hashlib.sha256(_canonical(row).encode("utf-8")).hexdigest()


def _append(conn, rows):
    prev = conn.execute(
        select(AuditLog.row_hash).order_by(AuditLog.id.desc()).limit(1)
    ).scalar() or GENESIS
    for row in rows:
        row["prev_hash"] = prev
        row["row_hash"] = compute_hash(row)
        prev = row["row_hash"]
        conn.execute(insert(AuditLog.__table__).values(**row))


def _semantic_action(entity, kind, changes):
    if kind in ("created", "deleted"):
        return f"{entity}.{kind}"
    if "status" in changes:
        return f"{entity}.{changes['status'][1]}"
    flags = {
        "evidence": ("is_locked", "locked"),
        "communication": ("is_approved", "approved"),
        "recovery": ("is_confirmed", "confirmed"),
        "postmortem": ("is_finalized", "finalized"),
    }
    if entity in flags:
        col, name = flags[entity]
        if changes.get(col, [None, None])[1] is True:
            return f"{entity}.{name}"
    return f"{entity}.updated"


def _incident_of(conn, entity, obj):
    if entity == "incident":
        return obj.id
    if entity == "asset":
        return None
    if entity == "custody":
        return conn.execute(
            select(Evidence.incident_id).where(Evidence.id == obj.evidence_id)
        ).scalar()
    return getattr(obj, "incident_id", None)


def _changes(obj, entity):
    ignored = NOISE["*"] | NOISE.get(entity, set())
    out = {}
    for attr in inspect(obj).mapper.column_attrs:
        if attr.key in ignored:
            continue
        hist = inspect(obj).attrs[attr.key].history
        if not hist.has_changes():
            continue
        old = hist.deleted[0] if hist.deleted else None
        new = hist.added[0] if hist.added else None
        out[attr.key] = [_clip(old), _clip(new)]
    return out


def _created(obj):
    out = {}
    for attr in inspect(obj).mapper.column_attrs:
        if attr.key in SKIP_ON_CREATE:
            continue
        value = _clip(getattr(obj, attr.key, None))
        if value is not None:
            out[attr.key] = value
    return out


@event.listens_for(Session, "after_flush")
def _audit_after_flush(session, flush_context):
    if session.info.get("audit_disabled"):
        return
    actor = session.info.get("actor") or {}
    note = session.info.pop("audit_note", None)
    conn = session.connection()
    now = utcnow().replace(microsecond=0)
    rows = []

    def add(entity, obj, kind, detail):
        changes = detail if kind == "updated" else {}
        rows.append({
            "at": now,
            "user_id": actor.get("id"),
            "username": actor.get("username", "system"),
            "role": actor.get("role"),
            "action": _semantic_action(entity, kind, changes),
            "entity_type": entity,
            "entity_id": obj.id,
            "incident_id": _incident_of(conn, entity, obj),
            "detail": json.dumps(
                ({"note": note} if note else {}) | detail if detail or note else {},
                ensure_ascii=False,
            ) or None,
        })

    for obj in list(session.new):
        entity = TRACKED.get(type(obj))
        if entity:
            add(entity, obj, "created", _created(obj))
    for obj in list(session.dirty):
        entity = TRACKED.get(type(obj))
        if entity and session.is_modified(obj, include_collections=False):
            changes = _changes(obj, entity)
            if changes:
                add(entity, obj, "updated", changes)
    for obj in list(session.deleted):
        entity = TRACKED.get(type(obj))
        if entity:
            add(entity, obj, "deleted", {})
    if rows:
        _append(conn, rows)


def log_event(db, action, user=None, username=None, entity_type="auth",
              entity_id=None, incident_id=None, detail=None):
    row = {
        "at": utcnow().replace(microsecond=0),
        "user_id": getattr(user, "id", None),
        "username": getattr(user, "username", None) or username,
        "role": getattr(getattr(user, "role", None), "value", None),
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "incident_id": incident_id,
        "detail": json.dumps(detail, ensure_ascii=False) if detail else None,
    }
    _append(db.connection(), [row])


def verify_chain(db):
    rows = db.query(AuditLog).order_by(AuditLog.id.asc()).all()
    prev = GENESIS
    for r in rows:
        data = {
            "prev_hash": r.prev_hash, "at": r.at, "user_id": r.user_id,
            "username": r.username, "role": r.role, "action": r.action,
            "entity_type": r.entity_type, "entity_id": r.entity_id,
            "incident_id": r.incident_id, "detail": r.detail,
        }
        if r.prev_hash != prev or compute_hash(data) != r.row_hash:
            return {"ok": False, "total": len(rows), "first_bad_id": r.id}
        prev = r.row_hash
    return {"ok": True, "total": len(rows), "first_bad_id": None}


LABELS = {
    "alert.created": "Cảnh báo được tạo",
    "alert.triaged": "Cảnh báo đã triage",
    "alert.escalated": "Cảnh báo được nâng thành incident",
    "alert.false_positive": "Cảnh báo được đánh dấu báo nhầm",
    "alert.closed": "Cảnh báo được đóng",
    "incident.created": "Incident được tạo",
    "incident.open": "Incident mở lại",
    "incident.investigating": "Bắt đầu điều tra",
    "incident.contained": "Đã khống chế",
    "incident.recovering": "Chuyển sang phục hồi",
    "incident.closed": "Incident đã đóng",
    "incident.updated": "Cập nhật thông tin incident",
    "evidence.created": "Thu thập bằng chứng",
    "evidence.locked": "Khóa bằng chứng",
    "custody.created": "Nhật ký chain of custody",
    "impact.created": "Ghi phân tích phạm vi ảnh hưởng",
    "impact.updated": "Cập nhật phân tích phạm vi",
    "containment.created": "Đề xuất containment",
    "containment.approved": "Phê duyệt containment",
    "containment.rejected": "Từ chối containment",
    "containment.executed": "Thực hiện containment",
    "containment.verified": "Xác minh containment",
    "recovery.created": "Tạo hành động recovery",
    "recovery.in_progress": "Recovery đang thực hiện",
    "recovery.done": "Recovery hoàn tất",
    "recovery.failed": "Recovery thất bại",
    "recovery.confirmed": "Chủ hệ thống xác nhận recovery",
    "communication.created": "Soạn thông báo",
    "communication.approved": "Phê duyệt nội dung thông báo",
    "communication.sent": "Gửi thông báo",
    "communication.acknowledged": "Bên nhận xác nhận thông báo",
    "postmortem.created": "Tạo postmortem",
    "postmortem.updated": "Cập nhật postmortem",
    "postmortem.finalized": "Chốt postmortem",
}


def label_for(action, detail):
    if action == "custody.created":
        sub = (detail or {}).get("action")
        names = {"collected": "thu thập", "accessed": "truy cập xem", "locked": "khóa"}
        return f"Chain of custody: {names.get(sub, sub or 'ghi nhận')}"
    return LABELS.get(action, action)
