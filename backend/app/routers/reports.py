"""
Reports Router — comprehensive date-filtered reports.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc, func
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.permissions import require_permission
from app.models.user import User
from app.models.voucher import TrnVoucher, TrnAccounting, MstVoucherType
from app.models.ledger import MstLedger, MstGroup

router = APIRouter(prefix="/reports", tags=["Reports Hub"])


@router.get("/daybook")
async def get_daybook(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all vouchers for the company within the date range."""
    query = select(TrnVoucher).options(
        selectinload(TrnVoucher.voucher_type),
        selectinload(TrnVoucher.entries).selectinload(TrnAccounting.ledger)
    ).where(TrnVoucher.company_id == user.company_id)
    
    if from_date:
        query = query.where(TrnVoucher.voucher_date >= date.fromisoformat(from_date))
    if to_date:
        query = query.where(TrnVoucher.voucher_date <= date.fromisoformat(to_date))

    result = await db.execute(query.order_by(desc(TrnVoucher.voucher_date)).limit(100))
    vouchers = result.scalars().all()

    output = []
    for v in vouchers:
        amount = float(v.total_amount)
        party_name = "Generic Party"
        if v.entries:
            # Try to find a ledger name from entries
            for entry in v.entries:
                if entry.ledger:
                    party_name = entry.ledger.name
                    break

        output.append({
            "id": v.voucher_id,
            "voucher_number": v.voucher_number,
            "date": v.voucher_date.isoformat() if v.voucher_date else None,
            "type": v.voucher_type.name if v.voucher_type else "Unknown",
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
    query = select(TrnVoucher).join(MstVoucherType).options(
        selectinload(TrnVoucher.voucher_type),
        selectinload(TrnVoucher.entries).selectinload(TrnAccounting.ledger)
    ).where(
        TrnVoucher.company_id == user.company_id,
        MstVoucherType.name == "Sales"
    )
    
    if from_date:
        query = query.where(TrnVoucher.voucher_date >= date.fromisoformat(from_date))
    if to_date:
        query = query.where(TrnVoucher.voucher_date <= date.fromisoformat(to_date))

    result = await db.execute(query.order_by(desc(TrnVoucher.voucher_date)).limit(100))
    vouchers = result.scalars().all()

    output = []
    for v in vouchers:
        amount = float(v.total_amount)
        party_name = "Generic Party"
        if v.entries:
            for entry in v.entries:
                if entry.ledger:
                    party_name = entry.ledger.name
                    break

        output.append({
            "id": v.voucher_id,
            "voucher_number": v.voucher_number,
            "date": v.voucher_date.isoformat() if v.voucher_date else None,
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

    # Retrieve all Open/Partially Settled purchase bills (normally bills from Suppliers)
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
    stmt = select(MstLedger).options(selectinload(MstLedger.group)).where(MstLedger.company_id == user.company_id)
    res = await db.execute(stmt)
    ledgers = res.scalars().all()

    groups = {}
    for l in ledgers:
        # Use opening balance as fallback
        bal = float(l.opening_balance or 0.0)
        group_name = l.group.name if l.group else "Other Accounts"
        groups[group_name] = groups.get(group_name, 0.0) + bal

    return [
        {"name": group_name, "balance": bal}
        for group_name, bal in groups.items()
    ]


class DashboardSummaryResponse(BaseModel):
    total_sales: float
    total_receipts: float
    outstanding_receivables: float
    outstanding_payables: float


class DashboardDetailItem(BaseModel):
    ledger_id: int
    name: str
    group_name: str
    balance: float


@router.get("/dashboard-details", response_model=List[DashboardDetailItem])
async def get_dashboard_details(
    category: str,
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import text
    
    if category == "sales":
        query_str = """
            SELECT l.ledger_id, l.name, g.name as group_name,
                   COALESCE(sub.net_bal, 0) as balance
            FROM tally_sync.ledgers l
            JOIN tally_sync.account_groups g ON l.group_id = g.group_id
            LEFT JOIN (
                SELECT ledger_id, SUM(credit_amount) - SUM(debit_amount) as net_bal
                FROM tally_sync.voucher_entries e
                JOIN tally_sync.vouchers v ON e.voucher_id = v.voucher_id
                WHERE v.is_cancelled = False AND v.is_optional = False AND v.company_id = :comp_id
                GROUP BY ledger_id
            ) sub ON l.ledger_id = sub.ledger_id
            WHERE g.name = 'Sales Accounts' AND l.company_id = :comp_id
            ORDER BY balance DESC
        """
    elif category == "receipts":
        query_str = """
            SELECT l.ledger_id, l.name, g.name as group_name,
                   COALESCE(sub.net_bal, 0) as balance
            FROM tally_sync.ledgers l
            JOIN tally_sync.account_groups g ON l.group_id = g.group_id
            LEFT JOIN (
                SELECT ledger_id, SUM(debit_amount) - SUM(credit_amount) as net_bal
                FROM tally_sync.voucher_entries e
                JOIN tally_sync.vouchers v ON e.voucher_id = v.voucher_id
                WHERE v.is_cancelled = False AND v.is_optional = False AND v.company_id = :comp_id
                GROUP BY ledger_id
            ) sub ON l.ledger_id = sub.ledger_id
            WHERE g.name IN ('Cash-in-hand', 'Bank Accounts') AND l.company_id = :comp_id
            ORDER BY balance DESC
        """
    elif category == "receivables":
        query_str = """
            SELECT l.ledger_id, l.name, g.name as group_name,
                   COALESCE(sub.net_bal, 0) as balance
            FROM tally_sync.ledgers l
            JOIN tally_sync.account_groups g ON l.group_id = g.group_id
            LEFT JOIN (
                SELECT ledger_id, SUM(debit_amount) - SUM(credit_amount) as net_bal
                FROM tally_sync.voucher_entries e
                JOIN tally_sync.vouchers v ON e.voucher_id = v.voucher_id
                WHERE v.is_cancelled = False AND v.is_optional = False AND v.company_id = :comp_id
                GROUP BY ledger_id
            ) sub ON l.ledger_id = sub.ledger_id
            WHERE g.name = 'Sundry Debtors' AND l.company_id = :comp_id
            ORDER BY balance DESC
        """
    elif category == "payables":
        query_str = """
            SELECT l.ledger_id, l.name, g.name as group_name,
                   COALESCE(sub.net_bal, 0) as balance
            FROM tally_sync.ledgers l
            JOIN tally_sync.account_groups g ON l.group_id = g.group_id
            LEFT JOIN (
                SELECT ledger_id, SUM(credit_amount) - SUM(debit_amount) as net_bal
                FROM tally_sync.voucher_entries e
                JOIN tally_sync.vouchers v ON e.voucher_id = v.voucher_id
                WHERE v.is_cancelled = False AND v.is_optional = False AND v.company_id = :comp_id
                GROUP BY ledger_id
            ) sub ON l.ledger_id = sub.ledger_id
            WHERE g.name = 'Sundry Creditors' AND l.company_id = :comp_id
            ORDER BY balance DESC
        """
    else:
        raise HTTPException(status_code=400, detail="Invalid category requested.")

    res = await db.execute(text(query_str), {"comp_id": user.company_id})
    rows = res.all()
    
    return [
        {
            "ledger_id": row.ledger_id,
            "name": row.name,
            "group_name": row.group_name,
            "balance": float(row.balance or 0.0)
        }
        for row in rows
    ]


@router.get("/dashboard-summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app.core.cache import get_cached_response, set_cached_response
    # cached = get_cached_response(user.company_id, "dashboard-summary")
    # if cached:
    #     return cached

    # Calculate exact closing balances for Ledgers
    from sqlalchemy import text
    
    # Total Sales (from Sales Accounts, Net Credit Balance)
    sales_query = await db.execute(text("""
        SELECT SUM(COALESCE(sub.net_bal, 0)) as final_bal
        FROM tally_sync.ledgers l
        JOIN tally_sync.account_groups g ON l.group_id = g.group_id
        LEFT JOIN (
            SELECT ledger_id, SUM(credit_amount) - SUM(debit_amount) as net_bal
            FROM tally_sync.voucher_entries e
            JOIN tally_sync.vouchers v ON e.voucher_id = v.voucher_id
            WHERE v.is_cancelled = False AND v.is_optional = False AND v.company_id = :comp_id
            GROUP BY ledger_id
        ) sub ON l.ledger_id = sub.ledger_id
        WHERE g.name = 'Sales Accounts' AND l.company_id = :comp_id
    """), {"comp_id": user.company_id})
    total_sales = sales_query.scalar() or 0.0

    # Total Receipts (Cash/Bank Accounts, Net Debit Balance)
    receipts_query = await db.execute(text("""
        SELECT SUM(COALESCE(sub.net_bal, 0)) as final_bal
        FROM tally_sync.ledgers l
        JOIN tally_sync.account_groups g ON l.group_id = g.group_id
        LEFT JOIN (
            SELECT ledger_id, SUM(debit_amount) - SUM(credit_amount) as net_bal
            FROM tally_sync.voucher_entries e
            JOIN tally_sync.vouchers v ON e.voucher_id = v.voucher_id
            WHERE v.is_cancelled = False AND v.is_optional = False AND v.company_id = :comp_id
            GROUP BY ledger_id
        ) sub ON l.ledger_id = sub.ledger_id
        WHERE g.name IN ('Cash-in-hand', 'Bank Accounts') AND l.company_id = :comp_id
    """), {"comp_id": user.company_id})
    total_receipts = receipts_query.scalar() or 0.0
    
    # Receivables: Sum of (Dr Balances) for Sundry Debtors
    receivables_query = await db.execute(text("""
        SELECT SUM(COALESCE(sub.net_bal, 0)) as final_bal
        FROM tally_sync.ledgers l
        JOIN tally_sync.account_groups g ON l.group_id = g.group_id
        LEFT JOIN (
            SELECT ledger_id, SUM(debit_amount) - SUM(credit_amount) as net_bal
            FROM tally_sync.voucher_entries e
            JOIN tally_sync.vouchers v ON e.voucher_id = v.voucher_id
            WHERE v.is_cancelled = False AND v.is_optional = False AND v.company_id = :comp_id
            GROUP BY ledger_id
        ) sub ON l.ledger_id = sub.ledger_id
        WHERE g.name = 'Sundry Debtors' AND l.company_id = :comp_id
    """), {"comp_id": user.company_id})
    outstanding_receivables = receivables_query.scalar() or 0.0
    
    # Payables: Sum of (Cr Balances) for Sundry Creditors
    payables_query = await db.execute(text("""
        SELECT SUM(COALESCE(sub.net_bal, 0)) as final_bal
        FROM tally_sync.ledgers l
        JOIN tally_sync.account_groups g ON l.group_id = g.group_id
        LEFT JOIN (
            SELECT ledger_id, SUM(credit_amount) - SUM(debit_amount) as net_bal
            FROM tally_sync.voucher_entries e
            JOIN tally_sync.vouchers v ON e.voucher_id = v.voucher_id
            WHERE v.is_cancelled = False AND v.is_optional = False AND v.company_id = :comp_id
            GROUP BY ledger_id
        ) sub ON l.ledger_id = sub.ledger_id
        WHERE g.name = 'Sundry Creditors' AND l.company_id = :comp_id
    """), {"comp_id": user.company_id})
    outstanding_payables = payables_query.scalar() or 0.0

    res = {
        "total_sales": float(total_sales),
        "total_receipts": float(total_receipts),
        "outstanding_receivables": float(outstanding_receivables),
        "outstanding_payables": float(outstanding_payables)
    }
    set_cached_response(user.company_id, "dashboard-summary", res)
    return res
