from datetime import datetime, timedelta
import jwt
from fastapi import HTTPException, Security, Depends
from fastapi.security import APIKeyHeader
from typing import Optional
from ..config.settings import settings

api_key_header = APIKeyHeader(name="X-API-Key")

def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != settings.API_KEY:
        raise HTTPException(
            status_code=403,
            detail="Invalid API key"
        )
    return api_key

def create_jwt_token() -> str:
    expiration = datetime.utcnow() + timedelta(hours=settings.JWT_EXPIRATION_HOURS)
    return jwt.encode(
        {"exp": expiration, "iat": datetime.utcnow()},
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM
    )

def verify_jwt_token(token: str) -> bool:
    try:
        jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return True
    except jwt.InvalidTokenError:
        return False