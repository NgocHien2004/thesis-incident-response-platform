from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
import httpx
from app.core.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/ai", tags=["AI"])

AI_SERVICE_URL = "http://localhost:8001"

class AlertSuggestRequest(BaseModel):
    title: str
    description: Optional[str] = ""
    ioc: Optional[str] = ""

class AttckSearchRequest(BaseModel):
    description: str
    top_k: Optional[int] = 5

async def _call_ai(endpoint: str, payload: dict) -> dict:
    """Gọi AI service, xử lý lỗi nếu service down."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{AI_SERVICE_URL}{endpoint}",
                json=payload
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.ConnectError:
        raise HTTPException(503, "AI service không khả dụng — thử lại sau")
    except httpx.TimeoutException:
        raise HTTPException(504, "AI service timeout")
    except Exception as e:
        raise HTTPException(500, f"Lỗi AI service: {str(e)}")

# Đề xuất mức độ và ATT&CK cho alert
@router.post("/alert/suggest")
async def suggest_alert(
    payload: AlertSuggestRequest,
    current_user: User = Depends(get_current_user)
):
    result = await _call_ai("/alert/suggest", {
        "title": payload.title,
        "description": payload.description,
        "ioc": payload.ioc,
    })
    # Đánh dấu rõ nội dung AI tạo
    result["ai_generated"] = True
    result["generated_by"] = "rf_binary_v1 + attck_14.1"
    return result

# Tìm kiếm ATT&CK techniques
@router.post("/attck/search")
async def attck_search(
    payload: AttckSearchRequest,
    current_user: User = Depends(get_current_user)
):
    result = await _call_ai("/attck/search", {
        "description": payload.description,
        "top_k": payload.top_k,
    })
    result["ai_generated"] = True
    return result

# Health check AI service
@router.get("/health")
async def ai_health(current_user: User = Depends(get_current_user)):
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{AI_SERVICE_URL}/")
            return {"ai_service": "up", "detail": resp.json()}
    except Exception:
        return {"ai_service": "down"}