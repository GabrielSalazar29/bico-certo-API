# app/service/chat_service.py
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime

from app.service.ipfs_service import IPFSService
from ..model.bico_certo_main import BicoCerto
from ..model.chat_model import ChatRoom, ChatMessage, MessageStatus, ChatNotification
from ..model.user import User
from ..config.settings import fuso_local
import json


class ChatService:
    """Serviço para gerenciar chats"""

    def __init__(self, db: Session):
        self.db = db

    def create_or_get_room(
            self,
            job_id: str,
            client_id: str,
            provider_id: Optional[str] = None
    ) -> Tuple[bool, str, Optional[ChatRoom]]:
        """
        Cria ou recupera uma sala de chat para um job
        """

        # Verificar se já existe sala para este job
        existing_room = self.db.query(ChatRoom).filter(
            ChatRoom.job_id == job_id,
            ChatRoom.client_id == client_id
        )

        if provider_id:
            existing_room = existing_room.filter(ChatRoom.provider_id == provider_id)

        existing_room = existing_room.first()

        if existing_room:
            return True, "Sala existente recuperada", existing_room

        # Criar nova sala
        try:
            room = ChatRoom(
                job_id=job_id,
                client_id=client_id,
                provider_id=provider_id,
                is_active=True
            )

            self.db.add(room)
            self.db.commit()
            self.db.refresh(room)

            return True, "Sala criada com sucesso", room

        except Exception as e:
            self.db.rollback()
            return False, f"Erro ao criar sala: {str(e)}", None

    def get_user_rooms(
            self,
            user_id: str,
            only_active: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Retorna todas as salas de chat de um usuário
        """

        bico_certo = BicoCerto()
        ipfs_service = IPFSService()

        rooms_query = self.db.query(ChatRoom).filter(
            (ChatRoom.client_id == user_id) | (ChatRoom.provider_id == user_id)
        )

        if only_active:
            rooms_query = rooms_query.filter(ChatRoom.is_active == True)

        rooms = rooms_query.options(
            joinedload(ChatRoom.provider),
        ).order_by(ChatRoom.last_message_at.desc()).all()

        result = []
        for room in rooms:
            # Determinar papel do usuário
            is_client = room.client_id == user_id

            # Buscar última mensagem
            last_message = self.db.query(ChatMessage).filter(
                ChatMessage.room_id == room.id
            ).options(joinedload(ChatMessage.sender)).order_by(ChatMessage.created_at.desc()).first()

            # Contar mensagens não lidas
            unread_count = int(room.unread_client if is_client else room.unread_provider)

            job_data = bico_certo.get_job(bytes.fromhex(room.job_id)).to_dict()

            success, message, metadata = ipfs_service.get_job_data(job_data['ipfs_hash'])

            # Buscar dados do outro participante
            other_user_id = room.provider_id if room.client_id == user_id else room.client_id
            other_user = self.db.query(User).filter(User.id == other_user_id).first()

            result.append({
                "room_id": room.id,
                "job_id": room.job_id,
                "job_title": metadata["data"]["title"],
                "is_client": is_client,
                "is_active": room.is_active,
                "other_user": {
                    "id": other_user.id if other_user else None,
                    "name": other_user.full_name if other_user else "Usuário",
                    "email": other_user.email if other_user else None
                },
                "last_message": {
                    "id": last_message.id if last_message else None,
                    "message": last_message.message[:100] if last_message else None,
                    "full_name": last_message.sender.full_name if last_message else None,
                    "created_at": last_message.created_at.isoformat() if last_message else None
                } if last_message else None,
                "unread_count": unread_count,
                "total_messages": int(room.total_messages),
                "created_at": room.created_at.isoformat()
            })

        return result

    def get_room_messages(
            self,
            room_id: str,
            user_id: str,
            limit: int = 50,
            offset: int = 0
    ) -> Tuple[bool, str, Optional[List[Dict]]]:
        """
        Recupera mensagens de uma sala
        """

        # Verificar se sala existe
        room = self.db.query(ChatRoom).filter(ChatRoom.id == room_id).first()

        if not room:
            return False, "Sala não encontrada", None

        # Verificar se usuário tem acesso
        if user_id not in [room.client_id, room.provider_id]:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user or not getattr(user, 'is_admin', False):
                return False, "Acesso negado", None

        # Buscar mensagens
        messages = self.db.query(ChatMessage).filter(
            ChatMessage.room_id == room_id
        ).order_by(
            ChatMessage.created_at.desc()
        ).limit(limit).offset(offset).all()

        # Marcar como lidas
        self._mark_messages_as_read(room_id, user_id)

        # Formatar mensagens
        result = []
        for msg in reversed(messages):
            sender = self.db.query(User).filter(User.id == msg.sender_id).first()

            message_data = {
                "id": msg.id,
                "sender": {
                    "id": sender.id,
                    "name": sender.full_name,
                    "is_sender": sender.id == user_id
                },
                "message": msg.message,
                "message_type": msg.message_type,
                "json_metadata": json.loads(msg.json_metadata) if msg.json_metadata else None,
                "status": msg.status.value,
                "created_at": msg.created_at.strftime('%d/%m/%Y às %H:%M'),
                "delivered_at": msg.delivered_at.isoformat() if msg.delivered_at else None,
                "read_at": msg.read_at.strftime('%d/%m/%Y às %H:%M') if msg.read_at else None
            }

            # ← ADICIONE: Buscar mensagem original se for resposta
            if msg.reply_to_id:
                reply = self.db.query(ChatMessage).filter(
                    ChatMessage.id == msg.reply_to_id
                ).first()

                if reply:
                    reply_sender = self.db.query(User).filter(
                        User.id == reply.sender_id
                    ).first()

                    message_data["reply_to"] = {
                        "id": reply.id,
                        "message": reply.message[:100],  # Limitar tamanho
                        "sender_id": reply.sender_id,
                        "sender_name": reply_sender.full_name if reply_sender else "Usuário"
                    }

            result.append(message_data)

        return True, "Mensagens recuperadas", result

    def _mark_messages_as_read(self, room_id: str, user_id: str):
        """
        Marca mensagens como lidas
        """

        room = self.db.query(ChatRoom).filter(ChatRoom.id == room_id).first()

        if not room:
            return

        # Determinar se é cliente ou provider
        is_client = user_id == room.client_id

        # Atualizar mensagens não lidas
        unread_messages = self.db.query(ChatMessage).filter(
            ChatMessage.room_id == room_id,
            ChatMessage.sender_id != user_id,
            ChatMessage.status != MessageStatus.READ
        ).all()

        for msg in unread_messages:
            msg.status = MessageStatus.READ
            msg.read_at = datetime.now(fuso_local)

        # Resetar contador de não lidas
        if is_client:
            room.unread_client = "0"
        else:
            room.unread_provider = "0"

        # Marcar notificações como lidas
        self.db.query(ChatNotification).filter(
            ChatNotification.room_id == room_id,
            ChatNotification.user_id == user_id,
            ChatNotification.is_read == False
        ).update({
            "is_read": True,
            "read_at": datetime.now(fuso_local)
        })

        self.db.commit()

    def get_room_data_for_notification(
            self,
            room_id: str,
            user_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retorna dados da sala formatados para notificação WebSocket
        """

        room = self.db.query(ChatRoom).filter(ChatRoom.id == room_id).first()
        if not room:
            return None

        # Determinar papel do usuário
        is_client = room.client_id == user_id
        other_user_id = room.provider_id if is_client else room.client_id

        # Buscar outro usuário
        other_user = self.db.query(User).filter(User.id == other_user_id).first() if other_user_id else None

        # Buscar última mensagem
        last_message = self.db.query(ChatMessage).filter(
            ChatMessage.room_id == room.id
        ).order_by(ChatMessage.created_at.desc()).first()

        last_sender = self.db.query(User).filter(
            User.id == last_message.sender_id).first() if last_message.sender_id else None
        # Contar mensagens não lidas
        unread_count = int(room.unread_client if is_client else room.unread_provider)

        # Buscar dados do job
        bico_certo = BicoCerto()
        ipfs_service = IPFSService()

        try:
            job_data = bico_certo.get_job(bytes.fromhex(room.job_id)).to_dict()
            success, message, metadata = ipfs_service.get_job_data(job_data['ipfs_hash'])
            job_title = metadata.get("data", {}).get("title", "Trabalho sem título")
        except:
            job_title = "Trabalho sem título"

        return {
            "room_id": room.id,
            "job_id": room.job_id,
            "job_title": job_title,
            "is_client": is_client,
            "is_active": room.is_active,
            "other_user": {
                "id": other_user.id if other_user else None,
                "name": other_user.full_name if other_user else "Aguardando provider",
                "email": other_user.email if other_user else None
            },
            "last_message": {
                "id": last_message.id if last_message else None,
                "message": last_message.message[:100] if last_message else None,
                "full_name": last_sender.full_name if last_message else None,
                "created_at": last_message.created_at.isoformat() if last_message else None
            } if last_message else None,
            "unread_count": unread_count,
            "total_messages": int(room.total_messages),
            "created_at": room.created_at.isoformat()
        }

    def send_message(
            self,
            room_id: str,
            sender_id: str,
            message: str,
            message_type: str = "text",
            json_metadata: Optional[Dict] = None,
            reply_to_id: Optional[str] = None
    ) -> Tuple[bool, str, Optional[ChatMessage], Optional[str]]:
        """
        Envia uma mensagem
        Retorna: (success, message, chat_message, receiver_id)
        """

        # Verificar se sala existe
        room = self.db.query(ChatRoom).filter(ChatRoom.id == room_id).first()

        if not room:
            return False, "Sala não encontrada", None, None

        # Verificar se usuário tem acesso
        if sender_id not in [room.client_id, room.provider_id]:
            sender = self.db.query(User).filter(User.id == sender_id).first()
            if not sender or not getattr(sender, 'is_admin', False):
                return False, "Acesso negado", None, None

        # Verificar se está respondendo a uma mensagem válida
        reply_to_message = None
        if reply_to_id:
            reply_to_message = self.db.query(ChatMessage).filter(
                ChatMessage.id == reply_to_id,
                ChatMessage.room_id == room_id
            ).first()

            if not reply_to_message:
                return False, "Mensagem de resposta não encontrada", None, None

        try:
            # Criar mensagem
            chat_message = ChatMessage(
                room_id=room_id,
                sender_id=sender_id,
                message=message,
                message_type=message_type,
                json_metadata=json.dumps(json_metadata) if json_metadata else None,
                reply_to_id=reply_to_id,
                status=MessageStatus.SENT
            )

            self.db.add(chat_message)

            # Atualizar sala
            room.last_message_at = datetime.now(fuso_local)
            room.total_messages = str(int(room.total_messages) + 1)

            self.db.flush()

            # Incrementar contador de não lidas para o outro usuário
            if sender_id == room.client_id:
                room.unread_provider = str(int(room.unread_provider) + 1)
                receiver_id = room.provider_id
            else:
                room.unread_client = str(int(room.unread_client) + 1)
                receiver_id = room.client_id

            # Criar notificação se houver receiver
            if receiver_id:
                notification = ChatNotification(
                    user_id=receiver_id,
                    room_id=room_id,
                    message_id=chat_message.id
                )
                self.db.add(notification)

            self.db.commit()
            self.db.refresh(chat_message)

            # NOVO: Adicionar dados da mensagem de resposta ao objeto
            if reply_to_message:
                # Buscar dados do remetente da mensagem original
                reply_sender = self.db.query(User).filter(
                    User.id == reply_to_message.sender_id
                ).first()

                # Adicionar atributo temporário com dados da resposta
                chat_message.reply_to_data = {
                    'id': reply_to_message.id,
                    'sender_name': reply_sender.full_name if reply_sender else 'Usuário',
                    'message': reply_to_message.message
                }

            return True, "Mensagem enviada", chat_message, receiver_id

        except Exception as e:
            self.db.rollback()
            return False, f"Erro ao enviar mensagem: {str(e)}", None, None

    def get_unread_messages_status(
            self,
            room_id: str,
            user_id: str
    ) -> List[Dict[str, Any]]:
        """
        Retorna status de leitura das mensagens
        Usado para sincronizar status quando usuário entra no chat
        """

        room = self.db.query(ChatRoom).filter(ChatRoom.id == room_id).first()

        if not room:
            return []

        # Determinar quem é o outro usuário
        other_user_id = room.provider_id if user_id == room.client_id else room.client_id

        if not other_user_id:
            return []

        # Buscar mensagens do usuário atual que foram lidas pelo outro
        read_messages = self.db.query(ChatMessage).filter(
            ChatMessage.room_id == room_id,
            ChatMessage.sender_id == user_id,
            ChatMessage.status == MessageStatus.READ
        ).all()

        return [
            {
                "message_id": msg.id,
                "read_at": msg.read_at.isoformat() if msg.read_at else None,
                "read_by": other_user_id
            }
            for msg in read_messages
        ]