"""P0.3 / P0.4 server side: a master delete or rename that Tally finds by NAME goes to the agent with the GUID it
must find under that name, and a ledger whose group is missing is never filed under a guessed one."""
import pytest
from sqlalchemy import select

import app.models.portal_core as P
import app.models.tally_core as T
from app.routers import auth, sync
from app.services.group_deletion import queue_sync_event
from tests.conftest import bearer, login, run

GUID = "guid-alpha"


@pytest.fixture
def world(harness):
    c = harness.company("Alpha")
    harness.execute(P.Company.__table__.update().where(P.Company.company_id == c.company_id).values(tally_guid=GUID))
    role = harness.role("Admin")
    module = harness.add(P.Module(code="sync", name="sync"))
    harness.add(P.Permission(role_id=role.role_id, module_id=module.module_id, can_read=True, can_create=True,
                             can_update=True, can_delete=True))
    admin = harness.user(c, role, "owner")
    client = harness.app(auth.router, sync.router)
    h = {**bearer(login(client, admin.email)), "X-Tally-Company-GUID": GUID}
    cid = c.company_id
    group = harness.add(T.MstGroup(company_id=cid, name="Sundry Debtors", nature="Asset", tally_guid="g-group"))

    class W:
        pass
    w = W()
    w.harness, w.client, w.h, w.cid, w.group = harness, client, h, cid, group
    w.ledger = lambda name="ABC Traders", guid="g-led", group_id=None: harness.add(
        T.MstLedger(company_id=cid, name=name, group_id=group_id or group.group_id, tally_guid=guid))
    w.queue = lambda record_type, record_id, action, snapshot=None: harness.add(
        P.SyncQueue(company_id=cid, record_type=record_type, record_id=record_id, action=action, snapshot_data=snapshot))
    w.fetch = lambda: w.client.get("/sync/outbound-queue", headers=h).json()
    w.row = lambda sync_id: harness.query(select(P.SyncQueue).where(P.SyncQueue.sync_id == sync_id))[0][0]
    return w


def test_a_ledger_delete_carries_the_name_and_guid_to_check(world):
    row = world.queue("Ledger", 4040, "Delete", {"tally_name": "ABC Traders", "tally_guid": "g-old"})   # the ledger row is gone
    (task,) = world.fetch()
    assert task["address"] == {"mode": "name_verified", "object_type": "Ledger", "name": "ABC Traders", "expect_guid": "g-old"}
    assert 'NAME="ABC Traders"' in task["xml_payload"] and row.sync_id == task["sync_id"]


def test_queueing_a_delete_records_the_guid_while_the_row_still_exists(world):
    ledger = world.ledger()

    async def go():
        async with world.harness.Session() as db:
            item = await queue_sync_event(db, world.cid, "Ledger", ledger.ledger_id, "Delete", {"tally_name": "ABC Traders"})
            await db.commit()
            return item.sync_id
    sync_id = run(go())
    assert world.row(sync_id).snapshot_data == {"tally_name": "ABC Traders", "tally_guid": "g-led"}
    # the ledger is deleted later; the queue still knows which object it meant
    world.harness.execute(T.MstLedger.__table__.delete().where(T.MstLedger.ledger_id == ledger.ledger_id))
    (task,) = world.fetch()
    assert task["address"]["expect_guid"] == "g-led"


def test_a_ledger_never_seen_in_tally_has_no_guid_to_expect(world):
    ledger = world.ledger(guid=None)
    world.queue("Ledger", ledger.ledger_id, "Delete", {"tally_name": "ABC Traders"})
    (task,) = world.fetch()
    assert task["address"]["expect_guid"] is None        # the agent will not send it


def test_a_rename_addresses_the_old_name_and_expects_the_ledgers_guid(world):
    ledger = world.ledger(name="ABC Traders Pvt")
    world.queue("Ledger", ledger.ledger_id, "Alter", {"tally_name": "ABC Traders"})
    (task,) = world.fetch()
    assert task["address"] == {"mode": "name_verified", "object_type": "Ledger", "name": "ABC Traders", "expect_guid": "g-led"}
    assert 'NAME="ABC Traders"' in task["xml_payload"] and "<NAME>ABC Traders Pvt</NAME>" in task["xml_payload"]


def test_a_create_and_an_alter_that_renames_nothing_need_no_check(world):
    a, b = world.ledger("A", "g-a"), world.ledger("B", "g-b")
    world.queue("Ledger", a.ledger_id, "Create")
    world.queue("Ledger", b.ledger_id, "Alter", {"tally_name": "B"})
    assert all("address" not in t for t in world.fetch())


def test_group_and_stock_item_deletes_are_checked_too(world):
    unit = world.harness.add(T.MstUom(company_id=world.cid, name="Nos", symbol="Nos"))
    item = world.harness.add(T.MstStockItem(company_id=world.cid, name="Widget", unit_id=unit.unit_id, tally_guid="g-w"))
    world.queue("StockItem", item.stock_item_id, "Delete", {"tally_name": "Widget Old"})
    world.queue("Group", 777, "Delete", {"tally_name": "Old Group", "tally_guid": "g-g"})
    tasks = {t["record_type"]: t for t in world.fetch()}
    assert tasks["StockItem"]["address"] == {"mode": "name_verified", "object_type": "StockItem", "name": "Widget Old", "expect_guid": "g-w"}
    assert 'NAME="Widget Old"' in tasks["StockItem"]["xml_payload"]
    assert tasks["Group"]["address"] == {"mode": "name_verified", "object_type": "Group", "name": "Old Group", "expect_guid": "g-g"}


def test_a_stock_item_rename_addresses_the_old_name(world):
    unit = world.harness.add(T.MstUom(company_id=world.cid, name="Nos", symbol="Nos"))
    item = world.harness.add(T.MstStockItem(company_id=world.cid, name="Widget Pro", unit_id=unit.unit_id, tally_guid="g-w"))
    world.queue("StockItem", item.stock_item_id, "Alter", {"tally_name": "Widget"})
    (task,) = world.fetch()
    assert 'NAME="Widget"' in task["xml_payload"] and "<NAME>Widget Pro</NAME>" in task["xml_payload"]
    assert task["address"]["name"] == "Widget" and task["address"]["expect_guid"] == "g-w"


# ── P0.4 ──

@pytest.mark.parametrize("action", ["Create", "Alter"])
def test_a_ledger_with_a_dangling_group_is_never_sent(world, action):
    ledger = world.ledger(group_id=9999)
    row = world.queue("Ledger", ledger.ledger_id, action)
    assert world.fetch() == []
    held = world.row(row.sync_id)
    assert (held.failure_kind, held.status, held.error_message) == ("needs_review", "NEEDS_REVIEW", "Group not found for ledger")
    assert not held.is_processed            # kept, not retired as "entity gone"
    assert world.fetch() == []               # and not offered again
    kinds = [e[0].kind for e in world.harness.query(select(P.SyncEvent))]
    assert kinds == ["needs_review"]


def test_the_fix_that_follows_replaces_the_held_item(world):
    ledger = world.ledger(group_id=9999)
    world.queue("Ledger", ledger.ledger_id, "Create")
    world.fetch()
    world.harness.execute(T.MstLedger.__table__.update().where(T.MstLedger.ledger_id == ledger.ledger_id).values(group_id=world.group.group_id))

    async def go():
        async with world.harness.Session() as db:
            await queue_sync_event(db, world.cid, "Ledger", ledger.ledger_id, "Alter")
            await db.commit()
    run(go())
    (task,) = world.fetch()
    assert "<PARENT>Sundry Debtors</PARENT>" in task["xml_payload"]


def test_no_envelope_files_a_ledger_under_a_guessed_group(world):
    good = world.ledger("Good", "g-1")
    bad = world.ledger("Bad", "g-2", group_id=9999)
    world.queue("Ledger", good.ledger_id, "Create")
    world.queue("Ledger", bad.ledger_id, "Create")
    tasks = world.fetch()
    assert [t["record_id"] for t in tasks] == [good.ledger_id]
    assert all('<NAME>Bad</NAME>' not in t["xml_payload"] for t in tasks)


# ── reports from the agent ──

def test_the_agent_can_set_an_item_aside_and_it_is_not_offered_again(world):
    row = world.queue("Ledger", 4040, "Delete", {"tally_name": "ABC Traders", "tally_guid": "g-old"})
    assert len(world.fetch()) == 1
    reply = world.client.post("/sync/needs-review", headers=world.h,
                              json={"sync_id": row.sync_id, "message": "different ledger in Tally", "guid_seen": "g-new"})
    assert reply.status_code == 200 and reply.json() == {"held": True}
    held = world.row(row.sync_id)
    assert (held.failure_kind, held.verified_guid, held.is_processed) == ("needs_review", "g-new", False)
    assert world.fetch() == []


def test_an_alterid_regression_event_is_recorded_and_other_kinds_are_not_accepted(world):
    ok = world.client.post("/sync/events", headers=world.h, json={"kind": "alterid_regression", "detail": {"alt_vch_id": 100}})
    assert ok.status_code == 200
    assert world.client.post("/sync/events", headers=world.h, json={"kind": "whatever"}).status_code == 422
    (event,) = [e[0] for e in world.harness.query(select(P.SyncEvent))]
    assert (event.kind, event.detail, event.company_id) == ("alterid_regression", {"alt_vch_id": 100}, world.cid)
