# app/config/settings.py
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # Existing settings
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 1
    FIREBASE_SERVICE_ACCOUNT_PATH: str
    FIREBASE_WEB_API_KEY: str
    INTERNAL_API_KEY: str
    
    SMTP_HOST: str = "localhost"  
    SMTP_PORT: int = 25  
    SMTP_FROM_EMAIL: str = "no-reply@mail.fintrackit.my.id"

    class Config:
        env_file = ".env"

settings = Settings()