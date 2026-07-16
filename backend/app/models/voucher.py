from sqlalchemy import Column, Integer, BigInteger, String, Date, Boolean, DateTime, ForeignKey, Enum, Numeric, TEXT, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.core.config import settings

# SQLAlchemy BigInteger fits the MySQL BIGINT correctly.

class MstVoucherType(Base):
    __tablename__ = "voucher_types"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    
    voucher_type_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(50), nullable=False)
    abbreviation = Column(String(10), nullable=True)
    numbering_method = Column(Enum('Automatic', 'Manual', name='numbering_method_type'), default='Automatic')
    prefix = Column(String(10), default='')
    next_number = Column(Integer, default=1)
    is_system_defined = Column(Boolean, default=True)
    
    vouchers = relationship("TrnVoucher", back_populates="voucher_type")

class TrnVoucher(Base):
    __tablename__ = "vouchers"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    
    voucher_id = Column(BigInteger, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    voucher_type_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.voucher_types.voucher_type_id"), nullable=False)
    voucher_number = Column(String(30), nullable=False)
    voucher_date = Column(Date, nullable=False)
    reference_number = Column(String(50), nullable=True)
    narration = Column(TEXT, nullable=True)
    total_amount = Column(Numeric(18, 2), nullable=False, default=0.00)
    is_cancelled = Column(Boolean, default=False)
    is_optional = Column(Boolean, default=False)
    tally_guid = Column(String(50), nullable=True, index=True)
    tally_alter_id = Column(Integer, nullable=True)
    created_by = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    voucher_type = relationship("MstVoucherType", back_populates="vouchers")
    entries = relationship("TrnAccounting", back_populates="voucher", cascade="all, delete-orphan")
    approvals = relationship("ApprovalRequest", back_populates="voucher", cascade="all, delete-orphan")

class TrnAccounting(Base):
    __tablename__ = "voucher_entries"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    
    entry_id = Column(BigInteger, primary_key=True, index=True)
    voucher_id = Column(BigInteger, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.vouchers.voucher_id", ondelete="CASCADE"), nullable=False)
    ledger_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.ledgers.ledger_id"), nullable=False)
    cost_center_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.cost_centers.cost_center_id", ondelete="SET NULL"), nullable=True)
    debit_amount = Column(Numeric(18, 2), default=0.00)
    credit_amount = Column(Numeric(18, 2), default=0.00)
    entry_narration = Column(String(300), nullable=True)
    
    # Forex details (extension)
    forex_currency_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.currencies.currency_id"), nullable=True)
    forex_amount = Column(Numeric(18, 4), nullable=True)
    exchange_rate_used = Column(Numeric(14, 6), nullable=True)
    
    # Relationship back to voucher
    voucher = relationship("TrnVoucher", back_populates="entries")

class ApprovalRule(Base):
    __tablename__ = "approval_rules"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    rule_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    module_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.modules.module_id"), nullable=False)
    voucher_type_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.voucher_types.voucher_type_id"), nullable=True)
    condition_field = Column(String(50), default="total_amount")
    condition_operator = Column(Enum('>', '>=', '<', '<=', '=', name='operator_type'), default='>')
    condition_value = Column(Numeric(18, 2), nullable=False)
    approver_role_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.roles.role_id"), nullable=False)
    is_active = Column(Boolean, default=True)

class ApprovalRequest(Base):
    __tablename__ = "approval_requests"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    request_id = Column(BigInteger, primary_key=True, index=True)
    rule_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.approval_rules.rule_id"), nullable=False)
    voucher_id = Column(BigInteger, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.vouchers.voucher_id", ondelete="CASCADE"), nullable=False)
    requested_by = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id"), nullable=False)
    status = Column(Enum('Pending', 'Approved', 'Rejected', name='approval_status'), default='Pending')
    acted_by = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id"), nullable=True)
    comments = Column(String(500), nullable=True)
    requested_at = Column(DateTime, server_default=func.now())
    acted_at = Column(DateTime, nullable=True)
    
    voucher = relationship("TrnVoucher", back_populates="approvals")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    audit_id = Column(BigInteger, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id"), nullable=False)
    action = Column(String(20), nullable=False)  # CREATE, UPDATE, DELETE, CANCEL
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(BigInteger, nullable=False)
    old_value = Column(JSON, nullable=True)
    new_value = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
