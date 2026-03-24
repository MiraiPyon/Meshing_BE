"""
Auth Endpoints — Google OAuth2 → JWT.
"""

import httpx
from fastapi import APIRouter, HTTPException, status, Depends, Query
from fastapi.security import HTTPBearer

from app.schemas.auth import GoogleCallbackRequest, RefreshRequest, TokenResponse, UserResponse
from app.services import auth_service


router = APIRouter(prefix="/api/auth")
security = HTTPBearer()


@router.get("/google/url")
def google_auth_url():
    """Trả về URL để redirect user sang Google OAuth."""
    import urllib.parse

    params = {
        "client_id": auth_service.settings.GOOGLE_CLIENT_ID,
        "redirect_uri": auth_service.settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "include_granted_scopes": "true",
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    return {"url": url}


@router.post("/callback", response_model=TokenResponse)
def google_callback(req: GoogleCallbackRequest):
    """Đổi Google auth code → JWT tokens."""
    try:
        return auth_service.google_auth(req.code)
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Google OAuth error: {e.response.text}",
        ) from e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e


@router.get("/callback", response_model=TokenResponse)
def google_callback_get(code: str = Query(..., description="Google authorization code")):
    """Google redirect callback (GET) cho trường hợp test không có frontend."""
    try:
        return auth_service.google_auth(code)
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Google OAuth error: {e.response.text}",
        ) from e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e


@router.post("/refresh", response_model=TokenResponse)
def refresh(req: RefreshRequest):
    """Đổi refresh token lấy token mới."""
    try:
        return auth_service.refresh_tokens(req.refresh_token)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e


@router.post("/logout")
def logout(req: RefreshRequest):
    """Revoke refresh token (logout)."""
    auth_service.revoke_refresh_token(req.refresh_token)
    return {"message": "Logged out"}


@router.get("/me", response_model=UserResponse)
def me(token: str = Depends(security)):
    """Lấy thông tin user hiện tại."""
    try:
        payload = auth_service.verify_access_token(token.credentials)
        user = auth_service.get_user_by_id(payload["sub"])
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return auth_service.user_to_response(user)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e
