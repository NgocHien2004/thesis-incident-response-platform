from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv
import os

load_dotenv()

SERVER   = os.getenv("DB_SERVER")
DATABASE = os.getenv("DB_NAME")
USER     = os.getenv("DB_USER")
PASSWORD = os.getenv("DB_PASSWORD")

CONN_STR = (
    f"mssql+pyodbc://{USER}:{PASSWORD}@{SERVER}/{DATABASE}"
    f"?driver=ODBC+Driver+17+for+SQL+Server"
    f"&TrustServerCertificate=yes"
)

engine = create_engine(CONN_STR, echo=False)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()