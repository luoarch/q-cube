import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def ensure_psycopg_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


DATABASE_URL = ensure_psycopg_url(os.getenv("DATABASE_URL", "postgresql://127.0.0.1:5432/q3"))

engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
