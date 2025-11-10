from sqlalchemy.orm import Session
from ..model.user import User
from ..model.wallet import Wallet
from .fcm_service import FCMService
from ..ipfs.ipfs_service import IPFSService


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

            if not user or not user.fcm_token:
                return

            job_title = JobNotificationService._get_job_title(ipfs_hash)

            FCMService.send_notification(
                token=user.fcm_token,
                title="Proposta Aceita! 🎉",
                body=f"{client_name} aceitou sua proposta para '{job_title}'",
                data={
                    "type": "job_status_change",
                    "job_id": job_id,
                    "status": "accepted",
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

            if not user or not user.fcm_token:
                return

            job_title = JobNotificationService._get_job_title(ipfs_hash)

            FCMService.send_notification(
                token=user.fcm_token,
                title="Proposta Rejeitada",
                body=f"{client_name} rejeitou sua proposta para '{job_title}'",
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

            if not user or not user.fcm_token:
                return

            job_title = JobNotificationService._get_job_title(ipfs_hash)

            FCMService.send_notification(
                token=user.fcm_token,
                title="Trabalho Concluído! ✅",
                body=f"{provider_name} concluiu o trabalho '{job_title}'. Aguardando sua aprovação.",
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

            if not user or not user.fcm_token:
                return

            job_title = JobNotificationService._get_job_title(ipfs_hash)

            stars = "⭐" * rating

            FCMService.send_notification(
                token=user.fcm_token,
                title="Pagamento Liberado! 💰",
                body=f"{client_name} aprovou '{job_title}' - Avaliação: {stars}",
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

            if not user or not user.fcm_token:
                return

            job_title = JobNotificationService._get_job_title(ipfs_hash)

            FCMService.send_notification(
                token=user.fcm_token,
                title="Job Aceito! 🤝",
                body=f"{provider_name} aceitou o trabalho '{job_title}'",
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

            if not user or not user.fcm_token:
                return

            job_title = JobNotificationService._get_job_title(ipfs_hash)

            FCMService.send_notification(
                token=user.fcm_token,
                title="Nova Proposta Recebida! 📩",
                body=f"{provider_name} enviou uma proposta para '{job_title}'",
                data={
                    "type": "job_status_change",
                    "job_id": job_id,
                    "status": "new_proposal",
                }
            )
        except Exception as e:
            print(f"Erro ao enviar notificação: {e}")