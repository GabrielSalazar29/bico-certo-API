from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional

class UserBase(BaseModel):
    email: EmailStr
    full_name: str


class UserCreate(UserBase):
    password: str

class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    description: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    profile_pic_url: Optional[str] = None

class UserResponse(UserBase):
    id: str
    is_active: bool
    created_at: datetime

    description: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    profile_pic_url: Optional[str] = None
    class Config:
        from_attributes = True
