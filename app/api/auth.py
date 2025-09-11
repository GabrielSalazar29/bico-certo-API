# app/api/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..config.database import get_db
from ..model.user import User
from ..schema.user import UserCreate, UserResponse
from ..util.security import hash_password
from ..schema.auth import LoginRequest, RefreshRequest, TokenResponse
from ..util.security import verify_password
from ..auth.jwt_handler import create_access_token
from ..auth.dependencies import get_current_user
from ..model.user import RefreshToken
from ..auth.jwt_handler import create_tokens
from datetime import datetime, UTC


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    # Verificar se email já existe
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email já cadastrado"
        )

    # Criar novo usuário
    user = User(
        email=user_data.email,
        full_name=user_data.full_name,
        password_hash=hash_password(user_data.password)
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


@router.post("/login", response_model=TokenResponse)
def login(credentials: LoginRequest, db: Session = Depends(get_db)):
    # Buscar usuário
    user = db.query(User).filter(User.email == credentials.email).first()

    # Verificar se existe e senha está correta
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos"
        )

    # Verificar se está ativo
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário inativo"
        )

    # Criar tokens
    tokens = create_tokens(user.id, user.email)

    # Salvar refresh token no banco
    refresh_token = RefreshToken(
        user_id=user.id,
        token=tokens["refresh_token"],
        expires_at=tokens["refresh_expires_at"]
    )
    db.add(refresh_token)
    db.commit()

    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"]
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(request: RefreshRequest, db: Session = Depends(get_db)):
    # Buscar refresh token
    stored_token = db.query(RefreshToken).filter(
        RefreshToken.token == request.refresh_token,
        RefreshToken.revoked == False
    ).first()

    if not stored_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido"
        )

    # Verificar se expirou
    if stored_token.expires_at.replace(tzinfo=UTC) < datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expirado"
        )

    # Revogar token antigo
    stored_token.revoked = True

    # Criar novos tokens
    tokens = create_tokens(stored_token.user_id, stored_token.user.email)

    # Salvar novo refresh token
    new_refresh_token = RefreshToken(
        user_id=stored_token.user_id,
        token=tokens["refresh_token"],
        expires_at=tokens["refresh_expires_at"]
    )
    db.add(new_refresh_token)
    db.commit()

    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"]
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
