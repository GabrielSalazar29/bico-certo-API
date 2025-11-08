from sqlalchemy.orm import Session
from app.model.user import User  
from app.schema.user import UserUpdate 

class ProfileService:
    
    def update_user_profile(
        self, 
        db_session: Session, 
        *, 
        user: User,  
        user_update: UserUpdate  
    ) -> User:
        update_data = user_update.model_dump(exclude_unset=True)

        if not update_data:
            return user

        
        for key, value in update_data.items():
            setattr(user, key, value) 

        db_session.add(user)
        db_session.commit()
        db_session.refresh(user) 
        
        return user