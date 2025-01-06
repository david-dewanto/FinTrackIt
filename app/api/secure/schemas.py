from pydantic import BaseModel, EmailStr
from datetime import date
from typing import List

class EmailRequest(BaseModel):
    recipient_email: EmailStr
    subject: str
    body: str  

class EmailResponse(BaseModel):
    success: bool
    message: str

class StockPriceData(BaseModel):
    date: date  # Changed from datetime to date
    closing_price: int
    volume_thousands: int

    class Config:
        from_attributes = True
        json_encoders = {
            date: lambda v: v.strftime("%Y-%m-%d")  
        }

class StockPriceResponse(BaseModel):
    symbol: str
    prices: List[StockPriceData]

    class Config:
        from_attributes = True


class SharpeRatioResponse(BaseModel):
    stock_code: str
    sharpe_ratio: float
    avg_annual_return: float  # Average annual return over 3 years
    return_volatility: float  # Standard deviation of returns (annualized)
    risk_free_rate: float  # The risk-free rate used (5.5%)

    class Config:
        from_attributes = True