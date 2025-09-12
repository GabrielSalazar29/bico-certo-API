# app/utils/exceptions.py
from fastapi import HTTPException, status
from typing import Any, Dict, Optional


class AuthException(HTTPException):
    """Exceção customizada para autenticação"""

    def __init__(
            self,
            detail: str,
            status_code: int = status.HTTP_401_UNAUTHORIZED,
            headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=status_code,
            detail=detail,
            headers=headers or {"WWW-Authenticate": "Bearer"}
        )


class ValidationException(HTTPException):
    """Exceção para validação de dados"""

    def __init__(self, detail: str, field: str = None):
        error_detail = {
            "message": detail,
            "field": field
        } if field else detail

        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=error_detail
        )


class RateLimitException(HTTPException):
    """Exceção para rate limiting"""

    def __init__(self, retry_after: int):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Muitas tentativas. Tente novamente em {retry_after} segundos",
            headers={"Retry-After": str(retry_after)}
        )