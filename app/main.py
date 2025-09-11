from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config.settings import settings

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


@app.get("/")
def read_root():
    return {"message": "Bico Certo API", "version": settings.APP_VERSION}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


from .api import auth
from .controller import job_controller
from .config.database import engine
from .model import user as user_model

# Criar tabelas
user_model.Base.metadata.create_all(bind=engine)

# Incluir rotas
app.include_router(auth.router)
app.include_router(job_controller.router)

