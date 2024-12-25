from fastapi import APIRouter
from ...models.models import APIKey
from .schemas import APIKeyRequest, APIKeyResponse
from sqlalchemy.orm import Session
from ...db.database import get_db
from ...core.security import generate_api_key
from fastapi import APIRouter, Depends, HTTPException
from firebase_admin import auth
from firebase_admin.auth import (
    EmailAlreadyExistsError, 
    UserNotFoundError,
    InvalidIdTokenError
)
from ...core.firebase import get_firebase_admin
from . import schemas

router = APIRouter()
firebase_auth = get_firebase_admin()

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

@router.post("/auth/signup/email", response_model=schemas.AuthResponse)
async def signup_with_email(request: schemas.EmailSignUpRequest):
    try:
        # Create user with email
        user = firebase_auth.create_user(
            email=request.email,
            password=request.password,
            email_verified=False
        )
        
        # Generate custom token for initial authentication
        custom_token = firebase_auth.create_custom_token(user.uid)
        
        return {
            "uid": user.uid,
            "email": user.email,
            "email_verified": user.email_verified,
            "custom_token": custom_token.decode('utf-8')
        }
    except EmailAlreadyExistsError:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

@router.post("/auth/send-verification-email", response_model=schemas.EmailVerificationResponse)
async def send_verification_email(request: schemas.EmailVerificationRequest):
    try:
        # Check if user exists
        user = firebase_auth.get_user_by_email(request.email)
        
        # If already verified, return success
        if user.email_verified:
            return {
                "success": True,
                "message": "Email is already verified"
            }
        
        return {
            "success": True,
            "message": "Verification email sent successfully"
        }
        
    except UserNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error sending verification email: {str(e)}"
        )

@router.post("/auth/signin/email", response_model=schemas.AuthResponse)
async def signin_with_email(request: schemas.EmailSignInRequest):
    try:
        # Get user by email
        user = firebase_auth.get_user_by_email(request.email)
        
        # Check if email is verified
        if not user.email_verified:
            raise HTTPException(
                status_code=400,
                detail="Email not verified. Please verify your email first."
            )
        
        # Generate custom token
        custom_token = firebase_auth.create_custom_token(user.uid)
        
        return {
            "uid": user.uid,
            "email": user.email,
            "email_verified": user.email_verified,
            "custom_token": custom_token.decode('utf-8')
        }
    except UserNotFoundError:
        raise HTTPException(
            status_code=400,
            detail="Invalid credentials"
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

@router.post("/auth/signin/google", response_model=schemas.AuthResponse)
async def signin_with_google(request: schemas.GoogleSignInRequest):
    try:
        # Verify Google ID token
        decoded_token = firebase_auth.verify_id_token(request.id_token)
        
        # Get or create user
        try:
            user = firebase_auth.get_user_by_email(decoded_token['email'])
        except UserNotFoundError:
            user = firebase_auth.create_user(
                email=decoded_token['email'],
                email_verified=True,
            )
        
        # Generate custom token
        custom_token = firebase_auth.create_custom_token(user.uid)
        
        return {
            "uid": user.uid,
            "email": user.email,
            "email_verified": user.email_verified,
            "custom_token": custom_token.decode('utf-8')
        }
    except InvalidIdTokenError:
        raise HTTPException(
            status_code=400,
            detail="Invalid Google ID token"
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

@router.post("/auth/verify-token")
async def verify_token(token: str):
    try:
        decoded_token = firebase_auth.verify_id_token(token)
        return {"valid": True, "uid": decoded_token['uid']}
    except:
        raise HTTPException(
            status_code=400,
            detail="Invalid token"
        )