# app/api/internal/schemas.py
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from enum import Enum

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
    display_name: str

class EmailSignInRequest(BaseModel):
    email: EmailStr
    password: str

class GoogleSignInRequest(BaseModel):
    id_token: str

class AuthResponse(BaseModel):
    uid: str
    email: str
    email_verified: bool
    display_name: Optional[str] = None
    message: Optional[str] = None
    id_token: Optional[str] = None 

# Token Verification Schema
class TokenResponse(BaseModel):
    valid: bool
    uid: str

class EmailVerificationRequest(BaseModel):
    email: EmailStr
    password: str  

class EmailVerificationResponse(BaseModel):
    success: bool
    message: str

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetResponse(BaseModel):
    success: bool
    message: str

class TransactionType(str, Enum):
    BUY = "buy"
    SELL = "sell"

class TransactionCreate(BaseModel):
    stock_code: str
    transaction_type: TransactionType
    quantity: int
    transaction_date: datetime  # Added transaction_date field
    token: str

class TransactionDelete(BaseModel):
    token: str

class TransactionList(BaseModel):
    token: str

class TransactionResponse(BaseModel):
    id: str
    uid: str
    stock_code: str
    transaction_type: TransactionType
    quantity: int
    price_per_share: int
    total_value: int
    transaction_date: datetime

    class Config:
        from_attributes = True

class TransactionListResponse(BaseModel):
    transactions: List[TransactionResponse]