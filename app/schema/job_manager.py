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


class CreateJob(BaseModel):
    provider_address: str = "0x9Eededda12AB8124f349c58A4109F84D4B564788"
    from_address: str = "0x2Aa6189c6375dB807Ea231CD50E20b804ac2A27B"
    deadline: str = "10-10-2026"
    service_type: str = "Pintura"
    ipfs_hash: str = "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
    value: int = 20


class GetJob(BaseModel):
    job_id: str = "1e97c24742d3249620f7612bec38cee3da664e79e51fca5c16a21f18cae2b11b"