from fastapi import Security, HTTPException, status, Depends
from fastapi.security import APIKeyHeader
from db import check_api_key, get_user_from_api_key, get_historical_prices

api_key_header = APIKeyHeader(name="X-API-Key")

async def get_api_key(api_key_header: str = Security(api_key_header)) -> str:
    if check_api_key(api_key_header):
        return api_key_header
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing or invalid API key"
    )

async def get_user(api_key: str = Depends(get_api_key)):
    return get_user_from_api_key(api_key)

async def get_historical_data(api_key: str = Depends(get_api_key)):
    return get_historical_prices(api_key)