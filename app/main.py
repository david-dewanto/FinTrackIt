from fastapi import FastAPI
from .core.middleware import setup_middleware
from .api.public import routes as public_routes
from .api.secure import routes as secure_routes
from .api.internal import routes as internal_routes
from .api.auth import routes as auth_routes
from .models import models
from .db.database import engine

# Create database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="FastAPI Service")

# Setup CORS middleware
setup_middleware(app)

# Include routers
app.include_router(auth_routes.router, prefix="/v1/auth", tags=["auth"])
app.include_router(public_routes.router, prefix="/v1/public", tags=["public"])
app.include_router(secure_routes.router, prefix="/v1/secure", tags=["secure"])
app.include_router(internal_routes.router, prefix="/v1/internal", tags=["internal"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)