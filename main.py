import uvicorn
from starlette.middleware.base import BaseHTTPMiddleware

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.redis_client import init_redis
from app.api.v1.api import api_router


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
        # Check if we're behind CloudFront or other proxy
        is_cloudfront = (
            "cloudfront" in request.headers.get("user-agent", "").lower() or
            "x-amz-cf-id" in request.headers or
            "x-from-cloudfront" in request.headers
        )
        
        # Check if we're behind a proxy and the original request was HTTPS
        is_https = (
            request.headers.get("x-forwarded-proto") == "https" or
            request.headers.get("x-forwarded-ssl") == "on" or
            request.headers.get("x-forwarded-scheme") == "https" or
            request.headers.get("x-forwarded-port") == "443"
        )
        
        # Special case: if we're behind CloudFront and the request URL is HTTPS,
        # but x-forwarded-proto is http, assume the original was HTTPS
        if is_cloudfront and str(request.url).startswith("https://"):
            is_https = True
        
        if is_https:
            # Force the request to use HTTPS scheme
            request.scope["scheme"] = "https"
            # Also set the host to use HTTPS
            if "host" in request.scope:
                host = request.scope["host"]
                if not host.startswith("https://"):
                    request.scope["host"] = f"https://{host}"
        response = await call_next(request)
        
        # If this is a redirect response, ensure it uses HTTPS
        if response.status_code in [301, 302, 303, 307, 308]:
            location = response.headers.get("location")
            if location:
                # Handle both absolute and relative URLs
                if location.startswith("http://"):
                    # Replace http:// with https:// in the location header
                    https_location = location.replace("http://", "https://", 1)
                    response.headers["location"] = https_location
                elif location.startswith("/") and is_https:
                    # For relative URLs, construct the full HTTPS URL
                    host = request.headers.get("host", "")
                    if host:
                        https_location = f"https://{host}{location}"
                        response.headers["location"] = https_location
        
        return response


app = FastAPI(
    title="Shared Notes API",
    description="A RESTful API for taking and sharing notes",
    version="1.0.0",
    lifespan=lifespan
)

# Add HTTPS redirect middleware FIRST (always active to handle proxy scenarios)
app.add_middleware(HTTPSRedirectMiddleware)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
