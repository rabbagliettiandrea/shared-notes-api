import redis.asyncio as redis
from app.core.config import settings

redis_client = None


async def get_redis() -> redis.Redis:
    """Get Redis client"""
    return redis_client


async def init_redis():
    """Initialize Redis connection"""
    global redis_client
    redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    
    # Test connection
    try:
        await redis_client.ping()
        print("Redis connection established")
    except Exception as e:
        print(f"Redis connection failed: {e}")
        raise
