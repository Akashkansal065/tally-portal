from sqlalchemy import Column, Integer, BigInteger, String, Date, Boolean, DateTime, ForeignKey, Enum, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.core.config import settings

class ExchangeRate(Base):
    __tablename__ = "exchange_rates"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    
    rate_id = Column(BigInteger, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    currency_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.currencies.currency_id"), nullable=False)
    rate_date = Column(Date, nullable=False)
    rate_to_base = Column(Numeric(14, 6), nullable=False)
    source = Column(Enum('Manual', 'RBI', 'API', name='exchange_rate_source'), default='Manual')
    
    currency = relationship("Currency")

class TdsSection(Base):
    __tablename__ = "tds_sections"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    
    section_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    section_code = Column(String(10), nullable=False)
    description = Column(String(150), nullable=False)
    default_rate_percent = Column(Numeric(5, 2), nullable=False)
    threshold_limit = Column(Numeric(18, 2), default=0.00)

class TcsSection(Base):
    __tablename__ = "tcs_sections"
    __table_args__ = {"schema": settings.TALLY_DATABASE_NAME}
    
    section_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    section_code = Column(String(10), nullable=False)
    description = Column(String(150), nullable=False)
    default_rate_percent = Column(Numeric(5, 2), nullable=False)
    threshold_limit = Column(Numeric(18, 2), default=0.00)

class LowerDeductionCertificate(Base):
    __tablename__ = "lower_deduction_certificates"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    certificate_id = Column(Integer, primary_key=True, index=True)
    party_ledger_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.ledgers.ledger_id"), nullable=False)
    section_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.tds_sections.section_id"), nullable=False)
    certificate_number = Column(String(50), nullable=False)
    reduced_rate_percent = Column(Numeric(5, 2), nullable=False)
    valid_from = Column(Date, nullable=False)
    valid_to = Column(Date, nullable=False)
    
    ledger = relationship("MstLedger")
    tds_section = relationship("TdsSection")

class TdsTcsEntry(Base):
    __tablename__ = "tds_tcs_entries"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    entry_id = Column(BigInteger, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    entry_type = Column(Enum('TDS', 'TCS', name='tds_tcs_type'), nullable=False)
    voucher_id = Column(BigInteger, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.vouchers.voucher_id", ondelete="CASCADE"), nullable=False)
    party_ledger_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.ledgers.ledger_id"), nullable=False)
    section_id = Column(Integer, nullable=False)  # references either tds_sections or tcs_sections depending on entry_type
    taxable_amount = Column(Numeric(18, 2), nullable=False)
    rate_percent_applied = Column(Numeric(5, 2), nullable=False)
    tax_amount = Column(Numeric(18, 2), nullable=False)
    certificate_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.lower_deduction_certificates.certificate_id"), nullable=True)
    deduction_date = Column(Date, nullable=False)
    
    voucher = relationship("TrnVoucher")
    party = relationship("MstLedger")
    ldc = relationship("LowerDeductionCertificate")

class TaxChallan(Base):
    __tablename__ = "tax_challans"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    challan_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    entry_type = Column(Enum('TDS', 'TCS', name='challan_entry_type'), nullable=False)
    challan_number = Column(String(30), nullable=False)
    bsr_code = Column(String(10), nullable=False)
    payment_date = Column(Date, nullable=False)
    amount = Column(Numeric(18, 2), nullable=False)
    quarter = Column(Integer, nullable=False)
    financial_year = Column(String(9), nullable=False)

class ChallanEntryMap(Base):
    __tablename__ = "challan_entry_map"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    map_id = Column(BigInteger, primary_key=True, index=True)
    challan_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.tax_challans.challan_id", ondelete="CASCADE"), nullable=False)
    entry_id = Column(BigInteger, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.tds_tcs_entries.entry_id", ondelete="CASCADE"), nullable=False)
