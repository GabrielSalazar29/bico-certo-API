import secrets
import json
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from ..model.user import User
from ..model.two_factor import TwoFactorSettings, OTPCode, TwoFactorMethod
from ..service.email_service import EmailService, generate_otp_email_template
from ..config.settings import settings, fuso_local


def generate_otp_code() -> str:
    """Gera código OTP de 6 dígitos"""
    return str(secrets.randbelow(1000000)).zfill(settings.OTP_LENGTH)


def generate_backup_codes(count: int = None) -> List[str]:
    """Gera códigos de backup"""
    if count is None:
        count = settings.BACKUP_CODES_COUNT

    codes = []
    for _ in range(count):
        # Formato: XXXX-XXXX
        part1 = secrets.token_hex(2).upper()
        part2 = secrets.token_hex(2).upper()
        codes.append(f"{part1}-{part2}")

    return codes


class TwoFactorService:
    """Serviço unificado para 2FA"""

    def __init__(self, db: Session):
        self.db = db
        self.email_service = EmailService()

    async def send_otp_code(
            self,
            user_id: str,
            method: TwoFactorMethod,
            purpose: str = "login",
            ip_address: Optional[str] = None,
            user_agent: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Envia código OTP por email ou SMS"""

        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return False, "Usuário não encontrado"

        # Invalidar códigos anteriores não utilizados
        self.db.query(OTPCode).filter(
            OTPCode.user_id == user_id,
            OTPCode.purpose == purpose,
            OTPCode.used == False
        ).update({"used": True, "used_at": datetime.now(fuso_local)})

        # Gerar novo código
        code = generate_otp_code()

        # Salvar no banco
        otp_code = OTPCode(
            user_id=user_id,
            code=code,
            method=method,
            purpose=purpose,
            expires_at=datetime.now(fuso_local) + timedelta(minutes=settings.OTP_EXPIRY_MINUTES),
            ip_address=ip_address,
            user_agent=user_agent
        )
        self.db.add(otp_code)
        self.db.commit()

        # Enviar código
        success = False

        if method == TwoFactorMethod.EMAIL:
            templates = generate_otp_email_template(
                code,
                user.full_name,
                purpose
            )

            success = await self.email_service.send_email(
                to_email=user.email,
                subject=f"Código de Verificação: {code}",
                body_html=templates["html"],
                body_text=templates["text"]
            )

        if success:
            return True, "Código enviado com sucesso"

        return False, "Erro ao enviar código"

    def verify_otp_code(
            self,
            user_id: str,
            code: str,
            purpose: str = "login"
    ) -> Tuple[bool, str]:
        """Verifica código OTP"""

        # Buscar código válido
        otp_code = self.db.query(OTPCode).filter(
            OTPCode.user_id == user_id,
            OTPCode.code == code,
            OTPCode.purpose == purpose,
            OTPCode.used == False,
            OTPCode.expires_at > datetime.now(fuso_local)
        ).first()

        if not otp_code:
            # Incrementar tentativas falhas
            self._increment_failed_attempts(user_id)

            # Verificar se é backup code
            if self._verify_backup_code(user_id, code):
                return True, "Código de backup válido"

            return False, "Código inválido ou expirado"

        # Verificar tentativas
        if otp_code.attempts >= settings.OTP_MAX_ATTEMPTS:
            return False, "Muitas tentativas para este código"

        # Marcar como usado
        otp_code.used = True
        otp_code.used_at = datetime.now(fuso_local)

        # Reset tentativas falhas
        self._reset_failed_attempts(user_id)

        self.db.commit()

        return True, "Código verificado com sucesso"

    def _verify_backup_code(self, user_id: str, code: str) -> bool:
        """Verifica e consome código de backup"""
        settings_2fa = self.db.query(TwoFactorSettings).filter(
            TwoFactorSettings.user_id == user_id
        ).first()

        if not settings_2fa or not settings_2fa.backup_codes:
            return False

        backup_codes = json.loads(settings_2fa.backup_codes)

        # Normalizar código
        normalized_code = code.replace("-", "").replace(" ", "").upper()

        for i, stored_code in enumerate(backup_codes):
            stored_normalized = stored_code.replace("-", "").replace(" ", "").upper()

            if stored_normalized == normalized_code:
                # Remover código usado
                backup_codes.pop(i)
                settings_2fa.backup_codes = json.dumps(backup_codes)
                settings_2fa.last_used = datetime.now(fuso_local)
                self.db.commit()

                return True

        return False

    def _increment_failed_attempts(self, user_id: str):
        """Incrementa tentativas falhas"""
        settings_2fa = self.db.query(TwoFactorSettings).filter(
            TwoFactorSettings.user_id == user_id
        ).first()

        if settings_2fa:
            settings_2fa.failed_attempts += 1

            if settings_2fa.failed_attempts >= settings.MAX_2FA_ATTEMPTS:
                settings_2fa.locked_until = datetime.now(fuso_local) + timedelta(
                    minutes=settings.ACCOUNT_LOCKOUT_MINUTES
                )

            self.db.commit()

    def _reset_failed_attempts(self, user_id: str):
        """Reset tentativas falhas"""
        settings_2fa = self.db.query(TwoFactorSettings).filter(
            TwoFactorSettings.user_id == user_id
        ).first()

        if settings_2fa:
            settings_2fa.failed_attempts = 0
            settings_2fa.locked_until = None
            self.db.commit()

    def setup_2fa(
            self,
            user_id: str,
            method: TwoFactorMethod,
    ) -> Tuple[bool, str]:
        """Configura 2FA para o usuário"""

        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return False, "Usuário não encontrado"

        # Verificar ou criar settings
        settings_2fa = self.db.query(TwoFactorSettings).filter(
            TwoFactorSettings.user_id == user_id
        ).first()

        if not settings_2fa:
            settings_2fa = TwoFactorSettings(
                user_id=user_id,
                method=method,
                enabled=False
            )
            self.db.add(settings_2fa)
        else:
            settings_2fa.method = method

        # Gerar backup codes
        backup_codes = generate_backup_codes()
        settings_2fa.backup_codes = json.dumps(backup_codes)

        self.db.commit()

        return True, "2FA configurado. Verifique seu método escolhido."

    def enable_2fa(self, user_id: str) -> bool:
        """Habilita 2FA após verificação"""
        settings_2fa = self.db.query(TwoFactorSettings).filter(
            TwoFactorSettings.user_id == user_id
        ).first()

        if not settings_2fa:
            return False

        settings_2fa.enabled = True

        # Atualizar usuário
        user = self.db.query(User).filter(User.id == user_id).first()
        user.two_factor_enabled = True
        user.preferred_2fa_method = settings_2fa.method.value

        self.db.commit()

        return True

    def disable_2fa(self, user_id: str, password: str) -> Tuple[bool, str]:
        """Desabilita 2FA (requer senha)"""
        from ..util.security import verify_password

        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return False, "Usuário não encontrado"

        # Verificar senha
        if not verify_password(password, user.password_hash):
            return False, "Senha incorreta"

        # Desabilitar
        settings_2fa = self.db.query(TwoFactorSettings).filter(
            TwoFactorSettings.user_id == user_id
        ).first()

        if settings_2fa:
            settings_2fa.enabled = False

        user.two_factor_enabled = False
        user.preferred_2fa_method = None

        self.db.commit()

        return True, "2FA desabilitado com sucesso"
