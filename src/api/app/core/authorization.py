from sqlalchemy.orm import Session
from fastapi import Depends, Header

from app.db.postgres import get_db
from app.models.user_login import UserDetails
from app.services.user_login import Service as UserService
from app.repositories.user_login import Repository as UserRepository


def get_user_details(
    x_user_id: str = Header(..., alias="X-User-ID"),
    db: Session = Depends(get_db),
) -> UserDetails:
    """Resolve the authenticated user's details using the X-User-ID header."""
    user_repo = UserRepository(db)
    user_service = UserService(user_repo)
    return user_service.get_user_details(user_id=x_user_id)
