from fastapi import WebSocket
from typing import Dict, Set
import logging

logger = logging.getLogger(__name__)


class NotificationsManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        """Conecta um usuário ao sistema de notificações"""

        await websocket.accept()

        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()

        self.active_connections[user_id].add(websocket)

    def disconnect(self, user_id: str, websocket: WebSocket):
        """Desconecta um usuário"""
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)

            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

            logger.info(f"User {user_id} disconnected from notifications")

    async def send_to_user(self, user_id: str, message: dict):
        """Envia mensagem para todas as conexões de um usuário"""
        if user_id not in self.active_connections:
            return

        disconnected = set()

        for connection in self.active_connections[user_id]:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to user {user_id}: {e}")
                disconnected.add(connection)

        # Remove conexões mortas
        for conn in disconnected:
            self.active_connections[user_id].discard(conn)


# Instância global
notifications_manager = NotificationsManager()
