from pydantic import BaseModel
from typing import Optional, List
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
