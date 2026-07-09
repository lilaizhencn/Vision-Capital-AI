from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.auth import TokenResponse, UserLogin, UserRead, UserRegister
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    return AuthService(db).register(payload)


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    return AuthService(db).login(payload)


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(get_current_user)):
    return user

