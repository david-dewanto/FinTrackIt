# app/api/public/routes.py

from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def public_route():
    return {"message": "This is a public endpoint"}