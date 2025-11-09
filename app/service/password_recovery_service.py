import asyncio
import secrets
from typing import Tuple, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from ..model.user import User
from ..model.password_reset import PasswordResetToken
from ..service.email_service import EmailService
from ..config.settings import settings, fuso_local
from ..util.security import hash_password
from ..util.validators import PasswordValidator
from .two_factor_service import generate_otp_code


def generate_reset_token() -> str:
    """Gera token único para reset"""
    return secrets.token_urlsafe(32)


class PasswordRecoveryService:
    """Serviço para recuperação de senha com 2FA"""

    def __init__(self, db: Session):
        self.db = db
        self.email_service = EmailService()

    async def request_password_reset(
            self,
            email: str,
            ip_address: Optional[str] = None,
            user_agent: Optional[str] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Inicia processo de recuperação de senha
        Retorna: (sucesso, mensagem, reset_token se aplicável)
        """
        # Buscar usuário
        user = self.db.query(User).filter(User.email == email).first()
        # IMPORTANTE: Sempre retornar sucesso para não revelar se email existe
        if not user:
            # Retorna sucesso falso para segurança
            return True, "Se o email existir, você receberá instruções de recuperação.", None
        # Verificar se já existe token ativo
        existing_token = self.db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used == False,
            PasswordResetToken.expires_at > datetime.now(fuso_local)
        ).first()
        if existing_token:
            # Rate limiting - não permite novo token se já existe um válido
            time_remaining = (existing_token.expires_at.replace(tzinfo=fuso_local) - datetime.now(fuso_local)).seconds // 60
            return False, f"Já existe uma solicitação ativa. Aguarde {time_remaining} minutos.", None
        # Invalidar tokens antigos
        self.db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used == False
        ).update({"used": True, "used_at": datetime.now(fuso_local)})

        # Criar novo token
        reset_token = generate_reset_token()
        verification_code = generate_otp_code()

        # Verificar se usuário tem 2FA habilitado
        has_2fa = user.two_factor_enabled

        password_reset = PasswordResetToken(
            user_id=user.id,
            token=reset_token,
            verification_code=verification_code,
            expires_at=datetime.now(fuso_local) + timedelta(minutes=30),  # 30 minutos
            ip_address=ip_address,
            user_agent=user_agent,
            requires_2fa_verification=has_2fa
        )

        self.db.add(password_reset)
        self.db.commit()

        # Enviar email
        success = await self._send_reset_email(user, reset_token, verification_code)

        if success:
            return True, "Instruções de recuperação enviadas para seu email.", reset_token

        return False, "Erro ao enviar email. Tente novamente.", None

    async def _send_reset_email(
            self,
            user: User,
            reset_token: str,
            verification_code: str
    ) -> bool:
        """Envia email com instruções de reset"""

        # URL do frontend para reset (ajustar conforme necessário)
        # Trechos com reset_url, comentados.
        reset_url = f"{settings.FRONTEND_URL}/reset-password"
        
        html_template = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .container {{
                    background: white;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    padding: 30px;
                }}
                .header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 30px;
                    border-radius: 10px 10px 0 0;
                    text-align: center;
                    margin: -30px -30px 30px -30px;
                }}
                .code-box {{
                    background: #f8f9fa;
                    border: 2px solid #667eea;
                    border-radius: 8px;
                    font-size: 32px;
                    font-weight: bold;
                    text-align: center;
                    padding: 20px;
                    margin: 25px 0;
                    letter-spacing: 8px;
                    color: #667eea;
                    font-family: 'Courier New', monospace;
                }}
                .button {{
                    display: inline-block;
                    padding: 14px 32px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white !important;
                    text-decoration: none;
                    border-radius: 8px;
                    font-weight: bold;
                    margin: 20px 0;
                    text-align: center;
                }}
                .warning {{
                    background: #fff3cd;
                    border-left: 4px solid #ffc107;
                    padding: 15px;
                    margin: 20px 0;
                    border-radius: 4px;
                }}
                .steps {{
                    background: #f8f9fa;
                    padding: 20px;
                    border-radius: 8px;
                    margin: 20px 0;
                }}
                .step {{
                    display: flex;
                    align-items: center;
                    margin: 15px 0;
                }}
                .step-number {{
                    background: #667eea;
                    color: white;
                    width: 30px;
                    height: auto;
                    border-radius: 50%;
                    padding: 5px 0px;
                    text-align: center;
                    margin-right: 15px;
                    font-weight: bold;
                }}
                .footer {{
                    text-align: center;
                    color: #6c757d;
                    font-size: 14px;
                    margin-top: 40px;
                    padding-top: 20px;
                    border-top: 1px solid #dee2e6;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔐 Recuperação de Senha</h1>
                    <p style="margin: 10px 0 0 0; font-size: 16px;">Bico Certo</p>
                </div>

                <p style="font-size: 18px;">Olá <strong>{user.full_name}</strong>,</p>

                <p>Recebemos uma solicitação para redefinir sua senha. Se você não fez esta solicitação, pode ignorar este email.</p>

                <div class="steps">
                    <h3 style="margin-top: 0;">Para redefinir sua senha:</h3>

                    <div class="step">
                        <div class="step-number">1</div>
                        <div>Clique no botão abaixo ou copie o link</div>
                    </div>

                    <div class="step">
                        <div class="step-number">2</div>
                        <div>Digite o código de verificação quando solicitado</div>
                    </div>

                    <div class="step">
                        <div class="step-number">3</div>
                        <div>Crie sua nova senha</div>
                    </div>
                </div>

                <p><strong>Seu código de verificação:</strong></p>
                <div class="code-box">{verification_code}</div>

                <!--<div style="text-align: center;">
                    <a href="{reset_url}" class="button">Redefinir Minha Senha</a>
                </div>

                <p style="color: #6c757d; font-size: 14px;">
                    Ou copie e cole este link no seu navegador:<br>
                    <code style="background: #f8f9fa; padding: 5px; border-radius: 3px; word-break: break-all;">
                        {reset_url}
                    </code>
                </p>-->

                <div class="warning">
                    <strong>⚠️ Importante:</strong>
                    <ul style="margin: 10px 0 0 0; padding-left: 20px;">
                        <li>Este link expira em <strong>30 minutos</strong></li>
                        <li>O código só pode ser usado <strong>uma vez</strong></li>
                        <li>Nunca compartilhe este código ou link com ninguém</li>
                        {"<li>Como você tem <strong>2FA habilitado</strong>, precisará verificá-lo também</li>" if user.two_factor_enabled else ""}
                    </ul>
                </div>

                <p style="color: #6c757d;">
                    Se você não solicitou esta recuperação de senha, por favor ignore este email 
                    e considere verificar a segurança da sua conta.
                </p>

                <div class="footer">
                    <p><strong>Bico Certo</strong> - Conectando Profissionais</p>
                    <p>Este é um email automático, por favor não responda.</p>
                    <p style="font-size: 12px; color: #999;">
                        © {datetime.now().year} Bico Certo. Todos os direitos reservados.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """

        text_template = f"""
        Recuperação de Senha - Bico Certo

        Olá {user.full_name},

        Recebemos uma solicitação para redefinir sua senha.

        Seu código de verificação é: {verification_code}

        <!--Para redefinir sua senha, acesse:
        {reset_url}-->

        Este link expira em 30 minutos e só pode ser usado uma vez.

        {"ATENÇÃO: Como você tem 2FA habilitado, precisará verificá-lo também." if user.two_factor_enabled else ""}

        Se você não solicitou esta recuperação, ignore este email.

        Atenciosamente,
        Equipe Bico Certo
        """

        return await self.email_service.send_email(
            to_email=user.email,
            subject="Recuperação de Senha - Bico Certo",
            body_html=html_template,
            body_text=text_template
        )

    def verify_reset_code(
            self,
            reset_token: str,
            verification_code: str
    ) -> Tuple[bool, str, Optional[dict]]:
        """
        Verifica código de reset
        Retorna: (sucesso, mensagem, dados_adicionais)
        """

        # Buscar token
        password_reset = self.db.query(PasswordResetToken).filter(
            PasswordResetToken.token == reset_token,
            PasswordResetToken.used == False
        ).first()

        if not password_reset:
            return False, "Token inválido ou expirado", None

        # Verificar expiração
        if password_reset.expires_at.replace(tzinfo=fuso_local) < datetime.now(fuso_local):
            password_reset.used = True
            password_reset.used_at = datetime.now(fuso_local)
            self.db.commit()
            return False, "Token expirado. Solicite nova recuperação.", None

        # Verificar tentativas
        if password_reset.attempts >= 3:
            password_reset.used = True
            password_reset.used_at = datetime.now(fuso_local)
            self.db.commit()
            return False, "Muitas tentativas falhas. Solicite nova recuperação.", None

        # Verificar código
        if password_reset.verification_code != verification_code:
            password_reset.attempts += 1
            self.db.commit()

            attempts_remaining = 3 - password_reset.attempts
            return False, f"Código incorreto. {attempts_remaining} tentativas restantes.", None

        # Tudo verificado, pode resetar senha
        return True, "Código verificado com sucesso", {
            "can_reset": True,
            "user_id": password_reset.user_id
        }

    def reset_password(
            self,
            reset_token: str,
            new_password: str,
            ip_address: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Efetua o reset da senha
        """

        # Validar nova senha
        is_valid, error_message = PasswordValidator.validate(new_password)
        if not is_valid:
            return False, error_message

        # Buscar token
        password_reset = self.db.query(PasswordResetToken).filter(
            PasswordResetToken.token == reset_token,
            PasswordResetToken.used == False
        ).first()

        if not password_reset:
            return False, "Token inválido ou já utilizado"

        # Verificar se tudo foi verificado
        if password_reset.requires_2fa_verification and not password_reset.two_fa_verified:
            return False, "Verificação 2FA necessária"

        # Buscar usuário
        user = self.db.query(User).filter(User.id == password_reset.user_id).first()

        if not user:
            return False, "Usuário não encontrado"

        # Atualizar senha
        user.password_hash = hash_password(new_password)
        user.last_password_change = datetime.now(fuso_local)

        # Marcar token como usado
        password_reset.used = True
        password_reset.used_at = datetime.now(fuso_local)

        # Invalidar todas as sessões do usuário (forçar novo login)
        from ..model.session import Session
        self.db.query(Session).filter(
            Session.user_id == user.id,
            Session.is_active == True
        ).update({
            "is_active": False,
            "revoked_at": datetime.now(fuso_local)
        })

        self.db.commit()

        # Enviar email de confirmação
        asyncio.create_task(self._send_confirmation_email(user))

        return True, "Senha alterada com sucesso. Faça login com sua nova senha."

    async def _send_confirmation_email(self, user: User):
        """Envia email confirmando mudança de senha"""

        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2>Senha Alterada com Sucesso</h2>
            <p>Olá {user.full_name},</p>
            <p>Sua senha foi alterada com sucesso em {datetime.now(fuso_local).strftime('%d/%m/%Y às %H:%M')}.</p>
            <p>Se você não fez esta alteração, entre em contato imediatamente com nosso suporte.</p>
            <p>Por segurança, todas as suas sessões foram encerradas. Você precisará fazer login novamente.</p>
        </body>
        </html>
        """

        await self.email_service.send_email(
            to_email=user.email,
            subject="Senha Alterada - Bico Certo",
            body_html=html,
            body_text=f"Sua senha foi alterada com sucesso. Se não foi você, contate o suporte."
        )
