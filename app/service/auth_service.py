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
        <!DOCTYPE html>
        <html>
        <head>
            <style>        
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .container {{
                    background: #f0f0f0;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    padding: 0 0 30px 0;
                    width: fit-content;
                    max-width: 600px;
                }}
                .header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 30px;
                    border-radius: 10px 10px 0 0;
                    text-align: center;
                    margin: -30px -30px 30px -30px;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 28px;
                }}
                .main{{
                    padding:30px 70px 0 70px;
                }}
                .main h2 {{
                    margin: 10px 25px 35px;
                    font-size: 30px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎉 Bico Certo</h1>
                </div> 
                <div class="main"> 
                    <h2>Conta criada com Sucesso</h2>
                    <p style="font-size:18px;">Olá {user.full_name},</p>
                    <p>Sua conta criada com sucesso!<br> {datetime.now(fuso_local).strftime('%d/%m/%Y às %H:%M')}.</p>
                </div>
            </div>
        </body>
        </html>
        """

        await self.email_service.send_email(
            to_email=user.email,
            subject="Bem Vindo(a) - Bico Certo",
            body_html=html,
            body_text=f"Sua conta foi criada com sucesso."
        )
