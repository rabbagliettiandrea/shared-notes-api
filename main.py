from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from contextlib import asynccontextmanager
import uvicorn

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


app = FastAPI(
    title="Shared Notes API",
    description="A RESTful API for taking and sharing notes",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_HOSTS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
        reload=True
    )
