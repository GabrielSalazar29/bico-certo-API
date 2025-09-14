from pydantic import BaseModel, Field


class Setup2FARequest(BaseModel):
    method: str = Field(..., description="Método: 'email' ou 'sms'")


class Enable2FARequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=6, description="Código OTP de 6 dígitos")


class Verify2FARequest(BaseModel):
    temp_token: str = Field(..., description="Token temporário do login")
    code: str = Field(..., description="Código OTP ou backup code")


class Disable2FARequest(BaseModel):
    password: str = Field(..., description="Senha para confirmação")


class RegenerateBackupCodesRequest(BaseModel):
    password: str = Field(..., description="Senha para confirmação")
