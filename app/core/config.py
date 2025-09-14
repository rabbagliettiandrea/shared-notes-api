from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    class Config:
        env_file = [".env"]
        case_sensitive = True


settings = Settings()
