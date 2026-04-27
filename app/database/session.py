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
    _ensure_picture_column()
    _ensure_mesh_meshing_params_column()
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


def _ensure_picture_column() -> None:
    """Add 'picture' column to users table if it doesn't exist yet.

    Since the project doesn't use Alembic, this ensures the column
    exists for databases created before the picture field was added.
    """
    if not database_url.startswith("postgresql"):
        return

    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'users'
                  AND column_name = 'picture'
                """
            )
        ).fetchone()

        if not row:
            # Column doesn't exist — check if table exists at all
            table_exists = conn.execute(
                text(
                    """
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name = 'users'
                    """
                )
            ).fetchone()
            if table_exists:
                conn.execute(
                    text("ALTER TABLE users ADD COLUMN picture VARCHAR(512)")
                )


def _ensure_mesh_meshing_params_column() -> None:
    """Add `meshing_params` column to meshes table if missing."""
    if not database_url.startswith("postgresql"):
        return

    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'meshes'
                  AND column_name = 'meshing_params'
                """
            )
        ).fetchone()

        if row:
            return

        table_exists = conn.execute(
            text(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = 'meshes'
                """
            )
        ).fetchone()
        if table_exists:
            conn.execute(text("ALTER TABLE meshes ADD COLUMN meshing_params TEXT"))
