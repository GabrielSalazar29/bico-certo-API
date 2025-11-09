import os
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .api import auth, job_manager, two_factor, password_recovery, wallet, dashboard, chat
from .config.database import engine, Base
from .config.settings import fuso_local
from .config.settings import settings
from .service.fcm_service import FCMService

from .util.responses import APIResponse

# Criar tabelas
Base.metadata.create_all(bind=engine)

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


# Incluir rotas
app.include_router(auth.router)
app.include_router(two_factor.router)
app.include_router(password_recovery.router)
app.include_router(wallet.router)
app.include_router(job_manager.router)
# app.include_router(payment_gateway.router)
app.include_router(chat.router)
app.include_router(dashboard.router)


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
            "timestamp": datetime.now(fuso_local).isoformat()
        },
        message="Sistema operacional"
    )

@app.on_event("startup")
async def startup_event():
    credentials_path = os.path.join(
        os.path.dirname(__file__),
        'firebase-credentials.json'
    )

    if os.path.exists(credentials_path):
        FCMService.initialize(credentials_path)
        print("✅ Firebase inicializado com sucesso")
    else:
        print(f"❌ Arquivo de credenciais não encontrado: {credentials_path}")