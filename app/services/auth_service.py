"""
Auth Service — Google OAuth2 → JWT.
"""

import httpx
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from app.core.config import settings
from app.database.models import User, RefreshToken
from app.database.session import SessionLocal
from app.schemas.auth import TokenResponse, UserResponse


# ---- JWT ----

ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 30


def _import_jwt():
    try:
        import jwt
        return jwt
    except ImportError:
        raise RuntimeError("pip install pyjwt")


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _parse_uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as e:
        raise ValueError("Invalid user id in token") from e


def _to_utc(dt: datetime) -> datetime:
    """Normalize datetime values from DB to timezone-aware UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def create_tokens(user: User) -> TokenResponse:
    """Tạo access + refresh tokens cho user."""
    jwt = _import_jwt()
    now = datetime.now(timezone.utc)
    secret = settings.JWT_SECRET

    # Access token
    access_payload = {
        "sub": str(user.id),
        "email": user.email,
        "name": user.name,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    access_token = jwt.encode(access_payload, secret, algorithm="HS256")

    # Refresh token (JWT)
    refresh_payload = {
        "sub": str(user.id),
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    }
    refresh_token = jwt.encode(refresh_payload, secret, algorithm="HS256")

    # Lưu refresh token hash vào DB
    db = SessionLocal()
    try:
        db.add(RefreshToken(
            user_id=user.id,
            token_hash=_hash_token(refresh_token),
            expires_at=datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        ))
        db.commit()
    finally:
        db.close()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


def verify_access_token(token: str) -> dict:
    """Verify access token, trả về payload."""
    jwt = _import_jwt()
    payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    if payload.get("type") != "access":
        raise ValueError("Invalid token type")
    return payload


def refresh_tokens(refresh_token: str) -> TokenResponse:
    """Đổi refresh token lấy token mới."""
    jwt = _import_jwt()
    db = SessionLocal()
    try:
        # Verify JWT signature
        payload = jwt.decode(refresh_token, settings.JWT_SECRET, algorithms=["HS256"])
        if payload.get("type") != "refresh":
            raise ValueError("Invalid token type")

        user_id = _parse_uuid(payload["sub"])
        token_hash = _hash_token(refresh_token)

        # Check token chưa bị revoke
        stored = db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id,
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked == False,
        ).first()

        now_utc = datetime.now(timezone.utc)
        if not stored or _to_utc(stored.expires_at) < now_utc:
            raise ValueError("Token expired or revoked")

        # Revoke old refresh token
        stored.revoked = True
        db.commit()

        # Lấy user và tạo token mới
        user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
        if not user:
            raise ValueError("User not found")

        return create_tokens(user)
    finally:
        db.close()


def revoke_refresh_token(refresh_token: str) -> bool:
    """Revoke một refresh token (logout)."""
    jwt = _import_jwt()
    db = SessionLocal()
    try:
        payload = jwt.decode(refresh_token, settings.JWT_SECRET, algorithms=["HS256"])
        token_hash = _hash_token(refresh_token)
        user_id = _parse_uuid(payload["sub"])
        stored = db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id,
            RefreshToken.token_hash == token_hash,
        ).first()
        if stored:
            stored.revoked = True
            db.commit()
            return True
        return False
    except Exception:
        return False
    finally:
        db.close()


# ---- Google OAuth2 ----

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


def exchange_google_code(code: str) -> dict:
    """Đổi authorization code lấy tokens từ Google."""
    resp = httpx.post(GOOGLE_TOKEN_URL, data={
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }, timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_google_userinfo(access_token: str) -> dict:
    """Lấy thông tin user từ Google."""
    resp = httpx.get(GOOGLE_USERINFO_URL, headers={
        "Authorization": f"Bearer {access_token}",
    }, timeout=10)
    resp.raise_for_status()
    return resp.json()


def google_auth(code: str) -> TokenResponse:
    """
    Full Google OAuth2 flow:
      1. Exchange code → tokens
      2. Get user info
      3. Create user if not exists (upsert by email)
      4. Return JWT tokens
    """
    # 1. Get Google tokens
    google_tokens = exchange_google_code(code)
    access_token = google_tokens["access_token"]

    # 2. Get user info
    info = get_google_userinfo(access_token)

    # 3. Upsert user
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == info["email"]).first()
        if not user:
            user = User(
                email=info["email"],
                name=info.get("name", info["email"]),
                password_hash="",  # Google OAuth — no password
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        elif not user.is_active:
            raise ValueError("Account is deactivated")

        return create_tokens(user)
    finally:
        db.close()


def get_user_by_id(user_id: str) -> Optional[User]:
    db = SessionLocal()
    try:
        parsed_user_id = _parse_uuid(user_id)
        return db.query(User).filter(User.id == parsed_user_id, User.is_active == True).first()
    finally:
        db.close()


def user_to_response(user: User) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        created_at=user.created_at,
        is_active=user.is_active,
    )
