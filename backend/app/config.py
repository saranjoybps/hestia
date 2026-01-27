from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Settings(BaseSettings):
    """Application settings and configuration"""
    
    # Firebase
    firebase_credentials_path: str = "./firebase-credentials.json"
    firebase_credentials: str | None = None  # For Vercel/production deployment
    
    # API Settings
    api_title: str = "JoyHR API"
    api_description: str = "HR Management System API"
    api_version: str = "1.0.0"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    # CORS
    frontend_url: str = "http://localhost:3000"
    allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3005",
        "http://localhost:8000",
        "https://*.onrender.com",
        "https://*.vercel.app"
    ]
    
    # Security
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Google Drive (for document storage)
    google_service_account_path: str = "credentials/service-account.json"
    google_drive_folder_id: str = ""  # Optional: specific folder for letters
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
