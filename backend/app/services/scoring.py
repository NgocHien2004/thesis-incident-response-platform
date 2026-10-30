import json
import os

import httpx
from sqlalchemy.orm import Session

from app.core.timeutils import utcnow
from app.models.alert import Alert, AlertStatus
from app.models.asset import Asset
from app.services import scoring_rules as rules
from app.services.scoring_rules import extract_flow_features

from app.api.ai import AI_SERVICE_URL

AI_TIMEOUT = 5.0
SIMILAR_POOL = 300


def auto_close_enabled():
    return os.getenv("ALERT_AUTO_CLOSE", "").strip().lower() in ("1", "true", "yes")


def _classify(flow):
    """Gọi mô hình RF của AI service. Trả về (kết quả, lỗi)."""
    try:
        r = httpx.post(f"{AI_SERVICE_URL}/classify", json={"features": flow}, timeout=AI_TIMEOUT)
        r.raise_for_status()
        return r.json(), None
    except httpx.ConnectError:
        return None, "AI service không khả dụng"
    except httpx.TimeoutException:
        return None, "AI service quá thời gian"
    except Exception as e:  # noqa: BLE001
        return None, f"Lỗi AI service: {str(e)[:120]}"


def _similar(db: Session, alert: Alert):
    rows = db.query(Alert.id, Alert.title, Alert.description, Alert.ioc, Alert.status, Alert.group_id,
                    Alert.incident_id).filter(Alert.id != alert.id).order_by(Alert.id.desc()).limit(SIMILAR_POOL).all()
    by_id = {r.id: r for r in rows}
    text = lambda t, d, i: " ".join(x for x in (t, d, i) if x)  # noqa: E731
    ranked = rules.rank_similar(
        text(alert.title, alert.description, alert.ioc),
        [(r.id, text(r.title, r.description, r.ioc)) for r in rows],
    )
    return [{
        "id": cid, "title": by_id[cid].title, "similarity": sim,
        "status": by_id[cid].status.value, "incident_id": by_id[cid].incident_id,
        "same_group": bool(alert.group_id and by_id[cid].group_id == alert.group_id),
    } for cid, sim in ranked]


def score_alert(db: Session, alert: Alert) -> dict:
    asset = db.query(Asset).filter(Asset.id == alert.affected_asset).first() if alert.affected_asset else None
    criticality = asset.criticality.value if asset else None
    a_weight = rules.asset_weight(criticality)
    source = alert.source.value
    s_rel = rules.source_reliability(source)
    declared = alert.severity.value

    flow = extract_flow_features(alert.raw_data)
    ai_error, top_features, model = None, [], "heuristic_declared_severity"
    p, p_source = rules.declared_probability(declared), "declared_severity"
    if flow:
        result, ai_error = _classify(flow)
        if result:
            p, p_source, model = float(result["attack_probability"]), "rf", result.get("model_version", "rf_binary_v1")
            top_features = result.get("top_features", [])

    group_risk = False
    if alert.group_id:
        group_risk = db.query(Alert.id).filter(
            Alert.group_id == alert.group_id, Alert.id != alert.id, Alert.ml_zone.in_(["review", "urgent"])
        ).first() is not None

    priority = rules.priority_score(p, a_weight, s_rel)
    zone, reason, rule_list = rules.decide_zone(
        p=p, p_source=p_source, priority=priority, asset_criticality=criticality, asset_w=a_weight,
        source=source, declared_severity=declared, group_has_open_risk=group_risk,
    )

    result = {
        "model": model,
        "probability": round(p, 4),
        "probability_source": p_source,
        "priority": priority,
        "zone": zone,
        "zone_label": rules.ZONE_LABEL[zone],
        "zone_reason": reason,
        "rules": rule_list,
        "components": {
            "asset": {"id": asset.id if asset else None, "name": asset.name if asset else None,
                      "criticality": criticality, "weight": a_weight},
            "source": {"name": source, "reliability": s_rel},
            "declared_severity": declared,
        },
        "formula": {"base": rules.W_BASE, "asset": rules.W_ASSET, "source": rules.W_SOURCE,
                    "urgent_priority": rules.URGENT_PRIORITY, "urgent_probability": rules.URGENT_PROBABILITY,
                    "auto_close_probability": rules.AUTO_CLOSE_PROBABILITY},
        "top_features": top_features,
        "similar_alerts": _similar(db, alert),
        "ai_error": ai_error,
        "scored_at": utcnow().replace(microsecond=0).isoformat(),
        "ai_generated": True,
    }

    alert.ml_priority = int(round(priority))
    alert.ml_zone = zone
    alert.ml_result = json.dumps(result, ensure_ascii=False)
    db.info["audit_note"] = f"{rules.ZONE_LABEL[zone]}, điểm {priority}, xác suất {round(p, 3)} ({p_source})"
    db.commit()
    db.refresh(alert)

    if auto_close_enabled() and zone == "auto_close" and alert.status == AlertStatus.new:
        actor = db.info.get("actor")
        db.info["actor"] = {"id": None, "username": "hệ thống (luật tự đóng an toàn)", "role": None}
        alert.status = AlertStatus.closed
        alert.triage_note = f"Tự đóng theo luật an toàn: {reason}"
        db.info["audit_note"] = "Tự đóng theo luật an toàn; Analyst có thể mở lại cảnh báo"
        db.commit()
        db.refresh(alert)
        if actor is not None:
            db.info["actor"] = actor
        else:
            db.info.pop("actor", None)
    return result


def score_alert_safe(db: Session, alert: Alert):
    """Chấm điểm khi nhập cảnh báo; lỗi chấm điểm không được làm hỏng việc tiếp nhận."""
    try:
        return score_alert(db, alert)
    except Exception:  # noqa: BLE001
        db.rollback()
        return None
