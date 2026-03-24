import secrets
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


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
            return self.POSTGRES_URL
        return (
            f"postgresql+psycopg://{self.DB_USER}:{self.DB_PASS}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    model_config = SettingsConfigDict(
        env_file=(".env", "docker/.env"),
        extra="allow",
    )


settings = Settings()
