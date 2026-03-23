import secrets
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    APP_NAME: str = "FEA 2D Meshing API"
    DEBUG: bool = True

    # Database
    POSTGRES_URL: str = ""

    # JWT
    JWT_SECRET: str = secrets.token_urlsafe(64)

    # Google OAuth2
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/callback"

    class Config:
        env_file = ".env"
        extra = "allow"


settings = Settings()
