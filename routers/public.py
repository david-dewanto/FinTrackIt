from fastapi import APIRouter

router = APIRouter()

@router.get("/", tags=["Public Test Route"])
async def get_testroute():
    return "OK"
