# app/utils/responses.py
from typing import Any, Optional, Dict
from pydantic import BaseModel


class APIResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    data: Optional[Any] = None
    errors: Optional[Dict[str, Any]] = None

    @classmethod
    def success_response(cls, data: Any = None, message: str = "Operação realizada com sucesso"):
        return cls(success=True, message=message, data=data)

    @classmethod
    def error_response(cls, message: str, errors: Dict[str, Any] = None):
        return cls(success=False, message=message, errors=errors)