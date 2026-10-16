"""WS-14 server side: queue a reconciliation write-back, one at a time, behind the company switch."""
from datetime import date

import pytest
from sqlalchemy import select

import app.models.portal_core as P
import app.models.tally_core as T
from app.routers import auth, bank_recon, sync
from tests.conftest import bearer, login

GUID = "guid-wb"


@pytest.fixture
def world(harness):
    c = harness.company("Alpha")
    other = harness.company("Beta")
    harness.execute(P.Company.__table__.update().where(P.Company.company_id == c.company_id).values(tally_guid=GUID))
    role = harness.role("Admin")
    for code in ("vouchers", "sync"):
        module = harness.add(P.Module(code=code, name=code))
        harness.add(P.Permission(role_id=role.role_id, module_id=module.module_id, can_read=True, can_create=True,
                                 can_update=True, can_delete=True))
    admin = harness.user(c, role, "owner")
    cid = c.company_id
    group = harness.add(T.MstGroup(company_id=cid, name="Bank Accounts", nature="Asset"))
    bank = harness.add(T.MstLedger(company_id=cid, name="Bank", group_id=group.group_id))
    vtype = harness.add(T.MstVoucherType(company_id=cid, name="Receipt", parent_type="Receipt", numbering_method="Automatic", next_number=1))
    v = harness.add(T.TrnVoucher(company_id=cid, voucher_type_id=vtype.voucher_type_id, voucher_number="7",
                                 voucher_date=date(2026, 3, 1), created_by=admin.user_id, tally_master_id=301, tally_alter_id=9,
                                 tally_guid="g-301"))
    e = harness.add(T.TrnAccounting(voucher_id=v.voucher_id, ledger_id=bank.ledger_id, debit_amount=1000, credit_amount=0))
    a = harness.add(T.TrnBankAllocation(entry_id=e.entry_id, transaction_type="Cheque", instrument_number="000123", amount=1000))
    client = harness.app(auth.router, bank_recon.router, sync.router)
    h = {**bearer(login(client, admin.email)), "X-Tally-Company-GUID": GUID}

    class W:
        pass
    w = W()
    w.harness, w.client, w.h, w.company, w.other, w.v, w.a, w.admin = harness, client, h, c, other, v, a, admin
    w.on = lambda: harness.add(P.CompanyIntegration(company_id=cid, key="reconcile_writeback", enabled=True))
    w.ask = lambda **kw: client.post("/bank-recon/writeback", headers=h, json={
        "voucher_id": v.voucher_id, "allocation_id": a.allocation_id, "bankers_date": "2026-03-05", "manual_status": "Yes", **kw})
    w.rows = lambda: [r[0] for r in harness.query(select(P.SyncQueue).where(P.SyncQueue.record_type == "VoucherReconcile"))]
    w.alloc = lambda: harness.query(select(T.TrnBankAllocation))[0][0]
    return w


def test_off_by_default(world):
    assert world.ask().status_code == 403 and world.rows() == []


def test_a_request_is_queued_once_and_a_newer_one_replaces_it(world):
    world.on()
    first = world.ask()
    assert first.status_code == 202 and first.json()["status"] == "queued"
    second = world.ask(bankers_date="2026-03-09")
    assert second.json()["replaced"] is True and len(world.rows()) == 1
    request = world.rows()[0].snapshot_data
    assert (request["master_id"], request["date"], request["alter_id"], request["bankers_date"], request["manual_status"]) == \
           (301, "20260301", 9, "20260309", "Yes")
    assert world.alloc().bankers_date is None                 # nothing is recorded until Tally has done it


def test_the_agent_receives_a_directive_not_a_tally_payload(world):
    world.on()
    world.ask()
    queue = world.client.get("/sync/outbound-queue", headers=world.h).json()
    (item,) = queue
    assert item["record_type"] == "VoucherReconcile"
    assert "<MYTALLYRECONCILE" in item["xml_payload"] and "<MASTERID>301</MASTERID>" in item["xml_payload"]
    assert "<BANKERSDATE>20260305</BANKERSDATE>" in item["xml_payload"] and "<SVCURRENTCOMPANY>Alpha</SVCURRENTCOMPANY>" in item["xml_payload"]


def test_a_reported_success_records_the_values_and_the_new_alter_id(world):
    world.on()
    sync_id = world.ask().json()["sync_id"]
    res = world.client.post("/sync/reconcile-result", headers=world.h, json={"sync_id": sync_id, "outcome": "done", "alter_id": "10"})
    assert res.status_code == 200
    a = world.alloc()
    assert (a.bankers_date, a.bank_manual_status) == (date(2026, 3, 5), "Yes")
    assert world.harness.query(select(T.TrnVoucher.tally_alter_id))[0][0] == 10
    assert world.rows()[0].is_processed is True and world.rows()[0].status == "SUCCESS"
    # reporting again changes nothing, and asking for the same values is now a no-op
    assert world.client.post("/sync/reconcile-result", headers=world.h, json={"sync_id": sync_id, "outcome": "done", "alter_id": "10"}).json()["status"] == "already_recorded"
    assert world.ask().json()["status"] == "unchanged"


def test_a_stale_report_leaves_the_books_alone(world):
    world.on()
    sync_id = world.ask().json()["sync_id"]
    world.client.post("/sync/reconcile-result", headers=world.h, json={"sync_id": sync_id, "outcome": "stale", "alter_id": "12",
                                                                        "message": "The voucher changed in Tally"})
    assert world.alloc().bankers_date is None
    row = world.rows()[0]
    assert row.status == "FAILED" and "changed in Tally" in row.error_message


def test_only_vouchers_tally_knows_and_allocations_of_that_voucher(world):
    world.on()
    world.harness.execute(T.TrnVoucher.__table__.update().values(tally_master_id=None))
    assert world.ask().status_code == 409
    world.harness.execute(T.TrnVoucher.__table__.update().values(tally_master_id=301))
    assert world.ask(allocation_id=99999).status_code == 404
    assert world.ask(manual_status="Maybe").status_code == 400


def test_another_companys_queue_is_not_reachable(world):
    world.on()
    sync_id = world.ask().json()["sync_id"]
    harness = world.harness
    role = harness.query(select(P.Role))[0][0]
    beta_user = harness.user(world.other, role, "betaowner")
    harness.execute(P.Company.__table__.update().where(P.Company.company_id == world.other.company_id).values(tally_guid="guid-beta"))
    h = {**bearer(login(world.client, beta_user.email)), "X-Tally-Company-GUID": "guid-beta"}
    res = world.client.post("/sync/reconcile-result", headers=h, json={"sync_id": sync_id, "outcome": "done", "alter_id": "10"})
    assert res.status_code == 404 and world.alloc().bankers_date is None
