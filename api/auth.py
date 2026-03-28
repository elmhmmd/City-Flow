import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

SECRET_KEY      = os.getenv("SECRET_KEY", "change-me-in-production")
ALGORITHM       = "HS256"
ACCESS_EXPIRES  = timedelta(hours=1)
REFRESH_EXPIRES = timedelta(days=7)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + ACCESS_EXPIRES
    payload["type"] = "access"
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> tuple[str, datetime]:
    payload = data.copy()
    expires_at = datetime.now(timezone.utc) + REFRESH_EXPIRES
    payload["exp"] = expires_at
    payload["type"] = "refresh"
    payload["jti"] = secrets.token_hex(16)
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token, expires_at


def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
