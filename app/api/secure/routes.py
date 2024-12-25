from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Optional
from ...core.security import verify_jwt_token

router = APIRouter()

@router.get("/")
async def secure_route(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials"
        )
    
    token = authorization.split(" ")[1]
    if not verify_jwt_token(token):
        raise HTTPException(
            status_code=401,
            detail="Invalid token"
        )
    
    return {"message": "This is a secure endpoint"}