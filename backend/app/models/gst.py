from sqlalchemy import Column, Integer, BigInteger, String, Date, Enum, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.config import settings

class GstReturnPeriod(Base):
    __tablename__ = "gst_return_periods"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    return_period_id = Column(BigInteger, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    return_type = Column(Enum('GSTR1', 'GSTR3B', name='gst_return_type_enum'), nullable=False)
    period_month = Column(Integer, nullable=False)
    period_year = Column(Integer, nullable=False)
    status = Column(Enum('Draft', 'Filed', name='gst_return_status_enum'), default='Draft')
    filed_date = Column(Date, nullable=True)
    arn = Column(String(30), nullable=True)
    filed_by = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id"), nullable=True)
    
    company = relationship("Company")
    user = relationship("User")
    gstr1_lines = relationship("Gstr1LineItem", back_populates="period", cascade="all, delete-orphan")
    gstr1_hsn_summaries = relationship("Gstr1HsnSummary", back_populates="period", cascade="all, delete-orphan")
    gstr3b_summary = relationship("Gstr3bSummary", uselist=False, back_populates="period", cascade="all, delete-orphan")

class Gstr1LineItem(Base):
    __tablename__ = "gstr1_line_items"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    line_item_id = Column(BigInteger, primary_key=True, index=True)
    return_period_id = Column(BigInteger, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.gst_return_periods.return_period_id", ondelete="CASCADE"), nullable=False)
    voucher_id = Column(BigInteger, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.vouchers.voucher_id"), nullable=False)
    supply_type = Column(Enum('B2B', 'B2CL', 'B2CS', 'Export', 'Nil Rated', 'Exempt', name='gst_supply_type_enum'), nullable=False)
    party_gstin = Column(String(15), nullable=True)
    invoice_number = Column(String(30), nullable=False)
    invoice_date = Column(Date, nullable=False)
    place_of_supply = Column(String(50), nullable=False)
    taxable_value = Column(Numeric(18, 2), nullable=False)
    cgst_amount = Column(Numeric(18, 2), default=0.00)
    sgst_amount = Column(Numeric(18, 2), default=0.00)
    igst_amount = Column(Numeric(18, 2), default=0.00)
    cess_amount = Column(Numeric(18, 2), default=0.00)
    invoice_value = Column(Numeric(18, 2), nullable=False)
    
    period = relationship("GstReturnPeriod", back_populates="gstr1_lines")
    voucher = relationship("TrnVoucher")

class Gstr1HsnSummary(Base):
    __tablename__ = "gstr1_hsn_summary"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    hsn_summary_id = Column(BigInteger, primary_key=True, index=True)
    return_period_id = Column(BigInteger, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.gst_return_periods.return_period_id", ondelete="CASCADE"), nullable=False)
    hsn_code = Column(String(10), nullable=False)
    description = Column(String(150), nullable=True)
    uqc = Column(String(20), nullable=True)
    total_quantity = Column(Numeric(14, 3), nullable=False)
    taxable_value = Column(Numeric(18, 2), nullable=False)
    cgst_amount = Column(Numeric(18, 2), default=0.00)
    sgst_amount = Column(Numeric(18, 2), default=0.00)
    igst_amount = Column(Numeric(18, 2), default=0.00)
    cess_amount = Column(Numeric(18, 2), default=0.00)
    
    period = relationship("GstReturnPeriod", back_populates="gstr1_hsn_summaries")

class Gstr3bSummary(Base):
    __tablename__ = "gstr3b_summary"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    summary_id = Column(BigInteger, primary_key=True, index=True)
    return_period_id = Column(BigInteger, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.gst_return_periods.return_period_id", ondelete="CASCADE"), nullable=False, unique=True)
    
    outward_taxable_value = Column(Numeric(18, 2), default=0.00)
    outward_cgst = Column(Numeric(18, 2), default=0.00)
    outward_sgst = Column(Numeric(18, 2), default=0.00)
    outward_igst = Column(Numeric(18, 2), default=0.00)
    outward_cess = Column(Numeric(18, 2), default=0.00)
    
    itc_igst_available = Column(Numeric(18, 2), default=0.00)
    itc_cgst_available = Column(Numeric(18, 2), default=0.00)
    itc_sgst_available = Column(Numeric(18, 2), default=0.00)
    itc_cess_available = Column(Numeric(18, 2), default=0.00)
    itc_reversed = Column(Numeric(18, 2), default=0.00)
    
    net_igst_payable = Column(Numeric(18, 2), default=0.00)
    net_cgst_payable = Column(Numeric(18, 2), default=0.00)
    net_sgst_payable = Column(Numeric(18, 2), default=0.00)
    net_cess_payable = Column(Numeric(18, 2), default=0.00)
    
    tax_paid_via_cash = Column(Numeric(18, 2), default=0.00)
    tax_paid_via_itc = Column(Numeric(18, 2), default=0.00)
    interest_paid = Column(Numeric(18, 2), default=0.00)
    late_fee_paid = Column(Numeric(18, 2), default=0.00)
    
    period = relationship("GstReturnPeriod", back_populates="gstr3b_summary")

class ItcEntry(Base):
    __tablename__ = "itc_entries"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    itc_entry_id = Column(BigInteger, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    voucher_id = Column(BigInteger, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.vouchers.voucher_id"), nullable=False)
    supplier_gstin = Column(String(15), nullable=True)
    invoice_number = Column(String(30), nullable=False)
    invoice_date = Column(Date, nullable=False)
    taxable_value = Column(Numeric(18, 2), nullable=False)
    cgst_amount = Column(Numeric(18, 2), default=0.00)
    sgst_amount = Column(Numeric(18, 2), default=0.00)
    igst_amount = Column(Numeric(18, 2), default=0.00)
    cess_amount = Column(Numeric(18, 2), default=0.00)
    eligibility = Column(Enum('Eligible', 'Ineligible', 'Partially Eligible', name='itc_eligibility_enum'), default='Eligible')
    claimed_return_period_id = Column(BigInteger, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.gst_return_periods.return_period_id", ondelete="SET NULL"), nullable=True)
    
    company = relationship("Company")
    voucher = relationship("TrnVoucher")
    claimed_period = relationship("GstReturnPeriod")

class Gstr2bEntry(Base):
    """GSTR-2B Auto-drafted ITC statement — purchase reconciliation entries"""
    __tablename__ = "gstr2b_entries"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    entry_id = Column(BigInteger, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    return_period_id = Column(BigInteger, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.gst_return_periods.return_period_id", ondelete="SET NULL"), nullable=True)
    supplier_gstin = Column(String(15), nullable=False)
    supplier_name = Column(String(150), nullable=True)
    invoice_number = Column(String(30), nullable=False)
    invoice_date = Column(Date, nullable=False)
    invoice_type = Column(Enum('Regular', 'SEZ', 'Reverse Charge', 'Deemed Export', name='gstr2b_inv_type_enum'), default='Regular')
    taxable_value = Column(Numeric(18, 2), nullable=False)
    cgst_amount = Column(Numeric(18, 2), default=0.00)
    sgst_amount = Column(Numeric(18, 2), default=0.00)
    igst_amount = Column(Numeric(18, 2), default=0.00)
    cess_amount = Column(Numeric(18, 2), default=0.00)
    itc_availability = Column(Enum('Available', 'Not Available', 'Pending', name='gstr2b_itc_avail_enum'), default='Pending')
    match_status = Column(Enum('Matched', 'Unmatched', 'Mismatch', name='gstr2b_match_enum'), default='Unmatched')
    matched_voucher_id = Column(BigInteger, nullable=True)
    
    company = relationship("Company")
    period = relationship("GstReturnPeriod")

class Gstr9AnnualReturn(Base):
    """GSTR-9 Annual Return summary — year-end filing"""
    __tablename__ = "gstr9_annual_returns"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    annual_return_id = Column(BigInteger, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    financial_year = Column(String(9), nullable=False)  # e.g. '2025-2026'
    status = Column(Enum('Draft', 'Filed', name='gstr9_status_enum'), default='Draft')
    
    # Part II — Outward Supplies
    outward_taxable_supplies = Column(Numeric(18, 2), default=0.00)
    outward_tax_amount = Column(Numeric(18, 2), default=0.00)
    zero_rated_supplies = Column(Numeric(18, 2), default=0.00)
    nil_rated_supplies = Column(Numeric(18, 2), default=0.00)
    
    # Part III — Inward Supplies (ITC)
    inward_taxable_supplies = Column(Numeric(18, 2), default=0.00)
    inward_tax_amount = Column(Numeric(18, 2), default=0.00)
    itc_claimed = Column(Numeric(18, 2), default=0.00)
    itc_reversed = Column(Numeric(18, 2), default=0.00)
    
    # Part IV — Tax Paid
    total_tax_payable = Column(Numeric(18, 2), default=0.00)
    tax_paid_via_cash = Column(Numeric(18, 2), default=0.00)
    tax_paid_via_itc = Column(Numeric(18, 2), default=0.00)
    interest_paid = Column(Numeric(18, 2), default=0.00)
    late_fee_paid = Column(Numeric(18, 2), default=0.00)
    
    filed_date = Column(Date, nullable=True)
    arn = Column(String(30), nullable=True)
    filed_by = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id"), nullable=True)
    
    company = relationship("Company")
    user = relationship("User")

class ManualPurchase(Base):
    """User-entered manual purchases (Amazon, Flipkart, Offline, etc) for ITC calculation"""
    __tablename__ = "manual_purchases"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    purchase_id = Column(BigInteger, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    source = Column(String(100), nullable=False)
    invoice_number = Column(String(50), nullable=True)
    invoice_date = Column(Date, nullable=False)
    product_description = Column(String(200), nullable=False)
    taxable_value = Column(Numeric(18, 2), nullable=False, default=0.00)
    cgst_amount = Column(Numeric(18, 2), nullable=False, default=0.00)
    sgst_amount = Column(Numeric(18, 2), nullable=False, default=0.00)
    igst_amount = Column(Numeric(18, 2), nullable=False, default=0.00)
    claimed_return_period_id = Column(BigInteger, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.gst_return_periods.return_period_id", ondelete="SET NULL"), nullable=True)
    
    company = relationship("Company")
    claimed_period = relationship("GstReturnPeriod")
