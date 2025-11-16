from datetime import datetime

from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..config.database import Base
import uuid

from ..config.settings import fuso_local


class PasswordResetToken(Base):
    """Tokens de recuperação de senha"""
    __tablename__ = "password_reset_tokens"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)

    # Token único para identificar a solicitação
    token = Column(String, unique=True, nullable=False, index=True)

    # Código de verificação (6 dígitos)
    verification_code = Column(String, nullable=False)

    # Controle
    used = Column(Boolean, default=False)
    used_at = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True), nullable=False)

    # Segurança
    ip_address = Column(String)
    user_agent = Column(String)
    attempts = Column(Integer, default=0)

    # Se o usuário tem 2FA, precisa verificar também
    requires_2fa_verification = Column(Boolean, default=False)
    two_fa_verified = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.now(fuso_local))

    # Relationship
    user = relationship("User", back_populates="password_reset_tokens")
