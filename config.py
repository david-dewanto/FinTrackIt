# config.py
from pydantic import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://user:password@localhost/auth_service"
    SECRET_KEY: str = "your-secret-key-for-jwt-signing"
    INTERNAL_API_KEY: str = "your-internal-api-key"  # Set this through environment variables
    
    class Config:
        env_file = ".env"

settings = Settings()