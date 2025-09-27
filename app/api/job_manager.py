from datetime import datetime

from eth_account import Account

from app.ipfs.ipfs_service import IPFSService
from app.model.bico_certo_main import BicoCerto
from app.model.wallet import Wallet
from app.schema.job_manager import CreateJobRequest, CreateOpenJobRequest
from fastapi import APIRouter, Depends, HTTPException
from app.util.responses import APIResponse
from sqlalchemy.orm import Session
from app.config.database import get_db
from app.model.user import User
from app.auth.dependencies import get_current_user
from app.wallet.transaction import TransactionSigner
from app.wallet.wallet_service import WalletService
from app.config.settings import fuso_local

router = APIRouter(prefix="/jobs", tags=["JobManager"])
bico_certo = BicoCerto()
ipfs_service = IPFSService()


@router.post("/create", response_model=APIResponse)
async def create_job(
        request: CreateJobRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Cria um novo job
    """

    wallet = db.query(Wallet).filter(
        Wallet.user_id == current_user.id
    ).first()

    if not wallet:
        raise HTTPException(
            status_code=400,
            detail="Você precisa criar uma carteira primeiro"
        )

    job_metadata = {
        "title": request.title,
        "description": request.description,
        "category": request.category,
        "location": request.location,
        "employer": {
            "address": wallet.address,
            "user_id": current_user.id,
            "name": current_user.full_name if hasattr(current_user, 'full_name') else None
        },
        "payment": {
            "amount": request.payment_eth,
            "currency": "BRL"
        },
        "deadline": request.deadline,
        "created_at": datetime.now(fuso_local).isoformat()
    }

    success, message, ipfs_cid = ipfs_service.add_job_data(job_metadata)

    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao salvar no IPFS: {message}"
        )

    wallet_service = WalletService(db)
    success, message, private_key = wallet_service.get_private_key(
        user_id=current_user.id,
        password=request.password
    )

    if not success:
        raise HTTPException(status_code=401, detail=message)

    signer = TransactionSigner()
    balance = signer.get_balance(wallet.address)

    if balance < request.payment_eth:
        raise HTTPException(
            status_code=400,
            detail=f"Saldo insuficiente. Disponível: {balance} ETH, Necessário: {request.payment_eth} ETH"
        )

    try:
        date_split = request.deadline.split("-")
        date = datetime(int(date_split[2]), int(date_split[1]), int(date_split[0]), 0, 0, 0)

        transaction = bico_certo.prepare_create_job_transaction(
            from_address=wallet.address,
            provider_address=request.provider_address,
            ipfs_cid=ipfs_cid,
            category=request.category,
            deadline=date,
            payment_eth=request.payment_eth
        )

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Erro ao preparar transação: {str(e)}"
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

        job_info = bico_certo.get_job_from_receipt(receipt)

        if not job_info:
            job_info = {
                'jobId': None,
                'ipfsCid': ipfs_cid,
                'transactionHash': tx_hash_hex,
                'blockNumber': receipt['blockNumber']
            }

        return APIResponse.success_response(
            data={
                "blockchain_job_id": job_info['jobId'].hex(),
                "transaction_hash": tx_hash_hex,
                "block_number": receipt['blockNumber'],
                "status": "created",
            },
            message="Job criado com sucesso! Dados no IPFS, referência na blockchain."
        )

    except Exception as e:
        if ipfs_cid:
            ipfs_service.unpin_cid(ipfs_cid)

        raise HTTPException(
            status_code=400,
            detail=f"Erro ao criar job: {str(e)}"
        )


@router.post("/create-open", response_model=APIResponse)
async def create_open_job(
        request: CreateOpenJobRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Cria um job aberto para propostas
    Não especifica um provider, permitindo que vários façam propostas
    """

    wallet = db.query(Wallet).filter(
        Wallet.user_id == current_user.id
    ).first()

    if not wallet:
        raise HTTPException(
            status_code=400,
            detail="Você precisa criar uma carteira primeiro"
        )

    # Preparar metadata do job para IPFS
    job_metadata = {
        "title": request.title,
        "description": request.description,
        "category": request.category,
        "location": request.location,
        "max_budget": request.max_budget_eth,
        "deadline": request.deadline,
        "employer": {
            "address": wallet.address,
            "user_id": current_user.id,
            "name": current_user.full_name
        },
        "open_for_proposals": True,
        "created_at": datetime.now(fuso_local).isoformat()
    }

    # Salvar no IPFS
    success, message, ipfs_cid = ipfs_service.add_job_data(job_metadata)

    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao salvar no IPFS: {message}"
        )

    # Obter chave privada
    wallet_service = WalletService(db)
    success, message, private_key = wallet_service.get_private_key(
        user_id=current_user.id,
        password=request.password
    )

    if not success:
        raise HTTPException(status_code=401, detail=message)

    # Verificar saldo
    signer = TransactionSigner()
    balance = signer.get_balance(wallet.address)

    if balance < request.max_budget_eth:
        raise HTTPException(
            status_code=400,
            detail=f"Saldo insuficiente. Disponível: {balance} ETH, Necessário: {request.max_budget_eth} ETH"
        )

    try:
        # Preparar transação para criar job aberto
        date_split = request.deadline.split("-")
        date = datetime(int(date_split[2]), int(date_split[1]), int(date_split[0]), 0, 0, 0)

        transaction = bico_certo.prepare_create_open_job_transaction(
            from_address=wallet.address,
            ipfs_cid=ipfs_cid,
            category=request.category,
            deadline=date,
            max_budget_eth=request.max_budget_eth
        )

        # Assinar e enviar
        account = Account.from_key(private_key)
        signed_tx = account.sign_transaction(transaction)

        tx_hash = signer.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        tx_hash_hex = tx_hash.hex()

        # Aguardar confirmação
        receipt = signer.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)

        if receipt['status'] != 1:
            raise HTTPException(
                status_code=400,
                detail="Transação falhou na blockchain"
            )

        job_info = bico_certo.get_job_open_from_receipt(receipt)

        if not job_info:
            job_info = {
                'jobId': None,
                'ipfsCid': ipfs_cid,
                'transactionHash': tx_hash_hex,
                'blockNumber': receipt['blockNumber']
            }

        return APIResponse.success_response(
            data={
                "job_id": job_info['jobId'].hex(),
                "transaction_hash": tx_hash_hex,
                "ipfs_cid": ipfs_cid,
                "status": "open_for_proposals",
                "max_budget": request.max_budget_eth,
                "deadline": request.deadline
            },
            message="Job criado e aberto para propostas!"
        )

    except Exception as e:
        if ipfs_cid:
            ipfs_service.unpin_cid(ipfs_cid)

        raise HTTPException(
            status_code=400,
            detail=f"Erro ao criar job: {str(e)}"
        )


@router.get("/{job_id}/metadata", response_model=APIResponse)
async def get_job_metadata(
        job_id: str
):
    """
       Recupera os metadados completos do job do IPFS
       """

    job_data = bico_certo.get_job(job_id).to_dict()

    # Recuperar do IPFS
    success, message, metadata = ipfs_service.get_job_data(job_data['ipfs_hash'])

    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao recuperar dados do IPFS: {message}"
        )

    return APIResponse.success_response(
        data={
            "job_id": job_data['id'],
            "ipfs_cid": job_data['ipfs_hash'],
            "metadata": metadata
        },
        message="Metadados recuperados do IPFS"
    )
