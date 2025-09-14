from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    DEBUG: bool
    DATABASE_URL: str
    REDIS_URL: str
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_DAYS: int
    REFRESH_TOKEN_EXPIRE_DAYS: int
    ALLOWED_HOSTS: str
    
    class Config:
        env_file = [".env"]
        case_sensitive = True


settings = Settings()
