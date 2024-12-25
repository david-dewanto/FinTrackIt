from pydantic import BaseModel, EmailStr
from typing import Optional

class APIKeyRequest(BaseModel):
    full_name: str
    application_name: str
    organization: str
    email: EmailStr
    phone_number: str

class APIKeyResponse(BaseModel):
    api_key: str
    full_name: str
    application_name: str
    organization: str
    email: EmailStr
    phone_number: str

# Auth Request Schemas
class EmailSignUpRequest(BaseModel):
    email: EmailStr
    password: str

class EmailSignInRequest(BaseModel):
    email: EmailStr
    password: str

class GoogleSignInRequest(BaseModel):
    id_token: str

# Auth Response Schema
class AuthResponse(BaseModel):
    uid: str
    email: str
    email_verified: bool
    custom_token: str

# Token Verification Schema
class TokenResponse(BaseModel):
    valid: bool
    uid: str

class EmailVerificationRequest(BaseModel):
    email: EmailStr

class EmailVerificationResponse(BaseModel):
    success: bool
    message: str