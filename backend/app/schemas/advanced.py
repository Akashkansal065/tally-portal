from pydantic import BaseModel
from typing import Optional, List
from decimal import Decimal
from datetime import date, datetime

class EmployeeCreate(BaseModel):
    employee_code: str
    name: str
    designation: Optional[str] = None
    department: Optional[str] = None
    linked_user_id: Optional[int] = None
    date_of_joining: str  # YYYY-MM-DD
    pan: Optional[str] = None
    uan: Optional[str] = None
    pf_number: Optional[str] = None
    esi_number: Optional[str] = None
    bank_account_no: Optional[str] = None
    bank_ifsc: Optional[str] = None
    payment_ledger_id: int

class EmployeeResponse(EmployeeCreate):
    employee_id: int
    company_id: int
    is_active: bool
    date_of_joining: date
    
    class Config:
        from_attributes = True

class SalaryComponentCreate(BaseModel):
    name: str
    component_type: str  # 'Earning' or 'Deduction'
    calculation_type: str = "Fixed"  # 'Fixed', 'Percent of Basic', 'Formula'
    percent_of_basic: Optional[Decimal] = None
    is_statutory: bool = False
    linked_ledger_id: int

class SalaryComponentResponse(SalaryComponentCreate):
    component_id: int
    company_id: int
    
    class Config:
        from_attributes = True

class SalaryStructureComponentCreate(BaseModel):
    component_id: int
    amount: Decimal

class SalaryStructureComponentResponse(SalaryStructureComponentCreate):
    structure_component_id: int
    
    class Config:
        from_attributes = True

class SalaryStructureCreate(BaseModel):
    employee_id: int
    effective_from: str  # YYYY-MM-DD
    ctc_annual: Decimal
    components: List[SalaryStructureComponentCreate]

class SalaryStructureResponse(BaseModel):
    structure_id: int
    employee_id: int
    effective_from: date
    effective_to: Optional[date] = None
    ctc_annual: Decimal
    components: List[SalaryStructureComponentResponse]
    
    class Config:
        from_attributes = True

class PayrollPeriodCreate(BaseModel):
    period_month: int
    period_year: int

class PayrollPeriodResponse(PayrollPeriodCreate):
    period_id: int
    company_id: int
    status: str
    processed_at: Optional[datetime] = None
    processed_by: Optional[int] = None
    
    class Config:
        from_attributes = True

class PayslipComponentResponse(BaseModel):
    component_id: int
    amount: Decimal
    
    class Config:
        from_attributes = True

class PayslipResponse(BaseModel):
    payslip_id: int
    period_id: int
    employee_id: int
    days_present: Decimal
    days_in_period: int
    gross_earnings: Decimal
    total_deductions: Decimal
    net_pay: Decimal
    voucher_id: Optional[int] = None
    payment_voucher_id: Optional[int] = None
    generated_at: datetime
    components: List[PayslipComponentResponse]
    
    class Config:
        from_attributes = True

class PosPaymentCreate(BaseModel):
    voucher_id: int
    cash_amount: Decimal = Decimal("0.00")
    card_amount: Decimal = Decimal("0.00")
    upi_amount: Decimal = Decimal("0.00")
    points_redeemed: Decimal = Decimal("0.00")

class PosPaymentResponse(PosPaymentCreate):
    pos_payment_id: int
    
    class Config:
        from_attributes = True

class EinvoiceMetadataCreate(BaseModel):
    voucher_id: int
    irn: Optional[str] = None
    ack_no: Optional[str] = None
    ack_date: Optional[str] = None  # YYYY-MM-DD HH:MM:SS
    eway_bill_no: Optional[str] = None
    eway_bill_date: Optional[str] = None
    raw_response: Optional[str] = None

class EinvoiceMetadataResponse(BaseModel):
    metadata_id: int
    voucher_id: int
    irn: Optional[str] = None
    ack_no: Optional[str] = None
    ack_date: Optional[datetime] = None
    eway_bill_no: Optional[str] = None
    eway_bill_date: Optional[datetime] = None
    raw_response: Optional[str] = None
    
    class Config:
        from_attributes = True
