# app/core/firebase.py
import firebase_admin
from firebase_admin import credentials, auth
from functools import lru_cache
from ..config.settings import settings

# Initialize Firebase Admin
cred = credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT_PATH)
firebase_admin.initialize_app(cred)

@lru_cache()
def get_firebase_admin():
    return auth

# app/api/auth/schemas.py
from pydantic import BaseModel, EmailStr
from typing import Optional

class EmailSignUpRequest(BaseModel):
    email: EmailStr
    password: str

class EmailSignInRequest(BaseModel):
    email: EmailStr
    password: str

class GoogleSignInRequest(BaseModel):
    id_token: str

class AuthResponse(BaseModel):
    uid: str
    email: str
    email_verified: bool
    custom_token: str