from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.models.company import Company

class Currency(Base):
    __tablename__ = "currencies"
    
    currency_id = Column(Integer, primary_key=True, index=True)
    code = Column(String(3), nullable=False, unique=True)
    symbol = Column(String(10), nullable=False)
    decimal_places = Column(Integer, default=2)
    is_base_currency = Column(Boolean, default=False)

class AccountGroup(Base):
    __tablename__ = "account_groups"
    
    group_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    parent_group_id = Column(Integer, ForeignKey("account_groups.group_id", ondelete="SET NULL"), nullable=True)
    nature = Column(Enum('Asset', 'Liability', 'Income', 'Expense', name='account_group_nature'), nullable=False)
    affects_gross_profit = Column(Boolean, default=False)
    is_system_defined = Column(Boolean, default=False)
    tally_guid = Column(String(50), nullable=True, index=True)
    
    # Relationships
    parent = relationship("AccountGroup", remote_side=[group_id], backref="sub_groups")
    ledgers = relationship("Ledger", back_populates="group")

class Ledger(Base):
    __tablename__ = "ledgers"
    
    ledger_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(150), nullable=False)
    group_id = Column(Integer, ForeignKey("account_groups.group_id"), nullable=False)
    opening_balance = Column(Numeric(18, 2), default=0.00)
    opening_balance_type = Column(Enum('Dr', 'Cr', name='balance_type'), default='Dr')
    currency_id = Column(Integer, ForeignKey("currencies.currency_id"), nullable=True)
    gstin = Column(String(15), nullable=True)
    address = Column(String(300), nullable=True)
    state = Column(String(100), nullable=True)
    is_bank_account = Column(Boolean, default=False)
    bank_account_no = Column(String(30), nullable=True)
    bank_ifsc = Column(String(15), nullable=True)
    credit_limit = Column(Numeric(18, 2), nullable=True)
    credit_period_days = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    tally_guid = Column(String(50), nullable=True, index=True)
    tally_alter_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    group = relationship("AccountGroup", back_populates="ledgers")
    company = relationship("Company")

class CostCenter(Base):
    __tablename__ = "cost_centers"
    
    cost_center_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    parent_id = Column(Integer, ForeignKey("cost_centers.cost_center_id", ondelete="SET NULL"), nullable=True)
    
    parent = relationship("CostCenter", remote_side=[cost_center_id], backref="sub_centers")
