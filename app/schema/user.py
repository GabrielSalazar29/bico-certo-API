from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional

class UserBase(BaseModel):
    email: EmailStr
    full_name: str


class UserCreate(UserBase):
    password: str


class UserResponse(UserBase):
    id: str
    is_active: bool
    created_at: datetime
    # novos campos _______________
    description: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    profile_image_url: Optional[str] = None
    #____________________________________
    class Config:
        from_attributes = True

class UserUpdate(BaseModel):

   #Schema para receber dados de atualização de perfil.

    full_name: Optional[str] = None
    description: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = Field(
        default=None, 
        max_length=2, 
        description="Sigla do estado (ex: SP)"
    )
    profile_image_url: Optional[str] = None 
    
    class Config:
        from_attributes = True

