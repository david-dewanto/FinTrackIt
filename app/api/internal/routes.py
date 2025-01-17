# app/api/internal/routes.py
from fastapi import APIRouter, Depends, HTTPException
from fastapi import BackgroundTasks
from typing import Optional, List
from sqlalchemy.orm import Session
from firebase_admin import auth
from firebase_admin.auth import (
    EmailAlreadyExistsError, 
    UserNotFoundError
)
from ...db.database import get_db
from ...core.security import generate_api_key
from ...core.firebase import get_firebase_admin, sign_in_with_email_password, send_verification_email, send_password_reset_email
from ...models.models import APIKey, Transaction
from ..secure.routes import get_stock_price
from . import schemas
from ...models.models import StockAlert, PriceTriggerType
from .schemas import (
    StockAlertCreate, StockAlertResponse, StockAlertList,
    StockAlertListResponse, StockAlertDelete
)
from datetime import datetime, timezone, timedelta, date
from sqlalchemy import and_
import logging
from ..secure.schemas import EmailRequest
import httpx
import io
import csv

router = APIRouter()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
firebase_auth = get_firebase_admin()

@router.get("/")
async def internal_route():
    return {"message": "This is an internal endpoint"}

@router.post("/generate-api-key", response_model=schemas.APIKeyResponse)
async def generate_api_key_endpoint(
    request: schemas.APIKeyRequest,
    db: Session = Depends(get_db)
):
    try:
        # Check if email already exists
        existing_key = db.query(APIKey).filter(APIKey.email == request.email).first()
        
        # Generate new API key
        new_api_key = generate_api_key()
        
        if existing_key:
            # Update existing record
            existing_key.api_key = new_api_key
            existing_key.full_name = request.full_name
            existing_key.application_name = request.application_name
            existing_key.organization = request.organization
            existing_key.phone_number = request.phone_number
            db_api_key = existing_key
        else:
            # Create new API key record
            db_api_key = APIKey(
                api_key=new_api_key,
                full_name=request.full_name,
                application_name=request.application_name,
                organization=request.organization,
                email=request.email,
                phone_number=request.phone_number
            )
            db.add(db_api_key)
        
        db.commit()
        db.refresh(db_api_key)
        
        return schemas.APIKeyResponse(
            api_key=new_api_key,
            full_name=request.full_name,
            application_name=request.application_name,
            organization=request.organization,
            email=request.email,
            phone_number=request.phone_number
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not generate API key")

@router.post("/auth/signin/email", response_model=schemas.AuthResponse)
async def signin_with_email(request: schemas.EmailSignInRequest):
    try:
        # First, attempt to sign in using REST API to get ID token
        sign_in_response = await sign_in_with_email_password(request.email, request.password)
        id_token = sign_in_response['idToken']
        
        # Get user details from Firebase Admin SDK
        user = firebase_auth.get_user_by_email(request.email)
        
        # If email isn't verified, send verification email
        if not user.email_verified:
            try:
                await send_verification_email(id_token)
                return {
                    "uid": user.uid,
                    "email": user.email,
                    "email_verified": False,
                    "message": "Email not verified. A new verification email has been sent."
                }
            except Exception as e:
                # If sending verification fails, still allow login but notify user
                print(f"Error sending verification email: {str(e)}")
                return {
                    "uid": user.uid,
                    "email": user.email,
                    "email_verified": False,
                    "message": "Email not verified. Please check your email."
                }
        
        # If email is verified, proceed with normal login
        return {
            "uid": user.uid,
            "email": user.email,
            "display_name": user.display_name,
            "email_verified": True,
            "id_token": id_token,  # Include ID token in response
            "message": None
        }
        
    except UserNotFoundError:
        raise HTTPException(
            status_code=400,
            detail="Invalid credentials"
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

@router.post("/auth/signup/email", response_model=schemas.AuthResponse)
async def signup_with_email(request: schemas.EmailSignUpRequest):
    try:
        # First, check if a user already exists with this email
        try:
            existing_user = firebase_auth.get_user_by_email(request.email)
            
            # If we found a user, let's check their sign-in providers
            user_info = firebase_auth.get_user(existing_user.uid)
            
            # Get the provider information
            providers = [
                provider.provider_id 
                for provider in user_info.provider_data
            ]
            
            if 'google.com' in providers:
                raise HTTPException(
                    status_code=400,  
                    detail="This email is already registered with Google. Please sign in with Google instead."
                )
            
            # If we reach here, the user exists but not with Google
            # This means they're trying to create a duplicate account
            raise HTTPException(
                status_code=400,
                detail="Email already registered. Please use the sign-in page."
            )
            
        except UserNotFoundError:
            # No existing user found, proceed with creation
            user = firebase_auth.create_user(
                email=request.email,
                password=request.password,
                display_name=request.display_name,
                email_verified=False
            )
            
            try:
                # Sign in the user to get ID token
                sign_in_response = await sign_in_with_email_password(
                    request.email, 
                    request.password
                )
                id_token = sign_in_response['idToken']
                
                # Send verification email using the ID token
                await send_verification_email(id_token)
            except Exception as e:
                # Log the error but don't block account creation
                print(f"Error in verification flow: {str(e)}")
            
            return {
                "uid": user.uid,
                "email": user.email,
                "email_verified": user.email_verified,
                "message": "Please check your email for verification link"
            }
            
    except EmailAlreadyExistsError:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

@router.post("/auth/reset-password", response_model=schemas.PasswordResetResponse)
async def reset_password(request: schemas.PasswordResetRequest):
    try:
        # First get the user information
        user = firebase_auth.get_user_by_email(request.email)
        
        # Get the user's provider information
        user_info = firebase_auth.get_user(user.uid)
        providers = [
            provider.provider_id 
            for provider in user_info.provider_data
        ]
        
        # Check if the user is registered with Google
        if 'google.com' in providers:
            raise HTTPException(
                status_code=400,
                detail="This account uses Google Sign-In. Please sign in with Google instead of using password reset."
            )
            
        # If we reach here, the user is registered with email/password
        # Proceed with password reset
        result = await send_password_reset_email(request.email)
        
        return {
            "success": True,
            "message": "Password reset email sent successfully"
        }
        
    except UserNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )
    except HTTPException:
        # Re-raise HTTP exceptions without modification
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error sending password reset email: {str(e)}"
        )

@router.post("/auth/signin/google", response_model=schemas.AuthResponse)
async def signin_with_google(request: schemas.GoogleSignInRequest):
    try:
        # Verify the ID token using Firebase Admin SDK
        decoded_token = firebase_auth.verify_id_token(request.id_token)
        email = decoded_token.get('email')
        
        if not email:
            raise HTTPException(
                status_code=400,
                detail="Email not provided in Google sign-in"
            )
        
        try:
            # First try to find user by email
            existing_user = firebase_auth.get_user_by_email(email)
            
            # Check the user's provider information
            user_info = firebase_auth.get_user(existing_user.uid)
            providers = [
                provider.provider_id 
                for provider in user_info.provider_data
            ]
            
            # First, check if they're registered with email/password
            if 'password' in providers:
                raise HTTPException(
                    status_code=400,
                    detail="This email is already registered with email/password. Please sign in with your email and password instead."
                )
            
            # Then check if they're registered with Google
            if 'google.com' in providers:
                # This is the happy path - user exists and uses Google
                return {
                    "uid": existing_user.uid,
                    "email": existing_user.email,
                    "email_verified": existing_user.email_verified,
                    "display_name": existing_user.display_name,
                    "id_token": request.id_token,  
                    "message": None
                }
            
            # If we get here, the user exists but doesn't have any recognized providers
            # This is an edge case that shouldn't happen in normal circumstances
            raise HTTPException(
                status_code=400,
                detail="Account exists but with incompatible sign-in method. Please contact support."
            )
                
        except UserNotFoundError:
            # Only create new user if email doesn't exist at all
            user_properties = {
                'email': email,
                'email_verified': decoded_token.get('email_verified', False),
                'display_name': decoded_token.get('name'),
                'photo_url': decoded_token.get('picture')
            }
            
            # Remove None values
            user_properties = {k: v for k, v in user_properties.items() if v is not None}
            
            # Create new user
            user = firebase_auth.create_user(**user_properties)
            return {
                "uid": user.uid,
                "email": user.email,
                "email_verified": user.email_verified,
                "display_name": user.display_name,
                "message": None
            }
        
    except HTTPException:
        # Re-raise HTTP exceptions without modification
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to authenticate with Google: {str(e)}"
        )

@router.post("/transactions", response_model=schemas.TransactionResponse)
async def create_transaction(
    transaction: schemas.TransactionCreate,
    db: Session = Depends(get_db)
):
    try:
        # Validate quantity
        if transaction.quantity <= 0:
            raise HTTPException(
                status_code=400, 
                detail="Quantity must be greater than 0"
            )

        # Verify token and get user info
        try:
            decoded_token = auth.verify_id_token(transaction.token)
            uid = decoded_token['uid']
        except Exception as e:
            raise HTTPException(status_code=401, detail="Invalid account token, please login again")

        # Convert transaction date to date for stock price query
        transaction_date = transaction.transaction_date.date()
        # Get the day before and after to ensure we get the nearest trading day's price
        date_str = f"{transaction_date}_{transaction_date}"
        
        # Get stock price using the existing endpoint
        try:
            stock_data = await get_stock_price(transaction.stock_code, date_str, db)
            if not stock_data.prices or not stock_data.prices[-1]:
                raise HTTPException(status_code=404, detail="Could not get stock price for specified date")
            
            # Use the latest price in the range (which should be the nearest trading day)
            current_price = stock_data.prices[-1].closing_price

        except HTTPException as e:
            raise HTTPException(status_code=e.status_code, detail=str(e.detail))

        # Calculate total value
        total_value = transaction.quantity * current_price

        # Create new transaction
        db_transaction = Transaction(
            uid=uid,
            stock_code=transaction.stock_code,
            transaction_type=transaction.transaction_type,
            quantity=transaction.quantity,
            price_per_share=current_price,
            total_value=total_value,
            transaction_date=transaction.transaction_date
        )

        db.add(db_transaction)
        db.commit()
        db.refresh(db_transaction)

        return db_transaction

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/transactions/list", response_model=schemas.TransactionListResponse)
async def get_transactions(
    request: schemas.TransactionList,
    db: Session = Depends(get_db)
):
    try:
        # Verify token and get user info
        try:
            decoded_token = auth.verify_id_token(request.token)
            uid = decoded_token['uid']
        except Exception as e:
            raise HTTPException(status_code=401, detail="Invalid account token, please login again")

        # Get user's transactions
        transactions = db.query(Transaction).filter(Transaction.uid == uid).all()
        # Ensure we always return a list, even if empty
        return schemas.TransactionListResponse(transactions=transactions or [])

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/transactions/delete/{transaction_id}")
async def delete_transaction(
    transaction_id: str,
    request: schemas.TransactionDelete,
    db: Session = Depends(get_db)
):
    try:
        # Verify token and get user info
        try:
            decoded_token = auth.verify_id_token(request.token)
            uid = decoded_token['uid']
        except Exception as e:
            raise HTTPException(status_code=401, detail="Invalid account token, please login again")

        # Get transaction
        transaction = db.query(Transaction).filter(
            Transaction.id == transaction_id,
            Transaction.uid == uid  # Add this to ensure we only get user's own transaction
        ).first()
        
        if not transaction:
            raise HTTPException(status_code=404, detail="Transaction not found")

        try:
            # Delete transaction
            db.delete(transaction)
            db.commit()
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail="Failed to delete transaction")

        return {"message": "Transaction deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
async def check_and_send_alerts(background_tasks: BackgroundTasks, db: Session):
    """Background task to check price alerts and send notifications"""
    try:
        # Get current UTC hour from UTC+7
        jakarta_time = datetime.now(timezone.utc) + timedelta(hours=7)
        current_hour_utc = (jakarta_time.hour - 7) % 24
        
        # Get all active alerts for current hour
        alerts = db.query(StockAlert).filter(
            and_(
                StockAlert.is_active == True,
                StockAlert.notification_hour == current_hour_utc
            )
        ).all()
        
        if not alerts:
            return
            
        # Group alerts by user
        alerts_by_user = {}
        for alert in alerts:
            if alert.uid not in alerts_by_user:
                alerts_by_user[alert.uid] = []
            alerts_by_user[alert.uid].append(alert)
            
        # Process alerts for each user
        for uid, user_alerts in alerts_by_user.items():
            triggered_alerts = []
            
            for alert in user_alerts:
                try:
                    # Get current stock price
                    today = datetime.now(timezone.utc).date()
                    date_str = f"{today}_{today}"
                    stock_data = await get_stock_price(alert.stock_code, date_str, db)
                    
                    if not stock_data.prices:
                        continue
                        
                    current_price = stock_data.prices[-1].closing_price
                    
                    # Check if price trigger condition is met
                    is_triggered = (
                        (alert.trigger_type == PriceTriggerType.ABOVE and current_price > alert.trigger_price) or
                        (alert.trigger_type == PriceTriggerType.BELOW and current_price < alert.trigger_price)
                    )
                    
                    if is_triggered:
                        triggered_alerts.append({
                            "stock_code": alert.stock_code,
                            "current_price": current_price,
                            "trigger_price": alert.trigger_price,
                            "trigger_type": alert.trigger_type
                        })
                        
                        # Update alert status
                        alert.last_checked = datetime.now(timezone.utc)
                        alert.last_notified = datetime.now(timezone.utc)
                        
                        # If not repeating, deactivate the alert
                        if not alert.is_repeating:
                            alert.is_active = False
                            
                except Exception as e:
                    logger.error(f"Error checking alert {alert.id}: {str(e)}")
                    continue
            
            # If any alerts were triggered for this user, send email
            if triggered_alerts:
                try:
                    # Get user email from Firebase
                    user = firebase_auth.get_user(uid)
                    
                    # Create email content
                    email_body = "<h2>Stock Price Alert</h2>"
                    for alert in triggered_alerts:
                        condition = "above" if alert["trigger_type"] == PriceTriggerType.ABOVE else "below"
                        email_body += f"""
                        <p>
                            Stock: {alert["stock_code"]}<br>
                            Current Price: {alert["current_price"]}<br>
                            Trigger: {condition} {alert["trigger_price"]}<br>
                        </p>
                        """
                    
                    # Send email using existing endpoint
                    email_request = EmailRequest(
                        recipient_email=user.email,
                        subject="Stock Price Alert",
                        body=email_body
                    )
                    
                    # Call the secure email endpoint
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            "http://localhost:8000/secure/send-email",
                            json=email_request.dict()
                        )
                        if response.status_code != 200:
                            raise Exception(f"Failed to send email: {response.text}")
                    
                except Exception as e:
                    logger.error(f"Error sending alert email to user {uid}: {str(e)}")
        
        # Commit all changes
        db.commit()
        
    except Exception as e:
        logger.error(f"Error in check_and_send_alerts: {str(e)}")
        db.rollback()

@router.post("/alerts", response_model=StockAlertResponse)
async def create_alert(
    alert: StockAlertCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    try:
        # Verify token and get user info
        try:
            decoded_token = auth.verify_id_token(alert.token)
            uid = decoded_token['uid']
        except Exception as e:
            raise HTTPException(status_code=401, detail="Invalid account token")

        # Validate notification hour (in UTC+7)
        if not 0 <= alert.notification_hour <= 23:
            raise HTTPException(
                status_code=400,
                detail="Notification hour must be between 0 and 23"
            )

        # Convert UTC+7 to UTC
        utc_hour = (alert.notification_hour - 7) % 24

        # Create new alert
        db_alert = StockAlert(
            uid=uid,
            stock_code=alert.stock_code,
            trigger_price=alert.trigger_price,
            trigger_type=alert.trigger_type,
            notification_hour=utc_hour,  # Store in UTC
            is_repeating=alert.is_repeating
        )

        db.add(db_alert)
        db.commit()
        db.refresh(db_alert)

        # Schedule initial check
        background_tasks.add_task(check_and_send_alerts, background_tasks, db)

        return db_alert

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/alerts/list", response_model=StockAlertListResponse)
async def list_alerts(
    request: StockAlertList,
    db: Session = Depends(get_db)
):
    try:
        # Verify token and get user info
        try:
            decoded_token = auth.verify_id_token(request.token)
            uid = decoded_token['uid']
        except Exception as e:
            raise HTTPException(status_code=401, detail="Invalid account token")

        # Get user's alerts
        alerts = db.query(StockAlert).filter(
            StockAlert.uid == uid
        ).all()

        return StockAlertListResponse(alerts=alerts or [])

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/alerts/delete/{alert_id}")
async def delete_alert(
    alert_id: str,
    request: StockAlertDelete,
    db: Session = Depends(get_db)
):
    try:
        # Verify token and get user info
        try:
            decoded_token = auth.verify_id_token(request.token)
            uid = decoded_token['uid']
        except Exception as e:
            raise HTTPException(status_code=401, detail="Invalid account token")

        # Get alert
        alert = db.query(StockAlert).filter(
            StockAlert.id == alert_id,
            StockAlert.uid == uid
        ).first()
        
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")

        # Delete alert
        db.delete(alert)
        db.commit()

        return {"message": "Alert deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.post("/analyze-stocks")
async def analyze_stocks(
    request: schemas.StockAnalysisRequest,
    db: Session = Depends(get_db)
):
    """
    Analyze historical stock data using Pintar Ekspor's analytics service.
    
    Steps:
    1. Fetch 3 years of historical data for each requested stock
    2. Format data into required CSV structure
    3. Send to analytics API
    4. Return analysis results
    """
    try:
        # Calculate date range (3 years from today)
        end_date = date.today()
        start_date = end_date - timedelta(days=3*365)
        date_range = f"{start_date.isoformat()}_{end_date.isoformat()}"
        
        # Create CSV in memory
        csv_buffer = io.StringIO()
        csv_writer = csv.writer(csv_buffer)
        csv_writer.writerow(['date', 'category', 'value'])  # Write header
        
        # Fetch and write data for each stock
        for stock_code in request.stock_codes:
            try:
                # Get historical prices using existing endpoint
                stock_data = await get_stock_price(stock_code, date_range, db)
                
                # Write each price point to CSV
                for price_data in stock_data.prices:
                    csv_writer.writerow([
                        price_data.date.isoformat(),
                        stock_code,
                        price_data.closing_price
                    ])
                    
            except Exception as e:
                logger.error(f"Error fetching data for {stock_code}: {str(e)}")
                continue
        
        # Prepare the CSV data
        csv_content = csv_buffer.getvalue()
        csv_buffer.close()
        
        # If no data was written, return error
        if csv_content.count('\n') <= 1:  # Only header exists
            raise HTTPException(
                status_code=400,
                detail="No valid stock data found for analysis"
            )
            
        # Convert string CSV to bytes for file upload
        csv_bytes = csv_content.encode('utf-8')
        
        # Prepare file for upload
        files = {
            'file': ('stock_data.csv', csv_bytes, 'text/csv')
        }
        
        # Set query parameters with default values
        params = {
            'include_forecast': 'true',
            'include_visualizations': 'false',
            'export_format': 'json'
        }
        
        # Send request to analytics API
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    'https://pintar-ekspor-production.up.railway.app/analytics/analyze',
                    params=params,
                    files=files,
                    headers={
                        'X-API-Key': ''
                    },
                    timeout=30.0  # Set reasonable timeout
                )
                
                # Check response status
                response.raise_for_status()
                
                # Return the analytics response directly
                return response.json()
                
            except httpx.HTTPError as e:
                logger.error(f"Analytics API error: {str(e)}")
                raise HTTPException(
                    status_code=503,
                    detail="Pintar Ekspor (Friend's Server) is down"
                )
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in analyze_stocks: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@router.post("/validate-token", response_model=schemas.TokenValidationResponse)
async def validate_token(request: schemas.TokenValidationRequest):
    try:
        # Verify the token using Firebase Admin SDK
        decoded_token = firebase_auth.verify_id_token(request.token)
        
        # Get additional user information
        user = firebase_auth.get_user(decoded_token['uid'])
        
        # Return successful validation response with user info
        return schemas.TokenValidationResponse(
            is_valid=True,
            uid=user.uid,
            email=user.email,
            display_name=user.display_name,
            email_verified=user.email_verified
        )
        
    except Exception as e:
        # Return failed validation response with error message
        return schemas.TokenValidationResponse(
            is_valid=False,
            error_message=str(e)
        )