from eth_account import Account

from app.model.bico_certo_main import BicoCerto
from app.model.wallet import Wallet
from fastapi import APIRouter, Depends, HTTPException
from app.util.responses import APIResponse
from sqlalchemy.orm import Session
from app.config.database import get_db
from app.model.user import User
from app.auth.dependencies import get_current_user
from app.wallet.transaction import TransactionSigner
from app.wallet.wallet_service import WalletService

router = APIRouter(prefix="/payment", tags=["PaymentGateway"])
bico_certo = BicoCerto()


@router.post("/withdraw", response_model=APIResponse)
async def withdraw(
        password: str,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Saca o dinheiro do contrato para a carteira (se tiver saldo disponivel)
    """

    wallet = db.query(Wallet).filter(
        Wallet.user_id == current_user.id
    ).first()

    if not wallet:
        raise HTTPException(
            status_code=400,
            detail="Você precisa criar uma carteira primeiro"
        )

    wallet_service = WalletService(db)
    success, message, private_key = wallet_service.get_private_key(
        user_id=current_user.id,
        password=password
    )

    if not success:
        raise HTTPException(status_code=401, detail=message)

    signer = TransactionSigner()

    try:
        transaction = bico_certo.prepare_withdraw_transaction(from_address=wallet.address)

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Erro ao preparar transação: {str(e.args[1]['reason'])}"
        )

    try:
        account = Account.from_key(private_key)
        signed_tx = account.sign_transaction(transaction)

        tx_hash = signer.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        tx_hash_hex = tx_hash.hex()

        receipt = signer.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)

        if receipt['status'] != 1:
            raise HTTPException(
                status_code=400,
                detail="Transação falhou na blockchain"
            )

        return APIResponse.success_response(
            data={
                "transaction_hash": tx_hash_hex
            },
            message="Saque realizado com sucesso"
        )

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=f"Erro ao enviar a transação: {str(e.args[1]['reason'])}"
        )