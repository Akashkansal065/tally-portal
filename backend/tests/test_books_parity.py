"""WS-5: the books-parity check compares Tally's own figures with what MyTally computes, and only reads."""
import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import select

import app.models.portal_core as P
import app.models.tally_core as T
from app.core.datetime_utils import get_ist_now
from app.routers import auth, reports, sync
from app.services.books_parity import financial_year
from tests.conftest import bearer, login

GUID = "guid-parity"


@pytest.fixture
def world(harness):
    company = harness.company("Alpha")
    harness.execute(P.Company.__table__.update().where(P.Company.company_id == company.company_id).values(tally_guid=GUID))
    role = harness.role("Admin")
    for code in ("sync", "reports"):
        module = harness.add(P.Module(code=code, name=code))
        harness.add(P.Permission(role_id=role.role_id, module_id=module.module_id, can_read=True, can_create=True,
                                 can_update=True, can_delete=True))
    admin = harness.user(company, role, "owner")
    client = harness.app(auth.router, sync.router, reports.router)
    headers = {**bearer(login(client, admin.email)), "X-Tally-Company-GUID": GUID}
    cid = company.company_id
    grp = harness.add(T.MstGroup(company_id=cid, name="Sundry Debtors", nature="Asset"))
    party = harness.add(T.MstLedger(company_id=cid, name="Party", group_id=grp.group_id, opening_balance=100,
                                    opening_balance_type="Dr", tally_guid="lg-party", tally_master_id=11))
    sales = harness.add(T.MstLedger(company_id=cid, name="Sales", group_id=grp.group_id, opening_balance=0,
                                    tally_guid="lg-sales", tally_master_id=12))
    sale_t = harness.add(T.MstVoucherType(company_id=cid, name="Sales", parent_type="Sales", numbering_method="Automatic", next_number=1))
    order_t = harness.add(T.MstVoucherType(company_id=cid, name="Sales Order", parent_type="Sales Order", numbering_method="Automatic", next_number=1))

    class W:
        pass
    w = W()
    w.harness, w.client, w.headers, w.cid = harness, client, headers, cid
    w.party, w.sales, w.sale_t, w.order_t, w.admin = party, sales, sale_t, order_t, admin

    def voucher(vtype, amount, number, day=date(2026, 5, 1), master=None, **flags):
        v = harness.add(T.TrnVoucher(company_id=cid, voucher_type_id=vtype.voucher_type_id, voucher_number=str(number),
                                     voucher_date=day, created_by=admin.user_id, tally_master_id=master,
                                     tally_guid=f"v{number}", **flags))
        harness.add(T.TrnAccounting(voucher_id=v.voucher_id, ledger_id=party.ledger_id, debit_amount=amount, credit_amount=0),
                    T.TrnAccounting(voucher_id=v.voucher_id, ledger_id=sales.ledger_id, debit_amount=0, credit_amount=amount))
        return v.voucher_id
    w.voucher = voucher

    def send(vouchers, ledgers):
        res = client.post("/sync/active-keys", headers=headers, json={
            "list_id": uuid.uuid4().hex, "complete": True, "voucher_count_expected": len(vouchers),
            "vouchers": vouchers, "ledgers": ledgers})
        assert res.status_code == 200, res.text
        return res.json()
    w.send = send
    w.health = lambda: client.get("/sync/health", headers=headers).json()["books_parity"]
    return w


def tally_voucher(master, number, vtype="Sales", day="20260501"):
    return {"master_id": master, "guid": f"v{number}", "date": day, "voucher_type": vtype}


def ledgers(party_closing, sales_closing):
    # Tally writes a debit balance as negative
    return [{"name": "Party", "guid": "lg-party", "master_id": 11, "closing_balance": party_closing},
            {"name": "Sales", "guid": "lg-sales", "master_id": 12, "closing_balance": sales_closing}]


def test_financial_year():
    assert financial_year(date(2026, 3, 31)) == "2025-26" and financial_year(date(2026, 4, 1)) == "2026-27"


def test_a_fully_synced_company_shows_no_drift(world):
    world.voucher(world.sale_t, 500, 1, master=101)
    world.send([tally_voucher(101, 1)], ledgers("-600.00", "500.00"))
    parity = world.health()
    assert parity["in_sync"] is True and parity["ledgers_checked"] == 2 and parity["vouchers_here"] == 1


def test_a_missed_voucher_shows_on_the_right_ledger_and_in_the_counts(world):
    world.voucher(world.sale_t, 500, 1, master=101)
    # Tally also holds a 250 sale that never reached MyTally
    world.send([tally_voucher(101, 1), tally_voucher(102, 2)], ledgers("-850.00", "750.00"))
    parity = world.health()
    assert parity["in_sync"] is False and parity["ledgers_drifting"] == 2
    top = {l["name"]: l for l in parity["top_ledgers"]}
    assert top["Party"]["tally"] == 850.0 and top["Party"]["computed"] == 600.0 and top["Party"]["difference"] == -250.0
    assert parity["voucher_count_drift"] == [{"voucher_type": "Sales", "financial_year": "2026-27", "tally": 2, "here": 1}]


def test_orders_and_cancelled_vouchers_do_not_count_as_books(world):
    world.voucher(world.sale_t, 500, 1, master=101)
    world.voucher(world.order_t, 900, 2, master=102)                    # an order posts nothing in Tally
    world.voucher(world.sale_t, 70, 3, master=103, is_cancelled=True)
    world.send([tally_voucher(101, 1), tally_voucher(102, 2, "Sales Order"), tally_voucher(103, 3)],
               ledgers("-600.00", "500.00"))
    parity = world.health()
    assert parity["ledgers_drifting"] == 0 and parity["voucher_count_drift"] == []


def test_the_parity_check_never_changes_the_books(world):
    world.voucher(world.sale_t, 500, 1, master=101)
    before = world.harness.query(select(T.MstLedger.name, T.MstLedger.closing_balance, T.MstLedger.opening_balance))
    entries = world.harness.query(select(T.TrnAccounting.entry_id, T.TrnAccounting.debit_amount, T.TrnAccounting.credit_amount))
    world.send([tally_voucher(101, 1), tally_voucher(102, 2)], ledgers("-1.00", "9.00"))
    assert world.harness.query(select(T.MstLedger.name, T.MstLedger.closing_balance, T.MstLedger.opening_balance)) == before
    assert world.harness.query(select(T.TrnAccounting.entry_id, T.TrnAccounting.debit_amount, T.TrnAccounting.credit_amount)) == entries


def test_trial_balance_leaves_out_orders(world):
    world.voucher(world.sale_t, 500, 1, master=101)
    world.voucher(world.order_t, 900, 2, master=102)
    rows = world.client.get("/reports/trial-balance", headers=world.headers).json()
    (debtors,) = [r for r in rows if r["name"] == "Sundry Debtors"]
    # both ledgers sit under one group here: 100 opening + 500 sale debit, 500 sale credit; the order adds nothing
    assert debtors["debit"] == 500.0 and debtors["credit"] == 500.0
