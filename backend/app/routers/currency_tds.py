from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from datetime import datetime, date
import logging

from app.core.database import get_db
from app.core import master_cache
from app.core.master_cache import as_schema_list, cached_master
from app.core.permissions import require_permission
from app.models.portal_core import User
from app.models.tally_core import MstLedger
from app.models.portal_core import Currency, SyncQueue
from app.models.portal_core import ExchangeRate, TdsSection, LowerDeductionCertificate, TdsTcsEntry
from sqlalchemy.orm import selectinload
from app.schemas.currency_tds import (
    CurrencyCreate, CurrencyResponse,
    ExchangeRateCreate, ExchangeRateResponse,
    TdsSectionCreate, TdsSectionResponse,
    LowerDeductionCertificateCreate, LowerDeductionCertificateResponse,
    TdsTcsEntryCreate, TdsTcsEntryResponse
)
from app.routers.sync import try_push_currency_realtime

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Currency & TDS"])

from app.core.world_currencies import WORLD_CURRENCIES as SEED_CURRENCIES


def _own_currency(user: User, *conditions):
    """A query for currencies of the signed-in user's company. Each company has its own list."""
    return select(Currency).where(Currency.company_id == user.company_id, *conditions)


@router.get("/currency/iso")
async def list_world_currencies(user: User = Depends(require_permission("currencies", "read"))):
    """The world currencies to pick from when adding one. The same for everyone; not a company's own list."""
    return [{"code": c["code"], "symbol": c["symbol"], "formal_name": c["formal_name"],
             "decimal_places": c["decimal_places"]} for c in SEED_CURRENCIES]


@router.post("/currency/seed")
async def seed_currencies(
    user: User = Depends(require_permission("currencies", "update")),
    db: AsyncSession = Depends(get_db)
):
    """Bulk-insert world currencies for this company. Skips any it already has by code."""
    inserted = 0
    skipped = 0
    for c in SEED_CURRENCIES:
        existing = (await db.execute(_own_currency(user, Currency.code == c["code"]))).scalars().first()
        if existing:
            skipped += 1
            continue
        curr = Currency(
            company_id=user.company_id,
            code=c["code"],
            symbol=c["code"],
            formal_name=c["formal_name"],
            decimal_places=c["decimal_places"],
            show_amount_in_millions=c.get("show_amount_in_millions", False),
            suffix_symbol_to_amount=c.get("suffix_symbol_to_amount", False),
            add_space_between_amount_and_symbol=c.get("add_space_between_amount_and_symbol", True),
            word_representing_amount_after_decimal=c.get("word_representing_amount_after_decimal", ""),
            decimal_places_for_words=c.get("decimal_places_for_words", 2),
            is_base_currency=False
        )
        db.add(curr)
        inserted += 1
    await db.commit()
    return {"status": "success", "inserted": inserted, "skipped": skipped, "total_available": len(SEED_CURRENCIES)}

# --- Currencies ---

@router.post("/currency", response_model=CurrencyResponse)
async def create_currency(
    req: CurrencyCreate,
    user: User = Depends(require_permission("currencies", "create")),
    db: AsyncSession = Depends(get_db)
):
    logger.info(f"User {user.email} attempting to create currency: {req.code}")
    dup_query = await db.execute(_own_currency(user, Currency.code == req.code))
    if dup_query.scalars().first():
        logger.warning(f"Currency creation failed: Code {req.code} already exists.")
        raise HTTPException(status_code=400, detail="Currency code already exists.")
        
    currency = Currency(
        company_id=user.company_id,
        code=req.code,
        symbol=req.symbol,
        formal_name=req.formal_name,
        decimal_places=req.decimal_places,
        show_amount_in_millions=req.show_amount_in_millions,
        suffix_symbol_to_amount=req.suffix_symbol_to_amount,
        add_space_between_amount_and_symbol=req.add_space_between_amount_and_symbol,
        word_representing_amount_after_decimal=req.word_representing_amount_after_decimal,
        decimal_places_for_words=req.decimal_places_for_words,
        is_base_currency=req.is_base_currency
    )
    db.add(currency)
    await db.commit()
    await db.refresh(currency)
    
    # Process Rates
    if req.rates:
        for rate_req in req.rates:
            try:
                rdate = datetime.strptime(rate_req.rate_date, "%Y-%m-%d").date()
                rate = ExchangeRate(
                    company_id=user.company_id,
                    currency_id=currency.currency_id,
                    rate_date=rdate,
                    standard_rate=rate_req.standard_rate,
                    selling_rate=rate_req.selling_rate,
                    buying_rate=rate_req.buying_rate,
                    source=rate_req.source
                )
                db.add(rate)
            except ValueError:
                pass
        await db.commit()
        await db.refresh(currency)
        
    new_sq = SyncQueue(company_id=user.company_id, record_type="Currency", record_id=currency.currency_id, action="Create", is_processed=False)
    db.add(new_sq)
    await db.commit()
    
    logger.info(f"Currency {currency.code} created successfully. Added to SyncQueue (Create).")
    
    # Try pushing to Tally in real-time
    logger.info(f"Triggering real-time Tally push for Currency {currency.code} (Create)...")
    await try_push_currency_realtime(currency.currency_id, new_sq.sync_id, "Create", db)

    # Reload with its rates: the response lists them, and they cannot be fetched lazily here
    return (await db.execute(_own_currency(user, Currency.currency_id == currency.currency_id)
                             .options(selectinload(Currency.rates)).execution_options(populate_existing=True))).scalars().first()

@router.put("/currency/{currency_id}", response_model=CurrencyResponse)
async def update_currency(
    currency_id: int,
    req: CurrencyCreate,
    user: User = Depends(require_permission("currencies", "update")),
    db: AsyncSession = Depends(get_db)
):
    logger.info(f"User {user.email} attempting to alter currency ID {currency_id} to code {req.code}")
    curr = (await db.execute(_own_currency(user, Currency.currency_id == currency_id).options(selectinload(Currency.rates)))).scalars().first()
    if not curr:
        logger.warning(f"Currency alter failed: Currency ID {currency_id} not found.")
        raise HTTPException(status_code=404, detail="Currency not found.")
        
    if curr.code != req.code:
        dup = (await db.execute(_own_currency(user, Currency.code == req.code))).scalars().first()
        if dup:
            logger.warning(f"Currency alter failed: Code {req.code} already exists.")
            raise HTTPException(status_code=400, detail="Currency code already exists.")
            
    curr.code = req.code
    curr.symbol = req.symbol
    curr.formal_name = req.formal_name
    curr.decimal_places = req.decimal_places
    curr.show_amount_in_millions = req.show_amount_in_millions
    curr.suffix_symbol_to_amount = req.suffix_symbol_to_amount
    curr.add_space_between_amount_and_symbol = req.add_space_between_amount_and_symbol
    curr.word_representing_amount_after_decimal = req.word_representing_amount_after_decimal
    curr.decimal_places_for_words = req.decimal_places_for_words
    curr.is_base_currency = req.is_base_currency
    
    if req.rates is not None:
        from sqlalchemy import delete
        await db.execute(delete(ExchangeRate).where(ExchangeRate.currency_id == currency_id, ExchangeRate.company_id == user.company_id))
        
        for rate_req in req.rates:
            try:
                rdate = datetime.strptime(rate_req.rate_date, "%Y-%m-%d").date()
                rate = ExchangeRate(
                    company_id=user.company_id,
                    currency_id=currency_id,
                    rate_date=rdate,
                    standard_rate=rate_req.standard_rate,
                    selling_rate=rate_req.selling_rate,
                    buying_rate=rate_req.buying_rate,
                    source=rate_req.source
                )
                db.add(rate)
            except ValueError:
                pass
                
    new_sq = SyncQueue(company_id=user.company_id, record_type="Currency", record_id=currency_id, action="Alter", is_processed=False)
    db.add(new_sq)
    await db.commit()
    await db.refresh(curr)
    
    logger.info(f"Currency {curr.code} (ID: {currency_id}) updated successfully. Added to SyncQueue (Alter).")
    
    # Try pushing to Tally in real-time
    logger.info(f"Triggering real-time Tally push for Currency {curr.code} (Alter)...")
    await try_push_currency_realtime(currency_id, new_sq.sync_id, "Alter", db)
    
    # Reload with the new rates
    curr = (await db.execute(_own_currency(user, Currency.currency_id == currency_id)
                             .options(selectinload(Currency.rates)).execution_options(populate_existing=True))).scalars().first()
    return curr

@router.get("/currency", response_model=List[CurrencyResponse])
async def get_currencies(
    user: User = Depends(require_permission("currencies", "read")),
    db: AsyncSession = Depends(get_db)
):
    # This company's currencies with their exchange rates
    async def load():
        res = await db.execute(_own_currency(user).options(selectinload(Currency.rates)).order_by(Currency.code))
        return as_schema_list(CurrencyResponse, res.scalars().all())
    return await cached_master(user.company_id, master_cache.CURRENCIES, load)
    
@router.delete("/currency/{currency_id}")
async def delete_currency(
    currency_id: int,
    user: User = Depends(require_permission("currencies", "delete")),
    db: AsyncSession = Depends(get_db)
):
    logger.info(f"User {user.email} attempting to delete currency ID {currency_id}")
    curr = (await db.execute(_own_currency(user, Currency.currency_id == currency_id))).scalars().first()
    if not curr:
        logger.warning(f"Currency delete failed: Currency ID {currency_id} not found.")
        raise HTTPException(status_code=404, detail="Currency not found.")
        
    code = curr.code
    curr_symbol = curr.symbol
    # The row is about to go, so the queue entry carries the name Tally knows the currency by (its symbol).
    # Without it a delete that Tally did not answer could never be sent again.
    new_sq = SyncQueue(company_id=user.company_id, record_type="Currency", record_id=currency_id, action="Delete",
                       is_processed=False, snapshot_data={"tally_name": curr_symbol, "code": code})
    db.add(new_sq)
    # The currency is this company's own, and its exchange rates go with it
    from sqlalchemy import delete as sql_delete
    await db.execute(sql_delete(ExchangeRate).where(ExchangeRate.currency_id == currency_id))
    await db.delete(curr)
    await db.commit()
    
    logger.info(f"Currency {code} (ID: {currency_id}) deleted successfully. Added to SyncQueue (Delete).")
    
    # Try pushing to Tally in real-time
    logger.info(f"Triggering real-time Tally push for Currency {code} (Delete)...")
    await try_push_currency_realtime(currency_id, new_sq.sync_id, "Delete", db, deleted_symbol=curr_symbol, deleted_code=code)
    
    return {"message": "Currency deleted successfully"}

# --- TDS Sections ---

@router.get("/tds/sections", response_model=List[TdsSectionResponse])
async def get_tds_sections(
    user: User = Depends(require_permission("settings", "read")),
    db: AsyncSession = Depends(get_db)
):
    async def load():
        stmt = select(TdsSection).where(TdsSection.company_id == user.company_id)
        res = await db.execute(stmt)
        return as_schema_list(TdsSectionResponse, res.scalars().all())
    return await cached_master(user.company_id, master_cache.TDS_SECTIONS, load)

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
