from pydantic import BaseModel
from typing import Optional, List
from decimal import Decimal
from datetime import datetime

class AccountGroupBase(BaseModel):
    name: str
    parent_group_id: Optional[int] = None
    nature: str  # 'Asset', 'Liability', 'Income', 'Expense'
    affects_gross_profit: bool = False

class AccountGroupCreate(AccountGroupBase):
    pass

class AccountGroupResponse(AccountGroupBase):
    group_id: int
    company_id: int
    is_system_defined: bool
    
    class Config:
        from_attributes = True

class LedgerBase(BaseModel):
    name: str
    group_id: int
    opening_balance: Decimal = Decimal("0.00")
    opening_balance_type: str = "Dr"  # 'Dr' or 'Cr'
    currency_id: Optional[int] = None
    gstin: Optional[str] = None
    address: Optional[str] = None
    state: Optional[str] = None
    is_bank_account: bool = False
    bank_account_no: Optional[str] = None
    bank_ifsc: Optional[str] = None
    credit_limit: Optional[Decimal] = None
    credit_period_days: Optional[int] = None
    is_active: bool = True

class LedgerCreate(LedgerBase):
    pass

from pydantic import field_validator

class LedgerResponse(LedgerBase):
    ledger_id: int
    company_id: int
    tally_guid: Optional[str] = None
    tally_alter_id: Optional[int] = None
    created_at: datetime
    closing_balance: Optional[Decimal] = None
    group_name: Optional[str] = None
    mobile: Optional[str] = None
    email: Optional[str] = None
    is_customer: Optional[bool] = None
    is_supplier: Optional[bool] = None
    
    @field_validator('name')
    @classmethod
    def to_title_case(cls, v: str) -> str:
        return v.title() if v else v

    class Config:
        from_attributes = True

class CostCenterBase(BaseModel):
    name: str
    parent_id: Optional[int] = None

class CostCenterCreate(CostCenterBase):
    pass

class CostCenterResponse(CostCenterBase):
    cost_center_id: int
    company_id: int
    
    class Config:
        from_attributes = True
