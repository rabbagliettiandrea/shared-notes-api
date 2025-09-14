from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.security import HTTPBearer
from contextlib import asynccontextmanager
import uvicorn
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.redis_client import init_redis
from app.api.v1.api import api_router
# Import models to ensure tables are created
from app.models import User, Note, NoteShare, Tag, note_tags


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    # Note: Database tables are managed by Alembic migrations
    await init_redis()
    yield
    # Shutdown
    pass


class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    """Middleware to ensure HTTPS redirects use the correct protocol"""
    async def dispatch(self, request: Request, call_next):
        # Check if we're behind a proxy and the original request was HTTPS
        if request.headers.get("x-forwarded-proto") == "https":
            # Force the request to use HTTPS scheme
            request.scope["scheme"] = "https"
        elif request.headers.get("x-forwarded-ssl") == "on":
            # Alternative header for HTTPS detection
            request.scope["scheme"] = "https"
        
        response = await call_next(request)
        return response


app = FastAPI(
    title="Shared Notes API",
    description="A RESTful API for taking and sharing notes",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_HOSTS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add HTTPS redirect middleware for production
if not settings.DEBUG:
    app.add_middleware(HTTPSRedirectMiddleware)

# Add trusted host middleware for production
if not settings.DEBUG:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"]  # Configure with your actual domains in production
    )

# Include API router
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"message": "Shared Notes API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        proxy_headers=True,  # Enable proxy headers support
        forwarded_allow_ips="*"  # Allow forwarded headers from any IP
    )
