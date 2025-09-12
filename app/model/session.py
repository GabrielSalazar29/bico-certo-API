# app/models/session.py
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from ..config.database import Base
import uuid
from sqlalchemy.sql import func
from .user import User
from .device import Device


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    device_id = Column(String, ForeignKey("devices.id"), nullable=True)

    # Token info
    access_token_jti = Column(String, unique=True, nullable=False)  # JWT ID
    refresh_token = Column(String, unique=True, nullable=False)

    # Session data
    ip_address = Column(String)
    user_agent = Column(String)
    location = Column(JSON)  # GeoIP data

    # Status
    is_active = Column(Boolean, default=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_activity = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="sessions")
    device = relationship("Device", back_populates="sessions")


# Adicionar relationships
User.sessions = relationship("Session", back_populates="user")
Device.sessions = relationship("Session", back_populates="device")