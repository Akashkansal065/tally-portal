"""
Reports Router — comprehensive date-filtered reports with 2-hour in-memory caching.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
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
from app.core.cache import (
    get_cached_response,
    set_cached_response,
    clear_company_cache,
    clear_all_cache,
    get_cache_stats
)

router = APIRouter(prefix="/reports", tags=["Reports Hub"])


@router.post("/cache/clear")
async def clear_reports_cache(
    all_companies: bool = Query(False, description="Clear cache across all companies if true"),
    user: User = Depends(require_permission("reports", "read"))
):
    """Manually purge in-memory report cache for the current user's company (or all companies)."""
    if all_companies:
        cleared_count = clear_all_cache()
    else:
        cleared_count = clear_company_cache(user.company_id)
    return {
        "status": "success",
        "message": "Reports cache cleared successfully",
        "cleared_entries": cleared_count,
        "company_id": user.company_id if not all_companies else "all"
    }


@router.get("/cache/stats")
async def get_reports_cache_stats(
    user: User = Depends(require_permission("reports", "read"))
):
    """Return in-memory reports cache health and performance statistics."""
    return get_cache_stats()


@router.get("/daybook")
async def get_daybook(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all vouchers for the company within the date range."""
    cache_key = f"daybook_{from_date}_{to_date}"
    cached = get_cached_response(user.company_id, cache_key)
    if cached is not None:
        return cached

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

    set_cached_response(user.company_id, cache_key, output)
    return output


@router.get("/sales-register")
async def get_sales_register(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all Sales vouchers within the period."""
    cache_key = f"sales_register_{from_date}_{to_date}"
    cached = get_cached_response(user.company_id, cache_key)
    if cached is not None:
        return cached

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

    set_cached_response(user.company_id, cache_key, output)
    return output


@router.get("/outstanding-payables")
async def get_outstanding_payables(
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Return outstanding purchase/supplier payable bills."""
    cache_key = "outstanding_payables"
    cached = get_cached_response(user.company_id, cache_key)
    if cached is not None:
        return cached

    from app.models.payment import TrnBill

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

    set_cached_response(user.company_id, cache_key, output)
    return output


@router.get("/trial-balance")
async def get_trial_balance(
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Return group-level ledger trial balance with Dr/Cr balances."""
    cache_key = "trial_balance"
    cached = get_cached_response(user.company_id, cache_key)
    if cached is not None:
        return cached

    from sqlalchemy import text
    
    query = await db.execute(text("""
        SELECT g.name as group_name,
               SUM(COALESCE(l.opening_balance, 0)) as opening_sum,
               SUM(COALESCE(e.debit_amount, 0)) as total_debit,
               SUM(COALESCE(e.credit_amount, 0)) as total_credit
        FROM tally_sync.ledgers l
        JOIN tally_sync.account_groups g ON l.group_id = g.group_id
        LEFT JOIN tally_sync.voucher_entries e ON l.ledger_id = e.ledger_id
        LEFT JOIN tally_sync.vouchers v ON e.voucher_id = v.voucher_id AND v.is_cancelled = False AND v.is_optional = False
        WHERE l.company_id = :comp_id
        GROUP BY g.name
        ORDER BY ABS(SUM(COALESCE(e.debit_amount, 0)) - SUM(COALESCE(e.credit_amount, 0))) DESC
    """), {"comp_id": user.company_id})

    rows = query.all()
    results = []

    for r in rows:
        opening = float(r.opening_sum or 0.0)
        dr = float(r.total_debit or 0.0)
        cr = float(r.total_credit or 0.0)
        net = (dr - cr) + opening

        results.append({
            "name": r.group_name,
            "balance": net,
            "debit": dr,
            "credit": cr
        })

    set_cached_response(user.company_id, cache_key, results)
    return results


class DashboardSummaryResponse(BaseModel):
    total_sales: float
    total_sales_gross: Optional[float] = 0.0
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
    cache_key = f"dashboard_details_{category}"
    cached = get_cached_response(user.company_id, cache_key)
    if cached is not None:
        return cached

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
    
    output = [
        {
            "ledger_id": row.ledger_id,
            "name": row.name,
            "group_name": row.group_name,
            "balance": float(row.balance or 0.0)
        }
        for row in rows
    ]

    set_cached_response(user.company_id, cache_key, output)
    return output


@router.get("/dashboard-summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    cache_key = f"dashboard_summary_{from_date}_{to_date}"
    cached = get_cached_response(user.company_id, cache_key)
    if cached is not None:
        return cached

    from sqlalchemy import text
    
    date_where = ""
    params = {"comp_id": user.company_id}
    if from_date:
        date_where += " AND v.voucher_date >= :from_date"
        params["from_date"] = from_date
    if to_date:
        date_where += " AND v.voucher_date <= :to_date"
        params["to_date"] = to_date

    sales_query = await db.execute(text(f"""
        SELECT SUM(COALESCE(sub.net_bal, 0)) as final_bal
        FROM tally_sync.ledgers l
        JOIN tally_sync.account_groups g ON l.group_id = g.group_id
        LEFT JOIN (
            SELECT ledger_id, SUM(credit_amount) - SUM(debit_amount) as net_bal
            FROM tally_sync.voucher_entries e
            JOIN tally_sync.vouchers v ON e.voucher_id = v.voucher_id
            WHERE v.is_cancelled = False AND v.is_optional = False AND v.company_id = :comp_id {date_where}
            GROUP BY ledger_id
        ) sub ON l.ledger_id = sub.ledger_id
        WHERE g.name = 'Sales Accounts' AND l.company_id = :comp_id
    """), params)
    total_sales = sales_query.scalar() or 0.0

    gross_sales_query = await db.execute(text(f"""
        SELECT SUM(COALESCE(v.total_amount, 0)) as final_bal
        FROM tally_sync.vouchers v
        JOIN tally_sync.voucher_types vt ON v.voucher_type_id = vt.voucher_type_id
        WHERE vt.name = 'Sales' AND v.company_id = :comp_id AND v.is_cancelled = False AND v.is_optional = False {date_where}
    """), params)
    total_sales_gross = gross_sales_query.scalar() or 0.0

    receipts_query = await db.execute(text(f"""
        SELECT SUM(COALESCE(v.total_amount, 0)) as final_bal
        FROM tally_sync.vouchers v
        JOIN tally_sync.voucher_types vt ON v.voucher_type_id = vt.voucher_type_id
        WHERE vt.name = 'Receipt' AND v.company_id = :comp_id AND v.is_cancelled = False AND v.is_optional = False {date_where}
    """), params)
    total_receipts = receipts_query.scalar() or 0.0
    
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

    output = {
        "total_sales": float(total_sales),
        "total_sales_gross": float(total_sales_gross),
        "total_receipts": float(total_receipts),
        "outstanding_receivables": float(outstanding_receivables),
        "outstanding_payables": float(outstanding_payables)
    }

    set_cached_response(user.company_id, cache_key, output)
    return output


@router.get("/executive-analytics")
async def get_executive_analytics(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db)
):
    """Return aggregated trends, aging distribution, and expense category breakdown for charts within date range."""
    cache_key = f"executive_analytics_{from_date}_{to_date}"
    cached = get_cached_response(user.company_id, cache_key)
    if cached is not None:
        return cached

    from sqlalchemy import text
    from app.models.payment import TrnBill
    
    date_where = ""
    params = {"comp_id": user.company_id}
    if from_date:
        date_where += " AND v.voucher_date >= :from_date"
        params["from_date"] = from_date
    if to_date:
        date_where += " AND v.voucher_date <= :to_date"
        params["to_date"] = to_date

    trend_query = await db.execute(text(f"""
        SELECT 
            DATE_FORMAT(v.voucher_date, '%b %Y') as month_label,
            DATE_FORMAT(v.voucher_date, '%Y-%m') as sort_key,
            SUM(CASE WHEN vt.name = 'Sales' THEN v.total_amount ELSE 0 END) as sales,
            SUM(CASE WHEN vt.name = 'Receipt' THEN v.total_amount ELSE 0 END) as receipts,
            SUM(CASE WHEN vt.name = 'Purchase' THEN v.total_amount ELSE 0 END) as purchases
        FROM tally_sync.vouchers v
        JOIN tally_sync.voucher_types vt ON v.voucher_type_id = vt.voucher_type_id
        WHERE v.company_id = :comp_id AND v.is_cancelled = False AND v.is_optional = False {date_where}
        GROUP BY month_label, sort_key
        ORDER BY sort_key ASC
        LIMIT 12
    """), params)
    
    trend_rows = trend_query.all()
    monthly_trend = [
        {
            "month": r.month_label,
            "sales": float(r.sales or 0.0),
            "receipts": float(r.receipts or 0.0),
            "purchases": float(r.purchases or 0.0)
        }
        for r in trend_rows
    ]

    today_dt = date.today()
    rec_aging = {"0-30 Days": 0.0, "31-60 Days": 0.0, "61-90 Days": 0.0, "90+ Days": 0.0}
    pay_aging = {"0-30 Days": 0.0, "31-60 Days": 0.0, "61-90 Days": 0.0, "90+ Days": 0.0}

    debtors_res = await db.execute(text("""
        SELECT l.ledger_id, l.name as party_name,
               COALESCE(SUM(e.debit_amount), 0) - COALESCE(SUM(e.credit_amount), 0) as net_balance
        FROM tally_sync.ledgers l
        JOIN tally_sync.account_groups g ON l.group_id = g.group_id
        LEFT JOIN tally_sync.voucher_entries e ON l.ledger_id = e.ledger_id
        LEFT JOIN tally_sync.vouchers v ON e.voucher_id = v.voucher_id AND v.is_cancelled = False AND v.is_optional = False
        WHERE g.name = 'Sundry Debtors' AND l.company_id = :comp_id
        GROUP BY l.ledger_id, l.name
        HAVING net_balance > 0
    """), {"comp_id": user.company_id})

    rec_details = []
    for d in debtors_res.all():
        rem_bal = float(d.net_balance)
        invoices_res = await db.execute(text("""
            SELECT v.voucher_id, v.voucher_number, v.voucher_date, v.total_amount
            FROM tally_sync.vouchers v
            JOIN tally_sync.voucher_types vt ON v.voucher_type_id = vt.voucher_type_id
            JOIN tally_sync.voucher_entries e ON v.voucher_id = e.voucher_id
            WHERE e.ledger_id = :ledger_id AND vt.name = 'Sales' AND v.is_cancelled = False AND v.is_optional = False
            ORDER BY v.voucher_date DESC, v.voucher_id DESC
        """), {"ledger_id": d.ledger_id})

        for inv in invoices_res.all():
            if rem_bal <= 0:
                break
            inv_amt = float(inv.total_amount)
            allocated = min(rem_bal, inv_amt)
            days = (today_dt - inv.voucher_date).days if inv.voucher_date else 0
            bucket = "0-30 Days" if days <= 30 else ("31-60 Days" if days <= 60 else ("61-90 Days" if days <= 90 else "90+ Days"))
            rec_aging[bucket] += allocated
            rec_details.append({
                "id": inv.voucher_id,
                "voucher_number": inv.voucher_number,
                "party_name": d.party_name,
                "date": inv.voucher_date.isoformat() if inv.voucher_date else None,
                "days": days,
                "bucket": bucket,
                "amount": allocated
            })
            rem_bal -= allocated

        if rem_bal > 0:
            rec_aging["90+ Days"] += rem_bal
            rec_details.append({
                "id": 0,
                "voucher_number": "Historic Ledger Balance",
                "party_name": d.party_name,
                "date": None,
                "days": 91,
                "bucket": "90+ Days",
                "amount": rem_bal
            })

    creditors_res = await db.execute(text("""
        SELECT l.ledger_id,
               COALESCE(SUM(e.credit_amount), 0) - COALESCE(SUM(e.debit_amount), 0) as net_balance
        FROM tally_sync.ledgers l
        JOIN tally_sync.account_groups g ON l.group_id = g.group_id
        LEFT JOIN tally_sync.voucher_entries e ON l.ledger_id = e.ledger_id
        LEFT JOIN tally_sync.vouchers v ON e.voucher_id = v.voucher_id AND v.is_cancelled = False AND v.is_optional = False
        WHERE g.name = 'Sundry Creditors' AND l.company_id = :comp_id
        GROUP BY l.ledger_id
        HAVING net_balance > 0
    """), {"comp_id": user.company_id})

    for c in creditors_res.all():
        rem_bal = float(c.net_balance)
        invoices_res = await db.execute(text("""
            SELECT v.voucher_date, v.total_amount
            FROM tally_sync.vouchers v
            JOIN tally_sync.voucher_types vt ON v.voucher_type_id = vt.voucher_type_id
            JOIN tally_sync.voucher_entries e ON v.voucher_id = e.voucher_id
            WHERE e.ledger_id = :ledger_id AND vt.name = 'Purchase' AND v.is_cancelled = False AND v.is_optional = False
            ORDER BY v.voucher_date DESC, v.voucher_id DESC
        """), {"ledger_id": c.ledger_id})

        for inv in invoices_res.all():
            if rem_bal <= 0:
                break
            inv_amt = float(inv.total_amount)
            allocated = min(rem_bal, inv_amt)
            days = (today_dt - inv.voucher_date).days if inv.voucher_date else 0
            bucket = "0-30 Days" if days <= 30 else ("31-60 Days" if days <= 60 else ("61-90 Days" if days <= 90 else "90+ Days"))
            pay_aging[bucket] += allocated
            rem_bal -= allocated

        if rem_bal > 0:
            pay_aging["90+ Days"] += rem_bal

    exp_q = await db.execute(text(f"""
        SELECT g.name as category, SUM(COALESCE(e.debit_amount, 0) - COALESCE(e.credit_amount, 0)) as amount
        FROM tally_sync.voucher_entries e
        JOIN tally_sync.ledgers l ON e.ledger_id = l.ledger_id
        JOIN tally_sync.account_groups g ON l.group_id = g.group_id
        JOIN tally_sync.vouchers v ON e.voucher_id = v.voucher_id
        WHERE v.company_id = :comp_id AND v.is_cancelled = False {date_where}
          AND (g.name LIKE '%%Expense%%' OR g.name LIKE '%%Direct%%' OR g.name LIKE '%%Indirect%%' OR g.name LIKE '%%Tax%%' OR g.name LIKE '%%Bank%%')
        GROUP BY g.name
        HAVING amount > 0
        ORDER BY amount DESC
        LIMIT 6
    """), params)
    exp_rows = exp_q.all()
    expense_breakdown = [
        {"category": r.category, "amount": float(r.amount or 0.0)}
        for r in exp_rows
    ]

    output = {
        "monthly_trend": monthly_trend,
        "receivables_aging": [{"bucket": k, "amount": v} for k, v in rec_aging.items()],
        "receivables_aging_details": rec_details,
        "payables_aging": [{"bucket": k, "amount": v} for k, v in pay_aging.items()],
        "expense_breakdown": expense_breakdown
    }

    set_cached_response(user.company_id, cache_key, output)
    return output


@router.get("/top-customers")
async def get_top_customers(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db)
):
    """Return top 10 Debtors ranked by total sales volume within date range."""
    cache_key = f"top_customers_{from_date}_{to_date}"
    cached = get_cached_response(user.company_id, cache_key)
    if cached is not None:
        return cached

    from sqlalchemy import text
    date_where = ""
    params = {"comp_id": user.company_id}
    if from_date:
        date_where += " AND v.voucher_date >= :from_date"
        params["from_date"] = from_date
    if to_date:
        date_where += " AND v.voucher_date <= :to_date"
        params["to_date"] = to_date

    query = await db.execute(text(f"""
        SELECT l.ledger_id, l.name, l.gstin,
               COUNT(DISTINCT v.voucher_id) as invoice_count,
               SUM(COALESCE(e.debit_amount, 0) - COALESCE(e.credit_amount, 0)) as total_sales
        FROM tally_sync.ledgers l
        JOIN tally_sync.account_groups g ON l.group_id = g.group_id
        JOIN tally_sync.voucher_entries e ON l.ledger_id = e.ledger_id
        JOIN tally_sync.vouchers v ON e.voucher_id = v.voucher_id
        JOIN tally_sync.voucher_types vt ON v.voucher_type_id = vt.voucher_type_id
        WHERE l.company_id = :comp_id AND vt.name = 'Sales' AND v.is_cancelled = False {date_where}
        GROUP BY l.ledger_id, l.name, l.gstin
        HAVING total_sales > 0
        ORDER BY total_sales DESC
        LIMIT 10
    """), params)

    rows = query.all()
    output = [
        {
            "ledger_id": r.ledger_id,
            "name": r.name,
            "gstin": r.gstin or "N/A",
            "invoice_count": r.invoice_count,
            "total_sales": float(r.total_sales or 0.0),
            "avg_invoice": float((r.total_sales or 0) / r.invoice_count) if r.invoice_count > 0 else 0.0
        }
        for r in rows
    ]

    set_cached_response(user.company_id, cache_key, output)
    return output


@router.get("/inventory-analytics")
async def get_inventory_analytics(
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db)
):
    """Return inventory valuation by group and top valuable stock items."""
    cache_key = "inventory_analytics"
    cached = get_cached_response(user.company_id, cache_key)
    if cached is not None:
        return cached

    from app.models.inventory import MstStockItem
    
    stmt = (
        select(MstStockItem)
        .options(selectinload(MstStockItem.group), selectinload(MstStockItem.unit))
        .where(MstStockItem.company_id == user.company_id)
    )
    res = await db.execute(stmt)
    items = res.scalars().all()

    group_valuation = {}
    group_valuation_gross = {}
    item_list = []

    for item in items:
        qty = float(item.closing_qty or 0.0)
        c_rate = float(item.closing_rate or 0.0)
        val = float(item.closing_value or (qty * c_rate))
        rate = c_rate if c_rate > 0 else (val / qty if qty > 0 else float(item.opening_rate or 0.0))
        
        gst_percent = float(item.gst_rate_percent or 0.0)
        if gst_percent == 0.0:
            gst_percent = 18.0
            
        val_gross = val * (1 + gst_percent / 100.0)
        rate_gross = rate * (1 + gst_percent / 100.0)

        grp_name = item.group.name if item.group else "General Inventory"

        group_valuation[grp_name] = group_valuation.get(grp_name, 0.0) + val
        group_valuation_gross[grp_name] = group_valuation_gross.get(grp_name, 0.0) + val_gross
        
        item_list.append({
            "item_id": item.stock_item_id,
            "name": item.name,
            "group_name": grp_name,
            "quantity": qty,
            "uom": item.unit.symbol if item.unit else "PCS",
            "rate": rate,
            "rate_gross": rate_gross,
            "total_value": val,
            "total_value_gross": val_gross,
            "gst_rate_percent": gst_percent
        })

    group_chart = [
        {"group_name": k, "total_value": v, "total_value_gross": group_valuation_gross.get(k, v)}
        for k, v in group_valuation.items()
    ]

    output = {
        "group_valuation": group_chart,
        "top_items": item_list
    }

    set_cached_response(user.company_id, cache_key, output)
    return output
