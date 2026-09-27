from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import json
from database import get_db
from app.models.impact import ImpactAnalysis
from app.models.incident import Incident
from app.models.asset import Asset
from app.schemas.impact import ImpactAnalysisCreate, ImpactAnalysisOut
from app.core.dependencies import get_current_user, require_roles
from app.models.user import RoleEnum, User

router = APIRouter(prefix="/incidents/{incident_id}/impact", tags=["Impact Analysis"])

def _get_incident(incident_id: int, db: Session) -> Incident:
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(404, "Không tìm thấy incident")
    return incident

# Xem phân tích phạm vi
@router.get("/", response_model=List[ImpactAnalysisOut])
def list_analyses(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _get_incident(incident_id, db)
    return db.query(ImpactAnalysis).filter(
        ImpactAnalysis.incident_id == incident_id
    ).all()

# Tạo phân tích phạm vi — chỉ Analyst
@router.post("/", response_model=ImpactAnalysisOut)
def create_analysis(
    incident_id: int,
    payload: ImpactAnalysisCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.analyst_soc))
):
    _get_incident(incident_id, db)

    # Validate asset ids tồn tại
    for asset_id in (payload.affected_assets or []):
        if not db.query(Asset).filter(Asset.id == asset_id).first():
            raise HTTPException(404, f"Asset {asset_id} không tồn tại")

    analysis = ImpactAnalysis(
        incident_id=incident_id,
        ioc_list=json.dumps(payload.ioc_list),
        affected_assets=json.dumps(payload.affected_assets),
        affected_accounts=json.dumps(payload.affected_accounts),
        attck_techniques=json.dumps(payload.attck_techniques),
        attck_version=payload.attck_version,
        related_events=payload.related_events,
        summary=payload.summary,
        analyzed_by=current_user.id,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis

# Cập nhật phân tích
@router.put("/{analysis_id}", response_model=ImpactAnalysisOut)
def update_analysis(
    incident_id: int,
    analysis_id: int,
    payload: ImpactAnalysisCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.analyst_soc))
):
    analysis = db.query(ImpactAnalysis).filter(
        ImpactAnalysis.id == analysis_id,
        ImpactAnalysis.incident_id == incident_id
    ).first()
    if not analysis:
        raise HTTPException(404, "Không tìm thấy phân tích")

    analysis.ioc_list         = json.dumps(payload.ioc_list)
    analysis.affected_assets  = json.dumps(payload.affected_assets)
    analysis.affected_accounts = json.dumps(payload.affected_accounts)
    analysis.attck_techniques = json.dumps(payload.attck_techniques)
    analysis.attck_version    = payload.attck_version
    analysis.related_events   = payload.related_events
    analysis.summary          = payload.summary
    db.commit()
    db.refresh(analysis)
    return analysis

# Xem tóm tắt nhanh — tài sản + IOC + ATT&CK
@router.get("/summary")
def get_summary(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _get_incident(incident_id, db)
    analyses = db.query(ImpactAnalysis).filter(
        ImpactAnalysis.incident_id == incident_id
    ).all()
    if not analyses:
        return {"message": "Chưa có phân tích phạm vi nào"}

    latest = analyses[-1]

    # Lấy tên tài sản từ asset ids
    asset_ids = json.loads(latest.affected_assets or "[]")
    assets = []
    for aid in asset_ids:
        asset = db.query(Asset).filter(Asset.id == aid).first()
        if asset:
            assets.append({"id": aid, "name": asset.name, "criticality": asset.criticality})

    return {
        "incident_id": incident_id,
        "ioc_list": json.loads(latest.ioc_list or "[]"),
        "affected_assets": assets,
        "affected_accounts": json.loads(latest.affected_accounts or "[]"),
        "attck_techniques": json.loads(latest.attck_techniques or "[]"),
        "attck_version": latest.attck_version,
        "summary": latest.summary,
        "analyzed_by": latest.analyzed_by,
        "updated_at": latest.updated_at,
    }