from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from ..config.database import get_db
from ..service.two_factor_service import TwoFactorService, generate_backup_codes
from ..model.two_factor import TwoFactorMethod
from ..schema.two_factor import (
    Setup2FARequest,
    Verify2FARequest,
    Enable2FARequest,
    Disable2FARequest,
    RegenerateBackupCodesRequest,
)
from ..util.responses import APIResponse
from ..auth.dependencies import get_current_user
from ..model.user import User
from ..config.settings import fuso_local

router = APIRouter(prefix="/auth/2fa", tags=["Two Factor Authentication"])


@router.post("/setup", response_model=APIResponse)
async def setup_two_factor(
        request: Setup2FARequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Configura 2FA para o usuário"""
    service = TwoFactorService(db)

    # Validar método
    try:
        method = TwoFactorMethod(request.method)
    except ValueError:
        raise HTTPException(status_code=400, detail="Método inválido. Use 'email' ou 'sms'")

    # Setup
    success, message = service.setup_2fa(
        user_id=current_user.id,
        method=method
    )

    if not success:
        raise HTTPException(status_code=400, detail=message)

    # Enviar código de verificação
    send_success, send_message = await service.send_otp_code(
        user_id=current_user.id,
        method=method,
        purpose="enable_2fa"
    )

    if not send_success:
        raise HTTPException(status_code=500, detail=send_message)

    # Buscar backup codes gerados
    from ..model.two_factor import TwoFactorSettings
    settings_2fa = db.query(TwoFactorSettings).filter(
        TwoFactorSettings.user_id == current_user.id
    ).first()

    import json
    backup_codes = json.loads(settings_2fa.backup_codes) if settings_2fa else []

    return APIResponse.success_response(
        data={
            "method": method.value,
            "backup_codes": backup_codes,
            "message": f"Código enviado por {method.value}"
        },
        message="Configure 2FA verificando o código enviado"
    )


@router.post("/enable", response_model=APIResponse)
async def enable_two_factor(
        request: Enable2FARequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Habilita 2FA após verificação do código"""
    service = TwoFactorService(db)

    # Verificar código
    valid, message = service.verify_otp_code(
        user_id=current_user.id,
        code=request.code,
        purpose="enable_2fa"
    )

    if not valid:
        raise HTTPException(status_code=400, detail=message)

    # Habilitar 2FA
    if service.enable_2fa(current_user.id):
        return APIResponse.success_response(
            message="Autenticação de dois fatores habilitada com sucesso"
        )

    raise HTTPException(status_code=500, detail="Erro ao habilitar 2FA")


@router.post("/verify", response_model=APIResponse)
async def verify_two_factor(
        request: Verify2FARequest,
        req: Request,
        db: Session = Depends(get_db)
):
    """Verifica código 2FA durante login"""
    from ..model.two_factor import OTPCode
    from datetime import datetime

    # Verificar token temporário
    temp_session = db.query(OTPCode).filter(
        OTPCode.code == request.temp_token,
        OTPCode.purpose == "2fa_verification",
        OTPCode.used == False,
        OTPCode.expires_at > datetime.now(fuso_local)
    ).first()

    if not temp_session:
        raise HTTPException(status_code=401, detail="Sessão expirada ou inválida")

    service = TwoFactorService(db)

    # Verificar código OTP
    valid, message = service.verify_otp_code(
        user_id=temp_session.user_id,
        code=request.code,
        purpose="login"
    )

    if not valid:
        raise HTTPException(status_code=401, detail=message)

    # Marcar token temporário como usado
    temp_session.used = True
    temp_session.used_at = datetime.now(fuso_local)
    db.commit()

    # Buscar usuário e criar tokens JWT
    user = db.query(User).filter(User.id == temp_session.user_id).first()

    from ..auth.jwt_handler import create_tokens
    tokens = create_tokens(user.id, user.email)

    # Log
    from ..util.logger import AuditLogger
    AuditLogger.log_auth_event(
        event_type="2fa_login_success",
        user_id=user.id,
        email=user.email,
        ip_address=req.client.host if req.client else None,
        success=True
    )

    return APIResponse.success_response(
        data={
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name
            }
        },
        message="Login realizado com sucesso"
    )


@router.post("/disable", response_model=APIResponse)
async def disable_two_factor(
        request: Disable2FARequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Desabilita 2FA (requer senha)"""
    service = TwoFactorService(db)

    success, message = service.disable_2fa(
        user_id=current_user.id,
        password=request.password
    )

    if not success:
        raise HTTPException(status_code=400, detail=message)

    return APIResponse.success_response(message=message)


@router.post("/backup-codes/regenerate", response_model=APIResponse)
async def regenerate_backup_codes(
        request: RegenerateBackupCodesRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Regenera códigos de backup (requer senha)"""
    from ..util.security import verify_password
    from ..model.two_factor import TwoFactorSettings
    import json

    # Verificar senha
    if not verify_password(request.password, current_user.password_hash):
        raise HTTPException(status_code=401, detail="Senha incorreta")

    # Verificar se 2FA está habilitado
    settings_2fa = db.query(TwoFactorSettings).filter(
        TwoFactorSettings.user_id == current_user.id,
        TwoFactorSettings.enabled == True
    ).first()

    if not settings_2fa:
        raise HTTPException(status_code=400, detail="2FA não está habilitado")

    # Gerar novos códigos
    TwoFactorService(db)
    new_codes = generate_backup_codes()

    # Salvar
    settings_2fa.backup_codes = json.dumps(new_codes)
    db.commit()

    # Log
    from ..util.logger import AuditLogger
    AuditLogger.log_auth_event(
        event_type="backup_codes_regenerated",
        user_id=current_user.id,
        email=current_user.email,
        success=True,
        details={"count": len(new_codes)}
    )

    return APIResponse.success_response(
        data={"backup_codes": new_codes},
        message="Novos códigos de backup gerados"
    )


@router.get("/status", response_model=APIResponse)
async def two_factor_status(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Retorna status do 2FA do usuário"""
    from ..model.two_factor import TwoFactorSettings
    import json

    settings_2fa = db.query(TwoFactorSettings).filter(
        TwoFactorSettings.user_id == current_user.id
    ).first()

    if not settings_2fa:
        return APIResponse.success_response(
            data={
                "enabled": False,
                "method": None,
                "backup_codes_count": 0
            }
        )

    backup_codes_count = 0
    if settings_2fa.backup_codes:
        backup_codes_count = len(json.loads(settings_2fa.backup_codes))

    return APIResponse.success_response(
        data={
            "enabled": settings_2fa.enabled,
            "method": settings_2fa.method.value if settings_2fa.method else None,
            "email_verified": settings_2fa.email_verified,
            "backup_codes_count": backup_codes_count,
            "last_used": settings_2fa.last_used.isoformat() if settings_2fa.last_used else None
        }
    )


@router.post("/resend-code", response_model=APIResponse)
async def resend_otp_code(
        current_user: User = Depends(get_current_user),
        req: Request = None,
        db: Session = Depends(get_db)
):
    """Reenvia código OTP"""
    from ..model.two_factor import TwoFactorSettings

    settings_2fa = db.query(TwoFactorSettings).filter(
        TwoFactorSettings.user_id == current_user.id
    ).first()

    if not settings_2fa:
        raise HTTPException(status_code=400, detail="2FA não configurado")

    service = TwoFactorService(db)

    success, message = await service.send_otp_code(
        user_id=current_user.id,
        method=settings_2fa.method,
        purpose="login",
        ip_address=req.client.host if req and req.client else None
    )

    if not success:
        raise HTTPException(status_code=429, detail=message)

    return APIResponse.success_response(
        message=f"Código reenviado por {settings_2fa.method.value}"
    )
