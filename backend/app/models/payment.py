from sqlalchemy import Column, Integer, BigInteger, String, Date, Enum, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class Bill(Base):
    __tablename__ = "bills"
    
    bill_id = Column(BigInteger, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    party_ledger_id = Column(Integer, ForeignKey("ledgers.ledger_id"), nullable=False, index=True)
    voucher_id = Column(BigInteger, ForeignKey("vouchers.voucher_id", ondelete="CASCADE"), nullable=False)
    bill_reference = Column(String(50), nullable=False)
    bill_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=True)
    bill_amount = Column(Numeric(18, 2), nullable=False)
    settled_amount = Column(Numeric(18, 2), default=0.00)
    status = Column(Enum('Open', 'Partially Settled', 'Settled', name='bill_status'), default='Open')
    tally_guid = Column(String(50), nullable=True, index=True)
    
    voucher = relationship("Voucher")
    party = relationship("Ledger")
    allocations = relationship("BillAllocation", back_populates="bill", cascade="all, delete-orphan")

class BillAllocation(Base):
    __tablename__ = "bill_allocations"
    
    allocation_id = Column(BigInteger, primary_key=True, index=True)
    voucher_entry_id = Column(BigInteger, ForeignKey("voucher_entries.entry_id", ondelete="CASCADE"), nullable=False)
    bill_id = Column(BigInteger, ForeignKey("bills.bill_id", ondelete="SET NULL"), nullable=True)
    allocation_type = Column(Enum('Against Ref', 'Advance', 'On Account', 'New Ref', name='allocation_type_enum'), nullable=False)
    amount = Column(Numeric(18, 2), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    
    bill = relationship("Bill", back_populates="allocations")

class ShopPayment(Base):
    __tablename__ = "shop_payments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    ledger_id = Column(Integer, ForeignKey("ledgers.ledger_id"), nullable=False)
    amount = Column(Numeric(18, 2), nullable=False)
    payment_mode = Column(String(64), nullable=False)  # Cash, Cheque, Online
    comments = Column(String(1024), nullable=True)
    photo_url = Column(String(1024), nullable=True)
    status = Column(String(32), default="pending")  # pending, success, cancelled
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User")
    ledger = relationship("Ledger")

