from sqlalchemy.orm import Session
from app.model.user import User  
from app.schema.user import UserUpdate # Importe o schema de update

class ProfileService:
    
    def update_user_profile(
        self, 
        db_session: Session, 
        *, 
        user: User,  # O objeto User do SQLAlchemy (do get_current_active_user)
        user_update: UserUpdate  # Os dados do Pydantic vindos do App
    ) -> User:
        # Converte o schema Pydantic para um dict, 
        # excluindo campos que não foram enviados (unset)
        # Isso garante que um PATCH não apague campos existentes com None
        update_data = user_update.model_dump(exclude_unset=True)

        if not update_data:
            # Se o body estava vazio (ex: {}), não faz nada
            return user

        # Itera sobre os dados enviados e atualiza o objeto 'user'
        for key, value in update_data.items():
            setattr(user, key, value) # Ex: user.full_name = "Novo Nome"

        # Adiciona o usuário modificado à sessão e commita
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user) # Recarrega o usuário do DB
        
        return user