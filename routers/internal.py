# routers/internal.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from database import get_db
from models import APIKey, APIKeyCreate, APIKeyResponse
from auth_utils import (
    verify_internal_token,
    generate_api_key,
    hash_api_key,
)
from firebase.auth_models import (
    EmailLoginRequest, 
    GoogleLoginRequest, 
    LoginResponse, 
    LogoutResponse,
    RegisterRequest, 
    RegisterResponse, 
    ForgotPasswordRequest, 
    ForgotPasswordResponse
)

from firebase.firebase_auth_utils import (
    sign_in_with_email,
    verify_google_token,
    revoke_firebase_tokens,
    FirebaseAuthError,
    create_user_with_email,
    send_password_reset_email
)

router = APIRouter()

@router.get("/", tags=["Internal"])
async def internal_root(token_data: dict = Depends(verify_internal_token)):
    """
    Root endpoint for internal API access.
    Only accessible with internal API keys.
    """
    return {
        "message": "Internal API accessed successfully",
        "timestamp": datetime.utcnow(),
        "token_info": token_data
    }

@router.post("/api-keys/generate", response_model=APIKeyResponse, tags=["Internal"])
async def generate_external_api_key(
    key_data: APIKeyCreate,
    token_data: dict = Depends(verify_internal_token),
    db: Session = Depends(get_db)
):
    """
    Generate a new external API key with associated user information.
    Only accessible with internal API tokens.
    Returns the API key which should be securely transmitted to the requestor.
    """
    try:
        # Generate new API key
        new_api_key = generate_api_key()
        hashed_key = hash_api_key(new_api_key)
        
        # Create database record
        db_api_key = APIKey(
            key_hash=hashed_key,
            application_name=key_data.application_name,
            email=key_data.email,
            full_name=key_data.full_name,
            phone_number=key_data.phone_number,
            organization_name=key_data.organization_name,
            description=key_data.description,
            is_internal=False,
            created_at=datetime.utcnow(),
            request_count=0,
            status='active'
        )
        db.add(db_api_key)
        db.commit()
        db.refresh(db_api_key)
        
        return {
            "api_key": new_api_key,
            "application_name": db_api_key.application_name,
            "email": db_api_key.email,
            "full_name": db_api_key.full_name,
            "organization_name": db_api_key.organization_name,
            "created_at": db_api_key.created_at,
            "request_count": db_api_key.request_count,
            "status": db_api_key.status
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate API key: {str(e)}"
        )

@router.post("/auth/login/email", response_model=LoginResponse, tags=["Authentication"])
async def login_with_email(
    login_data: EmailLoginRequest,
    db: Session = Depends(get_db)
):
    """
    Handle email/password login through Firebase.
    Frontend sends credentials, backend verifies with Firebase.
    """
    try:
        # Authenticate with Firebase
        user_data = await sign_in_with_email(
            login_data.email,
            login_data.password
        )
        
        return user_data
    except FirebaseAuthError as e:
        raise HTTPException(
            status_code=401,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Login failed: {str(e)}"
        )

@router.post("/auth/login/google", response_model=LoginResponse, tags=["Authentication"])
async def login_with_google(
    login_data: GoogleLoginRequest,
    db: Session = Depends(get_db)
):
    """
    Handle Google sign-in through Firebase.
    Frontend sends Google ID token, backend verifies with Firebase.
    """
    try:
        # Verify Google token with Firebase
        user_data = await verify_google_token(login_data.id_token)
        
        return user_data
    except FirebaseAuthError as e:
        raise HTTPException(
            status_code=401,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Google login failed: {str(e)}"
        )

@router.post("/auth/logout", response_model=LogoutResponse, tags=["Authentication"])
async def logout(
    uid: str,
):
    """
    Handle user logout.
    Revokes Firebase tokens and cleans up any local sessions.
    """
    try:
        # Revoke Firebase tokens
        await revoke_firebase_tokens(uid)
        
        return {"message": "Logout successful"}
    except FirebaseAuthError as e:
        raise HTTPException(
            status_code=401,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Logout failed: {str(e)}"
        )

@router.post("/auth/register", response_model=RegisterResponse, tags=["Authentication"])
async def register_user(
    register_data: RegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Register a new user with email and password through Firebase.
    """
    try:
        user_data = await create_user_with_email(
            email=register_data.email,
            password=register_data.password,
        )
        
        return user_data
    except FirebaseAuthError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Registration failed: {str(e)}"
        )

@router.post("/auth/forgot-password", response_model=ForgotPasswordResponse, tags=["Authentication"])
async def forgot_password(
    forgot_password_data: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Send password reset email through Firebase.
    User will receive an email with a link to reset their password.
    """
    try:
        result = await send_password_reset_email(
            email=forgot_password_data.email
        )
        return result
    except FirebaseAuthError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Password reset failed: {str(e)}"
        )