from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Any

from app.config.database import get_db
from app.auth.dependencies import get_current_user 
from app.model.user import User
from app.schema.user import UserResponse as UserRead, UserUpdate 
from app.service.profile_service import ProfileService 
from app.util.responses import APIResponse
from app.util.exceptions import ValidationException


router = APIRouter(prefix="/perfil", tags=["Perfil"])

profile_service = ProfileService() 

@router.get("/me", response_model=APIResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Para buscar a reputação, o usuário PRECISA ter uma wallet
    user_address = current_user.wallet.address if current_user.wallet else None
    
    # Busca a reputação na blockchain
    reputation_data = profile_service.get_reputation_summary(
        db_session=db,
        user_address=user_address
    )

    # Converte o modelo SQLAlchemy para o schema de resposta
    user_data = UserRead.model_validate(current_user).model_dump()
    
    return APIResponse.success_response(
        data={
            "profile": user_data,
            "reputation": reputation_data
        },
        message="Dados do perfil recuperados com sucesso"
    )

@router.patch("/me", response_model=APIResponse)
async def update_my_profile(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        updated_user = profile_service.update_user_profile(
            db_session=db,
            user=current_user,
            user_update=user_update
        )
        
        # Busca a reputação atualizada 
        user_address = updated_user.wallet.address if updated_user.wallet else None
        reputation_data = profile_service.get_reputation_summary(
            db_session=db,
            user_address=user_address
        )

        user_data = UserRead.model_validate(updated_user).model_dump()
        
        return APIResponse.success_response(
            data={
                "profile": user_data,
                "reputation": reputation_data
            },
            message="Perfil atualizado com sucesso"
        )
        
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=e.detail
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erro ao atualizar o perfil: {str(e)}"
        )
