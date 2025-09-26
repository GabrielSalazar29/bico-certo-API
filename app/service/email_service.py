import datetime

import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict
from ..config.settings import settings


def generate_otp_email_template(code: str, user_name: str, purpose: str = "login") -> Dict[str, str]:
    """Gera templates HTML e texto para email de OTP"""

    purpose_text = {
        "login": "fazer login",
        "enable_2fa": "habilitar autenticação de dois fatores",
        "verify_email": "verificar seu email",
        "reset_password": "redefinir sua senha"
    }.get(purpose, "continuar")

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
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
            .header h1 {{
                margin: 0;
                font-size: 28px;
            }}
            .code-box {{ 
                background: #f8f9fa;
                border: 2px solid #667eea;
                border-radius: 8px;
                font-size: 36px;
                font-weight: bold;
                text-align: center;
                padding: 25px;
                margin: 30px 0;
                letter-spacing: 10px;
                color: #667eea;
                font-family: 'Courier New', monospace;
            }}
            .warning {{
                background: #fff3cd;
                border-left: 4px solid #ffc107;
                padding: 15px;
                margin: 20px 0;
                border-radius: 4px;
            }}
            .footer {{ 
                text-align: center;
                color: #6c757d;
                font-size: 14px;
                margin-top: 40px;
                padding-top: 20px;
                border-top: 1px solid #dee2e6;
            }}
            .button {{
                display: inline-block;
                padding: 12px 30px;
                background: #667eea;
                color: white;
                text-decoration: none;
                border-radius: 5px;
                margin: 20px 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔐 Bico Certo</h1>
                <p style="margin: 10px 0 0 0; font-size: 16px;">Código de Verificação</p>
            </div>

            <p style="font-size: 18px;">Olá <strong>{user_name}</strong>,</p>

            <p>Você solicitou um código para <strong>{purpose_text}</strong>.</p>

            <p>Seu código de verificação é:</p>

            <div class="code-box">{code}</div>

            <div class="warning">
                <strong>⚠️ Importante:</strong>
                <ul style="margin: 10px 0 0 0; padding-left: 20px;">
                    <li>Este código expira em <strong>5 minutos</strong></li>
                    <li>Não compartilhe este código com ninguém</li>
                    <li>Nossa equipe nunca pedirá este código</li>
                </ul>
            </div>

            <p>Se você não solicitou este código, por favor ignore este email e considere alterar sua senha.</p>

            <div class="footer">
                <p><strong>Bico Certo</strong> - Conectando Profissionais</p>
                <p>Este é um email automático, por favor não responda.</p>
                <p style="font-size: 12px; color: #999;">
                    © {datetime.datetime.now().year} Bico Certo. Todos os direitos reservados.
                </p>
            </div>
        </div>
    </body>
    </html>
    """

    text = f"""
    Bico Certo - Código de Verificação

    Olá {user_name},

    Você solicitou um código para {purpose_text}.

    Seu código de verificação é: {code}

    IMPORTANTE:
    - Este código expira em 5 minutos
    - Não compartilhe este código com ninguém
    - Nossa equipe nunca pedirá este código

    Se você não solicitou este código, ignore este email.

    Atenciosamente,
    Equipe Bico Certo

    Este é um email automático, por favor não responda.
    """

    return {"html": html, "text": text}


class EmailService:
    """Serviço para envio de emails"""

    def __init__(self):
        self.host = settings.SMTP_HOST
        self.port = settings.SMTP_PORT
        self.username = settings.SMTP_USER
        self.password = settings.SMTP_PASSWORD
        self.from_email = settings.SMTP_FROM
        self.use_tls = settings.EMAIL_USE_TLS

    async def send_email(
            self,
            to_email: str,
            subject: str,
            body_html: str,
            body_text: Optional[str] = None
    ) -> bool:
        """Envia email assíncrono"""
        try:
            message = MIMEMultipart("alternative")
            message["From"] = self.from_email
            message["To"] = to_email
            message["Subject"] = subject

            # Parte texto
            if body_text:
                part_text = MIMEText(body_text, "plain", "utf-8")
                message.attach(part_text)

            # Parte HTML
            part_html = MIMEText(body_html, "html", "utf-8")
            message.attach(part_html)

            # Enviar
            await aiosmtplib.send(
                message,
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                start_tls=self.use_tls
            )

            return True

        except Exception as e:
            return False
