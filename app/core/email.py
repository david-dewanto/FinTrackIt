# app/core/email.py
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from ..config.settings import settings

async def send_email_async(recipient_email: str, subject: str, body: str) -> bool:
    """
    Send an email asynchronously using configured SMTP server
    """
    # Create message
    message = MIMEMultipart()
    message["From"] = settings.SMTP_FROM_EMAIL
    message["To"] = recipient_email
    message["Subject"] = subject
    
    # Add HTML body
    message.attach(MIMEText(body, "html"))

    try:
        # Connect to SMTP server
        smtp = aiosmtplib.SMTP(hostname=settings.SMTP_HOST, port=settings.SMTP_PORT)
        await smtp.connect()
        
        # If using authentication (e.g., in development with Mailtrap)
        if hasattr(settings, 'SMTP_USERNAME') and settings.SMTP_USERNAME:
            await smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        
        # Send email
        await smtp.send_message(message)
        await smtp.quit()
        return True
        
    except Exception as e:
        print(f"Failed to send email: {str(e)}")
        return False