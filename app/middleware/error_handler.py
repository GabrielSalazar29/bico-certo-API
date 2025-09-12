from fastapi import Request, Response
from fastapi.responses import JSONResponse
from ..util.exceptions import AuthException, ValidationException, RateLimitException
from ..util.responses import APIResponse
import traceback


class ErrorHandlerMiddleware:
    """Middleware global para tratamento de erros"""

    async def __call__(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response

        except AuthException as e:
            # Erro de autenticação
            return JSONResponse(
                status_code=e.status_code,
                content=APIResponse.error_response(
                    message=e.detail,
                    errors={"type": "authentication_error"}
                ).dict(),
                headers=e.headers
            )

        except ValidationException as e:
            # Erro de validação
            return JSONResponse(
                status_code=e.status_code,
                content=APIResponse.error_response(
                    message=e.detail.get("message") if isinstance(e.detail, dict) else e.detail,
                    errors={"field": e.detail.get("field") if isinstance(e.detail, dict) else None}
                ).dict()
            )

        except RateLimitException as e:
            # Rate limit excedido
            return JSONResponse(
                status_code=e.status_code,
                content=APIResponse.error_response(
                    message=e.detail,
                    errors={"retry_after": e.headers.get("Retry-After")}
                ).dict(),
                headers=e.headers
            )

        except Exception as e:
            # Erro genérico
            print(f"Unhandled error: {traceback.format_exc()}")

            return JSONResponse(
                status_code=500,
                content=APIResponse.error_response(
                    message="Erro interno do servidor",
                    errors={"detail": str(e) if request.app.debug else None}
                ).dict()
            )
