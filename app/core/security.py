# app/core/security.py
from fastapi import HTTPException, Security, Depends, Request
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session
from ..models.models import APIKey
from ..db.database import get_db
from ..config.settings import settings
import secrets
from jose import jwt, JWTError
from datetime import timedelta, datetime

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(
    request: Request,
    api_key: str | None = Security(api_key_header),
    db: Session = Depends(get_db)
):
    path = request.url.path
    
    # Internal routes - only check frontend server IP
    if "/v1/internal/" in path:
        if request.client.host == settings.FRONTEND_SERVER_IP:
            return True
        raise HTTPException(
            status_code=403,
            detail="Access to internal routes is restricted"
        )
    
    # Secure routes - require valid API key
    if "/v1/secure/" in path:
        if not api_key:
            raise HTTPException(
                status_code=403,
                detail="API key required for secure routes"
            )
        
        db_api_key = db.query(APIKey).filter(APIKey.api_key == api_key).first()
        if not db_api_key:
            raise HTTPException(
                status_code=403,
                detail="Invalid API key"
            )
        return api_key
    
    # Public and auth routes - no verification needed
    return True

def generate_api_key() -> str:
    """Generate a new API key for external applications"""
    return secrets.token_urlsafe(32)

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
    except JWTError:  
        return False