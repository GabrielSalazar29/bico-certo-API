from datetime import datetime, timedelta, UTC
from typing import Optional, Dict, Any
import secrets
from jose import JWTError, jwt
from ..config.settings import settings


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": expire,
        "iat": datetime.now(UTC),
        "type": "access"
    })

    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


def create_refresh_token() -> tuple[str, datetime]:
    """Cria refresh token e retorna (token, expiration)"""
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + timedelta(days=7)
    return token, expires_at


def create_tokens(user_id: str, email: str) -> dict:
    """Cria access e refresh tokens"""
    access_token = create_access_token(
        data={"sub": user_id, "email": email}
    )
    refresh_token, expires_at = create_refresh_token()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "refresh_expires_at": expires_at,
        "token_type": "bearer"
    }