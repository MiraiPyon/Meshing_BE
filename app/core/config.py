import os
import secrets
from pathlib import Path
from sqlalchemy.engine.url import make_url
from pydantic_settings import BaseSettings
from pydantic_settings import PydanticBaseSettingsSource
from pydantic_settings import SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[2]
LOCAL_ENV_FILE = ROOT_DIR / ".env"
DOCKER_ENV_FILE = ROOT_DIR / "docker" / ".env"


def _resolve_env_files() -> tuple[str, ...]:
    """Load a single source of truth for runtime settings.

    Prefer the project-local .env for host runs. If it doesn't exist,
    fall back to docker/.env so Docker-based workflows still work.
    """
    if LOCAL_ENV_FILE.exists():
        return (str(LOCAL_ENV_FILE),)
    if DOCKER_ENV_FILE.exists():
        return (str(DOCKER_ENV_FILE),)
    return ()


def _is_running_in_container() -> bool:
    """Best-effort detection for containerized runtime."""
    if Path("/.dockerenv").exists():
        return True
    marker = os.getenv("RUNNING_IN_DOCKER", "").strip().lower()
    return marker in {"1", "true", "yes"}


def _normalize_db_host(host: str) -> str:
    """Avoid Docker DNS host in host-run mode.

    `db` only resolves inside Docker compose network.
    """
    if host == "db" and not _is_running_in_container():
        return "localhost"
    return host


def _normalize_database_url(database_url: str) -> str:
    """Rewrite URL host `db` to localhost when running outside Docker."""
    if _is_running_in_container():
        return database_url

    try:
        parsed = make_url(database_url)
    except Exception:
        return database_url

    if parsed.host == "db":
        normalized = parsed.set(host="localhost")
        return normalized.render_as_string(hide_password=False)
    return database_url


class Settings(BaseSettings):
    # App
    APP_NAME: str = "FEA 2D Meshing API"
    DEBUG: bool = True

    # Database
    POSTGRES_URL: str = ""
    DB_USER: str = "admin"
    DB_PASS: str = "123456789"
    DB_NAME: str = "meshing_db"
    DB_PORT: int = 5432
    DB_HOST: str = "localhost"

    # JWT
    JWT_SECRET: str = secrets.token_urlsafe(64)

    # Google OAuth2
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/auth/callback"

    @property
    def database_url(self) -> str:
        if self.POSTGRES_URL:
            return _normalize_database_url(self.POSTGRES_URL)
        host = _normalize_db_host(self.DB_HOST)
        return (
            f"postgresql+psycopg://{self.DB_USER}:{self.DB_PASS}"
            f"@{host}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Keep `.env` as source-of-truth for local development to avoid
        # stale exported shell variables overriding DB credentials.
        return (
            init_settings,
            dotenv_settings,
            env_settings,
            file_secret_settings,
        )

    model_config = SettingsConfigDict(env_file=_resolve_env_files(), extra="allow")


settings = Settings()
