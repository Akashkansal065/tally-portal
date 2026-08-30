from sqlalchemy import Column, Integer, BigInteger, String, Date, Boolean, DateTime, ForeignKey, Enum, Numeric, Text, TEXT, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.core.config import settings
from app.models.tally_core import *

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
    status = Column(String(50), default="PENDING") # PENDING, PROCESSING, SUCCESS, FAILED, EXCEPTION
    last_payload = Column(Text, nullable=True)
    last_response = Column(Text, nullable=True)
    last_attempt_at = Column(DateTime, nullable=True)
    snapshot_data = Column(JSON, nullable=True) # Pre-alter snapshot for rollback if sync fails
    created_at = Column(DateTime, server_default=func.now())

class SyncTrafficLog(Base):
    __tablename__ = "sync_traffic_logs"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}

    log_id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    sync_id = Column(BigInteger, nullable=True, index=True)
    entity_type = Column(String(50), nullable=False, index=True) # Voucher, Ledger, StockItem, Group, VoucherType
    entity_id = Column(BigInteger, nullable=True, index=True)
    entity_name = Column(String(255), nullable=True) # e.g. "Purchase #27", "Amar Enterprises"
    action = Column(String(50), nullable=False) # Create, Alter, Delete, Cancel, Query
    status = Column(String(50), nullable=False, index=True) # SUCCESS, FAILED, EXCEPTION, TIMEOUT, CONFLICT
    http_status = Column(Integer, default=200)
    outbound_format = Column(String(20), default="XML") # XML, JSONEX, JSON
    outbound_payload = Column(Text, nullable=True)
    curl_command = Column(Text, nullable=True) # Copy-paste ready for Postman / Terminal
    inbound_response = Column(Text, nullable=True)
    error_summary = Column(String(500), nullable=True)
    parsed_created = Column(Integer, default=0)
    parsed_altered = Column(Integer, default=0)
    parsed_deleted = Column(Integer, default=0)
    parsed_errors = Column(Integer, default=0)
    parsed_exceptions = Column(Integer, default=0)
    tally_vchnumber = Column(String(50), nullable=True)
    duration_ms = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now(), index=True)

class DeletedRecordAudit(Base):
    __tablename__ = "deleted_records_audit"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}

    audit_id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False, index=True) # Voucher, Ledger, StockItem, Group, VoucherType
    record_id = Column(BigInteger, nullable=False, index=True)
    tally_guid = Column(String(150), nullable=True, index=True)
    entity_identifier = Column(String(255), nullable=True) # e.g. "Purchase #27", "Amar Enterprises"
    deleted_by_user_id = Column(Integer, nullable=True)
    tally_sync_status = Column(String(50), default="PENDING") # PENDING, SYNCED_TO_TALLY, ALREADY_DELETED_IN_TALLY, SYNC_FAILED, NOT_DELETED_IN_TALLY
    tally_error_message = Column(String(500), nullable=True)
    snapshot_data = Column(JSON, nullable=True) # Full JSON snapshot before deletion for audit / rollback
    deleted_at = Column(DateTime, server_default=func.now(), index=True)

class SalaryComponent(Base):
    __tablename__ = "salary_components"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    component_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(60), nullable=False)
    component_type = Column(Enum('Earning', 'Deduction', name='salary_component_type'), nullable=False)
    calculation_type = Column(Enum('Fixed', 'Percent of Basic', 'Formula', name='salary_calculation_type'), default='Fixed')
    percent_of_basic = Column(Numeric(5, 2), nullable=True)
    is_statutory = Column(Boolean, default=False)
    linked_ledger_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.ledgers.ledger_id"), nullable=False)

class SalaryStructure(Base):
    __tablename__ = "salary_structures"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    structure_id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.employees.employee_id", ondelete="CASCADE"), nullable=False)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=True)
    ctc_annual = Column(Numeric(18, 2), nullable=False)
    
    components = relationship("SalaryStructureComponent", back_populates="structure", cascade="all, delete-orphan")

class SalaryStructureComponent(Base):
    __tablename__ = "salary_structure_components"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    structure_component_id = Column(BigInteger, primary_key=True, index=True)
    structure_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.salary_structures.structure_id", ondelete="CASCADE"), nullable=False)
    component_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.salary_components.component_id"), nullable=False)
    amount = Column(Numeric(18, 2), nullable=False)
    
    structure = relationship("SalaryStructure", back_populates="components")
    component = relationship("SalaryComponent")

class PayrollPeriod(Base):
    __tablename__ = "payroll_periods"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    period_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    period_month = Column(Integer, nullable=False)
    period_year = Column(Integer, nullable=False)
    status = Column(Enum('Draft', 'Processed', 'Paid', 'Locked', name='payroll_period_status'), default='Draft')
    processed_at = Column(DateTime, nullable=True)
    processed_by = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id"), nullable=True)

class Payslip(Base):
    __tablename__ = "payslips"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    payslip_id = Column(BigInteger, primary_key=True, index=True)
    period_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.payroll_periods.period_id", ondelete="CASCADE"), nullable=False)
    employee_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.employees.employee_id"), nullable=False)
    days_present = Column(Numeric(4, 1), nullable=False)
    days_in_period = Column(Integer, nullable=False)
    gross_earnings = Column(Numeric(18, 2), nullable=False)
    total_deductions = Column(Numeric(18, 2), nullable=False)
    net_pay = Column(Numeric(18, 2), nullable=False)
    voucher_id = Column(BigInteger, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.vouchers.voucher_id", ondelete="SET NULL"), nullable=True)
    payment_voucher_id = Column(BigInteger, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.vouchers.voucher_id", ondelete="SET NULL"), nullable=True)
    generated_at = Column(DateTime, server_default=func.now())
    
    period = relationship("PayrollPeriod")
    # employee = relationship("Employee")
    # voucher = relationship("TrnVoucher", foreign_keys=[voucher_id])
    # payment_voucher = relationship("TrnVoucher", foreign_keys=[payment_voucher_id])
    components = relationship("PayslipComponent", back_populates="payslip", cascade="all, delete-orphan")

class PayslipComponent(Base):
    __tablename__ = "payslip_components"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    payslip_component_id = Column(BigInteger, primary_key=True, index=True)
    payslip_id = Column(BigInteger, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.payslips.payslip_id", ondelete="CASCADE"), nullable=False)
    component_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.salary_components.component_id"), nullable=False)
    amount = Column(Numeric(18, 2), nullable=False)
    
    payslip = relationship("Payslip", back_populates="components")
    component = relationship("SalaryComponent")

class EinvoiceMetadata(Base):
    __tablename__ = "einvoice_metadata"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    metadata_id = Column(Integer, primary_key=True, index=True)
    voucher_id = Column(BigInteger, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.vouchers.voucher_id", ondelete="CASCADE"), nullable=False)
    irn = Column(String(64), nullable=True)
    ack_no = Column(String(30), nullable=True)
    ack_date = Column(DateTime, nullable=True)
    eway_bill_no = Column(String(20), nullable=True)
    eway_bill_date = Column(DateTime, nullable=True)
    raw_response = Column(TEXT, nullable=True)
    environment = Column(String(20), default='mock')



class MstBudget(Base):
    __tablename__ = "budgets"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}

    budget_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    period_from = Column(Date, nullable=False)
    period_to = Column(Date, nullable=False)
    is_active = Column(Boolean, default=True)

class MstScenario(Base):
    __tablename__ = "scenarios"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}

    scenario_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    include_actuals = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)



class MstEmployeeCategory(Base):
    __tablename__ = "employee_categories"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}

    category_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    allocate_revenue = Column(Boolean, default=True)

class MstEmployeeGroup(Base):
    __tablename__ = "employee_groups"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}

    group_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    category_id = Column(Integer, nullable=True)
    parent_group_id = Column(Integer, nullable=True)

class MstGstRegistration(Base):
    __tablename__ = "gst_registrations"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}

    gst_reg_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    state = Column(String(100), nullable=False)
    gst_registration_type = Column(String(50), default="Regular")
    gstin = Column(String(20), nullable=False)
    applicable_from = Column(Date, nullable=False)
    place_of_supply = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)

class Role(Base):
    __tablename__ = "roles"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    role_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True)
    description = Column(String(200), nullable=True)
    
    users = relationship("User", back_populates="role")
    permissions = relationship("Permission", back_populates="role", cascade="all, delete-orphan")

class UserCompanyAccess(Base):
    __tablename__ = "user_company_access"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    access_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id", ondelete="CASCADE"), nullable=False)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    
    user = relationship("User", back_populates="company_access")
    company = relationship("Company")

class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    user_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    username = Column(String(50), nullable=False)
    email = Column(String(120), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.roles.role_id"), nullable=False)
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    

    ledger_scope = Column(String(64), default='dr_only')
    stock_scope = Column(String(64), default='full')
    allowed_stock_groups = Column(String(1024), nullable=True)
    allowed_ledger_groups = Column(String(1024), nullable=True)
    allowed_report_categories = Column(String(1024), nullable=True)
    
    company = relationship("Company", back_populates="users")
    role = relationship("Role", back_populates="users")
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    overrides = relationship("UserPermissionOverride", back_populates="user", cascade="all, delete-orphan", foreign_keys="[UserPermissionOverride.user_id]")
    granted_overrides = relationship("UserPermissionOverride", back_populates="granter", foreign_keys="[UserPermissionOverride.granted_by]")
    company_access = relationship("UserCompanyAccess", back_populates="user", cascade="all, delete-orphan")

class Module(Base):
    __tablename__ = "modules"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    module_id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), nullable=False, unique=True)
    name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)
    is_system = Column(Boolean, default=True)
    
    permissions = relationship("Permission", back_populates="module", cascade="all, delete-orphan")
    overrides = relationship("UserPermissionOverride", back_populates="module", cascade="all, delete-orphan")

class Permission(Base):
    __tablename__ = "permissions"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    permission_id = Column(Integer, primary_key=True, index=True)
    role_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.roles.role_id", ondelete="CASCADE"), nullable=False)
    module_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.modules.module_id"), nullable=True)
    can_create = Column(Boolean, default=False)
    can_read = Column(Boolean, default=True)
    can_update = Column(Boolean, default=False)
    can_delete = Column(Boolean, default=False)
    
    role = relationship("Role", back_populates="permissions")
    module = relationship("Module", back_populates="permissions")

class UserPermissionOverride(Base):
    __tablename__ = "user_permission_overrides"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    override_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id", ondelete="CASCADE"), nullable=False)
    module_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.modules.module_id"), nullable=False)
    can_create = Column(Boolean, nullable=True)
    can_read = Column(Boolean, nullable=True)
    can_update = Column(Boolean, nullable=True)
    can_delete = Column(Boolean, nullable=True)
    reason = Column(String(255), nullable=True)
    granted_by = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id"), nullable=False)
    granted_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="overrides", foreign_keys=[user_id])
    module = relationship("Module", back_populates="overrides")
    granter = relationship("User", back_populates="granted_overrides", foreign_keys=[granted_by])

class UserDataScope(Base):
    __tablename__ = "user_data_scopes"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    scope_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id", ondelete="CASCADE"), nullable=False)
    scope_type = Column(Enum('Godown', 'CostCenter', 'VoucherType', name='user_data_scope_type'), nullable=False)
    scope_ref_id = Column(Integer, nullable=False)

class UserSession(Base):
    __tablename__ = "user_sessions"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    session_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String(255), nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="sessions")

class Company(Base):
    __tablename__ = "companies"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    company_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    gstin = Column(String(15), nullable=True)
    pan = Column(String(10), nullable=True)
    address_line1 = Column(String(200), nullable=True)
    address_line2 = Column(String(200), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    pincode = Column(String(10), nullable=True)
    country = Column(String(100), default="India")
    base_currency = Column(String(10), default="INR")
    books_begin_date = Column(Date, nullable=False)
    is_active = Column(Boolean, default=True)
    telephone = Column(String(20), nullable=True)
    mobile = Column(String(20), nullable=True)
    email = Column(String(100), nullable=True)
    website = Column(String(150), nullable=True)
    financial_year_start = Column(Date, nullable=True)
    financial_year_end = Column(Date, nullable=True)
    features = Column(JSON, nullable=True)
    einvoice_env = Column(String(20), default='mock')
    tally_guid = Column(String(100), nullable=True, index=True)
    einvoice_username = Column(String(100), nullable=True)
    einvoice_password = Column(String(255), nullable=True)
    einvoice_gsp_client_id = Column(String(100), nullable=True)
    einvoice_gsp_client_secret = Column(String(255), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    financial_years = relationship("FinancialYear", back_populates="company", cascade="all, delete-orphan")
    users = relationship("User", back_populates="company", cascade="all, delete-orphan")

class FinancialYear(Base):
    __tablename__ = "financial_years"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    fy_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    is_locked = Column(Boolean, default=False)
    
    company = relationship("Company", back_populates="financial_years")

class PaymentGatewayConfig(Base):
    __tablename__ = "payment_gateway_configs"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    gateway_config_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    gateway = Column(Enum('Razorpay', 'Stripe', name='gateway_provider_enum'), nullable=False)
    public_key = Column(String(255), nullable=False)
    secret_key_ref = Column(String(100), nullable=False)
    webhook_secret_ref = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True)
    is_test_mode = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

class PaymentLink(Base):
    __tablename__ = "payment_links"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    payment_link_id = Column(BigInteger, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    bill_id = Column(BigInteger, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.bills.bill_id", ondelete="CASCADE"), nullable=False)
    gateway_config_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.payment_gateway_configs.gateway_config_id"), nullable=False)
    gateway_link_id = Column(String(100), nullable=True)
    link_url = Column(String(500), nullable=True)
    amount = Column(Numeric(18, 2), nullable=False)
    currency = Column(String(3), default="INR")
    status = Column(Enum('Created', 'Sent', 'Paid', 'Expired', 'Cancelled', name='payment_link_status_enum'), default='Created')
    expires_at = Column(DateTime, nullable=True)
    created_by = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

class GatewayTransaction(Base):
    __tablename__ = "gateway_transactions"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    transaction_id = Column(BigInteger, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    payment_link_id = Column(BigInteger, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.payment_links.payment_link_id", ondelete="SET NULL"), nullable=True)
    bill_id = Column(BigInteger, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.bills.bill_id"), nullable=False)
    gateway_config_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.payment_gateway_configs.gateway_config_id"), nullable=False)
    gateway_payment_id = Column(String(100), nullable=False)
    gateway_order_id = Column(String(100), nullable=True)
    amount = Column(Numeric(18, 2), nullable=False)
    currency = Column(String(3), default="INR")
    status = Column(Enum('Created', 'Authorized', 'Captured', 'Failed', 'Refunded', 'Partially Refunded', name='gateway_txn_status_enum'), nullable=False)
    failure_reason = Column(String(255), nullable=True)
    method = Column(String(30), nullable=True)
    voucher_id = Column(BigInteger, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.vouchers.voucher_id", ondelete="SET NULL"), nullable=True)
    raw_payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    webhook_event_id = Column(BigInteger, primary_key=True, index=True)
    gateway_config_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.payment_gateway_configs.gateway_config_id", ondelete="CASCADE"), nullable=False)
    gateway_event_id = Column(String(150), nullable=False)
    event_type = Column(String(60), nullable=False)
    payload = Column(JSON, nullable=False)
    signature_verified = Column(Boolean, default=False)
    processed = Column(Boolean, default=False)
    processing_error = Column(String(500), nullable=True)
    received_at = Column(DateTime, server_default=func.now())
    processed_at = Column(DateTime, nullable=True)

class Currency(Base):
    __tablename__ = "currencies"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    currency_id = Column(Integer, primary_key=True, index=True)
    code = Column(String(3), nullable=False, unique=True)
    symbol = Column(String(10), nullable=False)
    formal_name = Column(String(100), nullable=True)
    decimal_places = Column(Integer, default=2)
    show_amount_in_millions = Column(Boolean, default=False)
    suffix_symbol_to_amount = Column(Boolean, default=False)
    add_space_between_amount_and_symbol = Column(Boolean, default=True)
    word_representing_amount_after_decimal = Column(String(50), nullable=True)
    decimal_places_for_words = Column(Integer, default=2)
    is_base_currency = Column(Boolean, default=False)
    
    rates = relationship("ExchangeRate", back_populates="currency", cascade="all, delete-orphan")

class GstRegistrationType(Base):
    __tablename__ = "gst_registration_types"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    code = Column(String(50), nullable=False, unique=True)
    requires_gstin = Column(Boolean, default=True)
    display_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

class ExchangeRate(Base):
    __tablename__ = "exchange_rates"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    rate_id = Column(BigInteger, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    currency_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.currencies.currency_id", ondelete="CASCADE"), nullable=False)
    rate_date = Column(Date, nullable=False)
    standard_rate = Column(Numeric(14, 6), nullable=True)
    selling_rate = Column(Numeric(14, 6), nullable=True)
    buying_rate = Column(Numeric(14, 6), nullable=True)
    source = Column(Enum('Manual', 'RBI', 'API', name='exchange_rate_source'), default='Manual')
    
    currency = relationship("Currency", back_populates="rates")

class TdsSection(Base):
    __tablename__ = "tds_sections"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    section_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    section_code = Column(String(10), nullable=False)
    description = Column(String(150), nullable=False)
    default_rate_percent = Column(Numeric(5, 2), nullable=False)
    threshold_limit = Column(Numeric(18, 2), default=0.00)

class TcsSection(Base):
    __tablename__ = "tcs_sections"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    section_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    section_code = Column(String(10), nullable=False)
    description = Column(String(150), nullable=False)
    default_rate_percent = Column(Numeric(5, 2), nullable=False)
    threshold_limit = Column(Numeric(18, 2), default=0.00)

class LowerDeductionCertificate(Base):
    __tablename__ = "lower_deduction_certificates"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    certificate_id = Column(Integer, primary_key=True, index=True)
    party_ledger_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.ledgers.ledger_id"), nullable=False)
    section_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.tds_sections.section_id"), nullable=False)
    certificate_number = Column(String(50), nullable=False)
    reduced_rate_percent = Column(Numeric(5, 2), nullable=False)
    valid_from = Column(Date, nullable=False)
    valid_to = Column(Date, nullable=False)
    
    # ledger = relationship("MstLedger")
    tds_section = relationship("TdsSection")

class TdsTcsEntry(Base):
    __tablename__ = "tds_tcs_entries"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    entry_id = Column(BigInteger, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    entry_type = Column(Enum('TDS', 'TCS', name='tds_tcs_type'), nullable=False)
    voucher_id = Column(BigInteger, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.vouchers.voucher_id", ondelete="CASCADE"), nullable=False)
    party_ledger_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.ledgers.ledger_id"), nullable=False)
    section_id = Column(Integer, nullable=False)  # references either tds_sections or tcs_sections depending on entry_type
    taxable_amount = Column(Numeric(18, 2), nullable=False)
    rate_percent_applied = Column(Numeric(5, 2), nullable=False)
    tax_amount = Column(Numeric(18, 2), nullable=False)
    certificate_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.lower_deduction_certificates.certificate_id"), nullable=True)
    deduction_date = Column(Date, nullable=False)
    
    # voucher = relationship("TrnVoucher")
    # party = relationship("MstLedger")
    ldc = relationship("LowerDeductionCertificate")

class TaxChallan(Base):
    __tablename__ = "tax_challans"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    challan_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    entry_type = Column(Enum('TDS', 'TCS', name='challan_entry_type'), nullable=False)
    challan_number = Column(String(30), nullable=False)
    bsr_code = Column(String(10), nullable=False)
    payment_date = Column(Date, nullable=False)
    amount = Column(Numeric(18, 2), nullable=False)
    quarter = Column(Integer, nullable=False)
    financial_year = Column(String(9), nullable=False)

class ChallanEntryMap(Base):
    __tablename__ = "challan_entry_map"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    map_id = Column(BigInteger, primary_key=True, index=True)
    challan_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.tax_challans.challan_id", ondelete="CASCADE"), nullable=False)
    entry_id = Column(BigInteger, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.tds_tcs_entries.entry_id", ondelete="CASCADE"), nullable=False)

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
    requested_at = Column(DateTime, server_default=func.now(), index=True)
    acted_at = Column(DateTime, nullable=True, index=True)
    
    voucher = relationship("TrnVoucher", backref="approvals")

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
    created_at = Column(DateTime, server_default=func.now(), index=True)

class GstReturnPeriod(Base):
    __tablename__ = "gst_return_periods"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    return_period_id = Column(BigInteger, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    return_type = Column(Enum('GSTR1', 'GSTR3B', name='gst_return_type_enum'), nullable=False)
    period_month = Column(Integer, nullable=False)
    period_year = Column(Integer, nullable=False)
    status = Column(Enum('Draft', 'Filed', name='gst_return_status_enum'), default='Draft')
    filed_date = Column(Date, nullable=True)
    arn = Column(String(30), nullable=True)
    filed_by = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id"), nullable=True)
    
    company = relationship("Company")
    user = relationship("User")
    gstr1_lines = relationship("Gstr1LineItem", back_populates="period", cascade="all, delete-orphan")
    gstr1_hsn_summaries = relationship("Gstr1HsnSummary", back_populates="period", cascade="all, delete-orphan")
    gstr3b_summary = relationship("Gstr3bSummary", uselist=False, back_populates="period", cascade="all, delete-orphan")

class Gstr1LineItem(Base):
    __tablename__ = "gstr1_line_items"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    line_item_id = Column(BigInteger, primary_key=True, index=True)
    return_period_id = Column(BigInteger, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.gst_return_periods.return_period_id", ondelete="CASCADE"), nullable=False)
    voucher_id = Column(BigInteger, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.vouchers.voucher_id"), nullable=False)
    supply_type = Column(Enum('B2B', 'B2CL', 'B2CS', 'Export', 'Nil Rated', 'Exempt', name='gst_supply_type_enum'), nullable=False)
    party_gstin = Column(String(15), nullable=True)
    invoice_number = Column(String(30), nullable=False)
    invoice_date = Column(Date, nullable=False)
    place_of_supply = Column(String(50), nullable=False)
    taxable_value = Column(Numeric(18, 2), nullable=False)
    cgst_amount = Column(Numeric(18, 2), default=0.00)
    sgst_amount = Column(Numeric(18, 2), default=0.00)
    igst_amount = Column(Numeric(18, 2), default=0.00)
    cess_amount = Column(Numeric(18, 2), default=0.00)
    invoice_value = Column(Numeric(18, 2), nullable=False)
    
    period = relationship("GstReturnPeriod", back_populates="gstr1_lines")
    voucher = relationship("TrnVoucher")

class Gstr1HsnSummary(Base):
    __tablename__ = "gstr1_hsn_summary"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    hsn_summary_id = Column(BigInteger, primary_key=True, index=True)
    return_period_id = Column(BigInteger, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.gst_return_periods.return_period_id", ondelete="CASCADE"), nullable=False)
    hsn_code = Column(String(10), nullable=False)
    description = Column(String(150), nullable=True)
    uqc = Column(String(20), nullable=True)
    total_quantity = Column(Numeric(14, 3), nullable=False)
    taxable_value = Column(Numeric(18, 2), nullable=False)
    cgst_amount = Column(Numeric(18, 2), default=0.00)
    sgst_amount = Column(Numeric(18, 2), default=0.00)
    igst_amount = Column(Numeric(18, 2), default=0.00)
    cess_amount = Column(Numeric(18, 2), default=0.00)
    
    period = relationship("GstReturnPeriod", back_populates="gstr1_hsn_summaries")

class Gstr3bSummary(Base):
    __tablename__ = "gstr3b_summary"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    summary_id = Column(BigInteger, primary_key=True, index=True)
    return_period_id = Column(BigInteger, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.gst_return_periods.return_period_id", ondelete="CASCADE"), nullable=False, unique=True)
    
    outward_taxable_value = Column(Numeric(18, 2), default=0.00)
    outward_cgst = Column(Numeric(18, 2), default=0.00)
    outward_sgst = Column(Numeric(18, 2), default=0.00)
    outward_igst = Column(Numeric(18, 2), default=0.00)
    outward_cess = Column(Numeric(18, 2), default=0.00)
    
    itc_igst_available = Column(Numeric(18, 2), default=0.00)
    itc_cgst_available = Column(Numeric(18, 2), default=0.00)
    itc_sgst_available = Column(Numeric(18, 2), default=0.00)
    itc_cess_available = Column(Numeric(18, 2), default=0.00)
    itc_reversed = Column(Numeric(18, 2), default=0.00)
    
    net_igst_payable = Column(Numeric(18, 2), default=0.00)
    net_cgst_payable = Column(Numeric(18, 2), default=0.00)
    net_sgst_payable = Column(Numeric(18, 2), default=0.00)
    net_cess_payable = Column(Numeric(18, 2), default=0.00)
    
    tax_paid_via_cash = Column(Numeric(18, 2), default=0.00)
    tax_paid_via_itc = Column(Numeric(18, 2), default=0.00)
    interest_paid = Column(Numeric(18, 2), default=0.00)
    late_fee_paid = Column(Numeric(18, 2), default=0.00)
    
    period = relationship("GstReturnPeriod", back_populates="gstr3b_summary")

class ItcEntry(Base):
    __tablename__ = "itc_entries"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    itc_entry_id = Column(BigInteger, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    voucher_id = Column(BigInteger, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.vouchers.voucher_id"), nullable=False)
    supplier_gstin = Column(String(15), nullable=True)
    invoice_number = Column(String(30), nullable=False)
    invoice_date = Column(Date, nullable=False)
    taxable_value = Column(Numeric(18, 2), nullable=False)
    cgst_amount = Column(Numeric(18, 2), default=0.00)
    sgst_amount = Column(Numeric(18, 2), default=0.00)
    igst_amount = Column(Numeric(18, 2), default=0.00)
    cess_amount = Column(Numeric(18, 2), default=0.00)
    eligibility = Column(Enum('Eligible', 'Ineligible', 'Partially Eligible', name='itc_eligibility_enum'), default='Eligible')
    claimed_return_period_id = Column(BigInteger, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.gst_return_periods.return_period_id", ondelete="SET NULL"), nullable=True)
    
    company = relationship("Company")
    voucher = relationship("TrnVoucher")
    claimed_period = relationship("GstReturnPeriod")

class Gstr2bEntry(Base):
    """GSTR-2B Auto-drafted ITC statement — purchase reconciliation entries"""
    __tablename__ = "gstr2b_entries"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    entry_id = Column(BigInteger, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    return_period_id = Column(BigInteger, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.gst_return_periods.return_period_id", ondelete="SET NULL"), nullable=True)
    supplier_gstin = Column(String(15), nullable=False)
    supplier_name = Column(String(150), nullable=True)
    invoice_number = Column(String(30), nullable=False)
    invoice_date = Column(Date, nullable=False)
    invoice_type = Column(Enum('Regular', 'SEZ', 'Reverse Charge', 'Deemed Export', name='gstr2b_inv_type_enum'), default='Regular')
    taxable_value = Column(Numeric(18, 2), nullable=False)
    cgst_amount = Column(Numeric(18, 2), default=0.00)
    sgst_amount = Column(Numeric(18, 2), default=0.00)
    igst_amount = Column(Numeric(18, 2), default=0.00)
    cess_amount = Column(Numeric(18, 2), default=0.00)
    itc_availability = Column(Enum('Available', 'Not Available', 'Pending', name='gstr2b_itc_avail_enum'), default='Pending')
    match_status = Column(Enum('Matched', 'Unmatched', 'Mismatch', name='gstr2b_match_enum'), default='Unmatched')
    matched_voucher_id = Column(BigInteger, nullable=True)
    
    company = relationship("Company")
    period = relationship("GstReturnPeriod")

class Gstr9AnnualReturn(Base):
    """GSTR-9 Annual Return summary — year-end filing"""
    __tablename__ = "gstr9_annual_returns"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    annual_return_id = Column(BigInteger, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    financial_year = Column(String(9), nullable=False)  # e.g. '2025-2026'
    status = Column(Enum('Draft', 'Filed', name='gstr9_status_enum'), default='Draft')
    
    # Part II — Outward Supplies
    outward_taxable_supplies = Column(Numeric(18, 2), default=0.00)
    outward_tax_amount = Column(Numeric(18, 2), default=0.00)
    zero_rated_supplies = Column(Numeric(18, 2), default=0.00)
    nil_rated_supplies = Column(Numeric(18, 2), default=0.00)
    
    # Part III — Inward Supplies (ITC)
    inward_taxable_supplies = Column(Numeric(18, 2), default=0.00)
    inward_tax_amount = Column(Numeric(18, 2), default=0.00)
    itc_claimed = Column(Numeric(18, 2), default=0.00)
    itc_reversed = Column(Numeric(18, 2), default=0.00)
    
    # Part IV — Tax Paid
    total_tax_payable = Column(Numeric(18, 2), default=0.00)
    tax_paid_via_cash = Column(Numeric(18, 2), default=0.00)
    tax_paid_via_itc = Column(Numeric(18, 2), default=0.00)
    interest_paid = Column(Numeric(18, 2), default=0.00)
    late_fee_paid = Column(Numeric(18, 2), default=0.00)
    
    filed_date = Column(Date, nullable=True)
    arn = Column(String(30), nullable=True)
    filed_by = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id"), nullable=True)
    
    company = relationship("Company")
    user = relationship("User")

class ManualPurchase(Base):
    """User-entered manual purchases (Amazon, Flipkart, Offline, etc) for ITC calculation"""
    __tablename__ = "manual_purchases"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    purchase_id = Column(BigInteger, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    source = Column(String(100), nullable=False)
    invoice_number = Column(String(50), nullable=True)
    invoice_date = Column(Date, nullable=False)
    product_description = Column(String(200), nullable=False)
    taxable_value = Column(Numeric(18, 2), nullable=False, default=0.00)
    cgst_amount = Column(Numeric(18, 2), nullable=False, default=0.00)
    sgst_amount = Column(Numeric(18, 2), nullable=False, default=0.00)
    igst_amount = Column(Numeric(18, 2), nullable=False, default=0.00)
    claimed_return_period_id = Column(BigInteger, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.gst_return_periods.return_period_id", ondelete="SET NULL"), nullable=True)
    
    company = relationship("Company")
    claimed_period = relationship("GstReturnPeriod")

class ShopPayment(Base):
    __tablename__ = "shop_payments"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id", ondelete="CASCADE"), nullable=False)
    ledger_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.ledgers.ledger_id"), nullable=False)
    amount = Column(Numeric(18, 2), nullable=False)
    payment_mode = Column(String(64), nullable=False)  # Cash, Cheque, Online, etc.
    cheque_date = Column(Date, nullable=True, index=True)
    comments = Column(String(1024), nullable=True)
    photo_url = Column(Text, nullable=True)
    status = Column(String(32), default="pending")  # pending, success, cancelled
    created_at = Column(DateTime, server_default=func.now(), index=True)

    user = relationship("User")
    ledger = relationship("MstLedger")

class BillOfMaterials(Base):
    __tablename__ = "bill_of_materials"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    bom_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    stock_item_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.stock_items.stock_item_id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    qty_to_produce = Column(Numeric(14, 3), default=1.000)
    created_at = Column(DateTime, server_default=func.now())
    
    stock_item = relationship("MstStockItem")
    bom_items = relationship("BomItem", back_populates="bom", cascade="all, delete-orphan")

class BomItem(Base):
    __tablename__ = "bom_items"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    bom_item_id = Column(Integer, primary_key=True, index=True)
    bom_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.bill_of_materials.bom_id", ondelete="CASCADE"), nullable=False)
    stock_item_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.stock_items.stock_item_id"), nullable=False)
    qty_needed = Column(Numeric(14, 3), nullable=False)
    
    bom = relationship("BillOfMaterials", back_populates="bom_items")
    stock_item = relationship("MstStockItem")

class SerialNumber(Base):
    __tablename__ = "serial_numbers"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    serial_id = Column(BigInteger, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    stock_item_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.stock_items.stock_item_id"), nullable=False)
    serial_number = Column(String(80), nullable=False)
    godown_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.godowns.godown_id", ondelete="SET NULL"), nullable=True)
    status = Column(Enum('Available', 'Sold', 'Returned', 'Damaged', 'In Transit', name='serial_status_enum'), default='Available')
    purchase_voucher_id = Column(BigInteger, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.vouchers.voucher_id", ondelete="SET NULL"), nullable=True)
    sale_voucher_id = Column(BigInteger, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.vouchers.voucher_id", ondelete="SET NULL"), nullable=True)
    warranty_expiry = Column(Date, nullable=True)