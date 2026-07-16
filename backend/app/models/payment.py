from sqlalchemy import Column, Integer, BigInteger, String, Date, Enum, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.core.config import settings

class TrnBill(Base):
    __tablename__ = "bills"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    
    bill_id = Column(BigInteger, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    party_ledger_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.ledgers.ledger_id"), nullable=False, index=True)
    voucher_id = Column(BigInteger, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.vouchers.voucher_id", ondelete="CASCADE"), nullable=False)
    bill_reference = Column(String(50), nullable=False)
    bill_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=True)
    bill_amount = Column(Numeric(18, 2), nullable=False)
    settled_amount = Column(Numeric(18, 2), default=0.00)
    status = Column(Enum('Open', 'Partially Settled', 'Settled', name='bill_status'), default='Open')
    tally_guid = Column(String(50), nullable=True, index=True)
    
    voucher = relationship("TrnVoucher")
    party = relationship("MstLedger")
    allocations = relationship("BillAllocation", back_populates="bill", cascade="all, delete-orphan")

class BillAllocation(Base):
    __tablename__ = "bill_allocations"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    
    allocation_id = Column(BigInteger, primary_key=True, index=True)
    voucher_entry_id = Column(BigInteger, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.voucher_entries.entry_id", ondelete="CASCADE"), nullable=False)
    bill_id = Column(BigInteger, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.bills.bill_id", ondelete="SET NULL"), nullable=True)
    allocation_type = Column(Enum('Against Ref', 'Advance', 'On Account', 'New Ref', name='allocation_type_enum'), nullable=False)
    amount = Column(Numeric(18, 2), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    
    bill = relationship("TrnBill", back_populates="allocations")

class ShopPayment(Base):
    __tablename__ = "shop_payments"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id", ondelete="CASCADE"), nullable=False)
    ledger_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.ledgers.ledger_id"), nullable=False)
    amount = Column(Numeric(18, 2), nullable=False)
    payment_mode = Column(String(64), nullable=False)  # Cash, Cheque, Online
    comments = Column(String(1024), nullable=True)
    photo_url = Column(String(1024), nullable=True)
    status = Column(String(32), default="pending")  # pending, success, cancelled
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User")
    ledger = relationship("MstLedger")

