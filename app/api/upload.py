from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from ..config.database import get_db
from ..auth.dependencies import get_current_user
from ..model.user import User
from ..util.responses import APIResponse
from ..util.image_utils import ImageUtils

router = APIRouter(prefix="/upload", tags=["Upload"])


@router.post("/profile-picture", response_model=APIResponse)
async def upload_profile_picture(
        file: UploadFile = File(...),
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Upload de foto de perfil

    - Aceita: JPG, PNG, WEBP
    - Tamanho máximo: 5MB
    - Dimensões: redimensionada para 800x800px
    - Qualidade: 85%
    """

    try:
        # Salva e otimiza imagem
        relative_path = await ImageUtils.save_profile_picture(
            file=file,
            user_id=current_user.id
        )

        ImageUtils.delete_old_profile_pictures(
            user_id=current_user.id,
            keep_current=relative_path
        )

        from ..config.settings import settings
        full_url = f"{settings.BASE_URL}/uploads/{relative_path}"

        current_user.profile_pic_url = full_url
        db.commit()

        return APIResponse.success_response(
            data={
                "url": full_url,
                "relative_path": relative_path
            },
            message="Foto de perfil atualizada com sucesso!"
        )

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao fazer upload: {str(e)}"
        )


@router.delete("/profile-picture", response_model=APIResponse)
async def delete_profile_picture(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Remove a foto de perfil do usuário"""

    try:
        ImageUtils.delete_old_profile_pictures(current_user.id)

        current_user.profile_pic_url = None
        db.commit()

        return APIResponse.success_response(
            message="Foto de perfil removida com sucesso"
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao remover foto: {str(e)}"
        )
