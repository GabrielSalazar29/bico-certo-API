from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .util.responses import APIResponse
from .config.settings import settings
from .model import user, device, session
from .util.logger import logger
from .config.database import engine
from .api import auth, job_manager
from datetime import datetime, UTC


# Criar tabelas
user.Base.metadata.create_all(bind=engine)
device.Base.metadata.create_all(bind=engine)
session.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# @app.middleware("http")
# async def audit_middleware(request: Request, call_next):
#     """Middleware de auditoria para todas as requisições"""
#     middleware = AuditMiddleware()
#     return await middleware(request, call_next)


@app.middleware("http")
async def error_handler(request: Request, call_next):
    """Tratamento global de erros"""
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        logger.error(f"Unhandled error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content=APIResponse.error_response(
                message="Erro interno do servidor"
            ).dict()
        )


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Adiciona headers de segurança"""
    response = await call_next(request)

    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    # Rate limit headers (se disponível)
    if hasattr(request.state, "rate_limit_remaining"):
        response.headers["X-RateLimit-Remaining"] = str(request.state.rate_limit_remaining)
        response.headers["X-RateLimit-Limit"] = str(request.state.rate_limit_limit)

    return response


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Adiciona ID único para cada request"""
    import uuid
    request_id = str(uuid.uuid4())

    # Adiciona ao request
    request.state.request_id = request_id

    # Processa
    response = await call_next(request)

    # Adiciona ao response
    response.headers["X-Request-ID"] = request_id

    return response


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log de todas as requisições"""
    import time

    start_time = time.time()

    # Log request
    logger.info(f"Request: {request.method} {request.url.path}")

    # Process
    response = await call_next(request)

    # Calculate process time
    process_time = time.time() - start_time

    # Log response
    logger.info(
        f"Response: {response.status_code} - "
        f"Process time: {process_time:.3f}s - "
        f"Path: {request.url.path}"
    )

    return response


# Incluir rotas
app.include_router(auth.router)
app.include_router(job_manager.router)


# Root endpoint
@app.get("/", response_model=APIResponse)
async def root():
    return APIResponse.success_response(
        data={
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "status": "running"
        },
        message="API Bico Certo"
    )


# Health check
@app.get("/health", response_model=APIResponse)
async def health_check():
    return APIResponse.success_response(
        data={
            "status": "healthy",
            "timestamp": datetime.now(UTC).isoformat()
        },
        message="Sistema operacional"
    )


# Startup event
@app.on_event("startup")
async def startup_event():
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    # Verificar conexões
    try:
        # # Test database
        # from .config.database import SessionLocal
        # db = SessionLocal()
        # db.execute("SELECT 1")
        # db.close()
        # logger.info("Database connection: OK")

        # Test Redis
        from .config.redis_config import get_redis
        redis = get_redis()
        redis.ping()
        logger.info("Redis connection: OK")

    except Exception as e:
        logger.error(f"Startup check failed: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info(f"Shutting down {settings.APP_NAME}")
