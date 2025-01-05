from pydantic import BaseModel, EmailStr

class EmailRequest(BaseModel):
    recipient_email: EmailStr
    subject: str
    body: str  

class EmailResponse(BaseModel):
    success: bool
    message: str