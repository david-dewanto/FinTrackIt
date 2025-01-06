from sqlalchemy import Column, String, Date
from sqlalchemy.sql import func
import uuid
from ..db.database import Base
from sqlalchemy import Column, String, DateTime, Integer, PrimaryKeyConstraint, BigInteger

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

class StockPrice(Base):
    __tablename__ = "stock_prices"
    
    symbol = Column(String)
    date = Column(Date)
    closing_price = Column(Integer)
    volume_thousands = Column(BigInteger) 

    __table_args__ = (PrimaryKeyConstraint('symbol', 'date'),)