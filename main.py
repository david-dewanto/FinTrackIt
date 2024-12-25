# main.py
from fastapi import FastAPI, Depends
from routers import secure, public, auth, internal
from auth_utils import verify_token, verify_internal_token

app = FastAPI(
    title="Secure API Service",
    version="1.0.0",
)

# Public routes (no authentication required)
app.include_router(
    public.router,
    prefix="/api/v1/public"
)

# Authentication routes
app.include_router(
    auth.router,
    prefix="/api/v1/auth",
    tags=["Authentication"]
)

# Secure routes (requires valid JWT token)
app.include_router(
    secure.router,
    prefix="/api/v1/secure",
    dependencies=[Depends(verify_token)]
)

# Internal routes (requires internal JWT token)
app.include_router(
    internal.router,
    prefix="/api/v1/internal",
    dependencies=[Depends(verify_internal_token)]
)