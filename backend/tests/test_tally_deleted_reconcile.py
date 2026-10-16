"""WS-3: records deleted inside Tally are soft-deleted here after two consecutive complete key lists."""
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select

import app.models.portal_core as P
import app.models.tally_core as T
from app.core.datetime_utils import get_ist_now
from app.routers import auth, sync
from tests.conftest import bearer, login

GUID = "guid-company-1"


@pytest.fixture
def world(harness):
    company = harness.company("Alpha")
    harness.execute(P.Company.__table__.update().where(P.Company.company_id == company.company_id).values(tally_guid=GUID))
    role = harness.role("Admin")
    for code in ("sync",):
        module = harness.add(P.Module(code=code, name=code))
        harness.add(P.Permission(role_id=role.role_id, module_id=module.module_id, can_read=True, can_create=True,
                                 can_update=True, can_delete=True))
    admin = harness.user(company, role, "owner")
    client = harness.app(auth.router, sync.router)
    headers = {**bearer(login(client, admin.email)), "X-Tally-Company-GUID": GUID}
    old = get_ist_now() - timedelta(days=3)

    def voucher(number, master_id, guid=None, provisional=False, age=None):
        v = harness.add(T.TrnVoucher(company_id=company.company_id, voucher_type_id=1, voucher_number=str(number),
                                     voucher_date=old.date(), created_by=admin.user_id, tally_master_id=master_id,
                                     tally_guid=guid, number_is_provisional=provisional))
        stamp = old if age is None else get_ist_now() - age
        harness.execute(T.TrnVoucher.__table__.update().where(T.TrnVoucher.voucher_id == v.voucher_id)
                        .values(created_at=stamp, updated_at=stamp))
        return v.voucher_id

    class W:
        pass
    w = W()
    w.harness, w.client, w.headers, w.company_id, w.voucher = harness, client, headers, company.company_id, voucher

    def send(vouchers, complete=True, list_id=None, expected="auto", **extra):
        body = {"list_id": list_id or uuid.uuid4().hex, "complete": complete,
                "voucher_count_expected": len(vouchers) if expected == "auto" else expected,
                "vouchers": [{"master_id": m, "guid": g} for m, g in vouchers], **extra}
        res = client.post("/sync/active-keys", json=body, headers=headers)
        assert res.status_code == 200, res.text
        return res.json()
    w.send = send
    w.cancelled = lambda vid: harness.scalar(select(T.TrnVoucher.is_cancelled).where(T.TrnVoucher.voucher_id == vid))
    w.deleted_count = lambda: client.get("/sync/health", headers=headers).json()["deleted_in_tally_count"]
    return w


def test_a_voucher_missing_from_two_complete_lists_is_soft_deleted(world):
    keep, gone = world.voucher(1, 101, "g101"), world.voucher(2, 102, "g102")

    first = world.send([(101, "g101")])
    assert first["results"][0]["deleted"] == 0 and first["results"][0]["missing"] == 1
    assert world.cancelled(gone) is False                       # one list is not enough
    second = world.send([(101, "g101")])
    assert second["results"][0]["deleted"] == 1
    assert world.cancelled(gone) is True and world.cancelled(keep) is False
    assert world.harness.scalar(select(T.TrnVoucher.status).where(T.TrnVoucher.voucher_id == gone)) == "cancelled"
    assert world.deleted_count() == 1
    audit = world.harness.query(select(P.TallyMissingRecord))[0][0]
    assert (audit.status, audit.record_id, audit.tally_master_id) == ("deleted", gone, 102)
    # nothing was hard-deleted
    assert world.harness.scalar(select(T.TrnVoucher.voucher_id).where(T.TrnVoucher.voucher_id == gone)) == gone


def test_a_partial_or_failed_export_removes_nothing(world):
    gone = world.voucher(2, 102, "g102")
    world.voucher(1, 101, "g101")
    for _ in range(3):
        assert world.send([(101, "g101")], complete=False)["status"] == "ignored"
    # the agent's own index count disagrees with the list: ignored
    for _ in range(3):
        assert world.send([(101, "g101")], expected=5)["results"][0]["skipped"] == "count_mismatch"
    # an empty list is never "everything was deleted"
    for _ in range(3):
        assert world.send([])["results"][0]["skipped"] == "empty_list"
    assert world.cancelled(gone) is False and world.deleted_count() == 0


def test_the_same_list_sent_twice_counts_once(world):
    gone = world.voucher(2, 102, "g102")
    world.voucher(1, 101, "g101")
    world.send([(101, "g101")], list_id="list-0001-aaaa")
    again = world.send([(101, "g101")], list_id="list-0001-aaaa")
    assert again["results"][0]["skipped"] == "duplicate_list"
    assert world.cancelled(gone) is False
    world.send([(101, "g101")], list_id="list-0002-bbbb")
    assert world.cancelled(gone) is True
    # and a further repeat changes nothing
    world.send([(101, "g101")], list_id="list-0002-bbbb")
    world.send([(101, "g101")])
    assert world.deleted_count() == 1


def test_app_vouchers_not_yet_confirmed_in_tally_are_kept(world):
    world.voucher(1, 101, "g101")
    no_identity = world.voucher(5, None, None)
    provisional = world.voucher(6, 106, "g106", provisional=True)
    queued = world.voucher(7, 107, "g107")
    world.harness.add(P.SyncQueue(company_id=world.company_id, record_type="Voucher", record_id=queued,
                                  action="Alter", is_processed=False))
    just_now = world.voucher(8, 108, "g108", age=timedelta(minutes=5))
    for _ in range(3):
        world.send([(101, "g101")])
    for vid in (no_identity, provisional, queued, just_now):
        assert world.cancelled(vid) is False
    assert world.deleted_count() == 0


def test_a_voucher_that_comes_back_is_put_back(world):
    gone = world.voucher(2, 102, "g102")
    world.voucher(1, 101, "g101")
    world.send([(101, "g101")])
    world.send([(101, "g101")])
    assert world.cancelled(gone) is True
    world.send([(101, "g101"), (102, "g102")])
    assert world.cancelled(gone) is False and world.deleted_count() == 0


def test_matching_by_guid_alone_keeps_a_voucher(world):
    v = world.voucher(3, None, "g103")
    world.voucher(1, 101, "g101")
    for _ in range(3):
        world.send([(101, "g101"), (None, "g103")])
    assert world.cancelled(v) is False


def test_a_list_that_would_remove_a_large_share_is_held_back(world):
    ids = [world.voucher(n, 1000 + n, f"g{n}") for n in range(1, 41)]
    keep = [(1001, "g1")]
    for _ in range(3):
        out = world.send(keep)
    assert out["results"][0]["held_back"] == 39
    assert not any(world.cancelled(v) for v in ids)


def test_masters_are_deactivated_not_deleted(world):
    world.harness.add(T.MstLedger(company_id=world.company_id, name="Old Party", group_id=1,
                                           tally_master_id=900, tally_guid="lg900"))
    world.harness.add(T.MstLedger(company_id=world.company_id, name="Live Party", group_id=1,
                                  tally_master_id=901, tally_guid="lg901"))
    world.voucher(1, 101, "g101")
    for _ in range(2):
        world.send([(101, "g101")], ledgers=[{"name": "Live Party", "guid": "lg901", "master_id": 901}])
    active = dict(world.harness.query(select(T.MstLedger.name, T.MstLedger.is_active)))
    assert active == {"Old Party": False, "Live Party": True}


def test_a_company_that_is_not_linked_is_refused(world):
    gone = world.voucher(2, 102, "g102")
    res = world.client.post("/sync/active-keys", headers={**world.headers, "X-Tally-Company-GUID": "guid-copy"},
                            json={"list_id": uuid.uuid4().hex, "complete": True, "vouchers": [{"master_id": 1, "guid": "x"}]})
    assert res.status_code == 409 and res.headers["X-Sync-Reason"] == "company_not_linked"
    assert world.cancelled(gone) is False
