from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import date, datetime

class BillAllocationCreate(BaseModel):
    voucher_entry_id: int
    bill_id: Optional[int] = None
    allocation_type: str  # 'Against Ref', 'Advance', 'On Account', 'New Ref'
    amount: Decimal

class BillAllocationResponse(BaseModel):
    allocation_id: int
    voucher_entry_id: int
    bill_id: Optional[int] = None
    allocation_type: str
    amount: Decimal
    created_at: datetime
    
    class Config:
        from_attributes = True

class BillResponse(BaseModel):
    bill_id: int
    company_id: int
    party_ledger_id: int
    voucher_id: int
    bill_reference: str
    bill_date: date
    due_date: Optional[date] = None
    bill_amount: Decimal
    settled_amount: Decimal
    status: str
    
    class Config:
        from_attributes = True

class OutstandingBill(BaseModel):
    bill_id: int
    party_name: str
    bill_reference: str
    bill_date: date
    due_date: Optional[date] = None
    bill_amount: Decimal
    settled_amount: Decimal
    outstanding_amount: Decimal
    overdue_days: int

class AgingBucket(BaseModel):
    range_label: str  # e.g., '0-30 Days', '31-60 Days', etc.
    total_outstanding: Decimal
    bills: List[OutstandingBill]

class CustomerAgingBill(BaseModel):
    bill_id: int
    voucher_id: Optional[int] = None
    bill_reference: str
    bill_date: str
    due_date: Optional[str] = None
    bill_amount: float
    settled_amount: float
    outstanding_amount: float
    days_overdue: int
    status: str

class CustomerAgingSummary(BaseModel):
    party_ledger_id: int
    party_name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    credit_period_days: int
    total_outstanding: float
    current_not_due: float
    days_1_30: float
    days_31_60: float
    days_61_90: float
    days_90_plus: float
    open_bills_count: int
    overdue_bills_count: int
    dunning_level: str  # 'CURRENT', 'GENTLE', 'FORMAL', 'URGENT'
    bills: List[CustomerAgingBill]

class AgingKPISummary(BaseModel):
    total_receivables: float
    total_overdue: float
    total_current: float
    bucket_0_30: float
    bucket_31_60: float
    bucket_61_90: float
    bucket_90_plus: float
    total_debtors_count: int
    overdue_debtors_count: int

class AgingDashboardResponse(BaseModel):
    kpis: AgingKPISummary
    customers: List[CustomerAgingSummary]
    upi_vpa: str
    merchant_name: str

class ReminderMessageRequest(BaseModel):
    party_ledger_id: int
    dunning_level: Optional[str] = "auto"  # "auto", "gentle", "formal", "urgent"
    aging_bucket: Optional[str] = "ALL"    # "ALL", "OVERDUE", "0-30", "31-60", "61-90", "90+"
    channel: Optional[str] = "whatsapp"   # "whatsapp", "email", "sms"

class ReminderMessageResponse(BaseModel):
    party_ledger_id: int
    party_name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    total_due: float
    overdue_bills_count: int
    dunning_level: str
    message_text: str
    whatsapp_url: Optional[str] = None
    upi_uri: str
    upi_vpa: str

class BulkReminderRequest(BaseModel):
    party_ledger_ids: Optional[List[int]] = None
    aging_bucket: Optional[str] = None  # "ALL_OVERDUE", "1-30", "31-60", "61-90", "90_PLUS"
    channel: str = "whatsapp"

class BulkReminderResponse(BaseModel):
    total_targeted: int
    reminders: List[ReminderMessageResponse]
