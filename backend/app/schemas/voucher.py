from pydantic import BaseModel
from typing import Optional, List
from decimal import Decimal
from datetime import date, datetime

class VoucherEntryCreate(BaseModel):
    ledger_id: int
    cost_center_id: Optional[int] = None
    debit_amount: Decimal = Decimal("0.00")
    credit_amount: Decimal = Decimal("0.00")
    entry_narration: Optional[str] = None
    
    # Forex fields
    forex_currency_id: Optional[int] = None
    forex_amount: Optional[Decimal] = None
    exchange_rate_used: Optional[Decimal] = None

class VoucherEntryResponse(VoucherEntryCreate):
    entry_id: int
    voucher_id: int
    
    class Config:
        from_attributes = True

class VoucherCreate(BaseModel):
    voucher_type_id: int
    voucher_date: str  # YYYY-MM-DD
    reference_number: Optional[str] = None
    narration: Optional[str] = None
    is_optional: bool = False
    entries: List[VoucherEntryCreate]

class VoucherResponse(BaseModel):
    voucher_id: int
    company_id: int
    voucher_type_id: int
    voucher_number: str
    voucher_date: date
    reference_number: Optional[str] = None
    narration: Optional[str] = None
    total_amount: Decimal
    is_cancelled: bool
    is_optional: bool
    created_by: int
    created_at: datetime
    tally_guid: Optional[str] = None
    tally_alter_id: Optional[int] = None
    entries: List[VoucherEntryResponse]
    
    class Config:
        from_attributes = True

class ApprovalRuleCreate(BaseModel):
    module_id: int
    voucher_type_id: Optional[int] = None
    condition_field: str = "total_amount"
    condition_operator: str = ">"
    condition_value: Decimal
    approver_role_id: int

class ApprovalRuleResponse(ApprovalRuleCreate):
    rule_id: int
    company_id: int
    is_active: bool
    
    class Config:
        from_attributes = True

class ApprovalRequestResponse(BaseModel):
    request_id: int
    rule_id: int
    voucher_id: int
    requested_by: int
    status: str
    acted_by: Optional[int] = None
    comments: Optional[str] = None
    requested_at: datetime
    acted_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
