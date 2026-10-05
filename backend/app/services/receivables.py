"""Receivables ageing: one definition of "overdue", shared by Outstanding, Executive Analytics and Home.

A customer's balance (opening balance + debits - credits on vouchers that aren't cancelled or optional) is matched
to their sales invoices newest first, so payments are taken to have cleared the oldest bills. Whatever is left
after the last invoice is the opening / pre-sync balance. Each invoice falls due its credit days after its date:
the customer's own credit days (set in MyTally), else Tally's credit period, else the default credit days setting.
Days overdue then decide the bucket: not due, 1-30, 31-60, 61-90 or 90+.
"""
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime_utils import get_ist_date
from app.models.portal_core import CustomerCreditTerm
from app.models.tally_core import MstGroup, MstLedger, MstVoucherType, TrnAccounting, TrnVoucher
from app.services.app_settings import get_setting

BUCKETS = ("Not due", "1-30 Days", "31-60 Days", "61-90 Days", "90+ Days")
# Days overdue shown for the opening / pre-sync balance, whose bills aren't known
HISTORIC_DAYS_OVERDUE = 91


@dataclass
class AgedBill:
    voucher_id: Optional[int]
    voucher_number: str
    bill_date: Optional[date]
    due_date: Optional[date]
    bill_amount: float
    outstanding: float
    days_overdue: int
    bucket: str


@dataclass
class PartyAgeing:
    ledger_id: int
    name: str
    phone: Optional[str]
    email: Optional[str]
    credit_days: int
    credit_days_source: str  # 'customer' (set in MyTally), 'tally' or 'default'
    balance: float
    buckets: Dict[str, float] = field(default_factory=lambda: {b: 0.0 for b in BUCKETS})
    bills: List[AgedBill] = field(default_factory=list)

    @property
    def overdue(self) -> float:
        return sum(v for k, v in self.buckets.items() if k != "Not due")


def bucket_for(days_overdue: int) -> str:
    if days_overdue <= 0:
        return "Not due"
    if days_overdue <= 30:
        return "1-30 Days"
    if days_overdue <= 60:
        return "31-60 Days"
    if days_overdue <= 90:
        return "61-90 Days"
    return "90+ Days"


def live_voucher():
    """Vouchers that count: not cancelled and not optional (memo)."""
    return and_(func.coalesce(TrnVoucher.is_cancelled, False) == False,  # noqa: E712
                func.coalesce(TrnVoucher.is_optional, False) == False)  # noqa: E712


def sales_voucher_type():
    """The Sales voucher type and any custom type built on it (e.g. 'Sales GST')."""
    return or_(MstVoucherType.name == "Sales", MstVoucherType.parent_type == "Sales")


async def group_ids_under(db: AsyncSession, company_id: int, root_name: str) -> Set[int]:
    """A Tally group (matched by name, any case) and every group nested under it."""
    groups = (await db.execute(
        select(MstGroup.group_id, MstGroup.name, MstGroup.parent_group_id).where(MstGroup.company_id == company_id)
    )).all()
    found = {g.group_id for g in groups if (g.name or "").strip().lower() == root_name.lower()}
    changed = True
    while changed:
        changed = False
        for g in groups:
            if g.parent_group_id in found and g.group_id not in found:
                found.add(g.group_id)
                changed = True
    return found


async def credit_days_for(
    db: AsyncSession, company_id: int, tally_days: Dict[int, Optional[int]]
) -> Dict[int, Tuple[int, str]]:
    """Credit days and where they came from, for each ledger id (tally_days maps ledger id to Tally's value)."""
    default_days = int(await get_setting(db, "default_credit_days"))
    own = {}
    if tally_days:
        rows = await db.execute(select(CustomerCreditTerm.ledger_id, CustomerCreditTerm.credit_days).where(
            CustomerCreditTerm.company_id == company_id, CustomerCreditTerm.ledger_id.in_(list(tally_days))))
        own = dict(rows.all())
    result = {}
    for ledger_id, from_tally in tally_days.items():
        if ledger_id in own:
            result[ledger_id] = (int(own[ledger_id]), "customer")
        elif from_tally and from_tally > 0:
            result[ledger_id] = (int(from_tally), "tally")
        else:
            result[ledger_id] = (default_days, "default")
    return result


def age_balance(balance: float, invoices: Iterable[Tuple[int, Optional[str], Optional[date], float]],
                credit_days: int, today: date) -> Tuple[Dict[str, float], List[AgedBill]]:
    """Spread a customer's balance over their invoices (voucher_id, number, date, amount), newest first."""
    buckets = {b: 0.0 for b in BUCKETS}
    bills: List[AgedBill] = []
    remaining = balance
    for voucher_id, number, bill_date, amount in invoices:
        if remaining <= 0.001:
            break
        amount = float(amount or 0)
        allocated = min(remaining, amount)
        if allocated <= 0:
            continue
        due = bill_date + timedelta(days=credit_days) if bill_date else None
        days_overdue = max(0, (today - due).days) if due else 0
        bucket = bucket_for(days_overdue)
        buckets[bucket] += allocated
        bills.append(AgedBill(voucher_id, number or f"INV-{voucher_id}", bill_date, due, amount,
                              round(allocated, 2), days_overdue, bucket))
        remaining -= allocated
    if remaining > 0.01:
        buckets["90+ Days"] += remaining
        bills.append(AgedBill(None, "Opening / Historic Balance", None, None, round(remaining, 2),
                              round(remaining, 2), HISTORIC_DAYS_OVERDUE, "90+ Days"))
    return {k: round(v, 2) for k, v in buckets.items()}, bills


async def receivables_ageing(
    db: AsyncSession, company_id: int, party_ledger_id: Optional[int] = None, today: Optional[date] = None
) -> List[PartyAgeing]:
    """Every debtor (Sundry Debtors and its sub-groups) who owes money, aged by due date, largest balance first.
    Dates are Indian (IST) dates, so a bill isn't a day late or early on a server running in UTC."""
    today = today or get_ist_date()
    debtor_groups = await group_ids_under(db, company_id, "Sundry Debtors")
    if not debtor_groups:
        return []

    counted = case((TrnVoucher.voucher_id.isnot(None), 1), else_=0)
    stmt = (
        select(
            MstLedger.ledger_id, MstLedger.name, MstLedger.mobile, MstLedger.phone, MstLedger.email,
            MstLedger.credit_period_days, MstLedger.opening_balance, MstLedger.opening_balance_type,
            func.coalesce(func.sum(TrnAccounting.debit_amount * counted), 0).label("debit"),
            func.coalesce(func.sum(TrnAccounting.credit_amount * counted), 0).label("credit"),
        )
        .select_from(MstLedger)
        .outerjoin(TrnAccounting, TrnAccounting.ledger_id == MstLedger.ledger_id)
        .outerjoin(TrnVoucher, and_(TrnVoucher.voucher_id == TrnAccounting.voucher_id, live_voucher()))
        .where(MstLedger.company_id == company_id, MstLedger.group_id.in_(debtor_groups))
        .group_by(MstLedger.ledger_id, MstLedger.name, MstLedger.mobile, MstLedger.phone, MstLedger.email,
                  MstLedger.credit_period_days, MstLedger.opening_balance, MstLedger.opening_balance_type)
    )
    if party_ledger_id:
        stmt = stmt.where(MstLedger.ledger_id == party_ledger_id)

    owing = []
    for r in (await db.execute(stmt)).all():
        opening = float(r.opening_balance or 0) * (-1 if (r.opening_balance_type or "Dr").strip().lower() == "cr" else 1)
        balance = round(opening + float(r.debit) - float(r.credit), 2)
        if balance > 0.01:
            owing.append((r, balance))
    if not owing:
        return []

    terms = await credit_days_for(db, company_id, {r.ledger_id: r.credit_period_days for r, _ in owing})

    # All their sales invoices in one query, newest first per customer
    invoices: Dict[int, List[tuple]] = defaultdict(list)
    rows = await db.execute(
        select(TrnAccounting.ledger_id, TrnVoucher.voucher_id, TrnVoucher.voucher_number,
               TrnVoucher.voucher_date, TrnVoucher.total_amount)
        .join(TrnVoucher, TrnVoucher.voucher_id == TrnAccounting.voucher_id)
        .join(MstVoucherType, MstVoucherType.voucher_type_id == TrnVoucher.voucher_type_id)
        .where(TrnAccounting.ledger_id.in_([r.ledger_id for r, _ in owing]), sales_voucher_type(), live_voucher())
        .distinct()
        .order_by(TrnAccounting.ledger_id, TrnVoucher.voucher_date.desc(), TrnVoucher.voucher_id.desc())
    )
    for ledger_id, voucher_id, number, voucher_date, amount in rows.all():
        invoices[ledger_id].append((voucher_id, number, voucher_date, amount))

    result = []
    for r, balance in owing:
        days, source = terms[r.ledger_id]
        buckets, bills = age_balance(balance, invoices[r.ledger_id], days, today)
        result.append(PartyAgeing(r.ledger_id, r.name, r.mobile or r.phone, r.email, days, source, balance, buckets, bills))
    result.sort(key=lambda p: p.balance, reverse=True)
    return result
