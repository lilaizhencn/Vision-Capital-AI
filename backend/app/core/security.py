from datetime import datetime, timedelta, timezone
import hashlib

import bcrypt
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    digest = hashlib.sha256(plain_password.encode("utf-8")).digest()
    try:
        if bcrypt.checkpw(digest, hashed_password.encode("utf-8")):
            return True
    except ValueError:
        pass
    # Keep compatibility with accounts created by the previous Passlib format.
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except (ValueError, RuntimeError):
        return False


def get_password_hash(password: str) -> str:
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return bcrypt.hashpw(digest, bcrypt.gensalt()).decode("utf-8")


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("Invalid token") from exc
