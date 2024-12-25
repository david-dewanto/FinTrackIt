from firebase_admin import auth, credentials, initialize_app
from fastapi import HTTPException
from typing import Dict, Optional
from pydantic import BaseModel, EmailStr
import requests
from datetime import datetime

# Initialize Firebase Admin SDK
cred = credentials.Certificate("firebase/firebase-private-key.json")
firebase_app = initialize_app(cred)

# Firebase Web API Key (from Firebase Console)
FIREBASE_WEB_API_KEY = "AIzaSyCj4SyXCRwpczyfttFAPJuqDHqowY3oQAw"

class FirebaseAuthError(Exception):
    pass

async def sign_in_with_email(email: str, password: str) -> Dict:
    """
    Sign in with email/password using Firebase Auth REST API
    """
    try:
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_WEB_API_KEY}"
        data = {
            "email": email,
            "password": password,
            "returnSecureToken": True
        }
        response = requests.post(url, json=data)
        response.raise_for_status()
        auth_data = response.json()
        
        # Get additional user info from Firebase Admin SDK
        user = auth.get_user_by_email(email)
        
        # Check if email is verified
        if not user.email_verified:
            try:
                # Attempt to send verification email
                await send_email_verification(auth_data.get("idToken"))
                raise FirebaseAuthError("Email not verified. A new verification email has been sent.")
            except FirebaseAuthError as e:
                if "TOO_MANY_ATTEMPTS_TRY_LATER" in str(e):
                    raise FirebaseAuthError("Email hasn't been verified, please verify your email first")
                raise e
        
        return {
            "uid": user.uid,
            "email": user.email,
            "emailVerified": user.email_verified,
            "idToken": auth_data.get("idToken"),
            "refreshToken": auth_data.get("refreshToken"),
            "expiresIn": auth_data.get("expiresIn")
        }
    except FirebaseAuthError:
        raise
    except requests.exceptions.HTTPError as e:
        error_message = e.response.json().get("error", {}).get("message", "Unknown error")
        raise FirebaseAuthError(f"Firebase authentication failed: {error_message}")
    except Exception as e:
        raise FirebaseAuthError(f"Authentication failed: {str(e)}")

async def verify_google_token(id_token: str) -> Dict:
    """
    Verify Google ID token and get user info
    """
    try:
        # Verify the ID token
        decoded_token = auth.verify_id_token(id_token)
        user = auth.get_user(decoded_token['uid'])
        
        return {
            "uid": user.uid,
            "email": user.email,
            "idToken": id_token, 
            "providerId": "google.com"
        }
    except Exception as e:
        raise FirebaseAuthError(f"Google authentication failed: {str(e)}")

async def revoke_firebase_tokens(uid: str) -> None:
    """
    Revoke all Firebase tokens for a user
    """
    try:
        auth.revoke_refresh_tokens(uid)
        return True
    except Exception as e:
        raise FirebaseAuthError(f"Failed to revoke tokens: {str(e)}")

async def create_user_with_email(email: str, password: str) -> Dict:
    """
    Create a new user with email and password using Firebase Auth REST API
    """
    try:
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_WEB_API_KEY}"
        data = {
            "email": email,
            "password": password,
            "returnSecureToken": True
        }
        
        response = requests.post(url, json=data)
        response.raise_for_status()
        auth_data = response.json()
        
        user = auth.get_user(auth_data['localId'])
        
        # Send verification email
        await send_email_verification(auth_data.get("idToken"))
        
        return {
            "uid": user.uid,
            "email": user.email,
            "emailVerified": user.email_verified,
            "idToken": auth_data.get("idToken"),
            "refreshToken": auth_data.get("refreshToken"),
            "message": "Registration successful. Please check your email to verify your account."
        }
    except requests.exceptions.HTTPError as e:
        error_message = e.response.json().get("error", {}).get("message", "Unknown error")
        raise FirebaseAuthError(f"User creation failed: {error_message}")
    except Exception as e:
        raise FirebaseAuthError(f"Registration failed: {str(e)}")

async def send_password_reset_email(email: str) -> Dict:
    """
    Send password reset email using Firebase Auth REST API
    """
    try:
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={FIREBASE_WEB_API_KEY}"
        data = {
            "requestType": "PASSWORD_RESET",
            "email": email
        }
        
        response = requests.post(url, json=data)
        response.raise_for_status()
        
        return {
            "email": email,
            "success": True,
            "message": "Password reset email sent successfully"
        }
    except requests.exceptions.HTTPError as e:
        error_message = e.response.json().get("error", {}).get("message", "Unknown error")
        raise FirebaseAuthError(f"Password reset failed: {error_message}")
    except Exception as e:
        raise FirebaseAuthError(f"Password reset failed: {str(e)}")

async def send_email_verification(id_token: str) -> Dict:
    """
    Send email verification link to the user
    """
    try:
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={FIREBASE_WEB_API_KEY}"
        data = {
            "requestType": "VERIFY_EMAIL",
            "idToken": id_token
        }
        
        response = requests.post(url, json=data)
        response.raise_for_status()
        
        return {
            "success": True,
            "message": "Verification email sent successfully"
        }
    except requests.exceptions.HTTPError as e:
        error_message = e.response.json().get("error", {}).get("message", "Unknown error")
        raise FirebaseAuthError(f"Failed to send verification email: {error_message}")
    except Exception as e:
        raise FirebaseAuthError(f"Failed to send verification email: {str(e)}")