from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone
import json
from database import get_db
from app.models.incident import Incident, IncidentStatus, IncidentSeverity
from app.models.alert import Alert, AlertStatus
from app.models.postmortem import Postmortem
from app.core.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

def _minutes_between(start, end) -> float:
    """Tính số phút giữa 2 datetime, trả về None nếu thiếu dữ liệu."""
    if not start or not end:
        return None
    start = start.replace(tzinfo=timezone.utc) if start.tzinfo is None else start
    end   = end.replace(tzinfo=timezone.utc)   if end.tzinfo is None   else end
    return round((end - start).total_seconds() / 60, 1)

@router.get("/")
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    now = datetime.now(timezone.utc)
    incidents = db.query(Incident).all()
    alerts    = db.query(Alert).all()

    # ── Số vụ theo trạng thái ──
    open_incidents     = [i for i in incidents if i.status != IncidentStatus.closed]
    closed_incidents   = [i for i in incidents if i.status == IncidentStatus.closed]

    by_status = {}
    for s in IncidentStatus:
        by_status[s.value] = sum(1 for i in incidents if i.status == s)

    by_severity = {}
    for s in IncidentSeverity:
        by_severity[s.value] = sum(
            1 for i in open_incidents if i.severity == s
        )

    # ── MTTD (phút): detected_at - created_at của alert đầu tiên ──
    mttd_list = []
    for i in closed_incidents:
        # Lấy alert cũ nhất gắn với incident
        first_alert = (
            db.query(Alert)
            .filter(Alert.incident_id == i.id)
            .order_by(Alert.created_at.asc())
            .first()
        )
        if first_alert and i.detected_at:
            mins = _minutes_between(first_alert.created_at, i.detected_at)
            if mins is not None:
                mttd_list.append(mins)

    # ── MTTA (phút): detected_at → triaged_at của alert đầu tiên ──
    mtta_list = []
    for i in incidents:
        first_alert = (
            db.query(Alert)
            .filter(Alert.incident_id == i.id)
            .order_by(Alert.created_at.asc())
            .first()
        )
        if first_alert and first_alert.triaged_at and i.detected_at:
            mins = _minutes_between(i.detected_at, first_alert.triaged_at)
            if mins is not None:
                mtta_list.append(mins)

    # ── MTTR (phút): detected_at → resolved_at ──
    mttr_list = []
    for i in closed_incidents:
        if i.detected_at and i.resolved_at:
            mins = _minutes_between(i.detected_at, i.resolved_at)
            if mins is not None:
                mttr_list.append(mins)

    def avg(lst):
        return round(sum(lst) / len(lst), 1) if lst else None

    # ── Lỗi lặp: incident cùng loại xảy ra lại sau khi đã closed ──
    repeat_incidents = 0
    closed_root_causes = [
        i.root_cause for i in closed_incidents if i.root_cause
    ]
    for i in open_incidents:
        if i.root_cause and i.root_cause in closed_root_causes:
            repeat_incidents += 1

    # ── % hoàn thành action items postmortem ──
    all_items  = 0
    done_items = 0
    postmortems = db.query(Postmortem).all()
    for pm in postmortems:
        items = json.loads(pm.action_items or "[]")
        all_items  += len(items)
        done_items += sum(1 for it in items if it.get("done"))

    action_completion_pct = (
        round(done_items / all_items * 100, 1) if all_items > 0 else None
    )

    # ── SLA: cảnh báo quá hạn ──
    sla_breached = sum(
        1 for a in alerts
        if a.triage_sla_deadline
        and a.status not in [AlertStatus.closed, AlertStatus.false_positive]
        and a.triage_sla_deadline.replace(tzinfo=timezone.utc) < now
    )

    # ── Alert stats ──
    alert_by_status = {}
    for s in AlertStatus:
        alert_by_status[s.value] = sum(1 for a in alerts if a.status == s)

    return {
        "incidents": {
            "total": len(incidents),
            "open": len(open_incidents),
            "closed": len(closed_incidents),
            "by_status": by_status,
            "open_by_severity": by_severity,
        },
        "metrics": {
            "mttd_minutes": avg(mttd_list),
            "mtta_minutes": avg(mtta_list),
            "mttr_minutes": avg(mttr_list),
            "repeat_incidents": repeat_incidents,
            "sla_breached_alerts": sla_breached,
            "action_item_completion_pct": action_completion_pct,
        },
        "alerts": {
            "total": len(alerts),
            "by_status": alert_by_status,
        },
        "generated_at": now.isoformat(),
    }

@router.get("/sla")
def get_sla_detail(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Danh sách cảnh báo đang tiệm cận hoặc đã vượt SLA."""
    now = datetime.now(timezone.utc)
    alerts = db.query(Alert).filter(
        Alert.triage_sla_deadline.isnot(None),
        Alert.status.notin_([AlertStatus.closed, AlertStatus.false_positive])
    ).all()

    result = []
    for a in alerts:
        deadline = a.triage_sla_deadline.replace(tzinfo=timezone.utc)
        remaining = (deadline - now).total_seconds() / 60
        result.append({
            "alert_id": a.id,
            "title": a.title,
            "severity": a.severity,
            "sla_deadline": a.triage_sla_deadline,
            "remaining_minutes": round(remaining, 1),
            "status": "breached" if remaining < 0 else (
                "warning" if remaining < 60 else "ok"
            ),
        })

    return sorted(result, key=lambda x: x["remaining_minutes"])