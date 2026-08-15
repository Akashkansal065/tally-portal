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
    alias = Column(String(100), nullable=True)
    allocate_revenue = Column(Boolean, default=True)
    allocate_non_revenue = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

class MstCostCentre(Base):
    __tablename__ = "cost_centres"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    cost_centre_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.cost_categories.category_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    alias = Column(String(100), nullable=True)
    parent_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.cost_centres.cost_centre_id", ondelete="SET NULL"), nullable=True, index=True)
    is_active = Column(Boolean, default=True)
    
    category = relationship("MstCostCategory")
    parent = relationship("MstCostCentre", remote_side=[cost_centre_id])

class MstCostCentreClass(Base):
    __tablename__ = "cost_centre_classes"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    
    class_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    
    allocations = relationship("MstCostCentreClassAllocation", back_populates="cost_centre_class", cascade="all, delete-orphan")

class MstCostCentreClassAllocation(Base):
    __tablename__ = "cost_centre_class_allocations"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    
    allocation_id = Column(Integer, primary_key=True, index=True)
    class_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.cost_centre_classes.class_id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.cost_categories.category_id", ondelete="CASCADE"), nullable=False)
    cost_centre_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.cost_centres.cost_centre_id", ondelete="CASCADE"), nullable=False)
    percentage = Column(Numeric(5, 2), nullable=False)
    
    cost_centre_class = relationship("MstCostCentreClass", back_populates="allocations")
    category = relationship("MstCostCategory")
    cost_centre = relationship("MstCostCentre")

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
    language_id = Column(Integer, default=1033)
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
class GstRegistration(Base):
    __tablename__ = "gst_registrations"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    gstin = Column(String(15), nullable=False)
    registered_state = Column(String(100), nullable=False)
    is_default = Column(Boolean, default=True)

class MstVoucherType(Base):
    __tablename__ = "voucher_types"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    voucher_type_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(50), nullable=False)
    parent_type = Column(String(50), nullable=True)
    abbreviation = Column(String(10), nullable=True)
    numbering_method = Column(Enum('Automatic', 'Automatic (Manual Override)', 'Manual', 'Multi-user Auto', 'None', name='numbering_method_type'), default='Automatic')
    numbering_behavior = Column(String(50), nullable=True) # 'Auto Retain', 'Auto Renumber'
    prefix = Column(String(20), default='')
    suffix = Column(String(20), default='')
    next_number = Column(Integer, default=1)
    width_of_numerical_part = Column(Integer, default=0)
    prefill_with_zero = Column(Boolean, default=False)
    prevent_duplicates = Column(Boolean, default=False)
    use_effective_dates = Column(Boolean, default=False)
    allow_zero_valued_transactions = Column(Boolean, default=False)
    is_optional_by_default = Column(Boolean, default=False)
    allow_narration_in_voucher = Column(Boolean, default=True)
    provide_narrations_for_each_ledger = Column(Boolean, default=False)
    print_voucher_after_saving = Column(Boolean, default=False)
    enable_default_accounting_allocations = Column(Boolean, default=False)
    track_additional_costs_for_purchases = Column(Boolean, default=False)
    default_jurisdiction = Column(String(100), nullable=True)
    default_title_to_print = Column(String(100), nullable=True)
    show_unused_vch_nos = Column(Boolean, default=False)
    whatsapp_voucher_after_saving = Column(Boolean, default=False)
    is_system_defined = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    tally_guid = Column(String(50), nullable=True, index=True)
    tally_alter_id = Column(Integer, nullable=True)
    vouchers = relationship("TrnVoucher", back_populates="voucher_type")
    
    prefixes = relationship("MstVoucherTypePrefix", back_populates="voucher_type", cascade="all, delete-orphan")
    suffixes = relationship("MstVoucherTypeSuffix", back_populates="voucher_type", cascade="all, delete-orphan")
    restarts = relationship("MstVoucherTypeRestart", back_populates="voucher_type", cascade="all, delete-orphan")
    classes = relationship("MstVoucherTypeClass", back_populates="voucher_type", cascade="all, delete-orphan")
    configuration = relationship("MstVoucherConfiguration", back_populates="voucher_type", uselist=False, cascade="all, delete-orphan")

class MstVoucherTypePrefix(Base):
    __tablename__ = "voucher_type_prefixes"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    id = Column(Integer, primary_key=True, index=True)
    voucher_type_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.voucher_types.voucher_type_id", ondelete="CASCADE"), nullable=False, index=True)
    applicable_from = Column(Date, nullable=False)
    particulars = Column(String(50), nullable=False)
    
    voucher_type = relationship("MstVoucherType", back_populates="prefixes")

class MstVoucherTypeSuffix(Base):
    __tablename__ = "voucher_type_suffixes"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    id = Column(Integer, primary_key=True, index=True)
    voucher_type_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.voucher_types.voucher_type_id", ondelete="CASCADE"), nullable=False, index=True)
    applicable_from = Column(Date, nullable=False)
    particulars = Column(String(50), nullable=False)
    
    voucher_type = relationship("MstVoucherType", back_populates="suffixes")

class MstVoucherTypeRestart(Base):
    __tablename__ = "voucher_type_restarts"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    id = Column(Integer, primary_key=True, index=True)
    voucher_type_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.voucher_types.voucher_type_id", ondelete="CASCADE"), nullable=False, index=True)
    applicable_from = Column(Date, nullable=False)
    starting_number = Column(Integer, nullable=False)
    periodicity = Column(String(30), nullable=False) # Yearly, Monthly, Daily, Never
    
    voucher_type = relationship("MstVoucherType", back_populates="restarts")

class MstVoucherTypeClass(Base):
    __tablename__ = "voucher_type_classes"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    class_id = Column(Integer, primary_key=True, index=True)
    voucher_type_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.voucher_types.voucher_type_id", ondelete="CASCADE"), nullable=False, index=True)
    class_name = Column(String(100), nullable=False)
    bank_alloc_for = Column(String(30), nullable=True) # Employees, Cost Centres, Both, None
    default_ledger_name = Column(String(100), nullable=True)
    
    voucher_type = relationship("MstVoucherType", back_populates="classes")
    groups = relationship("MstVoucherTypeClassGroup", back_populates="voucher_class", cascade="all, delete-orphan")

class MstVoucherTypeClassGroup(Base):
    __tablename__ = "voucher_type_class_groups"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    id = Column(Integer, primary_key=True, index=True)
    class_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.voucher_type_classes.class_id", ondelete="CASCADE"), nullable=False, index=True)
    group_name = Column(String(100), nullable=False)
    is_included = Column(Boolean, nullable=False, default=True) # True = Include, False = Exclude
    
    voucher_class = relationship("MstVoucherTypeClass", back_populates="groups")

class MstVoucherConfiguration(Base):
    __tablename__ = "voucher_configurations"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}

    config_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    voucher_type_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.voucher_types.voucher_type_id", ondelete="CASCADE"), nullable=False, unique=True)

    # General Details
    use_cr_dr = Column(Boolean, default=True)
    provide_supplier_ref = Column(Boolean, default=False)
    warn_negative_cash = Column(Boolean, default=True)
    preallocate_bills = Column(Boolean, default=False)
    show_bill_wise_details = Column(Boolean, default=True)
    show_bill_wise_multiple_lines = Column(Boolean, default=True)
    show_list_of_bills = Column(Boolean, default=True)
    show_final_bill_balances = Column(Boolean, default=True)
    skip_date_field = Column(Boolean, default=False)
    show_inventory_details = Column(Boolean, default=False)
    show_ledger_current_balance = Column(Boolean, default=True)
    warn_voucher_number_length = Column(Boolean, default=True)
    enable_stripe_view = Column(Boolean, default=False)

    # Sales / Invoice Specific Details
    provide_buyer_details = Column(Boolean, default=True)
    provide_dispatch_order_export = Column(Boolean, default=True)
    provide_order_details = Column(Boolean, default=True)
    select_common_sales_ledger = Column(Boolean, default=True)
    use_vch_no_as_bill_ref = Column(Boolean, default=True)
    warn_negative_stock = Column(Boolean, default=True)
    provide_trade_discount = Column(Boolean, default=False)
    rate_inclusive_of_tax = Column(Boolean, default=False)
    show_party_turnover = Column(Boolean, default=False)

    # Bank Details
    use_default_bank_allocations = Column(Boolean, default=False)
    auto_cheque_numbering = Column(Boolean, default=True)
    select_cheque_range = Column(Boolean, default=True)
    set_ledger_bank_allocations = Column(Boolean, default=False)
    print_cheque_after_saving = Column(Boolean, default=False)
    show_cheque_details_before_printing = Column(Boolean, default=True)
    provide_cash_denominations = Column(Boolean, default=False)

    # Payment Gateway Details
    use_default_pg_allocations = Column(Boolean, default=False)
    set_ledger_pg_allocations = Column(Boolean, default=False)

    # GST & E-Way Bill Details
    provide_party_gst_details = Column(Boolean, default=False)
    modify_gst_hsn_details = Column(Boolean, default=False)
    send_eway_bill_details = Column(Boolean, default=True)

    voucher_type = relationship("MstVoucherType", back_populates="configuration")
    company = relationship("Company")


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
    status = Column(Enum('draft', 'optional', 'confirmed', 'cancelled', name='voucher_status'), default='confirmed')
    party_ledger_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.ledgers.ledger_id", ondelete="SET NULL"), nullable=True)
    persisted_view = Column(String(50), default='Accounting Voucher View')
    is_invoice = Column(Boolean, default=False)
    is_cancelled = Column(Boolean, default=False, nullable=False)
    is_optional = Column(Boolean, default=False, nullable=False)
    original_voucher_id = Column(BigInteger, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.vouchers.voucher_id", ondelete="SET NULL"), nullable=True)
    gst_registration_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.gst_registrations.id", ondelete="SET NULL"), nullable=True)
    tally_guid = Column(String(50), nullable=True, index=True)
    tally_alter_id = Column(Integer, nullable=True)
    created_by = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), index=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    voucher_type = relationship("MstVoucherType", back_populates="vouchers")
    entries = relationship("TrnAccounting", back_populates="voucher", cascade="all, delete-orphan")
    inventory_entries = relationship("TrnInventory", back_populates="voucher", cascade="all, delete-orphan")
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
    bank_allocations = relationship("TrnBankAllocation", back_populates="entry", cascade="all, delete-orphan")
    bill_allocations = relationship("BillAllocation", back_populates="entry", cascade="all, delete-orphan")

class TrnBankAllocation(Base):
    __tablename__ = "bank_allocations"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    allocation_id = Column(BigInteger, primary_key=True, index=True)
    entry_id = Column(BigInteger, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.voucher_entries.entry_id", ondelete="CASCADE"), nullable=False, index=True)
    instrument_date = Column(Date, nullable=True)
    transaction_type = Column(String(50), nullable=False)
    payment_favouring = Column(String(150), nullable=True)
    instrument_number = Column(String(50), nullable=True)
    amount = Column(Numeric(18, 2), nullable=False)
    transfer_mode = Column(String(50), nullable=True)
    virtual_payment_address = Column(String(100), nullable=True)
    cheque_cross_comment = Column(String(50), nullable=True)
    bank_name = Column(String(150), nullable=True)
    account_number = Column(String(50), nullable=True)
    ifs_code = Column(String(20), nullable=True)
    is_connected_payment = Column(Boolean, default=False)
    
    entry = relationship("TrnAccounting", back_populates="bank_allocations")
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
    original_name = Column(String(100), nullable=True)
    is_simple_unit = Column(Boolean, default=True)
    decimal_places = Column(Integer, default=2)
    base_unit_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.units_of_measure.unit_id", ondelete="SET NULL"), nullable=True)
    additional_unit_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.units_of_measure.unit_id", ondelete="SET NULL"), nullable=True)
    conversion_factor = Column(Numeric(12, 4), nullable=True)
    tally_alter_id = Column(BigInteger, nullable=True, index=True)
    
    base_unit = relationship("MstUom", foreign_keys=[base_unit_id], remote_side=[unit_id])
    additional_unit = relationship("MstUom", foreign_keys=[additional_unit_id], remote_side=[unit_id])
    items = relationship("MstStockItem", back_populates="unit", foreign_keys="MstStockItem.unit_id")

class StockGroupAlias(Base):
    __tablename__ = "stock_group_aliases"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    id = Column(Integer, primary_key=True, index=True)
    stock_group_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.stock_groups.stock_group_id", ondelete="CASCADE"), nullable=False)
    alias = Column(String(255), nullable=False)
    
    stock_group = relationship("MstStockGroup", back_populates="aliases")

class MstStockGroup(Base):
    __tablename__ = "stock_groups"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    stock_group_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    parent_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.stock_groups.stock_group_id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, default=True)
    tally_alter_id = Column(BigInteger, nullable=True, index=True)
    
    parent = relationship("MstStockGroup", remote_side=[stock_group_id], backref="sub_groups")
    items = relationship("MstStockItem", back_populates="group")
    aliases = relationship("StockGroupAlias", back_populates="stock_group", cascade="all, delete-orphan")

class MstStockCategory(Base):
    __tablename__ = "stock_categories"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    stock_category_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    parent_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.stock_categories.stock_category_id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, default=True)
    tally_alter_id = Column(BigInteger, nullable=True, index=True)
    
    parent = relationship("MstStockCategory", remote_side=[stock_category_id], backref="sub_categories")
    items = relationship("MstStockItem", back_populates="category")

class MstGodown(Base):
    __tablename__ = "godowns"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    godown_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    address = Column(TEXT, nullable=True)
    parent_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.godowns.godown_id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, default=True)
    contact_person = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)
    tally_alter_id = Column(BigInteger, nullable=True, index=True)
    
    parent = relationship("MstGodown", remote_side=[godown_id], backref="sub_godowns")
    stock_entries = relationship("TrnInventory", back_populates="godown")

class StockItemAlias(Base):
    __tablename__ = "stock_item_aliases"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    id = Column(BigInteger, primary_key=True, index=True)
    stock_item_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.stock_items.stock_item_id", ondelete="CASCADE"), nullable=False)
    alias = Column(String(255), nullable=False)
    alias_type = Column(String(20), default="name")  # "name" or "part_number"
    
    stock_item = relationship("MstStockItem", back_populates="aliases")

class StockItemPriceList(Base):
    __tablename__ = "stock_item_price_lists"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    id = Column(BigInteger, primary_key=True, index=True)
    stock_item_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.stock_items.stock_item_id", ondelete="CASCADE"), nullable=False)
    price_type = Column(String(20), nullable=False)  # "cost" or "selling"
    effective_from = Column(Date, nullable=False)
    rate = Column(Numeric(14, 2), nullable=False)
    
    stock_item = relationship("MstStockItem", back_populates="price_lists")

class StockItemOpeningBalance(Base):
    __tablename__ = "stock_item_opening_balances"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    id = Column(BigInteger, primary_key=True, index=True)
    stock_item_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.stock_items.stock_item_id", ondelete="CASCADE"), nullable=False)
    godown_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.godowns.godown_id"), nullable=True)
    batch_name = Column(String(50), nullable=True)
    quantity = Column(Numeric(14, 3), nullable=False, default=0)
    rate = Column(Numeric(14, 2), nullable=False, default=0)
    amount = Column(Numeric(18, 2), nullable=False, default=0)
    
    stock_item = relationship("MstStockItem", back_populates="opening_balances")
    godown = relationship("MstGodown")

class MstPriceLevel(Base):
    __tablename__ = "price_levels"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    price_level_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True)
    tally_alter_id = Column(BigInteger, nullable=True, index=True)

class StockItemPriceLevelRate(Base):
    __tablename__ = "stock_item_price_level_rates"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    id = Column(BigInteger, primary_key=True, index=True)
    stock_item_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.stock_items.stock_item_id", ondelete="CASCADE"), nullable=False)
    price_level_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.price_levels.price_level_id", ondelete="CASCADE"), nullable=False)
    effective_from = Column(Date, nullable=False)
    qty_from = Column(Numeric(14, 3), nullable=True)
    qty_to = Column(Numeric(14, 3), nullable=True)
    rate = Column(Numeric(14, 2), nullable=False)
    discount_percent = Column(Numeric(5, 2), nullable=True, default=0)
    
    stock_item = relationship("MstStockItem", back_populates="price_level_rates")
    price_level = relationship("MstPriceLevel")

class StockItemBOM(Base):
    __tablename__ = "stock_item_boms"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    bom_id = Column(Integer, primary_key=True, index=True)
    stock_item_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.stock_items.stock_item_id", ondelete="CASCADE"), nullable=False)
    bom_name = Column(String(100), nullable=False)
    unit_of_manufacture = Column(Numeric(14, 3), nullable=False, default=1)
    is_active = Column(Boolean, default=True)
    
    stock_item = relationship("MstStockItem", back_populates="boms")
    components = relationship("StockItemBOMComponent", back_populates="bom", cascade="all, delete-orphan")

class StockItemBOMComponent(Base):
    __tablename__ = "stock_item_bom_components"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    id = Column(BigInteger, primary_key=True, index=True)
    bom_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.stock_item_boms.bom_id", ondelete="CASCADE"), nullable=False)
    component_item_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.stock_items.stock_item_id", ondelete="RESTRICT"), nullable=False)
    godown_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.godowns.godown_id", ondelete="SET NULL"), nullable=True)
    quantity = Column(Numeric(14, 3), nullable=False)
    component_type = Column(String(50), nullable=False, default="Component") # Component, Scrap, By-Product, Co-Product
    
    bom = relationship("StockItemBOM", back_populates="components")
    component_item = relationship("MstStockItem", foreign_keys=[component_item_id])
    godown = relationship("MstGodown")

class MstStockItem(Base):
    __tablename__ = "stock_items"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    stock_item_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    stock_group_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.stock_groups.stock_group_id", ondelete="SET NULL"), nullable=True)
    stock_category_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.stock_categories.stock_category_id", ondelete="SET NULL"), nullable=True)
    unit_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.units_of_measure.unit_id", ondelete="RESTRICT"), nullable=False)
    
    # New Phase C fields
    alt_unit_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.units_of_measure.unit_id", ondelete="SET NULL"), nullable=True)
    alt_unit_conversion = Column(Numeric(12, 4), nullable=True)
    description = Column(TEXT, nullable=True)
    standard_cost_price = Column(Numeric(14, 2), nullable=True)
    standard_selling_price = Column(Numeric(14, 2), nullable=True)
    image_url = Column(String(255), nullable=True) # If Tally supports, we can at least store an image URL for the web
    
    hsn_code = Column(String(20), nullable=True)
    gst_rate_percent = Column(Numeric(5, 2), default=0)
    
    opening_qty = Column(Numeric(14, 3), default=0)
    opening_rate = Column(Numeric(14, 2), default=0)
    closing_qty = Column(Numeric(14, 3), default=0)
    closing_rate = Column(Numeric(14, 2), default=0)
    closing_value = Column(Numeric(18, 2), default=0)
    
    reorder_level = Column(Numeric(14, 3), default=0)
    minimum_order_qty = Column(Numeric(14, 3), default=0)
    tracking_type = Column(String(20), default="None")
    shelf_life_days = Column(Integer, nullable=True)
    
    is_active = Column(Boolean, default=True)
    tally_alter_id = Column(BigInteger, nullable=True, index=True)
    
    group = relationship("MstStockGroup", back_populates="items")
    category = relationship("MstStockCategory", back_populates="items")
    unit = relationship("MstUom", foreign_keys=[unit_id], back_populates="items")
    alt_unit = relationship("MstUom", foreign_keys=[alt_unit_id])
    
    aliases = relationship("StockItemAlias", back_populates="stock_item", cascade="all, delete-orphan")
    price_lists = relationship("StockItemPriceList", back_populates="stock_item", cascade="all, delete-orphan")
    opening_balances = relationship("StockItemOpeningBalance", back_populates="stock_item", cascade="all, delete-orphan")
    
    boms = relationship("StockItemBOM", back_populates="stock_item", cascade="all, delete-orphan")
    price_level_rates = relationship("StockItemPriceLevelRate", back_populates="stock_item", cascade="all, delete-orphan")
    
    stock_entries = relationship("TrnInventory", back_populates="stock_item")# Will be available when inventory module is imported
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
    billed_qty = Column(Numeric(14, 3), nullable=True)
    rate = Column(Numeric(14, 2), nullable=False)
    rate_unit_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.units_of_measure.unit_id", ondelete="SET NULL"), nullable=True)
    amount = Column(Numeric(18, 2), nullable=False)
    discount_percent = Column(Numeric(5, 2), nullable=True, default=0.00)
    discount_amount = Column(Numeric(18, 2), nullable=True, default=0.00)
    is_inward = Column(Boolean, default=True)
    is_deemed_positive = Column(Boolean, default=True)
    flow_type = Column(Enum('source', 'destination', name='stock_flow_type'), nullable=True)
    
    voucher = relationship("TrnVoucher", back_populates="inventory_entries")
    godown = relationship("MstGodown", back_populates="stock_entries")
    stock_item = relationship("MstStockItem")
    batch = relationship("Batch")
    rate_unit = relationship("MstUom")
    accounting_allocations = relationship("VoucherAccountingAllocation", back_populates="stock_entry", cascade="all, delete-orphan")
    # Will be available when inventory module is imported
    # serial = relationship("SerialNumber")

class VoucherAccountingAllocation(Base):
    __tablename__ = "voucher_accounting_allocations"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    id = Column(BigInteger, primary_key=True, index=True)
    stock_entry_id = Column(BigInteger, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.stock_entries.stock_entry_id", ondelete="CASCADE"), nullable=False, index=True)
    ledger_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.ledgers.ledger_id"), nullable=False)
    is_deemed_positive = Column(Boolean, nullable=False)
    amount = Column(Numeric(18, 2), nullable=False)
    
    stock_entry = relationship("TrnInventory", back_populates="accounting_allocations")
    ledger = relationship("MstLedger")

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
    entry = relationship("TrnAccounting", back_populates="bill_allocations")
