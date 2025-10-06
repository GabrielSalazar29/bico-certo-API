from datetime import datetime

from eth_account import Account

from app.ipfs.ipfs_service import IPFSService
from app.model.bico_certo_main import BicoCerto
from app.model.wallet import Wallet
from app.schema.job_manager import (
    CreateJobRequest, CreateOpenJobRequest, SubmitProposalRequest, AcceptJobRequest, AnswerProposalRequest,
    CompleteJobRequest, ApproveJobRequest, CancelJobRequest)
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

        # Tenta extrair a razão da falha da blockchain
        reason = "Erro desconhecido na blockchain."
        try:
            # A mensagem de erro do contrato geralmente está aninhada nos argumentos da exceção
            if e.args and isinstance(e.args[0], dict) and 'message' in e.args[0]:
                reason = e.args[0]['message']
        except (IndexError, KeyError, TypeError):
            # Se não conseguir extrair, usa a mensagem de erro padrão
            reason = str(e)

        raise HTTPException(
            status_code=400,
            detail=f"Erro ao criar job: {reason}"
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

@router.post("/accept", response_model=APIResponse)
async def accept_job(
        request: AcceptJobRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Aceita um job existente.
    Esta ação deve ser executada pelo prestador de serviço (provider).
    """
    # 1. Verificar se o usuário (provider) tem uma carteira
    wallet = db.query(Wallet).filter(Wallet.user_id == current_user.id).first()
    if not wallet:
        raise HTTPException(
            status_code=400,
            detail="Você precisa de uma carteira para aceitar um trabalho."
        )

    # 2. Obter a chave privada de forma segura
    wallet_service = WalletService(db)
    success, message, private_key = wallet_service.get_private_key(
        user_id=current_user.id,
        password=request.password
    )
    if not success:
        raise HTTPException(status_code=401, detail=message)

    # 3. Preparar, assinar e enviar a transação
    try:
        signer = TransactionSigner()

        # Prepara a transação de aceite
        transaction = bico_certo.prepare_accept_job_transaction(
            from_address=wallet.address,
            job_id=request.job_id
        )

        # Assina a transação com a chave privada
        account = Account.from_key(private_key)
        signed_tx = account.sign_transaction(transaction)

        # Envia a transação para a blockchain
        tx_hash = signer.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        tx_hash_hex = tx_hash.hex()

        # Aguarda a confirmação (recibo)
        receipt = signer.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

        # Verifica se a transação foi bem-sucedida
        if receipt['status'] != 1:
            raise HTTPException(
                status_code=400,
                detail="A transação falhou na blockchain. Verifique se você é o prestador correto e se o job está disponível."
            )

        # Processa o evento para obter dados de confirmação
        job_info = bico_certo.get_job_accepted_from_receipt(receipt)

        return APIResponse.success_response(
            data={
                "transaction_hash": tx_hash_hex,
                "block_number": receipt['blockNumber'],
                "status": "accepted",
                "job_info_from_event": job_info
            },
            message="Job aceito com sucesso!"
        )

    except Exception as e:
        # Erro genérico durante o processo
        raise HTTPException(
            status_code=400,
            detail=f"Erro ao aceitar o job: {str(e)}"
        )
    
@router.post("/complete", response_model=APIResponse)
async def complete_job(
        request: CompleteJobRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Marca um job como concluído. Ação realizada pelo prestador de serviço.
    """
    wallet_service = WalletService(db)
    wallet = wallet_service.get_wallet(current_user.id)
    if not wallet:
        raise HTTPException(status_code=400, detail="Você precisa de uma carteira para esta ação.")

    success, message, private_key = wallet_service.get_private_key(current_user.id, request.password)
    if not success:
        raise HTTPException(status_code=401, detail=message)

    try:
        signer = TransactionSigner()
        job_id_bytes = bytes.fromhex(request.job_id)
        transaction = bico_certo.prepare_complete_job_transaction(wallet["address"], job_id_bytes)

        account = Account.from_key(private_key)
        signed_tx = account.sign_transaction(transaction)
        tx_hash = signer.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = signer.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

        if receipt['status'] != 1:
            raise HTTPException(status_code=400, detail="Transação falhou na blockchain.")

        return APIResponse.success_response(
            data={"transaction_hash": tx_hash.hex(), "status": "completed"},
            message="Job marcado como concluído com sucesso!"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao concluir o job: {str(e)}")


@router.post("/approve", response_model=APIResponse)
async def approve_job(
        request: ApproveJobRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Aprova um job concluído, liberando o pagamento para o prestador. Ação realizada pelo cliente.
    """
    wallet_service = WalletService(db)
    wallet = wallet_service.get_wallet(current_user.id)
    if not wallet:
        raise HTTPException(status_code=400, detail="Você precisa de uma carteira para esta ação.")

    success, message, private_key = wallet_service.get_private_key(current_user.id, request.password)
    if not success:
        raise HTTPException(status_code=401, detail=message)

    try:
        signer = TransactionSigner()
        job_id_bytes = bytes.fromhex(request.job_id)
        transaction = bico_certo.prepare_approve_job_transaction(wallet["address"], job_id_bytes, request.rating)

        account = Account.from_key(private_key)
        signed_tx = account.sign_transaction(transaction)
        tx_hash = signer.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = signer.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

        if receipt['status'] != 1:
            raise HTTPException(status_code=400, detail="Transação falhou na blockchain.")

        return APIResponse.success_response(
            data={"transaction_hash": tx_hash.hex(), "status": "approved"},
            message="Job aprovado e pagamento liberado com sucesso!"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao aprovar o job: {str(e)}")


@router.post("/cancel", response_model=APIResponse)
async def cancel_job(
        request: CancelJobRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Cancela um job que ainda está no estado 'Created'. Ação realizada pelo cliente.
    """
    wallet_service = WalletService(db)
    wallet = wallet_service.get_wallet(current_user.id)
    if not wallet:
        raise HTTPException(status_code=400, detail="Você precisa de uma carteira para esta ação.")

    success, message, private_key = wallet_service.get_private_key(current_user.id, request.password)
    if not success:
        raise HTTPException(status_code=401, detail=message)

    try:
        signer = TransactionSigner()
        job_id_bytes = bytes.fromhex(request.job_id)
        transaction = bico_certo.prepare_cancel_job_transaction(wallet["address"], job_id_bytes)

        account = Account.from_key(private_key)
        signed_tx = account.sign_transaction(transaction)
        tx_hash = signer.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = signer.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

        if receipt['status'] != 1:
            raise HTTPException(status_code=400, detail="Transação falhou na blockchain.")

        return APIResponse.success_response(
            data={"transaction_hash": tx_hash.hex(), "status": "cancelled"},
            message="Job cancelado com sucesso e fundos estornados."
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao cancelar o job: {str(e)}")


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
