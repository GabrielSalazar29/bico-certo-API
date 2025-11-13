from datetime import datetime
from typing import Optional
import base64, binascii

from eth_account import Account

from app.ipfs.ipfs_service import IPFSService
from app.model.bico_certo_main import BicoCerto, ProposalStatus, JobStatus, Reputation
from app.model.wallet import Wallet
from app.schema.job_manager import (
    CreateJobRequest, CreateOpenJobRequest, SubmitProposalRequest, AcceptJobRequest, AnswerProposalRequest,
    CompleteJobRequest, ApproveJobRequest, CancelJobRequest)
from fastapi import APIRouter, Depends, HTTPException, Query

from app.service.job_notification_service import JobNotificationService
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

    success, message, ipfs_cid = ipfs_service.add_data_to_ipfs(job_metadata)

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
                "job_id": job_info['jobId'].hex(),
                "transaction_hash": tx_hash_hex,
                "status": "created",
            },
            message="Job criado com sucesso!"
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


        image_cids = []
    
    
    
    image_cids = []
    if request.job_images:
            for base64_string in request.job_images:
                try:
                    sucess_img, msg_img, cid = ipfs_service.add_bytes_to_ipfs(base64_string) 

                    if not sucess_img:
                        raise HTTPException(status_code=500, detail=f"Erro ao salvar imagens no IPFS: {msg_img}")
                    image_cids.append(cid)

                except Exception as e:
                    HTTPException(status_code=500, detail=f"Erro no processamento de sub-dados: {e}")
                    

    # Preparar metadata do job para IPFS
    job_metadata = {
        "title": request.title,
        "description": request.description,
        "category": request.category,
        "location": request.location,
        "max_budget": request.max_budget_eth,
        "deadline": request.deadline,
        "job_images": image_cids,
        "employer": {
            "address": wallet.address,
            "user_id": current_user.id,
            "name": current_user.full_name
        },
        "open_for_proposals": True,
        "created_at": datetime.now(fuso_local).isoformat()
    }


    success, message, ipfs_cid = ipfs_service.add_data_to_ipfs(job_metadata)

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

    signer = TransactionSigner()
    balance = signer.get_balance(wallet.address)

    if balance < request.max_budget_eth:
        raise HTTPException(
            status_code=400,
            detail=f"Saldo insuficiente. Disponível: {balance} ETH, Necessário: {request.max_budget_eth} ETH"
        )

    try:
        date_split = request.deadline.split("-")
        date = datetime(int(date_split[2]), int(date_split[1]), int(date_split[0]), 0, 0, 0)

        transaction = bico_certo.prepare_create_open_job_transaction(
            from_address=wallet.address,
            ipfs_cid=ipfs_cid,
            category=request.category,
            deadline=date,
            max_budget_eth=request.max_budget_eth
        )

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
                "status": "open_for_proposals"
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

@router.post("/submit-proposal", response_model=APIResponse)
async def submit_proposal(
        request: SubmitProposalRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Envia uma proposta para um Job especifico
    """

    wallet = db.query(Wallet).filter(
        Wallet.user_id == current_user.id
    ).first()

    if not wallet:
        raise HTTPException(
            status_code=400,
            detail="Você precisa criar uma carteira primeiro"
        )

    proposal_metadata = {
        "description": request.description,
        "value": request.amount_eth,
        "estimatedTime": request.estimated_time_days,
        "provider": {
            "created_at": current_user.created_at.isoformat(),
            "address": wallet.address,
            "user_id": current_user.id,
            "name": current_user.full_name
        },
        "created_at": datetime.now(fuso_local).isoformat()
    }

    success, message, ipfs_cid = ipfs_service.add_data_to_ipfs(proposal_metadata)

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

    try:
        transaction = bico_certo.prepare_submit_proposal_transaction(
            from_address=wallet.address,
            ipfs_cid=ipfs_cid,
            job_id=bytes.fromhex(request.job_id),
            amount_eth=request.amount_eth,
            estimated_time=request.estimated_time_days
        )

        # Assinar e enviar
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

        proposal_info = bico_certo.get_proposal_from_receipt(receipt)

        try:
            job = bico_certo.get_job(bytes.fromhex(request.job_id))
            JobNotificationService.notify_new_proposal(
                db=db,
                client_address=job.client,
                job_id=request.job_id,
                ipfs_hash=job.ipfs_hash,
                provider_name=current_user.full_name
            )
        except Exception as e:
            print(f"Erro ao enviar notificação de nova proposta: {e}")

        return APIResponse.success_response(
            data={
                "proposal_id": proposal_info['proposal_id'].hex(),
                "transaction_hash": tx_hash_hex,
                "ipfs_cid": ipfs_cid
            },
            message="Proposta enviada!"
        )

    except Exception as e:
        if ipfs_cid:
            ipfs_service.unpin_cid(ipfs_cid)

        raise HTTPException(
            status_code=400,
            detail=f"Erro ao submeter proposta: {str(e.args[1]['reason'])}"
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
    wallet = db.query(Wallet).filter(Wallet.user_id == current_user.id).first()
    if not wallet:
        raise HTTPException(
            status_code=400,
            detail="Você precisa de uma carteira para aceitar um trabalho."
        )
    wallet_service = WalletService(db)
    success, message, private_key = wallet_service.get_private_key(
        user_id=current_user.id,
        password=request.password
    )
    if not success:
        raise HTTPException(status_code=401, detail=message)
    try:
        signer = TransactionSigner()

        job_id_bytes = bytes.fromhex(request.job_id)

        transaction = bico_certo.prepare_accept_job_transaction(
            from_address=wallet.address,
            job_id=job_id_bytes
        )

        account = Account.from_key(private_key)
        signed_tx = account.sign_transaction(transaction)

        tx_hash = signer.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        tx_hash_hex = tx_hash.hex()

        receipt = signer.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

        if receipt['status'] != 1:
            raise HTTPException(
                status_code=400,
                detail="A transação falhou na blockchain. Verifique se você é o prestador correto e se o job está disponível."
            )

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

        try:
            job = bico_certo.get_job(job_id_bytes)

            JobNotificationService.notify_job_completed(
                db=db,
                client_address=job.client,
                job_id=request.job_id,
                ipfs_hash=job.ipfs_hash,
                provider_name=current_user.full_name
            )
        except Exception as e:
            print(f"Erro ao enviar notificação: {e}")

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

        try:
            job = bico_certo.get_job(job_id_bytes)

            # JobNotificationService.notify_job_approved(
            #     db=db,
            #     provider_address=job.provider,
            #     job_id=request.job_id,
            #     ipfs_hash=job.ipfs_hash,
            #     client_name=current_user.full_name,
            #     rating=request.rating
            # )

            # Após aprovar o job com sucesso
            JobNotificationService.notify_provider_to_rate_client(
                db=db,
                provider_address=job.provider,
                job_id=request.job_id,
                ipfs_hash=job.ipfs_hash,
                client_name=current_user.full_name
            )
        except Exception as e:
            print(f"Erro ao enviar notificação: {e}")

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

@router.post("/accept-proposal", response_model=APIResponse)
async def accept_proposal(
        request: AnswerProposalRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Aceita uma proposta para um job
    """

    wallet = db.query(Wallet).filter(
        Wallet.user_id == current_user.id
    ).first()

    if not wallet:
        raise HTTPException(
            status_code=400,
            detail="Você precisa criar uma carteira primeiro"
        )

    # Obter chave privada
    wallet_service = WalletService(db)
    success, message, private_key = wallet_service.get_private_key(
        user_id=current_user.id,
        password=request.password
    )

    if not success:
        raise HTTPException(status_code=401, detail=message)

    try:
        # Buscar detalhes da proposta
        proposal = bico_certo.contract.functions.getProposal(
            bytes.fromhex(request.proposal_id)
        ).call()

        job = bico_certo.contract.functions.getJob(proposal[1]).call()  # jobId

        # Calcular se precisa de fundos adicionais
        original_total = job[3] + job[4]  # amount + platformFee
        proposal_total = proposal[3]  # proposal amount

        additional_funds_needed = 0
        if proposal_total > original_total:
            additional_funds_needed = proposal_total - original_total

            # Verificar saldo
            signer = TransactionSigner()
            balance = signer.get_balance(wallet.address)

            if balance < bico_certo.w3.from_wei(additional_funds_needed, 'ether'):
                raise HTTPException(
                    status_code=400,
                    detail=f"Saldo insuficiente para fundos adicionais. Necessário: {bico_certo.w3.from_wei(additional_funds_needed, 'ether')} ETH"
                )

        # Preparar transação
        transaction = bico_certo.prepare_accept_proposal_transaction(wallet.address, bytes.fromhex(request.proposal_id), additional_funds_needed)

        # Assinar e enviar
        account = Account.from_key(private_key)
        signed_tx = account.sign_transaction(transaction)

        signer = TransactionSigner()
        tx_hash = signer.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        tx_hash_hex = tx_hash.hex()

        # Aguardar confirmação
        receipt = signer.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)

        if receipt['status'] != 1:
            raise HTTPException(
                status_code=400,
                detail="Transação falhou na blockchain"
            )

        try:
            proposal = bico_certo.contract.functions.getProposal(
                bytes.fromhex(request.proposal_id)
            ).call()
            job = bico_certo.get_job(proposal[1])

            JobNotificationService.notify_proposal_accepted(
                db=db,
                provider_address=proposal[2],
                job_id=proposal[1].hex(),
                ipfs_hash=job.ipfs_hash,
                client_name=current_user.full_name
            )
        except Exception as e:
            print(f"Erro ao enviar notificação: {e}")

        return APIResponse.success_response(
            data={
                "proposal_id": request.proposal_id,
                "transaction_hash": tx_hash_hex,
                "status": "accepted"
            },
            message="Proposta aceita com sucesso!"
        )

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Erro ao aceitar proposta: {str(e.args[1]['reason'])}"
        )


@router.post("/reject-proposal", response_model=APIResponse)
async def reject_proposal(
        request: AnswerProposalRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Rejeita uma proposta
    """

    wallet = db.query(Wallet).filter(
        Wallet.user_id == current_user.id
    ).first()

    if not wallet:
        raise HTTPException(
            status_code=400,
            detail="Você precisa criar uma carteira primeiro"
        )

    # Obter chave privada
    wallet_service = WalletService(db)
    success, message, private_key = wallet_service.get_private_key(
        user_id=current_user.id,
        password=request.password
    )

    if not success:
        raise HTTPException(status_code=401, detail=message)

    try:
        # Chamar função do contrato
        transaction = bico_certo.prepare_reject_proposal_transaction(
            wallet.address,
            bytes.fromhex(request.proposal_id)
        )

        # Preparar transação
        signer = TransactionSigner()

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

        try:
            proposal = bico_certo.contract.functions.getProposal(
                bytes.fromhex(request.proposal_id)
            ).call()
            job = bico_certo.get_job(proposal[1])

            JobNotificationService.notify_proposal_rejected(
                db=db,
                provider_address=proposal[2],
                job_id=proposal[1].hex(),
                ipfs_hash=job.ipfs_hash,
                client_name=current_user.full_name
            )
        except Exception as e:
            print(f"Erro ao enviar notificação: {e}")

        return APIResponse.success_response(
            data={
                "proposal_id": request.proposal_id,
                "transaction_hash": tx_hash_hex,
                "status": "rejected"
            },
            message="Proposta rejeitada"
        )

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Erro ao rejeitar proposta: {str(e.args[1]['reason'])}"
        )


@router.post("/cancel-proposal", response_model=APIResponse)
async def cancel_proposal(
        request: AnswerProposalRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Retira uma proposta enviada
    """

    wallet = db.query(Wallet).filter(
        Wallet.user_id == current_user.id
    ).first()

    if not wallet:
        raise HTTPException(
            status_code=400,
            detail="Você precisa criar uma carteira primeiro"
        )

    # Obter chave privada
    wallet_service = WalletService(db)
    success, message, private_key = wallet_service.get_private_key(
        user_id=current_user.id,
        password=request.password
    )

    if not success:
        raise HTTPException(status_code=401, detail=message)

    try:

        transaction = bico_certo.prepare_cancel_proposal_transaction(
            wallet.address,
            bytes.fromhex(request.proposal_id)
        )

        signer = TransactionSigner()

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
                "proposal_id": request.proposal_id,
                "transaction_hash": tx_hash_hex,
                "status": "canceled"
            },
            message="Proposta retirada com sucesso"
        )

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Erro ao retirar proposta: {str(e.args[1]['reason'])}"
        )


@router.get("/job/{job_id}/info", response_model=APIResponse)
async def get_job(
        job_id: str
):
    """
       Recupera as informações do Job
    """

    job_data = bico_certo.get_job(bytes.fromhex(job_id)).to_dict()

    success, message, metadata = ipfs_service.get_job_data(job_data['ipfs_hash'])

    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao recuperar dados do IPFS: {message}"
        )

    pending_proposal_count = 0
    if job_data["total_proposals"] > 0:
        proposals = bico_certo.contract.functions.getJobProposals(bytes.fromhex(job_id)).call()
        for proposal_id in proposals:
            proposal_data = bico_certo.contract.functions.getProposal(proposal_id).call()
            if ProposalStatus(proposal_data[6]) == ProposalStatus.PENDING:
                pending_proposal_count += 1

    return APIResponse.success_response(
        data={
            **job_data,
            "pending_proposal_count": pending_proposal_count,
            "metadata": metadata
        },
        message="Informações do Job recuperadas com sucesso"
    )


@router.get("/open-jobs", response_model=APIResponse)
async def get_open_jobs(
        category: Optional[str] = Query(None, description="Filtrar por categoria"),
        search: Optional[str] = Query(None, description="Buscar por título ou descrição")
):
    """
    Lista todos os jobs abertos para propostas
    Opcionalmente filtra por categoria e/ou busca por texto
    """
    try:
        open_job_ids = bico_certo.contract.functions.getOpenJobs().call()

        jobs = []
        for job_id in open_job_ids:
            job_data = bico_certo.get_job(job_id).to_dict()

            success, message, metadata = ipfs_service.get_job_data(job_data["ipfs_hash"])
            success_image, message_image, metadata_image = ipfs_service.get_job_data(metadata["data"])
            print(f"\n\n{metadata_image}\n\n")


            if success:
                # Filtrar por categoria se fornecida
                if category is not None and job_data["service_type"].lower() != category.lower():
                    continue

                # Filtrar por busca de texto se fornecida
                if search is not None:
                    search_lower = search.lower()
                    title = metadata.get("data", {}).get("title", "").lower()
                    description = metadata.get("data", {}).get("description", "").lower()

                    # Verifica se o termo de busca está no título ou descrição
                    if search_lower not in title and search_lower not in description:
                        continue

                pending_proposal_count = 0

                if job_data["total_proposals"] > 0:
                    proposals = bico_certo.contract.functions.getJobProposals(job_id).call()
                    for proposal_id in proposals:
                        proposal_data = bico_certo.contract.functions.getProposal(proposal_id).call()
                        if ProposalStatus(proposal_data[6]) == ProposalStatus.PENDING:
                            pending_proposal_count += 1

                jobs.append({
                    **job_data,
                    "pending_proposal_count": pending_proposal_count,
                    "metadata": metadata,
                })

        message = f"Encontrados {len(jobs)} jobs abertos"
        if category:
            message += f" na categoria '{category}'"
        if search:
            message += f" com o termo '{search}'"

        return APIResponse.success_response(
            data={
                "open_jobs": jobs,
                "total": len(jobs),
                "category_filter": category,
                "search_term": search
            },
            message=message
        )

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Erro ao buscar jobs abertos: {str(e)}"
        )


@router.get("/my-jobs", response_model=APIResponse)
async def get_my_jobs(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Lista jobs criados pelo usuário (como cliente)
    """

    wallet = db.query(Wallet).filter(
        Wallet.user_id == current_user.id
    ).first()

    if not wallet:
        return APIResponse.success_response(
            data={"jobs": [], "total": 0},
            message="Você não possui uma carteira"
        )

    try:
        # Buscar jobs onde o usuário é o cliente
        all_jobs = bico_certo.contract.functions.getUserJobs(wallet.address).call()

        jobs = []
        for job_id in all_jobs:
            job_data = bico_certo.get_job(job_id).to_dict()

            # Filtrar apenas jobs onde o usuário é o cliente
            if job_data["client"].lower() != wallet.address.lower():
                continue

            ipfs_cid = job_data["ipfs_hash"]
            success, message, metadata = ipfs_service.get_job_data(ipfs_cid)

            pending_proposal_count = 0
            total_proposals = job_data["total_proposals"]
            accepted_proposal = None

            if total_proposals > 0:
                # Buscar todas as propostas do job
                proposals = bico_certo.contract.functions.getJobProposals(job_id).call()

                for proposal_id in proposals:
                    proposal_data = bico_certo.contract.functions.getProposal(proposal_id).call()
                    if job_data["openForProposals"]:
                        if ProposalStatus(proposal_data[6]) == ProposalStatus.PENDING:
                            pending_proposal_count += 1
                    else:
                        if ProposalStatus(proposal_data[6]) == ProposalStatus.ACCEPTED:
                            success, message, metadata_proposal = ipfs_service.get_job_data(proposal_data[7])
                            accepted_proposal = metadata_proposal["data"]

            jobs.append({
                **job_data,
                "pending_proposal_count": pending_proposal_count,
                "metadata": metadata if success else None,
                "accepted_proposal": accepted_proposal
            })

        return APIResponse.success_response(
            data={
                "jobs": jobs,
                "total": len(jobs)
            },
            message=f"Você criou {len(jobs)} jobs"
        )

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Erro ao buscar seus jobs: {str(e)}"
        )

@router.get("/job/{job_id}/proposals", response_model=APIResponse)
async def get_job_proposals(job_id: str):
    """
    Lista todas as propostas de um job
    """
    try:
        # Buscar propostas do job
        proposal_ids = bico_certo.contract.functions.getJobProposals(
            bytes.fromhex(job_id)
        ).call()

        proposals = []
        for proposal_id in proposal_ids:
            proposal_data = bico_certo.contract.functions.getProposal(proposal_id).call()

            # Buscar metadata do IPFS
            ipfs_cid = proposal_data[7]  # ipfsHash
            success, message, metadata = ipfs_service.get_job_data(ipfs_cid)

            proposals.append({
                "proposal_id": proposal_id.hex(),
                "provider": proposal_data[2],
                "amount": bico_certo.w3.from_wei(proposal_data[3], 'ether'),
                "estimated_time_days": proposal_data[4],
                "created_at": datetime.fromtimestamp(proposal_data[5]).isoformat(),
                "status": ProposalStatus(proposal_data[6]).name,
                "metadata": metadata if success else None,
                "ipfs_cid": ipfs_cid
            })

        # Ordenar por data de criação (mais recentes primeiro)
        proposals.sort(key=lambda x: x["created_at"], reverse=True)

        return APIResponse.success_response(
            data={
                "job_id": job_id,
                "proposals": proposals,
                "total": len(proposals),
                "pending_count": sum(1 for p in proposals if p["status"] == "pending")
            },
            message=f"Encontradas {len(proposals)} propostas para o job"
        )

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Erro ao buscar propostas: {str(e)}"
        )


@router.get("/my-proposals", response_model=APIResponse)
async def get_my_proposals(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Lista propostas enviadas pelo usuário
    """

    wallet = db.query(Wallet).filter(
        Wallet.user_id == current_user.id
    ).first()

    if not wallet:
        return APIResponse.success_response(
            data={"proposals": [], "total": 0},
            message="Você não possui uma carteira"
        )

    try:
        # Buscar propostas do provider
        proposal_ids = bico_certo.contract.functions.getProviderProposals(
            wallet.address
        ).call()

        proposals = []
        for proposal_id in proposal_ids:
            proposal_data = bico_certo.contract.functions.getProposal(proposal_id).call()
            job_data = bico_certo.get_job(proposal_data[1]).to_dict()

            success, message, metadata = ipfs_service.get_job_data(job_data["ipfs_hash"])
            job_data["metadata"] = metadata

            proposals.append({
                "proposal_id": proposal_id.hex(),
                "job_id": proposal_data[1].hex(),
                "amount": bico_certo.w3.from_wei(proposal_data[3], 'ether'),
                "estimated_time_days": proposal_data[4],
                "status": ProposalStatus(proposal_data[6]).name,
                "created_at": datetime.fromtimestamp(proposal_data[5]).isoformat(),
                "job": {**job_data}
            })

        return APIResponse.success_response(
            data={
                "proposals": proposals,
                "total": len(proposals),
                "pending": sum(1 for p in proposals if p["status"] == "pending"),
                "accepted": sum(1 for p in proposals if p["status"] == "accepted")
            },
            message=f"Você tem {len(proposals)} propostas"
        )

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Erro ao buscar suas propostas: {str(e)}"
        )


@router.get("/proposal/{proposalId}", response_model=APIResponse)
async def get_proposal(proposal_id: str):
    """
    Recupera as informações de uma proposta
    """
    try:
        # Buscar jobs abertos do contrato
        proposal = bico_certo.contract.functions.getProposal(
            bytes.fromhex(proposal_id)
        ).call()

        # Buscar metadata do IPFS
        ipfs_cid = proposal[7]  # ipfsHash
        success, message, metadata = ipfs_service.get_job_data(ipfs_cid)

        if success:
            return APIResponse.success_response(
                data={
                 "proposalId": proposal[0].hex(),
                 "jobId": proposal[1].hex(),
                 "provider": proposal[2],
                 "amount": bico_certo.w3.from_wei(proposal[3], 'ether'),
                 "estimatedTime": proposal[4],
                 "created_at": datetime.fromtimestamp(proposal[5]).isoformat(),
                 "status": ProposalStatus(proposal[6]).name,
                 "metadata": metadata
                }
            )

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Erro ao buscar jobs abertos: {str(e)}"
        )


@router.get("/job/{job_id}/proposals_active", response_model=APIResponse)
async def get_job_active_proposals(job_id: str):
    """
    Lista todas as propostas ativas de um job
    """
    try:
        # Buscar propostas do job
        proposals = bico_certo.contract.functions.getActiveProposalsForJob(
            bytes.fromhex(job_id)
        ).call()

        proposals_formated = []
        for proposal_data in proposals:

            # Buscar metadata do IPFS
            ipfs_cid = proposal_data[7]  # ipfsHash
            success, message, metadata = ipfs_service.get_job_data(ipfs_cid)

            proposals_formated.append({
                "proposal_id": proposal_data[0].hex(),
                "provider": proposal_data[2],
                "amount": bico_certo.w3.from_wei(proposal_data[3], 'ether'),
                "estimated_time_days": proposal_data[4],
                "created_at": datetime.fromtimestamp(proposal_data[5]).isoformat(),
                "status": ProposalStatus(proposal_data[6]).name,
                "metadata": metadata if success else None,
                "ipfs_cid": ipfs_cid
            })

        # Ordenar por data de criação (mais recentes primeiro)
        proposals_formated.sort(key=lambda x: x["created_at"], reverse=True)

        return APIResponse.success_response(
            data={
                "job_id": job_id,
                "proposals": proposals_formated,
                "total": len(proposals_formated),
                "pending_count": sum(1 for p in proposals_formated if p["status"] == "pending")
            },
            message=f"Encontradas {len(proposals_formated)} propostas abertas para o job"
        )

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Erro ao buscar propostas: {str(e)}"
        )


@router.get("/reputation", response_model=APIResponse)
async def get_reputation(address: str):
    """
    Recupera as informações da reputação de um Usuario
    """
    try:
        # Buscar jobs abertos do contrato
        reputation = Reputation(bico_certo.contract.functions.getUserProfile(
            address
        ).call()).to_dict()

        return APIResponse.success_response(
            data={
             **reputation
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Erro ao buscar jobs abertos: {str(e)}"
        )

@router.post("/rate-client", response_model=APIResponse)
async def rate_client(
    request: ApproveJobRequest,  # Reutilizando o schema existente (job_id, rating, password)
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Avalia um cliente após a aprovação do job. Ação realizada pelo prestador.
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
        transaction = bico_certo.prepare_rate_client_transaction(
            wallet["address"],
            job_id_bytes,
            request.rating
        )

        account = Account.from_key(private_key)
        signed_tx = account.sign_transaction(transaction)
        tx_hash = signer.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = signer.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

        if receipt['status'] != 1:
            raise HTTPException(status_code=400, detail="Transação falhou na blockchain.")

        return APIResponse.success_response(
            data={"transaction_hash": tx_hash.hex(), "rating": request.rating},
            message="Cliente avaliado com sucesso!"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao avaliar cliente: {str(e)}")
