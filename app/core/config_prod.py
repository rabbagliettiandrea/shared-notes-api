from pydantic_settings import BaseSettings
from typing import List
import os


class ProductionSettings(BaseSettings):
    """Production settings for Shared Notes API"""
    
    # Database - Will be injected from AWS Secrets Manager
    DATABASE_URL: str = ""
    
    # Redis - Will be injected from AWS Secrets Manager
    REDIS_URL: str = ""
    
    # JWT - Will be injected from AWS Secrets Manager
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # CORS - Allow all origins in production (configure as needed)
    ALLOWED_HOSTS: List[str] = ["*"]
    
    # App
    DEBUG: bool = False
    
    # AWS specific settings
    AWS_REGION: str = "eu-central-1"
    
    class Config:
        env_file = [".env.production"]
        case_sensitive = True


# Use production settings
settings = ProductionSettings()
