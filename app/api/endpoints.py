from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.core.config import settings

try:
    import psycopg
except ImportError:  # pragma: no cover - depends on runtime environment
    psycopg = None


router = APIRouter()


@router.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/db", tags=["health"])
def database_health() -> JSONResponse:
    if psycopg is None:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "reason": "psycopg is not installed",
            },
        )

    try:
        with psycopg.connect(
            host=settings.db_host,
            port=settings.db_port,
            dbname=settings.db_name,
            user=settings.db_user,
            password=settings.db_pass,
            connect_timeout=3,
        ) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()

        return JSONResponse(content={"status": "ok", "database": "connected"})
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "reason": str(exc),
            },
        )
