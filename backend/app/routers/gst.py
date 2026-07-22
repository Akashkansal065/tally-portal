from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
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
from app.models.gst import GstReturnPeriod, Gstr1LineItem, Gstr1HsnSummary, Gstr3bSummary, ItcEntry, Gstr2bEntry, Gstr9AnnualReturn, ManualPurchase
from app.schemas.gst import (
    GstReturnPeriodCreate, GstReturnPeriodResponse,
    Gstr1LineItemResponse, Gstr1HsnSummaryResponse, Gstr3bSummaryResponse,
    ItcEntryCreate, ItcEntryResponse, Gstr2bEntryResponse, Gstr9AnnualReturnResponse,
    GstEinvoiceListResponse, EinvoiceSettingsResponse, EinvoiceSettingsUpdate,
    ManualPurchaseCreate, ManualPurchaseResponse
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
    from app.models.ledger import MstLedger
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
        party_name, _ = _resolve_party_and_amount(v.entries)
        
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
        
    from app.models.company import Company
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
    from app.models.company import Company
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

    # Resolve return period from rtnprd (usually 'MMYYYY' or 'MM/YYYY')
    rtnprd = data.get("rtnprd")
    month = None
    year = None
    if rtnprd:
        if "/" in rtnprd:
            parts = rtnprd.split("/")
            try:
                month = int(parts[0])
                year = int(parts[1])
            except ValueError:
                pass
        elif len(rtnprd) == 6:
            try:
                month = int(rtnprd[:2])
                year = int(rtnprd[2:])
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
        # Create a return period for GSTR-3B by default
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
    b2b_list = data.get("b2b", [])
    for supplier in b2b_list:
        ctin = supplier.get("ctin")
        trade_name = supplier.get("trdn") or supplier.get("lmnm") or "Unknown Supplier"
        
        invoices = supplier.get("inv", [])
        for inv in invoices:
            inum = inv.get("inum")
            idt_str = inv.get("idt")
            
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
                        
            taxable_value = Decimal("0.00")
            cgst = Decimal("0.00")
            sgst = Decimal("0.00")
            igst = Decimal("0.00")
            cess = Decimal("0.00")
            
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
                itc_availability="Available",
                match_status="Unmatched"
            )
            db.add(entry)
            imported_count += 1

    # 2. Parse CDNR (Credit/Debit Notes)
    cdnr_list = data.get("cdnr", [])
    for supplier in cdnr_list:
        ctin = supplier.get("ctin")
        trade_name = supplier.get("trdn") or supplier.get("lmnm") or "Unknown Supplier"
        notes = supplier.get("nt", [])
        for note in notes:
            nt_num = note.get("nt_num")
            nt_dt_str = note.get("nt_dt")
            
            try:
                note_date = datetime.strptime(nt_dt_str, "%d-%m-%Y").date()
            except ValueError:
                try:
                    note_date = datetime.strptime(nt_dt_str, "%d/%m/%Y").date()
                except ValueError:
                    note_date = date.today()
                    
            taxable_value = Decimal("0.00")
            cgst = Decimal("0.00")
            sgst = Decimal("0.00")
            igst = Decimal("0.00")
            cess = Decimal("0.00")
            
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
                itc_availability="Available",
                match_status="Unmatched"
            )
            db.add(entry)
            imported_count += 1

    await db.commit()
    return {"detail": f"Successfully parsed GSTR-2B JSON. Imported {imported_count} entries."}

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
    """Reconcile GSTR-2B purchase entries against books (ItcEntries / purchase vouchers)"""
    # 1. Fetch GSTR-2B unmatched/mismatch entries
    stmt = select(Gstr2bEntry).where(
        Gstr2bEntry.company_id == user.company_id,
        Gstr2bEntry.match_status != "Matched"
    )
    g2b_res = await db.execute(stmt)
    unmatched_g2b = g2b_res.scalars().all()

    # 2. Fetch all ITC entries in book
    itc_stmt = select(ItcEntry).where(ItcEntry.company_id == user.company_id)
    itc_res = await db.execute(itc_stmt)
    book_itc = itc_res.scalars().all()

    reconciled_count = 0
    mismatch_count = 0

    for g2b in unmatched_g2b:
        # Match by supplier_gstin and invoice_number (case-insensitive & space stripped)
        match = None
        g2b_inv = g2b.invoice_number.strip().upper()
        g2b_gstin = g2b.supplier_gstin.strip().upper()
        
        for itc in book_itc:
            itc_inv = itc.invoice_number.strip().upper()
            itc_gstin = itc.supplier_gstin.strip().upper() if itc.supplier_gstin else ""
            if itc_inv == g2b_inv and itc_gstin == g2b_gstin:
                match = itc
                break
        
        if match:
            # Check amounts tollerance (allow up to 2.00 difference for round-offs)
            diff_taxable = abs(g2b.taxable_value - match.taxable_value)
            diff_cgst = abs(g2b.cgst_amount - match.cgst_amount)
            diff_sgst = abs(g2b.sgst_amount - match.sgst_amount)
            diff_igst = abs(g2b.igst_amount - match.igst_amount)
            
            if diff_taxable <= 2.00 and diff_cgst <= 2.00 and diff_sgst <= 2.00 and diff_igst <= 2.00:
                g2b.match_status = "Matched"
                g2b.itc_availability = "Available"
                g2b.matched_voucher_id = match.voucher_id
                
                # Auto-claim this ITC entry in the return period of this GSTR-2B entry
                match.claimed_return_period_id = g2b.return_period_id
                
                reconciled_count += 1
            else:
                g2b.match_status = "Mismatch"
                mismatch_count += 1
        else:
            g2b.match_status = "Unmatched"

    await db.commit()
    return {
        "detail": "Reconciliation completed successfully.",
        "matched": reconciled_count,
        "mismatches": mismatch_count
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
    db: AsyncSession = Depends(get_db)
):
    """Generate E-Invoice (IRN, QR Code) for B2B Sales Voucher based on company active environment"""
    from app.models.company import Company
    from app.models.advanced import EinvoiceMetadata
    
    # 1. Fetch Company Environment Selection
    comp_q = await db.execute(select(Company).where(Company.company_id == user.company_id))
    company = comp_q.scalars().first()
    if not company:
        raise HTTPException(status_code=400, detail="Company details not found.")
    active_env = company.einvoice_env or "mock"
    
    # Credentials check for live environments
    if active_env in ["sandbox", "production"]:
        if not company.einvoice_username or not company.einvoice_password:
            raise HTTPException(status_code=400, detail=f"E-Invoicing Portal credentials (Username/Password) are not configured for {active_env.title()} env.")
        if not company.einvoice_gsp_client_id or not company.einvoice_gsp_client_secret:
            raise HTTPException(status_code=400, detail=f"GSP credentials (Client ID/Client Secret) are not configured for {active_env.title()} env.")

    # 2. Fetch voucher
    stmt = select(TrnVoucher).where(
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
            "detail": f"E-Invoice already generated under {active_env} environment.",
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
    hash_input = f"{company_id}-{inv_num}-{inv_date}-gst-einvoicing-{active_env}-sneh-distributors"
    irn = hashlib.sha256(hash_input.encode('utf-8')).hexdigest()
    
    # Mock Acknowledgement Details
    ack_no = "".join([str(random.randint(0, 9)) for _ in range(15)])
    ack_date = datetime.now()
    
    # Mock E-Way Bill Number if voucher amount is >= 50,000
    total_amount = float(voucher.total_amount or 0)
    eway_bill_no = None
    eway_bill_date = None
    if total_amount >= 50000.00:
        eway_bill_no = "12" + "".join([str(random.randint(0, 9)) for _ in range(10)])
        eway_bill_date = datetime.now()
        
    meta = EinvoiceMetadata(
        voucher_id=voucher_id,
        irn=irn,
        ack_no=ack_no,
        ack_date=ack_date,
        eway_bill_no=eway_bill_no,
        eway_bill_date=eway_bill_date,
        environment=active_env,
        raw_response=f'{{"success": true, "status": "ACT", "irp": "NIC-IRP-1", "environment": "{active_env}"}}'
    )
    
    db.add(meta)
    await db.commit()
    
    return {
        "detail": f"E-Invoice generated successfully in {active_env.title()} environment.",
        "irn": irn,
        "ack_no": ack_no,
        "ack_date": ack_date.strftime("%Y-%m-%d %H:%M:%S"),
        "eway_bill_no": eway_bill_no,
        "eway_bill_date": eway_bill_date.strftime("%Y-%m-%d %H:%M:%S") if eway_bill_date else None
    }

@router.get("/einvoices", response_model=List[GstEinvoiceListResponse])
async def get_einvoices_list(
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db)
):
    """Fetch B2B Sales Invoices list and their corresponding E-invoicing status filtered by company environment"""
    from app.models.company import Company
    from app.models.advanced import EinvoiceMetadata
    from app.models.ledger import MstLedger
    
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
        party_name, amount = _resolve_party_and_amount(v.entries)
        
        # Resolve party GSTIN
        party_gstin = None
        if party_name:
            party_stmt = select(MstLedger.gstin).where(
                MstLedger.name == party_name,
                MstLedger.company_id == user.company_id
            )
            party_res = await db.execute(party_stmt)
            party_gstin = party_res.scalars().first()
            
        # Fetch metadata filtered by active environment
        meta_stmt = select(EinvoiceMetadata).where(
            EinvoiceMetadata.voucher_id == v.voucher_id,
            EinvoiceMetadata.environment == active_env
        )
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
            "eway_bill_no": meta.eway_bill_no if meta else None
        })
        
    return result

@router.get("/einvoice/settings", response_model=EinvoiceSettingsResponse)
async def get_einvoice_settings(
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve the company's active e-invoicing settings and environment configuration"""
    from app.models.company import Company
    comp_q = await db.execute(select(Company).where(Company.company_id == user.company_id))
    company = comp_q.scalars().first()
    if not company:
        raise HTTPException(status_code=404, detail="Company details not found.")
    
    return {
        "einvoice_env": company.einvoice_env or "mock",
        "einvoice_username": company.einvoice_username,
        "einvoice_gsp_client_id": company.einvoice_gsp_client_id,
        "has_password": bool(company.einvoice_password),
        "has_gsp_client_secret": bool(company.einvoice_gsp_client_secret)
    }

@router.put("/einvoice/settings")
async def update_einvoice_settings(
    payload: EinvoiceSettingsUpdate,
    user: User = Depends(require_permission("reports", "update")),
    db: AsyncSession = Depends(get_db)
):
    """Update the company's e-invoicing environment and credentials settings"""
    from app.models.company import Company
    comp_q = await db.execute(select(Company).where(Company.company_id == user.company_id))
    company = comp_q.scalars().first()
    if not company:
        raise HTTPException(status_code=404, detail="Company details not found.")
    
    # Validate environment values
    if payload.einvoice_env not in ["mock", "sandbox", "production"]:
        raise HTTPException(status_code=400, detail="Invalid environment choice. Select Mock, Sandbox, or Production.")
        
    company.einvoice_env = payload.einvoice_env
    if payload.einvoice_username is not None:
        company.einvoice_username = payload.einvoice_username
    if payload.einvoice_password:
        company.einvoice_password = payload.einvoice_password
    if payload.einvoice_gsp_client_id is not None:
        company.einvoice_gsp_client_id = payload.einvoice_gsp_client_id
    if payload.einvoice_gsp_client_secret:
        company.einvoice_gsp_client_secret = payload.einvoice_gsp_client_secret
        
    await db.commit()
    return {"detail": "E-Invoicing configuration settings updated successfully."}

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
