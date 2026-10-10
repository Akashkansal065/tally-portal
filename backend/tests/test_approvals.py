"""Phase 5: voucher approval (maker-checker). Vouchers matching a rule are held back from Tally until approved."""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

import app.models.portal_core as P
import app.models.tally_core as T
from app.routers import approvals, auth, sync, vouchers
from tests.conftest import bearer, login


@pytest.fixture
def world(harness, monkeypatch):
    pushed = []

    async def fake_push(voucher_id, sync_id, action, db):
        pushed.append((voucher_id, action))
        return (True, "OK", "")
    monkeypatch.setattr(sync, "try_push_voucher_realtime", fake_push)

    # Entering a voucher sends it before committing (a refusal by Tally undoes the entry), through these two
    async def fake_send(db, voucher_id, action, ident=None):
        pushed.append((voucher_id, action))
        return {"status": "SUCCESS", "reason": None, "envelope": None, "response": None, "name": None,
                "company_id": None, "duration_ms": 0, "renumbered_from": None}

    async def fake_record(db, voucher_id, sync_id, action, result):
        await db.commit()
    monkeypatch.setattr(sync, "send_voucher", fake_send)
    monkeypatch.setattr(sync, "record_voucher_push", fake_record)

    h = harness
    alpha = h.company("Alpha")
    admin_role, sales_role, accounts_role = h.role("Admin"), h.role("Sales"), h.role("Accountant")
    h.user(alpha, admin_role, "owner")
    h.user(alpha, sales_role, "maker")
    checker = h.user(alpha, accounts_role, "checker")
    module = h.add(P.Module(code="vouchers", name="Vouchers"))
    for role in (sales_role, accounts_role):
        h.add(P.Permission(role_id=role.role_id, module_id=module.module_id, can_read=True, can_create=True, can_update=True))
    cid = alpha.company_id
    group = h.add(T.MstGroup(company_id=cid, name="Sundry Debtors", nature="Asset"))
    party = h.add(T.MstLedger(company_id=cid, name="Gupta Electricals", group_id=group.group_id))
    sales = h.add(T.MstLedger(company_id=cid, name="Sales", group_id=group.group_id))
    jv = h.add(T.MstVoucherType(company_id=cid, name="Journal", parent_type="Journal"))
    client = h.app(auth.router, vouchers.router, approvals.router)
    heads = {n: bearer(login(client, f"{n}@example.com")) for n in ("owner", "maker", "checker")}

    def enter(who, amount=1000):
        r = client.post("/vouchers", json={
            "voucher_type_id": jv.voucher_type_id, "voucher_date": date(2026, 10, 6).isoformat(), "party_ledger_id": party.ledger_id,
            "entries": [{"ledger_id": party.ledger_id, "debit_amount": str(amount)},
                        {"ledger_id": sales.ledger_id, "credit_amount": str(amount)}]}, headers=heads[who])
        assert r.status_code in (201, 202), r.text  # 202: held for approval
        return r.json()

    return dict(h=h, client=client, heads=heads, enter=enter, pushed=pushed, jv=jv, accounts_role=accounts_role, checker=checker)


def test_rules_are_admin_only(world):
    c, heads = world["client"], world["heads"]
    body = {"min_amount": "0", "approver_role_id": world["accounts_role"].role_id}
    assert c.post("/approvals/rules", json=body, headers=heads["maker"]).status_code == 403
    rule = c.post("/approvals/rules", json=body, headers=heads["owner"]).json()
    assert rule["voucher_type"] == "All voucher types" and rule["approver_role"] == "Accountant"
    assert [r["rule_id"] for r in c.get("/approvals/rules", headers=heads["owner"]).json()] == [rule["rule_id"]]
    assert c.delete(f"/approvals/rules/{rule['rule_id']}", headers=heads["owner"]).status_code == 200
    assert c.get("/approvals/rules", headers=heads["owner"]).json() == []


def test_held_rejected_resubmitted_and_approved(world):
    c, heads, pushed, h = world["client"], world["heads"], world["pushed"], world["h"]
    c.post("/approvals/rules", json={"min_amount": "500", "approver_role_id": world["accounts_role"].role_id}, headers=heads["owner"])

    small = world["enter"]("maker", amount=100)       # under the limit: straight to Tally
    assert small["status"] == "confirmed" and pushed[-1] == (small["voucher_id"], "Create")
    admin_v = world["enter"]("owner")                  # admins are never held
    assert admin_v["status"] == "confirmed"

    held = world["enter"]("maker")
    assert held["status"] == "optional" and pushed[-1][0] != held["voucher_id"]
    titles = [r[0] for r in h.query(select(P.Notification.title).where(P.Notification.user_id == world["checker"].user_id))]
    assert any("Approve Journal" in t for t in titles)

    assert c.get("/approvals/summary", headers=heads["checker"]).json()["waiting_for_me"] == 1
    assert c.get("/approvals/requests?scope=to_me", headers=heads["maker"]).json() == []
    mine = c.get("/approvals/requests?scope=mine", headers=heads["maker"]).json()
    assert len(mine) == 1 and mine[0]["can_decide"] is False
    request_id = c.get("/approvals/requests?scope=to_me", headers=heads["checker"]).json()[0]["request_id"]

    # The maker can't approve their own voucher; a rejection needs a note
    assert c.post(f"/approvals/requests/{request_id}/approve", json={}, headers=heads["maker"]).status_code == 403
    assert c.post(f"/approvals/requests/{request_id}/reject", json={"note": " "}, headers=heads["checker"]).status_code == 422
    assert c.post(f"/approvals/requests/{request_id}/reject", json={"note": "Wrong party"}, headers=heads["checker"]).status_code == 200
    status = h.query(select(T.TrnVoucher.status).where(T.TrnVoucher.voucher_id == held["voucher_id"]))[0][0]
    assert status == "draft"
    banner = c.get(f"/approvals/vouchers/{held['voucher_id']}", headers=heads["maker"]).json()
    assert banner["status"] == "Rejected" and banner["note"] == "Wrong party" and banner["can_resubmit"]

    # Sent again: still over the limit, so a new request
    assert c.post(f"/approvals/vouchers/{held['voucher_id']}/resubmit", headers=heads["maker"]).json()["status"] == "Pending"
    request_id = c.get("/approvals/requests?scope=to_me", headers=heads["checker"]).json()[0]["request_id"]
    r = c.post(f"/approvals/requests/{request_id}/approve", json={"note": "OK"}, headers=heads["checker"])
    assert r.status_code == 200
    assert pushed[-1] == (held["voucher_id"], "Create")
    assert h.query(select(T.TrnVoucher.status).where(T.TrnVoucher.voucher_id == held["voucher_id"]))[0][0] == "confirmed"
    assert c.post(f"/approvals/requests/{request_id}/approve", json={}, headers=heads["checker"]).status_code == 409
    assert c.get("/approvals/summary", headers=heads["checker"]).json()["waiting_for_me"] == 0


def test_voucher_items_only_take_this_companys_godown_and_batch(world):
    """Voucher entry now sends godown and batch per item; another company's (or another item's) are refused."""
    h, c, heads = world["h"], world["client"], world["heads"]
    alpha_id = world["jv"].company_id
    beta = h.company("Beta")
    unit = h.add(T.MstUom(company_id=alpha_id, name="Pieces", symbol="PCS"))
    kettle = h.add(T.MstStockItem(company_id=alpha_id, name="Kettle", unit_id=unit.unit_id))
    fan = h.add(T.MstStockItem(company_id=alpha_id, name="Fan", unit_id=unit.unit_id))
    theirs = h.add(T.MstGodown(company_id=beta.company_id, name="Their Store"))
    fan_batch = h.add(T.Batch(company_id=alpha_id, stock_item_id=fan.stock_item_id, batch_number="F-1",
                              quantity_received=Decimal(5), quantity_available=Decimal(5)))

    def post(extra):
        return c.post("/vouchers", json={"voucher_type_id": world["jv"].voucher_type_id, "voucher_date": "2026-10-06",
                                         "inventory_entries": [{"stock_item_id": kettle.stock_item_id, "quantity": "1", "rate": "10",
                                                                "amount": "10", **extra}]}, headers=heads["owner"])
    assert post({"godown_id": theirs.godown_id}).json()["detail"] == "Godown not found."
    assert post({"batch_id": fan_batch.batch_id}).json()["detail"] == "That batch isn't for this item."
