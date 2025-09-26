from web3 import Web3
from eth_account import Account
from typing import Dict, Any, Optional, Tuple
from ..config.settings import settings


class TransactionSigner:
    """Assinatura e envio de transações com gas adequado"""

    def __init__(self, web3_provider_url: str = None):
        if web3_provider_url:
            self.w3 = Web3(Web3.HTTPProvider(web3_provider_url))
        else:
            # Default para rede local
            self.w3 = Web3(Web3.HTTPProvider('http://127.0.0.1:8545'))

        # Configuração para rede privada
        self.is_private_network = settings.NETWORK_TYPE == "private"
        self.zero_gas = settings.ZERO_GAS_COST if hasattr(settings, 'ZERO_GAS_COST') else True

    def prepare_transaction(
            self,
            from_address: str,
            to_address: str,
            value_eth: float,
            gas_limit: Optional[int] = None,
            data: str = "0x",
            nonce: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Prepara transação com gas adequado
        """

        value_wei = self.w3.to_wei(value_eth, 'ether')

        if gas_limit is None:
            if self.is_private_network:
                gas_limit = 100000

        if nonce is None:
            nonce = self.w3.eth.get_transaction_count(from_address)

        # Montar transação
        transaction = {
            'from': from_address,
            'to': to_address,
            'value': value_wei,
            'gas': gas_limit,
            'gasPrice': 0,
            'nonce': nonce,
            'data': data,
            'chainId': self.w3.eth.chain_id
        }

        return transaction

    def sign_and_send_transaction(
            self,
            from_address: str,
            to_address: str,
            value_eth: float,
            private_key: str,
            data: str = "0x"
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Prepara, assina e envia transação
        """

        try:

            transaction = self.prepare_transaction(
                from_address=from_address,
                to_address=to_address,
                value_eth=value_eth,
                data=data
            )

            account = Account.from_key(private_key)
            signed_tx = account.sign_transaction(transaction)

            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            tx_hash_hex = tx_hash.hex()

            return True, "Transação enviada com sucesso", tx_hash_hex

        except ValueError as e:
            # Erro específico do Web3/Ganache
            error_msg = str(e)

            if "intrinsic gas too low" in error_msg:
                return False, "Gas limit muito baixo. Tente aumentar o gas limit.", None
            elif "insufficient funds" in error_msg:
                return False, "Saldo insuficiente para a transação", None
            else:
                return False, f"Erro: {error_msg}", None

        except Exception as e:
            return False, f"Erro: {str(e)}", None

    def get_balance(self, address: str) -> float:
        """
        Retorna saldo em ETH
        """
        balance_wei = self.w3.eth.get_balance(address)
        balance_eth = self.w3.from_wei(balance_wei, 'ether')
        return balance_eth
