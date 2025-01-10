# app/api/secure/routes.py

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict
from .schemas import (
    EmailRequest, EmailResponse, 
    StockPriceData, StockPriceResponse,
    SharpeRatioResponse,
    PortfolioOptimizationRequest,
    PortfolioOptimizationResponse,
    PortfolioAllocation,
    FeasibleRangeRequest,
    FeasibleRangeResponse,
    RangeValues,
    PortfolioReturnResponse,
    PortfolioReturnRequest,
    ReturnCalculationTransaction
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
import numpy_financial as npf
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib

router = APIRouter()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@router.get("/")
async def secure_route():
    return {"message": "This is a secure endpoint"}

@router.post("/send-email", response_model=EmailResponse, tags=["Email"])
async def send_secure_email(request: EmailRequest):
    """
    Send email using SMTP with TLS support.
    Returns EmailResponse with success status and message.
    """
    try:        
        # Create message
        message = MIMEMultipart()
        message["From"] = "no-reply@mail.fintrackit.my.id"
        message["To"] = request.recipient_email
        message["Subject"] = request.subject
        message.attach(MIMEText(request.body, "html"))
        
        # Try different host configurations
        hosts_to_try = [
            ('172.17.0.1', 25),
            ('localhost', 25),
            ('127.0.0.1', 25)
        ]
        
        for host, port in hosts_to_try:            
            try:
                # Create SMTP connection with extended timeout
                with smtplib.SMTP(host, port, timeout=30) as server:
                    server.set_debuglevel(1)
                    
                    # Identify ourselves to SMTP server
                    server.ehlo("mail.fintrackit.my.id")
                    
                    # Start TLS encryption
                    server.starttls()
                    
                    # Send EHLO again after TLS
                    server.ehlo("mail.fintrackit.my.id")
                    
                    # Try sending the message
                    server.send_message(message)
                    return EmailResponse(success=True, message="Email sent successfully")
                    
            except smtplib.SMTPException as e:
                logger.error(f"SMTP error with {host}: {str(e)}")
                continue
            except Exception as e:
                logger.error(f"Error trying {host}: {str(e)}")
                continue
        
        # If we get here, all connection attempts failed
        return EmailResponse(
            success=False, 
            message="Failed to connect to any SMTP server"
        )
                
    except Exception as e:
        logger.error(f"General error in send_secure_email: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return EmailResponse(success=False, message=f"Failed to send email: {str(e)}")

@router.get("/stock-price/{stock_code}/{date_range}", response_model=StockPriceResponse)
async def get_stock_price(
    stock_code: str,
    date_range: str,
    db: Session = Depends(get_db)
):
    try:
        # Add debug logging
        date_parts = date_range.split("_")
        
        # Parse date range with extra validation
        if len(date_parts) != 2:
            raise ValueError("Date range must contain exactly two dates separated by underscore")
            
        start_date_str = date_parts[0]
        end_date_str = date_parts[1]
        
        try:
            start_date = date.fromisoformat(start_date_str)
            end_date = date.fromisoformat(end_date_str)
        except ValueError as e:
            logger.error(f"Date parsing error: {str(e)}")
            raise ValueError(f"Invalid date format. Dates must be in YYYY-MM-DD format. Got start={start_date_str}, end={end_date_str}")
                
        stock_code = f"{stock_code}.JK"

        # Generate list of expected trading days (excluding weekends)
        trading_days = set()
        current_date = start_date
        while current_date <= end_date:
            if current_date.weekday() < 5:  # Skip weekends
                trading_days.add(current_date)
            current_date += timedelta(days=1)

        # Check cache first
        cached_prices = db.query(StockPrice).filter(
            and_(
                StockPrice.symbol == stock_code,
                StockPrice.date >= start_date,
                StockPrice.date <= end_date
            )
        ).all()

        # Convert cached dates to a set for comparison
        cached_dates = {price.date.date() if isinstance(price.date, datetime) else price.date 
                       for price in cached_prices}

        # If we have all trading days in cache, return cached data
        if cached_dates >= trading_days:
            prices = [
                StockPriceData(
                    date=price.date.date() if isinstance(price.date, datetime) else price.date,  # Convert to date
                    closing_price=price.closing_price,
                    volume_thousands=price.volume_thousands
                ) for price in sorted(cached_prices, key=lambda x: x.date)
            ]
            return StockPriceResponse(symbol=stock_code, prices=prices)

        # If not fully cached, fetch from YFinance
        try:
            stock = yf.Ticker(stock_code)
            hist = stock.history(start=start_date, end=end_date + timedelta(days=1))
            
            if not hist.empty:
                # Get ALL existing dates for this stock to avoid duplicates
                existing_prices = db.query(StockPrice).filter(
                    StockPrice.symbol == stock_code
                ).all()
                existing_dates = {price.date.date() if isinstance(price.date, datetime) else price.date 
                                for price in existing_prices}

                # Only insert dates that don't exist
                new_prices = []
                for entry_date, row in hist.iterrows():
                    # Convert entry_date to date object
                    entry_date = entry_date.date()                    
                    # Check if this date exists
                    if entry_date not in existing_dates:
                        db_price = StockPrice(
                            symbol=stock_code,
                            date=entry_date,
                            closing_price=int(row['Close']),
                            volume_thousands=int(row['Volume'] // 1000)
                        )
                        new_prices.append(db_price)

                if new_prices:
                    try:
                        db.bulk_save_objects(new_prices)
                        db.commit()
                    except Exception as e:
                        db.rollback()
                        logger.error(f"Error committing to database: {str(e)}")
                        raise HTTPException(
                            status_code=500,
                            detail=f"Error saving to database: {str(e)}"
                        )

        except Exception as e:
            if "rate limit" in str(e).lower():
                logger.warning("YFinance rate limit reached")
                raise HTTPException(
                    status_code=429,
                    detail="API rate limit reached. Please try again later."
                )
            logger.error(f"YFinance error: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error fetching data from YFinance: {str(e)}"
            )

        # Return all prices for the requested range
        all_prices = db.query(StockPrice).filter(
            and_(
                StockPrice.symbol == stock_code,
                StockPrice.date >= start_date,
                StockPrice.date <= end_date
            )
        ).order_by(StockPrice.date).all()
        
        if not all_prices:
            logger.warning(f"No data found for {stock_code} in date range")
            raise HTTPException(
                status_code=404,
                detail=f"No data found for stock {stock_code} in the specified date range"
            )
            
        prices = [
            StockPriceData(
                date=price.date.date() if isinstance(price.date, datetime) else price.date,  # Convert to date
                closing_price=price.closing_price,
                volume_thousands=price.volume_thousands
            ) for price in all_prices
        ]
        
        return StockPriceResponse(symbol=stock_code, prices=prices)

    except ValueError as e:
        logger.error(f"Value error in get_stock_price: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid date format. Please use YYYY-MM-DD_YYYY-MM-DD format. Error: {str(e)}"
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

@router.post("/calculate-portfolio-returns", response_model=PortfolioReturnResponse, tags=["Analysis"])
async def calculate_portfolio_returns(
    request: PortfolioReturnRequest,
    db: Session = Depends(get_db)
):
    """
    Calculate portfolio-level TWR and MWR.
    
    TWR (Time-Weighted Return):
    - Eliminates the impact of cash flows
    - Each holding period return is weighted equally
    - Uses geometric linking of returns
    
    MWR (Money-Weighted Return):
    - Internal Rate of Return (IRR) calculation
    - Considers timing and size of cash flows
    - Uses iterative solver for better numerical stability 
    """
    try:
        if not request.transactions:
            raise HTTPException(status_code=400, detail="No transactions provided")

        # Group transactions by stock code to get latest prices
        stock_transactions: Dict[str, List[ReturnCalculationTransaction]] = {}
        for tx in request.transactions:
            if tx.stock_code not in stock_transactions:
                stock_transactions[tx.stock_code] = []
            stock_transactions[tx.stock_code].append(tx)

        # Get latest prices for all stocks
        today = datetime.now(timezone.utc).date()
        week_ago = (today - timedelta(days=7))
        date_range = f"{week_ago.isoformat()}_{today.isoformat()}"
        
        latest_prices = {}
        latest_dates = {}
        
        for stock_code in stock_transactions.keys():
            try:
                latest_price_data = await get_stock_price(stock_code, date_range, db)
                if not latest_price_data.prices:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Could not fetch latest price for stock {stock_code}"
                    )
                
                latest_prices[stock_code] = latest_price_data.prices[-1].closing_price
                latest_dates[stock_code] = latest_price_data.prices[-1].date
                
            except HTTPException as e:
                if e.status_code == 404:
                    raise HTTPException(
                        status_code=404,
                        detail=f"No recent trading data available for stock {stock_code}"
                    )
                raise e

        # Calculate portfolio TWR by weighting individual stock returns
        total_investment = 0
        weighted_twr = 0
        portfolio_cash_flows = []
        portfolio_dates = []

        def calculate_twr(transactions, latest_price):
            """
            Calculate Time-Weighted Return using geometric linking of holding period returns.
            Handles multiple transactions on same date.
            """
            if not transactions:
                return 0.0
                
            # Sort transactions chronologically
            sorted_txs = sorted(transactions, key=lambda x: x.transaction_date)
            
            # Group transactions by date
            from collections import defaultdict
            date_groups = defaultdict(list)
            for tx in sorted_txs:
                date_groups[tx.transaction_date].append(tx)
            
            # Process each date's transactions
            holding_period_returns = []
            current_shares = 0
            last_price = None
            last_date = None
            
            for date, txs in sorted(date_groups.items()):
                day_shares = current_shares
                day_value = day_shares * last_price if last_price else 0
                
                # Process all transactions for the day
                for tx in txs:
                    if tx.transaction_type == "buy":
                        day_value += tx.total_value
                        day_shares += tx.quantity
                    else:  # sell
                        day_value -= tx.total_value
                        day_shares -= tx.quantity
                
                # Calculate day's ending price (weighted average)
                if day_shares > 0:
                    day_price = day_value / day_shares
                else:
                    day_price = txs[-1].price_per_share
                
                # Calculate return for the period if we had shares
                if current_shares > 0 and last_price is not None:
                    r = (day_price / last_price) - 1
                    holding_period_returns.append(1 + r)
                
                current_shares = day_shares
                last_price = day_price
                last_date = date
            
            # Add final period return if we still have shares
            if current_shares > 0 and last_price is not None:
                final_return = (latest_price / last_price) - 1
                holding_period_returns.append(1 + final_return)
            
            # Calculate cumulative TWR using geometric linking
            if holding_period_returns:
                cumulative_twr = np.prod(holding_period_returns) - 1
                return float(cumulative_twr)
            return 0.0

        def calculate_mwr(transactions, end_date):
            """
            Calculate Money-Weighted Return (IRR) using robust numerical methods.
            """
            if not transactions:
                return 0.0
                
            sorted_txs = sorted(transactions, key=lambda x: x.transaction_date)
            
            # Prepare cash flows and dates for IRR calculation
            cash_flows = []
            dates = []
            
            for tx in sorted_txs:
                if tx.transaction_type == "buy":
                    cash_flows.append(-tx.total_value)
                else:  # sell
                    cash_flows.append(tx.total_value)
                dates.append(tx.transaction_date)
            
            if len(cash_flows) < 2:
                return 0.0
                
            # Convert dates to year fractions
            start_date = dates[0]
            year_fractions = [(d - start_date).total_seconds() / (365.25 * 24 * 60 * 60) 
                            for d in dates]
            
            # NPV calculation helper
            def npv(rate, cash_flows, year_fractions):
                return sum(cf / (1 + rate) ** t 
                        for cf, t in zip(cash_flows, year_fractions))
            
            # Use secant method for more reliable IRR calculation
            def secant_method(f, x0, x1, iterations=100, tolerance=1e-6):
                for _ in range(iterations):
                    fx0 = f(x0)
                    fx1 = f(x1)
                    if abs(fx1) < tolerance:
                        return x1
                    if fx0 == fx1:
                        break
                    x_new = x1 - fx1 * (x1 - x0) / (fx1 - fx0)
                    x0, x1 = x1, x_new
                return x1

            try:
                # Find IRR using secant method
                irr = secant_method(
                    lambda r: npv(r, cash_flows, year_fractions),
                    0.0,  # Initial guess 1
                    0.1   # Initial guess 2
                )
                return float(max(min(irr, 10), -0.99))  # Bound the result
            except:
                return 0.0

        # Calculate portfolio level returns
        for stock_code, transactions in stock_transactions.items():
            latest_price = latest_prices[stock_code]
            
            # Calculate investment for TWR weighting
            stock_investment = sum(
                tx.total_value 
                for tx in transactions 
                if tx.transaction_type == "buy"
            )
            total_investment += stock_investment
            
            # Add to weighted TWR
            stock_twr = calculate_twr(transactions, latest_price)
            weighted_twr += stock_twr * stock_investment
            
            # Collect cash flows for portfolio MWR
            for tx in transactions:
                portfolio_cash_flows.append(
                    -tx.total_value if tx.transaction_type == "buy" else tx.total_value
                )
                portfolio_dates.append(tx.transaction_date)
            
            # Add final value to portfolio cash flows
            current_shares = sum(
                tx.quantity * (1 if tx.transaction_type == "buy" else -1)
                for tx in transactions
            )
            if current_shares > 0:
                final_value = current_shares * latest_price
                portfolio_cash_flows.append(final_value)
                portfolio_dates.append(datetime.combine(
                    latest_dates[stock_code],
                    datetime.min.time()
                ).replace(tzinfo=timezone.utc))

        # Calculate final portfolio returns
        portfolio_twr = weighted_twr / total_investment if total_investment > 0 else 0
        portfolio_mwr = calculate_mwr(
            [
                ReturnCalculationTransaction(
                    id="portfolio",
                    uid="portfolio",
                    stock_code="PORTFOLIO",
                    transaction_type="buy" if cf < 0 else "sell",
                    quantity=1,
                    price_per_share=abs(cf),
                    total_value=abs(cf),
                    transaction_date=d
                )
                for cf, d in zip(portfolio_cash_flows, portfolio_dates)
            ],
            max(portfolio_dates)
        )

        return PortfolioReturnResponse(
            portfolio_twr=round(float(portfolio_twr), 4),
            portfolio_mwr=round(float(portfolio_mwr), 4),
            calculation_date=datetime.now(timezone.utc),
            start_date=min(portfolio_dates),
            end_date=max(latest_dates.values()),
            stock_breakdown={}  # Empty dict since we no longer calculate individual returns
        )

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error calculating portfolio returns: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating portfolio returns: {str(e)}"
        )