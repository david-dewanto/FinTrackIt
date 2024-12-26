# app/api/internal/routes.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from firebase_admin import auth
from firebase_admin.auth import (
    EmailAlreadyExistsError, 
    UserNotFoundError,
    InvalidIdTokenError
)
from ...db.database import get_db
from ...core.security import generate_api_key
from ...core.firebase import get_firebase_admin, sign_in_with_email_password, send_verification_email, send_password_reset_email
from ...models.models import APIKey
from . import schemas

router = APIRouter()
firebase_auth = get_firebase_admin()

@router.get("/")
async def internal_route():
    return {"message": "This is an internal endpoint"}

@router.post("/generate-api-key", response_model=schemas.APIKeyResponse)
async def generate_api_key_endpoint(
    request: schemas.APIKeyRequest,
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
    
    return schemas.APIKeyResponse(
        api_key=new_api_key,
        full_name=request.full_name,
        application_name=request.application_name,
        organization=request.organization,
        email=request.email,
        phone_number=request.phone_number
    )

@router.post("/auth/signin/email", response_model=schemas.AuthResponse)
async def signin_with_email(request: schemas.EmailSignInRequest):
    try:
        # First, attempt to sign in using REST API to get ID token
        sign_in_response = await sign_in_with_email_password(request.email, request.password)
        id_token = sign_in_response['idToken']
        
        # Get user details from Firebase Admin SDK
        user = firebase_auth.get_user_by_email(request.email)
        
        # If email isn't verified, send verification email
        if not user.email_verified:
            try:
                await send_verification_email(id_token)
                return {
                    "uid": user.uid,
                    "email": user.email,
                    "email_verified": False,
                    "message": "Email not verified. A new verification email has been sent."
                }
            except Exception as e:
                # If sending verification fails, still allow login but notify user
                print(f"Error sending verification email: {str(e)}")
                return {
                    "uid": user.uid,
                    "email": user.email,
                    "email_verified": False,
                    "message": "Email not verified. Failed to send verification email."
                }
        
        # If email is verified, proceed with normal login
        return {
            "uid": user.uid,
            "email": user.email,
            "email_verified": True,
            "message": None
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

@router.post("/auth/signup/email", response_model=schemas.AuthResponse)
async def signup_with_email(request: schemas.EmailSignUpRequest):
    try:
        # Create user with email
        user = firebase_auth.create_user(
            email=request.email,
            password=request.password,
            email_verified=False
        )
        
        try:
            # Sign in the user to get ID token
            sign_in_response = await sign_in_with_email_password(request.email, request.password)
            id_token = sign_in_response['idToken']
            
            # Send verification email using the ID token
            await send_verification_email(id_token)
        except Exception as e:
            # Log the error but don't block account creation
            print(f"Error in verification flow: {str(e)}")
        
        return {
            "uid": user.uid,
            "email": user.email,
            "email_verified": user.email_verified,
            "message": "Please check your email for verification link"
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

@router.post("/auth/reset-password", response_model=schemas.PasswordResetResponse)
async def reset_password(request: schemas.PasswordResetRequest):
    try:
        # Check if user exists
        user = firebase_auth.get_user_by_email(request.email)
        
        # Send password reset email
        result = await send_password_reset_email(request.email)
        
        return {
            "success": True,
            "message": "Password reset email sent successfully"
        }
    except UserNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error sending password reset email: {str(e)}"
        )