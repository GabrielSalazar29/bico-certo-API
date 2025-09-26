from cryptography.fernet import Fernet, InvalidToken
import hashlib
import base64


class WalletEncryption:
    """Criptografia com Fernet e debug melhorado"""

    def __init__(self, master_key: str):

        if not master_key:
            raise ValueError("Master key não pode ser vazia")

        self.master_key = master_key.strip()

    def _generate_fernet_key(self, user_id: str, password: str) -> bytes:
        """
        Gera uma chave Fernet determinística
        """

        # Criar string única e consistente
        combined = f"{self.master_key}|{user_id}|{password}"

        # Hash para criar chave de 32 bytes
        key_hash = hashlib.sha256(combined.encode('utf-8')).digest()

        # Fernet precisa de uma chave base64 de 32 bytes
        fernet_key = base64.urlsafe_b64encode(key_hash)

        return fernet_key

    def encrypt(self, plaintext: str, user_id: str, password: str) -> str:
        """
        Criptografa dados usando Fernet
        """
        try:

            fernet_key = self._generate_fernet_key(user_id, password)
            f = Fernet(fernet_key)

            encrypted_bytes = f.encrypt(plaintext.encode('utf-8'))
            encrypted_str = encrypted_bytes.decode('utf-8')

            return encrypted_str

        except Exception as e:
            raise Exception(f"Erro ao criptografar: {str(e)}")

    def decrypt(self, encrypted_data: str, user_id: str, password: str) -> str:
        """
        Descriptografa dados usando Fernet
        """
        try:

            fernet_key = self._generate_fernet_key(user_id, password)
            f = Fernet(fernet_key)

            encrypted_bytes = encrypted_data.encode('utf-8')
            decrypted_bytes = f.decrypt(encrypted_bytes)
            decrypted_str = decrypted_bytes.decode('utf-8')

            return decrypted_str

        except InvalidToken:
            raise Exception("Senha incorreta ou dados corrompidos")
        except Exception as e:
            raise Exception(f"Erro ao descriptografar: {str(e)}")
