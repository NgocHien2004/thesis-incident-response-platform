from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from database import engine, Base
from app.models.user import User
from app.api.auth import router as auth_router
from app.models.asset import Asset         
from app.api.assets import router as assets_router   
from app.models.alert import Alert
from app.api.alerts import router as alerts_router
from app.models.alert_group import AlertGroup
from app.models.incident import Incident
from app.api.incidents import router as incidents_router
from app.models.evidence import Evidence, ChainOfCustody
from app.api.evidences import router as evidences_router
from app.models.impact import ImpactAnalysis
from app.api.impact import router as impact_router
from app.models.containment import Containment
from app.api.containment import router as containment_router
from app.models.recovery import RecoveryAction
from app.api.recovery import router as recovery_router
from app.models.communication import Communication
from app.api.communication import router as communication_router
from app.models.postmortem import Postmortem
from app.api.postmortem import router as postmortem_router
from app.models.playbook import Playbook, PlaybookStep
from app.models.task import Task
from app.api.playbooks import router as playbooks_router
from app.api.tasks import router as tasks_router
from app.api.dashboard import router as dashboard_router
from app.api.ai import router as ai_router
from app.models.audit_log import AuditLog
import app.core.audit  # đăng ký bộ ghi nhật ký tự động
from app.api.audit import router as audit_router

# Tạo bảng nếu chưa có
Base.metadata.create_all(bind=engine)

# Nạp playbook mẫu khi bảng còn trống
from database import SessionLocal
from app.services.default_playbooks import seed_default_playbooks
with SessionLocal() as _db:
    seed_default_playbooks(_db)

app = FastAPI(title="Incident Response Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(assets_router)
app.include_router(alerts_router)
app.include_router(incidents_router)
app.include_router(evidences_router)
app.include_router(impact_router)
app.include_router(containment_router)
app.include_router(recovery_router)
app.include_router(playbooks_router)
app.include_router(tasks_router)
app.include_router(communication_router)
app.include_router(postmortem_router)
app.include_router(dashboard_router)
app.include_router(ai_router)
app.include_router(audit_router)

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