from pydantic import BaseModel
from typing import Optional, List
from decimal import Decimal
from datetime import datetime

from datetime import date
from enum import Enum

class AccountGroupNature(str, Enum):
    ASSET = 'Asset'
    LIABILITY = 'Liability'
    INCOME = 'Income'
    EXPENSE = 'Expense'

class GroupGstDetailSchema(BaseModel):
    applicable_from: date
    hsn_sac_details: Optional[str] = None
    hsn_sac: Optional[str] = None
    gst_rate_details: Optional[str] = None
    taxability_type: Optional[str] = None
    gst_rate: Optional[float] = None

    class Config:
        from_attributes = True

class AccountGroupBase(BaseModel):
    name: str
    parent_group_id: Optional[int] = None
    nature: str  # 'Asset', 'Liability', 'Income', 'Expense'
    affects_gross_profit: bool = False
    alias_name: Optional[str] = None
    is_addable: bool = True
    is_revenue: bool = False
    
    # Advanced Settings
    is_subledger: bool = False
    is_billwise_on: bool = False
    used_for_calculation: bool = False
    method_to_allocate: Optional[str] = None
    sort_position: int = 1000
    language_id: int = 1033

class AccountGroupCreate(AccountGroupBase):
    gst_details: Optional[List[GroupGstDetailSchema]] = []

class AccountGroupUpdate(AccountGroupBase):
    name: Optional[str] = None
    nature: Optional[str] = None
    gst_details: Optional[List[GroupGstDetailSchema]] = None

class AccountGroupResponse(AccountGroupBase):
    group_id: int
    company_id: int
    is_system_defined: bool
    is_deemed_positive: bool = False
    gst_details: Optional[List[GroupGstDetailSchema]] = []

    class Config:
        from_attributes = True

class AccountGroupTreeNode(AccountGroupResponse):
    children: List['AccountGroupTreeNode'] = []

    class Config:
        from_attributes = True

class BankDetailSchema(BaseModel):
    favouring_name: Optional[str] = None
    transaction_type: Optional[str] = None
    cross_using: Optional[str] = None
    account_number: Optional[str] = None
    ifsc_code: Optional[str] = None
    bank_name: Optional[str] = None
    branch_name: Optional[str] = None
    bilty_code: Optional[str] = None
    upi_id: Optional[str] = None

class LedgerBase(BaseModel):
    name: str
    group_id: int
    opening_balance: Decimal = Decimal("0.00")
    opening_balance_type: str = "Dr"  # 'Dr' or 'Cr'
    currency_id: Optional[int] = None
    gstin: Optional[str] = None
    gst_registration_type: Optional[str] = None
    aadhar_number: Optional[str] = None
    address: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    country: Optional[str] = "India"
    mobile: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    contact_person: Optional[str] = None
    pan_number: Optional[str] = None
    is_bank_account: bool = False
    bank_account_no: Optional[str] = None
    bank_ifsc: Optional[str] = None
    credit_limit: Optional[Decimal] = None
    credit_period_days: Optional[int] = None
    is_billwise_on: bool = True
    transporter_id: Optional[str] = None
    is_transporter: bool = False
    place_of_supply: Optional[str] = None
    is_other_territory_assessee: bool = False
    is_common_party: bool = False
    gst_applicable_from: Optional[datetime] = None
    is_inventory_affected: bool = False
    is_cost_centres_on: bool = False
    notes: Optional[str] = None
    is_active: bool = True

class LedgerBankDetailBase(BaseModel):
    transaction_type: str = "e-Fund Transfer"
    ref_id: Optional[str] = "Primary"
    favouring_name: Optional[str] = None
    cross_using: Optional[str] = "A/c Payee"
    account_number: Optional[str] = None
    ifsc_code: Optional[str] = None
    bank_name: Optional[str] = None
    upi_id: Optional[str] = None
    account_holder_name: Optional[str] = None
    is_default: bool = True

class LedgerBankDetailCreate(LedgerBankDetailBase):
    pass

class LedgerBankDetailResponse(LedgerBankDetailBase):
    bank_detail_id: int
    company_id: int
    ledger_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class LedgerCreate(LedgerBase):
    bank_details: Optional[List[LedgerBankDetailCreate]] = None

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
    bank_details: Optional[List[LedgerBankDetailResponse]] = None
    
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

class GstRegistrationTypeResponse(BaseModel):
    id: int
    name: str
    code: str
    requires_gstin: bool
    display_order: int
    is_active: bool

    class Config:
        from_attributes = True

class BankTransactionTypeResponse(BaseModel):
    id: int
    name: str
    display_order: int
    is_active: bool

    class Config:
        from_attributes = True
