# app/api/secure/routes.py

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from typing import Optional, List
import subprocess
from .schemas import (
    EmailRequest, EmailResponse, 
    StockPriceData, StockPriceResponse,
    SharpeRatioResponse,
    PortfolioOptimizationRequest,
    PortfolioOptimizationResponse,
    PortfolioAllocation,
    FeasibleRangeRequest,
    FeasibleRangeResponse,
    RangeValues
)
from sqlalchemy.orm import Session 
from datetime import datetime, timezone, timedelta, date
from ...db.database import get_db
import logging
import yfinance as yf
from sqlalchemy import and_
from ...models.models import StockPrice, SharpeRatioCache
import numpy as np
from scipy.optimize import minimize

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
        
        # Format the date range string
        date_range = f"{start_date.isoformat()}_{end_date.isoformat()}"
        
        # Use the stock-price endpoint to get the data
        stock_data = await get_stock_price(stock_code, date_range, db)
        
        if not stock_data.prices:
            raise HTTPException(
                status_code=404,
                detail=f"No data found for stock {stock_code} in the specified date range"
            )
            
        # Convert prices to numpy array for calculations
        closing_prices = np.array([price.closing_price for price in stock_data.prices])
        
        # Calculate daily returns
        daily_returns = np.diff(closing_prices) / closing_prices[:-1]
        
        if len(daily_returns) < 252:  # Minimum 1 year of trading days
            raise HTTPException(
                status_code=400,
                detail="Insufficient data for Sharpe ratio calculation"
            )
            
        # Calculate metrics
        avg_daily_return = np.mean(daily_returns)
        daily_volatility = np.std(daily_returns)
        
        # Annualize metrics
        avg_annual_return = ((1 + avg_daily_return) ** 252) - 1
        annual_volatility = daily_volatility * np.sqrt(252)
        
        # Calculate Sharpe ratio with risk-free rate of 5.5%
        risk_free_rate = 0.055
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

        db.merge(cache_entry)
        db.commit()
        
        return SharpeRatioResponse(
            stock_code=stock_code,
            sharpe_ratio=sharpe_ratio_rounded,
            avg_annual_return=avg_annual_return_rounded,
            return_volatility=annual_volatility_rounded,
            risk_free_rate=risk_free_rate
        )

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error calculating Sharpe ratio: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating Sharpe ratio: {str(e)}"
        )
    
@router.post("/optimize-portfolio", response_model=PortfolioOptimizationResponse, tags=["Analysis"])
async def optimize_portfolio(
    portfolio_request: PortfolioOptimizationRequest,
    db: Session = Depends(get_db)
):
    """
    Optimize portfolio weights based on Modern Portfolio Theory.
    Either minimizes volatility for a target minimum return or maximizes return for a target maximum volatility.
    Uses 3-year historical data and assumes no short selling.
    """
    try:
        # Validate request
        if len(portfolio_request.stock_codes) > 5:
            raise HTTPException(
                status_code=400,
                detail="Maximum 5 stocks allowed for optimization"
            )
        
        if len(portfolio_request.stock_codes) < 2:
            raise HTTPException(
                status_code=400,
                detail="Minimum 2 stocks required for optimization"
            )
            
        if portfolio_request.target_return is None and portfolio_request.target_volatility is None:
            raise HTTPException(
                status_code=400,
                detail="Must specify either target_return or target_volatility"
            )
            
        if portfolio_request.target_return is not None and portfolio_request.target_volatility is not None:
            raise HTTPException(
                status_code=400,
                detail="Cannot specify both target_return and target_volatility"
            )

        # Get historical data for all stocks
        end_date = date.today()
        start_date = end_date - timedelta(days=3*365)  # 3 years
        date_range = f"{start_date.isoformat()}_{end_date.isoformat()}"
        
        # Fetch and process data for all stocks
        stock_returns = {}
        for stock_code in portfolio_request.stock_codes:
            # Get stock data using existing endpoint
            stock_data = await get_stock_price(stock_code, date_range, db)
            
            if not stock_data.prices:
                raise HTTPException(
                    status_code=404,
                    detail=f"No data found for stock {stock_code}"
                )
                
            # Calculate daily returns
            prices = np.array([price.closing_price for price in stock_data.prices])
            returns = np.diff(prices) / prices[:-1]
            stock_returns[stock_code] = returns

        # Ensure all stocks have the same number of data points
        min_length = min(len(returns) for returns in stock_returns.values())
        if min_length < 252:  # Minimum 1 year of data
            raise HTTPException(
                status_code=400,
                detail="Insufficient historical data for optimization"
            )
            
        # Trim all returns to the same length
        for stock_code in stock_returns:
            stock_returns[stock_code] = stock_returns[stock_code][-min_length:]

        # Create returns matrix and calculate mean returns and covariance
        returns_matrix = np.array([stock_returns[code] for code in portfolio_request.stock_codes])
        mean_returns = np.mean(returns_matrix, axis=1)
        cov_matrix = np.cov(returns_matrix)
        
        # Annualize returns and covariance
        mean_returns = (1 + mean_returns) ** 252 - 1
        cov_matrix = cov_matrix * 252

        # Define optimization constraints
        constraints = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}  # weights sum to 1
        ]
        
        bounds = [(0, 1) for _ in portfolio_request.stock_codes]  # no short selling
        
        # Initial guess (equal weights)
        n_assets = len(portfolio_request.stock_codes)
        initial_weights = np.array([1/n_assets] * n_assets)

        # Define objective function based on optimization target
        if portfolio_request.target_return is not None:
            # Minimize volatility for target minimum return
            target_return = portfolio_request.target_return
            
            def objective(weights):
                return np.sqrt(weights.T @ cov_matrix @ weights)
            
            constraints.append({
                'type': 'ineq',
                'fun': lambda x: mean_returns @ x - target_return  # Return should be >= target
            })
            
            optimization_criteria = "return"
            target_value = target_return
        else:
            # Maximize return for target maximum volatility
            target_vol = portfolio_request.target_volatility
            
            def objective(weights):
                return -mean_returns @ weights  # negative for maximization
            
            constraints.append({
                'type': 'ineq',
                'fun': lambda x: target_vol - np.sqrt(x.T @ cov_matrix @ x)  # Volatility should be <= target
            })
            
            optimization_criteria = "volatility"
            target_value = target_vol

        # Perform optimization
        try:
            result = minimize(
                objective,
                initial_weights,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints
            )
            
            if not result.success:
                raise HTTPException(
                    status_code=400,
                    detail="Could not find optimal portfolio for given constraints"
                )
        except:
            raise HTTPException(
                status_code=400,
                detail="Optimization failed. Target might be infeasible."
            )

        # Calculate portfolio metrics
        optimal_weights = result.x
        portfolio_return = mean_returns @ optimal_weights
        portfolio_volatility = np.sqrt(optimal_weights.T @ cov_matrix @ optimal_weights)
        
        # Calculate Sharpe ratio
        risk_free_rate = 0.055  # 5.5%
        sharpe_ratio = (portfolio_return - risk_free_rate) / portfolio_volatility

        # Prepare response with 4 decimal precision
        allocations = [
            PortfolioAllocation(
                stock_code=code,
                weight=round(float(weight), 4)
            )
            for code, weight in zip(portfolio_request.stock_codes, optimal_weights)
        ]

        return PortfolioOptimizationResponse(
            allocations=allocations,
            expected_return=round(float(portfolio_return), 4),
            expected_volatility=round(float(portfolio_volatility), 4),
            sharpe_ratio=round(float(sharpe_ratio), 4),
            risk_free_rate=round(risk_free_rate, 4),
            optimization_criteria=optimization_criteria,
            target_value=round(float(target_value), 4)
        )

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error optimizing portfolio: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error optimizing portfolio: {str(e)}"
        )
    
@router.post("/portfolio-ranges", response_model=FeasibleRangeResponse, tags=["Analysis"])
async def get_portfolio_ranges(
    range_request: FeasibleRangeRequest,
    db: Session = Depends(get_db)
):
    """
    Calculate feasible ranges for target return and target volatility
    based on the selected stocks' historical data.
    """
    try:
        # Validate request
        if len(range_request.stock_codes) > 5:
            raise HTTPException(
                status_code=400,
                detail="Maximum 5 stocks allowed"
            )
        
        if len(range_request.stock_codes) < 2:
            raise HTTPException(
                status_code=400,
                detail="Minimum 2 stocks required"
            )

        # Get historical data for all stocks
        end_date = date.today()
        start_date = end_date - timedelta(days=3*365)  # 3 years
        date_range = f"{start_date.isoformat()}_{end_date.isoformat()}"
        
        # Fetch and process data for all stocks
        stock_returns = {}
        for stock_code in range_request.stock_codes:
            # Get stock data using existing endpoint
            stock_data = await get_stock_price(stock_code, date_range, db)
            
            if not stock_data.prices:
                raise HTTPException(
                    status_code=404,
                    detail=f"No data found for stock {stock_code}"
                )
                
            # Calculate daily returns
            prices = np.array([price.closing_price for price in stock_data.prices])
            returns = np.diff(prices) / prices[:-1]
            stock_returns[stock_code] = returns

        # Ensure all stocks have the same number of data points
        min_length = min(len(returns) for returns in stock_returns.values())
        if min_length < 252:  # Minimum 1 year of data
            raise HTTPException(
                status_code=400,
                detail="Insufficient historical data"
            )
            
        # Trim all returns to the same length
        for stock_code in stock_returns:
            stock_returns[stock_code] = stock_returns[stock_code][-min_length:]

        # Create returns matrix and calculate mean returns and covariance
        returns_matrix = np.array([stock_returns[code] for code in range_request.stock_codes])
        mean_returns = np.mean(returns_matrix, axis=1)
        cov_matrix = np.cov(returns_matrix)
        
        # Annualize returns and covariance
        mean_returns = (1 + mean_returns) ** 252 - 1
        cov_matrix = cov_matrix * 252

        # Find minimum volatility portfolio
        def min_vol_objective(weights):
            return np.sqrt(weights.T @ cov_matrix @ weights)

        constraints = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}  # weights sum to 1
        ]
        bounds = [(0, 1) for _ in range_request.stock_codes]  # no short selling
        
        n_assets = len(range_request.stock_codes)
        initial_weights = np.array([1/n_assets] * n_assets)

        min_vol_result = minimize(
            min_vol_objective,
            initial_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )

        if not min_vol_result.success:
            raise HTTPException(
                status_code=500,
                detail="Failed to calculate minimum volatility portfolio"
            )

        # Calculate metrics for minimum volatility portfolio
        min_vol_weights = min_vol_result.x
        min_return = float(mean_returns @ min_vol_weights)
        min_volatility = float(np.sqrt(min_vol_weights.T @ cov_matrix @ min_vol_weights))

        # Find maximum return (will be the single stock with highest return)
        max_return = float(np.max(mean_returns))
        
        # Calculate maximum volatility portfolio (maximize return)
        def max_return_objective(weights):
            return -mean_returns @ weights  # Negative for maximization

        max_return_result = minimize(
            max_return_objective,
            initial_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )

        if not max_return_result.success:
            raise HTTPException(
                status_code=500,
                detail="Failed to calculate maximum return portfolio"
            )

        max_return_weights = max_return_result.x
        max_volatility = float(np.sqrt(max_return_weights.T @ cov_matrix @ max_return_weights))

        return FeasibleRangeResponse(
            return_range=RangeValues(
                min=round(min_return, 4),
                max=round(max_return, 4)
            ),
            volatility_range=RangeValues(
                min=round(min_volatility, 4),
                max=round(max_volatility, 4)
            )
        )

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error calculating portfolio ranges: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating portfolio ranges: {str(e)}"
        )