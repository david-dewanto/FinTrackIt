# models.py
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, UUID, BigInteger
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
import uuid

Base = declarative_base()

# SQLAlchemy Models
class APIKey(Base):
    __tablename__ = "api_keys"
    
    # Primary Key
    key_hash = Column(String(255), primary_key=True)
    
    # User Information
    application_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    phone_number = Column(String(20))
    organization_name = Column(String(255))
    
    # System Fields
    is_internal = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used = Column(DateTime(timezone=True), nullable=True)
    description = Column(Text, nullable=True)
    status = Column(String(50), default='active')
    request_count = Column(BigInteger, default=0)

class KeyUsageLog(Base):
    __tablename__ = "key_usage_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key_hash = Column(String(255), ForeignKey('api_keys.key_hash'))
    accessed_at = Column(DateTime(timezone=True), server_default=func.now())
    ip_address = Column(String(45))
    endpoint = Column(String(255))
    success = Column(Boolean)

# Pydantic Models for API Request/Response
class APIKeyCreate(BaseModel):
    application_name: str
    email: EmailStr
    full_name: str
    phone_number: Optional[str] = None
    organization_name: Optional[str] = None
    description: Optional[str] = None

class APIKeyResponse(BaseModel):
    api_key: str  # Only returned once upon creation
    application_name: str
    email: str
    full_name: str
    organization_name: Optional[str]
    created_at: datetime
    request_count: int
    status: str
    
    class Config:
        from_attributes = True