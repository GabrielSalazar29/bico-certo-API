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
    OPEN = 2
    ACCEPTED = 3
    IN_PROGRESS = 4
    COMPLETED = 5
    APPROVED = 6
    CANCELLED = 7
    DISPUTED = 8
    REFUNDED = 9


class ProposalStatus(Enum):
    NONE = 0
    PENDING = 1
    ACCEPTED = 2
    REJECTED = 3
    CANCELED = 4

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
    openForProposals: bool
    total_proposals: int

    def to_dict(self) -> Dict[str, Any]:
        """Converte o Job para dicionário"""
        data = asdict(self)

        data['id'] = data['id'].hex() if isinstance(data['id'], bytes) else data['id']

        data['status'] = JobStatus(self.status).name

        data['max_budget'] = data['amount'] + data['platform_fee']

        data['created_at'] = datetime.fromtimestamp(
            self.created_at).isoformat() if self.created_at > 0 else None
        data['accepted_at'] = datetime.fromtimestamp(
            self.accepted_at).isoformat() if self.accepted_at > 0 else None
        data['completed_at'] = datetime.fromtimestamp(
            self.completed_at).isoformat() if self.completed_at > 0 else None
        data['deadline'] = datetime.fromtimestamp(self.deadline).isoformat() if self.deadline > 0 else None
        return data


@dataclass
class Reputation:
    """Represents a job in the BicoCerto system"""
    totalJobs: int
    successfulJobs: int
    totalEarned: int
    totalSpent: int
    reputationScore: int
    joinedAt: int

    def __init__(self, obj: tuple):
        self.totalJobs = obj[0]
        self.successfulJobs = obj[1]
        self.totalEarned = obj[2]
        self.totalSpent = obj[3]
        self.reputationScore = obj[4]
        self.joinedAt = obj[5]

    def to_dict(self) -> Dict[str, Any]:
        """Converte o Job para dicionário"""
        data = asdict(self)
        return data

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

        payment_wei = self.w3.to_wei(payment_eth, 'ether')
        deadline_timestamp = int(deadline.timestamp())

        function = self.contract.functions.createJob(
            provider_address,
            deadline_timestamp,
            category,
            ipfs_cid
        )

        return self.build_transaction(from_address, function, payment_wei)
    
    def prepare_create_open_job_transaction(
            self,
            from_address: str,
            ipfs_cid: str,
            category: str,
            deadline: datetime,
            max_budget_eth: float,
    ) -> Dict[str, Any]:
        """
        Prepara transação para criar um job em aberto
        """
        max_budget_wei = self.w3.to_wei(max_budget_eth, 'ether')
        deadline_timestamp = int(deadline.timestamp())

        function = self.contract.functions.createOpenJob(
            max_budget_wei,  # maxBudget
            deadline_timestamp,  # deadline
            category,  # serviceType
            ipfs_cid  # ipfsHash
        )

        return self.build_transaction(from_address, function, max_budget_wei)
    
    def prepare_submit_proposal_transaction(
            self,
            from_address: str,
            job_id: bytes,
            amount_eth: float,
            estimated_time: int,
            ipfs_cid: str,
    ) -> Dict[str, Any]:
        """
        Prepara transação para enviar uma proposta para um job especifico
        """
        amount_wei = self.w3.to_wei(amount_eth, 'ether')

        function = self.contract.functions.submitProposal(
            job_id,
            amount_wei,
            estimated_time,
            ipfs_cid
        )

        return self.build_transaction(from_address, function)

    def prepare_accept_proposal_transaction(
            self,
            from_address: str,
            proposal_id: bytes,
            amount_eth: float,
    ) -> Dict[str, Any]:
        """
        Prepara transação para aceitar uma proposta
        """
        amount_wei = self.w3.to_wei(amount_eth, 'ether')

        function = self.contract.functions.acceptProposal(
            proposal_id,
        )

        return self.build_transaction(from_address, function, amount_wei)

    def prepare_reject_proposal_transaction(
            self,
            from_address: str,
            proposal_id: bytes,
    ) -> Dict[str, Any]:
        """
        Prepara transação para rejeitar uma proposta
        """

        function = self.contract.functions.rejectProposal(
            proposal_id,
        )

        return self.build_transaction(from_address, function)

    def prepare_cancel_proposal_transaction(
            self,
            from_address: str,
            proposal_id: bytes,
    ) -> Dict[str, Any]:
        """
        Prepara transação para rejeitar uma proposta
        """

        function = self.contract.functions.withdrawProposal(
            proposal_id,
        )

        return self.build_transaction(from_address, function)

    def prepare_withdraw_transaction(
            self,
            from_address: str
    ) -> Dict[str, Any]:
        """
        Prepara transação para sacar o saldo para a carteira
        """
        function = self.contract.functions.withdraw()

        return self.build_transaction(from_address, function)

    def build_transaction(self, from_address: str, function, payment_wei: Optional[float] = None):

        nonce = self.w3.eth.get_transaction_count(from_address)

        # Prepara os parâmetros base da transação
        tx_params = {
            'from': from_address,
            'nonce': nonce,
            'gasPrice': 0,
            'chainId': self.w3.eth.chain_id
        }

        if payment_wei is not None:
            tx_params['value'] = payment_wei

        transaction = function.build_transaction(tx_params)

        return transaction

    def prepare_accept_job_transaction(
                self,
                from_address: str,
                job_id: bytes,
        ) -> Dict[str, Any]:
            """
            Prepara a transação para aceitar um job (sem enviar ETH).
            """
            function = self.contract.functions.acceptJob(job_id)
            return self.build_transaction(from_address, function)



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
        """Extrai o 'jobId' do evento 'JobCreated'."""
        return self._extract_event_data_from_receipt(
            tx_receipt,
            event_name="JobCreated",
            arg_key="jobId",
            return_key="jobId"
        )

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
        """Extrai o 'jobId' do evento 'JobOpenForProposals'."""
        return self._extract_event_data_from_receipt(
            tx_receipt,
            event_name="JobOpenForProposals",
            arg_key="jobId",
            return_key="jobId"
        )

    def get_proposal_from_receipt(self, tx_receipt) -> Optional[Dict[str, Any]]:
        """Extrai o 'proposalId' do evento 'ProposalSubmitted'."""
        return self._extract_event_data_from_receipt(
            tx_receipt,
            event_name="ProposalSubmitted",
            arg_key="proposalId",
            return_key="proposal_id"  # Note a diferença entre a chave do argumento e a de retorno
        )

    def _extract_event_data_from_receipt(self, tx_receipt, event_name: str, arg_key: str, return_key: str) -> Optional[
        Dict[str, Any]]:

        bicoCertoJobManager = get_instance("BicoCertoJobManager", self.registry.get_job_manager())

        try:
            event_handler = getattr(bicoCertoJobManager.events, event_name)

            processed_events = event_handler().process_receipt(tx_receipt)

            if processed_events:
                event = processed_events[0]
                return {
                    return_key: event['args'][arg_key]
                }

            return None

        except Exception as e:
            return None

    def get_job(self, job_id: bytes) -> Job:
        """Get job details through the main contract"""
        job_data = self.contract.functions.getJob(job_id).call()
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
            provider_rating=job_data[13],
            openForProposals=job_data[14],
            total_proposals=job_data[15]
        )
    
    def calculate_platform_fee(self, amount: int) -> int:
        """Calculate platform fee for a given amount"""
        return self.contract.functions.calculatePlatformFee(amount).call()
    
    def get_address(self) -> str:
        """Get the contract address"""
        return self.contract.address
