# app/api/internal/routes.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from firebase_admin import auth
from firebase_admin.auth import (
    EmailAlreadyExistsError, 
    UserNotFoundError
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
                    "message": "Email not verified. Please check your email."
                }
        
        # If email is verified, proceed with normal login
        return {
            "uid": user.uid,
            "email": user.email,
            "display_name": user.display_name,
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
        # First, check if a user already exists with this email
        try:
            existing_user = firebase_auth.get_user_by_email(request.email)
            
            # If we found a user, let's check their sign-in providers
            user_info = firebase_auth.get_user(existing_user.uid)
            
            # Get the provider information
            providers = [
                provider.provider_id 
                for provider in user_info.provider_data
            ]
            
            if 'google.com' in providers:
                raise HTTPException(
                    status_code=400,  
                    detail="This email is already registered with Google. Please sign in with Google instead."
                )
            
            # If we reach here, the user exists but not with Google
            # This means they're trying to create a duplicate account
            raise HTTPException(
                status_code=400,
                detail="Email already registered. Please use the sign-in page."
            )
            
        except UserNotFoundError:
            # No existing user found, proceed with creation
            user = firebase_auth.create_user(
                email=request.email,
                password=request.password,
                display_name=request.display_name,
                email_verified=False
            )
            
            try:
                # Sign in the user to get ID token
                sign_in_response = await sign_in_with_email_password(
                    request.email, 
                    request.password
                )
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
        # First get the user information
        user = firebase_auth.get_user_by_email(request.email)
        
        # Get the user's provider information
        user_info = firebase_auth.get_user(user.uid)
        providers = [
            provider.provider_id 
            for provider in user_info.provider_data
        ]
        
        # Check if the user is registered with Google
        if 'google.com' in providers:
            raise HTTPException(
                status_code=400,
                detail="This account uses Google Sign-In. Please sign in with Google instead of using password reset."
            )
            
        # If we reach here, the user is registered with email/password
        # Proceed with password reset
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
    except HTTPException:
        # Re-raise HTTP exceptions without modification
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error sending password reset email: {str(e)}"
        )

@router.post("/auth/signin/google", response_model=schemas.AuthResponse)
async def signin_with_google(request: schemas.GoogleSignInRequest):
    try:
        # Verify the ID token using Firebase Admin SDK
        decoded_token = firebase_auth.verify_id_token(request.id_token)
        email = decoded_token.get('email')
        
        if not email:
            raise HTTPException(
                status_code=400,
                detail="Email not provided in Google sign-in"
            )
        
        try:
            # First try to find user by email
            existing_user = firebase_auth.get_user_by_email(email)
            
            # Check the user's provider information
            user_info = firebase_auth.get_user(existing_user.uid)
            providers = [
                provider.provider_id 
                for provider in user_info.provider_data
            ]
            
            # First, check if they're registered with email/password
            if 'password' in providers:
                raise HTTPException(
                    status_code=400,
                    detail="This email is already registered with email/password. Please sign in with your email and password instead."
                )
            
            # Then check if they're registered with Google
            if 'google.com' in providers:
                # This is the happy path - user exists and uses Google
                return {
                    "uid": existing_user.uid,
                    "email": existing_user.email,
                    "email_verified": existing_user.email_verified,
                    "display_name": existing_user.display_name,
                    "message": None
                }
            
            # If we get here, the user exists but doesn't have any recognized providers
            # This is an edge case that shouldn't happen in normal circumstances
            raise HTTPException(
                status_code=400,
                detail="Account exists but with incompatible sign-in method. Please contact support."
            )
                
        except UserNotFoundError:
            # Only create new user if email doesn't exist at all
            user_properties = {
                'email': email,
                'email_verified': decoded_token.get('email_verified', False),
                'display_name': decoded_token.get('name'),
                'photo_url': decoded_token.get('picture')
            }
            
            # Remove None values
            user_properties = {k: v for k, v in user_properties.items() if v is not None}
            
            # Create new user
            user = firebase_auth.create_user(**user_properties)
            return {
                "uid": user.uid,
                "email": user.email,
                "email_verified": user.email_verified,
                "display_name": user.display_name,
                "message": None
            }
        
    except HTTPException:
        # Re-raise HTTP exceptions without modification
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to authenticate with Google: {str(e)}"
        )