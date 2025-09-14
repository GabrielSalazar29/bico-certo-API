from sqlalchemy import Column, String, Boolean, DateTime, Integer, Enum as SQLEnum, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..config.database import Base
import uuid
import enum


class TwoFactorMethod(enum.Enum):
    EMAIL = "email"  # Código por email
    BIOMETRIC = "biometric"  # Biometria (mobile)


class TwoFactorSettings(Base):
    """Configurações de 2FA do usuário"""
    __tablename__ = "two_factor_settings"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), unique=True, nullable=False)

    # Configurações
    enabled = Column(Boolean, default=False)
    method = Column(SQLEnum(TwoFactorMethod), default=TwoFactorMethod.EMAIL)

    # Contatos verificados
    email_verified = Column(Boolean, default=False)

    # Backup codes (JSON array)
    backup_codes = Column(Text)  # JSON com códigos de backup

    # Segurança
    failed_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime(timezone=True))
    last_used = Column(DateTime(timezone=True))

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationship
    user = relationship("User", back_populates="two_factor_settings")


class OTPCode(Base):
    """Códigos OTP temporários"""
    __tablename__ = "otp_codes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)

    code = Column(String, nullable=False)
    method = Column(SQLEnum(TwoFactorMethod), nullable=False)
    purpose = Column(String)  # 'login', 'enable_2fa', 'verify_phone', 'verify_email'

    # Controle
    attempts = Column(Integer, default=0)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used = Column(Boolean, default=False)
    used_at = Column(DateTime(timezone=True))

    # Segurança
    ip_address = Column(String)
    user_agent = Column(String)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    user = relationship("User", back_populates="otp_codes")


class LoginAttempt(Base):
    """Registro de tentativas de login com 2FA"""
    __tablename__ = "login_attempts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)

    # Dados da tentativa
    success = Column(Boolean, default=False)
    method = Column(SQLEnum(TwoFactorMethod))
    ip_address = Column(String)
    user_agent = Column(String)

    # Razão da falha
    failure_reason = Column(String)

    # Timestamp
    attempted_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    user = relationship("User", back_populates="login_attempts")
