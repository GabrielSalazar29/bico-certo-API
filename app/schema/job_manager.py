from pydantic import BaseModel, Field
from typing import Optional, List


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
