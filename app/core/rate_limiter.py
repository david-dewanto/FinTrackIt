from fastapi import HTTPException, Request
from redis import asyncio as aioredis
from typing import Optional
from datetime import datetime
from ..config.settings import settings
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self, redis_url: Optional[str] = None):
        # Use provided URL or fall back to settings
        self.redis_url = redis_url or settings.REDIS_URL
        try:
            self.redis = aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True,
                max_connections=10
            )
        except Exception as e:
            logger.error(f"Failed to initialize Redis connection: {str(e)}")
            # Initialize to None so we can handle the failed connection gracefully
            self.redis = None
        
        # Rate limits configuration
        self.RATE_LIMITS = {
            "public": {"requests": 150, "window": 3600},  # 100 requests per hour for public
            "secure": {"requests": 75, "window": 3600}  # 1000 requests per hour for secure
        }

    async def is_rate_limited(
        self, 
        request: Request,
        endpoint_type: str = "public"
    ) -> bool:
        # If Redis connection failed, don't rate limit
        if self.redis is None:
            return False

        try:
            # Get API key and token from headers
            api_key = request.headers.get("X-API-Key")
            auth_header = request.headers.get("Authorization")
            
            # Skip rate limiting for internal API key
            if api_key and api_key == settings.INTERNAL_API_KEY:
                return False

            # Determine identifier based on available credentials
            if api_key:
                identifier = f"apikey_{api_key}"
            elif auth_header and auth_header.startswith("Bearer "):
                # Use JWT token as identifier if present
                token = auth_header.split(" ")[1]
                identifier = f"jwt_{token}"
            else:
                # Fallback to IP for public routes
                identifier = f"ip_{request.client.host}"
            
            # Get rate limit config for endpoint type
            rate_config = self.RATE_LIMITS.get(endpoint_type, self.RATE_LIMITS["public"])
            
            # Create Redis key
            key = f"rate_limit:{endpoint_type}:{identifier}"
            
            try:
                # Test Redis connection
                await self.redis.ping()
            except Exception as e:
                logger.error(f"Redis ping failed: {str(e)}")
                return False

            # Get current request count
            requests = await self.redis.get(key)
            
            if requests is None:
                # First request, set initial counter
                await self.redis.setex(
                    key,
                    rate_config["window"],
                    1
                )
                return False
            
            request_count = int(requests)
            
            if request_count >= rate_config["requests"]:
                # Rate limit exceeded
                return True
            
            # Increment request counter
            await self.redis.incr(key)
            return False
            
        except Exception as e:
            logger.error(f"Rate limiter error: {str(e)}")
            # On error, allow request to proceed
            return False

    async def close(self):
        if self.redis is not None:
            try:
                await self.redis.close()
            except Exception as e:
                logger.error(f"Error closing Redis connection: {str(e)}")