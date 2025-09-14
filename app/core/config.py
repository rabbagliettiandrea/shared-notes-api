from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DEBUG: bool = True
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5433/shared_notes"
    REDIS_URL: str = "redis://localhost:6380"
    SECRET_KEY: str = "dev-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_DAYS: int = 7
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14
    ALLOWED_HOSTS: str = "d3e671tppt51wm.cloudfront.net,d2w8ulo83u5tax.cloudfront.net"


settings = Settings()