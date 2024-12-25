# routers/public.py
from fastapi import APIRouter, HTTPException
from typing import Dict
from datetime import datetime
from pydantic import BaseModel

router = APIRouter()

class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime

@router.get("/", tags=["Public"])
async def root():
    """
    Basic endpoint to verify the API is running.
    Returns a simple confirmation message.
    """
    return {"message": "Welcome to the API Service"}

@router.get("/health", response_model=HealthResponse, tags=["Public"])
async def health_check():
    """
    Health check endpoint that returns detailed service status.
    Useful for monitoring and automated health checks.
    """
    return {
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": datetime.utcnow()
    }

@router.get("/service-info", tags=["Public"])
async def get_service_info():
    """
    Returns public information about the service.
    Includes documentation links and basic usage instructions.
    """
    return {
        "service_name": "FastAPI Authentication Service",
        "description": "API service with internal and external authentication",
        "documentation": "/docs",
        "version": "1.0.0",
        "auth_instructions": {
            "step1": "Request an API key through the authorized channel",
            "step2": "Use the API key to obtain a JWT token",
            "step3": "Include the JWT token in the Authorization header"
        }
    }

@router.get("/example-error", tags=["Public"])
async def example_error():
    """
    Demonstrates proper error handling in the API.
    Intentionally raises an error to show error response format.
    """
    raise HTTPException(
        status_code=400,
        detail={
            "message": "Example error response",
            "error_code": "EXAMPLE_ERROR",
            "timestamp": datetime.utcnow().isoformat()
        }
    )