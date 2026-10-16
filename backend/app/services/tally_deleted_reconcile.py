"""Records deleted inside Tally (WS-3).

An AlterID-filtered export only returns objects that still exist, so a voucher or master deleted in Tally
would stay in MyTally for ever. The Desktop Sync Agent therefore sends, now and then, the complete list of
active keys Tally holds. A record MyTally holds with a Tally identity that is missing from two consecutive
complete lists is soft-deleted: vouchers are marked cancelled (every report already leaves those out),
ledgers and stock items are deactivated. The row in tally_missing_records says what it was; nothing is ever
hard-deleted, and a record that shows up in a later list is put back.

Safety rules, all of which only ever err towards keeping a record:
  - only a list the agent calls complete is used, and one whose count disagrees with itself is ignored;
  - an empty list removes nothing;
  - the same list arriving twice (same list_id) counts once;
  - records without a Tally identity, with a provisional number, or with an entry still waiting in the
    outbound queue are never touched; nor is anything created or changed in the last RECENT_GRACE;
  - a list that would remove more than a quarter of a company's records at once is held back.
"""
import logging
from datetime import timedelta
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime_utils import get_ist_now
from app.models.portal_core import SyncQueue, TallyKeyListState, TallyMissingRecord
from app.models.tally_core import MstLedger, MstStockItem, TrnVoucher

logger = logging.getLogger("uvicorn.error")

CONSECUTIVE_LISTS_NEEDED = 2
RECENT_GRACE = timedelta(hours=1)
MASS_REMOVAL_FRACTION = 0.25
MASS_REMOVAL_FLOOR = 25      # fewer than this many is never "mass"

ENTITIES = ("Voucher", "Ledger", "StockItem")


def _int(value: Any) -> Optional[int]:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _clean_keys(items: Iterable[Dict[str, Any]]):
    master_ids, guids = set(), set()
    for item in items or []:
        m, g = _int(item.get("master_id")), (item.get("guid") or "").strip()
        if m is not None:
            master_ids.add(m)
        if g:
            guids.add(g)
    return master_ids, guids


def _model_for(entity: str):
    return {"Voucher": TrnVoucher, "Ledger": MstLedger, "StockItem": MstStockItem}[entity]


def _pk(entity: str):
    return {"Voucher": TrnVoucher.voucher_id, "Ledger": MstLedger.ledger_id, "StockItem": MstStockItem.stock_item_id}[entity]


def _prior(entity: str, row) -> Dict[str, Any]:
    if entity == "Voucher":
        return {"is_cancelled": bool(row.is_cancelled), "status": row.status}
    return {"is_active": row.is_active if row.is_active is not None else True}


def _identifier(entity: str, row) -> str:
    if entity == "Voucher":
        return f"#{row.voucher_number} on {row.voucher_date}"[:255]
    return (row.name or "")[:255]


def _remove(entity: str, row) -> None:
    if entity == "Voucher":
        row.is_cancelled = True
        row.status = "cancelled"
    else:
        row.is_active = False


def _put_back(entity: str, row, prior: Dict[str, Any]) -> None:
    # Only undo what this module did: an import since then may already have set the record from Tally
    if entity == "Voucher":
        if row.is_cancelled and not prior.get("is_cancelled", False):
            row.is_cancelled = False
            row.status = prior.get("status") or "confirmed"
    elif row.is_active is False and prior.get("is_active", True):
        row.is_active = True


async def _reconcile_entity(db: AsyncSession, company_id: int, entity: str, items: List[Dict[str, Any]],
                            list_id: str) -> Dict[str, Any]:
    result = {"entity": entity, "received": len(items), "missing": 0, "deleted": 0, "restored": 0,
              "held_back": 0, "skipped": None}
    if not items:
        result["skipped"] = "empty_list"
        return result

    state = (await db.execute(select(TallyKeyListState).where(
        TallyKeyListState.company_id == company_id, TallyKeyListState.entity_type == entity))).scalars().first()
    if state is not None and state.last_list_id == list_id:
        result["skipped"] = "duplicate_list"
        return result

    master_ids, guids = _clean_keys(items)
    if not master_ids and not guids:
        result["skipped"] = "no_keys"
        return result

    model, pk = _model_for(entity), _pk(entity)
    rows = (await db.execute(select(model).where(model.company_id == company_id))).scalars().all()
    existing = {(r.entity_type, r.record_id): r for r in (await db.execute(
        select(TallyMissingRecord).where(TallyMissingRecord.company_id == company_id,
                                         TallyMissingRecord.entity_type == entity))).scalars().all()}
    pending = {r for (r,) in (await db.execute(
        select(SyncQueue.record_id).where(SyncQueue.company_id == company_id, SyncQueue.record_type == entity,
                                          SyncQueue.is_processed == False)))}  # noqa: E712
    recent_after = get_ist_now() - RECENT_GRACE
    now = get_ist_now()

    def record_id(row) -> int:
        return getattr(row, pk.key)

    def in_list(row) -> bool:
        return (row.tally_master_id is not None and row.tally_master_id in master_ids) or \
               (bool(row.tally_guid) and row.tally_guid in guids)

    eligible_missing, eligible_total = [], 0
    for row in rows:
        rid = record_id(row)
        tracked = existing.get((entity, rid))
        if in_list(row):
            # Present in Tally: forget any streak and put back what an earlier list removed
            if tracked is not None and tracked.status in ("missing", "deleted"):
                if tracked.status == "deleted":
                    _put_back(entity, row, tracked.prior_state or {})
                    result["restored"] += 1
                tracked.status = "restored" if tracked.status == "deleted" else "missing"
                tracked.streak = 0
                tracked.restored_at = now if tracked.status == "restored" else tracked.restored_at
                tracked.last_list_id = list_id
            continue
        if row.tally_master_id is None and not row.tally_guid:
            continue                                  # never confirmed in Tally
        if entity == "Voucher" and row.number_is_provisional:
            continue
        if rid in pending:
            continue
        stamp = getattr(row, "updated_at", None) or getattr(row, "created_at", None)
        if stamp is not None and stamp >= recent_after:
            continue
        if tracked is not None and tracked.status == "deleted":
            continue                                  # already removed by an earlier list
        eligible_total += 1
        eligible_missing.append((row, tracked))

    total_known = sum(1 for r in rows if (r.tally_master_id is not None or r.tally_guid))
    result["missing"] = len(eligible_missing)
    mass = (len(eligible_missing) >= MASS_REMOVAL_FLOOR and total_known and
            len(eligible_missing) > total_known * MASS_REMOVAL_FRACTION)

    for row, tracked in eligible_missing:
        rid = record_id(row)
        if tracked is None or tracked.status == "restored":
            if tracked is None:
                tracked = TallyMissingRecord(company_id=company_id, entity_type=entity, record_id=rid,
                                             tally_master_id=row.tally_master_id, tally_guid=row.tally_guid,
                                             identifier=_identifier(entity, row),
                                             last_alter_id=getattr(row, "tally_alter_id", None),
                                             first_missing_at=now)
                db.add(tracked)
            tracked.status, tracked.streak, tracked.restored_at = "missing", 0, None
        tracked.streak = (tracked.streak or 0) + 1
        tracked.last_list_id = list_id
        if tracked.streak >= CONSECUTIVE_LISTS_NEEDED:
            if mass:
                result["held_back"] += 1
                continue
            tracked.prior_state = _prior(entity, row)
            tracked.status, tracked.deleted_at = "deleted", now
            _remove(entity, row)
            result["deleted"] += 1

    if state is None:
        db.add(TallyKeyListState(company_id=company_id, entity_type=entity, last_list_id=list_id,
                                 last_list_at=now, last_key_count=len(items)))
    else:
        state.last_list_id, state.last_list_at, state.last_key_count = list_id, now, len(items)
    return result


async def apply_active_key_lists(db: AsyncSession, company_id: int, list_id: str, complete: bool,
                                 lists: Dict[str, Optional[List[Dict[str, Any]]]],
                                 expected_counts: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
    """Apply one set of active-key lists for a company. `lists` maps an entity type to its list, or None for a
    type the agent did not export. Commits. Returns what was done per type."""
    if not complete:
        return {"status": "ignored", "reason": "incomplete", "results": []}
    results = []
    for entity in ENTITIES:
        items = lists.get(entity)
        if items is None:
            continue
        expected = (expected_counts or {}).get(entity)
        if expected is not None and expected != len(items):
            results.append({"entity": entity, "received": len(items), "skipped": "count_mismatch"})
            continue
        results.append(await _reconcile_entity(db, company_id, entity, items, list_id))
    await db.flush()
    parity = None
    if lists.get("Voucher") or lists.get("Ledger"):
        # A verification only: it reads the books and writes its own report row, and must never fail the list
        try:
            from app.services.books_parity import build_parity_report
            parity = await build_parity_report(db, company_id, list_id, lists.get("Voucher"), lists.get("Ledger"))
        except Exception as e:
            logger.warning(f"Books-parity check failed for company {company_id}: {e}", exc_info=True)
    await db.commit()
    return {"status": "ok", "results": results, "parity": parity}


async def deleted_in_tally_count(db: AsyncSession, company_id: int) -> int:
    from sqlalchemy import func
    return (await db.execute(select(func.count(TallyMissingRecord.missing_id)).where(
        TallyMissingRecord.company_id == company_id, TallyMissingRecord.status == "deleted"))).scalar() or 0
