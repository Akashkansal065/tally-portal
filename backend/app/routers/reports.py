"""
Reports Router — comprehensive date-filtered reports.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, desc
from sqlalchemy.sql import func
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date

from app.core.database import get_db
from app.core.permissions import require_permission
from app.models.user import User
from app.models.voucher import TrnVoucher, TrnAccounting
from app.models.ledger import MstLedger

router = APIRouter(prefix="/reports", tags=["Reports Hub"])


@router.get("/daybook")
async def get_daybook(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all vouchers for the company within the date range."""
    query = select(Voucher).where(Voucher.company_id == user.company_id)
    if from_date:
        query = query.where(Voucher.date >= date.fromisoformat(from_date))
    if to_date:
        query = query.where(Voucher.date <= date.fromisoformat(to_date))

    result = await db.execute(query.order_by(desc(Voucher.date)).limit(100))
    vouchers = result.scalars().all()

    output = []
    for v in vouchers:
        # Load entries / amount info
        entries_query = await db.execute(select(VoucherEntry).where(VoucherEntry.voucher_id == v.voucher_id))
        entries = entries_query.scalars().all()
        # Choose amount of first debit or credit entry
        amount = 0.0
        party_name = "Generic Party"
        if entries:
            amount = float(entries[0].amount)
            party_name = entries[0].ledger_name

        output.append({
            "id": v.voucher_id,
            "voucher_number": v.voucher_number,
            "date": v.date.isoformat() if v.date else None,
            "type": v.type,
            "party_name": party_name,
            "amount": amount,
        })
    return output


@router.get("/sales-register")
async def get_sales_register(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all Sales vouchers within the period."""
    query = select(TrnVoucher).where(TrnVoucher.company_id == user.company_id)
    if from_date:
        query = query.where(TrnVoucher.date >= date.fromisoformat(from_date))
    if to_date:
        query = query.where(TrnVoucher.date <= date.fromisoformat(to_date))
    
    result = await db.execute(query.order_by(desc(TrnVoucher.date)).limit(100))
    vouchers = result.scalars().all()
    
    # Enrich with entries
    output = []
    for v in vouchers:
        entries_query = await db.execute(select(TrnAccounting).where(TrnAccounting.voucher_id == v.voucher_id))
        entries = entries_query.scalars().all()
        amount = 0.0
        party_name = "Generic Party"
        if entries:
            amount = float(entries[0].amount)
            party_name = entries[0].ledger_name

        output.append({
            "id": v.voucher_id,
            "voucher_number": v.voucher_number,
            "date": v.date.isoformat() if v.date else None,
            "party_name": party_name,
            "amount": amount,
        })
    return output


@router.get("/outstanding-payables")
async def get_outstanding_payables(
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Return outstanding purchase/supplier payable bills."""
    from app.models.payment import TrnBill
    from sqlalchemy.orm import selectinload

    # Outstanding
    stmt = (
        select(TrnBill)
        .options(selectinload(TrnBill.party))
        .where(TrnBill.company_id == user.company_id, TrnBill.status != "Settled")
    )
    res = await db.execute(stmt)
    bills = res.scalars().all()

    output = []
    for b in bills:
        outstanding = float(b.bill_amount - b.settled_amount)
        output.append({
            "id": b.bill_id,
            "ledger_name": b.party.name if b.party else "Unknown Supplier",
            "bill_reference": b.bill_reference,
            "date": b.bill_date.isoformat() if b.bill_date else None,
            "amount": outstanding,
        })
    return output


@router.get("/trial-balance")
async def get_trial_balance(
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Return group-level ledger trial balance."""
    # List all ledgers and their opening/closing balances grouped by group name
    stmt = select(MstLedger).where(MstLedger.company_id == user.company_id)
    res = await db.execute(stmt)
    ledgers = res.scalars().all()

    groups = {}
    for l in ledgers:
        bal = float(l.closing_balance if l.closing_balance is not None else l.opening_balance or 0.0)
        groups[l.group_name] = groups.get(l.group_name, 0.0) + bal

    return [
        {"name": group_name or "Other Accounts", "balance": bal}
        for group_name, bal in groups.items()
    ]

class DashboardSummaryResponse(BaseModel):
    total_sales: float
    total_receipts: float
    outstanding_receivables: float
    outstanding_payables: float

@router.get("/dashboard-summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app.core.cache import get_cached_response, set_cached_response
    cached = get_cached_response(user.company_id, "dashboard-summary")
    if cached:
        return cached

    from app.models.payment import TrnBill
    from app.models.voucher import TrnVoucher, MstVoucherType
    
    # Total Sales
    sales_query = await db.execute(
        select(func.sum(TrnVoucher.total_amount))
        .join(MstVoucherType, TrnVoucher.voucher_type_id == MstVoucherType.voucher_type_id)
        .where(
            TrnVoucher.company_id == user.company_id,
            MstVoucherType.name == "Sales",
            TrnVoucher.is_cancelled == False
        )
    )
    total_sales = sales_query.scalar() or 0.0

    # Total Receipts
    receipts_query = await db.execute(
        select(func.sum(TrnVoucher.total_amount))
        .join(MstVoucherType, TrnVoucher.voucher_type_id == MstVoucherType.voucher_type_id)
        .where(
            TrnVoucher.company_id == user.company_id,
            MstVoucherType.name == "Receipt",
            TrnVoucher.is_cancelled == False
        )
    )
    total_receipts = receipts_query.scalar() or 0
    
    from app.models.ledger import MstLedger, MstGroup
    
    # Receivables
    receivables_query = await db.execute(
        select(func.sum(TrnBill.bill_amount - TrnBill.settled_amount))
        .join(MstLedger, TrnBill.party_ledger_id == MstLedger.ledger_id)
        .join(MstGroup, MstLedger.group_id == MstGroup.group_id)
        .where(
            TrnBill.company_id == user.company_id,
            MstGroup.name == "Sundry Debtors",
            TrnBill.status != "Settled"
        )
    )
    outstanding_receivables = receivables_query.scalar() or 0
    
    # Payables
    payables_query = await db.execute(
        select(func.sum(TrnBill.bill_amount - TrnBill.settled_amount))
        .join(MstLedger, TrnBill.party_ledger_id == MstLedger.ledger_id)
        .join(MstGroup, MstLedger.group_id == MstGroup.group_id)
        .where(
            TrnBill.company_id == user.company_id,
            MstGroup.name == "Sundry Creditors",
            TrnBill.status != "Settled"
        )
    )
    outstanding_payables = payables_query.scalar() or 0.0

    res = {
        "total_sales": float(total_sales),
        "total_receipts": float(total_receipts),
        "outstanding_receivables": float(outstanding_receivables),
        "outstanding_payables": float(outstanding_payables)
    }
    set_cached_response(user.company_id, "dashboard-summary", res)
    return res

