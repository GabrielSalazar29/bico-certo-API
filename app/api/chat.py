import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from starlette.websockets import WebSocket

from ..config.database import get_db
from ..config.settings import fuso_local
from ..model.chat_model import ChatNotification, ChatMessage, ChatRoom
from ..service.chat_service import ChatService
from ..auth.dependencies import get_current_user
from ..model.user import User
from ..util.responses import APIResponse
from ..schema.chat import (
    CreateChatRoomRequest,
    SendMessageRequest
)
from ..websocket import chat_handler

router = APIRouter(prefix="/chat", tags=["Chat"])

@router.post("/room/create", response_model=APIResponse)
async def create_chat_room(
        request: CreateChatRoomRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    service = ChatService(db)

    success, message, room = service.create_or_get_room(
        job_id=request.job_id,
        client_id=request.client_id or current_user.id,
        provider_id=request.provider_id
    )

    if not success:
        raise HTTPException(status_code=400, detail=message)

    return APIResponse.success_response(
        data={
            "room_id": room.id,
            "job_id": room.job_id,
            "client_id": room.client_id,
            "provider_id": room.provider_id,
            "is_active": room.is_active,
            "created_at": room.created_at.isoformat()
        },
        message=message
    )


@router.get("/rooms", response_model=APIResponse)
async def get_user_chat_rooms(
        only_active: bool = Query(True),
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    service = ChatService(db)
    rooms = service.get_user_rooms(current_user.id, only_active)

    return APIResponse.success_response(
        data={
            "rooms": rooms,
            "total": len(rooms)
        },
        message=f"Encontradas {len(rooms)} salas de chat"
    )


@router.get("/room/{room_id}/messages", response_model=APIResponse)
async def get_room_messages(
    room_id: str,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    service = ChatService(db)

    success, message, messages = service.get_room_messages(
        room_id=room_id,
        user_id=current_user.id,
        limit=limit,
        offset=offset
    )

    if not success:
        raise HTTPException(status_code=403, detail=message)

    return APIResponse.success_response(
        data={
            "room_id": room_id,
            "messages": messages,
            "total": len(messages),
            "limit": limit,
            "offset": offset
        },
        message="Mensagens recuperadas com sucesso"
    )

@router.get("/room/{room_id}/info", response_model=APIResponse)
async def get_room_info(
        room_id: str,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Retorna informações básicas de uma sala"""
    try:
        room = db.query(ChatRoom).filter(ChatRoom.id == room_id).first()

        if not room:
            raise HTTPException(status_code=404, detail="Sala não encontrada")

        # Verificar se usuário tem acesso
        if room.client_id != current_user.id and room.provider_id != current_user.id:
            raise HTTPException(status_code=403, detail="Sem permissão para acessar esta sala")

        # Buscar título do job no IPFS
        job_title = 'Chat'
        try:
            from ..model.bico_certo_main import BicoCerto
            from app.service.ipfs_service import IPFSService

            bico_certo = BicoCerto()
            job_obj = bico_certo.get_job(bytes.fromhex(room.job_id))

            if hasattr(job_obj, 'ipfs_hash') and job_obj.ipfs_hash:
                ipfs_service = IPFSService()
                success, _, ipfs_data = ipfs_service.get_job_data(job_obj.ipfs_hash)

                if success and ipfs_data:
                    job_title = ipfs_data.get('data', {}).get('title', 'Chat')
                    if job_title:
                        job_title = job_title.title()
        except Exception as e:
            print(f"Erro ao buscar título do IPFS: {e}")

        # Buscar dados do outro participante
        other_user_id = room.provider_id if room.client_id == current_user.id else room.client_id
        other_user = db.query(User).filter(User.id == other_user_id).first()

        return APIResponse.success_response(
            data={
                "room_id": room.id,
                "job_id": room.job_id,
                "job_title": job_title,
                "is_active": room.is_active,
                "other_user": {
                    "id": other_user.id if other_user else None,
                    "name": other_user.full_name if other_user else "Usuário",
                    "email": other_user.email if other_user else None
                } if other_user else None
            },
            message="Informações da sala recuperadas"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar informações: {str(e)}")


@router.post("/send", response_model=APIResponse)
async def send_message(
        request: SendMessageRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    service = ChatService(db)

    success, message, chat_message, receiver_id = service.send_message(
        room_id=request.room_id,
        sender_id=current_user.id,
        message=request.message,
        message_type=request.message_type,
        json_metadata=request.json_metadata,
        reply_to_id=request.reply_to_id
    )

    if not success:
        raise HTTPException(status_code=400, detail=message)

    if receiver_id:
        receiver = db.query(User).filter(User.id == receiver_id).first()

        if receiver and receiver.fcm_token:
            from ..service.fcm_service import FCMService

            FCMService.send_notification(
                token=receiver.fcm_token,
                title=f"Nova mensagem de {current_user.full_name}",
                body=request.message[:100],
                data={
                    "type": "chat_message",
                    "room_id": request.room_id,
                }
            )

    from ..websocket.notifications_handler import notifications_manager
    import asyncio

    # Notificar receptor via WebSocket de notificações
    if receiver_id:
        room_data = service.get_room_data_for_notification(
            room_id=request.room_id,
            user_id=receiver_id
        )

        if room_data:
            asyncio.create_task(
                notifications_manager.send_to_user(receiver_id, {
                    "type": "room_update",
                    "data": room_data
                })
            )

    # Buscar dados da mensagem de resposta se houver
    reply_to_data = None
    if chat_message.reply_to_id:
        reply_message = db.query(ChatMessage).filter(
            ChatMessage.id == chat_message.reply_to_id
        ).first()

        if reply_message:
            reply_sender = db.query(User).filter(
                User.id == reply_message.sender_id
            ).first()

            reply_to_data = {
                'id': reply_message.id,
                'message': reply_message.message,
                'sender_id': reply_message.sender_id,
                'sender_name': reply_sender.full_name if reply_sender else 'Usuário'
            }

    # Notificar via WebSocket do chat
    from ..websocket.chat_handler import manager

    asyncio.create_task(
        manager.broadcast_to_room(request.room_id, {
            "type": "new_message",
            "message": {
                "id": chat_message.id,
                "sender": {
                    "id": current_user.id,
                    "name": current_user.full_name
                },
                "message": chat_message.message,
                "message_type": chat_message.message_type,
                "json_metadata": json.loads(chat_message.json_metadata) if chat_message.json_metadata else None,
                "created_at": chat_message.created_at.strftime('%d/%m/%Y às %H:%M'),
                "is_edited": False,
                "status": "sent",
                "reply_to": reply_to_data
            }
        })
    )

    return APIResponse.success_response(
        data={
            "message_id": chat_message.id,
            "status": chat_message.status.value,
            "created_at": chat_message.created_at.isoformat()
        },
        message="Mensagem enviada com sucesso"
    )


@router.get("/notifications", response_model=APIResponse)
async def get_chat_notifications(
        unread_only: bool = Query(True),
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    query = db.query(ChatNotification).filter(
        ChatNotification.user_id == current_user.id
    )

    if unread_only:
        query = query.filter(ChatNotification.is_read == False)

    notifications = query.order_by(ChatNotification.created_at.desc()).limit(50).all()

    result = []
    for notif in notifications:
        message = db.query(ChatMessage).filter(
            ChatMessage.id == notif.message_id
        ).first()

        if message:
            sender = db.query(User).filter(
                User.id == message.sender_id
            ).first()

            room = db.query(ChatRoom).filter(
                ChatRoom.id == notif.room_id
            ).first()

            message_preview = message.message
            if len(message_preview) > 100:
                message_preview = message_preview[:100] + "..."

            result.append({
                "id": notif.id,
                "room_id": notif.room_id,
                "job_id": room.job_id if room else None,
                "sender": {
                    "id": sender.id if sender else None,
                    "name": sender.full_name if sender else "Usuário desconhecido",
                    "email": sender.email if sender else None
                },
                "message": {
                    "id": message.id,
                    "content": message_preview,
                    "type": message.message_type,
                    "full_content": message.message,
                    "created_at": message.created_at.isoformat()
                },
                "is_read": notif.is_read,
                "created_at": notif.created_at.isoformat()
            })
        else:
            result.append({
                "id": notif.id,
                "room_id": notif.room_id,
                "job_id": None,
                "sender": None,
                "message": {
                    "id": notif.message_id,
                    "content": "[Mensagem não disponível]",
                    "type": "deleted",
                    "full_content": None,
                    "created_at": None
                },
                "is_read": notif.is_read,
                "created_at": notif.created_at.isoformat()
            })

    total_unread = db.query(ChatNotification).filter(
        ChatNotification.user_id == current_user.id,
        ChatNotification.is_read == False
    ).count()

    return APIResponse.success_response(
        data={
            "notifications": result,
            "unread_count": total_unread,
            "returned_count": len(result)
        },
        message=f"Você tem {total_unread} notificações não lidas"
    )


@router.put("/notification/{notification_id}/read", response_model=APIResponse)
async def mark_notification_as_read(
        notification_id: str,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    notification = db.query(ChatNotification).filter(
        ChatNotification.id == notification_id,
        ChatNotification.user_id == current_user.id
    ).first()

    if not notification:
        raise HTTPException(
            status_code=404,
            detail="Notificação não encontrada"
        )

    notification.is_read = True
    notification.read_at = datetime.now(fuso_local)

    db.commit()

    return APIResponse.success_response(
        message="Notificação marcada como lida"
    )


@router.put("/notifications/read-all", response_model=APIResponse)
async def mark_all_notifications_as_read(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    updated_count = db.query(ChatNotification).filter(
        ChatNotification.user_id == current_user.id,
        ChatNotification.is_read == False
    ).update({
        "is_read": True,
        "read_at": datetime.now(fuso_local)
    })

    db.commit()

    return APIResponse.success_response(
        data={"updated_count": updated_count},
        message=f"{updated_count} notificações marcadas como lidas"
    )


@router.post("/room/{room_id}/mark-read", response_model=APIResponse)
async def mark_room_as_read(
    room_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    service = ChatService(db)
    service._mark_messages_as_read(room_id, current_user.id)

    return APIResponse.success_response(
        message="Mensagens marcadas como lidas"
    )


@router.websocket("/ws/notifications")
async def websocket_notifications_endpoint(
        websocket: WebSocket,
        token: str = Query(...),
        db: Session = Depends(get_db)
):
    from ..auth.jwt_handler import decode_token
    from ..websocket.notifications_handler import notifications_manager
    from ..config.settings import fuso_local

    try:
        payload = decode_token(token)

        if not payload:
            await websocket.close(code=4001, reason="Invalid token")
            return

        user_id = payload.get("sub")

        if not user_id:
            await websocket.close(code=4001, reason="No user_id in token")
            return

        await notifications_manager.connect(user_id, websocket)

        await websocket.send_json({
            "type": "connected",
            "user_id": user_id,
            "timestamp": datetime.now(fuso_local).isoformat()
        })

        # Loop de heartbeat
        while True:
            data = await websocket.receive_text()

            if data == "ping":
                await websocket.send_json({"type": "pong"})

    except Exception as e:
        try:
            await websocket.close(code=1011, reason=f"Error: {str(e)}")
        except:
            pass
        notifications_manager.disconnect(user_id if 'user_id' in locals() else None, websocket)


@router.websocket("/ws/{room_id}")
async def websocket_endpoint(
        websocket: WebSocket,
        room_id: str,
        token: str,
        db: Session = Depends(get_db)
):
    await chat_handler.websocket_chat_endpoint(websocket, room_id, token, db)


@router.post("/fcm-token/update", response_model=APIResponse)
async def update_fcm_token(
        token: str,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    current_user.fcm_token = token
    db.commit()

    return APIResponse.success_response(
        message="Token FCM atualizado com sucesso"
    )

@router.delete("/fcm-token/remove", response_model=APIResponse)
async def remove_fcm_token(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Remove o FCM token do usuário (usado no logout)"""
    current_user.fcm_token = None
    db.commit()

    return APIResponse.success_response(
        message="Token FCM removido com sucesso"
    )