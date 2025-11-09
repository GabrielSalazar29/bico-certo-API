import firebase_admin
from firebase_admin import credentials, messaging
import logging

logger = logging.getLogger(__name__)


class FCMService:
    _initialized = False

    @classmethod
    def initialize(cls, service_account_path: str):
        """Inicializar FCM com credenciais"""
        if not cls._initialized:
            try:
                cred = credentials.Certificate(service_account_path)
                firebase_admin.initialize_app(cred)
                cls._initialized = True
                logger.info("FCM inicializado com sucesso")
            except Exception as e:
                logger.error(f"Erro ao inicializar FCM: {e}")

    @staticmethod
    def send_notification(
            token: str,
            title: str,
            body: str,
            data: dict = None
    ) -> bool:
        """Enviar notificação push"""
        try:
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                data=data or {},
                token=token,
                android=messaging.AndroidConfig(
                    priority='high',
                    notification=messaging.AndroidNotification(
                        sound='default',
                        channel_id='chat_messages'
                    )
                )
            )

            response = messaging.send(message)
            logger.info(f"Notificação enviada: {response}")
            return True

        except Exception as e:
            logger.error(f"Erro ao enviar notificação: {e}")
            return False