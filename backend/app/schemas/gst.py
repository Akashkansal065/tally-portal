from pydantic import BaseModel
from typing import Optional, List
from decimal import Decimal
from datetime import date, datetime

class GstReturnPeriodCreate(BaseModel):
    return_type: str  # 'GSTR1' or 'GSTR3B'
    period_month: int
    period_year: int

class GstReturnPeriodResponse(GstReturnPeriodCreate):
    return_period_id: int
    company_id: int
    status: str
    filed_date: Optional[date] = None
    arn: Optional[str] = None
    filed_by: Optional[int] = None
    
    class Config:
        from_attributes = True

class Gstr1LineItemResponse(BaseModel):
    line_item_id: int
    return_period_id: int
    voucher_id: int
    supply_type: str
    party_gstin: Optional[str] = None
    invoice_number: str
    invoice_date: date
    place_of_supply: str
    taxable_value: Decimal
    cgst_amount: Decimal
    sgst_amount: Decimal
    igst_amount: Decimal
    cess_amount: Decimal
    invoice_value: Decimal
    
    class Config:
        from_attributes = True

class Gstr1HsnSummaryResponse(BaseModel):
    hsn_summary_id: int
    return_period_id: int
    hsn_code: str
    description: Optional[str] = None
    uqc: Optional[str] = None
    total_quantity: Decimal
    taxable_value: Decimal
    cgst_amount: Decimal
    sgst_amount: Decimal
    igst_amount: Decimal
    cess_amount: Decimal
    
    class Config:
        from_attributes = True

class ManualPurchaseCreate(BaseModel):
    source: str
    invoice_number: Optional[str] = None
    invoice_date: date
    product_description: str
    taxable_value: Decimal
    cgst_amount: Decimal
    sgst_amount: Decimal
    igst_amount: Decimal

class ManualPurchaseResponse(ManualPurchaseCreate):
    purchase_id: int
    company_id: int
    claimed_return_period_id: Optional[int] = None
    
    class Config:
        from_attributes = True

class Gstr3bSummaryResponse(BaseModel):
    summary_id: int
    return_period_id: int
    outward_taxable_value: Decimal
    outward_cgst: Decimal
    outward_sgst: Decimal
    outward_igst: Decimal
    outward_cess: Decimal
    itc_igst_available: Decimal
    itc_cgst_available: Decimal
    itc_sgst_available: Decimal
    itc_cess_available: Decimal
    itc_reversed: Decimal
    net_igst_payable: Decimal
    net_cgst_payable: Decimal
    net_sgst_payable: Decimal
    net_cess_payable: Decimal
    tax_paid_via_cash: Decimal
    tax_paid_via_itc: Decimal
    interest_paid: Decimal
    late_fee_paid: Decimal
    company_name: Optional[str] = None
    company_gstin: Optional[str] = None
    company_pan: Optional[str] = None
    
    class Config:
        from_attributes = True

class ItcEntryCreate(BaseModel):
    voucher_id: int
    supplier_gstin: Optional[str] = None
    invoice_number: str
    invoice_date: str  # YYYY-MM-DD
    taxable_value: Decimal
    cgst_amount: Decimal = Decimal("0.00")
    sgst_amount: Decimal = Decimal("0.00")
    igst_amount: Decimal = Decimal("0.00")
    cess_amount: Decimal = Decimal("0.00")
    eligibility: str = "Eligible"

class ItcEntryResponse(BaseModel):
    itc_entry_id: int
    company_id: int
    voucher_id: int
    supplier_gstin: Optional[str] = None
    invoice_number: str
    invoice_date: date
    taxable_value: Decimal
    cgst_amount: Decimal
    sgst_amount: Decimal
    igst_amount: Decimal
    cess_amount: Decimal
    eligibility: str
    claimed_return_period_id: Optional[int] = None
    
    class Config:
        from_attributes = True

class Gstr2bEntryResponse(BaseModel):
    entry_id: int
    company_id: int
    return_period_id: Optional[int] = None
    supplier_gstin: str
    supplier_name: Optional[str] = None
    invoice_number: str
    invoice_date: date
    invoice_type: str
    taxable_value: Decimal
    cgst_amount: Decimal
    sgst_amount: Decimal
    igst_amount: Decimal
    cess_amount: Decimal
    itc_availability: str
    match_status: str
    matched_voucher_id: Optional[int] = None

    class Config:
        from_attributes = True

class Gstr9AnnualReturnResponse(BaseModel):
    annual_return_id: int
    company_id: int
    financial_year: str
    status: str
    outward_taxable_supplies: Decimal
    outward_tax_amount: Decimal
    zero_rated_supplies: Decimal
    nil_rated_supplies: Decimal
    inward_taxable_supplies: Decimal
    inward_tax_amount: Decimal
    itc_claimed: Decimal
    itc_reversed: Decimal
    total_tax_payable: Decimal
    tax_paid_via_cash: Decimal
    tax_paid_via_itc: Decimal
    interest_paid: Decimal
    late_fee_paid: Decimal
    filed_date: Optional[date] = None
    arn: Optional[str] = None
    filed_by: Optional[int] = None

    class Config:
        from_attributes = True

class GstEinvoiceListResponse(BaseModel):
    voucher_id: int
    voucher_number: str
    voucher_date: date
    party_name: str
    party_gstin: Optional[str] = None
    amount: float
    irn: Optional[str] = None
    ack_no: Optional[str] = None
    eway_bill_no: Optional[str] = None

    class Config:
        from_attributes = True

class EinvoiceSettingsResponse(BaseModel):
    einvoice_env: str
    einvoice_username: Optional[str] = None
    einvoice_gsp_client_id: Optional[str] = None
    has_password: bool
    has_gsp_client_secret: bool

class EinvoiceSettingsUpdate(BaseModel):
    einvoice_env: str
    einvoice_username: Optional[str] = None
    einvoice_password: Optional[str] = None
    einvoice_gsp_client_id: Optional[str] = None
    einvoice_gsp_client_secret: Optional[str] = None



