from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def internal_route():
    return {"message": "This is an internal endpoint"}