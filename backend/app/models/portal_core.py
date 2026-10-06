from sqlalchemy import Column, Integer, BigInteger, String, Date, Boolean, DateTime, ForeignKey, Enum, Numeric, Text, TEXT, JSON, Float, Double, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.core.config import settings
from app.models.tally_core import *

class SyncQueue(Base):
    __tablename__ = "sync_queue"
    __table_args__ = (
        Index("ix_sync_queue_company_processed", "company_id", "is_processed"),
        {"schema": settings.PORTAL_DATABASE_NAME},
    )
    
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
    __table_args__ = (
        Index("ix_sync_traffic_company_status", "company_id", "status"),
        Index("ix_sync_traffic_company_created", "company_id", "created_at"),
        {"schema": settings.PORTAL_DATABASE_NAME},
    )

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
    __table_args__ = (
        Index("ix_deleted_audit_company_status", "company_id", "tally_sync_status"),
        {"schema": settings.PORTAL_DATABASE_NAME},
    )

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
    environment = Column(String(20), default='mock')  # mock (demo), manual (typed in), live (from the GSP)
    signed_qr = Column(TEXT, nullable=True)  # the e-invoice QR content (signed JWT) from the IRP
    irn_status = Column(String(12), nullable=True)  # active, cancelled
    irn_cancelled_at = Column(DateTime, nullable=True)
    ewb_valid_till = Column(DateTime, nullable=True)
    ewb_status = Column(String(12), nullable=True)  # active, cancelled
    ewb_cancelled_at = Column(DateTime, nullable=True)



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
    # Maximum simultaneously signed-in devices for users of this role; NULL = unlimited
    max_active_devices = Column(Integer, nullable=True)
    
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
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan", foreign_keys="[UserSession.user_id]")
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
    # Indexes are also created on existing databases at startup (ensure_table_indexes), since the
    # schema sync only adds columns
    __table_args__ = (
        Index("ix_user_sessions_token", "token_hash"),
        Index("ix_user_sessions_active", "user_id", "revoked_at", "expires_at"),
        Index("ix_user_sessions_device", "user_id", "device_id"),
        {"schema": settings.PORTAL_DATABASE_NAME},
    )
    
    session_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String(255), nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    # Device identity and description (see app/core/sessions.py); NULL on sessions created before tracking
    device_id = Column(String(64), nullable=True)
    client_type = Column(String(20), nullable=True)   # web | android | ios | sync-agent | api
    device_type = Column(String(20), nullable=True)   # mobile | tablet | desktop
    device_name = Column(String(120), nullable=True)
    os_name = Column(String(60), nullable=True)
    browser_name = Column(String(60), nullable=True)
    app_version = Column(String(30), nullable=True)
    # Timestamps written by the app are UTC; legacy created_at values came from MySQL NOW() in IST
    created_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=False)
    last_active_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    revoked_by_user_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id", ondelete="SET NULL"), nullable=True)
    revoke_reason = Column(String(30), nullable=True)
    
    user = relationship("User", back_populates="sessions", foreign_keys=[user_id])


class BlockedDevice(Base):
    """A device that may no longer sign in as a given user (device ids come from the client; see sessions.py)."""
    __tablename__ = "blocked_devices"
    __table_args__ = (
        UniqueConstraint("user_id", "device_id", name="uq_blocked_devices_user_device"),
        {"schema": settings.PORTAL_DATABASE_NAME},
    )

    blocked_device_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id", ondelete="CASCADE"), nullable=False)
    device_id = Column(String(64), nullable=False)
    device_name = Column(String(120), nullable=True)
    client_type = Column(String(20), nullable=True)
    device_type = Column(String(20), nullable=True)
    reason = Column(String(255), nullable=True)
    blocked_by_user_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False)

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
    # e-Way bill portal API user (ewaybillgst.gov.in → Registration → For API, through the GSP)
    eway_username = Column(String(100), nullable=True)
    eway_password = Column(String(255), nullable=True)
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
    # Bank/cash ledger debited when a gateway payment is auto-posted as a Receipt
    settlement_ledger_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.ledgers.ledger_id"), nullable=True)
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

    user = relationship("User", foreign_keys=[user_id])

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
    locked_at = Column(DateTime, nullable=True)
    locked_by = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id"), nullable=True)
    
    company = relationship("Company")
    user = relationship("User", foreign_keys=[filed_by])
    locked_user = relationship("User", foreign_keys=[locked_by])
    gstr1_lines = relationship("Gstr1LineItem", back_populates="period", cascade="all, delete-orphan")
    gstr1_hsn_summaries = relationship("Gstr1HsnSummary", back_populates="period", cascade="all, delete-orphan")
    gstr3b_summary = relationship("Gstr3bSummary", uselist=False, back_populates="period", cascade="all, delete-orphan")


class GstComplianceException(Base):
    """Persisted validation or provider issue requiring tax-team action."""

    __tablename__ = "gst_compliance_exceptions"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}

    exception_id = Column(BigInteger, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    return_period_id = Column(BigInteger, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.gst_return_periods.return_period_id", ondelete="CASCADE"), nullable=True, index=True)
    code = Column(String(80), nullable=False, index=True)
    field = Column(String(120), nullable=True)
    message = Column(String(500), nullable=False)
    severity = Column(String(20), nullable=False, default="error")
    status = Column(String(20), nullable=False, default="open", index=True)
    resolution_note = Column(String(1000), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id"), nullable=True)


class GstFilingSnapshot(Base):
    """Append-only payload and response evidence for a GST filing attempt."""

    __tablename__ = "gst_filing_snapshots"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}

    snapshot_id = Column(BigInteger, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    return_period_id = Column(BigInteger, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.gst_return_periods.return_period_id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String(50), nullable=False, default="internal")
    payload_hash = Column(String(64), nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    response = Column(JSON, nullable=True)
    status = Column(String(30), nullable=False, default="generated")
    acknowledgement_number = Column(String(64), nullable=True)
    created_by = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), index=True)


class GstProviderAttempt(Base):
    """Append-only audit record for each provider submission or retry."""

    __tablename__ = "gst_provider_attempts"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}

    attempt_id = Column(BigInteger, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    return_period_id = Column(BigInteger, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.gst_return_periods.return_period_id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String(50), nullable=False)
    idempotency_key = Column(String(160), nullable=False, index=True)
    status = Column(String(30), nullable=False)
    correlation_id = Column(String(120), nullable=True)
    response = Column(JSON, nullable=True)
    error_message = Column(String(500), nullable=True)
    created_by = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), index=True)

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
    match_method = Column(String(30), nullable=True)
    match_confidence = Column(Numeric(5, 2), nullable=True)
    match_reason = Column(String(255), nullable=True)
    
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
    review_comment = Column(String(1024), nullable=True)
    photo_url = Column(Text, nullable=True)
    status = Column(String(32), default="pending")  # pending, success, cancelled
    reviewed_by_user_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)

    user = relationship("User", foreign_keys=[user_id])
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_user_id])
    ledger = relationship("MstLedger", foreign_keys=[ledger_id])

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


class CustomerProfile(Base):
    __tablename__ = "customer_profiles"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    ledger_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.ledgers.ledger_id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Standalone customer details (used if ledger_id is null or as custom override)
    custom_name = Column(String(255), nullable=True)
    contact_person = Column(String(150), nullable=True)
    phone = Column(String(50), nullable=True)
    whatsapp_number = Column(String(50), nullable=True)
    alternate_phone = Column(String(50), nullable=True)
    email = Column(String(150), nullable=True)
    
    # Established Master Coordinates
    latitude = Column(Double, nullable=True)
    longitude = Column(Double, nullable=True)
    location_verified = Column(Boolean, default=False)
    location_verified_at = Column(DateTime, nullable=True)
    
    # Categorization & Beats
    locality = Column(String(200), nullable=True, index=True)
    city = Column(String(100), nullable=True, index=True)
    state = Column(String(100), nullable=True)
    pincode = Column(String(20), nullable=True)
    landmark = Column(String(200), nullable=True)
    address = Column(Text, nullable=True)
    route_name = Column(String(100), nullable=True, index=True)
    shop_type = Column(String(50), nullable=True)
    weekly_off = Column(String(50), nullable=True)
    gstin = Column(String(15), nullable=True)
    pan_number = Column(String(30), nullable=True)
    payment_terms = Column(String(100), nullable=True)
    tags = Column(String(500), nullable=True)
    priority = Column(String(20), default="medium")
    visit_frequency = Column(String(20), default="weekly")
    
    # Media & Notes
    customer_photo_url = Column(Text, nullable=True)
    shop_photo_url = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    
    # Tracking
    last_visit_at = Column(DateTime, nullable=True)
    total_visits = Column(Integer, default=0)
    created_by = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    company = relationship("Company", foreign_keys=[company_id])
    user = relationship("User", foreign_keys=[created_by])
    ledger = relationship("MstLedger", foreign_keys=[ledger_id])
    location_logs = relationship("CustomerLocationLog", back_populates="customer_profile", cascade="all, delete-orphan")
    photos = relationship("CustomerPhoto", back_populates="customer_profile", cascade="all, delete-orphan")
    owners = relationship("CustomerOwner", back_populates="customer_profile", cascade="all, delete-orphan", order_by="CustomerOwner.is_primary.desc(), CustomerOwner.id.asc()")


class CustomerLocationLog(Base):
    __tablename__ = "customer_location_logs"
    __table_args__ = (
        Index("ix_customer_location_logs_latest", "company_id", "customer_profile_id", "created_at"),
        {"schema": settings.PORTAL_DATABASE_NAME},
    )

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    customer_profile_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.customer_profiles.id", ondelete="CASCADE"), nullable=True, index=True)
    ledger_id = Column(Integer, nullable=True, index=True)
    user_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id", ondelete="CASCADE"), nullable=False)
    
    # Captured GPS coordinates
    latitude = Column(Double, nullable=False)
    longitude = Column(Double, nullable=False)
    accuracy_meters = Column(Float, nullable=True)
    
    # Distance comparison against shop's established location
    distance_from_base_meters = Column(Float, nullable=True)
    verification_status = Column(String(50), default="UNVERIFIED")
    # Status values: "ESTABLISHED_BASE", "VERIFIED_ON_SITE", "NEARBY", "MISMATCH_FAR", "NO_BASE_COORDINATE"
    
    source = Column(String(50), default="check_in")
    # "check_in", "manual_tag", "admin_override"
    
    visit_id = Column(Integer, nullable=True)
    notes = Column(String(500), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    company = relationship("Company", foreign_keys=[company_id])
    user = relationship("User", foreign_keys=[user_id])
    customer_profile = relationship("CustomerProfile", back_populates="location_logs", foreign_keys=[customer_profile_id])


class CustomerPhoto(Base):
    __tablename__ = "customer_photos"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    customer_profile_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.customer_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    ledger_id = Column(Integer, nullable=True, index=True)

    photo_type = Column(String(50), default="shop_front")
    # "customer_owner", "shop_front", "shop_inside", "shop_board", "visiting_card", "qr_code", "other"

    imagekit_file_id = Column(String(255), nullable=True)
    imagekit_url = Column(Text, nullable=False)
    imagekit_thumbnail_url = Column(Text, nullable=True)
    imagekit_file_path = Column(String(500), nullable=True)

    caption = Column(String(255), nullable=True)
    latitude = Column(Double, nullable=True)
    longitude = Column(Double, nullable=True)
    is_primary = Column(Boolean, default=False)

    uploaded_by = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    company = relationship("Company", foreign_keys=[company_id])
    user = relationship("User", foreign_keys=[uploaded_by])
    customer_profile = relationship("CustomerProfile", back_populates="photos", foreign_keys=[customer_profile_id])


class CustomerOwner(Base):
    __tablename__ = "customer_owners"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    customer_profile_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.customer_profiles.id", ondelete="CASCADE"), nullable=False, index=True)

    name = Column(String(150), nullable=False)
    designation = Column(String(100), default="Owner / Partner")  # e.g., "Primary Owner", "Partner", "Co-Owner", "Managing Partner", "Key Contact / Manager"
    phone = Column(String(50), nullable=True)
    whatsapp_number = Column(String(50), nullable=True)
    email = Column(String(150), nullable=True)
    photo_url = Column(Text, nullable=True)
    imagekit_file_id = Column(String(255), nullable=True)
    is_primary = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    company = relationship("Company", foreign_keys=[company_id])
    customer_profile = relationship("CustomerProfile", back_populates="owners", foreign_keys=[customer_profile_id])


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_unread", "user_id", "company_id", "is_read"),
        {"schema": settings.PORTAL_DATABASE_NAME},
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String(50), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    reference_id = Column(String(100), nullable=True)
    reference_type = Column(String(50), nullable=True)
    # Where tapping the notification goes (app path with query), built once when it's created
    link = Column(String(500), nullable=True)
    # Preference bucket (approvals, attendance, orders, ...); see app/services/notifications.py
    category = Column(String(30), nullable=True, index=True)
    # Similar unread notifications (e.g. today's clock-ins) update one row instead of adding many
    group_key = Column(String(120), nullable=True)
    group_count = Column(Integer, default=1, nullable=False)
    is_read = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)

    # Relationships
    company = relationship("Company", foreign_keys=[company_id])
    user = relationship("User", foreign_keys=[user_id])


class AppSetting(Base):
    """Business-wide settings that apply across every company, e.g. the monthly sales target. One row per key;
    the value is JSON text. Defaults live in app/services/app_settings.py."""
    __tablename__ = "app_settings"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)
    updated_by_user_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class CustomerCreditTerm(Base):
    """Credit days agreed with one customer (a Tally debtor ledger). Tally doesn't hold these for this business,
    so they're kept here; customers without a row use the default credit days setting."""
    __tablename__ = "customer_credit_terms"
    __table_args__ = (
        UniqueConstraint("company_id", "ledger_id", name="uq_customer_credit_terms_ledger"),
        {"schema": settings.PORTAL_DATABASE_NAME},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    ledger_id = Column(Integer, nullable=False)
    credit_days = Column(Integer, nullable=False)
    updated_by_user_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class PincodeCity(Base):
    """City for a pincode, used for customers whose MyTally profile has no city. Proposed names come from
    app/services/cities.py; a row here is an admin's correction (or confirmation) and wins."""
    __tablename__ = "pincode_cities"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}

    pincode = Column(String(6), primary_key=True)
    city = Column(String(100), nullable=False)
    updated_by_user_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ReportSnapshot(Base):
    """One saved figure set per company, day and kind (e.g. receivables, dead_stock), so trends can be drawn for
    numbers Tally only knows as of today. Written at most once a day per kind."""
    __tablename__ = "report_snapshots"
    __table_args__ = (
        UniqueConstraint("company_id", "kind", "day", name="uq_report_snapshots_company_kind_day"),
        {"schema": settings.PORTAL_DATABASE_NAME},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(String(30), nullable=False)
    day = Column(Date, nullable=False)
    data = Column(JSON, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class CompanyIntegration(Base):
    """On/off switch for a feature that needs another provider's API keys or a paid subscription (e-invoice,
    WhatsApp API, ...), per company. No row means off. The list of switches lives in app/services/integrations.py."""
    __tablename__ = "company_integrations"
    __table_args__ = (
        UniqueConstraint("company_id", "key", name="uq_company_integrations_company_key"),
        {"schema": settings.PORTAL_DATABASE_NAME},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    key = Column(String(40), nullable=False)
    enabled = Column(Boolean, nullable=False, default=False)
    updated_by_user_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class CompanyBranding(Base):
    """What a company's invoices and statements look like beyond its profile: logo and signature images (PNG/JPEG
    data URLs, resized in the browser), bank details, declaration text and whether to print a UPI QR code. One row
    per company; no row means the defaults in app/routers/branding.py."""
    __tablename__ = "company_branding"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}

    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), primary_key=True)
    logo = Column(Text(length=1_000_000), nullable=True)  # MEDIUMTEXT on MySQL
    signature = Column(Text(length=1_000_000), nullable=True)
    bank_account_name = Column(String(150), nullable=True)
    bank_name = Column(String(150), nullable=True)
    bank_account_no = Column(String(40), nullable=True)
    bank_ifsc = Column(String(20), nullable=True)
    bank_branch = Column(String(150), nullable=True)
    declaration = Column(Text, nullable=True)
    show_upi_qr = Column(Boolean, nullable=False, default=True)
    updated_by_user_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ReminderSchedule(Base):
    """Automatic payment reminders for one customer (a Tally debtor ledger): which channels, how often and at
    what time (IST). One active schedule per customer; the worker in app/services/reminders.py sends them and
    stops the schedule once the customer has paid."""
    __tablename__ = "reminder_schedules"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    ledger_id = Column(Integer, nullable=False, index=True)
    channels = Column(JSON, nullable=False)  # ["email", "whatsapp"]
    frequency = Column(String(10), nullable=False)  # once, daily, weekly, monthly
    send_time = Column(String(5), nullable=False)  # "10:00", IST
    weekday = Column(Integer, nullable=True)  # weekly: 0 = Monday
    month_day = Column(Integer, nullable=True)  # monthly: 1-28
    only_when_overdue = Column(Boolean, nullable=False, default=True)
    next_run_at = Column(DateTime, nullable=True, index=True)  # IST
    active = Column(Boolean, nullable=False, default=True, index=True)
    stop_reason = Column(String(20), nullable=True)  # paid, stopped, no_contact
    last_run_at = Column(DateTime, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ReminderLog(Base):
    """One attempt to send a payment reminder on one channel, with what it said and what happened."""
    __tablename__ = "reminder_log"
    __table_args__ = (
        Index("ix_reminder_log_company_created", "company_id", "created_at"),
        {"schema": settings.PORTAL_DATABASE_NAME},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False)
    ledger_id = Column(Integer, nullable=False, index=True)
    schedule_id = Column(Integer, nullable=True)
    channel = Column(String(10), nullable=False)  # email, whatsapp
    recipient = Column(String(150), nullable=True)
    outstanding = Column(Numeric(15, 2), nullable=True)
    overdue = Column(Numeric(15, 2), nullable=True)
    status = Column(String(12), nullable=False)  # sent, delivered, read, failed, skipped, dry_run
    detail = Column(String(500), nullable=True)  # why it was skipped or failed
    provider_message_id = Column(String(128), nullable=True, index=True)
    sent_by_user_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False)  # IST
    updated_at = Column(DateTime, nullable=True)


class NotificationPreference(Base):
    """How one user wants one category of notifications delivered: all (in-app and push), in_app, or off."""
    __tablename__ = "notification_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", "category", name="uq_notification_pref_user_category"),
        {"schema": settings.PORTAL_DATABASE_NAME},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(30), nullable=False)
    delivery = Column(String(10), nullable=False, default="all")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    endpoint = Column(Text, nullable=False)
    p256dh = Column(String(255), nullable=False)
    auth = Column(String(255), nullable=False)
    user_agent = Column(String(255), nullable=True)
    # X-Device-Id of the browser that subscribed; its subscription is removed when that device signs out
    device_id = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)

    # Relationships
    company = relationship("Company", foreign_keys=[company_id])
    user = relationship("User", foreign_keys=[user_id])


class DevicePushToken(Base):
    """Firebase Cloud Messaging token of an installed Android (or iOS) app, for lock-screen notifications.
    One row per token: when another person signs in on the same phone the token moves to them."""
    __tablename__ = "device_push_tokens"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    token = Column(String(512), nullable=False, unique=True)
    platform = Column(String(20), nullable=False, default="android")
    device_id = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class BeatPlan(Base):
    __tablename__ = "beat_plans"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    plan_date = Column(Date, nullable=False, index=True)
    route_name = Column(String(100), nullable=False)
    locality = Column(String(200), nullable=True)
    notes = Column(Text, nullable=True)
    status = Column(String(32), default="assigned")  # assigned, in_progress, completed, cancelled
    created_by = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    company = relationship("Company", foreign_keys=[company_id])
    user = relationship("User", foreign_keys=[user_id])
    creator = relationship("User", foreign_keys=[created_by])
    stops = relationship("BeatPlanStop", back_populates="beat_plan", cascade="all, delete-orphan", order_by="BeatPlanStop.sequence_order.asc()")


class BeatPlanStop(Base):
    __tablename__ = "beat_plan_stops"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    beat_plan_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.beat_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_key = Column(String(100), nullable=False, index=True)
    customer_profile_id = Column(Integer, nullable=True)
    ledger_id = Column(Integer, nullable=True, index=True)
    shop_name = Column(String(255), nullable=False)
    locality = Column(String(200), nullable=True)
    address = Column(Text, nullable=True)
    latitude = Column(Double, nullable=True)
    longitude = Column(Double, nullable=True)
    sequence_order = Column(Integer, nullable=False, default=1)
    status = Column(String(32), default="pending")  # pending, visited, skipped
    visit_id = Column(Integer, nullable=True)
    visited_at = Column(DateTime, nullable=True)
    skip_reason = Column(String(255), nullable=True)
    notes = Column(String(500), nullable=True)

    # Relationships
    beat_plan = relationship("BeatPlan", back_populates="stops", foreign_keys=[beat_plan_id])


# ─── Bank Statement Reconciliation Models ────────────────────────────────────

class BankStatement(Base):
    __tablename__ = "bank_statements"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}

    statement_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    bank_ledger_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.ledgers.ledger_id"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_hash = Column(String(64), nullable=True, index=True)
    account_number = Column(String(64), nullable=True)
    statement_from = Column(Date, nullable=False)
    statement_to = Column(Date, nullable=False)
    opening_balance = Column(Numeric(18, 2), default=0.00)
    closing_balance = Column(Numeric(18, 2), default=0.00)
    total_transactions = Column(Integer, default=0)
    reconciled_transactions = Column(Integer, default=0)
    unmatched_transactions = Column(Integer, default=0)
    reviewed_transactions = Column(Integer, default=0)
    status = Column(String(32), default="imported")  # imported, in_progress, reconciled
    created_at = Column(DateTime, server_default=func.now())
    created_by_user_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id"), nullable=True)

    company = relationship("Company", foreign_keys=[company_id])
    bank_ledger = relationship("MstLedger", foreign_keys=[bank_ledger_id])
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    transactions = relationship("BankStatementTransaction", back_populates="statement", cascade="all, delete-orphan")


class BankStatementTransaction(Base):
    __tablename__ = "bank_statement_transactions"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}

    transaction_id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    statement_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.bank_statements.statement_id", ondelete="CASCADE"), nullable=False, index=True)
    transaction_date = Column(Date, nullable=False, index=True)
    value_date = Column(Date, nullable=True)
    description = Column(String(1024), nullable=False)
    reference_no = Column(String(128), nullable=True, index=True)  # UTR, Cheque No, Ref
    cheque_no = Column(String(64), nullable=True)
    transaction_type = Column(String(16), nullable=False)  # 'DEBIT' or 'CREDIT'
    amount = Column(Numeric(18, 2), nullable=False)
    running_balance = Column(Numeric(18, 2), nullable=True)
    matched_status = Column(String(32), default="unmatched")  # 'unmatched', 'suggested', 'matched'
    matched_voucher_id = Column(BigInteger, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.vouchers.voucher_id", ondelete="SET NULL"), nullable=True)
    matched_payment_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.shop_payments.id", ondelete="SET NULL"), nullable=True)
    matched_allocation_id = Column(BigInteger, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.bank_allocations.allocation_id", ondelete="SET NULL"), nullable=True)
    match_type = Column(String(64), nullable=True)  # 'exact_ref', 'exact_amount_date', 'fuzzy_narration', 'manual'
    matched_at = Column(DateTime, nullable=True)
    matched_by_user_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id"), nullable=True)
    match_notes = Column(String(512), nullable=True)

    # Admin Review Status fields for non-matching or external transactions
    review_status = Column(String(64), default="pending_review")  # 'pending_review', 'not_specific', 'bank_charges', 'interest', 'internal_transfer', 'other_account', 'under_investigation'
    review_notes = Column(String(512), nullable=True)
    reviewed_by_user_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    raw_data = Column(JSON, nullable=True)  # Full unparsed row data from XLSX/CSV
    row_hash = Column(String(64), nullable=True, index=True)

    statement = relationship("BankStatement", back_populates="transactions", foreign_keys=[statement_id])
    matched_voucher = relationship("TrnVoucher", foreign_keys=[matched_voucher_id])
    matched_payment = relationship("ShopPayment", foreign_keys=[matched_payment_id])
    matched_allocation = relationship("TrnBankAllocation", foreign_keys=[matched_allocation_id])
    matched_by = relationship("User", foreign_keys=[matched_by_user_id])
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_user_id])