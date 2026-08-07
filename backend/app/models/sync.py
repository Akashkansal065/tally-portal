from sqlalchemy import Column, Integer, BigInteger, String, Enum, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base
from app.core.config import settings

class SyncQueue(Base):
    __tablename__ = "sync_queue"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    sync_id = Column(BigInteger, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    record_type = Column(String(50), nullable=False)
    record_id = Column(BigInteger, nullable=False)
    action = Column(String(50), nullable=False)
    is_processed = Column(Boolean, default=False)
    attempts = Column(Integer, default=0)
    error_message = Column(String(500), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
