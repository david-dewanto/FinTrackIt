from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    API_KEY: str = "your-super-secret-api-key"  # In production, use environment variable
    JWT_SECRET: str = "your-jwt-secret-key"      # In production, use environment variable
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost",
        "https://yourapp.com"
    ]
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 1

    class Config:
        env_file = ".env"

settings = Settings()