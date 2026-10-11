import jwt
import bcrypt
import secrets
from datetime import datetime, timedelta, timezone
from typing import Union, Any
from app.core.config import settings

ALGORITHM = "HS256"
# Stored as the password of someone who signs in with a mobile number only. No password matches it.
NO_PASSWORD = "!"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def create_access_token(subject: Union[str, Any], expires_delta: timedelta = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    # jti makes every token unique: without it, two logins by the same user in the same second got
    # identical tokens, so their sessions shared a token_hash and couldn't be signed out separately
    to_encode = {"exp": expire, "sub": str(subject), "jti": secrets.token_urlsafe(16)}
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> dict:
    try:
        decoded_token = jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])
        return decoded_token
    except jwt.PyJWTError:
        return {}
