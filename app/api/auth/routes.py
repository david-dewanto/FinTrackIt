from fastapi import APIRouter, Depends
from ...core.security import verify_api_key, create_jwt_token
from ...core.firebase import get_firebase_admin

router = APIRouter()
firebase_auth = get_firebase_admin()

@router.post("/token")
async def get_token(api_key: str = Depends(verify_api_key)):
    token = create_jwt_token()
    return {"access_token": token}

