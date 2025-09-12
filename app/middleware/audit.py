from fastapi import Request, Response
from typing import Callable
import time
from ..util.logger import AuditLogger


class AuditMiddleware:
    """Middleware para auditar todas as requisições de autenticação"""

    async def __call__(
            self,
            request: Request,
            call_next: Callable,
    ) -> Response:
        # Captura início
        start_time = time.time()

        # Paths que queremos auditar
        audit_paths = ["/auth/login", "/auth/register", "/auth/logout", "/auth/refresh"]

        # Processa request
        response = await call_next(request)

        # Se é path de auth, audita
        if any(path in str(request.url.path) for path in audit_paths):
            process_time = time.time() - start_time

            # Extrai informações
            client_ip = request.client.host if request.client else "unknown"

            # Determina sucesso baseado no status code
            success = 200 <= response.status_code < 300

            # Log de auditoria
            AuditLogger.log_auth_event(
                event_type=request.url.path.split("/")[-1],  # login, register, etc
                user_id=None,  # Seria extraído do response se disponível
                email=None,
                ip_address=client_ip,
                device_id=None,
                success=success,
                details={
                    "method": request.method,
                    "path": str(request.url.path),
                    "status_code": response.status_code,
                    "process_time": f"{process_time:.3f}s",
                    "user_agent": request.headers.get("user-agent", "unknown")
                }
            )

        return response
