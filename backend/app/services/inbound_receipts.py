"""Durable receipts for /sync/inbound (WS-9).

The agent sends an Idempotency-Key with each upload (company GUID + collection + AlterID window + payload
hash). With a key:

  * no receipt        -> record one as PROCESSING (committed before the import starts), then import;
  * receipt DONE      -> the same payload gets the stored answer back, no import; a different payload under
                         the key is refused (422);
  * receipt PROCESSING-> another request is importing it: answer "busy". If it has been PROCESSING longer than
                         STALE_PROCESSING the worker died: the retry takes it over and imports again;
  * receipt FAILED    -> the earlier try changed nothing worth keeping: import again.

The import itself commits in many steps, so receipt and import cannot share one transaction. Recovery is the
other half: re-importing the same export is safe (the importer upserts by Tally GUID and AlterID), so a crash
between the import and the DONE mark only costs a repeat, never a duplicate. A stored answer is replayed for
REPLAY_WINDOW only, which is what a lost response needs; after that the upload is imported again, so a
server restored from a backup, or a company's data removed, is never blocked by an old receipt.
Receipts are scoped by company_id, so one company's key can never answer for another's.
"""
import hashlib
import logging
import re
from datetime import timedelta
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime_utils import get_ist_now
from app.models.portal_core import SyncInboundReceipt

logger = logging.getLogger("uvicorn.error")

STALE_PROCESSING = timedelta(minutes=20)
REPLAY_WINDOW = timedelta(minutes=15)
RETENTION = timedelta(days=7)
KEY_PATTERN = re.compile(r"^[A-Za-z0-9._:\-]{8,128}$")

RUN, REPLAY, MISMATCH, BUSY = "run", "replay", "mismatch", "busy"


def valid_key(key: Optional[str]) -> Optional[str]:
    key = (key or "").strip()
    return key if KEY_PATTERN.match(key) else None


def payload_hash(body: bytes, force: bool) -> str:
    h = hashlib.sha256(body)
    h.update(b"|force" if force else b"|plain")
    return h.hexdigest()


async def begin(db: AsyncSession, company_id: int, key: str, sha: str, force: bool) -> Tuple[str, Any]:
    """Decide what to do with an upload. Returns (RUN, receipt_id) / (REPLAY, response) / (MISMATCH, None) /
    (BUSY, None). Commits."""
    now = get_ist_now()
    for _ in range(2):
        row = (await db.execute(select(SyncInboundReceipt).where(
            SyncInboundReceipt.company_id == company_id, SyncInboundReceipt.idempotency_key == key))).scalars().first()
        if row is None:
            receipt = SyncInboundReceipt(company_id=company_id, idempotency_key=key, payload_sha256=sha,
                                         state="PROCESSING", started_at=now)
            db.add(receipt)
            try:
                await db.commit()
            except IntegrityError:
                await db.rollback()      # a concurrent request with the same key got in first: read its row
                continue
            receipt_id = receipt.receipt_id     # read before the purge: its rollback would expire the row
            await _purge_old(db, company_id, now)
            return RUN, receipt_id
        if row.payload_sha256 != sha:
            return MISMATCH, None
        age = now - (row.finished_at or row.started_at or row.created_at or now)
        if row.state == "DONE" and not force and age <= REPLAY_WINDOW and row.response_json is not None:
            return REPLAY, row.response_json
        if row.state == "PROCESSING" and now - (row.started_at or now) <= STALE_PROCESSING:
            return BUSY, None
        # FAILED, a stale PROCESSING, a DONE too old to replay, or a forced upload: import again, but only
        # one request may take the receipt over
        taken = await db.execute(update(SyncInboundReceipt).where(
            SyncInboundReceipt.receipt_id == row.receipt_id, SyncInboundReceipt.state == row.state,
            SyncInboundReceipt.attempts == row.attempts)
            .values(state="PROCESSING", started_at=now, finished_at=None, attempts=(row.attempts or 1) + 1))
        await db.commit()
        if taken.rowcount != 1:
            return BUSY, None
        return RUN, row.receipt_id
    return BUSY, None


async def finish(db: AsyncSession, receipt_id: int, response: Optional[Dict[str, Any]], ok: bool) -> None:
    """Record how the import ended. Only a successful import keeps its answer for replay."""
    await db.execute(update(SyncInboundReceipt).where(SyncInboundReceipt.receipt_id == receipt_id).values(
        state="DONE" if ok else "FAILED", response_json=response if ok else None, finished_at=get_ist_now()))
    await db.commit()


async def release(db: AsyncSession, receipt_id: int) -> None:
    """The import never started (the company was busy): let the next try run at once."""
    try:
        await db.rollback()
        await db.execute(update(SyncInboundReceipt).where(
            SyncInboundReceipt.receipt_id == receipt_id, SyncInboundReceipt.state == "PROCESSING")
            .values(state="FAILED", finished_at=get_ist_now()))
        await db.commit()
    except Exception as e:
        logger.warning(f"Could not release inbound receipt {receipt_id}: {e}")


async def _purge_old(db: AsyncSession, company_id: int, now) -> None:
    try:
        await db.execute(delete(SyncInboundReceipt).where(
            SyncInboundReceipt.company_id == company_id, SyncInboundReceipt.created_at < now - RETENTION))
        await db.commit()
    except Exception as e:
        logger.warning(f"Could not purge old inbound receipts for company {company_id}: {e}")
        await db.rollback()
