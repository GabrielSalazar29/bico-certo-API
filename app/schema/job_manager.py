from typing import Optional

from pydantic import BaseModel, Field


class CreateJobRequest(BaseModel):
    """Request para criar um job"""

    # Dados do job
    provider_address: str = "0x9Eededda12AB8124f349c58A4109F84D4B564788"
    title: str = Field(..., min_length=3, max_length=100)
    description: str = Field(..., min_length=10, max_length=1000)
    category: str = Field(..., min_length=3, max_length=50)
    location: str = Field(..., min_length=3, max_length=100)
    deadline: str = Field(..., description="ISO format datetime")
    payment_eth: float = Field(..., gt=0, description="Pagamento")

    # Autenticação
    password: str = Field(..., description="Senha do usuário para assinar transação")


class CreateOpenJobRequest(BaseModel):
    """Request para criar job aberto para propostas"""
    title: str = Field(..., min_length=3, max_length=100)
    description: str = Field(..., min_length=10, max_length=2000)
    category: str = Field(..., min_length=3, max_length=50)
    location: str = Field(..., min_length=3, max_length=100)
    max_budget_eth: float = Field(..., gt=0, description="Orçamento máximo em ETH")
    deadline: str = Field(..., description="Formato DD-MM-YYYY")
    password: str = Field(..., description="Senha do usuário")

class AcceptJobRequest(BaseModel):
    """Request para aceitar um job."""
    job_id: str = Field(..., description="O ID do job a ser aceito (formato hexadecimal)")
    password: str = Field(..., description="Senha do usuário para assinar a transação")

class SubmitProposalRequest(BaseModel):
    """Request para submeter proposta"""
    job_id: str = Field(..., description="ID do job (hex)")
    amount_eth: float = Field(..., gt=0, description="Valor da proposta em ETH")
    description: str = Field(..., min_length=10, max_length=1000)
    estimated_time_days: int = Field(..., gt=0, description="Tempo estimado em dias")
    password: str = Field(..., description="Senha do usuário")


class AnswerProposalRequest(BaseModel):
    """Request para aceitar proposta"""
    proposal_id: str = Field(..., description="ID da proposta (hex)")
    password: str = Field(..., description="Senha do usuário")

class CompleteJobRequest(BaseModel):
    """Request para marcar um job como concluído."""
    job_id: str = Field(..., description="O ID do job a ser concluído (hex)")
    password: str = Field(..., description="Senha do usuário para assinar a transação")


class ApproveJobRequest(BaseModel):
    """Request para aprovar um job concluído e liberar o pagamento."""
    job_id: str = Field(..., description="O ID do job a ser aprovado (hex)")
    rating: int = Field(..., ge=1, le=5, description="Nota de avaliação para o prestador (1 a 5)")
    password: str = Field(..., description="Senha do usuário para assinar a transação")

class CancelJobRequest(BaseModel):
    """Request para cancelar um job que ainda não foi aceito."""
    job_id: str = Field(..., description="O ID do job a ser cancelado (hex)")
    password: str = Field(..., description="Senha do usuário para assinar a transação")

class AnswerProposalRequest(BaseModel):
    """Request para aceitar proposta"""
    proposal_id: str = Field(..., description="ID da proposta (hex)")
    password: str = Field(..., description="Senha do usuário")
    
class ProposalResponse(BaseModel):
    """Response com dados da proposta"""
    proposal_id: str
    job_id: str
    provider: str
    amount: float
    description: str
    estimated_time_days: int
    status: str
    created_at: str
    ipfs_cid: Optional[str]
