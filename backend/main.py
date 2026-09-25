from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine
from sqlalchemy import text

app = FastAPI(title="Incident Response Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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