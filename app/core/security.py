# app/core/security.py
from fastapi import HTTPException, Security, Depends, Request
from fastapi.security import APIKeyHeader, HTTPBearer
from sqlalchemy.orm import Session
from ..models.models import APIKey
from ..db.database import get_db
from ..config.settings import settings
import secrets
from jose import jwt, JWTError, ExpiredSignatureError
from datetime import timedelta, datetime
from typing import Optional

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)

async def get_authorization_token(
    bearer_auth: Optional[HTTPBearer] = Depends(bearer_scheme)
) -> Optional[str]:
    """Extract JWT token from Authorization header"""
    if bearer_auth:
        return bearer_auth.credentials
    return None

async def verify_api_key(
    api_key: str | None = Security(api_key_header),
    db: Session = Depends(get_db)
) -> bool:
    """Verify API key validity"""
    if not api_key:
        raise HTTPException(
            status_code=403,
            detail="API key required"
        )
    
    # Allow internal API key
    if api_key == settings.INTERNAL_API_KEY:
        return True
        
    # Verify regular API key
    db_api_key = db.query(APIKey).filter(APIKey.api_key == api_key).first()
    if not db_api_key:
        raise HTTPException(
            status_code=403,
            detail="Invalid API key"
        )
    return True

async def verify_access(
    request: Request,
    token: str | None = Depends(get_authorization_token),
    api_key: str | None = Security(api_key_header),
    db: Session = Depends(get_db)
):
    """
    Main access verification:
    1. INTERNAL_API_KEY can access all routes
    2. Valid JWT token can access secure routes
    3. If JWT is invalid/missing, fallback to API key verification
    4. Internal routes require INTERNAL_API_KEY
    """
    path = request.url.path

    # Check internal API key first - gives access to everything
    if api_key and api_key == settings.INTERNAL_API_KEY:
        return True

    # Internal routes - only accessible with internal API key
    if "/v1/internal/" in path:
        raise HTTPException(
            status_code=403,
            detail="Access to internal routes requires internal API key"
        )
    
    # For secure routes, try JWT first
    if "/v1/secure/" in path:
        # If valid JWT token exists, allow access

        if not token and (not api_key or api_key != settings.INTERNAL_API_KEY):
            raise HTTPException(
                status_code=401,
                detail="Authentication required. Please provide a valid token."
            )

        if token:
            try:
                verify_jwt_token(token)
                return True
            except ExpiredSignatureError:
                raise HTTPException(
                    status_code=401,
                    detail="Token has expired. Please refresh your token."
                )
            except JWTError:
                raise HTTPException(
                    status_code=401,
                    detail="Invalid server to server token, please request another token at /v1/auth/token"
                )

        # If no token or invalid token, fallback to API key verification
        if api_key != settings.INTERNAL_API_KEY:
            raise HTTPException(
                status_code=403,
                detail="Invalid authentication method"
            )
        return True
    
    # Auth routes - only need API key to get token
    if "/v1/auth/" in path:
        return await verify_api_key(api_key, db)
    
    # Public routes - no verification needed
    return True

def generate_api_key() -> str:
    """Generate a new API key for external applications"""
    return f"key_{secrets.token_urlsafe(24)}"

def create_jwt_token() -> str:
    """Create a new JWT token"""
    expiration = datetime.utcnow() + timedelta(hours=settings.JWT_EXPIRATION_HOURS)
    return jwt.encode(
        {"exp": expiration, "iat": datetime.utcnow()},
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM
    )

def verify_jwt_token(token: str) -> bool:
    """Verify JWT token validity"""
    try:
        jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return True
    except JWTError:
        return False