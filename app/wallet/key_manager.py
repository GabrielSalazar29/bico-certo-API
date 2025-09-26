from eth_account import Account
from web3 import Web3
from typing import Optional


class KeyManager:
    """Gerenciamento de chaves privadas Ethereum"""

    def __init__(self):
        self.w3 = Web3()
        Account.enable_unaudited_hdwallet_features()

    def import_private_key(self, private_key: str) -> Optional[str]:
        """
        Importa chave privada e retorna endereço
        """
        try:
            # Validar formato
            if not private_key.startswith('0x'):
                private_key = f'0x{private_key}'

            # Verificar se tem 64 caracteres hex (32 bytes)
            if len(private_key) != 66:  # 0x + 64 chars
                return None

            account = Account.from_key(private_key)

            return account.address

        except Exception:
            return None
