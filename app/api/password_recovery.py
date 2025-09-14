from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from ..config.database import get_db
from ..service.password_recovery_service import PasswordRecoveryService
from ..schema.password_recovery import (
    PasswordResetRequestSchema,
    PasswordResetVerifySchema,
)
from ..util.responses import APIResponse

router = APIRouter(prefix="/auth/password", tags=["Password Recovery"])


@router.post("/forgot", response_model=APIResponse)
async def forgot_password(
        request: PasswordResetRequestSchema,
        req: Request,
        db: Session = Depends(get_db)
):
    """
    Solicita recuperação de senha
    Envia email com instruções
    """
    service = PasswordRecoveryService(db)

    success, message, reset_token = await service.request_password_reset(
        email=request.email,
        ip_address=req.client.host if req.client else None,
        user_agent=req.headers.get("user-agent")
    )

    # IMPORTANTE: Sempre retornar sucesso para não revelar se email existe
    return APIResponse.success_response(
        message="Se o email estiver cadastrado, você receberá instruções de recuperação.",
        data={"email": request.email}
    )


@router.post("/reset", response_model=APIResponse)
async def reset_password(
        request: PasswordResetVerifySchema,
        req: Request,
        db: Session = Depends(get_db)
):
    """
    Efetua o reset da senha
    Requer código verificado
    """
    service = PasswordRecoveryService(db)

    # Primeiro verifica o código
    code_valid, code_message, code_data = service.verify_reset_code(
        reset_token=request.reset_token,
        verification_code=request.code
    )

    if not code_valid:
        raise HTTPException(status_code=400, detail=code_message)

    # Resetar senha
    success, message = service.reset_password(
        reset_token=request.reset_token,
        new_password=request.new_password,
        ip_address=req.client.host if req.client else None
    )

    if not success:
        raise HTTPException(status_code=400, detail=message)

    return APIResponse.success_response(
        message=message,
        data={"password_changed": True}
    )
