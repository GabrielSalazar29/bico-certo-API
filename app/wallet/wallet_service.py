from sqlalchemy.orm import Session
from typing import Tuple, Optional, Dict, Any
from ..model.wallet import Wallet, WalletStatus, WalletType
from ..model.user import User
from .encryption import WalletEncryption
from .mnemonic_service import MnemonicService
from .key_manager import KeyManager
from ..config.settings import settings
from ..util.security import verify_password


class WalletService:
    """Serviço de wallet com criptografia consistente"""

    def __init__(self, db: Session):
        self.db = db
        self.encryption = WalletEncryption(settings.WALLET_ENCRYPTION_KEY)
        self.mnemonic_service = MnemonicService(settings.MNEMONIC_LANGUAGE)
        self.key_manager = KeyManager()

    def _normalize_password(self, password: str) -> str:
        """
        Normaliza a senha para garantir consistência
        IMPORTANTE: Sempre use este método antes de criptografar/descriptografar!
        """
        if not password:
            raise ValueError("Senha não pode ser vazia")

        normalized = password.strip()

        return normalized

    def create_or_replace_wallet(
            self,
            user_id: str,
            password: str,  # Senha em texto plano
            force_replace: bool = False
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Cria nova wallet com mnemonic
        """

        normalized_password = self._normalize_password(password)

        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return False, "Usuário não encontrado", None

        if not verify_password(password, user.password_hash):
            return False, "Senha incorreta", None

        existing_wallet = self.db.query(Wallet).filter(
            Wallet.user_id == user_id
        ).first()

        if existing_wallet and not force_replace:
            return False, "Você já possui uma carteira. Para substituí-la, confirme a ação.", {
                "has_wallet": True,
                "wallet_address": existing_wallet.address,
                "require_confirmation": True
            }

        if existing_wallet:
            self.db.delete(existing_wallet)
            self.db.flush()

        mnemonic_phrase = self.mnemonic_service.generate_mnemonic(
            strength=settings.MNEMONIC_STRENGTH
        )

        address, private_key = self.mnemonic_service.derive_account_from_mnemonic(
            mnemonic_phrase,
            account_index=0
        )

        encrypted_private_key = self.encryption.encrypt(
            private_key,
            user_id,
            normalized_password
        )

        encrypted_mnemonic = self.encryption.encrypt(
            mnemonic_phrase,
            user_id,
            normalized_password
        )

        wallet = Wallet(
            user_id=user_id,
            wallet_type=WalletType.GENERATED,
            address=address,
            encrypted_private_key=encrypted_private_key,
            encrypted_mnemonic=encrypted_mnemonic,
            status=WalletStatus.ACTIVE
        )

        self.db.add(wallet)
        self.db.commit()
        self.db.refresh(wallet)

        return True, "Carteira criada com sucesso", {
            "wallet_id": wallet.id,
            "address": address,
            "mnemonic": mnemonic_phrase,
            "warning": "⚠️ ATENÇÃO: Guarde estas palavras em local seguro!"
        }

    def import_from_private_key(
            self,
            user_id: str,
            private_key: str,
            password: str,
            force_replace: bool = False
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Importa wallet usando chave privada
        """

        normalized_password = self._normalize_password(password)

        # Verificar usuário
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return False, "Usuário não encontrado", None

        if not verify_password(password, user.password_hash):
            return False, "Senha incorreta", None

        # Verificar se já tem wallet
        existing_wallet = self.db.query(Wallet).filter(
            Wallet.user_id == user_id
        ).first()

        if existing_wallet and not force_replace:
            return False, "Você já possui uma carteira. Para substituí-la, confirme a ação.", {
                "has_wallet": True,
                "wallet_address": existing_wallet.address,
                "require_confirmation": True
            }

        address = self.key_manager.import_private_key(private_key)
        if not address:
            return False, "Chave privada inválida", None

        if existing_wallet:
            self.db.delete(existing_wallet)
            self.db.flush()

        encrypted_private_key = self.encryption.encrypt(
            private_key,
            user_id,
            normalized_password
        )

        wallet = Wallet(
            user_id=user_id,
            wallet_type=WalletType.IMPORTED_KEY,
            address=address,
            encrypted_private_key=encrypted_private_key,
            encrypted_mnemonic=None,
            status=WalletStatus.ACTIVE
        )

        self.db.add(wallet)
        self.db.commit()
        self.db.refresh(wallet)

        return True, "Carteira importada com sucesso", {
            "wallet_id": wallet.id,
            "address": address
        }

    def import_from_mnemonic(
            self,
            user_id: str,
            mnemonic_phrase: str,
            password: str,
            account_index: int = 0,
            force_replace: bool = False
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Importa wallet usando mnemonic phrase
        """
        normalized_password = self._normalize_password(password)

        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return False, "Usuário não encontrado", None

        if not verify_password(password, user.password_hash):
            return False, "Senha incorreta", None

        existing_wallet = self.db.query(Wallet).filter(
            Wallet.user_id == user_id
        ).first()

        if existing_wallet and not force_replace:
            return False, "Você já possui uma carteira. Para substituí-la, confirme a ação.", {
                "has_wallet": True,
                "wallet_address": existing_wallet.address,
                "require_confirmation": True
            }

        if not self.mnemonic_service.validate_mnemonic(mnemonic_phrase):
            return False, "Mnemonic inválido", None

        try:
            address, private_key = self.mnemonic_service.derive_account_from_mnemonic(
                mnemonic_phrase,
                account_index=account_index
            )
        except Exception as e:
            return False, f"Erro ao derivar conta: {str(e)}", None

        if existing_wallet:
            self.db.delete(existing_wallet)
            self.db.flush()

        encrypted_private_key = self.encryption.encrypt(
            private_key,
            user_id,
            normalized_password
        )

        encrypted_mnemonic = self.encryption.encrypt(
            mnemonic_phrase,
            user_id,
            normalized_password
        )

        wallet = Wallet(
            user_id=user_id,
            wallet_type=WalletType.IMPORTED_MNEMONIC,
            address=address,
            encrypted_private_key=encrypted_private_key,
            encrypted_mnemonic=encrypted_mnemonic,
            status=WalletStatus.ACTIVE
        )

        self.db.add(wallet)
        self.db.commit()
        self.db.refresh(wallet)

        return True, "Carteira importada com sucesso", {
            "wallet_id": wallet.id,
            "address": address
        }

    def get_private_key(
            self,
            user_id: str,
            password: str  # Senha em texto plano
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Recupera a chave privada para transações
        """
        from ..util.security import verify_password

        normalized_password = self._normalize_password(password)

        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return False, "Usuário não encontrado", None

        if not verify_password(password, user.password_hash):
            return False, "Senha incorreta", None

        wallet = self.db.query(Wallet).filter(
            Wallet.user_id == user_id
        ).first()

        if not wallet:
            return False, "Você não possui uma carteira", None

        if wallet.status != WalletStatus.ACTIVE:
            return False, f"Carteira está {wallet.status.value}", None

        try:

            private_key = self.encryption.decrypt(
                wallet.encrypted_private_key,
                user_id,
                normalized_password
            )

            return True, "Chave recuperada com sucesso", private_key

        except Exception as e:
            return False, f"Erro ao descriptografar: {str(e)}", None

    def get_wallet(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Retorna a carteira do usuário (informações públicas)
        """
        wallet = self.db.query(Wallet).filter(
            Wallet.user_id == user_id
        ).first()

        if not wallet:
            return None

        return {
            "id": wallet.id,
            "address": wallet.address,
            "type": wallet.wallet_type.value,
            "status": wallet.status.value,
            "balance": wallet.eth_balance,
            "backup_confirmed": wallet.backup_confirmed,
            "created_at": wallet.created_at.isoformat() if wallet.created_at else None,
            "has_mnemonic": wallet.encrypted_mnemonic is not None,
        }

    def delete_wallet(
            self,
            user_id: str,
            password: str
    ) -> Tuple[bool, str]:
        """
        Deleta a carteira do usuário (requer senha)
        """
        from ..util.security import verify_password

        wallet = self.db.query(Wallet).filter(
            Wallet.user_id == user_id
        ).first()

        if not wallet:
            return False, "Você não possui uma carteira"

        user = self.db.query(User).filter(User.id == user_id).first()
        if not verify_password(password, user.password_hash):
            return False, "Senha incorreta"

        self.db.delete(wallet)
        self.db.commit()

        return True, "Carteira deletada com sucesso"
