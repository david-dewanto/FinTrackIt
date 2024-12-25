# routers/secure.py
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

from database import get_db, APIKey
from auth_utils import verify_token

router = APIRouter()

class APIKeyStats(BaseModel):
    application_name: str
    email: str
    organization_name: Optional[str]
    request_count: int
    last_request: Optional[datetime]
    status: str

@router.get("/", tags=["Secure"])
async def secure_root(
    token_data: dict = Depends(verify_token),
    db: Session = Depends(get_db),
    request: Request = None
):
    """
    Basic secured endpoint that requires authentication.
    Verifies that authentication is working.
    Also updates the request count for the API key.
    """
    # Get API key from request headers
    api_key = request.headers.get("X-API-Key")
    if api_key:
        # Update request count and last used timestamp
        db_api_key = db.query(APIKey).filter(APIKey.key_hash == api_key).first()
        if db_api_key:
            db_api_key.request_count += 1
            db_api_key.last_used = datetime.utcnow()
            db.commit()
    
    return {
        "message": "You have accessed a secure endpoint",
        "token_data": token_data,
        "timestamp": datetime.utcnow()
    }

@router.get("/usage-stats", response_model=APIKeyStats, tags=["Secure"])
async def get_usage_stats(
    token_data: dict = Depends(verify_token),
    db: Session = Depends(get_db),
    request: Request = None
):
    """
    Get usage statistics for the current API key.
    """
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        raise HTTPException(status_code=400, detail="API key not found in headers")
    
    db_api_key = db.query(APIKey).filter(APIKey.key_hash == api_key).first()
    if not db_api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    
    return {
        "application_name": db_api_key.application_name,
        "email": db_api_key.email,
        "organization_name": db_api_key.organization_name,
        "request_count": db_api_key.request_count,
        "last_request": db_api_key.last_used,
        "status": db_api_key.status
    }