# routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from database import get_db, APIKey
from auth_utils import (
    verify_api_key,
    create_access_token,
    verify_internal_api_key,
)

router = APIRouter()

@router.post("/token")
async def generate_token(
    api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db)
):
    """Generate a JWT token using an API key."""
    try:
        # Check if it's an internal API key
        is_internal = await verify_internal_api_key(api_key)
        if is_internal:
            token_data = {"is_internal": True}
            return {"access_token": create_access_token(token_data)}
    except HTTPException:
        # If not an internal key, continue to check external keys
        pass
    
    # Check external API keys
    db_api_key = db.query(APIKey).filter(APIKey.is_internal == False).all()
    valid_key = False
    
    for stored_key in db_api_key:
        if verify_api_key(api_key, stored_key.key_hash):
            valid_key = True
            # Update last used timestamp
            stored_key.last_used = datetime.utcnow()
            db.commit()
            break
    
    if not valid_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    token_data = {"is_internal": False}
    return {"access_token": create_access_token(token_data)}