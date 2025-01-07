from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class CompanyInfoResponse(BaseModel):
    symbol: str
    company_name: str
    sector: Optional[str] = None
    industry: Optional[str] = None
    market_cap: Optional[int] = None
    description: Optional[str] = None
    last_updated: datetime

    class Config:
        from_attributes = True

class CompanySymbolsResponse(BaseModel):
    symbols: List[str]
    count: int