"""Books-parity check against Tally (WS-5): a verification, never a data source.

From a complete active-key list the agent sends, per ledger, the closing balance Tally computed, and per
voucher its type and date. This compares them with what MyTally computes from voucher_entries plus the
opening balance, and with MyTally's own voucher counts, and keeps the differences in tally_parity_reports.
It only reads the books; the report row is the only thing written.

Sign: Tally exports a debit balance as negative, MyTally's balances are debit-positive, so a Tally closing
balance is negated before it is compared.
"""
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime_utils import get_ist_now
from app.models.portal_core import TallyMissingRecord, TallyParityReport
from app.models.tally_core import MstLedger, MstVoucherType, TrnAccounting, TrnVoucher
from app.services.voucher_kinds import NON_POSTING

logger = logging.getLogger("uvicorn.error")

# Tally's own ledgers whose closing figure is worked out from the profit and loss, not from vouchers
TALLY_COMPUTED_LEDGERS = {"profit & loss a/c"}
TOLERANCE = Decimal("0.01")
TOP_LEDGERS = 10


def financial_year(day) -> str:
    """The April-March year a date falls in: 2026-03-31 -> '2025-26'."""
    start = day.year if day.month >= 4 else day.year - 1
    return f"{start}-{str(start + 1)[-2:]}"


def _dec(value) -> Optional[Decimal]:
    try:
        return Decimal(str(value).strip().replace(",", ""))
    except Exception:
        return None


def _parse_date(text: str):
    from app.services.tally_xml_importer import parse_tally_date
    return parse_tally_date(text)


async def build_parity_report(db: AsyncSession, company_id: int, list_id: str,
                              vouchers: Optional[List[Dict[str, Any]]],
                              ledgers: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
    """Compare the lists with the books and store the result. Does not commit."""
    # ── ledgers ──
    top: List[Dict[str, Any]] = []
    checked = drifting = 0
    if ledgers:
        type_name = func.lower(func.coalesce(func.nullif(MstVoucherType.parent_type, ""), MstVoucherType.name))
        sums = {row.ledger_id: (row.dr or Decimal(0), row.cr or Decimal(0)) for row in (await db.execute(
            select(TrnAccounting.ledger_id, func.sum(TrnAccounting.debit_amount).label("dr"),
                   func.sum(TrnAccounting.credit_amount).label("cr"))
            .join(TrnVoucher, TrnVoucher.voucher_id == TrnAccounting.voucher_id)
            .join(MstVoucherType, MstVoucherType.voucher_type_id == TrnVoucher.voucher_type_id)
            .where(TrnVoucher.company_id == company_id,
                   func.coalesce(TrnVoucher.is_cancelled, False) == False,       # noqa: E712
                   func.coalesce(TrnVoucher.is_optional, False) == False,        # noqa: E712
                   type_name.notin_(sorted(NON_POSTING)))
            .group_by(TrnAccounting.ledger_id))).all()}
        rows = (await db.execute(select(MstLedger).where(MstLedger.company_id == company_id))).scalars().all()
        by_guid = {r.tally_guid: r for r in rows if r.tally_guid}
        by_master = {r.tally_master_id: r for r in rows if r.tally_master_id is not None}
        diffs = []
        for item in ledgers:
            closing = _dec(item.get("closing_balance"))
            if closing is None:
                continue
            if (item.get("name") or "").strip().lower() in TALLY_COMPUTED_LEDGERS:
                continue
            ledger = by_guid.get((item.get("guid") or "").strip()) or by_master.get(
                int(item["master_id"]) if str(item.get("master_id") or "").strip().isdigit() else None)
            if ledger is None:
                continue
            dr, cr = sums.get(ledger.ledger_id, (Decimal(0), Decimal(0)))
            opening = ledger.opening_balance or Decimal(0)
            opening = -opening if ledger.opening_balance_type == "Cr" else opening
            computed = opening + dr - cr
            tally = -closing
            checked += 1
            difference = computed - tally
            if abs(difference) > TOLERANCE:
                drifting += 1
                diffs.append({"ledger_id": ledger.ledger_id, "name": ledger.name, "tally": float(tally),
                              "computed": float(computed), "difference": float(difference)})
        diffs.sort(key=lambda d: abs(d["difference"]), reverse=True)
        top = diffs[:TOP_LEDGERS]

    # ── voucher counts by type and financial year ──
    count_drift: List[Dict[str, Any]] = []
    tally_total = here_total = 0
    if vouchers:
        tally_counts: Dict[tuple, int] = {}
        for item in vouchers:
            day = _parse_date((item.get("date") or "").strip())
            if day is None:
                continue
            key = ((item.get("voucher_type") or "").strip(), financial_year(day))
            tally_counts[key] = tally_counts.get(key, 0) + 1
        removed = {r for (r,) in (await db.execute(select(TallyMissingRecord.record_id).where(
            TallyMissingRecord.company_id == company_id, TallyMissingRecord.entity_type == "Voucher",
            TallyMissingRecord.status == "deleted")))}
        here_counts: Dict[tuple, int] = {}
        for vid, vname, vdate in (await db.execute(
                select(TrnVoucher.voucher_id, MstVoucherType.name, TrnVoucher.voucher_date)
                .join(MstVoucherType, MstVoucherType.voucher_type_id == TrnVoucher.voucher_type_id)
                .where(TrnVoucher.company_id == company_id))).all():
            # What this company holds that Tally also holds: not what the app has only just made, nor what a
            # deletion in Tally already took out
            if vid in removed or vdate is None:
                continue
            key = ((vname or "").strip(), financial_year(vdate))
            here_counts[key] = here_counts.get(key, 0) + 1
        for key in sorted(set(tally_counts) | set(here_counts)):
            t, h = tally_counts.get(key, 0), here_counts.get(key, 0)
            tally_total += t
            here_total += h
            if t != h:
                count_drift.append({"voucher_type": key[0], "financial_year": key[1], "tally": t, "here": h})

    report = (await db.execute(select(TallyParityReport).where(TallyParityReport.company_id == company_id))).scalars().first()
    if report is None:
        report = TallyParityReport(company_id=company_id)
        db.add(report)
    report.taken_at, report.list_id = get_ist_now(), list_id
    report.ledgers_checked, report.ledgers_drifting = checked, drifting
    report.vouchers_tally, report.vouchers_here = tally_total, here_total
    report.top_ledgers, report.voucher_count_drift = top, count_drift
    return {"ledgers_checked": checked, "ledgers_drifting": drifting, "voucher_count_drift": len(count_drift)}


async def parity_summary(db: AsyncSession, company_id: int) -> Optional[Dict[str, Any]]:
    report = (await db.execute(select(TallyParityReport).where(TallyParityReport.company_id == company_id))).scalars().first()
    if report is None:
        return None
    return {
        "taken_at": report.taken_at.isoformat() if report.taken_at else None,
        "ledgers_checked": report.ledgers_checked or 0,
        "ledgers_drifting": report.ledgers_drifting or 0,
        "vouchers_in_tally": report.vouchers_tally or 0,
        "vouchers_here": report.vouchers_here or 0,
        "top_ledgers": report.top_ledgers or [],
        "voucher_count_drift": report.voucher_count_drift or [],
        "in_sync": not (report.ledgers_drifting or report.voucher_count_drift),
    }
