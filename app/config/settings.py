# app/config/settings.py
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # Existing settings
    JWT_SECRET: str = "61ac1ec5c6e2befc4eb58602fdbd7361892dbc921b3615506d4117b8641228b00e8dcdc50bfff15163e7befdd5eec7054b2cefc2bf14831e475862f57ab30df6adf70a3f98e62c69b54afca9eb0fe5fbc22c6b1ac5db7c42a83046eb543cad79dfebfd0a615db1ee97ab03dfc7302399e282e7c7ab7eee843218b7b967a37598096d828890a8697981febc8e87fe43eae4dd49cfb966a1642e93d236c0856a0f24f9260dae987f109b6d84a477a2f519f3e2415634059f33087d5adf4ab4abd87b486f9dbd3a6a0beb3dbd99f61894d40266707e4c8bbbb7aa2e11077403aee8aaf8fbe3979d773f481c7523a360a784d5b2b6c2498323007ac9bbf24319746a552c6905b4ce08df55a8ccfd8650091274a226644dfeb9ef7dba89cdd700cf11ab226ec7098fa708155bc76855ad75657741f54a289bfde571091824111ad43e35c32bf989f9bd625304520c41d98c7871321d485a7955e27da6d22ea634168f0329dcfb070383f584aa4b83ab8910e2d4e33fd2e5c9573c46b14889b8616f9a04c94ace601b0e58fa48e02641462ebb58a5e6c1a53851224eb7ece98d71cfe5cfc65ced799f30c319411bddd7deaf09da7866136c1f0ca877fede9ed00b713d5faf6854528bf998250d1bec8282d3435577fb14680572e814fff57187082c34204ce4ef954a53ddfcbdb1facd978f649d7e0156e088d014fcaca25993f81573"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 1
    FIREBASE_SERVICE_ACCOUNT_PATH: str
    FIREBASE_WEB_API_KEY: str

    # Frontend application settings
    FRONTEND_SERVER_IP: str = "123.456.789.0"  # Your frontend server IP
    
    # We only need to specify the frontend origin since it's the only special case
    FRONTEND_ORIGIN: str = "https://your-frontend-domain.com"

    class Config:
        env_file = ".env"

settings = Settings()