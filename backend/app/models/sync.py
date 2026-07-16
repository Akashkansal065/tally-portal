from sqlalchemy import Column, Integer, BigInteger, String, Enum, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base

class SyncQueue(Base):
    __tablename__ = "sync_queue"
    
    sync_id = Column(BigInteger, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    record_type = Column(Enum('Ledger', 'Voucher', name='sync_record_type_enum'), nullable=False)
    record_id = Column(BigInteger, nullable=False)
    action = Column(Enum('Create', 'Update', 'Delete', name='sync_action_enum'), nullable=False)
    is_processed = Column(Boolean, default=False)
    attempts = Column(Integer, default=0)
    error_message = Column(String(500), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
