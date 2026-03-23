"""
JWT Dependencies — dùng cho các endpoint cần xác thực.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer

from app.services import auth_service


security = HTTPBearer()


def get_current_user(token: str = Depends(security)) -> auth_service.User:
    """
    Dependency: lấy user hiện tại từ JWT access token.
    Dùng cho các endpoint cần authentication.
    """
    try:
        payload = auth_service.verify_access_token(token.credentials)
        user = auth_service.get_user_by_id(payload["sub"])
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
