# app/core/middleware.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from ..config.settings import settings

def setup_middleware(app: FastAPI):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "https://www.fintrackit.my.id",
            "https://fintrackit.my.id",
            "http://localhost:3000"
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=[
            "Content-Type", 
            "Authorization", 
            "X-API-Key",
            "Access-Control-Allow-Origin",
            "Access-Control-Allow-Credentials",
            "Access-Control-Allow-Headers"
        ],
        expose_headers=["*"]
    )