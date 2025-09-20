from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from ..config.database import Base
import uuid


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
   
    address: Mapped[str] = mapped_column(String, unique=True, nullable=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Security
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)

    two_factor_enabled = Column(Boolean, default=False)
    preferred_2fa_method = Column(String)  # 'email'
    require_2fa_setup = Column(Boolean, default=False)  # Forçar setup no próximo login

    # Security
    last_password_change = Column(DateTime(timezone=True))
    password_expires_at = Column(DateTime(timezone=True))

    # Relationships
    two_factor_settings = relationship("TwoFactorSettings", back_populates="user", uselist=False,
                                       cascade="all, delete-orphan")
    otp_codes = relationship("OTPCode", back_populates="user", cascade="all, delete-orphan")
    login_attempts = relationship("LoginAttempt", back_populates="user", cascade="all, delete-orphan")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    token = Column(String, unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    user = relationship("User", back_populates="refresh_tokens")


User.refresh_tokens = relationship("RefreshToken", back_populates="user")
User.password_reset_tokens = relationship("PasswordResetToken", back_populates="user", cascade="all, delete-orphan")
