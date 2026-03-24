from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.orm import declarative_base
from typing import Generator

from app.core.config import settings

database_url = settings.database_url
engine_kwargs = {
    "pool_pre_ping": True,
    "pool_size": 10,
    "max_overflow": 20,
}

# Create engine
engine = create_engine(database_url, **engine_kwargs)

# SessionLocal
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Dependency để lấy database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database - create tables"""
    _fix_legacy_auth_schema()
    Base.metadata.create_all(bind=engine)


def _fix_legacy_auth_schema() -> None:
    """Repair legacy auth tables created with integer ids.

    Older schema versions used users.id as integer, while current models use UUID.
    This function detects that mismatch in PostgreSQL and resets auth tables so
    SQLAlchemy can recreate them with correct UUID types.
    """
    if not database_url.startswith("postgresql"):
        return

    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT data_type
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'users'
                  AND column_name = 'id'
                """
            )
        ).fetchone()

        if row and row[0] != "uuid":
            conn.execute(text("DROP TABLE IF EXISTS refresh_tokens CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS users CASCADE"))
