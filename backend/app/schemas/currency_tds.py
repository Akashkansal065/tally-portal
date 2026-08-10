from pydantic import BaseModel
from typing import Optional, List
from decimal import Decimal
from datetime import date, datetime

class ExchangeRateNestedCreate(BaseModel):
    rate_date: str  # YYYY-MM-DD
    standard_rate: Optional[Decimal] = None
    selling_rate: Optional[Decimal] = None
    buying_rate: Optional[Decimal] = None
    source: str = "Manual"

class CurrencyCreate(BaseModel):
    code: str
    symbol: str
    formal_name: Optional[str] = None
    decimal_places: int = 2
    show_amount_in_millions: bool = False
    suffix_symbol_to_amount: bool = False
    add_space_between_amount_and_symbol: bool = True
    word_representing_amount_after_decimal: Optional[str] = None
    decimal_places_for_words: int = 2
    is_base_currency: bool = False
    rates: Optional[List[ExchangeRateNestedCreate]] = []

class ExchangeRateResponse(BaseModel):
    rate_id: int
    company_id: int
    currency_id: int
    rate_date: date
    standard_rate: Optional[Decimal]
    selling_rate: Optional[Decimal]
    buying_rate: Optional[Decimal]
    source: str

    class Config:
        from_attributes = True

class CurrencyResponse(CurrencyCreate):
    currency_id: int
    rates: List[ExchangeRateResponse] = []
    
    class Config:
        from_attributes = True


class ExchangeRateCreate(BaseModel):
    currency_id: int
    rate_date: str  # YYYY-MM-DD
    standard_rate: Optional[Decimal] = None
    selling_rate: Optional[Decimal] = None
    buying_rate: Optional[Decimal] = None
    source: str = "Manual"
    class Config:
        from_attributes = True

class TdsSectionCreate(BaseModel):
    section_code: str
    description: str
    default_rate_percent: Decimal
    threshold_limit: Decimal = Decimal("0.00")

class TdsSectionResponse(TdsSectionCreate):
    section_id: int
    company_id: int
    
    class Config:
        from_attributes = True

class TcsSectionCreate(BaseModel):
    section_code: str
    description: str
    default_rate_percent: Decimal
    threshold_limit: Decimal = Decimal("0.00")

class TcsSectionResponse(TcsSectionCreate):
    section_id: int
    company_id: int
    
    class Config:
        from_attributes = True

class LowerDeductionCertificateCreate(BaseModel):
    party_ledger_id: int
    section_id: int
    certificate_number: str
    reduced_rate_percent: Decimal
    valid_from: str  # YYYY-MM-DD
    valid_to: str    # YYYY-MM-DD

class LowerDeductionCertificateResponse(BaseModel):
    certificate_id: int
    party_ledger_id: int
    section_id: int
    certificate_number: str
    reduced_rate_percent: Decimal
    valid_from: date
    valid_to: date
    
    class Config:
        from_attributes = True

class TdsTcsEntryCreate(BaseModel):
    entry_type: str  # 'TDS' or 'TCS'
    voucher_id: int
    party_ledger_id: int
    section_id: int
    taxable_amount: Decimal
    rate_percent_applied: Decimal
    tax_amount: Decimal
    certificate_id: Optional[int] = None
    deduction_date: str  # YYYY-MM-DD

class TdsTcsEntryResponse(BaseModel):
    entry_id: int
    company_id: int
    entry_type: str
    voucher_id: int
    party_ledger_id: int
    section_id: int
    taxable_amount: Decimal
    rate_percent_applied: Decimal
    tax_amount: Decimal
    certificate_id: Optional[int] = None
    deduction_date: date
    
    class Config:
        from_attributes = True
