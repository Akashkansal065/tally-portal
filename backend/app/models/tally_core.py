from sqlalchemy import Column, Integer, BigInteger, String, Date, Boolean, DateTime, ForeignKey, Enum, Numeric, TEXT, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.core.config import settings

# ==========================================
# NEW MISSING MODELS (13 tables)
# ==========================================
class Config(Base):
    __tablename__ = "config"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    name = Column(String(64), primary_key=True)
    value = Column(String(1024), nullable=True)

class MstGstEffectiveRate(Base):
    __tablename__ = "mst_gst_effective_rate"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    item = Column(String(1024), nullable=True)
    applicable_from = Column(Date, nullable=True)
    hsn_description = Column(String(256), nullable=True)
    hsn_code = Column(String(64), nullable=True)
    duty_head = Column(String(64), nullable=True)
    rate = Column(Numeric(9, 4), nullable=True)
    rate_per_unit = Column(Numeric(9, 4), nullable=True)
    valuation_type = Column(String(64), nullable=True)
    is_rcm_applicable = Column(Boolean, nullable=True)
    nature_of_transaction = Column(String(64), nullable=True)
    nature_of_goods = Column(String(64), nullable=True)
    supply_type = Column(String(64), nullable=True)
    taxability = Column(String(64), nullable=True)

class MstOpeningBatchAllocation(Base):
    __tablename__ = "mst_opening_batch_allocation"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(1024), nullable=True)
    item = Column(String(1024), nullable=True)
    opening_balance = Column(Numeric(15, 4), nullable=True)
    opening_rate = Column(Numeric(15, 4), nullable=True)
    opening_value = Column(Numeric(17, 2), nullable=True)
    godown = Column(String(1024), nullable=True)
    manufactured_on = Column(Date, nullable=True)

class MstOpeningBillAllocation(Base):
    __tablename__ = "mst_opening_bill_allocation"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    ledger = Column(String(1024), nullable=True)
    opening_balance = Column(Numeric(17, 4), nullable=True)
    bill_date = Column(Date, nullable=True)
    name = Column(String(1024), nullable=True)
    bill_credit_period = Column(Integer, nullable=True)
    is_advance = Column(Boolean, nullable=True)

class TrnClosingStockLedger(Base):
    __tablename__ = "trn_closingstock_ledger"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    ledger = Column(String(1024), nullable=True)
    stock_date = Column(Date, nullable=True)
    stock_value = Column(Numeric(17, 2), nullable=True)

class MstStockItemStandardCost(Base):
    __tablename__ = "mst_stockitem_standard_cost"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    item = Column(String(1024), nullable=True)
    date = Column(Date, nullable=True)
    rate = Column(Numeric(15, 4), nullable=True)

class MstStockItemStandardPrice(Base):
    __tablename__ = "mst_stockitem_standard_price"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    item = Column(String(1024), nullable=True)
    date = Column(Date, nullable=True)
    rate = Column(Numeric(15, 4), nullable=True)

class TrnCostCentre(Base):
    __tablename__ = "trn_cost_centre"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    guid = Column(String(64), nullable=True, index=True)
    ledger = Column(String(1024), nullable=True)
    costcentre = Column(String(1024), nullable=True)
    amount = Column(Numeric(17, 2), nullable=True)

class TrnCostCategoryCentre(Base):
    __tablename__ = "trn_cost_category_centre"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    guid = Column(String(64), nullable=True, index=True)
    ledger = Column(String(1024), nullable=True)
    costcategory = Column(String(1024), nullable=True)
    costcentre = Column(String(1024), nullable=True)
    amount = Column(Numeric(17, 2), nullable=True)

class TrnCostInventoryCategoryCentre(Base):
    __tablename__ = "trn_cost_inventory_category_centre"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    guid = Column(String(64), nullable=True, index=True)
    ledger = Column(String(1024), nullable=True)
    item = Column(String(1024), nullable=True)
    costcategory = Column(String(1024), nullable=True)
    costcentre = Column(String(1024), nullable=True)
    amount = Column(Numeric(17, 2), nullable=True)

class TrnInventoryAdditionalCost(Base):
    __tablename__ = "trn_inventory_additional_cost"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    guid = Column(String(64), nullable=True, index=True)
    ledger = Column(String(1024), nullable=True)
    amount = Column(Numeric(17, 2), nullable=True)
    additional_allocation_type = Column(String(32), nullable=True)
    rate_of_invoice_tax = Column(Numeric(9, 4), nullable=True)

class TrnEmployee(Base):
    __tablename__ = "trn_employee"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    guid = Column(String(64), nullable=True, index=True)
    category = Column(String(1024), nullable=True)
    employee_name = Column(String(1024), nullable=True)
    amount = Column(Numeric(17, 2), nullable=True)
    employee_sort_order = Column(Integer, nullable=True)

class TrnPayHead(Base):
    __tablename__ = "trn_payhead"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    guid = Column(String(64), nullable=True, index=True)
    category = Column(String(1024), nullable=True)
    employee_name = Column(String(1024), nullable=True)
    employee_sort_order = Column(Integer, nullable=True)
    payhead_name = Column(String(1024), nullable=True)
    payhead_sort_order = Column(Integer, nullable=True)
    amount = Column(Numeric(17, 2), nullable=True)

class TrnAttendance(Base):
    __tablename__ = "trn_attendance"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    guid = Column(String(64), nullable=True, index=True)
    employee_name = Column(String(1024), nullable=True)
    attendancetype_name = Column(String(1024), nullable=True)
    time_value = Column(Numeric(17, 2), nullable=True)
    type_value = Column(Numeric(17, 2), nullable=True)

# ==========================================
# MOVED FROM advanced.py
# ==========================================
class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    employee_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    linked_user_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id", ondelete="SET NULL"), nullable=True)
    employee_code = Column(String(30), nullable=False)
    name = Column(String(150), nullable=False)
    designation = Column(String(100), nullable=True)
    department = Column(String(100), nullable=True)
    date_of_joining = Column(Date, nullable=False)
    date_of_leaving = Column(Date, nullable=True)
    pan = Column(String(10), nullable=True)
    uan = Column(String(20), nullable=True)
    pf_number = Column(String(30), nullable=True)
    esi_number = Column(String(30), nullable=True)
    bank_account_no = Column(String(30), nullable=True)
    bank_ifsc = Column(String(15), nullable=True)
    payment_ledger_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.ledgers.ledger_id"), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    company = relationship("Company")
    payment_ledger = relationship("MstLedger")
class PosPayment(Base):
    __tablename__ = "pos_payments"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    pos_payment_id = Column(Integer, primary_key=True, index=True)
    voucher_id = Column(BigInteger, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.vouchers.voucher_id", ondelete="CASCADE"), nullable=False)
    cash_amount = Column(Numeric(18, 2), default=0.00)
    card_amount = Column(Numeric(18, 2), default=0.00)
    upi_amount = Column(Numeric(18, 2), default=0.00)
    points_redeemed = Column(Numeric(18, 2), default=0.00)
    voucher = relationship("TrnVoucher")

class MstCostCategory(Base):
    __tablename__ = "cost_categories"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    category_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    allocate_revenue = Column(Boolean, default=True)
    allocate_non_revenue = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

class MstAttendanceType(Base):
    __tablename__ = "attendance_types"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    attendance_type_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    type_of_attendance = Column(String(50), default="Present")
    unit_id = Column(Integer, nullable=True)

class MstPayHead(Base):
    __tablename__ = "pay_heads"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    pay_head_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    pay_head_type = Column(String(50), default="Earnings for Employees")
    income_type = Column(String(50), default="Fixed")
    under_group_id = Column(Integer, nullable=True)
    is_statutory = Column(Boolean, default=False)

# ==========================================
# MOVED FROM ledger.py
# ==========================================
class MstGroupGstDetails(Base):
    __tablename__ = "group_gst_details"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.account_groups.group_id", ondelete="CASCADE"), nullable=False, index=True)
    applicable_from = Column(Date, nullable=False)
    hsn_sac_details = Column(String(50), nullable=True)
    hsn_sac = Column(String(20), nullable=True)
    gst_rate_details = Column(String(50), nullable=True)
    taxability_type = Column(String(50), nullable=True)
    gst_rate = Column(Numeric(5, 2), nullable=True)
    
    group = relationship("MstGroup", back_populates="gst_details")

class MstGroup(Base):
    __tablename__ = "account_groups"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    group_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    parent_group_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.account_groups.group_id", ondelete="SET NULL"), nullable=True)
    nature = Column(Enum('Asset', 'Liability', 'Income', 'Expense', name='account_group_nature'), nullable=False)
    
    # New Tally fields
    alias_name = Column(String(150), nullable=True)
    is_addable = Column(Boolean, default=True)
    is_revenue = Column(Boolean, default=False)
    is_deemed_positive = Column(Boolean, default=False)
    affects_gross_profit = Column(Boolean, default=False)
    sort_position = Column(Integer, default=1000)
    is_system_defined = Column(Boolean, default=False)
    
    # Advanced Parameters
    is_subledger = Column(Boolean, default=False)
    is_billwise_on = Column(Boolean, default=False)
    used_for_calculation = Column(Boolean, default=False)
    method_to_allocate = Column(String(50), nullable=True)

    tally_guid = Column(String(50), nullable=True, index=True)
    tally_alter_id = Column(BigInteger, nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    company = relationship("Company")
    parent = relationship("MstGroup", remote_side=[group_id], backref="children")
    ledgers = relationship("MstLedger", back_populates="group")
    gst_details = relationship("MstGroupGstDetails", back_populates="group", cascade="all, delete-orphan")

class MstLedger(Base):
    __tablename__ = "ledgers"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    ledger_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(150), nullable=False)
    group_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.account_groups.group_id"), nullable=False)
    opening_balance = Column(Numeric(18, 2), default=0.00)
    opening_balance_type = Column(Enum('Dr', 'Cr', name='balance_type'), default='Dr')
    currency_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.currencies.currency_id"), nullable=True)
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
    ledger = relationship("MstLedger", back_populates="bank_details")

class CostCenter(Base):
    __tablename__ = "cost_centers"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    cost_center_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    parent_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.cost_centers.cost_center_id", ondelete="SET NULL"), nullable=True)
    parent = relationship("CostCenter", remote_side=[cost_center_id], backref="sub_centers")

class BankTransactionType(Base):
    __tablename__ = "bank_transaction_types"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True)
    display_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

# ==========================================
# MOVED FROM voucher.py
# ==========================================
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
    voucher_date = Column(Date, nullable=False, index=True)
    reference_number = Column(String(50), nullable=True)
    narration = Column(TEXT, nullable=True)
    total_amount = Column(Numeric(18, 2), nullable=False, default=0.00)
    is_cancelled = Column(Boolean, default=False)
    is_optional = Column(Boolean, default=False)
    tally_guid = Column(String(50), nullable=True, index=True)
    tally_alter_id = Column(Integer, nullable=True)
    created_by = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), index=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    voucher_type = relationship("MstVoucherType", back_populates="vouchers")
    entries = relationship("TrnAccounting", back_populates="voucher", cascade="all, delete-orphan")
    # Will be available when voucher module is imported
    # approvals = relationship("ApprovalRequest", back_populates="voucher", cascade="all, delete-orphan")

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
    forex_currency_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.currencies.currency_id"), nullable=True)
    forex_amount = Column(Numeric(18, 4), nullable=True)
    exchange_rate_used = Column(Numeric(14, 6), nullable=True)
    voucher = relationship("TrnVoucher", back_populates="entries")
    ledger = relationship("MstLedger")

# ==========================================
# MOVED FROM inventory.py
# ==========================================
class MstUom(Base):
    __tablename__ = "units_of_measure"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    unit_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    symbol = Column(String(100), nullable=False)
    decimal_places = Column(Integer, default=2)
    tally_alter_id = Column(BigInteger, nullable=True, index=True)
    items = relationship("MstStockItem", back_populates="unit")

class MstStockGroup(Base):
    __tablename__ = "stock_groups"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    stock_group_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    parent_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.stock_groups.stock_group_id", ondelete="SET NULL"), nullable=True)
    tally_alter_id = Column(BigInteger, nullable=True, index=True)
    parent = relationship("MstStockGroup", remote_side=[stock_group_id], backref="sub_groups")
    items = relationship("MstStockItem", back_populates="group")

class MstStockCategory(Base):
    __tablename__ = "stock_categories"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    stock_category_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    parent_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.stock_categories.stock_category_id", ondelete="SET NULL"), nullable=True)
    tally_alter_id = Column(BigInteger, nullable=True, index=True)
    parent = relationship("MstStockCategory", remote_side=[stock_category_id], backref="sub_categories")
    items = relationship("MstStockItem", back_populates="category")

class MstGodown(Base):
    __tablename__ = "godowns"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    godown_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    address = Column(String(300), nullable=True)
    tally_alter_id = Column(BigInteger, nullable=True, index=True)
    stock_entries = relationship("TrnInventory", back_populates="godown")

class MstStockItem(Base):
    __tablename__ = "stock_items"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    stock_item_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(150), nullable=False)
    stock_group_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.stock_groups.stock_group_id", ondelete="SET NULL"), nullable=True)
    stock_category_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.stock_categories.stock_category_id", ondelete="SET NULL"), nullable=True)
    unit_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.units_of_measure.unit_id"), nullable=False)
    hsn_code = Column(String(10), nullable=True)
    gst_rate_percent = Column(Numeric(5, 2), default=0.00)
    opening_qty = Column(Numeric(14, 3), default=0.00)
    opening_rate = Column(Numeric(14, 2), default=0.00)
    closing_qty = Column(Numeric(14, 3), default=0.00)
    closing_rate = Column(Numeric(14, 2), default=0.00)
    closing_value = Column(Numeric(14, 2), default=0.00)
    reorder_level = Column(Numeric(14, 3), default=0.00)
    tracking_type = Column(Enum('None', 'Batch', 'Serial', name='tracking_type_enum'), default='None')
    shelf_life_days = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    tally_alter_id = Column(BigInteger, nullable=True, index=True)
    unit = relationship("MstUom", back_populates="items")
    group = relationship("MstStockGroup", back_populates="items")
    category = relationship("MstStockCategory", back_populates="items")
    # Will be available when inventory module is imported
    # boms = relationship("BillOfMaterials", back_populates="stock_item", cascade="all, delete-orphan")

    @property
    def item_id(self):
        return self.stock_item_id

    @property
    def group_name(self):
        return self.group.name if self.group else "All"

    @property
    def uom(self):
        return self.unit.symbol if self.unit else "PCS"

    @property
    def closing_balance(self):
        return self.closing_qty

class Batch(Base):
    __tablename__ = "batches"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    batch_id = Column(BigInteger, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    stock_item_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.stock_items.stock_item_id"), nullable=False)
    batch_number = Column(String(50), nullable=False)
    manufacture_date = Column(Date, nullable=True)
    expiry_date = Column(Date, nullable=True)
    quantity_received = Column(Numeric(14, 3), nullable=False)
    quantity_available = Column(Numeric(14, 3), nullable=False)
    purchase_voucher_id = Column(BigInteger, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.vouchers.voucher_id", ondelete="SET NULL"), nullable=True)

class TrnInventory(Base):
    __tablename__ = "stock_entries"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    stock_entry_id = Column(BigInteger, primary_key=True, index=True)
    voucher_id = Column(BigInteger, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.vouchers.voucher_id", ondelete="CASCADE"), nullable=False)
    stock_item_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.stock_items.stock_item_id"), nullable=False)
    godown_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.godowns.godown_id"), nullable=True)
    batch_id = Column(BigInteger, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.batches.batch_id", ondelete="SET NULL"), nullable=True)
    serial_id = Column(BigInteger, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.serial_numbers.serial_id", ondelete="SET NULL"), nullable=True)
    quantity = Column(Numeric(14, 3), nullable=False)
    rate = Column(Numeric(14, 2), nullable=False)
    amount = Column(Numeric(18, 2), nullable=False)
    is_inward = Column(Boolean, default=True)
    godown = relationship("MstGodown", back_populates="stock_entries")
    stock_item = relationship("MstStockItem")
    batch = relationship("Batch")
    # Will be available when inventory module is imported
    # serial = relationship("SerialNumber")

# ==========================================
# MOVED FROM payment.py
# ==========================================
class TrnBill(Base):
    __tablename__ = "bills"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    bill_id = Column(BigInteger, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    party_ledger_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.ledgers.ledger_id"), nullable=False, index=True)
    voucher_id = Column(BigInteger, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.vouchers.voucher_id", ondelete="CASCADE"), nullable=False)
    bill_reference = Column(String(50), nullable=False)
    bill_date = Column(Date, nullable=False, index=True)
    due_date = Column(Date, nullable=True, index=True)
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
    created_at = Column(DateTime, server_default=func.now(), index=True)
    bill = relationship("TrnBill", back_populates="allocations")
