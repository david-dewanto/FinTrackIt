from fastapi import HTTPException, Request
from redis import asyncio as aioredis
from typing import Optional
from datetime import datetime
from ..config.settings import settings

class RateLimiter:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis = aioredis.from_url(redis_url, encoding="utf-8", decode_responses=True)
        
        # Rate limits configuration
        self.RATE_LIMITS = {
            "public": {"requests": 100, "window": 3600},  # 100 requests per hour for public
            "secure": {"requests": 1000, "window": 3600}  # 1000 requests per hour for secure
        }

    async def is_rate_limited(
        self, 
        request: Request,
        endpoint_type: str = "public"
    ) -> bool:
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
            # Log the error in production
            print(f"Rate limiter error: {str(e)}")
            # On error, allow request to proceed
            return False

    async def close(self):
        await self.redis.close()