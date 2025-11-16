import asyncio

from ..model.wallet import Wallet
from ..service.auth_service import AuthService
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from ..config.database import get_db
from ..model.user import User, RefreshToken
from ..model.device import Device
from ..util.responses import APIResponse
from ..util.validators import PasswordValidator, EmailValidator
from ..util.exceptions import ValidationException
from ..schema.user import UserCreate, UserProfileUpdate, UserResponse
from ..schema.auth import LoginRequest, RefreshRequest, TokenResponse
from ..util.security import hash_password, verify_password
from ..util.device import generate_fingerprint
from ..auth.dependencies import get_current_user
from ..auth.jwt_handler import create_tokens
from datetime import datetime, timedelta
from typing import List
from ..model.session import Session
from ..util.exceptions import AuthException
import uuid
from ..config.settings import settings, fuso_local
from ..model.two_factor import TwoFactorSettings, OTPCode, TwoFactorMethod
from ..service.two_factor_service import TwoFactorService
import secrets

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=APIResponse)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    service = AuthService(db)

    if not EmailValidator.validate(user_data.email):
        raise ValidationException(
            detail="Formato de email inválido",
            field="email"
        )

    if EmailValidator.is_disposable(user_data.email):
        raise ValidationException(
            detail="Emails temporários não são permitidos",
            field="email"
        )

    is_valid, error_message = PasswordValidator.validate(user_data.password)
    if not is_valid:
        raise ValidationException(
            detail=error_message,
            field="password"
        )

    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:

        raise ValidationException(
            detail="Este email já está cadastrado",
            field="email"
        )

    try:
        user = User(
            email=user_data.email,
            full_name=user_data.full_name,
            password_hash=hash_password(user_data.password)
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        asyncio.create_task(service.send_confirmation_email(user))

        return APIResponse.success_response(
            data={
                "user_id": user.id,
                "email": user.email,
                "full_name": user.full_name
            },
            message="Usuário criado com sucesso! Verifique seu email."
        )

    except Exception as e:
        db.rollback()

        raise ValidationException(
            detail="Erro ao criar usuário. Tente novamente."
        )


@router.post("/login", response_model=APIResponse)
async def login(credentials: LoginRequest, request: Request, db: Session = Depends(get_db)):
    # Buscar usuário
    user = db.query(User).filter(User.email == credentials.email).first()

    # Verificar se conta está bloqueada
    if user and user.locked_until and user.locked_until.replace(tzinfo=fuso_local) > datetime.now(fuso_local):
        time_remaining = (user.locked_until.replace(tzinfo=fuso_local) - datetime.now(fuso_local)).seconds // 60

        raise AuthException(
            detail=f"Conta bloqueada. Tente em {time_remaining} minutos.",
            status_code=403
        )

    # Verificar se existe e senha está correta
    if not user or not verify_password(credentials.password, user.password_hash):
        if user:
            # INCREMENTAR TENTATIVAS FALHAS
            user.failed_login_attempts += 1

            if user.failed_login_attempts >= 5:
                user.locked_until = datetime.now(fuso_local) + timedelta(minutes=15)
                db.commit()

                raise AuthException(
                    detail="Conta bloqueada por 15 minutos após 5 tentativas falhas",
                    status_code=403
                )

            db.commit()

        raise AuthException(detail="Email ou senha incorretos")

    # Reset tentativas em login bem-sucedido
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = datetime.now(fuso_local)
    user.last_ip = request.client.host

    # Verificar se está ativo
    if not user.is_active:
        raise AuthException(detail="Usuário inativo")

    # Verifica se tem 2FA
    if user.two_factor_enabled:
        settings_2fa = db.query(TwoFactorSettings).filter(
            TwoFactorSettings.user_id == user.id,
            TwoFactorSettings.enabled == True
        ).first()

        if settings_2fa:
            # Verificar se conta está bloqueada por muitas tentativas 2FA
            if settings_2fa.locked_until and settings_2fa.locked_until.replace(tzinfo=fuso_local) > datetime.now(fuso_local):
                time_remaining = (settings_2fa.locked_until.replace(tzinfo=fuso_local) - datetime.now(fuso_local)).seconds // 60

                raise AuthException(
                    detail=f"2FA bloqueado. Tente em {time_remaining} minutos.",
                    status_code=403
                )

            # Criar token temporário para verificação 2FA
            temp_token = secrets.token_urlsafe(32)

            # Salvar token temporário
            temp_session = OTPCode(
                user_id=user.id,
                code=temp_token,  # Usamos o campo code para o token
                method=settings_2fa.method,
                purpose="2fa_verification",
                expires_at=datetime.now(fuso_local) + timedelta(minutes=10),
                ip_address=request.client.host,
                user_agent=request.headers.get("user-agent", "unknown")
            )
            db.add(temp_session)
            db.commit()

            # Enviar código OTP
            service = TwoFactorService(db)
            await service.send_otp_code(
                user_id=user.id,
                method=settings_2fa.method,
                purpose="login",
                ip_address=request.client.host,
                user_agent=request.headers.get("user-agent")
            )

            return APIResponse.success_response(
                data={
                    "requires_2fa": True,
                    "method": settings_2fa.method.value,
                    "temp_token": temp_token,
                    "user_id": user.id,
                    "masked_contact": _mask_contact(user, settings_2fa)
                },
                message="Verificação de dois fatores necessária"
            )

    wallet = db.query(Wallet).filter(user.id == Wallet.user_id).first()
    address = None
    if wallet:
        address = wallet.address

    device_dict = credentials.device_info.dict()
    fingerprint = generate_fingerprint(device_dict)

    device = db.query(Device).filter(Device.fingerprint == fingerprint).first()


    if not device:
        # Novo dispositivo
        device = Device(
            user_id=user.id,
            device_id=credentials.device_info.device_id,
            platform=credentials.device_info.platform,
            model=credentials.device_info.model,
            os_version=credentials.device_info.os_version,
            app_version=credentials.device_info.app_version,
            fingerprint=fingerprint,
            last_ip=request.client.host
        )
        db.add(device)
    else:
        # Atualizar device existente
        device.last_seen = datetime.now(fuso_local)
        device.last_ip = request.client.host

    # if is_new_device and user.two_factor_enabled:
    #     pass

    # Criar tokens
    tokens = create_tokens(user.id, user.email)

    session = Session(
        user_id=user.id,
        device_id=device.id,
        access_token_jti=str(uuid.uuid4()),  # JWT ID único
        refresh_token=tokens["refresh_token"],
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent", "unknown"),
        expires_at=tokens["refresh_expires_at"],
        is_active=True
    )

    db.add(session)

    # Salvar refresh token no banco
    refresh_token = RefreshToken(
        user_id=user.id,
        token=tokens["refresh_token"],
        expires_at=tokens["refresh_expires_at"]
    )
    db.add(refresh_token)
    db.commit()

    return APIResponse.success_response(
        data={
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "address": address
            }
        },
        message="Login realizado com sucesso!"
    )


def _mask_contact(user: User, settings_2fa: TwoFactorSettings) -> str:
    """Mascara email ou telefone para exibição"""
    if settings_2fa.method == TwoFactorMethod.EMAIL:
        email = user.email
        parts = email.split("@")
        if len(parts[0]) > 3:
            masked = parts[0][:2] + "*" * (len(parts[0]) - 3) + parts[0][-1]
        else:
            masked = parts[0][0] + "*" * (len(parts[0]) - 1)
        return f"{masked}@{parts[1]}"

    return ""


@router.get("/{user_id}/profile-picture", response_model=APIResponse)
async def get_user_profile_picture(
        user_id: str,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Retorna a URL da foto de perfil de um usuário
    """

    try:
        # Buscar usuário no banco
        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            raise HTTPException(
                status_code=404,
                detail="Usuário não encontrado"
            )

        return APIResponse.success_response(
            data={
                "user_id": user.id,
                "profile_pic_url": user.profile_pic_url,
                "full_name": user.full_name,
            },
            message="Foto de perfil recuperada com sucesso"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao buscar foto de perfil: {str(e)}"
        )

@router.post("/refresh", response_model=TokenResponse)
def refresh_token(request: RefreshRequest, db: Session = Depends(get_db)):
    # Buscar refresh token
    stored_token = db.query(RefreshToken).filter(
        RefreshToken.token == request.refresh_token,
        RefreshToken.revoked == False
    ).first()

    if not stored_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido"
        )

    # Verificar se expirou
    if stored_token.expires_at.replace(tzinfo=fuso_local) < datetime.now(fuso_local):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expirado"
        )

    # Revogar token antigo
    stored_token.revoked = True

    # Criar novos tokens
    tokens = create_tokens(stored_token.user_id, stored_token.user.email)

    # Salvar novo refresh token
    new_refresh_token = RefreshToken(
        user_id=stored_token.user_id,
        token=tokens["refresh_token"],
        expires_at=tokens["refresh_expires_at"]
    )
    db.add(new_refresh_token)
    db.commit()

    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"]
    )


@router.get("/devices", response_model=List[dict])
async def list_devices(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    devices = db.query(Device).filter(Device.user_id == current_user.id).all()

    return [
        {
            "id": d.id,
            "platform": d.platform,
            "model": d.model,
            "trusted": d.trusted,
            "last_seen": d.last_seen,
            "last_ip": d.last_ip
        }
        for d in devices
    ]


@router.delete("/devices/{device_id}")
async def remove_device(
        device_id: str,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    device = db.query(Device).filter(
        Device.id == device_id,
        Device.user_id == current_user.id
    ).first()

    if not device:
        raise HTTPException(status_code=404, detail="Device não encontrado")

    db.delete(device)
    db.commit()

    return {"message": "Device removido"}


@router.post("/logout", response_model=APIResponse)
async def logout(
        current_user: User = Depends(get_current_user),
        all_devices: bool = False,
        db: Session = Depends(get_db)
):
    """Logout com resposta padronizada"""

    if all_devices:
        # LOGOUT DE TODOS OS DISPOSITIVOS
        sessions = db.query(Session).filter(
            Session.user_id == current_user.id,
            Session.is_active == True
        ).all()

        for session in sessions:
            session.is_active = False
            session.revoked_at = datetime.now(fuso_local)

        # Revogar todos os refresh tokens
        refresh_tokens = db.query(RefreshToken).filter(
            RefreshToken.user_id == current_user.id,
            RefreshToken.revoked == False
        ).all()

        for token in refresh_tokens:
            token.revoked = True

        db.commit()

        return APIResponse.success_response(
            message=f"Logout realizado em {len(sessions)} dispositivos"
        )

    else:
        # LOGOUT APENAS DA SESSÃO ATUAL
        # Por simplicidade, vamos invalidar o último refresh token
        # Em produção, rastrear qual token está sendo usado

        return APIResponse.success_response(
            message="Logout realizado com sucesso"
        )


@router.get("/me", response_model=APIResponse)
async def get_me(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Retorna informações do usuário atual com resposta padronizada"""

    # Buscar sessões ativas
    active_sessions = db.query(Session).filter(
        Session.user_id == current_user.id,
        Session.is_active == True
    ).count()

    # Buscar dispositivos
    devices = db.query(Device).filter(
        Device.user_id == current_user.id
    ).all()

    return APIResponse.success_response(
        data={
            "user": {
                "id": current_user.id,
                "email": current_user.email,
                "full_name": current_user.full_name,
                "is_active": current_user.is_active,
                "created_at": current_user.created_at.isoformat(),
                "description": current_user.description,
                "city": current_user.city,
                "state": current_user.state,
                "profile_pic_url": current_user.profile_pic_url
            },
            "security": {
                "active_sessions": active_sessions,
                "registered_devices": len(devices),
                "two_factor_enabled": getattr(current_user, 'two_factor_enabled', False)
            }
        },
        message="Dados recuperados com sucesso"
    )

@router.put("/profile", response_model=APIResponse)
async def update_profile(
    profile_data: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Atualiza o perfil do usuário (nome, descrição, local, foto)
    """
    
    update_data = profile_data.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nenhum dado fornecido para atualização"
        )

    for key, value in update_data.items():
        if hasattr(current_user, key):
            setattr(current_user, key, value)

    try:
        db.commit()
        db.refresh(current_user)

        updated_user_data = UserResponse.model_validate(current_user).model_dump()

        return APIResponse.success_response(
            data=updated_user_data,
            message="Perfil atualizado com sucesso"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao atualizar perfil: {str(e)}"
        )


@router.get("/sessions", response_model=APIResponse)
async def list_sessions(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Lista todas as sessões ativas do usuário"""

    sessions = db.query(Session).filter(
        Session.user_id == current_user.id,
        Session.is_active == True
    ).all()

    sessions_data = []
    for session in sessions:
        device = db.query(Device).filter(Device.id == session.device_id).first()

        sessions_data.append({
            "id": session.id,
            "device": {
                "platform": device.platform if device else "unknown",
                "model": device.model if device else "unknown",
                "last_ip": session.ip_address
            },
            "created_at": session.created_at.isoformat(),
            "last_activity": session.last_activity.isoformat() if session.last_activity else None,
            "expires_at": session.expires_at.isoformat()
        })

    return APIResponse.success_response(
        data=sessions_data,
        message=f"Você tem {len(sessions_data)} sessões ativas"
    )


@router.delete("/sessions/{session_id}", response_model=APIResponse)
async def revoke_session(
        session_id: str,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Revoga uma sessão específica"""

    session = db.query(Session).filter(
        Session.id == session_id,
        Session.user_id == current_user.id
    ).first()

    if not session:
        raise ValidationException(
            detail="Sessão não encontrada",
            field="session_id"
        )

    session.is_active = False
    session.revoked_at = datetime.now(fuso_local)

    db.commit()

    return APIResponse.success_response(
        message="Sessão revogada com sucesso"
    )
