from web3 import Web3
from typing import Dict, Any
from ..config.settings import settings


class BlockchainService:
    """Serviço otimizado para rede privada"""

    def __init__(self, provider_url: str = None):
        if provider_url:
            self.w3 = Web3(Web3.HTTPProvider(provider_url))
        else:
            self.w3 = Web3(Web3.HTTPProvider('http://127.0.0.1:8545'))

        self.is_private = settings.NETWORK_TYPE == "private"
        self.zero_gas = settings.ZERO_GAS_COST if hasattr(settings, 'ZERO_GAS_COST') else True

    def get_wallet_transactions(
            self,
            address: str,
            start_block: int = 0,
            end_block: str = 'latest'
    ) -> Dict[str, Any]:
        """
        Busca transações (otimizado para rede privada)
        """
        return self._get_private_network_transactions(address, start_block, end_block)

    def _get_private_network_transactions(
            self,
            address: str,
            start_block: int,
            end_block: str
    ) -> Dict[str, Any]:
        """
        Busca otimizada para rede privada
        """
        transactions = []
        address = Web3.to_checksum_address(address)

        if end_block == 'latest':
            end_block = self.w3.eth.block_number

        for block_num in range(max(start_block, end_block - 1000), end_block + 1):
            try:
                block = self.w3.eth.get_block(block_num, full_transactions=True)

                for tx in block.transactions:
                    if tx['from'] == address or tx['to'] == address:
                        receipt = self.w3.eth.get_transaction_receipt(tx['hash'])

                        transactions.append({
                            "hash": tx['hash'].hex(),
                            "from": tx['from'],
                            "to": tx['to'],
                            "value": self.w3.from_wei(tx['value'], 'ether'),
                            "gas": tx['gas'],
                            "gasPrice": 0 if self.zero_gas else self.w3.from_wei(tx['gasPrice'], 'gwei'),
                            "gasUsed": receipt['gasUsed'],
                            "gasCost": 0 if self.zero_gas else self.w3.from_wei(receipt['gasUsed'] * tx['gasPrice'],
                                                                                'ether'),
                            "blockNumber": tx['blockNumber'],
                            "timestamp": block['timestamp'],
                            "status": "success" if receipt['status'] == 1 else "failed",
                            "type": "send" if tx['from'] == address else "receive",
                            "confirmations": end_block - tx['blockNumber']
                        })
            except Exception:
                continue

        transactions.sort(key=lambda x: x['timestamp'], reverse=True)

        return {
            "transactions": transactions,
            "total": len(transactions),
            "address": address,
            "network": "private",
            "gas_cost": "FREE" if self.zero_gas else "PAID"
        }
