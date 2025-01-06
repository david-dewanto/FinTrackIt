from pydantic import BaseModel, EmailStr
from datetime import date, datetime
from typing import List, Optional, Dict
from enum import Enum

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

class TransactionType(str, Enum):
    BUY = "buy"
    SELL = "sell"

# Request schemas
class ReturnCalculationTransaction(BaseModel):
    stock_code: str
    transaction_type: TransactionType
    quantity: int
    price_per_share: int
    total_value: int
    transaction_date: datetime

class TWRRequest(BaseModel):
    transactions: List[ReturnCalculationTransaction]

class MWRRequest(BaseModel):
    transactions: List[ReturnCalculationTransaction]

# Response schemas
class TWRResponse(BaseModel):
    stock_code: str
    twr: float  # Time-Weighted Return as a decimal (e.g., 0.15 for 15%)
    calculation_date: datetime
    start_date: datetime  # First transaction date
    end_date: datetime   # Last transaction date or current date
    
    class Config:
        from_attributes = True

class MWRResponse(BaseModel):
    stock_code: str
    mwr: float  # Money-Weighted Return (IRR) as a decimal
    calculation_date: datetime
    start_date: datetime
    end_date: datetime
    
    class Config:
        from_attributes = True

class PortfolioReturnResponse(BaseModel):
    portfolio_twr: float
    portfolio_mwr: float
    calculation_date: datetime
    start_date: datetime
    end_date: datetime
    stock_breakdown: Dict[str, Dict[str, float]]  # e.g., {"BBCA": {"twr": 0.083, "mwr": 0.0825}}
    
    class Config:
        from_attributes = True

class PortfolioReturnRequest(BaseModel):
    transactions: List[ReturnCalculationTransaction]