# app/api/secure/routes.py

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from typing import Optional, Dict
from ...core.security import verify_jwt_token
import subprocess
from .schemas import EmailRequest, EmailResponse
from sqlalchemy.orm import Session 
from datetime import datetime 
from ...db.database import get_db
import logging

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