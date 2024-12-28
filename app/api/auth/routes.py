# app/api/auth/routes.py
from fastapi import APIRouter, Depends, HTTPException
from ...core.security import create_jwt_token, verify_api_key
from ...core.firebase import get_firebase_admin

router = APIRouter()
firebase_auth = get_firebase_admin()

@router.post("/token")
async def get_token(verified: bool = Depends(verify_api_key)):
    """Get JWT token using API key authentication"""
    token = create_jwt_token()
    return {"access_token": token, "token_type": "bearer"}