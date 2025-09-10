from utils.w3_utils import *
from model.bico_certo_registry import BicoCertoRegistry
from dataclasses import dataclass
from enum import Enum


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

    def create_job(
        self,
        provider: str,
        deadline: int,
        service_type: str,
        ipfs_hash: str,
        value: int,
        from_address: str
    ) -> bytes:
        """Create a new job through the main contract"""
        
        tx = self.contract.functions.createJob(
            provider,
            deadline,
            service_type,
            ipfs_hash
        ).transact({
            'from': from_address,
            'value': self.w3.to_wei(value, 'ether')
        })

        receipt = w3.eth.wait_for_transaction_receipt(tx)
        # signed_tx = self.w3.eth.account.sign_transaction(tx, self.account.key)
        # tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)

        bicoCertoJobManager = get_instance("BicoCertoJobManager", self.registry.get_job_manager())

        try:
            logs = bicoCertoJobManager.events.JobCreated().process_receipt(receipt)

            if logs:
                job_id_bytes = logs[0]['args']['jobId']

        except Exception as e:
            print(f"\n❌ Ocorreu um erro ao processar os eventos: {e}")

        return job_id_bytes
    
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
    
    def get_job(self, job_id: bytes) -> Job:
        """Get job details through the main contract"""
        job_data = self.contract.functions.getJob(job_id).call()
        return Job(
            id=job_data[0],
            client=job_data[1],
            provider=job_data[2],
            amount=job_data[3],
            platform_fee=job_data[4],
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
