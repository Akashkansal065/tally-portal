from sqlalchemy import Column, Integer, BigInteger, String, Boolean, DateTime, ForeignKey, Enum, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.models.company import Company
from app.core.config import settings

class Currency(Base):
    __tablename__ = "currencies"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    
    currency_id = Column(Integer, primary_key=True, index=True)
    code = Column(String(3), nullable=False, unique=True)
    symbol = Column(String(10), nullable=False)
    decimal_places = Column(Integer, default=2)
    is_base_currency = Column(Boolean, default=False)

class MstGroup(Base):
    __tablename__ = "account_groups"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    
    group_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    parent_group_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.account_groups.group_id", ondelete="SET NULL"), nullable=True)
    nature = Column(Enum('Asset', 'Liability', 'Income', 'Expense', name='account_group_nature'), nullable=False)
    affects_gross_profit = Column(Boolean, default=False)
    is_system_defined = Column(Boolean, default=False)
    tally_guid = Column(String(50), nullable=True, index=True)
    tally_alter_id = Column(BigInteger, nullable=True, index=True)
    
    # Relationships
    parent = relationship("MstGroup", remote_side=[group_id], backref="sub_groups")
    ledgers = relationship("MstLedger", back_populates="group")

class MstLedger(Base):
    __tablename__ = "ledgers"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    
    ledger_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(150), nullable=False)
    group_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.account_groups.group_id"), nullable=False)
    opening_balance = Column(Numeric(18, 2), default=0.00)
    opening_balance_type = Column(Enum('Dr', 'Cr', name='balance_type'), default='Dr')
    currency_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.currencies.currency_id"), nullable=True)
    gstin = Column(String(15), nullable=True)
    gst_registration_type = Column(String(50), nullable=True)
    pan_number = Column(String(30), nullable=True)
    aadhar_number = Column(String(12), nullable=True)
    address = Column(String(300), nullable=True)
    state = Column(String(100), nullable=True)
    pincode = Column(String(10), nullable=True)
    country = Column(String(100), default='India')
    contact_person = Column(String(100), nullable=True)
    phone = Column(String(30), nullable=True)
    mobile = Column(String(30), nullable=True)
    email = Column(String(100), nullable=True)
    email_cc = Column(String(100), nullable=True)
    website = Column(String(100), nullable=True)
    description = Column(String(255), nullable=True)
    fax = Column(String(30), nullable=True)
    alias_name = Column(String(150), nullable=True)
    is_bank_account = Column(Boolean, default=False)
    bank_account_no = Column(String(30), nullable=True)
    bank_ifsc = Column(String(15), nullable=True)
    credit_limit = Column(Numeric(18, 2), nullable=True)
    credit_period_days = Column(Integer, nullable=True)
    is_billwise_on = Column(Boolean, default=True)
    transporter_id = Column(String(50), nullable=True)
    is_transporter = Column(Boolean, default=False)
    place_of_supply = Column(String(100), nullable=True)
    is_other_territory_assessee = Column(Boolean, default=False)
    is_common_party = Column(Boolean, default=False)
    gst_applicable_from = Column(DateTime, nullable=True)
    is_inventory_affected = Column(Boolean, default=False)
    is_cost_centres_on = Column(Boolean, default=False)
    notes = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    tally_guid = Column(String(50), nullable=True, index=True)
    tally_alter_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    group = relationship("MstGroup", back_populates="ledgers")
    company = relationship("Company")
    bank_details = relationship("MstLedgerBankDetail", back_populates="ledger", cascade="all, delete-orphan")

class MstLedgerBankDetail(Base):
    __tablename__ = "ledger_bank_details"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}

    bank_detail_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    ledger_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.ledgers.ledger_id", ondelete="CASCADE"), nullable=False, index=True)
    transaction_type = Column(String(50), nullable=False, default="e-Fund Transfer")
    ref_id = Column(String(50), default="Primary")
    favouring_name = Column(String(150), nullable=True)
    cross_using = Column(String(50), default="A/c Payee")
    account_number = Column(String(50), nullable=True)
    ifsc_code = Column(String(20), nullable=True)
    bank_name = Column(String(150), nullable=True)
    upi_id = Column(String(100), nullable=True)
    account_holder_name = Column(String(150), nullable=True)
    is_default = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    ledger = relationship("MstLedger", back_populates="bank_details")

class CostCenter(Base):
    __tablename__ = "cost_centers"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    
    cost_center_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    parent_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.cost_centers.cost_center_id", ondelete="SET NULL"), nullable=True)
    
    parent = relationship("CostCenter", remote_side=[cost_center_id], backref="sub_centers")

class GstRegistrationType(Base):
    __tablename__ = "gst_registration_types"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    code = Column(String(50), nullable=False, unique=True)
    requires_gstin = Column(Boolean, default=True)
    display_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

class BankTransactionType(Base):
    __tablename__ = "bank_transaction_types"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True)
    display_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
