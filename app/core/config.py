from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""

    # App
    APP_NAME: str = "FEA 2D Meshing API"
    DEBUG: bool = True

    # Database - PostgreSQL/Supabase
    POSTGRES_URL: str = ""

    class Config:
        env_file = ".env"
        extra = "allow"


settings = Settings()
