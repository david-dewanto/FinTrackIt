# app/main.py
from fastapi import FastAPI, Depends, Request, HTTPException
from .core.middleware import setup_middleware
from .core.security import verify_access
from .core.rate_limiter import RateLimiter
from .api.public import routes as public_routes
from .api.secure import routes as secure_routes
from .api.internal import routes as internal_routes
from .api.auth import routes as auth_routes
from .models import models
from .db.database import engine

# Create database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="FastAPI Service")

# Initialize rate limiter
rate_limiter = RateLimiter()

# Setup CORS middleware
setup_middleware(app)

# Rate limiter dependency for public routes
async def check_public_rate_limit(request: Request):
    is_limited = await rate_limiter.is_rate_limited(request, endpoint_type="public")
    if is_limited:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again later."
        )

# Rate limiter dependency for secure routes
async def check_secure_rate_limit(request: Request):
    is_limited = await rate_limiter.is_rate_limited(request, endpoint_type="secure")
    if is_limited:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again later."
        )

# Include routers with dependencies
app.include_router(
    auth_routes.router, 
    prefix="/v1/auth", 
    tags=["auth"]
)
app.include_router(
    public_routes.router, 
    prefix="/v1/public", 
    tags=["public"],
    dependencies=[Depends(check_public_rate_limit)]
)
app.include_router(
    secure_routes.router, 
    prefix="/v1/secure", 
    tags=["secure"],
    dependencies=[Depends(verify_access), Depends(check_secure_rate_limit)]
)
app.include_router(
    internal_routes.router, 
    prefix="/v1/internal", 
    tags=["internal"],
    dependencies=[Depends(verify_access)]  # No rate limit for internal routes
)

@app.on_event("shutdown")
async def shutdown_event():
    await rate_limiter.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)