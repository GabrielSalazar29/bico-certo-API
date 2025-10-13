# app/model/chat_model.py
from sqlalchemy import Column, String, Text, DateTime, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..config.database import Base
import uuid
import enum


class MessageStatus(enum.Enum):
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"


class ChatRoom(Base):
    """Sala de chat vinculada a um job"""
    __tablename__ = "chat_rooms"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, nullable=False, index=True)  # ID do job na blockchain

    # Participantes
    client_id = Column(String, ForeignKey("users.id"), nullable=False)
    provider_id = Column(String, ForeignKey("users.id"), nullable=True)  # Pode ser null para jobs abertos

    # Status
    is_active = Column(Boolean, default=True)
    last_message_at = Column(DateTime(timezone=True))

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Contadores para otimização
    total_messages = Column(String, default="0")
    unread_client = Column(String, default="0")  # Mensagens não lidas pelo cliente
    unread_provider = Column(String, default="0")  # Mensagens não lidas pelo provider

    # Relationships
    client = relationship("User", foreign_keys=[client_id], backref="client_chats")
    provider = relationship("User", foreign_keys=[provider_id], backref="provider_chats")
    messages = relationship("ChatMessage", back_populates="room", cascade="all, delete-orphan")


class ChatMessage(Base):
    """Mensagens do chat"""
    __tablename__ = "chat_messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    room_id = Column(String, ForeignKey("chat_rooms.id"), nullable=False, index=True)
    sender_id = Column(String, ForeignKey("users.id"), nullable=False)

    # Conteúdo
    message = Column(Text, nullable=False)
    message_type = Column(String, default="text")  # text, image, file, proposal_update

    # Metadata para tipos especiais
    json_metadata = Column(Text)  # JSON para dados adicionais (ex: proposta aceita, valor alterado)

    # Status
    status = Column(SQLEnum(MessageStatus), default=MessageStatus.SENT)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    delivered_at = Column(DateTime(timezone=True))
    read_at = Column(DateTime(timezone=True))

    # Relationships
    room = relationship("ChatRoom", back_populates="messages")
    sender = relationship("User", backref="sent_messages")

    # Para respostas
    reply_to_id = Column(String, ForeignKey("chat_messages.id"), nullable=True)
    reply_to = relationship("ChatMessage", remote_side=[id])


class ChatNotification(Base):
    """Notificações de chat"""
    __tablename__ = "chat_notifications"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    room_id = Column(String, ForeignKey("chat_rooms.id"), nullable=False)
    message_id = Column(String, ForeignKey("chat_messages.id"), nullable=False)

    # Status
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime(timezone=True))

    # Push notification
    push_sent = Column(Boolean, default=False)
    push_sent_at = Column(DateTime(timezone=True))

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", backref="chat_notifications")