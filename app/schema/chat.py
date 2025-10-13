from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


class CreateChatRoomRequest(BaseModel):
    """Request para criar sala de chat"""
    job_id: str = Field(..., description="ID do job na blockchain")
    client_id: Optional[str] = Field(None, description="ID do cliente (se admin criando)")
    provider_id: Optional[str] = Field(None, description="ID do provider")


class SendMessageRequest(BaseModel):
    """Request para enviar mensagem"""
    room_id: str = Field(..., description="ID da sala")
    message: str = Field(..., min_length=1, max_length=5000)
    message_type: str = Field(default="text", description="text, image, file, proposal_update")
    json_metadata: Optional[Dict[str, Any]] = Field(None)
    reply_to_id: Optional[str] = Field(None, description="ID da mensagem sendo respondida")
