# app/service/job_notification_service.py

from sqlalchemy.orm import Session
from ..model.user import User
from ..model.wallet import Wallet
from .fcm_service import FCMService
from app.service.ipfs_service import IPFSService
import asyncio


class JobNotificationService:
    """Serviço para enviar notificações relacionadas a Jobs"""

    @staticmethod
    def _get_job_title(ipfs_hash: str) -> str:
        """Busca o título do job no IPFS"""
        try:
            ipfs_service = IPFSService()
            success, _, ipfs_data = ipfs_service.get_job_data(ipfs_hash)

            if success and ipfs_data:
                return ipfs_data.get('data', {}).get('title', 'Job')
            return 'Job'
        except Exception as e:
            print(f"Erro ao buscar título do job: {e}")
            return 'Job'

    @staticmethod
    def _get_user_by_wallet_address(db: Session, wallet_address: str):
        """Busca usuário pelo endereço da carteira"""
        try:
            wallet = db.query(Wallet).filter(
                Wallet.address == wallet_address
            ).first()

            if wallet:
                return db.query(User).filter(User.id == wallet.user_id).first()
            return None
        except Exception as e:
            print(f"Erro ao buscar usuário: {e}")
            return None

    @staticmethod
    async def _send_websocket_update(user_id: str, job_id: str, status: str, message: str):
        """Envia atualização via WebSocket"""
        try:
            from ..websocket.notifications_handler import notifications_manager

            await notifications_manager.send_to_user(user_id, {
                "type": "job_status_update",
                "data": {
                    "job_id": job_id,
                    "status": status,
                    "message": message
                }
            })
        except Exception as e:
            print(f"Erro ao enviar via WebSocket: {e}")

    @staticmethod
    async def notify_receiver(
            db: Session,
            receiver_address: str,
            amount: float,
            tx_hash: str,
            sender_address: str
    ):
        """Envia notificação apenas para quem recebeu o dinheiro"""
        try:
            # Buscar a carteira do destinatário
            receiver_wallet = db.query(Wallet).filter(
                Wallet.address == receiver_address
            ).first()

            if not receiver_wallet:
                print(f"Destinatário {receiver_address} não é usuário da plataforma")
                return

            # Buscar o usuário
            receiver = db.query(User).filter(
                User.id == receiver_wallet.user_id
            ).first()

            if not receiver:
                print(f"Usuário não encontrado para carteira {receiver_address}")
                return

            formato_us = f'{amount:,.2f}'

            message = f"Você recebeu R$ {formato_us.translate(str.maketrans(',.', '.,'))}"

            from ..websocket.notifications_handler import notifications_manager

            await notifications_manager.send_to_user(receiver.id, {
                "type": "wallet_update",
                "data": {
                    "transaction_type": "receive",
                    "amount": amount,
                    "from": sender_address,
                    "to": receiver_address,
                    "tx_hash": tx_hash,
                    "message": message
                }
            })

            if receiver.fcm_token:
                from ..service.fcm_service import FCMService

                FCMService.send_notification(
                    token=receiver.fcm_token,
                    title="Pagamento Recebido! 💰",
                    body=message,
                    data={
                        "type": "wallet_transaction",
                        "transaction_type": "receive",
                        "tx_hash": tx_hash,
                    }
                )

        except Exception as e:
            print(f"Erro ao enviar notificação: {e}")

    @staticmethod
    def notify_provider_to_rate_client(
            db: Session,
            provider_address: str,
            job_id: str,
            ipfs_hash: str,
            client_name: str
    ):
        """Notifica provider para avaliar o cliente após aprovação"""
        try:
            user = JobNotificationService._get_user_by_wallet_address(db, provider_address)

            if not user:
                return

            job_title = JobNotificationService._get_job_title(ipfs_hash)
            notification_message = f"Avalie {client_name} pelo trabalho '{job_title}'"

            asyncio.create_task(
                JobNotificationService._send_websocket_update(
                    user_id=user.id,
                    job_id=job_id,
                    status="rate_client_prompt",
                    message=notification_message
                )
            )

            if user.fcm_token:
                from ..service.fcm_service import FCMService

                FCMService.send_notification(
                    token=user.fcm_token,
                    title="Trabalho Aprovado! ⭐",
                    body=f"Avalie {client_name} pelo trabalho '{job_title}'",
                    data={
                        "type": "rate_client_prompt",
                        "job_id": job_id,
                        "client_name": client_name,
                        "job_title": job_title,  # ✅ ADICIONAR TÍTULO
                    }
                )
        except Exception as e:
            print(f"Erro ao enviar notificação: {e}")

    @staticmethod
    def notify_proposal_accepted(
            db: Session,
            provider_address: str,
            job_id: str,
            ipfs_hash: str,
            client_name: str
    ):
        """Notifica provider que sua proposta foi aceita"""
        try:
            user = JobNotificationService._get_user_by_wallet_address(db, provider_address)

            if not user:
                return

            job_title = JobNotificationService._get_job_title(ipfs_hash)
            notification_message = f"{client_name} aceitou sua proposta para '{job_title}'"

            asyncio.create_task(
                JobNotificationService._send_websocket_update(
                    user_id=user.id,
                    job_id=job_id,
                    status="accepted",
                    message=notification_message
                )
            )

            if user.fcm_token:
                FCMService.send_notification(
                    token=user.fcm_token,
                    title="Proposta Aceita! 🎉",
                    body=notification_message,
                    data={
                        "type": "job_status_change",
                        "job_id": job_id,
                        "status": "accepted",
                    }
                )
        except Exception as e:
            print(f"Erro ao enviar notificação: {e}")

    @staticmethod
    def notify_job_rejected(
            db: Session,
            provider_address: str,
            job_id: str,
            ipfs_hash: str,
            client_name: str
    ):
        """Notifica provider que seu Job não está completo"""
        try:
            user = JobNotificationService._get_user_by_wallet_address(db, provider_address)

            if not user:
                return

            job_title = JobNotificationService._get_job_title(ipfs_hash)
            notification_message = f"{client_name} não concorda que o trabalho '{job_title}' foi finalizado... Status voltou para 'Em Progresso'"

            asyncio.create_task(
                JobNotificationService._send_websocket_update(
                    user_id=user.id,
                    job_id=job_id,
                    status="rejected",
                    message=notification_message
                )
            )

            if user.fcm_token:
                FCMService.send_notification(
                    token=user.fcm_token,
                    title="Finalização do Trabalho Negada! 😢",
                    body=notification_message,
                    data={
                        "type": "job_status_change",
                        "job_id": job_id,
                        "status": "rejected",
                    }
                )
        except Exception as e:
            print(f"Erro ao enviar notificação: {e}")

    @staticmethod
    def notify_proposal_rejected(
            db: Session,
            provider_address: str,
            job_id: str,
            ipfs_hash: str,
            client_name: str
    ):
        """Notifica provider que sua proposta foi rejeitada"""
        try:
            user = JobNotificationService._get_user_by_wallet_address(db, provider_address)

            if not user:
                return

            job_title = JobNotificationService._get_job_title(ipfs_hash)
            notification_message = f"{client_name} rejeitou sua proposta para '{job_title}'"

            asyncio.create_task(
                JobNotificationService._send_websocket_update(
                    user_id=user.id,
                    job_id=job_id,
                    status="rejected",
                    message=notification_message
                )
            )

            if user.fcm_token:
                FCMService.send_notification(
                    token=user.fcm_token,
                    title="Proposta Rejeitada",
                    body=notification_message,
                    data={
                        "type": "job_status_change",
                        "job_id": job_id,
                        "status": "rejected",
                    }
                )
        except Exception as e:
            print(f"Erro ao enviar notificação: {e}")

    @staticmethod
    def notify_job_completed(
            db: Session,
            client_address: str,
            job_id: str,
            ipfs_hash: str,
            provider_name: str
    ):
        """Notifica cliente que o job foi completado"""
        try:
            user = JobNotificationService._get_user_by_wallet_address(db, client_address)

            if not user:
                return

            job_title = JobNotificationService._get_job_title(ipfs_hash)
            notification_message = f"{provider_name} concluiu o trabalho '{job_title}'. Aguardando sua aprovação."

            asyncio.create_task(
                JobNotificationService._send_websocket_update(
                    user_id=user.id,
                    job_id=job_id,
                    status="completed",
                    message=notification_message
                )
            )

            if user.fcm_token:
                FCMService.send_notification(
                    token=user.fcm_token,
                    title="Trabalho Concluído! ✅",
                    body=notification_message,
                    data={
                        "type": "job_status_change",
                        "job_id": job_id,
                        "status": "completed",
                    }
                )
        except Exception as e:
            print(f"Erro ao enviar notificação: {e}")

    @staticmethod
    def notify_job_approved(
            db: Session,
            provider_address: str,
            job_id: str,
            ipfs_hash: str,
            client_name: str,
            rating: int
    ):
        """Notifica provider que o job foi aprovado"""
        try:
            user = JobNotificationService._get_user_by_wallet_address(db, provider_address)

            if not user:
                return

            job_title = JobNotificationService._get_job_title(ipfs_hash)
            stars = "⭐" * rating
            notification_message = f"{client_name} aprovou '{job_title}' - Avaliação: {stars}"

            asyncio.create_task(
                JobNotificationService._send_websocket_update(
                    user_id=user.id,
                    job_id=job_id,
                    status="approved",
                    message=notification_message
                )
            )

            if user.fcm_token:
                FCMService.send_notification(
                    token=user.fcm_token,
                    title="Pagamento Liberado! 💰",
                    body=notification_message,
                    data={
                        "type": "job_status_change",
                        "job_id": job_id,
                        "status": "approved",
                    }
                )

        except Exception as e:
            print(f"Erro ao enviar notificação: {e}")

    @staticmethod
    def notify_job_accepted_by_provider(
            db: Session,
            client_address: str,
            job_id: str,
            ipfs_hash: str,
            provider_name: str
    ):
        """Notifica cliente que provider aceitou o job"""
        try:
            user = JobNotificationService._get_user_by_wallet_address(db, client_address)

            if not user:
                return

            job_title = JobNotificationService._get_job_title(ipfs_hash)
            notification_message = f"{provider_name} aceitou o trabalho '{job_title}'"

            asyncio.create_task(
                JobNotificationService._send_websocket_update(
                    user_id=user.id,
                    job_id=job_id,
                    status="in_progress",
                    message=notification_message
                )
            )

            if user.fcm_token:
                FCMService.send_notification(
                    token=user.fcm_token,
                    title="Job Aceito! 🤝",
                    body=notification_message,
                    data={
                        "type": "job_status_change",
                        "job_id": job_id,
                        "status": "in_progress",
                    }
                )
        except Exception as e:
            print(f"Erro ao enviar notificação: {e}")

    @staticmethod
    def notify_new_proposal(
            db: Session,
            client_address: str,
            job_id: str,
            ipfs_hash: str,
            provider_name: str
    ):
        """Notifica cliente que recebeu uma nova proposta"""
        try:
            user = JobNotificationService._get_user_by_wallet_address(db, client_address)

            if not user:
                return

            job_title = JobNotificationService._get_job_title(ipfs_hash)
            notification_message = f"{provider_name} enviou uma proposta para '{job_title}'"

            asyncio.create_task(
                JobNotificationService._send_websocket_update(
                    user_id=user.id,
                    job_id=job_id,
                    status="new_proposal",
                    message=notification_message
                )
            )

            if user.fcm_token:
                FCMService.send_notification(
                    token=user.fcm_token,
                    title="Nova Proposta Recebida! 📩",
                    body=notification_message,
                    data={
                        "type": "job_status_change",
                        "job_id": job_id,
                        "status": "new_proposal",
                    }
                )
        except Exception as e:
            print(f"Erro ao enviar notificação: {e}")

    @staticmethod
    def notify_cancel_proposal(
            db: Session,
            client_address: str,
            job_id: str,
            ipfs_hash: str,
            provider_name: str
    ):
        """Notifica cliente que recebeu uma nova proposta"""
        try:
            user = JobNotificationService._get_user_by_wallet_address(db, client_address)

            if not user:
                return

            job_title = JobNotificationService._get_job_title(ipfs_hash)
            notification_message = f"{provider_name} removeu uma proposta para '{job_title}'"

            asyncio.create_task(
                JobNotificationService._send_websocket_update(
                    user_id=user.id,
                    job_id=job_id,
                    status="proposal_removed",
                    message=notification_message
                )
            )
        except Exception as e:
            print(f"Erro ao enviar notificação: {e}")