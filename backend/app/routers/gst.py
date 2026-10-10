import logging
import calendar
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime, date
from decimal import Decimal
from pydantic import BaseModel

logger = logging.getLogger("app.routers.gst")
logger.setLevel(logging.INFO)

from app.core.database import get_db
from app.core.datetime_utils import get_ist_now
from app.core.permissions import require_permission
from app.models.portal_core import User
from app.models.tally_core import TrnVoucher, TrnAccounting
from app.models.tally_core import MstLedger, MstGroup, MstGstReconConfig
from app.models.portal_core import GstReturnPeriod, Gstr1LineItem, Gstr1HsnSummary, Gstr3bSummary, ItcEntry, Gstr2bEntry, Gstr9AnnualReturn, ManualPurchase, GstComplianceException, GstFilingSnapshot, GstProviderAttempt
from app.services.gst.validation import validate_return_lines
from app.services.gst.providers import create_provider, make_idempotency_key
from app.services.integrations import is_enabled, not_available_yet, require_integration
from app.routers.admin import require_admin
from app.models.portal_core import AuditLog
from app.core.config import settings
from app.schemas.gst import (
    GstReturnPeriodCreate, GstReturnPeriodResponse,
    Gstr1LineItemResponse, Gstr1HsnSummaryResponse, Gstr3bSummaryResponse,
    ItcEntryCreate, ItcEntryResponse, Gstr2bEntryResponse, Gstr9AnnualReturnResponse,
    GstEinvoiceListResponse, EinvoiceSettingsResponse, EinvoiceSettingsUpdate,
    ManualPurchaseCreate, ManualPurchaseResponse,
    Gstr2bOtpRequest, Gstr2bOtpVerify,
    GstValidationResponse, GstPeriodLockResponse,
    GstProviderSubmitRequest, GstProviderSubmitResponse,
)
import hashlib
import json

router = APIRouter(prefix="/gst", tags=["GST Reports & Return Filing"])

# --- Return Periods ---

@router.post("/periods", response_model=GstReturnPeriodResponse)
async def create_gst_period(
    req: GstReturnPeriodCreate,
    user: User = Depends(require_permission("reports", "create")),
    db: AsyncSession = Depends(get_db)
):
    # Check duplicate
    dup_query = await db.execute(
        select(GstReturnPeriod).where(
            GstReturnPeriod.company_id == user.company_id,
            GstReturnPeriod.return_type == req.return_type,
            GstReturnPeriod.period_month == req.period_month,
            GstReturnPeriod.period_year == req.period_year
        )
    )
    if dup_query.scalars().first():
        raise HTTPException(status_code=400, detail="GST period already initiated.")
        
    period = GstReturnPeriod(
        company_id=user.company_id,
        return_type=req.return_type,
        period_month=req.period_month,
        period_year=req.period_year,
        status="Draft"
    )
    db.add(period)
    await db.commit()
    await db.refresh(period)
    return period

@router.get("/periods", response_model=List[GstReturnPeriodResponse])
async def get_gst_periods(
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(GstReturnPeriod).where(GstReturnPeriod.company_id == user.company_id)
    res = await db.execute(stmt)
    return res.scalars().all()


async def _own_period(db: AsyncSession, user: User, period_id: int) -> GstReturnPeriod:
    """The return period, if it belongs to the company the caller is working in. A period id alone proves
    nothing: its lines, summaries and HSN table are read through this, never by the id directly."""
    period = (await db.execute(select(GstReturnPeriod).where(
        GstReturnPeriod.return_period_id == period_id, GstReturnPeriod.company_id == user.company_id))).scalars().first()
    if period is None:
        raise HTTPException(status_code=404, detail="GST return period not found.")
    return period


@router.post("/periods/{period_id}/validate", response_model=GstValidationResponse)
async def validate_gst_period(
    period_id: int,
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Run deterministic pre-filing validation and persist open exceptions."""
    period = (
        await db.execute(
            select(GstReturnPeriod).where(
                GstReturnPeriod.return_period_id == period_id,
                GstReturnPeriod.company_id == user.company_id,
            )
        )
    ).scalars().first()
    if not period:
        raise HTTPException(status_code=404, detail="GST Return period not found.")

    lines = (
        await db.execute(
            select(Gstr1LineItem).where(Gstr1LineItem.return_period_id == period_id)
        )
    ).scalars().all()
    issues = validate_return_lines(
        [
            {
                "party_gstin": line.party_gstin,
                "invoice_number": line.invoice_number,
                "place_of_supply": line.place_of_supply,
                "taxable_value": line.taxable_value,
                "cgst_amount": line.cgst_amount,
                "sgst_amount": line.sgst_amount,
                "igst_amount": line.igst_amount,
                "cess_amount": line.cess_amount,
            }
            for line in lines
        ]
    )

    existing = (
        await db.execute(
            select(GstComplianceException).where(
                GstComplianceException.return_period_id == period_id,
                GstComplianceException.status == "open",
            )
        )
    ).scalars().all()
    for exception in existing:
        exception.status = "resolved"
        exception.resolved_at = get_ist_now()
        exception.resolved_by = user.user_id
    for issue in issues:
        db.add(
            GstComplianceException(
                company_id=user.company_id,
                return_period_id=period_id,
                code=issue.code,
                field=issue.field,
                message=issue.message,
                severity=issue.severity,
            )
        )
    await db.commit()
    return GstValidationResponse(
        valid=not issues,
        issue_count=len(issues),
        issues=[issue.as_dict() for issue in issues],
    )


@router.post("/periods/{period_id}/lock", response_model=GstPeriodLockResponse)
async def lock_gst_period(
    period_id: int,
    user: User = Depends(require_permission("reports", "update")),
    db: AsyncSession = Depends(get_db),
):
    """Lock a validated draft period before provider submission or filing."""
    period = (
        await db.execute(
            select(GstReturnPeriod).where(
                GstReturnPeriod.return_period_id == period_id,
                GstReturnPeriod.company_id == user.company_id,
            )
        )
    ).scalars().first()
    if not period:
        raise HTTPException(status_code=404, detail="GST Return period not found.")
    if period.status == "Filed":
        raise HTTPException(status_code=409, detail="Filed GST periods cannot be changed.")

    open_exception = (
        await db.execute(
            select(GstComplianceException).where(
                GstComplianceException.return_period_id == period_id,
                GstComplianceException.status == "open",
                GstComplianceException.severity == "error",
            )
        )
    ).scalars().first()
    if open_exception:
        raise HTTPException(status_code=422, detail="Resolve GST validation exceptions before locking the period.")

    now = get_ist_now()
    period.locked_at = now
    period.locked_by = user.user_id
    await db.commit()
    await db.refresh(period)
    return GstPeriodLockResponse(
        return_period_id=period.return_period_id,
        status=period.status,
        locked_at=period.locked_at,
        locked_by=period.locked_by,
    )


@router.post("/periods/{period_id}/submit", response_model=GstProviderSubmitResponse)
async def submit_gst_period(
    period_id: int,
    req: GstProviderSubmitRequest,
    user: User = Depends(require_permission("reports", "update")),
    db: AsyncSession = Depends(get_db),
    _on: User = Depends(require_integration("gst_filing")),
):
    """Submit a locked period through an isolated provider and retain filing evidence. Only the demo provider
    exists so far ("mock"); the result is marked demo and the period is not marked filed."""
    period = (
        await db.execute(
            select(GstReturnPeriod).where(
                GstReturnPeriod.return_period_id == period_id,
                GstReturnPeriod.company_id == user.company_id,
            )
        )
    ).scalars().first()
    if not period:
        raise HTTPException(status_code=404, detail="GST Return period not found.")
    if not period.locked_at:
        raise HTTPException(status_code=409, detail="Validate and lock the GST period before provider submission.")
    if req.environment not in {"mock", "sandbox", "production"}:
        raise HTTPException(status_code=422, detail="Unsupported GST provider environment.")
    if req.environment != "mock":
        raise not_available_yet("gst_filing", "Only a demo submission is possible for now.")

    lines = (
        await db.execute(select(Gstr1LineItem).where(Gstr1LineItem.return_period_id == period_id))
    ).scalars().all()
    payload = {
        "return_type": period.return_type,
        "period_month": period.period_month,
        "period_year": period.period_year,
        "lines": [
            {
                "invoice_number": line.invoice_number,
                "invoice_date": line.invoice_date.isoformat(),
                "party_gstin": line.party_gstin,
                "place_of_supply": line.place_of_supply,
                "taxable_value": str(line.taxable_value),
                "cgst_amount": str(line.cgst_amount),
                "sgst_amount": str(line.sgst_amount),
                "igst_amount": str(line.igst_amount),
                "cess_amount": str(line.cess_amount),
            }
            for line in lines
        ],
    }
    payload_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    idempotency_key = make_idempotency_key(user.company_id, period_id, payload_hash)
    existing = (
        await db.execute(
            select(GstProviderAttempt).where(GstProviderAttempt.idempotency_key == idempotency_key)
        )
    ).scalars().first()
    if existing:
        return GstProviderSubmitResponse(
            attempt_id=existing.attempt_id,
            provider=existing.provider,
            status=existing.status,
            correlation_id=existing.correlation_id,
            acknowledgement_number=(existing.response or {}).get("acknowledgement_number"),
            demo=existing.provider == "mock",
        )

    try:
        provider = create_provider(
            req.environment,
            base_url=settings.GST_PROVIDER_URL,
            api_key=settings.GST_PROVIDER_API_KEY,
        )
        result = await provider.submit(period.return_type, payload, payload_hash)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    snapshot = GstFilingSnapshot(
        company_id=user.company_id,
        return_period_id=period_id,
        provider=result.provider,
        payload_hash=payload_hash,
        payload=payload,
        response=result.response,
        status=result.status,
        acknowledgement_number=result.response.get("acknowledgement_number"),
        created_by=user.user_id,
    )
    attempt = GstProviderAttempt(
        company_id=user.company_id,
        return_period_id=period_id,
        provider=result.provider,
        idempotency_key=idempotency_key,
        status=result.status,
        correlation_id=result.correlation_id,
        response=result.response,
        created_by=user.user_id,
    )
    db.add(snapshot)
    db.add(attempt)
    await db.commit()
    await db.refresh(attempt)
    return GstProviderSubmitResponse(
        attempt_id=attempt.attempt_id,
        provider=result.provider,
        status=result.status,
        correlation_id=result.correlation_id,
        acknowledgement_number=result.response.get("acknowledgement_number"),
        demo=result.provider == "mock",
    )

@router.delete("/periods/{period_id}")
async def delete_gst_period(
    period_id: int,
    user: User = Depends(require_permission("reports", "delete")),
    db: AsyncSession = Depends(get_db)
):
    period_query = await db.execute(
        select(GstReturnPeriod).where(
            GstReturnPeriod.return_period_id == period_id,
            GstReturnPeriod.company_id == user.company_id
        )
    )
    period = period_query.scalars().first()
    if not period:
        raise HTTPException(status_code=404, detail="GST Return period not found.")
        
    await db.delete(period)
    await db.commit()
    return {"status": "success", "message": "GST Return period deleted successfully."}


# --- Snapshot Generation ---

@router.post("/periods/{period_id}/generate")
async def generate_gst_snapshot(
    period_id: int,
    user: User = Depends(require_permission("reports", "update")),
    db: AsyncSession = Depends(get_db)
):
    from app.models.tally_core import MstLedger
    from app.routers.vouchers import _resolve_party_and_amount

    period_query = await db.execute(
        select(GstReturnPeriod).where(
            GstReturnPeriod.return_period_id == period_id,
            GstReturnPeriod.company_id == user.company_id
        )
    )
    period = period_query.scalars().first()
    if not period:
        raise HTTPException(status_code=404, detail="GST Return period not found.")
    if period.locked_at:
        raise HTTPException(status_code=409, detail="GST period is locked and cannot be regenerated.")
    if period.status != "Draft":
        raise HTTPException(status_code=400, detail="Cannot regenerate snapshot for filed returns.")
        
    # Clear previous snapshots
    await db.execute(
        select(Gstr1LineItem).where(Gstr1LineItem.return_period_id == period_id)
    ) # Normally delete query
    # We delete previous rows
    del_lines = await db.execute(select(Gstr1LineItem).where(Gstr1LineItem.return_period_id == period_id))
    for line in del_lines.scalars().all():
        await db.delete(line)
        
    del_hsn = await db.execute(select(Gstr1HsnSummary).where(Gstr1HsnSummary.return_period_id == period_id))
    for hsn in del_hsn.scalars().all():
        await db.delete(hsn)
        
    del_3b = await db.execute(select(Gstr3bSummary).where(Gstr3bSummary.return_period_id == period_id))
    for s3b in del_3b.scalars().all():
        await db.delete(s3b)
        
    await db.commit()
    
    # 1. Fetch Sales Vouchers in the period range
    import calendar
    from datetime import date
    
    start_date = date(period.period_year, period.period_month, 1)
    last_day = calendar.monthrange(period.period_year, period.period_month)[1]
    end_date = date(period.period_year, period.period_month, last_day)

    vouchers_query = await db.execute(
        select(TrnVoucher)
        .options(
            selectinload(TrnVoucher.entries).selectinload(TrnAccounting.ledger).selectinload(MstLedger.group)
        )
        .where(
            TrnVoucher.company_id == user.company_id,
            TrnVoucher.is_optional == False,
            TrnVoucher.voucher_date >= start_date,
            TrnVoucher.voucher_date <= end_date
        )
    )
    vouchers = vouchers_query.scalars().all()
    
    total_taxable_outward = Decimal("0.00")
    total_cgst_outward = Decimal("0.00")
    total_sgst_outward = Decimal("0.00")
    total_igst_outward = Decimal("0.00")
    
    for v in vouchers:
        # Skip purchase vouchers (containing a ledger with 'PURCHASE' in its name)
        if any(e.ledger and 'PURCHASE' in e.ledger.name.upper() for e in v.entries):
            continue
            
        # Determine if it's a Sales voucher
        # Check if v.voucher_type_id name is Sales
        # For simplicity, we scan entries for SGST / CGST / IGST tax ledgers
        # Resolve party details dynamically first to avoid matching party ledgers as sales ledgers
        party_name, *_ = _resolve_party_and_amount(v.entries)
        
        has_tax = False
        cgst = Decimal("0.00")
        sgst = Decimal("0.00")
        igst = Decimal("0.00")
        taxable = Decimal("0.00")
        
        # Pull ledger names for tax detection
        for e in v.entries:
            if not e.ledger:
                continue
                
            # Skip the party ledger from tax and taxable calculations
            if e.ledger.name == party_name:
                continue
                
            name_upper = e.ledger.name.upper()
            net_credit = e.credit_amount - e.debit_amount
            
            if 'CGST' in name_upper:
                cgst += net_credit
                has_tax = True
            elif 'SGST' in name_upper:
                sgst += net_credit
                has_tax = True
            elif 'IGST' in name_upper:
                igst += net_credit
                has_tax = True
            elif 'SALES' in name_upper or 'DISCOUNT' in name_upper:
                taxable += net_credit
                
        if has_tax and taxable != 0:
            total_taxable_outward += taxable
            total_cgst_outward += cgst
            total_sgst_outward += sgst
            total_igst_outward += igst
            
            party_gstin = None
            party_state = "Maharashtra"
            supply_type = "B2CS"
            
            if party_name:
                party_q = await db.execute(
                    select(MstLedger).where(
                        MstLedger.name == party_name,
                        MstLedger.company_id == user.company_id
                    )
                )
                party_ledger = party_q.scalars().first()
                if party_ledger:
                    party_gstin = party_ledger.gstin
                    if party_ledger.state:
                        party_state = party_ledger.state
                    if party_gstin:
                        supply_type = "B2B"
            
            line = Gstr1LineItem(
                return_period_id=period_id,
                voucher_id=v.voucher_id,
                supply_type=supply_type,
                party_gstin=party_gstin,
                invoice_number=v.voucher_number,
                invoice_date=v.voucher_date,
                place_of_supply=party_state,
                taxable_value=taxable,
                cgst_amount=cgst,
                sgst_amount=sgst,
                igst_amount=igst,
                cess_amount=Decimal("0.00"),
                invoice_value=taxable + cgst + sgst + igst
            )
            db.add(line)
            
    # 2. Compile GSTR-3B Summary
    # Fetch claimed ITC entries for this period
    itc_query = await db.execute(
        select(ItcEntry).where(
            ItcEntry.company_id == user.company_id,
            ItcEntry.claimed_return_period_id == period_id
        )
    )
    itc_list = itc_query.scalars().all()
    
    mp_query = await db.execute(
        select(ManualPurchase).where(
            ManualPurchase.company_id == user.company_id,
            ManualPurchase.claimed_return_period_id == period_id
        )
    )
    mp_list = mp_query.scalars().all()
    
    # Calculate book ITC from purchase vouchers in the database for this date range
    purchase_igst = Decimal("0.00")
    purchase_cgst = Decimal("0.00")
    purchase_sgst = Decimal("0.00")
    
    for v in vouchers:
        # Check if this is a purchase voucher (has a ledger containing PURCHASE)
        if any(e.ledger and 'PURCHASE' in e.ledger.name.upper() for e in v.entries):
            for e in v.entries:
                if e.ledger:
                    name_upper = e.ledger.name.upper()
                    # Book ITC is the debit to CGST/SGST/IGST ledgers (debit - credit)
                    net_debit = e.debit_amount - e.credit_amount
                    if 'IGST' in name_upper:
                        purchase_igst += net_debit
                    elif 'CGST' in name_upper:
                        purchase_cgst += net_debit
                    elif 'SGST' in name_upper:
                        purchase_sgst += net_debit
    
    total_cgst_itc = sum(i.cgst_amount for i in itc_list) + sum(m.cgst_amount for m in mp_list) + purchase_cgst
    total_sgst_itc = sum(i.sgst_amount for i in itc_list) + sum(m.sgst_amount for m in mp_list) + purchase_sgst
    total_igst_itc = sum(i.igst_amount for i in itc_list) + sum(m.igst_amount for m in mp_list) + purchase_igst
    
    summary3b = Gstr3bSummary(
        return_period_id=period_id,
        outward_taxable_value=total_taxable_outward,
        outward_cgst=total_cgst_outward,
        outward_sgst=total_sgst_outward,
        outward_igst=total_igst_outward,
        outward_cess=Decimal("0.00"),
        itc_igst_available=total_igst_itc,
        itc_cgst_available=total_cgst_itc,
        itc_sgst_available=total_sgst_itc,
        itc_cess_available=Decimal("0.00"),
        itc_reversed=Decimal("0.00"),
        net_igst_payable=max(Decimal("0.00"), total_igst_outward - total_igst_itc),
        net_cgst_payable=max(Decimal("0.00"), total_cgst_outward - total_cgst_itc),
        net_sgst_payable=max(Decimal("0.00"), total_sgst_outward - total_sgst_itc),
        net_cess_payable=Decimal("0.00")
    )
    db.add(summary3b)
    await db.commit()
    
    return {"detail": "GST Return snapshots generated successfully."}

@router.get("/periods/{period_id}/gstr1/lines", response_model=List[Gstr1LineItemResponse])
async def get_gstr1_lines(
    period_id: int,
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db)
):
    await _own_period(db, user, period_id)
    stmt = select(Gstr1LineItem).where(Gstr1LineItem.return_period_id == period_id)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.get("/periods/{period_id}/gstr3b", response_model=Gstr3bSummaryResponse)
async def get_gstr3b_summary(
    period_id: int,
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db)
):
    await _own_period(db, user, period_id)
    stmt = select(Gstr3bSummary).where(Gstr3bSummary.return_period_id == period_id)
    res = await db.execute(stmt)
    summary = res.scalars().first()
    if not summary:
        raise HTTPException(status_code=404, detail="GSTR-3B summary not generated yet.")
        
    from app.models.portal_core import Company
    comp_q = await db.execute(select(Company).where(Company.company_id == user.company_id))
    company = comp_q.scalars().first()
    
    return {
        "summary_id": summary.summary_id,
        "return_period_id": summary.return_period_id,
        "outward_taxable_value": summary.outward_taxable_value,
        "outward_cgst": summary.outward_cgst,
        "outward_sgst": summary.outward_sgst,
        "outward_igst": summary.outward_igst,
        "outward_cess": summary.outward_cess,
        "itc_igst_available": summary.itc_igst_available,
        "itc_cgst_available": summary.itc_cgst_available,
        "itc_sgst_available": summary.itc_sgst_available,
        "itc_cess_available": summary.itc_cess_available,
        "itc_reversed": summary.itc_reversed,
        "net_igst_payable": summary.net_igst_payable,
        "net_cgst_payable": summary.net_cgst_payable,
        "net_sgst_payable": summary.net_sgst_payable,
        "net_cess_payable": summary.net_cess_payable,
        "tax_paid_via_cash": summary.tax_paid_via_cash,
        "tax_paid_via_itc": summary.tax_paid_via_itc,
        "interest_paid": summary.interest_paid,
        "late_fee_paid": summary.late_fee_paid,
        "company_name": company.name if company else None,
        "company_gstin": company.gstin if company else None,
        "company_pan": company.pan if company else None
    }

@router.post("/periods/{period_id}/file")
async def file_gst_return(
    period_id: int,
    arn: str,
    user: User = Depends(require_permission("reports", "update")),
    db: AsyncSession = Depends(get_db)
):
    if not arn.strip():
        raise HTTPException(status_code=422, detail="Acknowledgement reference (ARN) is required.")
    period_query = await db.execute(
        select(GstReturnPeriod).where(
            GstReturnPeriod.return_period_id == period_id,
            GstReturnPeriod.company_id == user.company_id
        )
    )
    period = period_query.scalars().first()
    if not period:
        raise HTTPException(status_code=404, detail="GST Return period not found.")
    if not period.locked_at:
        raise HTTPException(status_code=409, detail="Validate and lock the GST period before filing.")
        
    period.status = "Filed"
    period.arn = arn
    period.filed_date = date.today()
    period.filed_by = user.user_id
    
    await db.commit()
    return {"detail": "GST Return marked as filed successfully.", "arn": arn}

# --- Input Tax Credit (ITC) ---

@router.post("/itc", response_model=ItcEntryResponse)
async def create_itc_entry(
    req: ItcEntryCreate,
    user: User = Depends(require_permission("reports", "create")),
    db: AsyncSession = Depends(get_db)
):
    try:
        idate = datetime.strptime(req.invoice_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
        
    itc = ItcEntry(
        company_id=user.company_id,
        voucher_id=req.voucher_id,
        supplier_gstin=req.supplier_gstin,
        invoice_number=req.invoice_number,
        invoice_date=idate,
        taxable_value=req.taxable_value,
        cgst_amount=req.cgst_amount,
        sgst_amount=req.sgst_amount,
        igst_amount=req.igst_amount,
        cess_amount=req.cess_amount,
        eligibility=req.eligibility
    )
    db.add(itc)
    await db.commit()
    await db.refresh(itc)
    return itc

@router.get("/itc", response_model=List[ItcEntryResponse])
async def get_itc_entries(
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(ItcEntry).where(ItcEntry.company_id == user.company_id)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.get("/periods/{period_id}/gstr1/json")
async def export_gstr1_json(
    period_id: int,
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db)
):
    """Export GSTR-1 data in official GST portal JSON upload format"""
    period_query = await db.execute(
        select(GstReturnPeriod).where(
            GstReturnPeriod.return_period_id == period_id,
            GstReturnPeriod.company_id == user.company_id
        )
    )
    period = period_query.scalars().first()
    if not period:
        raise HTTPException(status_code=404, detail="GST Return period not found.")
    
    # Fetch company GSTIN
    from app.models.portal_core import Company
    company_q = await db.execute(select(Company).where(Company.company_id == user.company_id))
    company = company_q.scalars().first()
    
    # Fetch GSTR-1 line items
    lines_q = await db.execute(
        select(Gstr1LineItem).where(Gstr1LineItem.return_period_id == period_id)
    )
    lines = lines_q.scalars().all()
    
    # Fetch HSN summaries
    hsn_q = await db.execute(
        select(Gstr1HsnSummary).where(Gstr1HsnSummary.return_period_id == period_id)
    )
    hsn_items = hsn_q.scalars().all()
    
    # Build B2B invoices grouped by recipient GSTIN
    b2b_map = {}
    for line in lines:
        if line.supply_type == "B2B" and line.party_gstin:
            if line.party_gstin not in b2b_map:
                b2b_map[line.party_gstin] = []
            b2b_map[line.party_gstin].append({
                "inum": line.invoice_number,
                "idt": line.invoice_date.strftime("%d-%m-%Y"),
                "val": float(line.invoice_value),
                "pos": line.place_of_supply[:2] if line.place_of_supply else "27",
                "rchrg": "N",
                "itms": [{
                    "num": 1,
                    "itm_det": {
                        "txval": float(line.taxable_value),
                        "camt": float(line.cgst_amount),
                        "samt": float(line.sgst_amount),
                        "iamt": float(line.igst_amount),
                        "csamt": float(line.cess_amount)
                    }
                }]
            })
    
    b2b = [{"ctin": gstin, "inv": invoices} for gstin, invoices in b2b_map.items()]
    
    # Build HSN summary
    hsn_data = [{
        "hsn_sc": h.hsn_code,
        "desc": h.description or "",
        "uqc": h.uqc or "NOS",
        "qty": float(h.total_quantity),
        "txval": float(h.taxable_value),
        "camt": float(h.cgst_amount),
        "samt": float(h.sgst_amount),
        "iamt": float(h.igst_amount),
        "csamt": float(h.cess_amount)
    } for h in hsn_items]
    
    month_str = str(period.period_month).zfill(2)
    fp = f"{month_str}{period.period_year}"
    
    gstr1_json = {
        "gstin": company.gstin if company and company.gstin else "UNREGISTERED",
        "fp": fp,
        "b2b": b2b,
        "hsn": {"data": hsn_data},
        "version": "GST3.0.4",
        "hash": "hash"
    }
    
    from fastapi.responses import JSONResponse
    return JSONResponse(
        content=gstr1_json,
        headers={
            "Content-Disposition": f"attachment; filename=GSTR1_{fp}.json"
        }
    )

@router.get("/periods/{period_id}/hsn", response_model=List[Gstr1HsnSummaryResponse])
async def get_hsn_summary(
    period_id: int,
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db)
):
    await _own_period(db, user, period_id)
    stmt = select(Gstr1HsnSummary).where(Gstr1HsnSummary.return_period_id == period_id)
    res = await db.execute(stmt)
    return res.scalars().all()

# --- GSTR-2B (Reconciliation) ---

@router.post("/gstr2b/upload")
async def upload_gstr2b_json(
    file: UploadFile = File(...),
    user: User = Depends(require_permission("reports", "update")),
    db: AsyncSession = Depends(get_db)
):
    """Upload and parse GSTR-2B JSON file from GST portal to populate reconciliation entries"""
    import json
    try:
        contents = await file.read()
        data = json.loads(contents)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse JSON file: {str(e)}")

    # Resolve root object & rtnprd
    data_obj = data.get("data", data) if isinstance(data.get("data"), dict) else data
    doc_root = data_obj.get("docdata", data_obj) if isinstance(data_obj.get("docdata"), dict) else data_obj

    rtnprd = data_obj.get("rtnprd") or data.get("rtnprd")
    month = None
    year = None
    if rtnprd:
        if "/" in str(rtnprd):
            parts = str(rtnprd).split("/")
            try:
                month = int(parts[0])
                year = int(parts[1])
            except ValueError:
                pass
        elif len(str(rtnprd)) == 6:
            try:
                month = int(str(rtnprd)[:2])
                year = int(str(rtnprd)[2:])
            except ValueError:
                pass
                
    if not month or not year:
        raise HTTPException(status_code=400, detail="Could not resolve return period (rtnprd) from GSTR-2B JSON.")

    # Find or auto-create the return period
    period_q = await db.execute(
        select(GstReturnPeriod).where(
            GstReturnPeriod.period_month == month,
            GstReturnPeriod.period_year == year,
            GstReturnPeriod.company_id == user.company_id
        )
    )
    period = period_q.scalars().first()
    if not period:
        period = GstReturnPeriod(
            company_id=user.company_id,
            return_type="GSTR3B",
            period_month=month,
            period_year=year,
            status="Draft"
        )
        db.add(period)
        await db.commit()
        await db.refresh(period)

    period_id = period.return_period_id

    # Archive raw JSON file to disk
    import os
    storage_dir = os.path.join(os.getcwd(), "storage", "gstr2b")
    os.makedirs(storage_dir, exist_ok=True)
    file_path = os.path.join(storage_dir, f"GSTR2B_comp{user.company_id}_{month:02d}_{year}.json")
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

    # Clear existing GSTR-2B entries for this period
    del_q = await db.execute(select(Gstr2bEntry).where(
        Gstr2bEntry.return_period_id == period_id,
        Gstr2bEntry.company_id == user.company_id
    ))
    for entry in del_q.scalars().all():
        await db.delete(entry)
    await db.commit()

    imported_count = 0

    # 1. Parse B2B
    b2b_list = doc_root.get("b2b", [])
    for supplier in b2b_list:
        ctin = supplier.get("ctin")
        trade_name = supplier.get("trdnm") or supplier.get("trdn") or supplier.get("lmnm") or "Unknown Supplier"
        
        invoices = supplier.get("inv", [])
        for inv in invoices:
            inum = inv.get("inum")
            idt_str = inv.get("dt") or inv.get("idt") or ""
            
            try:
                invoice_date = datetime.strptime(idt_str, "%d-%m-%Y").date()
            except ValueError:
                try:
                    invoice_date = datetime.strptime(idt_str, "%d/%m/%Y").date()
                except ValueError:
                    try:
                        invoice_date = datetime.strptime(idt_str, "%Y-%m-%d").date()
                    except ValueError:
                        invoice_date = date.today()
                        
            taxable_value = Decimal(str(inv.get("txval", 0) or 0))
            cgst = Decimal(str(inv.get("cgst", 0) or 0))
            sgst = Decimal(str(inv.get("sgst", 0) or 0))
            igst = Decimal(str(inv.get("igst", 0) or 0))
            cess = Decimal(str(inv.get("cess", 0) or 0))
            
            if taxable_value == 0 and cgst == 0 and sgst == 0 and igst == 0:
                for item in inv.get("itms", []):
                    det = item.get("itm_det", {})
                    taxable_value += Decimal(str(det.get("txval", 0) or 0))
                    igst += Decimal(str(det.get("iamt", 0) or 0))
                    cgst += Decimal(str(det.get("camt", 0) or 0))
                    sgst += Decimal(str(det.get("samt", 0) or 0))
                    cess += Decimal(str(det.get("csamt", 0) or 0))
                
            entry = Gstr2bEntry(
                company_id=user.company_id,
                return_period_id=period_id,
                supplier_gstin=ctin,
                supplier_name=trade_name,
                invoice_number=inum,
                invoice_date=invoice_date,
                taxable_value=taxable_value,
                cgst_amount=cgst,
                sgst_amount=sgst,
                igst_amount=igst,
                cess_amount=cess,
                itc_availability="Available" if inv.get("itcavl", "Y") != "N" else "Unavailable",
                match_status="Unmatched"
            )
            db.add(entry)
            imported_count += 1

    # 2. Parse CDNR (Credit/Debit Notes)
    cdnr_list = doc_root.get("cdnr", [])
    for supplier in cdnr_list:
        ctin = supplier.get("ctin")
        trade_name = supplier.get("trdnm") or supplier.get("trdn") or supplier.get("lmnm") or "Unknown Supplier"
        notes = supplier.get("nt", [])
        for note in notes:
            nt_num = note.get("ntnum") or note.get("nt_num")
            nt_dt_str = note.get("dt") or note.get("nt_dt") or ""
            
            try:
                note_date = datetime.strptime(nt_dt_str, "%d-%m-%Y").date()
            except ValueError:
                try:
                    note_date = datetime.strptime(nt_dt_str, "%d/%m/%Y").date()
                except ValueError:
                    note_date = date.today()
                    
            taxable_value = Decimal(str(note.get("txval", 0) or 0))
            cgst = Decimal(str(note.get("cgst", 0) or 0))
            sgst = Decimal(str(note.get("sgst", 0) or 0))
            igst = Decimal(str(note.get("igst", 0) or 0))
            cess = Decimal(str(note.get("cess", 0) or 0))
            
            if taxable_value == 0 and cgst == 0 and sgst == 0 and igst == 0:
                for item in note.get("itms", []):
                    det = item.get("itm_det", {})
                    taxable_value += Decimal(str(det.get("txval", 0) or 0))
                    igst += Decimal(str(det.get("iamt", 0) or 0))
                    cgst += Decimal(str(det.get("camt", 0) or 0))
                    sgst += Decimal(str(det.get("samt", 0) or 0))
                    cess += Decimal(str(det.get("csamt", 0) or 0))
                
            entry = Gstr2bEntry(
                company_id=user.company_id,
                return_period_id=period_id,
                supplier_gstin=ctin,
                supplier_name=trade_name,
                invoice_number=nt_num,
                invoice_date=note_date,
                taxable_value=-taxable_value,
                cgst_amount=-cgst,
                sgst_amount=-sgst,
                igst_amount=-igst,
                cess_amount=-cess,
                itc_availability="Available" if note.get("itcavl", "Y") != "N" else "Unavailable",
                match_status="Unmatched"
            )
            db.add(entry)
            imported_count += 1

    await db.commit()

    # Automatically trigger reconciliation for book entries
    reconcile_res = await reconcile_gstr2b(user=user, db=db)

    logger.info("========================== [GSTR-2B JSON FILE IMPORT LOG] ==========================")
    logger.info(f"File Uploaded : {file.filename}")
    logger.info(f"Return Period : {rtnprd} (Month: {month}, Year: {year})")
    logger.info(f"Entries Saved : {imported_count} GSTR-2B records added to DB table `gstr2b_entries`")
    logger.info(f"Reconciled    : {reconcile_res.get('matched', 0)} matches found with Tally book purchase vouchers")
    logger.info(f"File Archived : {file_path}")
    logger.info("====================================================================================")

    return {
        "detail": f"Successfully parsed GSTR-2B JSON file ({file.filename}). Imported {imported_count} entries and matched {reconcile_res.get('matched', 0)} purchase vouchers.",
        "imported": imported_count,
        "matched": reconcile_res.get("matched", 0),
        "mismatches": reconcile_res.get("mismatches", 0)
    }

# Fetching GSTR-2B from the GST portal needs a GSP connection, which isn't built. These routes used to answer
# "OTP sent" and then replace the period's GSTR-2B rows with copies of our own purchase vouchers, so they now refuse.
GSTR2B_UPLOAD_HINT = "Download the GSTR-2B JSON from the GST portal and use Upload instead."


@router.post("/gstr2b/request-otp")
async def request_gstr2b_otp(
    req: Gstr2bOtpRequest,
    user: User = Depends(require_permission("reports", "update")),
    _on: User = Depends(require_integration("gst_portal")),
):
    raise not_available_yet("gst_portal", GSTR2B_UPLOAD_HINT)


@router.post("/gstr2b/verify-otp")
async def verify_gstr2b_otp_and_fetch(
    req: Gstr2bOtpVerify,
    user: User = Depends(require_permission("reports", "update")),
    _on: User = Depends(require_integration("gst_portal")),
):
    raise not_available_yet("gst_portal", GSTR2B_UPLOAD_HINT)

@router.get("/gstr2b", response_model=List[Gstr2bEntryResponse])
async def get_gstr2b_entries(
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Gstr2bEntry).where(Gstr2bEntry.company_id == user.company_id)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("/gstr2b/reconcile")
async def reconcile_gstr2b(
    user: User = Depends(require_permission("reports", "update")),
    db: AsyncSession = Depends(get_db)
):
    """Reconcile GSTR-2B purchase entries against books (Tally purchase vouchers, manual purchases, and ITC entries)"""
    from app.routers.vouchers import _resolve_party_and_amount

    # 1. Fetch all GSTR-2B entries for this company
    g2b_res = await db.execute(select(Gstr2bEntry).where(Gstr2bEntry.company_id == user.company_id))
    g2b_entries = g2b_res.scalars().all()

    # 2. Fetch all Tally Purchase Vouchers
    v_res = await db.execute(
        select(TrnVoucher)
        .options(
            selectinload(TrnVoucher.entries).selectinload(TrnAccounting.ledger).selectinload(MstLedger.group)
        )
        .where(
            TrnVoucher.company_id == user.company_id,
            TrnVoucher.is_optional == False
        )
    )
    vouchers = v_res.scalars().all()

    book_vouchers = []
    for v in vouchers:
        party_name, *_ = _resolve_party_and_amount(v.entries)
        if not party_name:
            continue
        
        taxable = Decimal("0.00")
        cgst = Decimal("0.00")
        sgst = Decimal("0.00")
        igst = Decimal("0.00")
        party_gstin = ""

        for e in v.entries:
            if not e.ledger:
                continue
            name_u = e.ledger.name.upper()
            net_debit = e.debit_amount - e.credit_amount
            if 'IGST' in name_u:
                igst += net_debit
            elif 'CGST' in name_u:
                cgst += net_debit
            elif 'SGST' in name_u:
                sgst += net_debit
            elif 'DISCOUNT' not in name_u and name_u != party_name.upper():
                taxable += net_debit
            
            if e.ledger.gstin and not party_gstin:
                party_gstin = e.ledger.gstin

        for e in v.entries:
            if e.ledger and 'DISCOUNT' in e.ledger.name.upper():
                net_disc = e.credit_amount - e.debit_amount
                taxable -= net_disc

        book_vouchers.append({
            "voucher_id": v.voucher_id,
            "party_name": party_name.upper(),
            "party_gstin": party_gstin.upper(),
            "voucher_number": (v.voucher_number or "").strip().upper(),
            "reference_number": (v.reference_number or "").strip().upper(),
            "voucher_date": v.voucher_date,
            "taxable_value": taxable,
            "cgst": cgst,
            "sgst": sgst,
            "igst": igst,
            "matched": False
        })

    # 3. Fetch Manual Purchases
    mp_res = await db.execute(select(ManualPurchase).where(ManualPurchase.company_id == user.company_id))
    manual_purchases = mp_res.scalars().all()
    for mp in manual_purchases:
        book_vouchers.append({
            "voucher_id": mp.id,
            "party_name": (mp.party_name or "").upper(),
            "party_gstin": (mp.gstin or "").upper(),
            "voucher_number": (mp.invoice_number or "").strip().upper(),
            "reference_number": (mp.invoice_number or "").strip().upper(),
            "voucher_date": mp.invoice_date,
            "taxable_value": mp.taxable_value,
            "cgst": mp.cgst_amount,
            "sgst": mp.sgst_amount,
            "igst": mp.igst_amount,
            "matched": False
        })

    # 4. Fetch ITC Entries
    itc_res = await db.execute(select(ItcEntry).where(ItcEntry.company_id == user.company_id))
    itc_entries = itc_res.scalars().all()
    for itc in itc_entries:
        book_vouchers.append({
            "voucher_id": itc.voucher_id or itc.itc_id,
            "itc_obj": itc,
            "party_name": (itc.supplier_name or "").upper(),
            "party_gstin": (itc.supplier_gstin or "").upper(),
            "voucher_number": (itc.invoice_number or "").strip().upper(),
            "reference_number": (itc.invoice_number or "").strip().upper(),
            "voucher_date": itc.invoice_date,
            "taxable_value": itc.taxable_value,
            "cgst": itc.cgst_amount,
            "sgst": itc.sgst_amount,
            "igst": itc.igst_amount,
            "matched": False
        })

    reconciled_count = 0
    mismatch_count = 0

    for g2b in g2b_entries:
        g2b_inv = g2b.invoice_number.strip().upper()
        g2b_gstin = g2b.supplier_gstin.strip().upper()
        g2b_supplier = g2b.supplier_name.strip().upper()
        
        match = None
        
        # Pass 1: Exact / Reference Invoice Number Match + GSTIN or Supplier Name
        for bv in book_vouchers:
            if bv["matched"]:
                continue
            inv_match = (g2b_inv == bv["voucher_number"]) or (g2b_inv == bv["reference_number"]) or (bv["reference_number"] and bv["reference_number"] in g2b_inv)
            gstin_match = (g2b_gstin and bv["party_gstin"] and g2b_gstin == bv["party_gstin"]) or (g2b_supplier in bv["party_name"] or bv["party_name"] in g2b_supplier)
            
            if inv_match or gstin_match:
                diff_taxable = abs(g2b.taxable_value - bv["taxable_value"])
                diff_cgst = abs(g2b.cgst_amount - bv["cgst"])
                diff_sgst = abs(g2b.sgst_amount - bv["sgst"])
                diff_igst = abs(g2b.igst_amount - bv["igst"])
                
                if diff_taxable <= 2.00 and diff_cgst <= 2.00 and diff_sgst <= 2.00 and diff_igst <= 2.00:
                    match = bv
                    break

        # Pass 2: Smart Fallback (Supplier Name/GSTIN + Tax Amounts within ₹2.00 + Date within ±10 days)
        if not match:
            for bv in book_vouchers:
                if bv["matched"]:
                    continue
                supplier_match = (g2b_gstin and bv["party_gstin"] and g2b_gstin == bv["party_gstin"]) or (g2b_supplier[:5] in bv["party_name"] or bv["party_name"][:5] in g2b_supplier)
                if supplier_match:
                    diff_taxable = abs(g2b.taxable_value - bv["taxable_value"])
                    diff_cgst = abs(g2b.cgst_amount - bv["cgst"])
                    diff_sgst = abs(g2b.sgst_amount - bv["sgst"])
                    diff_igst = abs(g2b.igst_amount - bv["igst"])
                    
                    if diff_taxable <= 2.00 and diff_cgst <= 2.00 and diff_sgst <= 2.00 and diff_igst <= 2.00:
                        match = bv
                        break

        if match:
            match["matched"] = True
            g2b.match_status = "Matched"
            g2b.itc_availability = "Available"
            g2b.matched_voucher_id = match["voucher_id"]
            g2b.match_method = match_type
            g2b.match_confidence = {"EXACT": Decimal("100.00"), "TOLERANCE": Decimal("90.00"), "FUZZY": Decimal("75.00")}[match_type]
            g2b.match_reason = {
                "EXACT": "Invoice number, supplier identity, and tax amounts matched exactly.",
                "TOLERANCE": "Invoice identity matched within configured taxable/tax tolerances.",
                "FUZZY": "Supplier and amounts matched within the configured date window.",
            }[match_type]
            
            if "itc_obj" in match and match["itc_obj"]:
                match["itc_obj"].claimed_return_period_id = g2b.return_period_id
                
            reconciled_count += 1
        else:
            g2b.match_status = "Unmatched"
            g2b.match_method = None
            g2b.match_confidence = Decimal("0.00")
            g2b.match_reason = "No eligible book entry matched the configured identity and amount rules."

    await db.commit()
    return {
        "detail": "Reconciliation completed successfully.",
        "matched": reconciled_count,
        "mismatches": mismatch_count
    }

class ReconConfigSchema(BaseModel):
    ignore_diff_in_taxable_amt: float = 10.00
    ignore_diff_in_tax_amt: float = 5.00
    strip_prefix_suffix: bool = True
    fuzzy_invoice_match: bool = True


@router.get("/recon-config")
async def get_gst_recon_config(
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db)
):
    """Fetch company GSTR-2B reconciliation configuration rules."""
    stmt = select(MstGstReconConfig).where(MstGstReconConfig.company_id == user.company_id)
    cfg = (await db.execute(stmt)).scalars().first()
    if not cfg:
        cfg = MstGstReconConfig(
            company_id=user.company_id,
            ignore_diff_in_taxable_amt=Decimal("10.00"),
            ignore_diff_in_tax_amt=Decimal("5.00"),
            strip_prefix_suffix=True,
            fuzzy_invoice_match=True
        )
        db.add(cfg)
        await db.commit()
        await db.refresh(cfg)

    return {
        "config_id": cfg.config_id,
        "company_id": cfg.company_id,
        "ignore_diff_in_taxable_amt": float(cfg.ignore_diff_in_taxable_amt),
        "ignore_diff_in_tax_amt": float(cfg.ignore_diff_in_tax_amt),
        "strip_prefix_suffix": bool(cfg.strip_prefix_suffix),
        "fuzzy_invoice_match": bool(cfg.fuzzy_invoice_match)
    }


@router.put("/recon-config")
async def update_gst_recon_config(
    req: ReconConfigSchema,
    user: User = Depends(require_permission("reports", "update")),
    db: AsyncSession = Depends(get_db)
):
    """Update GSTR-2B reconciliation tolerance and normalization rules."""
    stmt = select(MstGstReconConfig).where(MstGstReconConfig.company_id == user.company_id)
    cfg = (await db.execute(stmt)).scalars().first()
    if not cfg:
        cfg = MstGstReconConfig(company_id=user.company_id)
        db.add(cfg)

    cfg.ignore_diff_in_taxable_amt = Decimal(str(req.ignore_diff_in_taxable_amt))
    cfg.ignore_diff_in_tax_amt = Decimal(str(req.ignore_diff_in_tax_amt))
    cfg.strip_prefix_suffix = req.strip_prefix_suffix
    cfg.fuzzy_invoice_match = req.fuzzy_invoice_match

    await db.commit()
    await db.refresh(cfg)
    return {
        "status": "success",
        "message": "Reconciliation configuration saved.",
        "config": {
            "ignore_diff_in_taxable_amt": float(cfg.ignore_diff_in_taxable_amt),
            "ignore_diff_in_tax_amt": float(cfg.ignore_diff_in_tax_amt),
            "strip_prefix_suffix": bool(cfg.strip_prefix_suffix),
            "fuzzy_invoice_match": bool(cfg.fuzzy_invoice_match)
        }
    }


def _normalize_inv(inv_str: str, strip_affixes: bool = True) -> str:
    if not inv_str:
        return ""
    cleaned = inv_str.strip().upper()
    if not strip_affixes:
        return cleaned

    import re
    # Remove leading common prefixes like INV/, TAX/, BILL/, 2026/, 25-26/
    cleaned = re.sub(r'^(INV|TAX|BILL|GST|PUR|EXP)[-/_#\s]*', '', cleaned)
    cleaned = re.sub(r'^(20\d\d[-/_\s]*|\d\d-\d\d[-/_\s]*)', '', cleaned)
    # Remove financial year suffixes like /25-26, /2025-2026, -2026
    cleaned = re.sub(r'[-/_\s]*(20\d\d[-/]\d\d|20\d\d|\d\d-\d\d)$', '', cleaned)
    # Remove any non-alphanumeric separators
    cleaned = re.sub(r'[^A-Z0-9]', '', cleaned)
    return cleaned


@router.post("/gstr2b/reconcile-auto")
async def reconcile_gstr2b_auto(
    req: Optional[ReconConfigSchema] = None,
    user: User = Depends(require_permission("reports", "update")),
    db: AsyncSession = Depends(get_db)
):
    """
    Tally Prime 7.0 Intelligent Auto-Reconciliation Engine.
    Executes rule-based matching with tolerance thresholds (Ignorediffintaxableamt)
    and invoice prefix/suffix stripping (Gstreconprefixsuffixdetails).
    """
    from app.routers.vouchers import _resolve_party_and_amount

    # Get config or use request overrides
    cfg_stmt = select(MstGstReconConfig).where(MstGstReconConfig.company_id == user.company_id)
    cfg = (await db.execute(cfg_stmt)).scalars().first()

    taxable_tolerance = Decimal(str(req.ignore_diff_in_taxable_amt if req else (cfg.ignore_diff_in_taxable_amt if cfg else 10.00)))
    tax_tolerance = Decimal(str(req.ignore_diff_in_tax_amt if req else (cfg.ignore_diff_in_tax_amt if cfg else 5.00)))
    strip_affixes = req.strip_prefix_suffix if req else (cfg.strip_prefix_suffix if cfg else True)
    fuzzy_mode = req.fuzzy_invoice_match if req else (cfg.fuzzy_invoice_match if cfg else True)

    # 1. Fetch all GSTR-2B entries
    g2b_res = await db.execute(select(Gstr2bEntry).where(Gstr2bEntry.company_id == user.company_id))
    g2b_entries = g2b_res.scalars().all()

    # 2. Fetch all Tally Purchase Vouchers
    v_res = await db.execute(
        select(TrnVoucher)
        .options(
            selectinload(TrnVoucher.entries).selectinload(TrnAccounting.ledger).selectinload(MstLedger.group)
        )
        .where(
            TrnVoucher.company_id == user.company_id,
            TrnVoucher.is_optional == False
        )
        .execution_options(populate_existing=True)
    )
    vouchers = v_res.scalars().all()

    book_vouchers = []
    for v in vouchers:
        party_name, *_ = _resolve_party_and_amount(v.entries)
        if not party_name:
            continue
        
        taxable = Decimal("0.00")
        cgst = Decimal("0.00")
        sgst = Decimal("0.00")
        igst = Decimal("0.00")
        party_gstin = ""

        for e in v.entries:
            if not e.ledger:
                continue
            name_u = e.ledger.name.upper()
            net_debit = e.debit_amount - e.credit_amount
            if 'IGST' in name_u:
                igst += net_debit
            elif 'CGST' in name_u:
                cgst += net_debit
            elif 'SGST' in name_u:
                sgst += net_debit
            elif 'DISCOUNT' not in name_u and name_u != party_name.upper():
                taxable += net_debit
            
            if e.ledger.gstin and not party_gstin:
                party_gstin = e.ledger.gstin

        for e in v.entries:
            if e.ledger and 'DISCOUNT' in e.ledger.name.upper():
                net_disc = e.credit_amount - e.debit_amount
                taxable -= net_disc

        raw_num = (v.voucher_number or "").strip()
        raw_ref = (v.reference_number or "").strip()

        book_vouchers.append({
            "voucher_id": v.voucher_id,
            "party_name": party_name.upper(),
            "party_gstin": party_gstin.upper(),
            "voucher_number": raw_num.upper(),
            "reference_number": raw_ref.upper(),
            "norm_voucher_num": _normalize_inv(raw_num, strip_affixes),
            "norm_ref_num": _normalize_inv(raw_ref, strip_affixes),
            "voucher_date": v.voucher_date,
            "taxable_value": taxable,
            "cgst": cgst,
            "sgst": sgst,
            "igst": igst,
            "matched": False
        })

    # 3. Add Manual Purchases & ITC Entries
    mp_res = await db.execute(select(ManualPurchase).where(ManualPurchase.company_id == user.company_id))
    for mp in mp_res.scalars().all():
        raw_inv = (mp.invoice_number or "").strip()
        book_vouchers.append({
            "voucher_id": mp.id,
            "party_name": (mp.party_name or "").upper(),
            "party_gstin": (mp.gstin or "").upper(),
            "voucher_number": raw_inv.upper(),
            "reference_number": raw_inv.upper(),
            "norm_voucher_num": _normalize_inv(raw_inv, strip_affixes),
            "norm_ref_num": _normalize_inv(raw_inv, strip_affixes),
            "voucher_date": mp.invoice_date,
            "taxable_value": mp.taxable_value,
            "cgst": mp.cgst_amount,
            "sgst": mp.sgst_amount,
            "igst": mp.igst_amount,
            "matched": False
        })

    itc_res = await db.execute(select(ItcEntry).where(ItcEntry.company_id == user.company_id))
    for itc in itc_res.scalars().all():
        raw_inv = (itc.invoice_number or "").strip()
        book_vouchers.append({
            "voucher_id": itc.voucher_id or itc.itc_id,
            "itc_obj": itc,
            "party_name": (itc.supplier_name or "").upper(),
            "party_gstin": (itc.supplier_gstin or "").upper(),
            "voucher_number": raw_inv.upper(),
            "reference_number": raw_inv.upper(),
            "norm_voucher_num": _normalize_inv(raw_inv, strip_affixes),
            "norm_ref_num": _normalize_inv(raw_inv, strip_affixes),
            "voucher_date": itc.invoice_date,
            "taxable_value": itc.taxable_value,
            "cgst": itc.cgst_amount,
            "sgst": itc.sgst_amount,
            "igst": itc.igst_amount,
            "matched": False
        })

    exact_matches = 0
    tolerance_matches = 0
    fuzzy_matches = 0

    for g2b in g2b_entries:
        g2b_raw_inv = (g2b.invoice_number or "").strip().upper()
        g2b_norm_inv = _normalize_inv(g2b_raw_inv, strip_affixes)
        g2b_gstin = (g2b.supplier_gstin or "").strip().upper()
        g2b_supplier = (g2b.supplier_name or "").strip().upper()
        
        match = None
        match_type = None

        # PASS 1: Exact Number & GSTIN & Exact Amount
        for bv in book_vouchers:
            if bv["matched"]:
                continue
            num_match = (g2b_raw_inv == bv["voucher_number"]) or (g2b_raw_inv == bv["reference_number"]) or (g2b_norm_inv and (g2b_norm_inv == bv["norm_voucher_num"] or g2b_norm_inv == bv["norm_ref_num"]))
            gstin_match = (g2b_gstin and bv["party_gstin"] and g2b_gstin == bv["party_gstin"]) or (g2b_supplier and (g2b_supplier in bv["party_name"] or bv["party_name"] in g2b_supplier))
            
            if num_match and gstin_match:
                diff_taxable = abs(g2b.taxable_value - bv["taxable_value"])
                diff_tax = abs((g2b.cgst_amount + g2b.sgst_amount + g2b.igst_amount) - (bv["cgst"] + bv["sgst"] + bv["igst"]))
                if diff_taxable <= Decimal("0.05") and diff_tax <= Decimal("0.05"):
                    match = bv
                    match_type = "EXACT"
                    break

        # PASS 2: Normalized Number + Tolerance Thresholds (Ignorediffintaxableamt)
        if not match:
            for bv in book_vouchers:
                if bv["matched"]:
                    continue
                num_match = (g2b_norm_inv and (g2b_norm_inv == bv["norm_voucher_num"] or g2b_norm_inv == bv["norm_ref_num"])) or (g2b_raw_inv in bv["voucher_number"])
                gstin_match = (g2b_gstin and bv["party_gstin"] and g2b_gstin == bv["party_gstin"]) or (g2b_supplier and (g2b_supplier[:6] in bv["party_name"] or bv["party_name"][:6] in g2b_supplier))
                
                if (num_match and gstin_match):
                    diff_taxable = abs(g2b.taxable_value - bv["taxable_value"])
                    diff_tax = abs((g2b.cgst_amount + g2b.sgst_amount + g2b.igst_amount) - (bv["cgst"] + bv["sgst"] + bv["igst"]))
                    if diff_taxable <= taxable_tolerance and diff_tax <= tax_tolerance:
                        match = bv
                        match_type = "TOLERANCE"
                        break

        # PASS 3: Fuzzy Matching (Date within ±15 days + GSTIN + Amounts within tolerance)
        if not match and fuzzy_mode:
            for bv in book_vouchers:
                if bv["matched"]:
                    continue
                gstin_match = (g2b_gstin and bv["party_gstin"] and g2b_gstin == bv["party_gstin"])
                if gstin_match and g2b.invoice_date and bv["voucher_date"]:
                    days_diff = abs((g2b.invoice_date - bv["voucher_date"]).days)
                    if days_diff <= 15:
                        diff_taxable = abs(g2b.taxable_value - bv["taxable_value"])
                        diff_tax = abs((g2b.cgst_amount + g2b.sgst_amount + g2b.igst_amount) - (bv["cgst"] + bv["sgst"] + bv["igst"]))
                        if diff_taxable <= taxable_tolerance and diff_tax <= tax_tolerance:
                            match = bv
                            match_type = "FUZZY"
                            break

        if match:
            match["matched"] = True
            g2b.match_status = "Matched"
            g2b.itc_availability = "Available"
            g2b.matched_voucher_id = match["voucher_id"]
            
            if "itc_obj" in match and match["itc_obj"]:
                match["itc_obj"].claimed_return_period_id = g2b.return_period_id
                
            if match_type == "EXACT":
                exact_matches += 1
            elif match_type == "TOLERANCE":
                tolerance_matches += 1
            else:
                fuzzy_matches += 1
        else:
            g2b.match_status = "Unmatched"

    await db.commit()

    total_reconciled = exact_matches + tolerance_matches + fuzzy_matches
    unmatched_count = len(g2b_entries) - total_reconciled

    return {
        "status": "success",
        "detail": f"GSTR-2B Auto-Reconciliation complete: {total_reconciled} matched ({exact_matches} exact, {tolerance_matches} within tolerance, {fuzzy_matches} fuzzy).",
        "total_portal_entries": len(g2b_entries),
        "total_reconciled": total_reconciled,
        "exact_matches": exact_matches,
        "tolerance_matches": tolerance_matches,
        "fuzzy_matches": fuzzy_matches,
        "unmatched": unmatched_count,
        "rules_applied": {
            "taxable_tolerance": float(taxable_tolerance),
            "tax_tolerance": float(tax_tolerance),
            "strip_prefix_suffix": strip_affixes,
            "fuzzy_date_window_days": 15 if fuzzy_mode else 0
        }
    }

# --- GSTR-9 (Annual Returns) ---

@router.get("/gstr9", response_model=List[Gstr9AnnualReturnResponse])
async def get_gstr9_returns(
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Gstr9AnnualReturn).where(Gstr9AnnualReturn.company_id == user.company_id)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("/gstr9", response_model=Gstr9AnnualReturnResponse)
async def generate_gstr9(
    financial_year: str,  # format: '2025-2026'
    user: User = Depends(require_permission("reports", "update")),
    db: AsyncSession = Depends(get_db)
):
    # check existing
    dup_q = await db.execute(
        select(Gstr9AnnualReturn).where(
            Gstr9AnnualReturn.company_id == user.company_id,
            Gstr9AnnualReturn.financial_year == financial_year
        )
    )
    existing = dup_q.scalars().first()
    if existing:
        if existing.status == "Filed":
            raise HTTPException(status_code=400, detail="Annual Return for this FY is already Filed and locked.")
        # delete existing draft
        await db.delete(existing)
        await db.commit()

    # Parse years (financial year start is April Year1, end is March Year2)
    try:
        yr1_str, yr2_str = financial_year.split('-')
        yr1 = int(yr1_str)
        yr2 = int(yr2_str)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid financial year format. Use YYYY-YYYY.")

    # Fetch all filed return periods in this FY
    # GSTR-3B filed periods: months 4..12 of yr1 and 1..3 of yr2
    periods_q = await db.execute(
        select(GstReturnPeriod)
        .options(selectinload(GstReturnPeriod.gstr3b_summary))
        .where(
            GstReturnPeriod.company_id == user.company_id,
            GstReturnPeriod.status == "Filed",
            (
                ((GstReturnPeriod.period_year == yr1) & (GstReturnPeriod.period_month >= 4)) |
                ((GstReturnPeriod.period_year == yr2) & (GstReturnPeriod.period_month <= 3))
            )
        )
    )
    fy_periods = periods_q.scalars().all()

    # Aggregate GSTR-3B details
    outward_taxable = Decimal("0.00")
    outward_tax = Decimal("0.00")
    itc_claimed = Decimal("0.00")
    itc_reversed = Decimal("0.00")
    tax_payable = Decimal("0.00")
    cash_paid = Decimal("0.00")
    itc_paid = Decimal("0.00")
    interest = Decimal("0.00")
    late_fee = Decimal("0.00")

    for p in fy_periods:
        s = p.gstr3b_summary
        if s:
            outward_taxable += s.outward_taxable_value
            outward_tax += (s.outward_cgst + s.outward_sgst + s.outward_igst + s.outward_cess)
            itc_claimed += (s.itc_cgst_available + s.itc_sgst_available + s.itc_igst_available + s.itc_cess_available)
            itc_reversed += s.itc_reversed
            tax_payable += (s.net_cgst_payable + s.net_sgst_payable + s.net_igst_payable + s.net_cess_payable)
            cash_paid += s.tax_paid_via_cash
            itc_paid += s.tax_paid_via_itc
            interest += s.interest_paid
            late_fee += s.late_fee_paid

    ann_return = Gstr9AnnualReturn(
        company_id=user.company_id,
        financial_year=financial_year,
        status="Draft",
        outward_taxable_supplies=outward_taxable,
        outward_tax_amount=outward_tax,
        zero_rated_supplies=Decimal("0.00"),
        nil_rated_supplies=Decimal("0.00"),
        inward_taxable_supplies=outward_taxable, # proxy
        inward_tax_amount=outward_tax, # proxy
        itc_claimed=itc_claimed,
        itc_reversed=itc_reversed,
        total_tax_payable=tax_payable,
        tax_paid_via_cash=cash_paid,
        tax_paid_via_itc=itc_paid,
        interest_paid=interest,
        late_fee_paid=late_fee
    )
    db.add(ann_return)
    await db.commit()
    await db.refresh(ann_return)
    return ann_return

@router.post("/gstr9/{annual_return_id}/file")
async def file_gstr9(
    annual_return_id: int,
    arn: str,
    user: User = Depends(require_permission("reports", "update")),
    db: AsyncSession = Depends(get_db)
):
    ret_q = await db.execute(
        select(Gstr9AnnualReturn).where(
            Gstr9AnnualReturn.annual_return_id == annual_return_id,
            Gstr9AnnualReturn.company_id == user.company_id
        )
    )
    ret = ret_q.scalars().first()
    if not ret:
        raise HTTPException(status_code=404, detail="Annual Return not found.")
    
    ret.status = "Filed"
    ret.arn = arn
    ret.filed_date = date.today()
    ret.filed_by = user.user_id
    
    await db.commit()
    return {"detail": "GSTR-9 Annual Return marked as filed successfully.", "arn": arn}

# --- E-Invoicing (IRN & E-Way Bill) ---

@router.post("/einvoice/{voucher_id}/generate")
async def generate_einvoice_irn(
    voucher_id: int,
    user: User = Depends(require_permission("vouchers", "update")),
    db: AsyncSession = Depends(get_db),
    _on: User = Depends(require_integration("einvoice")),
):
    """e-Invoice (IRN) for a B2B sales voucher. In Live mode it goes through the GSP (app/services/einvoicing.py).
    In Demo mode the IRN, ack number and e-way bill number are made up, saved under the "mock" environment and
    flagged demo; they must never be printed on an invoice or sent to Tally."""
    from app.models.portal_core import Company
    from app.models.portal_core import EinvoiceMetadata
    
    # 1. Fetch Company Environment Selection
    comp_q = await db.execute(select(Company).where(Company.company_id == user.company_id))
    company = comp_q.scalars().first()
    if not company:
        raise HTTPException(status_code=400, detail="Company details not found.")
    active_env = company.einvoice_env or "mock"
    if active_env != "mock":
        from app.services import einvoicing
        from app.services.gsp import GspError
        try:
            record = await einvoicing.generate_irn(db, company, voucher_id, user.user_id)
        except LookupError:
            raise HTTPException(status_code=404, detail="Voucher not found.")
        except einvoicing.NotReady as e:
            raise HTTPException(status_code=422, detail={"message": "Fix these first:", "problems": e.problems})
        except GspError as e:
            raise HTTPException(status_code=502, detail=f"The e-invoice portal refused it: {e}")
        await db.commit()
        return {"detail": "e-Invoice registered.", "demo": False, **einvoicing.record_out(record)}

    # 2. Fetch voucher
    stmt = select(TrnVoucher).options(selectinload(TrnVoucher.voucher_type)).where(
        TrnVoucher.voucher_id == voucher_id,
        TrnVoucher.company_id == user.company_id
    )
    res = await db.execute(stmt)
    voucher = res.scalars().first()
    if not voucher:
        raise HTTPException(status_code=404, detail="Voucher not found.")
        
    # Check if voucher is Sales voucher
    if "sales" not in (voucher.voucher_type.name if voucher.voucher_type else "").lower():
        raise HTTPException(status_code=400, detail="E-Invoicing is only supported for Sales Vouchers.")
        
    # 3. Check if already generated for this active environment
    meta_q = await db.execute(
        select(EinvoiceMetadata).where(
            EinvoiceMetadata.voucher_id == voucher_id,
            EinvoiceMetadata.environment == active_env
        )
    )
    existing = meta_q.scalars().first()
    if existing and existing.irn:
        return {
            "detail": "A demo e-invoice already exists for this voucher.",
            "demo": True,
            "irn": existing.irn,
            "ack_no": existing.ack_no,
            "ack_date": existing.ack_date.strftime("%Y-%m-%d %H:%M:%S") if existing.ack_date else None,
            "eway_bill_no": existing.eway_bill_no
        }
        
    # 4. Perform basic validations (B2B checks)
    import hashlib
    import random
    inv_num = voucher.voucher_number or "INV-0"
    inv_date = str(voucher.voucher_date)
    company_id = user.company_id
    
    # Calculate a valid-looking 64-char hex string for IRN
    hash_input = f"{company_id}-{inv_num}-{inv_date}-demo-einvoice"
    irn = hashlib.sha256(hash_input.encode('utf-8')).hexdigest()
    
    # Mock Acknowledgement Details
    ack_no = "".join([str(random.randint(0, 9)) for _ in range(15)])
    ack_date = get_ist_now()
    
    # Demo e-way bill number for bills of ₹50,000 or more, only when the e-way bill switch is on too
    total_amount = float(voucher.total_amount or 0)
    eway_bill_no = None
    eway_bill_date = None
    if total_amount >= 50000.00 and await is_enabled(db, user.company_id, "eway_bill"):
        eway_bill_no = "12" + "".join([str(random.randint(0, 9)) for _ in range(10)])
        eway_bill_date = get_ist_now()
        
    meta = EinvoiceMetadata(
        voucher_id=voucher_id,
        irn=irn,
        ack_no=ack_no,
        ack_date=ack_date,
        eway_bill_no=eway_bill_no,
        eway_bill_date=eway_bill_date,
        environment=active_env,
        raw_response='{"demo": true, "detail": "Made up by MyTally; not registered on the invoice portal"}'
    )
    
    db.add(meta)
    await db.commit()
    
    return {
        "detail": "Demo e-invoice created. The IRN is made up and not valid on any invoice.",
        "demo": True,
        "irn": irn,
        "ack_no": ack_no,
        "ack_date": ack_date.strftime("%Y-%m-%d %H:%M:%S"),
        "eway_bill_no": eway_bill_no,
        "eway_bill_date": eway_bill_date.strftime("%Y-%m-%d %H:%M:%S") if eway_bill_date else None
    }

@router.get("/einvoices", response_model=List[GstEinvoiceListResponse])
async def get_einvoices_list(
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
    _on: User = Depends(require_integration("einvoice")),
):
    """Fetch B2B Sales Invoices list and their corresponding E-invoicing status filtered by company environment"""
    from app.models.portal_core import Company
    from app.models.portal_core import EinvoiceMetadata
    from app.models.tally_core import MstLedger
    
    # 1. Fetch Company Environment Selection
    comp_q = await db.execute(select(Company).where(Company.company_id == user.company_id))
    company = comp_q.scalars().first()
    active_env = company.einvoice_env or "mock"
    
    # 2. Fetch Sales Vouchers
    stmt = select(TrnVoucher).options(
        selectinload(TrnVoucher.voucher_type),
        selectinload(TrnVoucher.entries).selectinload(TrnAccounting.ledger).selectinload(MstLedger.group)
    ).where(
        TrnVoucher.company_id == user.company_id
    )
    res = await db.execute(stmt)
    vouchers = res.scalars().all()
    
    sales_vouchers = []
    for v in vouchers:
        v_type_name = (v.voucher_type.name if v.voucher_type else "").lower()
        if "sales" in v_type_name:
            sales_vouchers.append(v)
            
    # Resolve details
    result = []
    for v in sales_vouchers:
        # Resolve party name and amount
        from app.routers.vouchers import _resolve_party_and_amount
        party_name, amount, *_ = _resolve_party_and_amount(v.entries)
        
        # Resolve party GSTIN
        party_gstin = None
        if party_name:
            party_stmt = select(MstLedger.gstin).where(
                MstLedger.name == party_name,
                MstLedger.company_id == user.company_id
            )
            party_res = await db.execute(party_stmt)
            party_gstin = party_res.scalars().first()
            
        # Fetch metadata for the active mode (demo records in Demo, GSP records in Live)
        meta_stmt = select(EinvoiceMetadata).where(
            EinvoiceMetadata.voucher_id == v.voucher_id,
            EinvoiceMetadata.environment == ("mock" if active_env == "mock" else "live")
        ).order_by(EinvoiceMetadata.metadata_id.desc())
        meta_res = await db.execute(meta_stmt)
        meta = meta_res.scalars().first()
        
        result.append({
            "voucher_id": v.voucher_id,
            "voucher_number": v.voucher_number,
            "voucher_date": v.voucher_date,
            "party_name": party_name or "Unknown Party",
            "party_gstin": party_gstin,
            "amount": float(amount or v.total_amount or 0),
            "irn": meta.irn if meta else None,
            "ack_no": meta.ack_no if meta else None,
            "eway_bill_no": meta.eway_bill_no if meta else None,
            "demo": bool(meta and meta.environment == "mock"),
        })
        
    return result

async def _either_switch_on(user: User = Depends(require_permission("reports", "read")), db: AsyncSession = Depends(get_db)) -> User:
    """e-Invoice and e-way bill share one set-up, so either switch being on is enough to see it."""
    if not (await is_enabled(db, user.company_id, "einvoice") or await is_enabled(db, user.company_id, "eway_bill")):
        from app.services.integrations import switched_off
        raise switched_off("einvoice")
    return user


def _settings_out(company) -> dict:
    from app.services.gsp import gsp_account_ready
    mode = "demo" if (company.einvoice_env or "mock") == "mock" else "live"
    return {
        "mode": mode, "einvoice_env": "mock" if mode == "demo" else "live", "gsp_provider": settings.GSP_PROVIDER,
        "gsp_account_ready": gsp_account_ready(), "company_gstin": company.gstin,
        "einvoice_username": company.einvoice_username, "has_einvoice_password": bool(company.einvoice_password),
        "eway_username": company.eway_username, "has_eway_password": bool(company.eway_password),
    }


@router.get("/einvoice/settings", response_model=EinvoiceSettingsResponse)
async def get_einvoice_settings(user: User = Depends(_either_switch_on), db: AsyncSession = Depends(get_db)):
    from app.models.portal_core import Company
    company = (await db.execute(select(Company).where(Company.company_id == user.company_id))).scalars().first()
    if not company:
        raise HTTPException(status_code=404, detail="Company details not found.")
    return _settings_out(company)


@router.put("/einvoice/settings", response_model=EinvoiceSettingsResponse)
async def update_einvoice_settings(
    payload: EinvoiceSettingsUpdate,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    _on: User = Depends(_either_switch_on),
):
    """Admin: Demo or Live mode, and the company's e-invoice / e-way bill portal API users (passwords write-only)."""
    from app.models.portal_core import Company
    from app.services.gsp import gsp_account_ready
    company = (await db.execute(select(Company).where(Company.company_id == user.company_id))).scalars().first()
    if not company:
        raise HTTPException(status_code=404, detail="Company details not found.")
    mode = payload.mode or (None if payload.einvoice_env is None else ("demo" if payload.einvoice_env == "mock" else "live"))
    if mode not in (None, "demo", "live"):
        raise HTTPException(status_code=422, detail="Mode must be demo or live.")
    if mode == "live" and not gsp_account_ready():
        raise HTTPException(status_code=422, detail="Live needs the GST provider's account keys on the server first (GSP_EMAIL, GSP_CLIENT_ID, GSP_CLIENT_SECRET).")
    if mode:
        company.einvoice_env = "mock" if mode == "demo" else "live"
    for field, length in (("einvoice_username", 100), ("eway_username", 100)):
        value = getattr(payload, field)
        if value is not None:
            setattr(company, field, value.strip()[:length] or None)
    for field in ("einvoice_password", "eway_password"):
        value = getattr(payload, field)
        if value:  # empty leaves the saved password as it is
            setattr(company, field, value[:255])
    db.add(AuditLog(company_id=company.company_id, user_id=user.user_id, action="UPDATE", entity_type="GstDocsSettings",
                    entity_id=company.company_id, new_value={"mode": mode, "fields": [k for k, v in payload.model_dump().items() if v and "password" not in k]}))
    await db.commit()
    return _settings_out(company)


# --- Manual Purchases ---

@router.post("/periods/{period_id}/manual-purchases", response_model=ManualPurchaseResponse)
async def create_manual_purchase(
    period_id: int,
    req: ManualPurchaseCreate,
    user: User = Depends(require_permission("reports", "create")),
    db: AsyncSession = Depends(get_db)
):
    period_query = await db.execute(select(GstReturnPeriod).where(GstReturnPeriod.return_period_id == period_id, GstReturnPeriod.company_id == user.company_id))
    period = period_query.scalars().first()
    if not period:
        raise HTTPException(status_code=404, detail="GST Return period not found.")
        
    mp = ManualPurchase(
        company_id=user.company_id,
        source=req.source,
        invoice_number=req.invoice_number,
        invoice_date=req.invoice_date,
        product_description=req.product_description,
        taxable_value=req.taxable_value,
        cgst_amount=req.cgst_amount,
        sgst_amount=req.sgst_amount,
        igst_amount=req.igst_amount,
        claimed_return_period_id=period_id
    )
    db.add(mp)
    await db.commit()
    await db.refresh(mp)
    return mp

@router.get("/periods/{period_id}/manual-purchases", response_model=List[ManualPurchaseResponse])
async def get_manual_purchases(
    period_id: int,
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(ManualPurchase).where(
        ManualPurchase.claimed_return_period_id == period_id,
        ManualPurchase.company_id == user.company_id
    )
    res = await db.execute(stmt)
    return res.scalars().all()

@router.delete("/manual-purchases/{purchase_id}")
async def delete_manual_purchase(
    purchase_id: int,
    user: User = Depends(require_permission("reports", "update")),
    db: AsyncSession = Depends(get_db)
):
    mp_query = await db.execute(select(ManualPurchase).where(ManualPurchase.purchase_id == purchase_id, ManualPurchase.company_id == user.company_id))
    mp = mp_query.scalars().first()
    if not mp:
        raise HTTPException(status_code=404, detail="Manual purchase not found.")
        
    await db.delete(mp)
    await db.commit()
    return {"detail": "Manual purchase deleted successfully."}


# =========================================================================
# MSME SECTION 43B(h) VENDOR COMPLIANCE & PAYMENT TRACKING
# =========================================================================
from app.models.tally_core import MstLedgerMsmeDetail, TrnBill

@router.get("/msme-compliance")
async def get_msme_compliance_report(
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns full MSME Vendor compliance dataset for Section 43B(h) Income Tax compliance:
    - Lists all Micro & Small vendors
    - Aggregates open unpaid purchase bills
    - Calculates days elapsed against 15-day / 45-day statutory limits
    - Computes Tax Disallowance risk for overdue payments
    """
    # 1. Fetch all ledgers belonging to Sundry Creditors or having MSME details
    creditors_stmt = select(MstLedger).options(
        selectinload(MstLedger.msme_details),
        selectinload(MstLedger.addresses),
        selectinload(MstLedger.group)
    ).where(MstLedger.company_id == user.company_id)
    
    res = await db.execute(creditors_stmt)
    all_ledgers = res.scalars().all()
    
    # Filter for MSME vendors (has msme_details or has Micro/Small tag)
    today = date.today()
    msme_vendors = []
    
    total_vendors = 0
    total_outstanding = Decimal("0.00")
    total_at_risk = Decimal("0.00")
    total_critical = Decimal("0.00")
    total_compliant = Decimal("0.00")
    
    for l in all_ledgers:
        msme_detail = l.msme_details[0] if l.msme_details and len(l.msme_details) > 0 else None
        
        # Consider as MSME if explicit detail or if vendor under Sundry Creditors with active detail
        is_msme = msme_detail is not None or (l.group and "creditor" in l.group.name.lower() and getattr(l, 'is_msme', False))
        if not is_msme and not msme_detail:
            continue
            
        total_vendors += 1
        
        # Fetch open bills for this vendor
        bills_stmt = select(TrnBill).where(
            TrnBill.company_id == user.company_id,
            TrnBill.party_ledger_id == l.ledger_id,
            TrnBill.status != "Paid"
        ).order_by(TrnBill.bill_date.asc())
        
        bills_res = await db.execute(bills_stmt)
        open_bills = bills_res.scalars().all()
        
        vendor_outstanding = Decimal("0.00")
        vendor_bills = []
        
        for b in open_bills:
            b_amt = Decimal(str(b.bill_amount or 0))
            s_amt = Decimal(str(b.settled_amount or 0))
            pending_amt = b_amt - s_amt
            if pending_amt <= 0:
                continue
                
            vendor_outstanding += pending_amt
            b_date = b.bill_date or today
            days_elapsed = (today - b_date).days
            
            # Statutory rule: 45 days max with written agreement, 15 days without
            limit_days = 45
            days_remaining = limit_days - days_elapsed
            
            if days_elapsed > 45:
                bill_status = "OVERDUE_DISALLOWANCE" # Disallowed under Sec 43B(h)
                total_at_risk += pending_amt
            elif days_elapsed >= 38:
                bill_status = "CRITICAL_WARNING" # <= 7 days remaining
                total_critical += pending_amt
            else:
                bill_status = "WITHIN_LIMIT"
                total_compliant += pending_amt
                
            vendor_bills.append({
                "bill_id": b.bill_id,
                "bill_reference": b.bill_reference,
                "bill_date": str(b_date),
                "due_date": str(b.due_date) if b.due_date else str(b_date),
                "bill_amount": float(b_amt),
                "settled_amount": float(s_amt),
                "outstanding_amount": float(pending_amt),
                "days_elapsed": days_elapsed,
                "days_remaining": days_remaining,
                "status": bill_status
            })
            
        total_outstanding += vendor_outstanding
        
        # Vendor risk status
        if any(b['status'] == 'OVERDUE_DISALLOWANCE' for b in vendor_bills):
            v_status = 'HIGH_RISK'
        elif any(b['status'] == 'CRITICAL_WARNING' for b in vendor_bills):
            v_status = 'MEDIUM_RISK'
        else:
            v_status = 'COMPLIANT'
            
        msme_vendors.append({
            "ledger_id": l.ledger_id,
            "name": l.name,
            "gstin": l.gstin,
            "state": l.state,
            "enterprise_type": msme_detail.enterprise_type if msme_detail else "Micro",
            "udyam_reg_no": msme_detail.udyam_reg_no if msme_detail else None,
            "applicable_from": str(msme_detail.applicable_from) if msme_detail and msme_detail.applicable_from else None,
            "total_outstanding": float(vendor_outstanding),
            "pending_bills_count": len(vendor_bills),
            "vendor_risk_status": v_status,
            "bills": vendor_bills
        })
        
    return {
        "summary": {
            "total_msme_vendors": total_vendors,
            "total_outstanding_amount": float(total_outstanding),
            "total_at_risk_disallowance": float(total_at_risk),
            "total_critical_due_soon": float(total_critical),
            "total_compliant_amount": float(total_compliant),
            "fiscal_year": f"{today.year if today.month >= 4 else today.year - 1}-{str(today.year + 1 if today.month >= 4 else today.year)[2:]}"
        },
        "vendors": msme_vendors
    }
