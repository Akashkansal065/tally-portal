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

from pydantic import model_validator

class VoucherEntryResponse(VoucherEntryCreate):
    entry_id: int
    voucher_id: int
    
    class Config:
        from_attributes = True

class VoucherItemResponse(BaseModel):
    ledger_id: int
    ledger_name: str
    amount: Decimal
    entry_type: str  # 'Debit' or 'Credit'

    class Config:
        from_attributes = True

class VoucherListResponse(BaseModel):
    """Flat voucher response matching tally-web's getVouchersList output."""
    voucher_id: int
    date: str                             # "YYYY-MM-DD"
    voucher_type: str                     # "Sales", "Receipt", etc.
    voucher_number: str
    reference_number: Optional[str] = None
    narration: Optional[str] = None
    party_name: str                       # Resolved from entries via group scoring
    amount: float                         # Primary party entry amount (abs)
    total_amount: float                   # voucher.total_amount

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
    
    # Frontend compatibility fields
    date: date
    type: str
    items: List[VoucherItemResponse]
    
    @model_validator(mode="before")
    @classmethod
    def map_frontend_fields(cls, data):
        # We need to extract entries list first
        is_dict = isinstance(data, dict)
        entries = data.get("entries") if is_dict else getattr(data, "entries", [])
        
        # Candidate scoring to identify the primary party ledger (Debtor, Creditor, Bank, or Cash)
        primary_idx = 0
        max_score = -100
        for idx, entry in enumerate(entries):
            ent_dict = isinstance(entry, dict)
            ledger = entry.get("ledger") if ent_dict else getattr(entry, "ledger", None)
            if ledger:
                group = ledger.get("group") if isinstance(ledger, dict) else getattr(ledger, "group", None)
                gname = (group.get("name") if isinstance(group, dict) else getattr(group, "name", "")).lower() if group else ""
                lname = (ledger.get("name") if isinstance(ledger, dict) else getattr(ledger, "name", "")).lower()
                
                # Base scoring
                score = 0
                if "debtors" in gname or "creditors" in gname:
                    score = 10
                elif "bank" in gname or "cash" in gname:
                    score = 5
                elif "sales" in gname or "purchase" in gname or "tax" in gname or "duty" in gname or "round" in lname:
                    score = -10
                else:
                    score = 1
                    
                if score > max_score:
                    max_score = score
                    primary_idx = idx
                    
        # Reorder entries to put the primary candidate first
        ordered_entries = []
        if entries:
            ordered_entries.append(entries[primary_idx])
            for idx, entry in enumerate(entries):
                if idx != primary_idx:
                    ordered_entries.append(entry)
                    
        # Map ordered entries to items
        items = []
        for entry in ordered_entries:
            ent_dict = isinstance(entry, dict)
            ledger_id = entry.get("ledger_id") if ent_dict else getattr(entry, "ledger_id", None)
            debit = entry.get("debit_amount", 0) if ent_dict else getattr(entry, "debit_amount", 0)
            credit = entry.get("credit_amount", 0) if ent_dict else getattr(entry, "credit_amount", 0)
            
            ledger = entry.get("ledger") if ent_dict else getattr(entry, "ledger", None)
            ledger_name = ledger.get("name") if isinstance(ledger, dict) else getattr(ledger, "name", "Unknown Ledger") if ledger else "Unknown Ledger"
            
            amount = debit if debit > 0 else credit
            entry_type = "Debit" if debit > 0 else "Credit"
            items.append({
                "ledger_id": ledger_id,
                "ledger_name": ledger_name,
                "amount": amount,
                "entry_type": entry_type
            })
            
        if is_dict:
            # Map date
            if "date" not in data and "voucher_date" in data:
                data["date"] = data["voucher_date"]
            # Map type
            if "type" not in data:
                vt = data.get("voucher_type")
                if vt:
                    data["type"] = vt.get("name") if isinstance(vt, dict) else getattr(vt, "name", "Unknown")
                else:
                    data["type"] = "Unknown"
            data["items"] = items
        else:
            obj_dict = {}
            for col in data.__table__.columns:
                obj_dict[col.name] = getattr(data, col.name)
            
            obj_dict["date"] = data.voucher_date
            obj_dict["type"] = data.voucher_type.name if data.voucher_type else "Unknown"
            obj_dict["items"] = items
            obj_dict["entries"] = data.entries
            obj_dict["voucher_type"] = data.voucher_type
            return obj_dict
            
        return data

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
