from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from datetime import datetime, date

from app.core.database import get_db
from app.core.permissions import require_permission
from app.models.user import User
from app.models.ledger import Currency, MstLedger
from app.models.currency_tds import ExchangeRate, TdsSection, LowerDeductionCertificate, TdsTcsEntry
from app.schemas.currency_tds import (
    CurrencyCreate, CurrencyResponse,
    ExchangeRateCreate, ExchangeRateResponse,
    TdsSectionCreate, TdsSectionResponse,
    LowerDeductionCertificateCreate, LowerDeductionCertificateResponse,
    TdsTcsEntryCreate, TdsTcsEntryResponse
)

router = APIRouter(tags=["Currency & TDS"])

# --- Currencies ---

@router.post("/currency", response_model=CurrencyResponse)
async def create_currency(
    req: CurrencyCreate,
    user: User = Depends(require_permission("settings", "update")),
    db: AsyncSession = Depends(get_db)
):
    dup_query = await db.execute(select(Currency).where(Currency.code == req.code))
    if dup_query.scalars().first():
        raise HTTPException(status_code=400, detail="Currency code already exists.")
        
    currency = Currency(
        code=req.code,
        symbol=req.symbol,
        decimal_places=req.decimal_places,
        is_base_currency=req.is_base_currency
    )
    db.add(currency)
    await db.commit()
    await db.refresh(currency)
    return currency

@router.get("/currency", response_model=List[CurrencyResponse])
async def get_currencies(
    user: User = Depends(require_permission("vouchers", "read")),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(Currency))
    return res.scalars().all()

# --- Exchange Rates ---

@router.get("/currency/exchange-rates", response_model=List[ExchangeRateResponse])
async def get_exchange_rates(
    user: User = Depends(require_permission("vouchers", "read")),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(ExchangeRate).where(ExchangeRate.company_id == user.company_id)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("/currency/exchange-rates", response_model=ExchangeRateResponse)
async def create_exchange_rate(
    req: ExchangeRateCreate,
    user: User = Depends(require_permission("settings", "update")),
    db: AsyncSession = Depends(get_db)
):
    try:
        rdate = datetime.strptime(req.rate_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
        
    # Check currency exists
    curr_query = await db.execute(select(Currency).where(Currency.currency_id == req.currency_id))
    if not curr_query.scalars().first():
        raise HTTPException(status_code=400, detail="Currency not found.")
        
    # Check if duplicate for date
    dup_query = await db.execute(
        select(ExchangeRate).where(
            ExchangeRate.company_id == user.company_id,
            ExchangeRate.currency_id == req.currency_id,
            ExchangeRate.rate_date == rdate
        )
    )
    dup = dup_query.scalars().first()
    if dup:
        dup.rate_to_base = req.rate_to_base
        dup.source = req.source
        await db.commit()
        await db.refresh(dup)
        return dup
        
    rate = ExchangeRate(
        company_id=user.company_id,
        currency_id=req.currency_id,
        rate_date=rdate,
        rate_to_base=req.rate_to_base,
        source=req.source
    )
    db.add(rate)
    await db.commit()
    await db.refresh(rate)
    return rate

# --- TDS Sections ---

@router.get("/tds/sections", response_model=List[TdsSectionResponse])
async def get_tds_sections(
    user: User = Depends(require_permission("settings", "read")),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(TdsSection).where(TdsSection.company_id == user.company_id)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("/tds/sections", response_model=TdsSectionResponse)
async def create_tds_section(
    req: TdsSectionCreate,
    user: User = Depends(require_permission("settings", "update")),
    db: AsyncSession = Depends(get_db)
):
    dup_query = await db.execute(
        select(TdsSection).where(
            TdsSection.company_id == user.company_id,
            TdsSection.section_code == req.section_code
        )
    )
    if dup_query.scalars().first():
        raise HTTPException(status_code=400, detail="TDS Section already exists.")
        
    section = TdsSection(
        company_id=user.company_id,
        section_code=req.section_code,
        description=req.description,
        default_rate_percent=req.default_rate_percent,
        threshold_limit=req.threshold_limit
    )
    db.add(section)
    await db.commit()
    await db.refresh(section)
    return section

# --- Lower Deduction Certificates ---

@router.get("/tds/certificates", response_model=List[LowerDeductionCertificateResponse])
async def get_ldcs(
    user: User = Depends(require_permission("settings", "read")),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(LowerDeductionCertificate).join(MstLedger, LowerDeductionCertificate.party_ledger_id == MstLedger.ledger_id).where(MstLedger.company_id == user.company_id)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("/tds/certificates", response_model=LowerDeductionCertificateResponse)
async def create_ldc(
    req: LowerDeductionCertificateCreate,
    user: User = Depends(require_permission("settings", "create")),
    db: AsyncSession = Depends(get_db)
):
    try:
        from_date = datetime.strptime(req.valid_from, "%Y-%m-%d").date()
        to_date = datetime.strptime(req.valid_to, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
        
    # Verify ledger
    ledg_query = await db.execute(
        select(MstLedger).where(MstLedger.ledger_id == req.party_ledger_id, MstLedger.company_id == user.company_id)
    )
    if not ledg_query.scalars().first():
        raise HTTPException(status_code=400, detail="Party ledger not found.")
        
    # Verify section
    sec_query = await db.execute(
        select(TdsSection).where(TdsSection.section_id == req.section_id, TdsSection.company_id == user.company_id)
    )
    if not sec_query.scalars().first():
        raise HTTPException(status_code=400, detail="TDS Section not found.")
        
    ldc = LowerDeductionCertificate(
        party_ledger_id=req.party_ledger_id,
        section_id=req.section_id,
        certificate_number=req.certificate_number,
        reduced_rate_percent=req.reduced_rate_percent,
        valid_from=from_date,
        valid_to=to_date
    )
    db.add(ldc)
    await db.commit()
    await db.refresh(ldc)
    return ldc

# --- TDS Resolver ---

@router.get("/tds/resolve-rate/{party_ledger_id}/{section_id}")
async def resolve_tds_rate(
    party_ledger_id: int,
    section_id: int,
    check_date: Optional[str] = None,
    user: User = Depends(require_permission("vouchers", "read")),
    db: AsyncSession = Depends(get_db)
):
    if check_date:
        try:
            target_date = datetime.strptime(check_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    else:
        target_date = date.today()
        
    # Verify section
    sec_query = await db.execute(
        select(TdsSection).where(TdsSection.section_id == section_id, TdsSection.company_id == user.company_id)
    )
    section = sec_query.scalars().first()
    if not section:
        raise HTTPException(status_code=400, detail="TDS Section not found.")
        
    # Check LDC
    ldc_query = await db.execute(
        select(LowerDeductionCertificate).where(
            LowerDeductionCertificate.party_ledger_id == party_ledger_id,
            LowerDeductionCertificate.section_id == section_id,
            LowerDeductionCertificate.valid_from <= target_date,
            LowerDeductionCertificate.valid_to >= target_date
        )
    )
    ldc = ldc_query.scalars().first()
    
    if ldc:
        return {
            "rate_percent": float(ldc.reduced_rate_percent),
            "certificate_id": ldc.certificate_id,
            "source": "Certificate"
        }
        
    return {
        "rate_percent": float(section.default_rate_percent),
        "certificate_id": None,
        "source": "Default"
    }

# --- TDS Entries ---

@router.post("/tds/entries", response_model=TdsTcsEntryResponse)
async def create_tds_entry(
    req: TdsTcsEntryCreate,
    user: User = Depends(require_permission("vouchers", "create")),
    db: AsyncSession = Depends(get_db)
):
    try:
        ddate = datetime.strptime(req.deduction_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
        
    entry = TdsTcsEntry(
        company_id=user.company_id,
        entry_type=req.entry_type,
        voucher_id=req.voucher_id,
        party_ledger_id=req.party_ledger_id,
        section_id=req.section_id,
        taxable_amount=req.taxable_amount,
        rate_percent_applied=req.rate_percent_applied,
        tax_amount=req.tax_amount,
        certificate_id=req.certificate_id,
        deduction_date=ddate
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry
