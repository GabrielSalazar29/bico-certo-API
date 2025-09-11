from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Bico Certo API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "sqlite:///./test.db"  # Começar com SQLite

    # Security (vamos adicionar mais tarde)
    SECRET_KEY: str = "dev-secret-key-change-in-production"

    class Config:
        env_file = ".env"


settings = Settings()
