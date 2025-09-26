from mnemonic import Mnemonic
from eth_account import Account
from typing import Tuple
import secrets


class MnemonicService:
    """Gerenciamento de mnemonic phrases usando apenas eth-account"""

    def __init__(self, language: str = "english"):
        self.mnemo = Mnemonic(language)
        self.language = language

        Account.enable_unaudited_hdwallet_features()

    def generate_mnemonic(self, strength: int = 128) -> str:
        """
        Gera mnemonic phrase
        strength: 128 (12 palavras), 256 (24 palavras)
        """
        entropy = secrets.token_bytes(strength // 8)
        mnemonic_phrase = self.mnemo.to_mnemonic(entropy)

        return mnemonic_phrase

    def validate_mnemonic(self, mnemonic_phrase: str) -> bool:
        """
        Valida se o mnemonic é válido
        """
        try:
            Account.from_mnemonic(mnemonic_phrase)
            return True
        except Exception:
            return False

    def derive_account_from_mnemonic(
            self,
            mnemonic_phrase: str,
            account_index: int = 0,
            passphrase: str = ""
    ) -> Tuple[str, str]:
        """
        Deriva conta Ethereum de mnemonic
        Retorna: (address, private_key)
        """
        # Path BIP44 para Ethereum: m/44'/60'/0'/0/index
        derivation_path = f"m/44'/60'/0'/0/{account_index}"

        # Criar account a partir do mnemonic
        account = Account.from_mnemonic(
            mnemonic=mnemonic_phrase,
            passphrase=passphrase,
            account_path=derivation_path
        )

        return account.address, account.key.hex()