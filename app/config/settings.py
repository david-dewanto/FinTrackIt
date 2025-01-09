# app/config/settings.py
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # Database and Redis settings
    SQLALCHEMY_DATABASE_URL: str
    REDIS_URL: str 

    # JWT settings
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 1
    
    # Firebase settings
    FIREBASE_SERVICE_ACCOUNT_PATH: str
    FIREBASE_WEB_API_KEY: str
    INTERNAL_API_KEY: str
    
    # SMTP settings
    SMTP_HOST: str = "localhost"  
    SMTP_PORT: int = 587  
    SMTP_FROM_EMAIL: str = "no-reply@mail.fintrackit.my.id"

    class Config:
        env_file = ".env"

settings = Settings()