# app/core/firebase.py
import firebase_admin
from firebase_admin import credentials, auth
from functools import lru_cache
import httpx
from ..config.settings import settings

# Initialize Firebase Admin
cred = credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT_PATH)
firebase_admin.initialize_app(cred)

# Firebase Web API endpoints
FIREBASE_WEB_API_KEY = settings.FIREBASE_WEB_API_KEY
FIREBASE_AUTH_BASE_URL = "https://identitytoolkit.googleapis.com/v1"
FIREBASE_AUTH_SIGNIN = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_WEB_API_KEY}"
FIREBASE_AUTH_EMAIL_VERIFICATION = f"{FIREBASE_AUTH_BASE_URL}/accounts:sendOobCode?key={FIREBASE_WEB_API_KEY}"

@lru_cache()
def get_firebase_admin():
    return auth

async def sign_in_with_email_password(email: str, password: str) -> dict:
    """
    Signs in a user with email and password to get an ID token.
    
    Args:
        email (str): User's email
        password (str): User's password
        
    Returns:
        dict: Response containing idToken and other user data
    """
    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(FIREBASE_AUTH_SIGNIN, json=payload)
        if not response.is_success:
            raise Exception(f"Sign in failed: {response.json().get('error', {}).get('message')}")
        return response.json()

async def send_verification_email(id_token: str) -> dict:
    """
    Sends an email verification using Firebase Auth REST API.
    Requires the user's ID token from signin.
    
    Args:
        id_token (str): The ID token from sign in response
        
    Returns:
        dict: The API response containing email delivery confirmation
    """
    payload = {
        "requestType": "VERIFY_EMAIL",
        "idToken": id_token
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(FIREBASE_AUTH_EMAIL_VERIFICATION, json=payload)
        if not response.is_success:
            raise Exception(f"Send verification email failed: {response.json().get('error', {}).get('message')}")
        return response.json()

async def send_password_reset_email(email: str) -> dict:
    """
    Sends a password reset email using Firebase Auth REST API.
    
    Args:
        email (str): The user's email address
        
    Returns:
        dict: The API response containing email delivery confirmation
    """
    payload = {
        "requestType": "PASSWORD_RESET",
        "email": email
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(FIREBASE_AUTH_EMAIL_VERIFICATION, json=payload)
        if not response.is_success:
            raise Exception(f"Password reset email failed: {response.json().get('error', {}).get('message')}")
        return response.json()