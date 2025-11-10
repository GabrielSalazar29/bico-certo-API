from pydantic_settings import BaseSettings
from zoneinfo import ZoneInfo

fuso_local = ZoneInfo("America/Sao_Paulo")


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Bico Certo API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "sqlite:///./test.db"

    # JWT
    SECRET_KEY: str = "23ac218b5044ecd4dd69185b8f29395b99bb7040036fda69f526f21d0f08f14e"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 600

    TWO_FACTOR_ENABLED: bool = True

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

    # Blockchain Configuration
    NETWORK_TYPE: str = "private"  # "private", "testnet", "mainnet"
    WEB3_PROVIDER_URL: str = "http://127.0.0.1:8545"
    ZERO_GAS_COST: bool = True  # Gas gratuito para rede privada
    NETWORK_CHAIN_ID: int = 1337  # Chain ID do Ganache/Hardhat

    # Wallet Configuration
    WALLET_ENCRYPTION_KEY: str
    MNEMONIC_LANGUAGE: str = "english"
    MNEMONIC_STRENGTH: int = 128

    IPFS_API_URL: str = "/ip4/127.0.0.1/tcp/5001"  # API do IPFS
    IPFS_GATEWAY_URL: str = "http://localhost:8080"  # Gateway para acessar arquivos

    class Config:
        env_file = ".env"


settings = Settings()
