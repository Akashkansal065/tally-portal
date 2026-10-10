"""
Deleting a stock group together with everything that blocks the delete: the stock-group counterpart of
group_deletion, built on the same pieces.

build_stock_group_delete_plan() lists every sub-group and stock item under the group, from MyTally and from
Tally, in the order they would have to be deleted, and marks the ones that cannot be (used in vouchers,
still referenced elsewhere). execute_stock_group_delete_plan() deletes them in that order, Tally first.
Every step is safe to repeat, and only one delete of a given stock group runs at a time.
"""
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.core.logging_config import get_logger
from app.core.permissions import get_effective_permission
from app.models.portal_core import Company, DeletedRecordAudit, User
from app.models.tally_core import MstStockGroup, MstStockItem, StockGroupAlias
from app.services.group_deletion import (
    GroupDeleteInProgress, TallyUnreachable, _blocking_references, _delete_in_tally, _describe_references,
    fetch_tally_members, queue_sync_event,
)

logger = get_logger("app.services.stock_group_deletion")

_stock_groups_being_deleted: set = set()

TALLY_CONTAINER = ("Stock Group", "StockGroup", "STOCKGROUP")
TALLY_MEMBER = ("StockItem", "STOCKITEM")


async def build_stock_group_delete_plan(db: AsyncSession, user: User, group: MstStockGroup) -> dict:
    """
    Everything that has to go before the stock group can, deepest first, ending with the group itself.
    Same shape as the account-group plan; items have kind "group" (stock group) or "item" (stock item).
    """
    company_id = group.company_id
    comp = (await db.execute(select(Company).where(Company.company_id == company_id))).scalars().first()
    company_name = comp.name if comp else ""

    tally: Optional[dict] = None
    tally_message = None
    if not settings.TALLY_URL:
        tally_message = "Tally is not connected; only MyTally was checked."
    else:
        tally = await fetch_tally_members(settings.TALLY_URL, company_name, group.name, TALLY_CONTAINER, TALLY_MEMBER)
        if tally is None:
            tally_message = "Tally could not be reached; only MyTally was checked."

    # Stock groups under the root in MyTally, level by level
    app_groups: Dict[int, MstStockGroup] = {group.stock_group_id: group}
    frontier = [group.stock_group_id]
    while frontier:
        res = await db.execute(select(MstStockGroup).where(MstStockGroup.company_id == company_id, MstStockGroup.parent_id.in_(frontier)))
        frontier = []
        for child in res.scalars().all():
            if child.stock_group_id not in app_groups:
                app_groups[child.stock_group_id] = child
                frontier.append(child.stock_group_id)

    res = await db.execute(select(MstStockItem).where(MstStockItem.company_id == company_id, MstStockItem.stock_group_id.in_(list(app_groups))))
    app_items = res.scalars().all()
    item_refs = await _blocking_references(db, MstStockItem.__table__.c.stock_item_id, [i.stock_item_id for i in app_items])
    can_delete_items = bool((await get_effective_permission(user, "stock_items", db)).get("can_delete", False)) if app_items or tally else True

    nodes: Dict[Tuple[str, str], dict] = {}

    def node(kind: str, name: str) -> dict:
        key = (kind, name.strip().lower())
        if key not in nodes:
            nodes[key] = {"kind": kind, "name": name.strip(), "parent": None, "app_id": None, "in_app": False,
                          "in_tally": False, "is_root": False, "can_delete": True, "reason": None}
        return nodes[key]

    def block(item: dict, reason: str):
        if item["can_delete"]:
            item["can_delete"] = False
            item["reason"] = reason

    for g in app_groups.values():
        item = node("group", g.name)
        item.update(app_id=g.stock_group_id, in_app=True)
        if g.stock_group_id != group.stock_group_id and g.parent_id in app_groups:
            item["parent"] = app_groups[g.parent_id].name

    for i in app_items:
        item = node("item", i.name)
        item.update(app_id=i.stock_item_id, in_app=True, parent=app_groups[i.stock_group_id].name)
        if item_refs.get(i.stock_item_id):
            block(item, f"Still used in MyTally ({_describe_references(item_refs[i.stock_item_id])}); remove those entries first.")
        if not can_delete_items:
            block(item, "You do not have permission to delete stock items.")

    root_key = group.name.strip().lower()
    if tally:
        for g in tally["groups"].values():
            item = node("group", g["name"])
            item["in_tally"] = True
            if g["name"].lower() != root_key and not item["parent"]:
                item["parent"] = g["parent"]
        for i in tally["ledgers"].values():
            item = node("item", i["name"])
            item["in_tally"] = True
            if not item["parent"]:
                item["parent"] = i["parent"]
            if not i["can_delete"]:
                block(item, "Tally will not delete it: it is used in vouchers or has stock there.")
            if not can_delete_items:
                block(item, "You do not have permission to delete stock items.")

    root = nodes[("group", root_key)]
    root["is_root"] = True
    root["parent"] = None

    # Deletion order: for each group its items, then its sub-groups (recursively), then the group
    children: Dict[str, List[dict]] = {}
    for item in nodes.values():
        if not item["is_root"] and item["parent"]:
            children.setdefault(item["parent"].strip().lower(), []).append(item)

    ordered: List[dict] = []
    visited = set()

    def walk(item: dict):
        key = item["name"].lower()
        if key in visited:
            return
        visited.add(key)
        inside = sorted(children.get(key, []), key=lambda c: (c["kind"] != "item", c["name"].lower()))
        blocked_inside = 0
        for child in inside:
            if child["kind"] == "group":
                walk(child)
            else:
                ordered.append(child)
            if not child["can_delete"]:
                blocked_inside += 1
        if blocked_inside:
            block(item, f"Contains {blocked_inside} item{'' if blocked_inside == 1 else 's'} that cannot be deleted.")
        ordered.append(item)

    walk(root)

    blockers = [i for i in ordered if not i["is_root"]]
    return {
        "group_id": group.stock_group_id,
        "group_name": group.name,
        "items": ordered,
        "blocker_count": len(blockers),
        "undeletable_count": sum(1 for i in blockers if not i["can_delete"]),
        "can_delete_all": all(i["can_delete"] for i in ordered),
        "tally_checked": tally is not None,
        "tally_message": tally_message,
    }


async def _delete_item(db: AsyncSession, user: User, company_name: str, item: dict, tally_available: bool) -> Tuple[bool, Optional[str]]:
    """Deletes one plan item on both sides, Tally first. (deleted, why not)."""
    company_id = user.company_id
    is_group = item["kind"] == "group"
    record_type = "StockGroup" if is_group else "StockItem"

    sync_item = None
    if item["in_app"]:
        # The name is all a later retry or the Desktop Sync Agent has once the row is gone
        sync_item = await queue_sync_event(db, company_id, record_type, item["app_id"], "Delete", {"tally_name": item["name"]})
        await db.commit()

    if tally_available and item["in_tally"]:
        outcome, reason = await _delete_in_tally(
            db, company_id, company_name, item, sync_item.sync_id if sync_item else None,
            tag="STOCKGROUP" if is_group else "STOCKITEM", entity_type=record_type)
        if outcome == "REJECTED":
            if sync_item:
                await db.delete(sync_item)
                await db.commit()
            return False, f"Tally refused: {reason}"

    if item["in_app"]:
        if is_group:
            row = (await db.execute(select(MstStockGroup).where(
                MstStockGroup.stock_group_id == item["app_id"], MstStockGroup.company_id == company_id))).scalars().first()
            if row:
                for alias in (await db.execute(select(StockGroupAlias).where(StockGroupAlias.stock_group_id == row.stock_group_id))).scalars().all():
                    await db.delete(alias)
        else:
            row = (await db.execute(select(MstStockItem).where(
                MstStockItem.stock_item_id == item["app_id"], MstStockItem.company_id == company_id))).scalars().first()
            if row:
                audit = (await db.execute(select(DeletedRecordAudit).where(
                    DeletedRecordAudit.company_id == company_id,
                    DeletedRecordAudit.entity_type == "StockItem",
                    DeletedRecordAudit.record_id == row.stock_item_id,
                ))).scalars().first()
                if not audit:
                    db.add(DeletedRecordAudit(
                        company_id=company_id, entity_type="StockItem", record_id=row.stock_item_id,
                        tally_guid=getattr(row, 'guid', None) or f"MYTALLY-ITEM-{row.stock_item_id}",
                        entity_identifier=row.name, deleted_by_user_id=user.user_id,
                        tally_sync_status="SYNCED_TO_TALLY" if tally_available else "PENDING",
                        snapshot_data={"stock_item_id": row.stock_item_id, "company_id": company_id, "name": row.name,
                                       "stock_group_id": row.stock_group_id, "unit_id": row.unit_id},
                    ))
        if row:
            try:
                await db.delete(row)
                await db.flush()
            except IntegrityError:
                # The plan checks references before anything is deleted, so this is a row added since
                await db.rollback()
                logger.error(f"{record_type} '{item['name']}' is gone from Tally but still referenced in MyTally", exc_info=True)
                return False, "Deleted in Tally, but other MyTally records still refer to it, so it remains in MyTally."
        # With Tally available the delete has been settled there; without it the row stays pending for the agent
        if sync_item and tally_available:
            sync_item.is_processed = True
            sync_item.status = "SUCCESS"
            sync_item.attempts = (sync_item.attempts or 0) + 1
            sync_item.last_attempt_at = func.now()
        await db.commit()
    return True, None


async def execute_stock_group_delete_plan(db: AsyncSession, user: User, group: MstStockGroup, cascade: bool) -> dict:
    """
    Deletes the stock group, and with cascade everything under it, in plan order.
    Returns {"status", "plan", "deleted", "failed"} with status deleted / blocked / partial / unreachable,
    as for account groups. Raises GroupDeleteInProgress when the same group is already being deleted.
    """
    lock_key = (group.company_id, group.stock_group_id)
    if lock_key in _stock_groups_being_deleted:
        raise GroupDeleteInProgress()
    _stock_groups_being_deleted.add(lock_key)
    try:
        plan = await build_stock_group_delete_plan(db, user, group)
        if (plan["blocker_count"] and not cascade) or not plan["can_delete_all"]:
            return {"status": "blocked", "plan": plan, "deleted": [], "failed": []}

        comp = (await db.execute(select(Company).where(Company.company_id == group.company_id))).scalars().first()
        company_name = comp.name if comp else ""
        group_id = group.stock_group_id

        deleted: List[dict] = []
        failed: List[dict] = []
        status_code = "deleted"
        refused: set = set()
        for item in plan["items"]:
            if item["kind"] == "group" and item["name"].lower() in refused:
                # Something inside it is still there, so Tally would only refuse this one too
                failed.append({"kind": item["kind"], "name": item["name"], "reason": "Not attempted: an item inside it could not be deleted."})
                if item["parent"]:
                    refused.add(item["parent"].lower())
                continue
            try:
                ok, reason = await _delete_item(db, user, company_name, item, plan["tally_checked"])
            except TallyUnreachable:
                await db.rollback()
                status_code = "unreachable"
                break
            if ok:
                deleted.append({"kind": item["kind"], "name": item["name"]})
            else:
                status_code = "partial"
                failed.append({"kind": item["kind"], "name": item["name"], "reason": reason})
                if item["parent"]:
                    refused.add(item["parent"].lower())

        if status_code != "deleted":
            remaining = (await db.execute(select(MstStockGroup).where(MstStockGroup.stock_group_id == group_id))).scalars().first()
            if remaining:
                plan = await build_stock_group_delete_plan(db, user, remaining)
        logger.info(f"Stock group delete '{plan['group_name']}' (cascade={cascade}) by user {user.user_id}: {status_code}, "
                    f"{len(deleted)} deleted, {len(failed)} failed")
        return {"status": status_code, "plan": plan, "deleted": deleted, "failed": failed}
    finally:
        _stock_groups_being_deleted.discard(lock_key)
