"""Phase 5 reports: cash & bank book, cost centres, stock by godown and by batch. Portable SQLAlchemy (runs on the
test SQLite too); amounts count only live vouchers (not cancelled, not optional)."""
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.datetime_utils import get_ist_date
from app.core.permissions import require_permission
from app.models.portal_core import Company, User
from app.models.tally_core import (
    Batch, MstCostCentre, MstGodown, MstLedger, MstStockItem, MstUom, TrnAccounting, TrnCostCentreAllocation,
    TrnInventory, TrnVoucher,
)
from app.services.receivables import group_ids_under, live_voucher

router = APIRouter(prefix="/reports", tags=["Reports: books"])

CASH_BANK_GROUPS = ("Cash-in-Hand", "Bank Accounts", "Bank OD A/c")


async def _period(db: AsyncSession, cid: int, from_date: Optional[date], to_date: Optional[date]):
    """The report period. A missing date means all time: from the company's first day (books begin, or an earlier
    voucher) up to today (or a later, post-dated voucher)."""
    start, end = from_date, to_date
    if start is None or end is None:
        first, last = (await db.execute(select(func.min(TrnVoucher.voucher_date), func.max(TrnVoucher.voucher_date))
                                        .where(TrnVoucher.company_id == cid))).one()
        today = get_ist_date()
        if end is None:
            end = max(today, last) if last else today
        if start is None:
            begin = (await db.execute(select(Company.books_begin_date).where(Company.company_id == cid))).scalar()
            start = min([d for d in (begin, first) if d] or [today])
            start = min(start, end)  # an explicit end before the books begin still gives a valid (empty) period
    if start > end:
        raise HTTPException(status_code=422, detail="The start date is after the end date.")
    return start, end


def _num(value) -> float:
    return round(float(value or 0), 2)


@router.get("/cash-bank-book")
async def cash_bank_book(
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Every cash and bank ledger: opening, money in, money out and closing for the period (Dr positive)."""
    cid = user.company_id
    start, end = await _period(db, cid, from_date, to_date)
    groups = set()
    kinds = {}
    for name in CASH_BANK_GROUPS:
        ids = await group_ids_under(db, cid, name)
        groups |= ids
        for gid in ids:
            kinds.setdefault(gid, "Cash" if name == "Cash-in-Hand" else "Bank")
    if not groups:
        return {"from": start.isoformat(), "to": end.isoformat(), "ledgers": [], "totals": None}
    ledgers = (await db.execute(select(MstLedger).where(MstLedger.company_id == cid, MstLedger.group_id.in_(groups))
                                .order_by(MstLedger.name))).scalars().all()
    ids = [l.ledger_id for l in ledgers]
    net = TrnAccounting.debit_amount - TrnAccounting.credit_amount
    moves = {r.ledger_id: r for r in (await db.execute(
        select(TrnAccounting.ledger_id,
               func.sum(case((TrnVoucher.voucher_date < start, net), else_=0)).label("before"),
               func.sum(case((TrnVoucher.voucher_date >= start, TrnAccounting.debit_amount), else_=0)).label("money_in"),
               func.sum(case((TrnVoucher.voucher_date >= start, TrnAccounting.credit_amount), else_=0)).label("money_out"),
               func.count(case((TrnVoucher.voucher_date >= start, 1))).label("entries"))
        .join(TrnVoucher, TrnVoucher.voucher_id == TrnAccounting.voucher_id)
        .where(TrnVoucher.company_id == cid, TrnAccounting.ledger_id.in_(ids), TrnVoucher.voucher_date <= end, live_voucher())
        .group_by(TrnAccounting.ledger_id))).all()}
    rows = []
    for l in ledgers:
        opening_master = Decimal(str(l.opening_balance or 0)) * (1 if (l.opening_balance_type or "Dr") == "Dr" else -1)
        m = moves.get(l.ledger_id)
        opening = opening_master + Decimal(str(m.before or 0)) if m else opening_master
        money_in, money_out = Decimal(str(m.money_in or 0)) if m else Decimal(0), Decimal(str(m.money_out or 0)) if m else Decimal(0)
        rows.append({"ledger_id": l.ledger_id, "name": l.name, "kind": kinds.get(l.group_id, "Bank"),
                     "opening": _num(opening), "money_in": _num(money_in), "money_out": _num(money_out),
                     "closing": _num(opening + money_in - money_out), "entries": int(m.entries) if m else 0})
    totals = {k: _num(sum(r[k] for r in rows)) for k in ("opening", "money_in", "money_out", "closing")}
    return {"from": start.isoformat(), "to": end.isoformat(), "ledgers": rows, "totals": totals}


@router.get("/cost-centres")
async def cost_centres(
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Totals per cost centre from Tally's cost-centre allocations (debits and credits of the allocated entries)."""
    cid = user.company_id
    start, end = await _period(db, cid, from_date, to_date)
    is_debit = TrnAccounting.debit_amount > 0
    rows = (await db.execute(
        select(MstCostCentre.cost_centre_id, MstCostCentre.name,
               func.sum(case((is_debit, func.abs(TrnCostCentreAllocation.amount)), else_=0)).label("debit"),
               func.sum(case((is_debit, 0), else_=func.abs(TrnCostCentreAllocation.amount))).label("credit"),
               func.count(func.distinct(TrnVoucher.voucher_id)).label("vouchers"))
        .join(TrnCostCentreAllocation, TrnCostCentreAllocation.cost_centre_id == MstCostCentre.cost_centre_id)
        .join(TrnAccounting, TrnAccounting.entry_id == TrnCostCentreAllocation.entry_id)
        .join(TrnVoucher, TrnVoucher.voucher_id == TrnAccounting.voucher_id)
        .where(TrnVoucher.company_id == cid, TrnVoucher.voucher_date >= start, TrnVoucher.voucher_date <= end, live_voucher())
        .group_by(MstCostCentre.cost_centre_id, MstCostCentre.name).order_by(MstCostCentre.name))).all()
    centres = (await db.execute(select(func.count(MstCostCentre.cost_centre_id)).where(MstCostCentre.company_id == cid))).scalar() or 0
    return {
        "from": start.isoformat(), "to": end.isoformat(), "cost_centres_in_tally": centres,
        "rows": [{"cost_centre_id": r.cost_centre_id, "name": r.name, "debit": _num(r.debit), "credit": _num(r.credit),
                  "net": _num((r.debit or 0) - (r.credit or 0)), "vouchers": int(r.vouchers)} for r in rows],
    }


@router.get("/stock-by-godown")
async def stock_by_godown(
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Quantities in and out of each godown in the period, per item (lines without a godown count as Main Location)."""
    cid = user.company_id
    start, end = await _period(db, cid, from_date, to_date)
    qty = func.abs(TrnInventory.quantity)
    rows = (await db.execute(
        select(TrnInventory.godown_id, MstGodown.name.label("godown"), MstStockItem.stock_item_id, MstStockItem.name.label("item"),
               MstUom.symbol.label("unit"),
               func.sum(case((TrnInventory.is_inward.is_(True), qty), else_=0)).label("qty_in"),
               func.sum(case((TrnInventory.is_inward.is_(True), 0), else_=qty)).label("qty_out"))
        .join(TrnVoucher, TrnVoucher.voucher_id == TrnInventory.voucher_id)
        .join(MstStockItem, MstStockItem.stock_item_id == TrnInventory.stock_item_id)
        .outerjoin(MstUom, MstUom.unit_id == MstStockItem.unit_id)
        .outerjoin(MstGodown, MstGodown.godown_id == TrnInventory.godown_id)
        .where(TrnVoucher.company_id == cid, TrnVoucher.voucher_date >= start, TrnVoucher.voucher_date <= end, live_voucher())
        .group_by(TrnInventory.godown_id, MstGodown.name, MstStockItem.stock_item_id, MstStockItem.name, MstUom.symbol)
        .order_by(MstGodown.name, MstStockItem.name))).all()
    godowns = {}
    for r in rows:
        g = godowns.setdefault(r.godown or "Main Location", {"godown": r.godown or "Main Location", "items": [], "qty_in": 0.0, "qty_out": 0.0})
        g["items"].append({"stock_item_id": r.stock_item_id, "item": r.item, "unit": r.unit or "",
                           "qty_in": _num(r.qty_in), "qty_out": _num(r.qty_out), "net": _num((r.qty_in or 0) - (r.qty_out or 0))})
        g["qty_in"] += float(r.qty_in or 0)
        g["qty_out"] += float(r.qty_out or 0)
    count = (await db.execute(select(func.count(MstGodown.godown_id)).where(MstGodown.company_id == cid))).scalar() or 0
    return {"from": start.isoformat(), "to": end.isoformat(), "godowns_in_tally": count, "godowns": list(godowns.values())}


@router.get("/stock-by-batch")
async def stock_by_batch(user: User = Depends(require_permission("reports", "read")), db: AsyncSession = Depends(get_db)):
    """Every batch with stock left, with expiry (soonest first)."""
    rows = (await db.execute(
        select(Batch.batch_id, Batch.batch_number, Batch.manufacture_date, Batch.expiry_date, Batch.quantity_received,
               Batch.quantity_available, MstStockItem.name.label("item"), MstUom.symbol.label("unit"))
        .join(MstStockItem, MstStockItem.stock_item_id == Batch.stock_item_id)
        .outerjoin(MstUom, MstUom.unit_id == MstStockItem.unit_id)
        .where(Batch.company_id == user.company_id, Batch.quantity_available > 0)
        .order_by(Batch.expiry_date.is_(None), Batch.expiry_date, MstStockItem.name))).all()
    today = get_ist_date()
    return {"batches": [{
        "batch_id": r.batch_id, "item": r.item, "batch": r.batch_number, "unit": r.unit or "",
        "manufactured": r.manufacture_date.isoformat() if r.manufacture_date else None,
        "expires": r.expiry_date.isoformat() if r.expiry_date else None,
        "days_to_expiry": (r.expiry_date - today).days if r.expiry_date else None,
        "received": _num(r.quantity_received), "available": _num(r.quantity_available),
    } for r in rows]}
