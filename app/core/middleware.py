# app/core/middleware.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from ..config.settings import settings

def setup_middleware(app: FastAPI):
    # Allow all origins by default - we'll handle access control through our API key system
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def internal_routes_protection(request: Request, call_next):
        try:
            # Only apply restrictions to internal routes
            if "/v1/internal/" in request.url.path:
                client_ip = request.client.host
                
                # Check if request comes from frontend server
                if client_ip != settings.FRONTEND_SERVER_IP:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "status": "error",
                            "code": "INVALID_IP",
                            "message": "Access to internal routes is restricted to authorized servers only",
                            "details": {
                                "client_ip": client_ip,
                                "path": request.url.path,
                                "method": request.method
                            }
                        }
                    )
                
                # For browser requests, verify it's from our frontend
                origin = request.headers.get("origin")
                if origin and origin != settings.FRONTEND_ORIGIN:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "status": "error",
                            "code": "INVALID_ORIGIN",
                            "message": "Invalid origin for internal routes access",
                            "details": {
                                "provided_origin": origin,
                                "path": request.url.path,
                                "method": request.method
                            }
                        }
                    )

            # If all checks pass, proceed with the request
            response = await call_next(request)
            return response
            
        except Exception as e:
            # Handle any unexpected errors with a proper response
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred while processing your request",
                    "details": {
                        "error_type": type(e).__name__,
                        "path": request.url.path
                    }
                }
            )