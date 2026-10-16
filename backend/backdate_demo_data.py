import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal                                  # noqa: E402
from app.models.user import User                                   # noqa: E402,F401  (cần để SQLAlchemy phân giải khóa ngoại)
from app.models.asset import Asset                                  # noqa: E402,F401
from app.models.alert import Alert                                  # noqa: E402
from app.models.alert_group import AlertGroup                       # noqa: E402
from app.models.incident import Incident                            # noqa: E402
from app.models.evidence import Evidence, ChainOfCustody            # noqa: E402
from app.models.impact import ImpactAnalysis                        # noqa: E402
from app.models.containment import Containment                      # noqa: E402
from app.models.recovery import RecoveryAction                      # noqa: E402
from app.models.communication import Communication                  # noqa: E402
from app.models.postmortem import Postmortem                        # noqa: E402
from app.models.audit_log import AuditLog                           # noqa: E402
from app.core.audit import compute_hash, GENESIS                    # noqa: E402

NOW = datetime.now(timezone.utc).replace(tzinfo=None)               # DB lưu UTC naive
M = lambda mins: timedelta(minutes=mins)                            # noqa: E731
db = SessionLocal()
db.info["audit_disabled"] = True

EXPECTED = ["Phishing", "Tấn công dò mật khẩu", "Mã độc beacon", "SQL injection"]
incs = db.query(Incident).order_by(Incident.id).all()
if len(incs) != 4 or not all(i.title.startswith(t) for i, t in zip(incs, EXPECTED)):
    print("Không nhận ra bộ dữ liệu seed (cần đúng 4 incident do seed_demo_data.py tạo). Dừng.")
    sys.exit(1)
if incs[0].detected_at and (NOW - incs[0].detected_at) > timedelta(hours=24):
    print("Dữ liệu có vẻ đã được dịch lùi trước đó. Dừng để tránh chạy lần hai.")
    sys.exit(1)


def alerts_of(inc):
    return db.query(Alert).filter(Alert.incident_id == inc.id).order_by(Alert.id).all()


def set_alert(a, created, triage_delay=None):
    a.created_at = created
    a.updated_at = created
    if a.triage_sla_hours is not None and triage_delay is not None:
        a.triaged_at = created + M(triage_delay)
        a.triage_sla_deadline = a.triaged_at + timedelta(hours=a.triage_sla_hours)


def set_children(inc, base, *, cont, rec, comm, ev_at):
    """Gán mốc thời gian cho containment/recovery/communication/evidence/impact của 1 incident."""
    for k, c in enumerate(db.query(Containment).filter(Containment.incident_id == inc.id)
                          .order_by(Containment.id)):
        c.proposed_at = base + M(cont["propose"])
        c.created_at = c.proposed_at
        if c.reviewed_at:
            c.reviewed_at = base + M(cont["review"])
        if c.executed_at:
            c.executed_at = base + M(cont["execute"])
        if c.verified_at:
            c.verified_at = base + M(cont.get("verify", cont["execute"] + 10))
    for k, r in enumerate(db.query(RecoveryAction).filter(RecoveryAction.incident_id == inc.id)
                          .order_by(RecoveryAction.id)):
        r.created_at = base + M(rec["create"])
        if r.executed_at:
            r.executed_at = base + M(rec["done"] + 20 * k)
        if r.confirmed_at:
            r.confirmed_at = base + M(rec["confirm"] + 20 * k)
    for cm in db.query(Communication).filter(Communication.incident_id == inc.id):
        cm.created_at = base + M(comm["create"])
        if cm.sent_at:
            cm.sent_at = base + M(comm["send"])
        if cm.acknowledged_at:
            cm.acknowledged_at = base + M(comm["ack"])
    for k, e in enumerate(db.query(Evidence).filter(Evidence.incident_id == inc.id)
                          .order_by(Evidence.id)):
        e.collected_at = base + M(ev_at + 10 * k)
        e.created_at = e.collected_at
        for j, log in enumerate(db.query(ChainOfCustody).filter(ChainOfCustody.evidence_id == e.id)
                                .order_by(ChainOfCustody.id)):
            log.performed_at = e.collected_at + M(2 * j)
    for im in db.query(ImpactAnalysis).filter(ImpactAnalysis.incident_id == inc.id):
        im.created_at = base + M(ev_at + 25)


# ── INC1 — Phishing: đã đóng (3 ngày trước) ──
b = NOW - timedelta(days=3)
i1 = incs[0]
for a in alerts_of(i1):
    set_alert(a, b, triage_delay=25)
i1.detected_at, i1.created_at = b + M(40), b + M(40)
i1.contained_at, i1.resolved_at = b + M(140), b + M(390)
set_children(i1, b, cont=dict(propose=100, review=115, execute=140, verify=150),
             rec=dict(create=150, done=200, confirm=300),
             comm=dict(create=210, send=240, ack=270), ev_at=55)
pm = db.query(Postmortem).filter(Postmortem.incident_id == i1.id).first()
if pm:
    pm.created_at = b + M(24 * 60)
    pm.finalized_at = b + M(26 * 60)

# ── INC2 — Credential: đang phục hồi (2 ngày trước), 3 cảnh báo cùng IOC ──
b = NOW - timedelta(days=2)
i2 = incs[1]
offs = [0, 12, 30]
for a, o in zip(alerts_of(i2), offs):
    set_alert(a, b + M(o), triage_delay=20)
i2.detected_at, i2.created_at = b + M(60), b + M(60)
i2.contained_at = b + M(190)
set_children(i2, b, cont=dict(propose=150, review=165, execute=190, verify=200),
             rec=dict(create=200, done=260, confirm=340),
             comm=dict(create=300, send=300, ack=300), ev_at=80)
for g in db.query(AlertGroup).filter(AlertGroup.alert_count > 1):
    g.first_seen, g.last_seen, g.created_at = b, b + M(30), b
# nhóm 1 alert: đồng bộ first/last_seen theo alert tương ứng
for g in db.query(AlertGroup).filter(AlertGroup.alert_count == 1):
    al = db.query(Alert).filter(Alert.group_id == g.id).first()
    if al:
        g.first_seen = g.last_seen = g.created_at = al.created_at

# ── INC3 — Malware: đang điều tra (20 giờ trước) ──
b = NOW - timedelta(hours=20)
i3 = incs[2]
for a in alerts_of(i3):
    set_alert(a, b, triage_delay=18)
i3.detected_at, i3.created_at = b + M(35), b + M(35)
set_children(i3, b, cont=dict(propose=110, review=0, execute=0),
             rec=dict(create=0, done=0, confirm=0),
             comm=dict(create=0, send=0, ack=0), ev_at=60)

# ── INC4 — Web attack: mới mở (5 giờ trước) ──
b = NOW - timedelta(hours=5)
i4 = incs[3]
for a in alerts_of(i4):
    set_alert(a, b, triage_delay=15)
i4.detected_at, i4.created_at = b + M(30), b + M(30)

# ── Cảnh báo lẻ (không thuộc incident nào) ──
loose = db.query(Alert).filter(Alert.incident_id.is_(None)).order_by(Alert.id).all()
for k, a in enumerate(loose):
    created = NOW - timedelta(hours=2 + 3 * k)
    if a.title.startswith("Thiết bị lạ"):
        # đã triage (SLA 24h) nhưng 30 giờ trước và chưa xử lý -> vi phạm SLA hợp lệ
        created = NOW - timedelta(hours=30)
        set_alert(a, created, triage_delay=60)
    else:
        set_alert(a, created)
    if a.group_id:
        g = db.get(AlertGroup, a.group_id)
        if g and g.alert_count == 1:
            g.first_seen = g.last_seen = g.created_at = created

db.flush()

# ── Nhật ký kiểm toán: đưa thời gian về khớp với dữ liệu đã dịch lùi, rồi tính lại chuỗi băm ──
alerts = {x.id: x for x in db.query(Alert).all()}
incidents = {x.id: x for x in db.query(Incident).all()}
evidences = {x.id: x for x in db.query(Evidence).all()}
custody = {x.id: x for x in db.query(ChainOfCustody).all()}
impacts = {x.id: x for x in db.query(ImpactAnalysis).all()}
conts = {x.id: x for x in db.query(Containment).all()}
recs = {x.id: x for x in db.query(RecoveryAction).all()}
comms = {x.id: x for x in db.query(Communication).all()}
pms = {x.id: x for x in db.query(Postmortem).all()}


def audit_time(r):
    e, i, a = r.entity_type, r.entity_id, r.action
    if e == "alert" and i in alerts:
        o = alerts[i]
        if a == "alert.triaged":
            return o.triaged_at or o.created_at + M(15)
        if a == "alert.escalated":
            inc = incidents.get(o.incident_id)
            return inc.detected_at if inc else None
        if a == "alert.false_positive":
            return o.created_at + M(10)
        return o.created_at
    if e == "incident" and i in incidents:
        o = incidents[i]
        if a == "incident.updated":
            pm = next((x for x in pms.values() if x.incident_id == i), None)
            return pm.created_at if pm else o.detected_at
        confirmed = [x.confirmed_at for x in recs.values() if x.incident_id == i and x.confirmed_at]
        return {"incident.created": o.detected_at, "incident.investigating": o.detected_at + M(5) if o.detected_at else None,
                "incident.contained": o.contained_at,
                "incident.recovering": min(confirmed) if confirmed else None,
                "incident.closed": o.resolved_at}.get(a)
    if e == "evidence" and i in evidences:
        return evidences[i].collected_at + M(2 if a == "evidence.locked" else 0)
    if e == "custody" and i in custody:
        return custody[i].performed_at
    if e == "impact" and i in impacts:
        return impacts[i].created_at
    if e == "containment" and i in conts:
        o = conts[i]
        return {"containment.created": o.proposed_at, "containment.approved": o.reviewed_at,
                "containment.rejected": o.reviewed_at, "containment.executed": o.executed_at,
                "containment.verified": o.verified_at}.get(a)
    if e == "recovery" and i in recs:
        o = recs[i]
        return {"recovery.created": o.created_at,
                "recovery.in_progress": (o.executed_at - M(10)) if o.executed_at else o.created_at + M(5),
                "recovery.done": o.executed_at, "recovery.failed": o.executed_at,
                "recovery.confirmed": o.confirmed_at}.get(a)
    if e == "communication" and i in comms:
        o = comms[i]
        return {"communication.created": o.created_at, "communication.approved": o.created_at + M(10),
                "communication.sent": o.sent_at, "communication.acknowledged": o.acknowledged_at}.get(a)
    if e == "postmortem" and i in pms:
        o = pms[i]
        return {"postmortem.created": o.created_at, "postmortem.updated": o.created_at + M(5),
                "postmortem.finalized": o.finalized_at}.get(a)
    if a == "asset.created":
        return NOW - timedelta(days=5)
    if a == "user.created":
        return NOW - timedelta(days=6)
    return None


rows = db.query(AuditLog).order_by(AuditLog.id.asc()).all()
logins = 0
for r in rows:
    t = audit_time(r)
    if t is None and r.action.startswith("auth."):
        t = NOW - timedelta(days=4) + M(7 * logins)
        logins += 1
    if t is not None:
        r.at = t.replace(microsecond=0)
db.flush()
prev = GENESIS
for r in rows:
    data = {"prev_hash": prev, "at": r.at, "user_id": r.user_id, "username": r.username, "role": r.role,
            "action": r.action, "entity_type": r.entity_type, "entity_id": r.entity_id,
            "incident_id": r.incident_id, "detail": r.detail}
    r.prev_hash = prev
    r.row_hash = compute_hash(data)
    prev = r.row_hash

db.commit()
db.close()
print("Đã dịch lùi mốc thời gian cho 4 incident và các cảnh báo lẻ.")
print("Đã tính lại chuỗi băm của nhật ký kiểm toán (chỉ làm với dữ liệu demo).")
print("Mở GET /dashboard/ để xem MTTD/MTTA/MTTR mới.")
