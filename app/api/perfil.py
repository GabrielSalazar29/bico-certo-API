from fastapi import APIRouter,Depends
from app.util.responses import APIResponse
from app.model.user import User
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/perfil", tags=["Perfil"])

# Endpoint
@router.get("/info",response_model=APIResponse)
async def info(current_user:User=Depends(get_current_user)):
    return APIResponse.success_response(data={"user_info":current_user.full_name},message="Informações recuperadas com sucesso")