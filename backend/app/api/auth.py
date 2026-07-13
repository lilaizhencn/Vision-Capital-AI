from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.auth import AIUsageRead, TokenResponse, UserLogin, UserRead, UserRegister
from app.services.ai_usage_service import AIUsageService
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


@router.get("/ai-usage", response_model=AIUsageRead)
def ai_usage(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return AIUsageService(db).snapshot(user.id)
