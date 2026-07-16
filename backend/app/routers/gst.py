from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime, date
from decimal import Decimal

from app.core.database import get_db
from app.core.permissions import require_permission
from app.models.user import User
from app.models.voucher import TrnVoucher, TrnAccounting
from app.models.gst import GstReturnPeriod, Gstr1LineItem, Gstr1HsnSummary, Gstr3bSummary, ItcEntry
from app.schemas.gst import (
    GstReturnPeriodCreate, GstReturnPeriodResponse,
    Gstr1LineItemResponse, Gstr1HsnSummaryResponse, Gstr3bSummaryResponse,
    ItcEntryCreate, ItcEntryResponse
)

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

# --- Snapshot Generation ---

@router.post("/periods/{period_id}/generate")
async def generate_gst_snapshot(
    period_id: int,
    user: User = Depends(require_permission("reports", "update")),
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
    # Simplification: query all non-optional vouchers for this company
    vouchers_query = await db.execute(
        select(TrnVoucher)
        .options(selectinload(TrnVoucher.entries))
        .where(
            TrnVoucher.company_id == user.company_id,
            TrnVoucher.is_optional == False
        )
    )
    vouchers = vouchers_query.scalars().all()
    
    total_taxable_outward = Decimal("0.00")
    total_cgst_outward = Decimal("0.00")
    total_sgst_outward = Decimal("0.00")
    total_igst_outward = Decimal("0.00")
    
    for v in vouchers:
        # Determine if it's a Sales voucher
        # Check if v.voucher_type_id name is Sales
        # For simplicity, we scan entries for SGST / CGST / IGST tax ledgers
        has_tax = False
        cgst = Decimal("0.00")
        sgst = Decimal("0.00")
        igst = Decimal("0.00")
        taxable = Decimal("0.00")
        
        # Pull ledger names for tax detection
        for e in v.entries:
            # We assume ledger names containing 'CGST', 'SGST', 'IGST' represent tax entries
            # In a real ERP, we look at the ledger group nature.
            # Fetch actual ledger name
            from app.models.ledger import MstLedger
            l_query = await db.execute(select(MstLedger).where(MstLedger.ledger_id == e.ledger_id))
            ledger = l_query.scalars().first()
            if not ledger:
                continue
            if 'CGST' in ledger.name:
                cgst += e.credit_amount if e.credit_amount > 0 else e.debit_amount
                has_tax = True
            elif 'SGST' in ledger.name:
                sgst += e.credit_amount if e.credit_amount > 0 else e.debit_amount
                has_tax = True
            elif 'IGST' in ledger.name:
                igst += e.credit_amount if e.credit_amount > 0 else e.debit_amount
                has_tax = True
            elif 'Sales' in ledger.name:
                taxable += e.credit_amount if e.credit_amount > 0 else e.debit_amount
                
        if has_tax and taxable > 0:
            total_taxable_outward += taxable
            total_cgst_outward += cgst
            total_sgst_outward += sgst
            total_igst_outward += igst
            
            line = Gstr1LineItem(
                return_period_id=period_id,
                voucher_id=v.voucher_id,
                supply_type="B2B", # default
                party_gstin="27AADCB2230M1Z5", # dummy
                invoice_number=v.voucher_number,
                invoice_date=v.voucher_date,
                place_of_supply="Maharashtra",
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
    
    total_cgst_itc = sum(i.cgst_amount for i in itc_list)
    total_sgst_itc = sum(i.sgst_amount for i in itc_list)
    total_igst_itc = sum(i.igst_amount for i in itc_list)
    
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
    stmt = select(Gstr1LineItem).where(Gstr1LineItem.return_period_id == period_id)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.get("/periods/{period_id}/gstr3b", response_model=Gstr3bSummaryResponse)
async def get_gstr3b_summary(
    period_id: int,
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Gstr3bSummary).where(Gstr3bSummary.return_period_id == period_id)
    res = await db.execute(stmt)
    summary = res.scalars().first()
    if not summary:
        raise HTTPException(status_code=404, detail="GSTR-3B summary not generated yet.")
    return summary

@router.post("/periods/{period_id}/file")
async def file_gst_return(
    period_id: int,
    arn: str,
    user: User = Depends(require_permission("reports", "update")),
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
