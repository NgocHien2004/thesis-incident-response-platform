from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from app.models.asset import Asset
from app.schemas.asset import AssetCreate, AssetUpdate, AssetOut
from app.core.dependencies import get_current_user, require_roles
from app.models.user import RoleEnum, User

router = APIRouter(prefix="/assets", tags=["Assets"])

# Xem danh sách — tất cả role đều xem được
@router.get("/", response_model=List[AssetOut])
def list_assets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(Asset).all()

# Xem chi tiết 1 tài sản
@router.get("/{asset_id}", response_model=AssetOut)
def get_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(404, "Không tìm thấy tài sản")
    return asset

# Tạo mới — chỉ IT và Analyst
@router.post("/", response_model=AssetOut)
def create_asset(
    payload: AssetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.it_helpdesk, RoleEnum.analyst_soc))
):
    asset = Asset(**payload.model_dump(), created_by=current_user.id)
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset

# Cập nhật — chỉ IT và Analyst
@router.put("/{asset_id}", response_model=AssetOut)
def update_asset(
    asset_id: int,
    payload: AssetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.it_helpdesk, RoleEnum.analyst_soc))
):
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(404, "Không tìm thấy tài sản")
    for k, v in payload.model_dump().items():
        setattr(asset, k, v)
    db.commit()
    db.refresh(asset)
    return asset

# Xóa — chỉ Analyst
@router.delete("/{asset_id}")
def delete_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.analyst_soc))
):
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(404, "Không tìm thấy tài sản")
    db.delete(asset)
    db.commit()
    return {"message": "Đã xóa tài sản"}