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