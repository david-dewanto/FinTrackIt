from fastapi import FastAPI
from .core.middleware import setup_cors_middleware
from .api.public import routes as public_routes
from .api.secure import routes as secure_routes
from .api.internal import routes as internal_routes

app = FastAPI(title="FastAPI Service")

# Setup CORS middleware
setup_cors_middleware(app)

# Include routers
app.include_router(public_routes.router, prefix="/public", tags=["public"])
app.include_router(secure_routes.router, prefix="/secure", tags=["secure"])
app.include_router(internal_routes.router, prefix="/internal", tags=["internal"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)