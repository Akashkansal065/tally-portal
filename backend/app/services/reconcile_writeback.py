"""Writing a bank reconciliation back to Tally, the safe way (WS-14). Per company, behind the
`reconcile_writeback` integration switch (off by default).

MyTally only *queues a request*: a VoucherReconcile row in the ordinary outbound queue, carrying the voucher's
master id and date, the AlterID MyTally last saw and the one bank allocation with its new BANKERSDATE and
BANKMANUALSTATUS. The sync agent then reads the voucher's current XML from Tally, refuses if its AlterID differs,
changes only those two tags and sends it back as an Alter addressed by master id and date (see
desktop-sync-agent/reconcile_writeback.py). The agent reports the outcome and only then does MyTally record it.
Asking again for the same values is a no-op, and a request for an entry that is waiting is replaced, not stacked.
"""
from datetime import date
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from xml.sax.saxutils import escape

from app.core.datetime_utils import get_ist_now
from app.models.portal_core import AuditLog, Company, SyncQueue
from app.models.tally_core import TrnAccounting, TrnBankAllocation, TrnVoucher

RECORD_TYPE = "VoucherReconcile"
INTEGRATION_KEY = "reconcile_writeback"
STATUS_VALUES = ("", "Yes", "No")


class WritebackRefused(Exception):
    def __init__(self, message: str, status_code: int = 409):
        super().__init__(message)
        self.status_code = status_code


def _yyyymmdd(d: Optional[date]) -> str:
    return d.strftime("%Y%m%d") if d else ""


async def queue_writeback(db: AsyncSession, company_id: int, user_id: int, voucher_id: int, allocation_id: int,
                          bankers_date: Optional[date], manual_status: Optional[str]) -> Dict[str, Any]:
    status = (manual_status or "").strip()
    if status not in STATUS_VALUES:
        raise WritebackRefused("manual_status must be Yes, No or empty.", 400)
    voucher = (await db.execute(select(TrnVoucher).where(
        TrnVoucher.voucher_id == voucher_id, TrnVoucher.company_id == company_id))).scalars().first()
    if voucher is None:
        raise WritebackRefused("Voucher not found.", 404)
    if not voucher.tally_master_id:
        raise WritebackRefused("This voucher is not known to Tally yet (no master id), so it cannot be reconciled there.")
    alloc = (await db.execute(
        select(TrnBankAllocation, TrnAccounting).join(TrnAccounting, TrnBankAllocation.entry_id == TrnAccounting.entry_id)
        .where(TrnBankAllocation.allocation_id == allocation_id, TrnAccounting.voucher_id == voucher.voucher_id))).first()
    if alloc is None:
        raise WritebackRefused("That bank allocation does not belong to this voucher.", 404)
    allocation = alloc[0]

    request = {
        "master_id": int(voucher.tally_master_id), "date": _yyyymmdd(voucher.tally_date or voucher.voucher_date),
        "alter_id": voucher.tally_alter_id, "allocation_id": allocation.allocation_id,
        "instrument_number": allocation.instrument_number or "", "amount": f"{abs(allocation.amount or 0):.2f}",
        "bankers_date": _yyyymmdd(bankers_date), "manual_status": status,
    }
    pending = (await db.execute(select(SyncQueue).where(
        SyncQueue.company_id == company_id, SyncQueue.record_type == RECORD_TYPE,
        SyncQueue.record_id == voucher.voucher_id, SyncQueue.is_processed == False))).scalars().all()  # noqa: E712
    same = [p for p in pending if (p.snapshot_data or {}).get("allocation_id") == allocation.allocation_id]
    stored_same = (allocation.bankers_date == bankers_date and (allocation.bank_manual_status or "") == status)
    if stored_same and not same:
        return {"status": "unchanged", "message": "MyTally already holds these values."}
    if same:
        # One request per entry at a time: the newest values replace the waiting ones
        row = same[0]
        row.snapshot_data = request
        row.status, row.error_message = "PENDING", None
        await db.commit()
        return {"status": "queued", "sync_id": row.sync_id, "replaced": True}
    row = SyncQueue(company_id=company_id, record_type=RECORD_TYPE, record_id=voucher.voucher_id, action="Alter",
                    is_processed=False, status="PENDING", snapshot_data=request)
    db.add(row)
    db.add(AuditLog(company_id=company_id, user_id=user_id, action="RECONCILE_WRITEBACK_QUEUED",
                    entity_type="Voucher", entity_id=voucher.voucher_id, new_value=request))
    await db.commit()
    await db.refresh(row)
    return {"status": "queued", "sync_id": row.sync_id, "replaced": False}


def marker_xml(company_name: str, request: Dict[str, Any], voucher_id: int) -> str:
    """The directive the agent receives in place of a ready-made Tally payload."""
    x = escape
    return (f'<MYTALLYRECONCILE VERSION="1" VOUCHERID="{int(voucher_id)}">'
            f"<SVCURRENTCOMPANY>{x(company_name)}</SVCURRENTCOMPANY>"
            f"<MASTERID>{int(request['master_id'])}</MASTERID><DATE>{x(str(request['date']))}</DATE>"
            f"<ALTERID>{x(str(request.get('alter_id') or ''))}</ALTERID>"
            f"<ALLOCATION><INSTRUMENTNUMBER>{x(str(request.get('instrument_number') or ''))}</INSTRUMENTNUMBER>"
            f"<AMOUNT>{x(str(request.get('amount') or ''))}</AMOUNT>"
            f"<BANKERSDATE>{x(str(request.get('bankers_date') or ''))}</BANKERSDATE>"
            f"<BANKMANUALSTATUS>{x(str(request.get('manual_status') or ''))}</BANKMANUALSTATUS></ALLOCATION>"
            "</MYTALLYRECONCILE>")


async def record_result(db: AsyncSession, company_id: int, sync_id: int, outcome: str, alter_id: str, message: str) -> Dict[str, Any]:
    """What the agent reports. Done/already: MyTally now holds the values and the new AlterID, and the request is
    finished. Stale/failed: nothing is changed here and the request is marked failed with the reason."""
    row = (await db.execute(select(SyncQueue).where(
        SyncQueue.sync_id == sync_id, SyncQueue.company_id == company_id, SyncQueue.record_type == RECORD_TYPE))).scalars().first()
    if row is None:
        raise WritebackRefused("Request not found.", 404)
    if row.is_processed and row.status == "SUCCESS":
        return {"status": "already_recorded"}
    request = row.snapshot_data or {}
    now = get_ist_now()
    row.last_attempt_at, row.attempts = now, (row.attempts or 0) + 1
    if outcome in ("done", "already"):
        allocation = (await db.execute(select(TrnBankAllocation).where(
            TrnBankAllocation.allocation_id == request.get("allocation_id")))).scalars().first()
        voucher = (await db.execute(select(TrnVoucher).where(
            TrnVoucher.voucher_id == row.record_id, TrnVoucher.company_id == company_id))).scalars().first()
        if allocation is not None and voucher is not None:
            bd = request.get("bankers_date") or ""
            allocation.bankers_date = date(int(bd[0:4]), int(bd[4:6]), int(bd[6:8])) if len(bd) == 8 else None
            allocation.bank_manual_status = request.get("manual_status") or None
            if alter_id and str(alter_id).isdigit():
                voucher.tally_alter_id = int(alter_id)
        row.is_processed, row.status, row.error_message = True, "SUCCESS", None
    else:
        row.is_processed, row.status = True, "FAILED"
        row.error_message = (message or outcome)[:500]
    db.add(AuditLog(company_id=company_id, user_id=None, action=f"RECONCILE_WRITEBACK_{outcome.upper()}",
                    entity_type="Voucher", entity_id=row.record_id, new_value={"message": (message or "")[:300], "alter_id": alter_id}))
    await db.commit()
    return {"status": outcome}
