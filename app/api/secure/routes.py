# app/api/secure/routes.py

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from typing import Optional
import subprocess
from .schemas import EmailRequest, EmailResponse, StockPriceData, StockPriceResponse
from sqlalchemy.orm import Session 
from datetime import date 
from ...db.database import get_db
import logging
import yfinance as yf
from sqlalchemy import and_
from ...models.models import StockPrice

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