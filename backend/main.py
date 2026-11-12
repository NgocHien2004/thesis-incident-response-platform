from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from database import engine, Base, SessionLocal
from app.models.user import User
from app.models.incident import Incident, AttackType, IncidentStatusHistory
from app.models.upload import Upload
from app.models.alert import Alert, AlertMoveHistory
from app.models.setting import Setting
from app.models.ml_model import MLModel, Label
from app.api.auth import router as auth_router
from app.api.incidents import router as incidents_router
from app.api.uploads import router as uploads_router
from app.api.alerts import router as alerts_router
from app.api.catalog import router as catalog_router
from app.api.dashboard import router as dashboard_router
from app.services.seed import seed_reference_data, fail_interrupted_uploads

# Tạo bảng nếu chưa có, nạp dữ liệu danh mục, đánh dấu lỗi cho file bị gián đoạn lần chạy trước
Base.metadata.create_all(bind=engine)
with SessionLocal() as _db:
    seed_reference_data(_db)
    fail_interrupted_uploads(_db)

app = FastAPI(title="Cybersecurity Incident Management")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(incidents_router)
app.include_router(uploads_router)
app.include_router(alerts_router)
app.include_router(catalog_router)
app.include_router(dashboard_router)

@app.get("/")
def root():
    return {"status": "ok"}

@app.get("/health/db")
def check_db():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"db": "connected"}
    except Exception as e:
        return {"db": "error", "detail": str(e)}
