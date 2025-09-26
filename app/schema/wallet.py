from pydantic import BaseModel, Field
from typing import Optional


class CreateWalletRequest(BaseModel):
    password: str = Field(..., description="Senha do usuário para criptografia")
    force_replace: bool = Field(default=False, description="Forçar substituição se já existir")


class ImportPrivateKeyRequest(BaseModel):
    private_key: str = Field(..., description="Chave privada (com ou sem 0x)")
    password: str = Field(..., description="Senha do usuário")
    force_replace: bool = Field(default=False, description="Forçar substituição se já existir")


class ImportMnemonicRequest(BaseModel):
    mnemonic_phrase: str = Field(..., description="12 ou 24 palavras")
    password: str = Field(..., description="Senha do usuário")
    account_index: int = Field(default=0, description="Índice da conta HD")
    force_replace: bool = Field(default=False, description="Forçar substituição se já existir")


class DeleteWalletRequest(BaseModel):
    password: str = Field(..., description="Senha da conta para confirmação")


class TransferRequest(BaseModel):
    password: str = Field(..., description="Senha do usuário para autorizar")
    to_address: str = Field(..., description="Endereço de destino")
    amount_eth: float = Field(..., gt=0, description="Quantidade em ETH")
    note: Optional[str] = Field(None, max_length=200, description="Nota da transação")
