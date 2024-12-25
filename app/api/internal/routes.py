from fastapi import APIRouter
from ...models.models import APIKey
from .schemas import APIKeyRequest, APIKeyResponse
from sqlalchemy.orm import Session
from ...db.database import get_db
from ...core.security import generate_api_key
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter()

@router.get("/")
async def internal_route():
    return {"message": "This is an internal endpoint"}


@router.post("/generate-api-key", response_model=APIKeyResponse)
async def generate_api_key_endpoint(
    request: APIKeyRequest,
    db: Session = Depends(get_db)
):
    # Generate new API key
    new_api_key = generate_api_key()
    
    # Create new API key record
    db_api_key = APIKey(
        api_key=new_api_key,
        full_name=request.full_name,
        application_name=request.application_name,
        organization=request.organization,
        email=request.email,
        phone_number=request.phone_number
    )
    
    try:
        db.add(db_api_key)
        db.commit()
        db.refresh(db_api_key)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not generate API key")
    
    return APIKeyResponse(
        api_key=new_api_key,
        full_name=request.full_name,
        application_name=request.application_name,
        organization=request.organization,
        email=request.email,
        phone_number=request.phone_number
    )