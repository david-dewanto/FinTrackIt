from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class EmailLoginRequest(BaseModel):
    email: EmailStr
    password: str

class GoogleLoginRequest(BaseModel):
    id_token: str

class LoginResponse(BaseModel):
    uid: str
    email: str
    idToken: str
    refreshToken: Optional[str]
    expiresIn: Optional[str]
    message: str = "Login successful"

class LogoutResponse(BaseModel):
    message: str = "Logout successful"

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)

class RegisterResponse(BaseModel):
    uid: str
    email: str
    emailVerified: bool
    idToken: str
    refreshToken: Optional[str]
    message: str = "Registration successful"

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ForgotPasswordResponse(BaseModel):
    email: str
    success: bool
    message: str