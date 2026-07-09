from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash, verify_password
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenResponse, UserLogin, UserRead, UserRegister


class AuthService:
    def __init__(self, db: Session):
        self.repo = UserRepository(db)

    def register(self, payload: UserRegister) -> TokenResponse:
        if self.repo.get_by_email(payload.email):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already exists")
        if self.repo.get_by_username(payload.username):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists")

        user = self.repo.create(
            email=payload.email,
            username=payload.username,
            hashed_password=get_password_hash(payload.password),
        )
        return TokenResponse(access_token=create_access_token(user.id), user=UserRead.model_validate(user))

    def login(self, payload: UserLogin) -> TokenResponse:
        user = self.repo.get_by_email(payload.email)
        if not user or not verify_password(payload.password, user.hashed_password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
        return TokenResponse(access_token=create_access_token(user.id), user=UserRead.model_validate(user))
