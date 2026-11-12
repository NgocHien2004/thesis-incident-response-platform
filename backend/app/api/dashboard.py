from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from database import get_db
from app.core.dependencies import get_current_user
from app.core.constants import INCIDENT_STATUSES, VERIFICATION_STATUSES
from app.models.user import User
from app.models.incident import Incident, AttackType
from app.models.alert import Alert

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("")
def dashboard(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    by_status = dict(db.query(Incident.status, func.count(Incident.id)).group_by(Incident.status).all())
    by_type = dict(db.query(Incident.attack_type, func.count(Incident.id)).group_by(Incident.attack_type).all())
    names = {t.code: t.name_vi for t in db.query(AttackType).all()}
    by_label = db.query(Alert.predicted_label, func.count(Alert.id)).group_by(Alert.predicted_label).all()
    by_ver = dict(db.query(Alert.verification_status, func.count(Alert.id)).group_by(Alert.verification_status).all())
    verified, dismissed = by_ver.get("verified", 0), by_ver.get("dismissed", 0)
    decided = verified + dismissed
    unassigned = db.query(Alert).filter(Alert.incident_id.is_(None)).count()
    return {
        "incidents_total": sum(by_status.values()),
        "incidents_by_status": {s: by_status.get(s, 0) for s in INCIDENT_STATUSES},
        "incidents_by_attack_type": [{"code": c, "name_vi": names.get(c, c), "count": n}
                                     for c, n in sorted(by_type.items(), key=lambda kv: -kv[1])],
        "alerts_total": sum(n for _, n in by_label),
        "alerts_unassigned": unassigned,
        "alerts_by_label": [{"label": l, "count": n} for l, n in sorted(by_label, key=lambda kv: -kv[1])],
        "alerts_by_verification": {s: by_ver.get(s, 0) for s in VERIFICATION_STATUSES},
        # Tỉ lệ bỏ qua = Bỏ qua / (Đã xác minh + Bỏ qua); chưa có cảnh báo nào được quyết định thì không tính
        "false_positive_rate": round(dismissed / decided, 4) if decided else None,
    }
