from datetime import datetime
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from web3 import Web3
from ..config.settings import fuso_local, settings
from ..config.database import get_db
from ..model.wallet import Wallet
from ..service.job_notification_service import JobNotificationService
from ..wallet.blockchain_service import BlockchainService
from ..wallet.wallet_service import WalletService
from ..wallet.transaction import TransactionSigner
from ..schema.wallet import (
    CreateWalletRequest,
    ImportPrivateKeyRequest,
    ImportMnemonicRequest,
    DeleteWalletRequest,
    TransferRequest
)
from ..util.responses import APIResponse
from ..auth.dependencies import get_current_user
from ..model.user import User
import asyncio

router = APIRouter(prefix="/wallet", tags=["Wallet"])


@router.post("/create", response_model=APIResponse)
async def create_wallet(
        request: CreateWalletRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Cria nova carteira com mnemonic
    Requer senha do usuário para criptografia
    """
    service = WalletService(db)

    success, message, data = service.create_or_replace_wallet(
        user_id=current_user.id,
        password=request.password,
        force_replace=request.force_replace
    )

    if not success and data and data.get("require_confirmation"):
        return APIResponse.success_response(
            data=data,
            message=message
        )

    if not success:
        raise HTTPException(status_code=400, detail=message)

    return APIResponse.success_response(
        data=data,
        message=message
    )


@router.post("/import/private-key", response_model=APIResponse)
async def import_private_key(
        request: ImportPrivateKeyRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Importa carteira usando chave privada
    """
    service = WalletService(db)

    success, message, data = service.import_from_private_key(
        user_id=current_user.id,
        private_key=request.private_key,
        password=request.password,
        force_replace=request.force_replace
    )

    if not success and data and data.get("require_confirmation"):
        return APIResponse.success_response(
            data=data,
            message=message
        )

    if not success:
        raise HTTPException(status_code=400, detail=message)

    return APIResponse.success_response(
        data=data,
        message=message
    )


@router.post("/import/mnemonic", response_model=APIResponse)
async def import_mnemonic(
        request: ImportMnemonicRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Importa carteira usando mnemonic phrase
    Se já tiver uma carteira, precisa confirmar substituição
    """
    service = WalletService(db)

    success, message, data = service.import_from_mnemonic(
        user_id=current_user.id,
        mnemonic_phrase=request.mnemonic_phrase,
        password=request.password,
        account_index=request.account_index,
        force_replace=request.force_replace
    )

    if not success and data and data.get("require_confirmation"):
        return APIResponse.success_response(
            data=data,
            message=message
        )

    if not success:
        raise HTTPException(status_code=400, detail=message)

    return APIResponse.success_response(
        data=data,
        message=message
    )


@router.get("/my-wallet", response_model=APIResponse)
async def get_my_wallet(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Retorna a carteira do usuário
    """
    service = WalletService(db)
    wallet = service.get_wallet(current_user.id)

    if not wallet:
        return APIResponse.success_response(
            data={"has_wallet": False},
            message="Você ainda não possui uma carteira"
        )

    blockchain = BlockchainService()
    current_balance = blockchain.w3.eth.get_balance(wallet["address"])
    wallet["balance"] = blockchain.w3.from_wei(current_balance, 'ether')

    return APIResponse.success_response(
        data=wallet,
        message="Carteira recuperada com sucesso"
    )


@router.delete("/delete", response_model=APIResponse)
async def delete_wallet(
        request: DeleteWalletRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Deleta a carteira (requer senha)
    """
    service = WalletService(db)

    success, message = service.delete_wallet(
        user_id=current_user.id,
        password=request.password
    )

    if not success:
        raise HTTPException(status_code=400, detail=message)

    return APIResponse.success_response(message=message)


@router.post("/transfer", response_model=APIResponse)
async def transfer_eth(
        request: TransferRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Transfere ETH para outro endereço
    Requer senha do usuário para acessar chave privada
    """

    service = WalletService(db)
    success, message, private_key = service.get_private_key(
        user_id=current_user.id,
        password=request.password
    )

    if not success:
        raise HTTPException(status_code=401, detail=message)

    wallet = db.query(Wallet).filter(
        Wallet.user_id == current_user.id
    ).first()

    if not wallet:
        raise HTTPException(status_code=404, detail="Carteira não encontrada")

    if not Web3.is_address(request.to_address):
        raise HTTPException(status_code=400, detail="Endereço de destino inválido")

    if request.to_address.lower() == wallet.address.lower():
        raise HTTPException(status_code=400, detail="Não pode enviar para sua própria carteira")

    signer = TransactionSigner()
    balance = signer.get_balance(wallet.address)

    if settings.NETWORK_TYPE == "private" and settings.ZERO_GAS_COST:
        if balance < request.amount_eth:
            raise HTTPException(
                status_code=400,
                detail=f"Saldo insuficiente. Disponível: {balance:.6f} ETH, Necessário: {request.amount_eth:.6f} ETH"
            )

    try:
        success, message, tx_hash = signer.sign_and_send_transaction(
            from_address=wallet.address,
            to_address=request.to_address,
            value_eth=request.amount_eth,
            private_key=private_key
        )

        if not success:
            raise HTTPException(status_code=400, detail=message)

        wallet.last_transaction = datetime.now(fuso_local)
        db.commit()

        asyncio.create_task(
            JobNotificationService.notify_receiver(
                db=db,
                receiver_address=request.to_address,
                amount=request.amount_eth,
                tx_hash=tx_hash,
                sender_address=wallet.address
            )
        )

        return APIResponse.success_response(
            data={
                "tx_hash": tx_hash,
                "from": wallet.address,
                "to": request.to_address,
                "amount": request.amount_eth
            },
            message="Transferência enviada com sucesso"
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro na transferência: {str(e)}")


@router.get("/transactions", response_model=APIResponse)
async def list_blockchain_transactions(
        limit: int = 20,
        filter_type: Optional[str] = None,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Lista transações diretamente da blockchain
    """

    wallet = db.query(Wallet).filter(
        Wallet.user_id == current_user.id
    ).first()

    if not wallet:
        return APIResponse.success_response(
            data={"transactions": [], "total": 0},
            message="Você não possui uma carteira"
        )

    blockchain_service = BlockchainService()

    result = blockchain_service.get_wallet_transactions(
        address=wallet.address
    )

    transactions = result.get("transactions", [])

    transactions = [tx for tx in transactions if tx.get("value", 0) != 0]

    if filter_type and filter_type in ["send", "receive"]:
        transactions = [tx for tx in transactions if tx["type"] == filter_type and tx["value"] != 0]

    safe_transactions = []

    for tx in transactions:

        tx_data = dict(tx)

        if 'input' in tx_data and isinstance(tx_data['input'], bytes):
            tx_data['input'] = blockchain_service.w3.to_hex(tx_data['input'])

        safe_transactions.append(tx_data)

    return APIResponse.success_response(
        data={
            "transactions": safe_transactions[:limit],
            "wallet_address": wallet.address,
            "total": len(transactions),
            "limit": limit,
            "current_balance": blockchain_service.w3.from_wei(
                blockchain_service.w3.eth.get_balance(wallet.address), 'ether'
            )
        },
        message=f"Encontradas {len(transactions)} transações na blockchain"
    )


@router.get("/balance", response_model=APIResponse)
async def get_balance(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Obtém saldo da carteira do usuário
    """
    service = WalletService(db)

    wallet = service.get_wallet(current_user.id)

    if not wallet:
        return APIResponse.error_response(
            message="Você não possui uma carteira"
        )

    signer = TransactionSigner()
    balance = signer.get_balance(wallet["address"])

    return APIResponse.success_response(
        data={
            "address": wallet["address"],
            "balance_eth": balance,
            "balance_wei": Web3.to_wei(balance, 'ether')
        }
    )