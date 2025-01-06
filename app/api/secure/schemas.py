from pydantic import BaseModel, EmailStr
from datetime import date
from typing import List, Optional

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

class PortfolioOptimizationRequest(BaseModel):
    stock_codes: List[str]
    target_return: Optional[float] = None
    target_volatility: Optional[float] = None

class PortfolioAllocation(BaseModel):
    stock_code: str
    weight: float

class PortfolioOptimizationResponse(BaseModel):
    allocations: List[PortfolioAllocation]
    expected_return: float
    expected_volatility: float
    sharpe_ratio: float
    risk_free_rate: float = 0.055  # 5.5%
    optimization_criteria: str  # Either "return" or "volatility"
    target_value: float  # The target that was used (either return or volatility)

    class Config:
        from_attributes = True

class FeasibleRangeRequest(BaseModel):
    stock_codes: List[str]

class RangeValues(BaseModel):
    min: float
    max: float

class FeasibleRangeResponse(BaseModel):
    return_range: RangeValues
    volatility_range: RangeValues

    class Config:
        from_attributes = True