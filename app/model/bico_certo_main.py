from app.config.settings import settings
from app.util.w3_util import *
from app.model.bico_certo_registry import BicoCertoRegistry
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Dict, Any, Optional
from datetime import datetime


# Enums
class JobStatus(Enum):
    NONE = 0
    CREATED = 1
    ACCEPTED = 2
    IN_PROGRESS = 3
    COMPLETED = 4
    APPROVED = 5
    CANCELLED = 6
    DISPUTED = 7
    REFUNDED = 8


# Data Classes
@dataclass
class Job:
    """Represents a job in the BicoCerto system"""
    id: bytes
    client: str
    provider: str
    amount: int
    platform_fee: int
    created_at: int
    accepted_at: int
    completed_at: int
    deadline: int
    status: JobStatus
    service_type: str
    ipfs_hash: str
    client_rating: int
    provider_rating: int

    def to_dict(self) -> Dict[str, Any]:
        """Converte o Job para dicionário"""
        data = asdict(self)
        # Converte bytes para hex string
        data['id'] = data['id'].hex() if isinstance(data['id'], bytes) else data['id']
        # Converte enum para valor
        data['status'] = self.status.value if isinstance(self.status, JobStatus) else self.status
        # Converte timestamps para formato legível (opcional)
        data['created_at_formatted'] = datetime.fromtimestamp(
            self.created_at).isoformat() if self.created_at > 0 else None
        data['accepted_at_formatted'] = datetime.fromtimestamp(
            self.accepted_at).isoformat() if self.accepted_at > 0 else None
        data['completed_at_formatted'] = datetime.fromtimestamp(
            self.completed_at).isoformat() if self.completed_at > 0 else None
        data['deadline_formatted'] = datetime.fromtimestamp(self.deadline).isoformat() if self.deadline > 0 else None
        return data

    def to_json(self) -> str:
        """Converte o Job para JSON string"""
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class User:
    """Represents a user profile with reputation"""
    address: str
    reputation_score: int
    total_jobs_as_client: int
    total_jobs_as_provider: int
    total_volume: int
    is_registered: bool


@dataclass
class Dispute:
    """Represents a dispute in the system"""
    job_id: bytes
    initiator: str
    reason: str
    created_at: int
    resolved: bool
    resolver: str
    resolution: str


class BicoCerto:
    """Main interface for the BicoCerto contract"""
    
    def __init__(
        self,
        deploy: bool = False,
        registry_address: str = "",
    ):
        self.w3 = w3
        if deploy:
            self.contract = deploy_contract("BicoCerto", registry_address)
            self.registry = BicoCertoRegistry(contract_address=registry_address)
            return
        contract_addresses = load_contracts_addresses()
        self.contract = get_instance("BicoCerto", contract_addresses["BicoCerto"])
        self.registry = self.registry = BicoCertoRegistry(contract_address=contract_addresses["BicoCertoRegistry"])

    def prepare_create_job_transaction(
            self,
            from_address: str,
            provider_address: str,
            ipfs_cid: str,
            category: str,
            deadline: datetime,
            payment_eth: float,
    ) -> Dict[str, Any]:
        """
        Prepara transação para criar um job
        """

        deadline_timestamp = int(deadline.timestamp())

        function = self.contract.functions.createJob(
            provider_address,
            deadline_timestamp,
            category,
            ipfs_cid
        )

        return self.payment_build_transaction(from_address, payment_eth, function)
    
    def prepare_create_open_job_transaction(
            self,
            from_address: str,
            ipfs_cid: str,
            category: str,
            deadline: datetime,
            max_budget_eth: int,
    ) -> Dict[str, Any]:
        """
        Prepara transação para criar um job em aberto
        """

        deadline_timestamp = int(deadline.timestamp())

        function = self.contract.functions.createOpenJob(
            max_budget_eth,  # maxBudget
            deadline_timestamp,  # deadline
            category,  # serviceType
            ipfs_cid  # ipfsHash
        )

        return self.payment_build_transaction(from_address, max_budget_eth, function)

    def payment_build_transaction(self, from_address: str, payment_eth: float, function):
        payment_wei = self.w3.to_wei(payment_eth, 'ether')

        try:
            gas_estimate = function.estimate_gas({
                'from': from_address,
                'value': payment_wei
            })
            gas_limit = int(gas_estimate * 1.2)  # 20% de margem
        except Exception as e:
            gas_limit = 300000  # Valor padrão alto para contratos

        nonce = self.w3.eth.get_transaction_count(from_address)

        transaction = function.build_transaction({
            'from': from_address,
            'value': payment_wei,
            'gas': gas_limit,
            'gasPrice': 0,
            'nonce': nonce,
            'chainId': self.w3.eth.chain_id
        })

        return transaction
    
    def build_transaction(self, from_address: str, function):
        """
        Constrói uma transação genérica sem envio de valor (ETH).
        """
        try:
            gas_estimate = function.estimate_gas({'from': from_address})
            gas_limit = int(gas_estimate * 1.2)
        except Exception as e:
            gas_limit = 200000

        nonce = self.w3.eth.get_transaction_count(from_address)

        transaction = function.build_transaction({
            'from': from_address,
            'gas': gas_limit,
            'gasPrice': 0,
            'nonce': nonce,
            'chainId': self.w3.eth.chain_id
        })

        return transaction

    def prepare_accept_job_transaction(
                self,
                from_address: str,
                job_id: str,
        ) -> Dict[str, Any]:
            """
            Prepara a transação para aceitar um job (sem enviar ETH).
            """
            job_id_bytes = bytes.fromhex(job_id.replace("0x", ""))

            function = self.contract.functions.acceptJob(job_id_bytes)

            try:
                gas_estimate = function.estimate_gas({'from': from_address})
                gas_limit = int(gas_estimate * 1.2)
            except Exception:
                gas_limit = 150000  

            nonce = self.w3.eth.get_transaction_count(from_address)

            transaction = function.build_transaction({
                'from': from_address,
                'gas': gas_limit,
                'gasPrice': 0,  
                'nonce': nonce,
                'chainId': self.w3.eth.chain_id
            })

            return transaction


    def prepare_complete_job_transaction(
            self,
            from_address: str,
            job_id: bytes,
    ) -> Dict[str, Any]:
        """Prepara a transação para marcar um job como concluído."""
        function = self.contract.functions.completeJob(job_id)
        return self.build_transaction(from_address, function)

    def prepare_approve_job_transaction(
            self,
            from_address: str,
            job_id: bytes,
            rating: int,
    ) -> Dict[str, Any]:
        """Prepara a transação para aprovar um job e liberar o pagamento."""
        function = self.contract.functions.approveJob(job_id, rating)
        return self.build_transaction(from_address, function)

    def prepare_cancel_job_transaction(
            self,
            from_address: str,
            job_id: bytes,
    ) -> Dict[str, Any]:
        """Prepara a transação para cancelar um job."""
        function = self.contract.functions.cancelJob(job_id)
        return self.build_transaction(from_address, function)
    
    def get_job_from_receipt(self, tx_receipt) -> Optional[Dict[str, Any]]:
        """
        Extrai informações do job criado a partir do receipt
        """

        bicoCertoJobManager = get_instance("BicoCertoJobManager", self.registry.get_job_manager())

        try:
            # Processar logs do evento JobCreated
            job_created_events = bicoCertoJobManager.events.JobCreated().process_receipt(tx_receipt)

            if job_created_events:
                event = job_created_events[0]
                return {
                    'jobId': event['args']['jobId']
                }

            return None

        except Exception as e:
            return None

    def get_job_accepted_from_receipt(self, tx_receipt) -> Optional[Dict[str, Any]]:
        """
        Extrai informações do evento JobAccepted a partir do recibo da transação.
        """
        # Instancia o contrato JobManager para acessar seus eventos
        bicoCertoJobManager = get_instance("BicoCertoJobManager", self.registry.get_job_manager())

        try:
            # Processa os logs do evento JobAccepted
            job_accepted_events = bicoCertoJobManager.events.JobAccepted().process_receipt(tx_receipt)
            if job_accepted_events:
                event = job_accepted_events[0]
                return {
                    'jobId': event['args']['jobId'].hex(),
                    'provider': event['args']['provider'],
                    'acceptedAt': datetime.fromtimestamp(event['args']['timestamp']).isoformat()
                }
            return None
        except Exception:
            return None

    def get_job_open_from_receipt(self, tx_receipt) -> Optional[Dict[str, Any]]:
        """
        Extrai informações do job criado a partir do receipt
        """

        bicoCertoJobManager = get_instance("BicoCertoJobManager", self.registry.get_job_manager())

        try:
            # Processar logs do evento JobCreated
            job_created_events = bicoCertoJobManager.events.JobOpenForProposals().process_receipt(tx_receipt)

            if job_created_events:
                event = job_created_events[0]
                return {
                    'jobId': event['args']['jobId']
                }

            return None

        except Exception as e:
            return None
    
    def accept_job(self, job_id: bytes, gas_limit: int = 150000) -> str:
        """Accept a job through the main contract"""
        if not self.account:
            raise ValueError("Account required for transactions")
        
        tx = self.contract.functions.acceptJob(job_id).build_transaction({
            'from': self.account.address,
            'gas': gas_limit,
            'gasPrice': self.w3.eth.gas_price,
            'nonce': self.w3.eth.get_transaction_count(self.account.address)
        })
        
        signed_tx = self.w3.eth.account.sign_transaction(tx, self.account.key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        return tx_hash.hex()
    
    def complete_job(self, job_id: bytes, gas_limit: int = 150000) -> str:
        """Complete a job through the main contract"""
        if not self.account:
            raise ValueError("Account required for transactions")
        
        tx = self.contract.functions.completeJob(job_id).build_transaction({
            'from': self.account.address,
            'gas': gas_limit,
            'gasPrice': self.w3.eth.gas_price,
            'nonce': self.w3.eth.get_transaction_count(self.account.address)
        })
        
        signed_tx = self.w3.eth.account.sign_transaction(tx, self.account.key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        return tx_hash.hex()
    
    def approve_job(self, job_id: bytes, rating: int, gas_limit: int = 200000) -> str:
        """Approve a job and release payment through the main contract"""
        if not self.account:
            raise ValueError("Account required for transactions")
        
        if rating < 0 or rating > 5:
            raise ValueError("Rating must be between 0 and 5")
        
        tx = self.contract.functions.approveJob(job_id, rating).build_transaction({
            'from': self.account.address,
            'gas': gas_limit,
            'gasPrice': self.w3.eth.gas_price,
            'nonce': self.w3.eth.get_transaction_count(self.account.address)
        })
        
        signed_tx = self.w3.eth.account.sign_transaction(tx, self.account.key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        return tx_hash.hex()
    
    def withdraw(self, gas_limit: int = 100000) -> str:
        """Withdraw pending funds through the main contract"""
        if not self.account:
            raise ValueError("Account required for transactions")
        
        tx = self.contract.functions.withdraw().build_transaction({
            'from': self.account.address,
            'gas': gas_limit,
            'gasPrice': self.w3.eth.gas_price,
            'nonce': self.w3.eth.get_transaction_count(self.account.address)
        })
        
        signed_tx = self.w3.eth.account.sign_transaction(tx, self.account.key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        return tx_hash.hex()
    
    def get_job(self, job_id: str) -> Job:
        """Get job details through the main contract"""
        job_data = self.contract.functions.getJob(bytes.fromhex(job_id)).call()
        return Job(
            id=job_data[0],
            client=job_data[1],
            provider=job_data[2],
            amount=w3.from_wei(job_data[3], 'ether'),
            platform_fee=w3.from_wei(job_data[4], 'ether'),
            created_at=job_data[5],
            accepted_at=job_data[6],
            completed_at=job_data[7],
            deadline=job_data[8],
            status=JobStatus(job_data[9]),
            service_type=job_data[10],
            ipfs_hash=job_data[11],
            client_rating=job_data[12],
            provider_rating=job_data[13]
        )
    
    def calculate_platform_fee(self, amount: int) -> int:
        """Calculate platform fee for a given amount"""
        return self.contract.functions.calculatePlatformFee(amount).call()
    
    def get_address(self) -> str:
        """Get the contract address"""
        return self.contract.address
