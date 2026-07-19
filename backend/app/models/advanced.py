from sqlalchemy import Column, Integer, BigInteger, String, Date, Boolean, DateTime, ForeignKey, Enum, Numeric, TEXT
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.core.config import settings

# --- Payroll Module ---

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

class SalaryComponent(Base):
    __tablename__ = "salary_components"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    
    component_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(60), nullable=False)
    component_type = Column(Enum('Earning', 'Deduction', name='salary_component_type'), nullable=False)
    calculation_type = Column(Enum('Fixed', 'Percent of Basic', 'Formula', name='salary_calculation_type'), default='Fixed')
    percent_of_basic = Column(Numeric(5, 2), nullable=True)
    is_statutory = Column(Boolean, default=False)
    linked_ledger_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.ledgers.ledger_id"), nullable=False)
    
    linked_ledger = relationship("MstLedger")

class SalaryStructure(Base):
    __tablename__ = "salary_structures"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    
    structure_id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.employees.employee_id", ondelete="CASCADE"), nullable=False)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=True)
    ctc_annual = Column(Numeric(18, 2), nullable=False)
    
    components = relationship("SalaryStructureComponent", back_populates="structure", cascade="all, delete-orphan")

class SalaryStructureComponent(Base):
    __tablename__ = "salary_structure_components"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    
    structure_component_id = Column(BigInteger, primary_key=True, index=True)
    structure_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.salary_structures.structure_id", ondelete="CASCADE"), nullable=False)
    component_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.salary_components.component_id"), nullable=False)
    amount = Column(Numeric(18, 2), nullable=False)
    
    structure = relationship("SalaryStructure", back_populates="components")
    component = relationship("SalaryComponent")

class PayrollPeriod(Base):
    __tablename__ = "payroll_periods"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    
    period_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    period_month = Column(Integer, nullable=False)
    period_year = Column(Integer, nullable=False)
    status = Column(Enum('Draft', 'Processed', 'Paid', 'Locked', name='payroll_period_status'), default='Draft')
    processed_at = Column(DateTime, nullable=True)
    processed_by = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id"), nullable=True)

class Payslip(Base):
    __tablename__ = "payslips"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    
    payslip_id = Column(BigInteger, primary_key=True, index=True)
    period_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.payroll_periods.period_id", ondelete="CASCADE"), nullable=False)
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
    employee = relationship("Employee")
    voucher = relationship("TrnVoucher", foreign_keys=[voucher_id])
    payment_voucher = relationship("TrnVoucher", foreign_keys=[payment_voucher_id])
    components = relationship("PayslipComponent", back_populates="payslip", cascade="all, delete-orphan")

class PayslipComponent(Base):
    __tablename__ = "payslip_components"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    
    payslip_component_id = Column(BigInteger, primary_key=True, index=True)
    payslip_id = Column(BigInteger, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.payslips.payslip_id", ondelete="CASCADE"), nullable=False)
    component_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.salary_components.component_id"), nullable=False)
    amount = Column(Numeric(18, 2), nullable=False)
    
    payslip = relationship("Payslip", back_populates="components")
    component = relationship("SalaryComponent")

# --- POS Billing (POS payments split) ---

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

# --- E-Way & E-Invoicing metadata logging ---

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
    
    voucher = relationship("TrnVoucher")
