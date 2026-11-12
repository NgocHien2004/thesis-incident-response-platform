from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from app.core.dependencies import get_current_user
from app.core.constants import DATA_TYPES
from app.core.timeutils import utcnow
from app.models.user import User
from app.models.incident import AttackType
from app.models.ml_model import MLModel, Label
from app.models.setting import Setting
from app.schemas.catalog import LabelUpdate, SettingUpdate
from app.services import classifier
from app.services.classifier import AIError
from app.services.settings_store import validate_setting
import json

router = APIRouter(tags=["Catalog"])

def label_dict(l: Label) -> dict:
    return {"id": l.id, "data_type": l.data_type, "code": l.code, "name_vi": l.name_vi,
            "is_dangerous": l.is_dangerous, "is_active": l.is_active}

@router.get("/attack-types")
def attack_types(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return [{"code": t.code, "name_vi": t.name_vi, "is_active": t.is_active}
            for t in db.query(AttackType).order_by(AttackType.name_vi).all()]

@router.get("/labels")
def labels(data_type: Optional[str] = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(Label)
    if data_type:
        if data_type not in DATA_TYPES:
            raise HTTPException(422, "data_type không hợp lệ")
        q = q.filter(Label.data_type == data_type)
    return [label_dict(l) for l in q.order_by(Label.data_type, Label.code).all()]

@router.put("/labels/{label_id}")
def update_label(label_id: int, payload: LabelUpdate, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    l = db.get(Label, label_id)
    if not l:
        raise HTTPException(404, "Không tìm thấy nhãn")
    data = payload.model_dump(exclude_unset=True)
    for k in ("is_dangerous", "is_active"):
        if k in data and data[k] is not None:
            setattr(l, k, data[k])
    if data.get("name_vi"):
        l.name_vi = data["name_vi"].strip()
    db.commit()
    return label_dict(l)

@router.get("/settings")
def settings(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return [{"key": s.key, "value": s.value, "description": s.description,
             "updated_at": s.updated_at, "updated_by": s.updated_by}
            for s in db.query(Setting).order_by(Setting.key).all()]

@router.put("/settings/{key}")
def update_setting(key: str, payload: SettingUpdate, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    try:
        value = validate_setting(key, payload.value)
    except ValueError as e:
        raise HTTPException(422, str(e))
    row = db.get(Setting, key)
    if not row:
        raise HTTPException(404, "Không tìm thấy khóa cấu hình")
    row.value, row.updated_at, row.updated_by = value, utcnow(), user.id
    db.commit()
    return {"key": row.key, "value": row.value, "description": row.description,
            "updated_at": row.updated_at, "updated_by": row.updated_by}

def model_dict(m: MLModel) -> dict:
    return {"id": m.id, "name": m.name, "version": m.version, "task_type": m.task_type,
            "is_active": m.is_active, "trained_at": m.trained_at, "file_path": m.file_path,
            "metrics": json.loads(m.metrics_json) if m.metrics_json else None,
            "features": json.loads(m.feature_names) if m.feature_names else None}

@router.get("/models")
def models(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return [model_dict(m) for m in db.query(MLModel).order_by(MLModel.task_type, MLModel.id.desc()).all()]

@router.post("/models/sync")
def sync_models(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        return [model_dict(m) for m in classifier.sync_models(db)]
    except AIError as e:
        raise HTTPException(503, str(e))
