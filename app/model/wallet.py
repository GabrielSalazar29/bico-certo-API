from sqlalchemy import Column, String, Boolean, DateTime, Text, Float, JSON, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..config.database import Base
import uuid
import enum


class WalletStatus(enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class WalletType(enum.Enum):
    GENERATED = "generated"  # Criada pelo sistema
    IMPORTED_KEY = "imported_key"  # Importada via private key
    IMPORTED_MNEMONIC = "imported_mnemonic"  # Importada via mnemonic


class Wallet(Base):
    """Carteira do usuário - Uma por usuário"""
    __tablename__ = "wallets"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), unique=True, nullable=False)

    # Identificação
    wallet_type = Column(SQLEnum(WalletType), nullable=False)

    # Endereço público (Ethereum)
    address = Column(String, unique=True, nullable=False, index=True)

    # Chave privada criptografada (AES-256 com senha do usuário)
    encrypted_private_key = Column(Text, nullable=False)

    # Mnemonic criptografado (se aplicável)
    encrypted_mnemonic = Column(Text)

    # Backup
    backup_confirmed = Column(Boolean, default=False)
    backup_date = Column(DateTime(timezone=True))

    # Status
    status = Column(SQLEnum(WalletStatus), default=WalletStatus.ACTIVE)

    # Balances (cache)
    eth_balance = Column(Float, default=0.0)
    token_balances = Column(JSON)
    last_balance_update = Column(DateTime(timezone=True))

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="wallet", uselist=False)
