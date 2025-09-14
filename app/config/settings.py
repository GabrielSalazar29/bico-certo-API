from pydantic_settings import BaseSettings
from zoneinfo import ZoneInfo

fuso_local = ZoneInfo("America/Sao_Paulo")


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Bico Certo API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "sqlite:///./test.db"  # Começar com SQLite

    # JWT
    SECRET_KEY: str = "23ac218b5044ecd4dd69185b8f29395b99bb7040036fda69f526f21d0f08f14e"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    TWO_FACTOR_ENABLED: bool = True
    TWO_FACTOR_ISSUER: str = "Bico Certo"
    TWO_FACTOR_DEFAULT_METHOD: str = "email"

    # Email Settings (para 2FA por email)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str
    SMTP_PASSWORD: str
    SMTP_FROM: str = "noreply@bicocerto.com"
    EMAIL_USE_TLS: bool = True

    # Security Settings
    OTP_LENGTH: int = 6
    OTP_EXPIRY_MINUTES: int = 5
    OTP_MAX_ATTEMPTS: int = 3
    OTP_RESEND_COOLDOWN: int = 60

    BACKUP_CODES_COUNT: int = 8
    BACKUP_CODE_LENGTH: int = 8

    # Security Settings
    MAX_2FA_ATTEMPTS: int = 3
    ACCOUNT_LOCKOUT_MINUTES: int = 30

    # Password Recovery
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30
    PASSWORD_RESET_MAX_ATTEMPTS: int = 3

    # Frontend URL (para links nos emails)
    FRONTEND_URL: str = "http://localhost:3000"

    # Biometric Settings
    BIOMETRIC_API_KEY: str = ""
    BIOMETRIC_API_URL: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
