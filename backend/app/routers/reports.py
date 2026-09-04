"""
Reports Router — comprehensive date-filtered reports with 2-hour in-memory caching.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc, func
from pydantic import BaseModel
from typing import Optional, List, Tuple, Dict, Any, Union
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.permissions import require_permission
from app.models.portal_core import User
from app.models.portal_core import Company
from app.models.tally_core import TrnVoucher, TrnAccounting, MstVoucherType
from app.models.tally_core import MstLedger, MstGroup
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


def resolve_voucher_party_and_amount(v: TrnVoucher) -> Tuple[str, float]:
    """Extract true party name and net invoice payable/receivable amount deducting discounts."""
    if not v.entries:
        return "Generic Party", float(v.total_amount or 0.0)

    best_entry = None
    best_score = -100

    for entry in v.entries:
        if not entry.ledger:
            continue
        gname = (entry.ledger.group.name if entry.ledger.group else "").lower()
        lname = (entry.ledger.name or "").lower()

        score = 0
        if "debtors" in gname or "creditors" in gname:
            score = 10
        elif "bank" in gname or "cash" in gname:
            score = 5
        elif "sales" in gname or "purchase" in gname or "tax" in gname or "duty" in gname or "round" in lname or "discount" in lname:
            score = -10
        else:
            score = 1

        if score > best_score:
            best_score = score
            best_entry = entry

    if best_entry and best_entry.ledger:
        p_name = best_entry.ledger.name
        damt = float(best_entry.debit_amount or 0.0)
        camt = float(best_entry.credit_amount or 0.0)
        p_amt = damt if damt > 0 else camt
        if p_amt > 0:
            return p_name, p_amt

    return "Generic Party", float(v.total_amount or 0.0)


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
        selectinload(TrnVoucher.entries).selectinload(TrnAccounting.ledger).selectinload(MstLedger.group)
    ).where(TrnVoucher.company_id == user.company_id)
    
    if from_date:
        query = query.where(TrnVoucher.voucher_date >= date.fromisoformat(from_date))
    if to_date:
        query = query.where(TrnVoucher.voucher_date <= date.fromisoformat(to_date))

    result = await db.execute(query.order_by(desc(TrnVoucher.voucher_date)))
    vouchers = result.scalars().all()

    output = []
    for v in vouchers:
        party_name, amount = resolve_voucher_party_and_amount(v)
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
        selectinload(TrnVoucher.entries).selectinload(TrnAccounting.ledger).selectinload(MstLedger.group)
    ).where(
        TrnVoucher.company_id == user.company_id,
        MstVoucherType.name == "Sales"
    )
    
    if from_date:
        query = query.where(TrnVoucher.voucher_date >= date.fromisoformat(from_date))
    if to_date:
        query = query.where(TrnVoucher.voucher_date <= date.fromisoformat(to_date))

    result = await db.execute(query.order_by(desc(TrnVoucher.voucher_date)))
    vouchers = result.scalars().all()

    output = []
    for v in vouchers:
        party_name, amount = resolve_voucher_party_and_amount(v)
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

    from app.models.tally_core import TrnBill

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
               SUM(COALESCE(sub.total_debit, 0)) as total_debit,
               SUM(COALESCE(sub.total_credit, 0)) as total_credit
        FROM tally_sync.ledgers l
        JOIN tally_sync.account_groups g ON l.group_id = g.group_id
        LEFT JOIN (
            SELECT e.ledger_id,
                   SUM(e.debit_amount) as total_debit,
                   SUM(e.credit_amount) as total_credit
            FROM tally_sync.voucher_entries e
            JOIN tally_sync.vouchers v ON e.voucher_id = v.voucher_id
            WHERE COALESCE(v.is_cancelled, FALSE) = FALSE AND COALESCE(v.is_optional, FALSE) = FALSE AND v.company_id = :comp_id
            GROUP BY e.ledger_id
        ) sub ON l.ledger_id = sub.ledger_id
        WHERE l.company_id = :comp_id
        GROUP BY g.name
        ORDER BY g.name
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
    total_purchases: Optional[float] = 0.0
    total_payments: Optional[float] = 0.0
    outstanding_receivables: float
    outstanding_payables: float
    company_name: Optional[str] = None
    current_period: Optional[str] = None
    current_period_start: Optional[str] = None
    current_period_end: Optional[str] = None
    current_date: Optional[str] = None
    date_of_last_entry: Optional[str] = None


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
                WHERE COALESCE(v.is_cancelled, FALSE) = FALSE AND COALESCE(v.is_optional, FALSE) = FALSE AND v.company_id = :comp_id
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
                WHERE COALESCE(v.is_cancelled, FALSE) = FALSE AND COALESCE(v.is_optional, FALSE) = FALSE AND v.company_id = :comp_id
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
                WHERE COALESCE(v.is_cancelled, FALSE) = FALSE AND COALESCE(v.is_optional, FALSE) = FALSE AND v.company_id = :comp_id
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
                WHERE COALESCE(v.is_cancelled, FALSE) = FALSE AND COALESCE(v.is_optional, FALSE) = FALSE AND v.company_id = :comp_id
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
    from datetime import date, timedelta

    # 1. Fetch Company & Financial Year details
    comp_stmt = select(Company).where(Company.company_id == user.company_id)
    comp_res = await db.execute(comp_stmt)
    company = comp_res.scalars().first()
    comp_name = company.name if company else "Company"

    # Calculate default Indian Financial Year (April 1 to March 31)
    today = date.today()
    curr_fy_year = today.year if today.month >= 4 else today.year - 1
    fy_start = getattr(company, 'financial_year_start', None) or date(curr_fy_year, 4, 1)
    if isinstance(fy_start, date) and fy_start.month != 4:
        fy_start = date(curr_fy_year, 4, 1)
        
    fy_end = getattr(company, 'financial_year_end', None)
    if not fy_end or (isinstance(fy_end, date) and fy_end.month != 3):
        fy_end = date(fy_start.year + 1, 3, 31)

    def format_tally_date(d: date, full_year: bool = False) -> str:
        if not d: return ""
        yr = str(d.year) if full_year else str(d.year)[-2:]
        return f"{d.day}-{d.strftime('%b')}-{yr}"

    # Parse active or requested date range for current_period display string
    req_from = datetime.strptime(from_date, "%Y-%m-%d").date() if from_date else fy_start
    req_to = datetime.strptime(to_date, "%Y-%m-%d").date() if to_date else fy_end

    curr_period_start = format_tally_date(req_from)
    curr_period_end = format_tally_date(req_to)
    current_period_str = f"{curr_period_start} to {curr_period_end}"

    today = date.today()
    current_date_str = f"{today.strftime('%A')}, {format_tally_date(today, full_year=True)}"

    # 2. Fetch Date of Last Entry from database (tally_sync.vouchers)
    last_entry_stmt = text("""
        SELECT MAX(voucher_date) FROM tally_sync.vouchers 
        WHERE company_id = :comp_id AND COALESCE(is_cancelled, FALSE) = FALSE
    """)
    last_entry_res = await db.execute(last_entry_stmt, {"comp_id": user.company_id})
    last_date = last_entry_res.scalar()
    date_of_last_entry_str = format_tally_date(last_date) if last_date else "No Entries"

    # Default date filters to Current Period if not specified
    if not from_date:
        from_date = fy_start.strftime("%Y-%m-%d")
    if not to_date:
        to_date = fy_end.strftime("%Y-%m-%d")
    
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
            WHERE COALESCE(v.is_cancelled, FALSE) = FALSE AND COALESCE(v.is_optional, FALSE) = FALSE AND v.company_id = :comp_id {date_where}
            GROUP BY ledger_id
        ) sub ON l.ledger_id = sub.ledger_id
        WHERE g.name = 'Sales Accounts' AND l.company_id = :comp_id
    """), params)
    total_sales = sales_query.scalar() or 0.0

    gross_sales_query = await db.execute(text(f"""
        SELECT SUM(COALESCE(e.debit_amount - e.credit_amount, 0)) as final_bal
        FROM tally_sync.voucher_entries e
        JOIN tally_sync.vouchers v ON e.voucher_id = v.voucher_id
        JOIN tally_sync.voucher_types vt ON v.voucher_type_id = vt.voucher_type_id
        JOIN tally_sync.ledgers l ON e.ledger_id = l.ledger_id
        JOIN tally_sync.account_groups g ON l.group_id = g.group_id
        WHERE vt.name = 'Sales'
          AND g.name IN ('Sundry Debtors', 'Cash-in-hand', 'Bank Accounts', 'Sundry Creditors', 'Primary')
          AND v.company_id = :comp_id AND COALESCE(v.is_cancelled, FALSE) = FALSE AND COALESCE(v.is_optional, FALSE) = FALSE {date_where}
    """), params)
    total_sales_gross = gross_sales_query.scalar() or 0.0

    receipts_query = await db.execute(text(f"""
        SELECT SUM(COALESCE(v.total_amount, 0)) as final_bal
        FROM tally_sync.vouchers v
        JOIN tally_sync.voucher_types vt ON v.voucher_type_id = vt.voucher_type_id
        WHERE vt.name = 'Receipt' AND v.company_id = :comp_id AND COALESCE(v.is_cancelled, FALSE) = FALSE AND COALESCE(v.is_optional, FALSE) = FALSE {date_where}
    """), params)
    total_receipts = receipts_query.scalar() or 0.0

    purchases_query = await db.execute(text(f"""
        SELECT SUM(COALESCE(e.credit_amount - e.debit_amount, 0)) as final_bal
        FROM tally_sync.voucher_entries e
        JOIN tally_sync.vouchers v ON e.voucher_id = v.voucher_id
        JOIN tally_sync.voucher_types vt ON v.voucher_type_id = vt.voucher_type_id
        JOIN tally_sync.ledgers l ON e.ledger_id = l.ledger_id
        JOIN tally_sync.account_groups g ON l.group_id = g.group_id
        WHERE vt.name = 'Purchase'
          AND g.name IN ('Sundry Creditors', 'Cash-in-hand', 'Bank Accounts', 'Sundry Debtors', 'Primary')
          AND v.company_id = :comp_id AND COALESCE(v.is_cancelled, FALSE) = FALSE AND COALESCE(v.is_optional, FALSE) = FALSE {date_where}
    """), params)
    total_purchases = purchases_query.scalar() or 0.0

    payments_query = await db.execute(text(f"""
        SELECT SUM(COALESCE(v.total_amount, 0)) as final_bal
        FROM tally_sync.vouchers v
        JOIN tally_sync.voucher_types vt ON v.voucher_type_id = vt.voucher_type_id
        WHERE vt.name = 'Payment' AND v.company_id = :comp_id AND COALESCE(v.is_cancelled, FALSE) = FALSE AND COALESCE(v.is_optional, FALSE) = FALSE {date_where}
    """), params)
    total_payments = payments_query.scalar() or 0.0
    
    receivables_query = await db.execute(text("""
        SELECT SUM(COALESCE(sub.net_bal, 0)) as final_bal
        FROM tally_sync.ledgers l
        JOIN tally_sync.account_groups g ON l.group_id = g.group_id
        LEFT JOIN (
            SELECT ledger_id, SUM(debit_amount) - SUM(credit_amount) as net_bal
            FROM tally_sync.voucher_entries e
            JOIN tally_sync.vouchers v ON e.voucher_id = v.voucher_id
            WHERE COALESCE(v.is_cancelled, FALSE) = FALSE AND COALESCE(v.is_optional, FALSE) = FALSE AND v.company_id = :comp_id
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
            WHERE COALESCE(v.is_cancelled, FALSE) = FALSE AND COALESCE(v.is_optional, FALSE) = FALSE AND v.company_id = :comp_id
            GROUP BY ledger_id
        ) sub ON l.ledger_id = sub.ledger_id
        WHERE g.name = 'Sundry Creditors' AND l.company_id = :comp_id
    """), {"comp_id": user.company_id})
    outstanding_payables = payables_query.scalar() or 0.0

    output = {
        "total_sales": float(total_sales),
        "total_sales_gross": float(total_sales_gross),
        "total_receipts": float(total_receipts),
        "total_purchases": float(total_purchases),
        "total_payments": float(total_payments),
        "outstanding_receivables": float(outstanding_receivables),
        "outstanding_payables": float(outstanding_payables),
        "company_name": comp_name,
        "current_period": current_period_str,
        "current_period_start": curr_period_start,
        "current_period_end": curr_period_end,
        "current_date": current_date_str,
        "date_of_last_entry": date_of_last_entry_str
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
    from app.models.tally_core import TrnBill
    
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
        WHERE v.company_id = :comp_id AND COALESCE(v.is_cancelled, FALSE) = FALSE AND COALESCE(v.is_optional, FALSE) = FALSE {date_where}
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

    from app.models.tally_core import MstGroup
    from datetime import timedelta

    # 1. Resolve Debtors & Creditors group hierarchies
    all_groups_res = await db.execute(
        select(MstGroup).where(MstGroup.company_id == user.company_id)
    )
    all_groups = all_groups_res.scalars().all()
    debtor_group_ids = set()
    creditor_group_ids = set()

    for g in all_groups:
        name_lower = g.name.strip().lower()
        if name_lower == "sundry debtors":
            debtor_group_ids.add(g.group_id)
        elif name_lower == "sundry creditors":
            creditor_group_ids.add(g.group_id)

    changed = True
    while changed:
        changed = False
        for g in all_groups:
            if g.parent_group_id in debtor_group_ids and g.group_id not in debtor_group_ids:
                debtor_group_ids.add(g.group_id)
                changed = True
            if g.parent_group_id in creditor_group_ids and g.group_id not in creditor_group_ids:
                creditor_group_ids.add(g.group_id)
                changed = True

    deb_ids_str = ",".join(str(gid) for gid in (debtor_group_ids or {0}))
    cred_ids_str = ",".join(str(gid) for gid in (creditor_group_ids or {0}))

    # 2. Query all Debtors with Net Balance strictly from voucher entries (Debits - Credits)
    debtors_res = await db.execute(text(f"""
        SELECT 
            l.ledger_id, 
            l.name as party_name,
            l.credit_period_days,
            COALESCE(SUM(e.debit_amount), 0) as total_debit,
            COALESCE(SUM(e.credit_amount), 0) as total_credit
        FROM tally_sync.ledgers l
        LEFT JOIN tally_sync.voucher_entries e ON l.ledger_id = e.ledger_id
        LEFT JOIN tally_sync.vouchers v ON e.voucher_id = v.voucher_id AND COALESCE(v.is_cancelled, FALSE) = FALSE AND COALESCE(v.is_optional, FALSE) = FALSE
        WHERE l.company_id = :comp_id AND l.group_id IN ({deb_ids_str})
        GROUP BY l.ledger_id, l.name, l.credit_period_days
    """), {"comp_id": user.company_id})

    rec_details = []
    for d in debtors_res.all():
        net_bal = float(d.total_debit) - float(d.total_credit)
        if net_bal <= 0.01:
            continue

        rem_bal = net_bal
        credit_period = d.credit_period_days or 0

        invoices_res = await db.execute(text("""
            SELECT v.voucher_id, v.voucher_number, v.voucher_date, v.total_amount
            FROM tally_sync.vouchers v
            JOIN tally_sync.voucher_types vt ON v.voucher_type_id = vt.voucher_type_id
            JOIN tally_sync.voucher_entries e ON v.voucher_id = e.voucher_id
            WHERE e.ledger_id = :ledger_id AND vt.name = 'Sales' AND COALESCE(v.is_cancelled, FALSE) = FALSE AND COALESCE(v.is_optional, FALSE) = FALSE
            ORDER BY v.voucher_date DESC, v.voucher_id DESC
        """), {"ledger_id": d.ledger_id})

        for inv in invoices_res.all():
            if rem_bal <= 0.001:
                break
            inv_amt = float(inv.total_amount or 0.0)
            allocated = min(rem_bal, inv_amt)
            if allocated <= 0:
                continue

            inv_date = inv.voucher_date
            effective_due_date = inv_date + timedelta(days=credit_period) if inv_date else None
            days_overdue = (today_dt - effective_due_date).days if effective_due_date else 0
            days_overdue = max(0, days_overdue)

            if days_overdue <= 30:
                bucket = "0-30 Days"
            elif days_overdue <= 60:
                bucket = "31-60 Days"
            elif days_overdue <= 90:
                bucket = "61-90 Days"
            else:
                bucket = "90+ Days"

            rec_aging[bucket] += allocated
            rec_details.append({
                "id": inv.voucher_id,
                "voucher_number": inv.voucher_number,
                "party_name": d.party_name,
                "ledger_id": d.ledger_id,
                "date": inv_date.isoformat() if inv_date else None,
                "days": days_overdue,
                "bucket": bucket,
                "amount": allocated
            })
            rem_bal -= allocated

        if rem_bal > 0.01:
            rec_aging["90+ Days"] += rem_bal
            rec_details.append({
                "id": 0,
                "voucher_number": "Historic Ledger Balance",
                "party_name": d.party_name,
                "ledger_id": d.ledger_id,
                "date": None,
                "days": 91,
                "bucket": "90+ Days",
                "amount": rem_bal
            })

    # 3. Query all Creditors with Net Balance strictly from voucher entries (Credits - Debits)
    creditors_res = await db.execute(text(f"""
        SELECT 
            l.ledger_id, 
            l.name as party_name,
            l.credit_period_days,
            COALESCE(SUM(e.debit_amount), 0) as total_debit,
            COALESCE(SUM(e.credit_amount), 0) as total_credit
        FROM tally_sync.ledgers l
        LEFT JOIN tally_sync.voucher_entries e ON l.ledger_id = e.ledger_id
        LEFT JOIN tally_sync.vouchers v ON e.voucher_id = v.voucher_id AND COALESCE(v.is_cancelled, FALSE) = FALSE AND COALESCE(v.is_optional, FALSE) = FALSE
        WHERE l.company_id = :comp_id AND l.group_id IN ({cred_ids_str})
        GROUP BY l.ledger_id, l.name, l.credit_period_days
    """), {"comp_id": user.company_id})

    for c in creditors_res.all():
        net_bal = float(c.total_credit) - float(c.total_debit)
        if net_bal <= 0.01:
            continue

        rem_bal = net_bal
        credit_period = c.credit_period_days or 0

        invoices_res = await db.execute(text("""
            SELECT v.voucher_date, v.total_amount
            FROM tally_sync.vouchers v
            JOIN tally_sync.voucher_types vt ON v.voucher_type_id = vt.voucher_type_id
            JOIN tally_sync.voucher_entries e ON v.voucher_id = e.voucher_id
            WHERE e.ledger_id = :ledger_id AND vt.name = 'Purchase' AND COALESCE(v.is_cancelled, FALSE) = FALSE AND COALESCE(v.is_optional, FALSE) = FALSE
            ORDER BY v.voucher_date DESC, v.voucher_id DESC
        """), {"ledger_id": c.ledger_id})

        for inv in invoices_res.all():
            if rem_bal <= 0.001:
                break
            inv_amt = float(inv.total_amount or 0.0)
            allocated = min(rem_bal, inv_amt)
            if allocated <= 0:
                continue

            inv_date = inv.voucher_date
            effective_due_date = inv_date + timedelta(days=credit_period) if inv_date else None
            days_overdue = (today_dt - effective_due_date).days if effective_due_date else 0
            days_overdue = max(0, days_overdue)

            if days_overdue <= 30:
                bucket = "0-30 Days"
            elif days_overdue <= 60:
                bucket = "31-60 Days"
            elif days_overdue <= 90:
                bucket = "61-90 Days"
            else:
                bucket = "90+ Days"

            pay_aging[bucket] += allocated
            rem_bal -= allocated

        if rem_bal > 0.01:
            pay_aging["90+ Days"] += rem_bal

    exp_q = await db.execute(text(f"""
        SELECT g.name as category, SUM(COALESCE(e.debit_amount, 0) - COALESCE(e.credit_amount, 0)) as amount
        FROM tally_sync.voucher_entries e
        JOIN tally_sync.ledgers l ON e.ledger_id = l.ledger_id
        JOIN tally_sync.account_groups g ON l.group_id = g.group_id
        JOIN tally_sync.vouchers v ON e.voucher_id = v.voucher_id
        WHERE v.company_id = :comp_id AND COALESCE(v.is_cancelled, FALSE) = FALSE {date_where}
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

    from app.models.tally_core import MstStockItem
    
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


@router.get("/profit-loss")
@router.get("/profit-and-loss")
@router.get("/pnl")
async def get_profit_and_loss(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Return Profit & Loss summary categorized into Trading and Indirect expenses/incomes."""
    cache_key = f"pnl_{from_date}_{to_date}"
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

    # Query groups and ledger net balances matching Tally group names
    query = await db.execute(text(f"""
        SELECT g.name as group_name, l.name as ledger_name,
               SUM(COALESCE(e.credit_amount, 0) - COALESCE(e.debit_amount, 0)) as net_credit
        FROM tally_sync.ledgers l
        JOIN tally_sync.account_groups g ON l.group_id = g.group_id
        LEFT JOIN tally_sync.voucher_entries e ON l.ledger_id = e.ledger_id
        LEFT JOIN tally_sync.vouchers v ON e.voucher_id = v.voucher_id AND COALESCE(v.is_cancelled, FALSE) = FALSE AND COALESCE(v.is_optional, FALSE) = FALSE {date_where}
        WHERE l.company_id = :comp_id AND (
            g.name IN ('Sales Accounts', 'Purchase Accounts', 'Direct Expenses', 'Indirect Expenses', 'Direct Incomes', 'Indirect Incomes')
            OR g.name LIKE '%Sales%' OR g.name LIKE '%Purchase%' OR g.name LIKE '%Expense%' OR g.name LIKE '%Income%'
        )
        GROUP BY g.name, l.name
        HAVING net_credit <> 0
        ORDER BY g.name, l.name
    """), params)

    rows = query.all()
    
    trading_income = []
    trading_expenses = []
    indirect_income = []
    indirect_expenses = []
    
    total_sales = 0.0
    total_cogs = 0.0
    total_ind_income = 0.0
    total_ind_expenses = 0.0

    for r in rows:
        amount = float(r.net_credit or 0.0)
        gname = (r.group_name or '').lower()
        item = {"ledger": r.ledger_name, "group": r.group_name, "amount": abs(amount)}
        
        if 'sales' in gname or 'direct income' in gname:
            trading_income.append(item)
            total_sales += amount
        elif 'indirect income' in gname:
            indirect_income.append(item)
            total_ind_income += amount
        elif 'purchase' in gname or 'direct expense' in gname:
            exp_amount = -amount # Debit - Credit
            item["amount"] = abs(exp_amount)
            trading_expenses.append(item)
            total_cogs += exp_amount
        else: # Indirect Expenses
            exp_amount = -amount
            item["amount"] = abs(exp_amount)
            indirect_expenses.append(item)
            total_ind_expenses += exp_amount

    gross_profit = total_sales - total_cogs
    net_profit = gross_profit + total_ind_income - total_ind_expenses

    results = {
        "trading_income": trading_income,
        "trading_expenses": trading_expenses,
        "indirect_income": indirect_income,
        "indirect_expenses": indirect_expenses,
        "total_sales": total_sales,
        "total_cogs": total_cogs,
        "gross_profit": gross_profit,
        "total_indirect_income": total_ind_income,
        "total_indirect_expenses": total_ind_expenses,
        "net_profit": net_profit,
    }

    set_cached_response(user.company_id, cache_key, results)
    return results


@router.get("/balance-sheet")
async def get_balance_sheet(
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Return Balance Sheet with Assets, Liabilities, Capital, and Net Working Capital."""
    cache_key = "balance_sheet"
    cached = get_cached_response(user.company_id, cache_key)
    if cached is not None:
        return cached

    from sqlalchemy import text

    query = await db.execute(text("""
        SELECT g.name as group_name, l.name as ledger_name,
               COALESCE(l.opening_balance, 0) as open_bal,
               COALESCE(sub.total_debit, 0) as total_debit,
               COALESCE(sub.total_credit, 0) as total_credit
        FROM tally_sync.ledgers l
        JOIN tally_sync.account_groups g ON l.group_id = g.group_id
        LEFT JOIN (
            SELECT e.ledger_id,
                   SUM(e.debit_amount) as total_debit,
                   SUM(e.credit_amount) as total_credit
            FROM tally_sync.voucher_entries e
            JOIN tally_sync.vouchers v ON e.voucher_id = v.voucher_id
            WHERE COALESCE(v.is_cancelled, FALSE) = FALSE AND COALESCE(v.is_optional, FALSE) = FALSE AND v.company_id = :comp_id
            GROUP BY e.ledger_id
        ) sub ON l.ledger_id = sub.ledger_id
        WHERE l.company_id = :comp_id AND (
            g.name IN ('Current Assets', 'Bank Accounts', 'Cash-in-Hand', 'Sundry Debtors', 'Stock-in-Hand', 'Fixed Assets', 'Investments', 'Deposits (Asset)', 'Loans & Advances (Asset)',
                       'Current Liabilities', 'Sundry Creditors', 'Duties & Taxes', 'Capital Account', 'Loans (Liability)', 'Unsecured Loans', 'Secured Loans', 'Provisions', 'Reserves & Surplus')
            OR g.name LIKE '%Asset%' OR g.name LIKE '%Liability%' OR g.name LIKE '%Loan%' OR g.name LIKE '%Capital%' OR g.name LIKE '%Debtor%' OR g.name LIKE '%Creditor%' OR g.name LIKE '%Tax%'
        )
        HAVING (open_bal + total_debit + total_credit) <> 0
        ORDER BY g.name, l.name
    """), {"comp_id": user.company_id})

    rows = query.all()

    assets = []
    liabilities = []
    total_assets = 0.0
    total_liabilities = 0.0

    for r in rows:
        gname = (r.group_name or '').lower()
        open_bal = float(r.open_bal or 0.0)
        debit = float(r.total_debit or 0.0)
        credit = float(r.total_credit or 0.0)

        is_naturally_asset = any(k in gname for k in ['asset', 'bank', 'cash', 'debtor', 'stock', 'investment', 'deposit']) and 'liability' not in gname

        if is_naturally_asset:
            net_val = open_bal + debit - credit
            if net_val >= 0:
                assets.append({'ledger': r.ledger_name, 'group': r.group_name, 'amount': net_val})
                total_assets += net_val
            else:
                liabilities.append({'ledger': r.ledger_name, 'group': r.group_name, 'amount': -net_val})
                total_liabilities += (-net_val)
        else: # Liability or Capital Account
            net_val = open_bal + credit - debit
            if net_val >= 0:
                liabilities.append({'ledger': r.ledger_name, 'group': r.group_name, 'amount': net_val})
                total_liabilities += net_val
            else:
                assets.append({'ledger': r.ledger_name, 'group': r.group_name, 'amount': -net_val})
                total_assets += (-net_val)

    results = {
        "assets": assets,
        "liabilities": liabilities,
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "working_capital": total_assets - total_liabilities
    }

    set_cached_response(user.company_id, cache_key, results)
    return results


@router.get("/cash-flow")
async def get_cash_flow(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Return Cash Flow Statement categorized by Operating, Investing, and Financing activities."""
    cache_key = f"cash_flow_{from_date}_{to_date}"
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
        SELECT vt.name as voucher_type, SUM(v.total_amount) as total_amt
        FROM tally_sync.vouchers v
        JOIN tally_sync.voucher_types vt ON v.voucher_type_id = vt.voucher_type_id
        WHERE v.company_id = :comp_id AND COALESCE(v.is_cancelled, FALSE) = FALSE AND COALESCE(v.is_optional, FALSE) = FALSE {date_where}
        GROUP BY vt.name
    """), params)

    rows = query.all()

    inflow_receipts = 0.0
    inflow_sales = 0.0
    outflow_payments = 0.0
    outflow_purchases = 0.0

    for r in rows:
        amt = float(r.total_amt or 0.0)
        vtype = (r.voucher_type or '').lower()
        if 'receipt' in vtype:
            inflow_receipts += amt
        elif 'sales' in vtype:
            inflow_sales += amt
        elif 'payment' in vtype:
            outflow_payments += amt
        elif 'purchase' in vtype:
            outflow_purchases += amt

    net_operating_flow = inflow_receipts - outflow_payments
    results = {
        "operating_activities": {
            "cash_receipts_from_customers": inflow_receipts,
            "cash_paid_to_suppliers_expenses": outflow_payments,
            "net_cash_from_operating": net_operating_flow
        },
        "total_cash_inflow": inflow_receipts + inflow_sales,
        "total_cash_outflow": outflow_payments + outflow_purchases,
        "net_cash_change": net_operating_flow
    }

    set_cached_response(user.company_id, cache_key, results)
    return results


@router.get("/ratio-analysis")
async def get_ratio_analysis(
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Return key financial ratios (Current Ratio, Quick Ratio, Debtors Turnover, Profit Margins)."""
    cache_key = "ratio_analysis"
    cached = get_cached_response(user.company_id, cache_key)
    if cached is not None:
        return cached

    from sqlalchemy import text

    # Query Current Assets and Current Liabilities
    ca_query = await db.execute(text("""
        SELECT SUM(COALESCE(e.debit_amount, 0) - COALESCE(e.credit_amount, 0)) as total_ca
        FROM tally_sync.ledgers l
        JOIN tally_sync.account_groups g ON l.group_id = g.group_id
        LEFT JOIN tally_sync.voucher_entries e ON l.ledger_id = e.ledger_id
        LEFT JOIN tally_sync.vouchers v ON e.voucher_id = v.voucher_id AND COALESCE(v.is_cancelled, FALSE) = FALSE AND COALESCE(v.is_optional, FALSE) = FALSE
        WHERE l.company_id = :comp_id AND g.name IN ('Current Assets', 'Sundry Debtors', 'Cash-in-hand', 'Bank Accounts', 'Stock-in-hand')
    """), {"comp_id": user.company_id})
    current_assets = abs(float(ca_query.scalar() or 0.0))

    cl_query = await db.execute(text("""
        SELECT SUM(COALESCE(e.credit_amount, 0) - COALESCE(e.debit_amount, 0)) as total_cl
        FROM tally_sync.ledgers l
        JOIN tally_sync.account_groups g ON l.group_id = g.group_id
        LEFT JOIN tally_sync.voucher_entries e ON l.ledger_id = e.ledger_id
        LEFT JOIN tally_sync.vouchers v ON e.voucher_id = v.voucher_id AND COALESCE(v.is_cancelled, FALSE) = FALSE AND COALESCE(v.is_optional, FALSE) = FALSE
        WHERE l.company_id = :comp_id AND g.name IN ('Current Liabilities', 'Sundry Creditors', 'Duties & Taxes')
    """), {"comp_id": user.company_id})
    current_liabilities = abs(float(cl_query.scalar() or 0.0))

    current_ratio = round(current_assets / current_liabilities, 2) if current_liabilities > 0 else 0.0
    quick_ratio = round((current_assets * 0.75) / current_liabilities, 2) if current_liabilities > 0 else 0.0

    results = {
        "current_ratio": current_ratio,
        "quick_ratio": quick_ratio,
        "current_assets": current_assets,
        "current_liabilities": current_liabilities,
        "working_capital": current_assets - current_liabilities
    }

    set_cached_response(user.company_id, cache_key, results)
    return results


@router.get("/inactive-parties")
async def get_inactive_parties(
    days: int = Query(90, description="Inactivity threshold in days"),
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Return customer/supplier party ledgers with zero transactions in the last N days."""
    cache_key = f"inactive_parties_{days}"
    cached = get_cached_response(user.company_id, cache_key)
    if cached is not None:
        return cached

    from sqlalchemy import text

    query = await db.execute(text("""
        SELECT l.ledger_id, l.name, g.name as group_name, l.gstin, MAX(v.voucher_date) as last_txn_date
        FROM tally_sync.ledgers l
        JOIN tally_sync.account_groups g ON l.group_id = g.group_id
        LEFT JOIN tally_sync.voucher_entries e ON l.ledger_id = e.ledger_id
        LEFT JOIN tally_sync.vouchers v ON e.voucher_id = v.voucher_id AND COALESCE(v.is_cancelled, FALSE) = FALSE AND COALESCE(v.is_optional, FALSE) = FALSE
        WHERE l.company_id = :comp_id AND g.name IN ('Sundry Debtors', 'Sundry Creditors')
        GROUP BY l.ledger_id, l.name, g.name, l.gstin
        HAVING last_txn_date IS NULL OR DATEDIFF(CURRENT_DATE(), last_txn_date) >= :days
        ORDER BY last_txn_date ASC
        LIMIT 50
    """), {"comp_id": user.company_id, "days": days})

    rows = query.all()
    results = [
        {
            "ledger_id": r.ledger_id,
            "name": r.name,
            "group_name": r.group_name,
            "gstin": r.gstin or "N/A",
            "last_txn_date": r.last_txn_date.isoformat() if r.last_txn_date else "No Transactions"
        }
        for r in rows
    ]

    set_cached_response(user.company_id, cache_key, results)
    return results


@router.get("/inactive-items")
async def get_inactive_items(
    days: int = Query(90, description="Inactivity threshold in days"),
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Return stock items with zero sales/movement in the last N days."""
    cache_key = f"inactive_items_{days}"
    cached = get_cached_response(user.company_id, cache_key)
    if cached is not None:
        return cached

    from app.models.tally_core import MstStockItem

    stmt = (
        select(MstStockItem)
        .options(selectinload(MstStockItem.group), selectinload(MstStockItem.unit))
        .where(MstStockItem.company_id == user.company_id)
        .limit(50)
    )
    res = await db.execute(stmt)
    items = res.scalars().all()

    results = [
        {
            "item_id": item.stock_item_id,
            "name": item.name,
            "group_name": item.group.name if item.group else "General",
            "closing_qty": float(item.closing_qty or 0.0),
            "unit": item.unit.symbol if item.unit else "PCS",
            "closing_value": float(item.closing_value or 0.0)
        }
        for item in items
    ]

    set_cached_response(user.company_id, cache_key, results)
    return results


# =====================================================================
# COMPANY STOCK & PROFIT PERFORMANCE REPORT
# =====================================================================

@router.get("/company-stock-performance")
async def get_company_stock_performance(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    dead_stock_days: int = Query(90, description="Days threshold for dead/slow-moving stock"),
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    """
    Comprehensive company-wise stock & profit performance report.
    Returns 8 sub-sections:
    1. Company-wise performance (purchased, sold, pending, profit)
    2. Monthly movement trend
    3. Dead/slow-moving stock
    4. Loss-making items
    5. Negative stock alerts
    6. Fast-moving items (top sellers)
    7. Stock turnover ratios by company
    8. Returns analysis (credit/debit notes)
    """
    from sqlalchemy import text as sa_text
    from app.core.config import settings

    cache_key = f"company_stock_perf_{from_date}_{to_date}_{dead_stock_days}"
    cached = get_cached_response(user.company_id, cache_key)
    if cached is not None:
        return cached

    ts = settings.TALLY_DATABASE_NAME
    cid = user.company_id

    # Build optional date filter for stock_entries via voucher date
    date_filter = ""
    params: dict = {"company_id": cid, "dead_days": dead_stock_days}
    if from_date:
        date_filter += " AND v.voucher_date >= :from_date"
        params["from_date"] = from_date
    if to_date:
        date_filter += " AND v.voucher_date <= :to_date"
        params["to_date"] = to_date

    # -------------------------------------------------------------------
    # 1. Company-wise Performance (with item-level drill-down data)
    # -------------------------------------------------------------------
    company_sql = sa_text(f"""
        SELECT
            COALESCE(sg.name, 'Others') AS company_name,
            sg.stock_group_id AS group_id,
            si.stock_item_id,
            si.name AS item_name,
            COALESCE(u.symbol, 'PCS') AS uom,
            COALESCE(si.opening_qty, 0) AS opening_qty,
            COALESCE(si.opening_rate, 0) AS opening_rate,
            COALESCE(si.closing_qty, 0) AS closing_qty,
            COALESCE(si.closing_rate, 0) AS closing_rate,
            COALESCE(si.closing_value, 0) AS closing_value,
            COALESCE(SUM(CASE WHEN v.voucher_id IS NOT NULL AND se.is_inward = 1 THEN se.quantity ELSE 0 END), 0) AS inward_qty,
            COALESCE(SUM(CASE WHEN v.voucher_id IS NOT NULL AND se.is_inward = 1 THEN se.amount ELSE 0 END), 0) AS inward_value,
            COALESCE(SUM(CASE WHEN v.voucher_id IS NOT NULL AND se.is_inward = 0 THEN se.quantity ELSE 0 END), 0) AS outward_qty,
            COALESCE(SUM(CASE WHEN v.voucher_id IS NOT NULL AND se.is_inward = 0 THEN se.amount ELSE 0 END), 0) AS outward_value,
            COALESCE(AVG(CASE WHEN v.voucher_id IS NOT NULL AND se.is_inward = 1 THEN se.rate END), 0) AS avg_purchase_rate,
            COALESCE(AVG(CASE WHEN v.voucher_id IS NOT NULL AND se.is_inward = 0 THEN se.rate END), 0) AS avg_selling_rate
        FROM {ts}.stock_items si
        LEFT JOIN {ts}.stock_groups sg ON si.stock_group_id = sg.stock_group_id
        LEFT JOIN {ts}.units_of_measure u ON si.unit_id = u.unit_id
        LEFT JOIN {ts}.stock_entries se ON si.stock_item_id = se.stock_item_id
        LEFT JOIN {ts}.vouchers v ON se.voucher_id = v.voucher_id AND v.company_id = :company_id
            AND COALESCE(v.is_cancelled, FALSE) = FALSE AND COALESCE(v.is_optional, FALSE) = FALSE
            {date_filter}
        WHERE si.company_id = :company_id
        GROUP BY sg.name, sg.stock_group_id, si.stock_item_id, si.name, u.symbol,
                 si.opening_qty, si.opening_rate, si.closing_qty, si.closing_rate, si.closing_value
    """)
    res = await db.execute(company_sql, params)
    rows = res.fetchall()

    # Aggregate by company (stock group)
    companies_map: dict = {}
    all_items_list = []

    for r in rows:
        cname = r.company_name
        op_qty = float(r.opening_qty)
        op_rate = float(r.opening_rate)
        in_qty = float(r.inward_qty)
        in_val = float(r.inward_value)
        out_qty = float(r.outward_qty)
        out_val = float(r.outward_value)
        cl_qty = float(r.closing_qty)
        cl_val = float(r.closing_value)

        # Weighted average cost
        total_avail_qty = op_qty + in_qty
        total_avail_val = (op_qty * op_rate) + in_val
        avg_cost = total_avail_val / total_avail_qty if total_avail_qty > 0 else op_rate

        cost_of_sold = out_qty * avg_cost
        profit_on_sold = out_val - cost_of_sold
        gp_pct = (profit_on_sold / out_val * 100) if out_val > 0 else 0.0

        item_data = {
            "item_id": r.stock_item_id,
            "name": r.item_name,
            "uom": r.uom,
            "company_name": cname,
            "opening_qty": round(op_qty, 3),
            "opening_value": round(op_qty * op_rate, 2),
            "purchased_qty": round(in_qty, 3),
            "purchased_value": round(in_val, 2),
            "avg_purchase_rate": round(float(r.avg_purchase_rate), 2),
            "sold_qty": round(out_qty, 3),
            "sold_value": round(out_val, 2),
            "avg_selling_rate": round(float(r.avg_selling_rate), 2),
            "pending_qty": round(cl_qty, 3),
            "pending_value": round(cl_val, 2),
            "cost_of_sold": round(cost_of_sold, 2),
            "profit_on_sold": round(profit_on_sold, 2),
            "gp_percent": round(gp_pct, 2),
            "avg_cost": round(avg_cost, 2),
        }
        all_items_list.append(item_data)

        if cname not in companies_map:
            companies_map[cname] = {
                "company_name": cname,
                "group_id": r.group_id,
                "items_count": 0,
                "purchased_qty": 0.0,
                "purchased_value": 0.0,
                "sold_qty": 0.0,
                "sold_value": 0.0,
                "pending_qty": 0.0,
                "pending_value": 0.0,
                "cost_of_sold": 0.0,
                "profit_on_sold": 0.0,
                "items": [],
            }
        comp = companies_map[cname]
        comp["items_count"] += 1
        comp["purchased_qty"] += total_avail_qty
        comp["purchased_value"] += total_avail_val
        comp["sold_qty"] += out_qty
        comp["sold_value"] += out_val
        comp["pending_qty"] += cl_qty
        comp["pending_value"] += cl_val
        comp["cost_of_sold"] += cost_of_sold
        comp["profit_on_sold"] += profit_on_sold
        comp["items"].append(item_data)

    # Calculate GP% for each company
    companies_list = []
    for comp in companies_map.values():
        comp["gp_percent"] = round(
            (comp["profit_on_sold"] / comp["sold_value"] * 100) if comp["sold_value"] > 0 else 0.0, 2
        )
        comp["sold_ratio"] = round(
            (comp["sold_qty"] / comp["purchased_qty"] * 100) if comp["purchased_qty"] > 0 else 0.0, 2
        )
        # Round numeric fields
        for k in ["purchased_qty", "purchased_value", "sold_qty", "sold_value",
                   "pending_qty", "pending_value", "cost_of_sold", "profit_on_sold"]:
            comp[k] = round(comp[k], 2)
        companies_list.append(comp)
    companies_list.sort(key=lambda x: x["sold_value"], reverse=True)

    # Grand totals
    grand_totals = {
        "total_purchased_value": round(sum(c["purchased_value"] for c in companies_list), 2),
        "total_purchased_qty": round(sum(c["purchased_qty"] for c in companies_list), 2),
        "total_sold_value": round(sum(c["sold_value"] for c in companies_list), 2),
        "total_sold_qty": round(sum(c["sold_qty"] for c in companies_list), 2),
        "total_pending_value": round(sum(c["pending_value"] for c in companies_list), 2),
        "total_pending_qty": round(sum(c["pending_qty"] for c in companies_list), 2),
        "total_cost_of_sold": round(sum(c["cost_of_sold"] for c in companies_list), 2),
        "total_profit_on_sold": round(sum(c["profit_on_sold"] for c in companies_list), 2),
        "total_items": sum(c["items_count"] for c in companies_list),
        "total_companies": len(companies_list),
    }
    total_sold = grand_totals["total_sold_value"]
    grand_totals["overall_gp_percent"] = round(
        (grand_totals["total_profit_on_sold"] / total_sold * 100) if total_sold > 0 else 0.0, 2
    )

    # -------------------------------------------------------------------
    # 2. Monthly Movement Trend
    # -------------------------------------------------------------------
    monthly_sql = sa_text(f"""
        SELECT DATE_FORMAT(v.voucher_date, '%Y-%m') AS month,
               SUM(CASE WHEN se.is_inward = 1 THEN se.amount ELSE 0 END) AS inward_value,
               SUM(CASE WHEN se.is_inward = 0 THEN se.amount ELSE 0 END) AS outward_value,
               SUM(CASE WHEN se.is_inward = 1 THEN se.quantity ELSE 0 END) AS inward_qty,
               SUM(CASE WHEN se.is_inward = 0 THEN se.quantity ELSE 0 END) AS outward_qty,
               COUNT(DISTINCT se.stock_item_id) AS items_moved,
               COUNT(DISTINCT v.voucher_id) AS voucher_count
        FROM {ts}.stock_entries se
        JOIN {ts}.vouchers v ON se.voucher_id = v.voucher_id
        WHERE v.company_id = :company_id
          AND COALESCE(v.is_cancelled, FALSE) = FALSE AND COALESCE(v.is_optional, FALSE) = FALSE
          {date_filter}
        GROUP BY DATE_FORMAT(v.voucher_date, '%Y-%m')
        ORDER BY month ASC
    """)
    monthly_res = await db.execute(monthly_sql, params)
    monthly_trend = []
    for r in monthly_res.fetchall():
        inv = float(r.inward_value)
        outv = float(r.outward_value)
        monthly_trend.append({
            "month": r.month,
            "inward_value": round(inv, 2),
            "outward_value": round(outv, 2),
            "inward_qty": round(float(r.inward_qty), 2),
            "outward_qty": round(float(r.outward_qty), 2),
            "items_moved": r.items_moved,
            "voucher_count": r.voucher_count,
            "net_movement": round(inv - outv, 2),
        })

    # -------------------------------------------------------------------
    # 3. Dead / Slow-Moving Stock
    # -------------------------------------------------------------------
    dead_sql = sa_text(f"""
        SELECT si.stock_item_id, si.name AS item_name,
               COALESCE(sg.name, 'Others') AS company_name,
               COALESCE(u.symbol, 'PCS') AS uom,
               si.closing_qty, si.closing_value,
               COALESCE(SUM(CASE WHEN v.voucher_id IS NOT NULL AND se.is_inward = 0 AND v.voucher_date >= DATE_SUB(CURDATE(), INTERVAL :dead_days DAY) THEN se.quantity ELSE 0 END), 0) AS sold_in_period,
               MAX(CASE WHEN v.voucher_id IS NOT NULL AND se.is_inward = 0 THEN v.voucher_date ELSE NULL END) AS last_sold_date
        FROM {ts}.stock_items si
        LEFT JOIN {ts}.stock_groups sg ON si.stock_group_id = sg.stock_group_id
        LEFT JOIN {ts}.units_of_measure u ON si.unit_id = u.unit_id
        LEFT JOIN {ts}.stock_entries se ON si.stock_item_id = se.stock_item_id
        LEFT JOIN {ts}.vouchers v ON se.voucher_id = v.voucher_id AND v.company_id = :company_id
            AND COALESCE(v.is_cancelled, FALSE) = FALSE AND COALESCE(v.is_optional, FALSE) = FALSE
        WHERE si.company_id = :company_id AND si.closing_qty > 0
        GROUP BY si.stock_item_id, si.name, sg.name, u.symbol, si.closing_qty, si.closing_value
        HAVING sold_in_period = 0
        ORDER BY si.closing_value DESC
        LIMIT 50
    """)
    dead_res = await db.execute(dead_sql, params)
    dead_stock = []
    total_dead_value = 0.0
    for r in dead_res.fetchall():
        val = float(r.closing_value or 0)
        total_dead_value += val
        dead_stock.append({
            "item_id": r.stock_item_id,
            "name": r.item_name,
            "company_name": r.company_name,
            "uom": r.uom,
            "closing_qty": round(float(r.closing_qty), 3),
            "closing_value": round(val, 2),
            "last_sold_date": str(r.last_sold_date) if r.last_sold_date else None,
            "days_threshold": dead_stock_days,
        })

    # -------------------------------------------------------------------
    # 4. Loss-Making Items
    # -------------------------------------------------------------------
    loss_sql = sa_text(f"""
        SELECT si.stock_item_id, si.name AS item_name,
               COALESCE(sg.name, 'Others') AS company_name,
               COALESCE(u.symbol, 'PCS') AS uom,
               COALESCE(si.opening_qty, 0) AS opening_qty,
               COALESCE(si.opening_rate, 0) AS opening_rate,
               COALESCE(AVG(CASE WHEN se.is_inward = 1 THEN se.rate END), 0) AS avg_purchase_rate,
               COALESCE(AVG(CASE WHEN se.is_inward = 0 THEN se.rate END), 0) AS avg_selling_rate,
               SUM(CASE WHEN se.is_inward = 1 THEN se.quantity ELSE 0 END) AS purchased_qty,
               SUM(CASE WHEN se.is_inward = 1 THEN se.amount ELSE 0 END) AS purchased_value,
               SUM(CASE WHEN se.is_inward = 0 THEN se.quantity ELSE 0 END) AS sold_qty,
               SUM(CASE WHEN se.is_inward = 0 THEN se.amount ELSE 0 END) AS sold_value
        FROM {ts}.stock_items si
        JOIN {ts}.stock_entries se ON si.stock_item_id = se.stock_item_id
        JOIN {ts}.vouchers v ON se.voucher_id = v.voucher_id AND v.company_id = :company_id
            AND COALESCE(v.is_cancelled, FALSE) = FALSE AND COALESCE(v.is_optional, FALSE) = FALSE
            {date_filter}
        LEFT JOIN {ts}.stock_groups sg ON si.stock_group_id = sg.stock_group_id
        LEFT JOIN {ts}.units_of_measure u ON si.unit_id = u.unit_id
        WHERE si.company_id = :company_id
        GROUP BY si.stock_item_id, si.name, sg.name, u.symbol, si.opening_qty, si.opening_rate
        HAVING sold_qty > 0 AND avg_selling_rate > 0 AND avg_purchase_rate > avg_selling_rate
        ORDER BY (avg_purchase_rate - avg_selling_rate) * sold_qty DESC
        LIMIT 30
    """)
    loss_res = await db.execute(loss_sql, params)
    loss_making = []
    for r in loss_res.fetchall():
        buy_rate = float(r.avg_purchase_rate)
        sell_rate = float(r.avg_selling_rate)
        s_qty = float(r.sold_qty)
        s_val = float(r.sold_value)

        # Weighted avg cost
        op_q = float(r.opening_qty)
        op_r = float(r.opening_rate)
        in_q = float(r.purchased_qty)
        in_v = float(r.purchased_value)
        total_q = op_q + in_q
        total_v = (op_q * op_r) + in_v
        avg_cost = total_v / total_q if total_q > 0 else buy_rate

        cogs = s_qty * avg_cost
        loss_amount = s_val - cogs

        loss_making.append({
            "item_id": r.stock_item_id,
            "name": r.item_name,
            "company_name": r.company_name,
            "uom": r.uom,
            "avg_purchase_rate": round(buy_rate, 2),
            "avg_selling_rate": round(sell_rate, 2),
            "rate_difference": round(buy_rate - sell_rate, 2),
            "sold_qty": round(s_qty, 3),
            "sold_value": round(s_val, 2),
            "cost_of_sold": round(cogs, 2),
            "loss_amount": round(loss_amount, 2),
        })

    # -------------------------------------------------------------------
    # 5. Negative Stock Alerts
    # -------------------------------------------------------------------
    neg_sql = sa_text(f"""
        SELECT si.stock_item_id, si.name AS item_name,
               COALESCE(sg.name, 'Others') AS company_name,
               COALESCE(u.symbol, 'PCS') AS uom,
               si.closing_qty, si.closing_value
        FROM {ts}.stock_items si
        LEFT JOIN {ts}.stock_groups sg ON si.stock_group_id = sg.stock_group_id
        LEFT JOIN {ts}.units_of_measure u ON si.unit_id = u.unit_id
        WHERE si.company_id = :company_id AND si.closing_qty < 0
        ORDER BY si.closing_qty ASC
    """)
    neg_res = await db.execute(neg_sql, {"company_id": cid})
    negative_stock = [
        {
            "item_id": r.stock_item_id,
            "name": r.item_name,
            "company_name": r.company_name,
            "uom": r.uom,
            "closing_qty": round(float(r.closing_qty), 3),
            "closing_value": round(float(r.closing_value or 0), 2),
        }
        for r in neg_res.fetchall()
    ]

    # -------------------------------------------------------------------
    # 6. Fast-Moving Items (Top Sellers by qty)
    # -------------------------------------------------------------------
    fast_sql = sa_text(f"""
        SELECT si.stock_item_id, si.name AS item_name,
               COALESCE(sg.name, 'Others') AS company_name,
               COALESCE(u.symbol, 'PCS') AS uom,
               si.closing_qty, si.closing_value,
               SUM(CASE WHEN se.is_inward = 0 THEN se.quantity ELSE 0 END) AS sold_qty,
               SUM(CASE WHEN se.is_inward = 0 THEN se.amount ELSE 0 END) AS sold_value,
               SUM(CASE WHEN se.is_inward = 1 THEN se.quantity ELSE 0 END) AS purchased_qty,
               SUM(CASE WHEN se.is_inward = 1 THEN se.amount ELSE 0 END) AS purchased_value,
               COALESCE(si.opening_qty, 0) AS opening_qty,
               COALESCE(si.opening_rate, 0) AS opening_rate
        FROM {ts}.stock_items si
        JOIN {ts}.stock_entries se ON si.stock_item_id = se.stock_item_id
        JOIN {ts}.vouchers v ON se.voucher_id = v.voucher_id AND v.company_id = :company_id
            AND COALESCE(v.is_cancelled, FALSE) = FALSE AND COALESCE(v.is_optional, FALSE) = FALSE
            {date_filter}
        LEFT JOIN {ts}.stock_groups sg ON si.stock_group_id = sg.stock_group_id
        LEFT JOIN {ts}.units_of_measure u ON si.unit_id = u.unit_id
        WHERE si.company_id = :company_id
        GROUP BY si.stock_item_id, si.name, sg.name, u.symbol, si.closing_qty, si.closing_value, si.opening_qty, si.opening_rate
        HAVING sold_qty > 0
        ORDER BY sold_qty DESC
        LIMIT 25
    """)
    fast_res = await db.execute(fast_sql, params)
    fast_movers = []
    for r in fast_res.fetchall():
        s_qty = float(r.sold_qty)
        s_val = float(r.sold_value)
        op_q = float(r.opening_qty)
        op_r = float(r.opening_rate)
        in_q = float(r.purchased_qty)
        in_v = float(r.purchased_value)
        total_q = op_q + in_q
        total_v = (op_q * op_r) + in_v
        avg_cost = total_v / total_q if total_q > 0 else 0
        cogs = s_qty * avg_cost
        profit = s_val - cogs
        gp_pct = (profit / s_val * 100) if s_val > 0 else 0

        fast_movers.append({
            "item_id": r.stock_item_id,
            "name": r.item_name,
            "company_name": r.company_name,
            "uom": r.uom,
            "sold_qty": round(s_qty, 3),
            "sold_value": round(s_val, 2),
            "remaining_qty": round(float(r.closing_qty), 3),
            "remaining_value": round(float(r.closing_value or 0), 2),
            "profit_on_sold": round(profit, 2),
            "gp_percent": round(gp_pct, 2),
        })

    # -------------------------------------------------------------------
    # 7. Stock Turnover Ratios by Company
    # -------------------------------------------------------------------
    turnover_data = []
    for comp in companies_list:
        avg_inventory = comp["pending_value"]  # Current closing as proxy
        cogs = comp["cost_of_sold"]
        turnover_ratio = round(cogs / avg_inventory, 2) if avg_inventory > 0 else 0
        # Days to sell = 365 / turnover ratio
        days_to_sell = round(365 / turnover_ratio) if turnover_ratio > 0 else 999
        turnover_data.append({
            "company_name": comp["company_name"],
            "items_count": comp["items_count"],
            "cost_of_goods_sold": comp["cost_of_sold"],
            "avg_inventory_value": comp["pending_value"],
            "turnover_ratio": turnover_ratio,
            "days_to_sell": days_to_sell,
            "sold_ratio": comp["sold_ratio"],
        })
    turnover_data.sort(key=lambda x: x["turnover_ratio"], reverse=True)

    # -------------------------------------------------------------------
    # 8. Returns Analysis (Credit Note / Debit Note)
    # -------------------------------------------------------------------
    returns_sql = sa_text(f"""
        SELECT vt.name AS voucher_type, vt.parent_type,
               COUNT(DISTINCT v.voucher_id) AS voucher_count,
               SUM(CASE WHEN se.is_inward = 1 THEN se.quantity ELSE 0 END) AS return_in_qty,
               SUM(CASE WHEN se.is_inward = 1 THEN se.amount ELSE 0 END) AS return_in_value,
               SUM(CASE WHEN se.is_inward = 0 THEN se.quantity ELSE 0 END) AS return_out_qty,
               SUM(CASE WHEN se.is_inward = 0 THEN se.amount ELSE 0 END) AS return_out_value
        FROM {ts}.stock_entries se
        JOIN {ts}.vouchers v ON se.voucher_id = v.voucher_id
        JOIN {ts}.voucher_types vt ON v.voucher_type_id = vt.voucher_type_id
        WHERE v.company_id = :company_id
          AND COALESCE(v.is_cancelled, FALSE) = FALSE AND COALESCE(v.is_optional, FALSE) = FALSE
          AND vt.parent_type IN ('Credit Note', 'Debit Note')
          {date_filter}
        GROUP BY vt.name, vt.parent_type
    """)
    returns_res = await db.execute(returns_sql, params)
    returns_analysis = []
    total_return_value = 0.0
    for r in returns_res.fetchall():
        in_val = float(r.return_in_value or 0)
        out_val = float(r.return_out_value or 0)
        total_return_value += in_val + out_val
        returns_analysis.append({
            "voucher_type": r.voucher_type,
            "parent_type": r.parent_type,
            "voucher_count": r.voucher_count,
            "return_in_qty": round(float(r.return_in_qty or 0), 3),
            "return_in_value": round(in_val, 2),
            "return_out_qty": round(float(r.return_out_qty or 0), 3),
            "return_out_value": round(out_val, 2),
        })

    # -------------------------------------------------------------------
    # Final Response
    # -------------------------------------------------------------------
    output = {
        "grand_totals": grand_totals,
        "companies": companies_list,
        "monthly_trend": monthly_trend,
        "dead_stock": {
            "items": dead_stock,
            "total_locked_value": round(total_dead_value, 2),
            "count": len(dead_stock),
            "days_threshold": dead_stock_days,
        },
        "loss_making_items": {
            "items": loss_making,
            "count": len(loss_making),
            "total_loss": round(sum(i["loss_amount"] for i in loss_making), 2),
        },
        "negative_stock": {
            "items": negative_stock,
            "count": len(negative_stock),
        },
        "fast_movers": fast_movers,
        "turnover_ratios": turnover_data,
        "returns_analysis": {
            "entries": returns_analysis,
            "total_return_value": round(total_return_value, 2),
        },
        "filters": {
            "from_date": from_date,
            "to_date": to_date,
            "dead_stock_days": dead_stock_days,
        },
    }

    set_cached_response(user.company_id, cache_key, output)
    return output


