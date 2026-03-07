from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from q3_fundamentals_engine.config import DATABASE_URL

engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
