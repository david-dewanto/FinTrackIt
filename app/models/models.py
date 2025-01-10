from sqlalchemy import Column, String, Date, Enum, UniqueConstraint
from sqlalchemy.sql import func
import uuid
from ..db.database import Base
from sqlalchemy import Column, String, DateTime, Integer, Boolean, BigInteger,Float
import enum
from datetime import datetime, timezone, date

class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    api_key = Column(String, unique=True, index=True)
    full_name = Column(String)
    application_name = Column(String)
    organization = Column(String)
    email = Column(String, unique=True, index=True)  
    phone_number = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# In models.py, update StockPrice class

class StockPrice(Base):
    __tablename__ = "stock_prices"
    
    symbol = Column(String, primary_key=True)
    date = Column(DateTime(timezone=True), primary_key=True)
    closing_price = Column(Integer)
    volume_thousands = Column(Integer)
    
    __table_args__ = (
        UniqueConstraint('symbol', 'date', name='stock_prices_pkey'),
    )
    
    @classmethod
    def normalize_date(cls, date):
        """Normalize date to UTC midnight"""
        if isinstance(date, datetime):
            # If datetime has timezone, convert to UTC
            if date.tzinfo is not None:
                date = date.astimezone(timezone.utc)
            # Set time to midnight UTC
            return datetime.combine(date.date(), datetime.min.time()).replace(tzinfo=timezone.utc)
        else:
            # If date object, convert to datetime at midnight UTC
            return datetime.combine(date, datetime.min.time()).replace(tzinfo=timezone.utc)

class SharpeRatioCache(Base):
    __tablename__ = "sharpe_ratio_cache"
    
    stock_code = Column(String, primary_key=True)
    sharpe_ratio = Column(Float)
    avg_annual_return = Column(Float)
    return_volatility = Column(Float)
    last_updated = Column(DateTime(timezone=True), server_default=func.now())

class TransactionType(str, enum.Enum):
    BUY = "buy"
    SELL = "sell"

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    uid = Column(String, index=True, nullable=False)  # Firebase user ID
    stock_code = Column(String, nullable=False)
    transaction_type = Column(Enum(TransactionType), nullable=False)
    quantity = Column(Integer, nullable=False)
    price_per_share = Column(Integer, nullable=False)
    total_value = Column(Integer, nullable=False)
    transaction_date = Column(DateTime(timezone=True), nullable=False)

class CompanyInfo(Base):
    __tablename__ = "company_info"
    
    symbol = Column(String, primary_key=True)  
    company_name = Column(String)
    sector = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    market_cap = Column(BigInteger, nullable=True)
    description = Column(String, nullable=True)
    last_updated = Column(DateTime(timezone=True), server_default=func.now())

class PriceTriggerType(str, enum.Enum):
    ABOVE = "above"
    BELOW = "below"

class StockAlert(Base):
    __tablename__ = "stock_alerts"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    uid = Column(String, index=True, nullable=False)  # Firebase user ID
    stock_code = Column(String, nullable=False)
    trigger_price = Column(Integer, nullable=False)
    trigger_type = Column(Enum(PriceTriggerType), nullable=False)
    notification_hour = Column(Integer, nullable=False)  # 0-23 hour in UTC
    is_repeating = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    last_checked = Column(DateTime(timezone=True), nullable=True)
    last_notified = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())