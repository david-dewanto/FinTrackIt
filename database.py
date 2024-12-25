# database.py
from sqlalchemy import create_engine, Column, String, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# Replace with your actual database URL
DATABASE_URL = "postgresql://postgres:admin@localhost/auth_service"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class APIKey(Base):
    __tablename__ = "api_keys"
    
    key_hash = Column(String, primary_key=True)  # Stored hashed API key
    is_internal = Column(Boolean, default=False)  # Whether this is an internal API key
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<APIKey(is_internal={self.is_internal}, created_at={self.created_at})>"

# Create all tables
Base.metadata.create_all(bind=engine)

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()