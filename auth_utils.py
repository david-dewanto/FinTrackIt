# auth_utils.py
from datetime import datetime, timedelta
from typing import Optional, Dict
import jwt
from passlib.hash import pbkdf2_sha256
from fastapi import HTTPException, Security, Header, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import secrets
from pydantic_settings import BaseSettings
import logging
from functools import lru_cache

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AuthSettings(BaseSettings):
    """
    Settings management using Pydantic. This provides automatic environment 
    variable loading and validation.
    """
    SECRET_KEY: str
    INTERNAL_API_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    INTERNAL_TOKEN_EXPIRE_MINUTES: int = 60
    MINIMUM_KEY_LENGTH: int = 32

    class Config:
        env_file = ".env"

@lru_cache()
def get_auth_settings() -> AuthSettings:
    """
    Cached settings loader to avoid reading environment variables repeatedly.
    Returns the same AuthSettings instance for subsequent calls.
    """
    return AuthSettings()

security = HTTPBearer()

def generate_api_key(length: int = 32) -> str:
    """
    Generate a cryptographically secure random API key.
    """
    settings = get_auth_settings()
    if length < settings.MINIMUM_KEY_LENGTH:
        length = settings.MINIMUM_KEY_LENGTH
    return secrets.token_urlsafe(length)

def hash_api_key(api_key: str) -> str:
    """
    Hash an API key for secure storage using pbkdf2_sha256.
    """
    if not api_key:
        raise ValueError("API key cannot be empty")
    return pbkdf2_sha256.hash(api_key)

def verify_api_key(api_key: str, hashed_key: str) -> bool:
    """
    Securely verify an API key against its hash.
    """
    try:
        return pbkdf2_sha256.verify(api_key, hashed_key)
    except Exception as e:
        logger.error(f"Error verifying API key: {str(e)}")
        return False

def create_access_token(
    data: Dict,
    token_type: str = "external",
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT token with claims and expiration.
    """
    # Get settings using our cached function
    settings = get_auth_settings()
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        # Use different expiration times for internal and external tokens
        minutes = (settings.INTERNAL_TOKEN_EXPIRE_MINUTES 
                  if token_type == "internal" 
                  else settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        expire = datetime.utcnow() + timedelta(minutes=minutes)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": token_type
    })
    
    try:
        return jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )
    except Exception as e:
        logger.error(f"Error creating access token: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Could not create access token"
        )

def verify_token(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> dict:
    """
    Verify and decode a JWT token.
    """
    settings = get_auth_settings()
    try:
        token = credentials.credentials
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Token has expired"
        )
    except jwt.PyJWTError as e:
        logger.error(f"JWT validation error: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail="Could not validate token"
        )
    except Exception as e:
        logger.error(f"Unexpected error validating token: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )

async def verify_internal_token(
    token_data: dict = Depends(verify_token)
) -> dict:
    """
    Verify that the token was issued for internal access.
    This is a stronger check than just verifying the token.
    """
    if not token_data.get("is_internal", False):
        logger.warning("Attempt to access internal route with non-internal token")
        raise HTTPException(
            status_code=403,
            detail="This endpoint requires internal access privileges"
        )
    return token_data

async def verify_internal_api_key(
    api_key: Optional[str] = Header(None, alias="X-Internal-API-Key")
) -> bool:
    """
    Verify if the provided API key matches the internal API key.
    """
    settings = get_auth_settings()
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Internal API key required"
        )
    
    is_valid = secrets.compare_digest(
        api_key,
        settings.INTERNAL_API_KEY
    )
    
    if not is_valid:
        logger.warning("Invalid internal API key attempt")
        raise HTTPException(
            status_code=401,
            detail="Invalid internal API key"
        )
    
    return True