from fastapi import WebSocket, WebSocketDisconnect, Depends, Query
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from ..config.database import get_db, SessionLocal
from ..model.chat_model import ChatMessage
from ..service.chat_service import ChatService
from ..auth.jwt_handler import decode_token
from ..model.user import User
import json
from datetime import datetime
from ..websocket.notifications_handler import notifications_manager


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[Dict]] = {}
        self.user_connections: Dict[str, WebSocket] = {}

    async def connect(
            self,
            websocket: WebSocket,
            room_id: str,
            user_id: str,
            user_name: str
    ):
        await websocket.accept()

        if room_id not in self.active_connections:
            self.active_connections[room_id] = []

        self.active_connections[room_id].append({
            "websocket": websocket,
            "user_id": user_id,
            "user_name": user_name
        })

        self.user_connections[user_id] = websocket

        await self.broadcast_to_room(
            room_id,
            {
                "type": "user_joined",
                "user_id": user_id,
                "user_name": user_name,
                "timestamp": datetime.now().isoformat()
            },
            exclude_user=user_id
        )

    def disconnect(self, room_id: str, user_id: str):
        if room_id in self.active_connections:
            self.active_connections[room_id] = [
                conn for conn in self.active_connections[room_id]
                if conn["user_id"] != user_id
            ]

            if not self.active_connections[room_id]:
                del self.active_connections[room_id]

        if user_id in self.user_connections:
            del self.user_connections[user_id]

    async def broadcast_to_room(
            self,
            room_id: str,
            message: dict,
            exclude_user: Optional[str] = None
    ):
        if room_id in self.active_connections:
            for connection in self.active_connections[room_id]:
                if exclude_user and connection["user_id"] == exclude_user:
                    continue

                try:
                    await connection["websocket"].send_json(message)
                except:
                    pass

    async def send_to_user(self, user_id: str, message: dict):
        if user_id in self.user_connections:
            try:
                await self.user_connections[user_id].send_json(message)
            except:
                pass

    def get_room_users(self, room_id: str) -> List[Dict]:
        if room_id not in self.active_connections:
            return []

        return [
            {
                "user_id": conn["user_id"],
                "user_name": conn["user_name"]
            }
            for conn in self.active_connections[room_id]
        ]


manager = ConnectionManager()


async def get_current_user_ws(
        token: str = Query(...),
        db: Session = Depends(get_db)
) -> Optional[User]:
    payload = decode_token(token)
    if not payload:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    user = db.query(User).filter(User.id == user_id).first()
    return user


async def websocket_chat_endpoint(
        websocket: WebSocket,
        room_id: str,
        token: str = Query(...),
        db: Session = Depends(get_db)
):
    user = await get_current_user_ws(token, db)
    if not user:
        await websocket.close(code=4001, reason="Unauthorized")
        db.close()
        return

    chat_service = ChatService(db)
    rooms = chat_service.get_user_rooms(user.id)

    if room_id not in [r["room_id"] for r in rooms]:
        if not getattr(user, 'is_admin', False):
            await websocket.close(code=4003, reason="Access Denied")
            db.close()
            return

    await manager.connect(websocket, room_id, user.id, user.full_name)

    db.close()

    try:
        await websocket.send_json({
            "type": "welcome",
            "room_id": room_id,
            "user_id": user.id,
            "online_users": manager.get_room_users(room_id)
        })

        db_temp = SessionLocal()
        try:
            temp_service = ChatService(db_temp)
            unread_messages = temp_service.get_unread_messages_status(room_id, user.id)
            if unread_messages:
                await websocket.send_json({
                    "type": "unread_status",
                    "messages": unread_messages
                })
        finally:
            db_temp.close()

        await manager.broadcast_to_room(
            room_id,
            {
                "type": "user_online",
                "user_id": user.id,
                "user_name": user.full_name,
                "timestamp": datetime.now().isoformat()
            },
            exclude_user=user.id
        )

        while True:
            data = await websocket.receive_text()

            if data == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            message_data = json.loads(data)

            db_operation = SessionLocal()
            try:
                chat_service = ChatService(db_operation)

                if message_data["type"] == "message":
                    success, msg, chat_message, receiver_id = chat_service.send_message(
                        room_id=room_id,
                        sender_id=user.id,
                        message=message_data["message"],
                        message_type=message_data.get("message_type", "text"),
                        json_metadata=message_data.get("json_metadata"),
                        reply_to_id=message_data.get("reply_to_id")
                    )

                    if success and chat_message:
                        reply_to_data = None
                        if chat_message.reply_to_id:
                            reply_message = db_operation.query(ChatMessage).filter(
                                ChatMessage.id == chat_message.reply_to_id
                            ).first()

                            if reply_message:
                                reply_sender = db_operation.query(User).filter(
                                    User.id == reply_message.sender_id
                                ).first()

                                reply_to_data = {
                                    'id': reply_message.id,
                                    'message': reply_message.message,
                                    'sender_id': reply_message.sender_id,
                                    'sender_name': reply_sender.full_name if reply_sender else 'Usuário'
                                }

                        await manager.broadcast_to_room(room_id, {
                            "type": "new_message",
                            "message": {
                                "id": chat_message.id,
                                "sender": {
                                    "id": user.id,
                                    "name": user.full_name
                                },
                                "message": chat_message.message,
                                "message_type": chat_message.message_type,
                                "json_metadata": json.loads(
                                    chat_message.json_metadata) if chat_message.json_metadata else None,
                                "created_at": chat_message.created_at.strftime('%d/%m/%Y às %H:%M'),
                                "status": "sent",
                                "reply_to": reply_to_data
                            }
                        })

                        if receiver_id:
                            is_receiver_in_room = any(
                                conn["user_id"] == receiver_id
                                for conn in manager.active_connections.get(room_id, [])
                            )

                            if not is_receiver_in_room:
                                room_data = chat_service.get_room_data_for_notification(room_id, receiver_id)
                                if room_data:
                                    await notifications_manager.send_to_user(receiver_id, {
                                        "type": "room_update",
                                        "data": room_data
                                    })
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": msg
                        })

                elif message_data["type"] == "typing":
                    await manager.broadcast_to_room(
                        room_id,
                        {
                            "type": "typing",
                            "user_id": user.id,
                            "user_name": user.full_name,
                            "is_typing": message_data.get("is_typing", False)
                        },
                        exclude_user=user.id
                    )

                elif message_data["type"] == "read":
                    chat_service._mark_messages_as_read(room_id, user.id)
                    await manager.broadcast_to_room(
                        room_id,
                        {
                            "type": "messages_read",
                            "user_id": user.id,
                            "user_name": user.full_name,
                            "timestamp": datetime.now().isoformat()
                        },
                        exclude_user=user.id
                    )

            finally:
                db_operation.close()

    except WebSocketDisconnect:
        manager.disconnect(room_id, user.id)
        await manager.broadcast_to_room(room_id, {
            "type": "user_left",
            "user_id": user.id,
            "user_name": user.full_name,
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        manager.disconnect(room_id, user.id)