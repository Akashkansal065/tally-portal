"""Reports → trial balance: follows the chosen period (opening at the start, period debits and credits, closing)."""
from datetime import date
from decimal import Decimal

import app.models.tally_core as T
from app.routers import auth, reports
from tests.conftest import bearer, login


def test_trial_balance_follows_the_period(harness):
    h = harness
    alpha = h.company("Alpha")
    owner = h.user(alpha, h.role("Admin"), "owner")
    cid = alpha.company_id
    cash_g = h.add(T.MstGroup(company_id=cid, name="Cash-in-Hand", nature="Asset"))
    capital_g = h.add(T.MstGroup(company_id=cid, name="Capital Account", nature="Liability"))
    sales_g = h.add(T.MstGroup(company_id=cid, name="Sales Accounts", nature="Income"))
    cash = h.add(T.MstLedger(company_id=cid, name="Cash", group_id=cash_g.group_id, opening_balance=Decimal("1000"), opening_balance_type="Dr"))
    capital = h.add(T.MstLedger(company_id=cid, name="Capital", group_id=capital_g.group_id, opening_balance=Decimal("1000"), opening_balance_type="Cr"))
    sales = h.add(T.MstLedger(company_id=cid, name="Sales", group_id=sales_g.group_id))
    vt = h.add(T.MstVoucherType(company_id=cid, name="Sales", parent_type="Sales"))
    n = [0]

    def sale(day, amount, cancelled=False):
        n[0] += 1
        v = h.add(T.TrnVoucher(company_id=cid, voucher_type_id=vt.voucher_type_id, voucher_number=str(n[0]), voucher_date=day,
                               total_amount=Decimal(amount), is_cancelled=cancelled, is_optional=False, created_by=owner.user_id))
        h.add(T.TrnAccounting(voucher_id=v.voucher_id, ledger_id=cash.ledger_id, debit_amount=Decimal(amount), credit_amount=Decimal(0)),
              T.TrnAccounting(voucher_id=v.voucher_id, ledger_id=sales.ledger_id, debit_amount=Decimal(0), credit_amount=Decimal(amount)))

    sale(date(2026, 4, 10), 200)                   # before the period: rolls into the opening
    sale(date(2026, 6, 1), 300)                    # in the period
    sale(date(2026, 6, 2), 999, cancelled=True)    # never counts
    sale(date(2026, 9, 1), 50)                     # after the period

    client = h.app(auth.router, reports.router)
    headers = bearer(login(client, "owner@example.com"))

    rows = client.get("/reports/trial-balance?from_date=2026-05-01&to_date=2026-06-30", headers=headers).json()
    by_name = {r["name"]: r for r in rows}
    assert by_name["Cash-in-Hand"] == {"name": "Cash-in-Hand", "opening": 1200.0, "debit": 300.0, "credit": 0.0, "balance": 1500.0}
    assert by_name["Sales Accounts"] == {"name": "Sales Accounts", "opening": -200.0, "debit": 0.0, "credit": 300.0, "balance": -500.0}
    # A Cr opening balance counts as credit, so the trial balance still nets to zero
    assert by_name["Capital Account"]["balance"] == -1000.0
    assert sum(r["balance"] for r in rows) == 0

    # No dates: all time, up to the latest voucher
    all_time = {r["name"]: r for r in client.get("/reports/trial-balance", headers=headers).json()}
    assert all_time["Cash-in-Hand"] == {"name": "Cash-in-Hand", "opening": 1000.0, "debit": 550.0, "credit": 0.0, "balance": 1550.0}

    # A different period isn't served from the first one's cache
    later = {r["name"]: r for r in client.get("/reports/trial-balance?from_date=2026-07-01", headers=headers).json()}
    assert later["Cash-in-Hand"]["opening"] == 1500.0 and later["Cash-in-Hand"]["debit"] == 50.0

    assert client.get("/reports/trial-balance?from_date=yesterday", headers=headers).status_code == 422
