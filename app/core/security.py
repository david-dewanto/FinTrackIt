from datetime import datetime, timedelta
import jwt
from fastapi import HTTPException, Security, Depends
from fastapi.security import APIKeyHeader
from ..config.settings import settings
import secrets
from sqlalchemy.orm import Session
from ..db.database import get_db
from ..models.models import APIKey

api_key_header = APIKeyHeader(name="X-API-Key")

def verify_api_key(
    api_key: str = Security(api_key_header),
    db: Session = Depends(get_db)
):
    db_api_key = db.query(APIKey).filter(APIKey.api_key == api_key).first()
    if not db_api_key:
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

def generate_api_key() -> str:
    return secrets.token_urlsafe(32)