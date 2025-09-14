from sqlalchemy.orm import Session
from datetime import datetime
from ..model.user import User
from ..service.email_service import EmailService
from ..config.settings import fuso_local


class AuthService:
    """Serviço para autenticação"""

    def __init__(self, db: Session):
        self.db = db
        self.email_service = EmailService()

    async def send_confirmation_email(self, user: User):
        """Envia email confirmando criação da conta"""

        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2>Conta criada com Sucesso</h2>
            <p>Olá {user.full_name},</p>
            <p>Sua conta criada com sucesso em {datetime.now(fuso_local).strftime('%d/%m/%Y às %H:%M')}.</p>
        </body>
        </html>
        """

        await self.email_service.send_email(
            to_email=user.email,
            subject="Bem Vindo(a) - Bico Certo",
            body_html=html,
            body_text=f"Sua conta foi criada com sucesso."
        )
