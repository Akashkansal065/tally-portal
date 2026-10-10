"""
Deleting an account group together with everything that blocks the delete.

A group cannot be deleted while it holds sub-groups or ledgers, in MyTally or in Tally, and Tally will not
say what is in the way. build_delete_plan() lists every sub-group and ledger under the group from both
sides, in the order they would have to be deleted, and marks the ones that can never be deleted (used in
vouchers, predefined in Tally, no permission). execute_delete_plan() deletes them in that order.

Every step is safe to repeat: an object already gone from one side is skipped rather than deleted again,
queue rows and delete audits are reused instead of duplicated, and only one delete of a given group runs
at a time. A run that stops half way can simply be run again.
"""
import asyncio
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.core.logging_config import get_logger
from app.core.permissions import get_effective_permission
from app.models.portal_core import Company, DeletedRecordAudit, SyncQueue, User
from app.models.tally_core import MstGroup, MstLedger
from app.services.tally_xml import x
from app.services.tally_xml_importer import sanitize_xml, tally_parent_name

logger = get_logger("app.services.group_deletion")

# Deletes of the same group must not overlap (a double click, a retry while the first is still running)
_groups_being_deleted: set = set()


class GroupDeleteInProgress(Exception):
    pass


# The same guard for single ledger deletes
_ledgers_being_deleted: set = set()


def begin_ledger_delete(company_id: int, ledger_id: int) -> bool:
    """False when this ledger is already being deleted by another request; otherwise claims it."""
    key = (company_id, ledger_id)
    if key in _ledgers_being_deleted:
        return False
    _ledgers_being_deleted.add(key)
    return True


def end_ledger_delete(company_id: int, ledger_id: int):
    _ledgers_being_deleted.discard((company_id, ledger_id))


class TallyUnreachable(Exception):
    pass


async def queue_sync_event(db: AsyncSession, company_id: int, record_type: str, record_id: int, action: str,
                           snapshot: Optional[dict] = None) -> SyncQueue:
    """
    Queues a push for this record. Rows this one makes redundant are closed when it is flushed, and the
    name Tally still knows the record by is carried over from them (see portal_core): after two renames
    Tally still knows the record by the first name.
    """
    item = SyncQueue(company_id=company_id, record_type=record_type, record_id=record_id, action=action,
                     snapshot_data=snapshot)
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return item


# ---------------------------------------------------------------------------------------------------
# What Tally holds under the group
# ---------------------------------------------------------------------------------------------------

def _export_envelope(header: str, company_name: str, extra: str = "") -> str:
    return f"""<ENVELOPE>
  <HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST>{header}</HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES><SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT><SVCURRENTCOMPANY>{x(company_name)}</SVCURRENTCOMPANY></STATICVARIABLES>
      {extra}
    </DESC>
  </BODY>
</ENVELOPE>"""


def _members_envelope(obj_type: str, group_name: str, company_name: str) -> str:
    """Every object of this type at any depth under the group, with whether Tally would let it be deleted."""
    return _export_envelope(
        "<TYPE>Collection</TYPE><ID>MyTallyGroupMembers</ID>", company_name,
        f"""<TDL><TDLMESSAGE>
        <COLLECTION NAME="MyTallyGroupMembers">
          <TYPE>{obj_type}</TYPE>
          <CHILDOF>{x(group_name)}</CHILDOF>
          <BELONGSTO>Yes</BELONGSTO>
          <NATIVEMETHOD>Name, Parent, CanDelete</NATIVEMETHOD>
        </COLLECTION>
      </TDLMESSAGE></TDL>""")


def _parse_members(resp: str, tag: str) -> Optional[Dict[str, dict]]:
    try:
        root = ET.fromstring(sanitize_xml(resp).strip())
    except ET.ParseError:
        return None
    members = {}
    for node in root.iter(tag):
        name = node.get("NAME")
        if not name:
            continue  # <CMPINFO> carries a counter with the same tag
        members[name.strip().lower()] = {
            "name": name.strip(),
            "parent": tally_parent_name(node.findtext("PARENT")),
            "can_delete": (node.findtext("CANDELETE") or "").strip().lower() != "no",
            "reserved": bool((node.get("RESERVEDNAME") or "").strip()),
        }
    return members


async def fetch_tally_members(tally_url: str, company_name: str, group_name: str,
                              container: Tuple[str, str, str] = ("Group", "Group", "GROUP"),
                              member: Tuple[str, str] = ("Ledger", "LEDGER")) -> Optional[dict]:
    """
    {"groups": {...}, "ledgers": {...}} keyed by lower-cased name; the group itself is among the groups
    when Tally has it. None when Tally cannot be reached or its answer cannot be read.
    container is (object subtype, collection type, XML tag) and member (collection type, XML tag); the
    defaults read an account group and its ledgers, and a stock group with its stock items is read the same
    way (its items come back under "ledgers").
    """
    from app.routers.sync import _post_to_tally_sync

    # A collection over a group Tally does not have is never requested: ask for the group by name first.
    # The fetch list is mandatory, an object export without one crashes TallyPrime.
    exists_xml = _export_envelope(
        f'<TYPE>Object</TYPE><SUBTYPE>{container[0]}</SUBTYPE><ID TYPE="Name">{x(group_name)}</ID>', company_name,
        "<FETCHLIST><FETCH>Name</FETCH><FETCH>Parent</FETCH></FETCHLIST>")
    resp = await asyncio.to_thread(_post_to_tally_sync, tally_url, exists_xml, 10)
    if not resp or not resp.strip():
        return None
    if "<ERRORMSG>" in resp or "<LINEERROR>" in resp:
        if "could not find" in resp.lower():
            return {"groups": {}, "ledgers": {}}
        return None

    result = {}
    for key, obj_type, tag in (("groups", container[1], container[2]), ("ledgers", member[0], member[1])):
        resp = await asyncio.to_thread(_post_to_tally_sync, tally_url, _members_envelope(obj_type, group_name, company_name), 15)
        members = _parse_members(resp, tag) if resp and resp.strip() else None
        if members is None:
            return None
        result[key] = members
    return result


# ---------------------------------------------------------------------------------------------------
# The plan
# ---------------------------------------------------------------------------------------------------

async def _blocking_references(db: AsyncSession, target, ids: List[int], skip_tables: Tuple[str, ...] = ()) -> Dict[int, Dict[str, int]]:
    """
    {id: {table: rows}} for rows elsewhere in the database that would stop these rows being deleted:
    every foreign key to the target column that neither cascades nor nulls itself on delete.
    Read from the models, so a table added later is covered without touching this.
    """
    found: Dict[int, Dict[str, int]] = {}
    if not ids:
        return found
    for table in target.table.metadata.tables.values():
        if table.name in skip_tables:
            continue
        for fk in table.foreign_keys:
            if fk.column is not target or (fk.ondelete or "").upper() in ("CASCADE", "SET NULL"):
                continue
            rows = await db.execute(select(fk.parent, func.count()).where(fk.parent.in_(ids)).group_by(fk.parent))
            for ref_id, count in rows.all():
                found.setdefault(ref_id, {})[table.name] = found.get(ref_id, {}).get(table.name, 0) + count
    return found


def _describe_references(refs: Dict[str, int]) -> str:
    return ", ".join(f"{count} in {table.replace('_', ' ')}" for table, count in sorted(refs.items()))


async def _ledger_delete_module(db: AsyncSession, company_id: int, group_id: int, known: Dict[int, MstGroup]) -> str:
    """The permission module a ledger in this group falls under, as the ledger delete endpoint decides it."""
    seen = set()
    current_id: Optional[int] = group_id
    while current_id is not None and current_id not in seen:
        seen.add(current_id)
        if current_id not in known:
            res = await db.execute(select(MstGroup).where(MstGroup.group_id == current_id, MstGroup.company_id == company_id))
            found = res.scalars().first()
            if not found:
                break
            known[current_id] = found
        current = known[current_id]
        lowered = current.name.lower()
        if lowered == "sundry debtors":
            return "ledger_customer"
        if lowered == "sundry creditors":
            return "ledger_supplier"
        current_id = current.parent_group_id
    return "ledgers"


async def build_delete_plan(db: AsyncSession, user: User, group: MstGroup) -> dict:
    """
    Everything that has to go before the group can, deepest first, ending with the group itself.

    Each item: kind ("group" / "ledger"), name, parent, app_id, in_app, in_tally, is_root, can_delete, reason.
    can_delete is False for an item that can never be deleted (its reason says why) and for a group that
    contains one. tally_checked tells whether Tally could be asked; without it the plan covers MyTally only.
    """
    company_id = group.company_id
    comp = (await db.execute(select(Company).where(Company.company_id == company_id))).scalars().first()
    company_name = comp.name if comp else ""

    tally_url = settings.TALLY_URL
    tally: Optional[dict] = None
    tally_message = None
    if not tally_url:
        tally_message = "Tally is not connected; only MyTally was checked."
    else:
        tally = await fetch_tally_members(tally_url, company_name, group.name)
        if tally is None:
            tally_message = "Tally could not be reached; only MyTally was checked."

    # Groups under the root in MyTally, level by level
    app_groups: Dict[int, MstGroup] = {group.group_id: group}
    frontier = [group.group_id]
    while frontier:
        res = await db.execute(select(MstGroup).where(MstGroup.company_id == company_id, MstGroup.parent_group_id.in_(frontier)))
        frontier = []
        for child in res.scalars().all():
            if child.group_id not in app_groups:
                app_groups[child.group_id] = child
                frontier.append(child.group_id)

    res = await db.execute(select(MstLedger).where(MstLedger.company_id == company_id, MstLedger.group_id.in_(list(app_groups))))
    app_ledgers = res.scalars().all()
    ledger_refs = await _blocking_references(db, MstLedger.__table__.c.ledger_id, [l.ledger_id for l in app_ledgers])
    # Sub-groups and ledgers are deleted before their group, so those two references are not blockers
    group_refs = await _blocking_references(db, MstGroup.__table__.c.group_id, list(app_groups),
                                            skip_tables=(MstGroup.__table__.name, MstLedger.__table__.name))

    # One node per name, merged from both sides
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
        item.update(app_id=g.group_id, in_app=True)
        if g.group_id != group.group_id and g.parent_group_id in app_groups:
            item["parent"] = app_groups[g.parent_group_id].name
        if g.is_system_defined:
            block(item, "System-defined group; it cannot be deleted.")
        if group_refs.get(g.group_id):
            block(item, f"Still used in MyTally ({_describe_references(group_refs[g.group_id])}).")

    permission_cache: Dict[str, bool] = {}
    known_groups = dict(app_groups)
    for l in app_ledgers:
        item = node("ledger", l.name)
        item.update(app_id=l.ledger_id, in_app=True, parent=app_groups[l.group_id].name)
        if ledger_refs.get(l.ledger_id):
            block(item, f"Still used in MyTally ({_describe_references(ledger_refs[l.ledger_id])}); remove those entries first.")
        module = await _ledger_delete_module(db, company_id, l.group_id, known_groups)
        if module not in permission_cache:
            permission_cache[module] = bool((await get_effective_permission(user, module, db)).get("can_delete", False))
        if not permission_cache[module]:
            block(item, "You do not have permission to delete this ledger.")

    root_key = group.name.strip().lower()
    if tally:
        for g in tally["groups"].values():
            item = node("group", g["name"])
            item["in_tally"] = True
            if g["name"].lower() != root_key and not item["parent"]:
                item["parent"] = g["parent"]
            if g["reserved"]:
                block(item, "Predefined Tally group; Tally never allows it to be deleted.")
        for l in tally["ledgers"].values():
            item = node("ledger", l["name"])
            item["in_tally"] = True
            if not item["parent"]:
                item["parent"] = l["parent"]
            if not l["can_delete"]:
                block(item, "Tally will not delete it: it is used in vouchers there, or is a predefined ledger.")

    root = nodes[("group", root_key)]
    root["is_root"] = True
    root["parent"] = None

    # Deletion order: for each group its ledgers, then its sub-groups (recursively), then the group
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
        inside = sorted(children.get(key, []), key=lambda c: (c["kind"] != "ledger", c["name"].lower()))
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
        "group_id": group.group_id,
        "group_name": group.name,
        "items": ordered,
        "blocker_count": len(blockers),
        "undeletable_count": sum(1 for i in blockers if not i["can_delete"]),
        "can_delete_all": all(i["can_delete"] for i in ordered),
        "tally_checked": tally is not None,
        "tally_message": tally_message,
    }


# ---------------------------------------------------------------------------------------------------
# Carrying the plan out
# ---------------------------------------------------------------------------------------------------

async def _delete_in_tally(db: AsyncSession, company_id: int, company_name: str, item: dict, sync_id: Optional[int],
                           tag: Optional[str] = None, entity_type: Optional[str] = None) -> Tuple[str, Optional[str]]:
    """
    Deletes one master in Tally by name. Returns (outcome, message): DELETED, ABSENT (Tally no
    longer has it, which is the state a delete is after), or REJECTED with Tally's reason.
    Raises TallyUnreachable when Tally gives no answer.
    tag / entity_type default to an account group or ledger according to item["kind"].
    """
    from app.routers.sync import _post_to_tally_sync, check_tally_success, parse_tally_response_metrics, record_sync_traffic_log

    tag = tag or ("GROUP" if item["kind"] == "group" else "LEDGER")
    entity_type = entity_type or ("Group" if item["kind"] == "group" else "Ledger")
    envelope = f"""<ENVELOPE>
  <HEADER><VERSION>1</VERSION><TALLYREQUEST>Import</TALLYREQUEST><TYPE>Data</TYPE><ID>All Masters</ID></HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES><SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT><SVCURRENTCOMPANY>{x(company_name)}</SVCURRENTCOMPANY></STATICVARIABLES>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        <{tag} NAME="{x(item['name'])}" Action="Delete">
          <NAME>{x(item['name'])}</NAME>
        </{tag}>
      </TALLYMESSAGE>
    </DESC>
  </BODY>
</ENVELOPE>"""
    start = time.time()
    resp = await asyncio.to_thread(_post_to_tally_sync, settings.TALLY_URL, envelope, 10)
    await record_sync_traffic_log(
        db=db, company_id=company_id, sync_id=sync_id, entity_type=entity_type,
        entity_id=item["app_id"], entity_name=item["name"], action="Delete", outbound_format="XML",
        outbound_payload=envelope, inbound_response=resp, duration_ms=int((time.time() - start) * 1000),
        tally_url=settings.TALLY_URL,
    )
    if not resp or not resp.strip():
        raise TallyUnreachable("Tally did not answer.")
    if check_tally_success(resp):
        return "DELETED", None
    reason = parse_tally_response_metrics(resp)["error_summary"] or "Tally refused the delete."
    if "does not exist" in reason.lower():
        return "ABSENT", None
    return "REJECTED", reason


async def _delete_item(db: AsyncSession, user: User, company_name: str, item: dict, tally_available: bool) -> Tuple[bool, Optional[str]]:
    """Deletes one plan item on both sides, Tally first. (deleted, why not)."""
    company_id = user.company_id
    record_type = "Group" if item["kind"] == "group" else "Ledger"

    sync_item = None
    if item["in_app"]:
        # The name is all a later retry or the Desktop Sync Agent has once the row is gone
        sync_item = await queue_sync_event(db, company_id, record_type, item["app_id"], "Delete", {"tally_name": item["name"]})
        await db.commit()

    pushed = False
    if tally_available and item["in_tally"]:
        outcome, reason = await _delete_in_tally(db, company_id, company_name, item, sync_item.sync_id if sync_item else None)
        if outcome == "REJECTED":
            if sync_item:
                await db.delete(sync_item)
                await db.commit()
            return False, f"Tally refused: {reason}"
        pushed = True

    if item["in_app"]:
        if item["kind"] == "group":
            row = (await db.execute(select(MstGroup).where(MstGroup.group_id == item["app_id"], MstGroup.company_id == company_id))).scalars().first()
        else:
            row = (await db.execute(select(MstLedger).where(MstLedger.ledger_id == item["app_id"], MstLedger.company_id == company_id))).scalars().first()
            if row:
                audit = (await db.execute(select(DeletedRecordAudit).where(
                    DeletedRecordAudit.company_id == company_id,
                    DeletedRecordAudit.entity_type == "Ledger",
                    DeletedRecordAudit.record_id == row.ledger_id,
                ))).scalars().first()
                if not audit:
                    db.add(DeletedRecordAudit(
                        company_id=company_id, entity_type="Ledger", record_id=row.ledger_id,
                        tally_guid=getattr(row, 'guid', None) or f"MYTALLY-LEDGER-{row.ledger_id}",
                        entity_identifier=row.name, deleted_by_user_id=user.user_id,
                        tally_sync_status="SYNCED_TO_TALLY" if (pushed or tally_available) else "PENDING",
                        snapshot_data={"ledger_id": row.ledger_id, "company_id": company_id, "name": row.name,
                                       "group_id": row.group_id, "opening_balance": float(row.opening_balance or 0)},
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
        # With Tally available the delete has been settled there (deleted now, or it never had the object),
        # so the queue row is done; without Tally it stays pending for the Desktop Sync Agent.
        if sync_item and tally_available:
            sync_item.is_processed = True
            sync_item.status = "SUCCESS"
            sync_item.attempts = (sync_item.attempts or 0) + 1
            sync_item.last_attempt_at = func.now()
        await db.commit()
    return True, None


async def execute_delete_plan(db: AsyncSession, user: User, group: MstGroup, cascade: bool) -> dict:
    """
    Deletes the group, and with cascade everything under it, in plan order.

    Returns {"status", "plan", "deleted", "failed"}; status is
      deleted      the group and everything asked for is gone on both sides
      blocked      nothing was deleted: there are blockers (and cascade was off, or some can never be deleted)
      partial      a delete was refused part way; what was deleted stays deleted, plan shows what is left
      unreachable  Tally stopped answering part way; what was deleted stays deleted, plan shows what is left
    Raises GroupDeleteInProgress when the same group is already being deleted.
    """
    lock_key = (group.company_id, group.group_id)
    if lock_key in _groups_being_deleted:
        raise GroupDeleteInProgress()
    _groups_being_deleted.add(lock_key)
    try:
        plan = await build_delete_plan(db, user, group)
        if plan["blocker_count"] and not cascade:
            return {"status": "blocked", "plan": plan, "deleted": [], "failed": []}
        if not plan["can_delete_all"]:
            return {"status": "blocked", "plan": plan, "deleted": [], "failed": []}

        comp = (await db.execute(select(Company).where(Company.company_id == group.company_id))).scalars().first()
        company_name = comp.name if comp else ""
        group_id = group.group_id

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
            # Show what is left as it stands now
            remaining = (await db.execute(select(MstGroup).where(MstGroup.group_id == group_id))).scalars().first()
            if remaining:
                plan = await build_delete_plan(db, user, remaining)
        logger.info(f"Group delete '{plan['group_name']}' (cascade={cascade}) by user {user.user_id}: {status_code}, "
                    f"{len(deleted)} deleted, {len(failed)} failed")
        return {"status": status_code, "plan": plan, "deleted": deleted, "failed": failed}
    finally:
        _groups_being_deleted.discard(lock_key)
