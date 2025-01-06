# app/api/secure/routes.py

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from typing import Optional
import subprocess
from .schemas import (
    EmailRequest, EmailResponse, 
    StockPriceData, StockPriceResponse,
    SharpeRatioResponse  # Added new schemas
)
from sqlalchemy.orm import Session 
from datetime import datetime, timezone, timedelta, date
from ...db.database import get_db
import logging
import yfinance as yf
from sqlalchemy import and_
from ...models.models import StockPrice
import numpy as np  # Added for financial calculations
from ...models.models import SharpeRatioCache  

router = APIRouter()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@router.get("/")
async def secure_route(authorization: Optional[str] = Header(None)):
    return {"message": "This is a secure endpoint"}

@router.post("/send-email", response_model=EmailResponse, tags=["Email"])
def send_email(
    email_data: EmailRequest,
    db: Session = Depends(get_db),
    request: Request = None
) -> EmailResponse:
    """
    Send an email using the local Postfix server.
    Requires authentication.
    """
    try:
        logger.info(f"Attempting to send email to {email_data.recipient_email}")
        
        # Construct the mail command
        mail_command = [
            'mail',
            '-s', email_data.subject,
            '-a', 'From: noreply@fintrackit.my.id',
            '-a', 'Content-Type: text/html',
            email_data.recipient_email
        ]
        
        # Execute the mail command
        process = subprocess.Popen(
            mail_command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Send the email body and get the output
        stdout, stderr = process.communicate(input=email_data.body)
        
        # Check if the command was successful
        if process.returncode == 0:
            logger.info(f"Email sent successfully to {email_data.recipient_email}")
            return EmailResponse(
                success=True,
                message="Email sent successfully"
            )
        else:
            error_msg = f"Failed to send email: {stderr}"
            logger.error(error_msg)
            raise HTTPException(
                status_code=500,
                detail=error_msg
            )
            
    except Exception as e:
        error_msg = f"Error sending email: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(
            status_code=500,
            detail=error_msg
        )

@router.get("/stock-price/{stock_code}/{date_range}", response_model=StockPriceResponse)
async def get_stock_price(
    stock_code: str,
    date_range: str,
    db: Session = Depends(get_db)
):
    try:
        # Parse date range (assuming format: YYYY-MM-DD_YYYY-MM-DD)
        start_date = date.fromisoformat(date_range.split("_")[0])
        end_date = date.fromisoformat(date_range.split("_")[1])
                
        stock_code = f"{stock_code}.JK"

        # Check cache first
        cached_prices = db.query(StockPrice).filter(
            and_(
                StockPrice.symbol == stock_code,
                StockPrice.date >= start_date,
                StockPrice.date <= end_date
            )
        ).all()

        # If all dates are cached, return cached data
        if cached_prices and len(cached_prices) == (end_date - start_date).days + 1:
            prices = [
                StockPriceData(
                    date=price.date,
                    closing_price=price.closing_price,
                    volume_thousands=price.volume_thousands
                ) for price in cached_prices
            ]
            return StockPriceResponse(symbol=stock_code, prices=prices)

        # Fetch from yfinance
        try:
            stock = yf.Ticker(stock_code)
            hist = stock.history(start=start_date, end=end_date)
            
            if hist.empty:
                raise HTTPException(
                    status_code=404,
                    detail=f"No data found for stock {stock_code} in the specified date range"
                )

            # Prepare data for response and caching
            prices = []
            for entry_date, row in hist.iterrows():
                price_data = StockPriceData(
                    date=entry_date,
                    closing_price=int(row['Close']),
                    volume_thousands=int(row['Volume'] // 1000)
                )
                prices.append(price_data)

                # Cache the data
                db_price = StockPrice(
                    symbol=stock_code,
                    date=entry_date,
                    closing_price=int(row['Close']),
                    volume_thousands=int(row['Volume'] // 1000)
                )

                db.merge(db_price)

            db.commit()
            return StockPriceResponse(symbol=stock_code, prices=prices)

        except Exception as e:
            if "rate limit" in str(e).lower():
                raise HTTPException(
                    status_code=429,
                    detail="API rate limit reached. Please try again later or consider using a different time interval."
                )
            raise HTTPException(
                status_code=500,
                detail=f"Error fetching data from YFinance: {str(e)}"
            )

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid date format. Please use YYYY-MM-DD_YYYY-MM-DD format"
        )
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@router.get("/sharpe-ratio/{stock_code}", response_model=SharpeRatioResponse, tags=["Analysis"])
async def calculate_sharpe_ratio(
    stock_code: str,
    db: Session = Depends(get_db)
):
    """
    Calculate the Sharpe Ratio for a given stock over a 3-year period.
    Uses a risk-free rate of 5.5%. Results are cached and updated weekly.
    """
    try:
        # Check cache first
        cached_data = db.query(SharpeRatioCache).filter(
            SharpeRatioCache.stock_code == stock_code
        ).first()

        current_time = datetime.now(timezone.utc)
        
        # If cache exists and is less than 7 days old, use it
        if cached_data and (current_time - cached_data.last_updated) < timedelta(days=7):
            return SharpeRatioResponse(
                stock_code=stock_code,
                sharpe_ratio=cached_data.sharpe_ratio,
                avg_annual_return=cached_data.avg_annual_return,
                return_volatility=cached_data.return_volatility,
                risk_free_rate=0.055
            )

        # Calculate new values if cache doesn't exist or is old
        end_date = date.today()
        start_date = end_date - timedelta(days=3*365)  # 3 years
        
        stock_code_jk = f"{stock_code}.JK"
        risk_free_rate = 0.055  # 5.5%
        
        # Fetch stock data
        stock = yf.Ticker(stock_code_jk)
        hist = stock.history(start=start_date, end=end_date)
        
        if hist.empty:
            raise HTTPException(
                status_code=404,
                detail=f"No data found for stock {stock_code} in the specified date range"
            )
            
        # Calculate daily returns
        daily_returns = hist['Close'].pct_change().dropna()
        
        if len(daily_returns) < 252:  # Minimum 1 year of trading days
            raise HTTPException(
                status_code=400,
                detail="Insufficient data for Sharpe ratio calculation"
            )
            
        # Calculate metrics
        avg_daily_return = daily_returns.mean()
        daily_volatility = daily_returns.std()
        
        # Annualize metrics
        avg_annual_return = ((1 + avg_daily_return) ** 252) - 1
        annual_volatility = daily_volatility * np.sqrt(252)
        
        # Calculate Sharpe ratio
        excess_return = avg_annual_return - risk_free_rate
        sharpe_ratio = excess_return / annual_volatility if annual_volatility != 0 else 0

        # Round the values
        sharpe_ratio_rounded = float(round(sharpe_ratio, 4))
        avg_annual_return_rounded = float(round(avg_annual_return, 4))
        annual_volatility_rounded = float(round(annual_volatility, 4))

        # Update cache
        cache_entry = SharpeRatioCache(
            stock_code=stock_code,
            sharpe_ratio=sharpe_ratio_rounded,
            avg_annual_return=avg_annual_return_rounded,
            return_volatility=annual_volatility_rounded,
            last_updated=current_time
        )

        db.merge(cache_entry)  # Use merge instead of add to handle both insert and update
        db.commit()
        
        return SharpeRatioResponse(
            stock_code=stock_code,
            sharpe_ratio=sharpe_ratio_rounded,
            avg_annual_return=avg_annual_return_rounded,
            return_volatility=annual_volatility_rounded,
            risk_free_rate=risk_free_rate
        )

    except Exception as e:
        if "rate limit" in str(e).lower():
            raise HTTPException(
                status_code=429,
                detail="API rate limit reached. Please try again later."
            )
        logger.error(f"Error calculating Sharpe ratio: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating Sharpe ratio: {str(e)}"
        )