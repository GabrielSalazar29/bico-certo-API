from pydantic import BaseModel, EmailStr
from typing import Optional


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class DeviceInfo(BaseModel):
    device_id: str
    platform: Optional[str] = None
    model: Optional[str] = None
    os_version: Optional[str] = None
    app_version: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    device_info: DeviceInfo
