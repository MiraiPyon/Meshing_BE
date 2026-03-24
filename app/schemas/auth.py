from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class GoogleCallbackRequest(BaseModel):
    """Frontend gửi authorization code từ Google OAuth flow."""
    code: str = Field(description="Authorization code từ Google OAuth callback")


class RefreshRequest(BaseModel):
    """Đổi refresh token."""
    refresh_token: str = Field(description="Refresh token")


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    picture: str | None = None
    created_at: datetime
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)
