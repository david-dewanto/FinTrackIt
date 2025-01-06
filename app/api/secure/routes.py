# app/api/secure/routes.py

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from typing import Optional, List, Dict
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
from .schemas import (
    TWRRequest, TWRResponse,
    MWRRequest, MWRResponse
)
import numpy_financial as npf

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
        
        # For single-day queries, adjust end_date to include the next day
        # This ensures yfinance returns data for the requested date
        is_single_day = start_date == end_date
        yf_end_date = end_date + timedelta(days=1) if is_single_day else end_date
                
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
        expected_days = (end_date - start_date).days + 1
        if cached_prices and len(cached_prices) == expected_days:
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
            hist = stock.history(start=start_date, end=yf_end_date)
            
            if hist.empty:
                raise HTTPException(
                    status_code=404,
                    detail=f"No data found for stock {stock_code} in the specified date range"
                )

            # Prepare data for response and caching
            prices = []
            for entry_date, row in hist.iterrows():
                # Skip data beyond the requested end_date for single-day queries
                if is_single_day and entry_date.date() > end_date:
                    continue
                    
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
            
            if not prices:
                raise HTTPException(
                    status_code=404,
                    detail=f"No data found for stock {stock_code} on {start_date}"
                )
                
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

@router.post("/calculate-portfolio-returns", response_model=PortfolioReturnResponse, tags=["Analysis"])
async def calculate_portfolio_returns(
    request: PortfolioReturnRequest,
    db: Session = Depends(get_db)
):
    """
    Calculate both TWR and MWR for the entire portfolio, including individual stock breakdowns.
    Uses latest market prices for current holdings.
    """
    try:
        if not request.transactions:
            raise HTTPException(
                status_code=400,
                detail="No transactions provided"
            )

        # Group transactions by stock code
        stock_transactions: Dict[str, List[ReturnCalculationTransaction]] = {}
        for tx in request.transactions:
            if tx.stock_code not in stock_transactions:
                stock_transactions[tx.stock_code] = []
            stock_transactions[tx.stock_code].append(tx)

        # Get latest prices for all stocks - look back up to 7 days to handle holidays
        today = date.today()
        week_ago = today - timedelta(days=7)
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
                
                # Get the most recent price from available data
                latest_prices[stock_code] = latest_price_data.prices[-1].closing_price
                latest_dates[stock_code] = datetime.combine(
                    latest_price_data.prices[-1].date.date() if isinstance(latest_price_data.prices[-1].date, datetime)
                    else latest_price_data.prices[-1].date,
                    datetime.min.time()
                )
                
            except HTTPException as e:
                if e.status_code == 404:
                    raise HTTPException(
                        status_code=404,
                        detail=f"No recent trading data available for stock {stock_code}"
                    )
                raise e

        stock_breakdown = {}
        portfolio_cash_flows = []
        portfolio_dates = []
        
        # Calculate returns for each stock and prepare portfolio-level data
        for stock_code, transactions in stock_transactions.items():
            sorted_txs = sorted(transactions, key=lambda x: x.transaction_date)
            latest_price = latest_prices[stock_code]
            
            # Calculate individual stock TWR
            holding_period_returns = []
            current_holdings = 0
            last_value = 0

            for tx in sorted_txs:
                if tx.transaction_type == "buy":
                    if current_holdings > 0:
                        period_return = (tx.price_per_share * current_holdings - last_value) / last_value
                        holding_period_returns.append(1 + period_return)
                    
                    current_holdings += tx.quantity
                    last_value = tx.total_value
                else:  # sell
                    if current_holdings == 0:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Invalid transaction sequence for {stock_code}: selling with no holdings"
                        )
                    
                    period_return = (tx.price_per_share * current_holdings - last_value) / last_value
                    holding_period_returns.append(1 + period_return)
                    
                    current_holdings -= tx.quantity
                    if current_holdings > 0:
                        last_value = current_holdings * tx.price_per_share

            # Calculate final period return using latest market price if we still have holdings
            if current_holdings > 0:
                final_value = current_holdings * latest_price
                final_return = (final_value - last_value) / last_value
                holding_period_returns.append(1 + final_return)

            stock_twr = np.prod(holding_period_returns) - 1 if holding_period_returns else 0

            # Calculate individual stock MWR
            stock_cash_flows = []
            current_holdings = 0
            stock_dates = []
            
            for tx in sorted_txs:
                if tx.transaction_type == "buy":
                    stock_cash_flows.append(-tx.total_value)
                    current_holdings += tx.quantity
                else:
                    stock_cash_flows.append(tx.total_value)
                    current_holdings -= tx.quantity
                
                # Convert transaction date to datetime
                tx_date = datetime.combine(
                    tx.transaction_date.date() if isinstance(tx.transaction_date, datetime)
                    else tx.transaction_date,
                    datetime.min.time()
                )
                stock_dates.append(tx_date)
                portfolio_dates.append(tx_date)
                portfolio_cash_flows.append(-tx.total_value if tx.transaction_type == "buy" else tx.total_value)

            # Add final market value if we still have holdings
            if current_holdings > 0:
                final_value = current_holdings * latest_price
                stock_cash_flows.append(final_value)
                latest_dt = latest_dates[stock_code]
                stock_dates.append(latest_dt)
                portfolio_dates.append(latest_dt)
                portfolio_cash_flows.append(final_value)

            # Calculate stock MWR
            try:
                start_date = stock_dates[0]
                days = [(date - start_date).days for date in stock_dates]
                
                daily_irr = npf.irr(stock_cash_flows)
                
                if daily_irr is None or np.isnan(daily_irr):
                    logger.warning(f"Invalid IRR calculated for {stock_code}")
                    stock_mwr = 0
                else:
                    total_days = max(1, days[-1])
                    stock_mwr = (1 + daily_irr) ** (365 / total_days) - 1
            except Exception as e:
                logger.error(f"Error calculating MWR for {stock_code}: {str(e)}")
                stock_mwr = 0

            stock_breakdown[stock_code] = {
                "twr": round(float(stock_twr), 4),
                "mwr": round(float(stock_mwr), 4)
            }

        # Calculate portfolio-level MWR
        try:
            start_date = min(portfolio_dates)
            days = [(date - start_date).days for date in portfolio_dates]
            
            daily_irr = npf.irr(portfolio_cash_flows)
            
            if daily_irr is None or np.isnan(daily_irr):
                logger.warning("Invalid portfolio IRR calculated")
                portfolio_mwr = 0
            else:
                total_days = max(1, days[-1])
                portfolio_mwr = (1 + daily_irr) ** (365 / total_days) - 1
        except Exception as e:
            logger.error(f"Error calculating portfolio MWR: {str(e)}")
            portfolio_mwr = 0

        # For portfolio TWR, use a value-weighted approach
        total_investment = sum(abs(cf) for cf in portfolio_cash_flows if cf < 0)
        portfolio_twr = 0
        
        for stock_code, transactions in stock_transactions.items():
            stock_investment = sum(tx.total_value for tx in transactions if tx.transaction_type == "buy")
            weight = stock_investment / total_investment
            portfolio_twr += weight * stock_breakdown[stock_code]["twr"]

        # Get overall date range from portfolio dates (which are now all in datetime format)
        start_date = min(portfolio_dates)
        end_date = max(latest_dates.values())

        return PortfolioReturnResponse(
            portfolio_twr=round(float(portfolio_twr), 4),
            portfolio_mwr=round(float(portfolio_mwr), 4),
            calculation_date=datetime.now(timezone.utc),
            start_date=start_date,
            end_date=end_date,
            stock_breakdown=stock_breakdown
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating portfolio returns: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating portfolio returns: {str(e)}"
        )
    
