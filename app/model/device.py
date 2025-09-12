from sqlalchemy import Column, String, Boolean, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .user import User
from ..config.database import Base
import uuid


class Device(Base):
    __tablename__ = "devices"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    device_id = Column(String, nullable=False, index=True)

    # Device Info
    platform = Column(String)  # android, ios, web
    model = Column(String)
    os_version = Column(String)
    app_version = Column(String)

    # Fingerprint
    fingerprint = Column(String, unique=True)

    # Security
    trusted = Column(Boolean, default=False)
    last_ip = Column(String)
    last_location = Column(JSON)  # {"country": "BR", "city": "São Paulo"}

    # Timestamps
    first_seen = Column(DateTime(timezone=True), server_default=func.now())
    last_seen = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationship
    user = relationship("User", back_populates="devices")


# Adicionar no User model
User.devices = relationship("Device", back_populates="user")
