from pydantic import BaseModel, EmailStr, Field


class PasswordResetRequestSchema(BaseModel):
    """Solicita reset de senha"""
    email: EmailStr = Field(..., description="Email do usuário")


class PasswordResetVerifySchema(BaseModel):
    """Verifica código e define nova senha"""
    reset_token: str = Field(..., description="Token de reset recebido por email")
    code: str = Field(..., min_length=6, max_length=6, description="Código de verificação")
    new_password: str = Field(..., min_length=8, description="Nova senha")
