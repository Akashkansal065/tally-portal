"""Phase 5: who to send a greeting to (customers with no sale in N days)."""
from datetime import date, timedelta
from decimal import Decimal

import app.models.portal_core as P
import app.models.tally_core as T
from app.routers import auth, greetings
from app.services import receivables
from tests.conftest import bearer, login

TODAY = date(2026, 10, 6)


def test_inactive_customers_first_with_whatsapp(harness, monkeypatch):
    monkeypatch.setattr(greetings, "get_ist_date", lambda: TODAY)
    h = harness
    alpha = h.company("Alpha")
    owner = h.user(alpha, h.role("Admin"), "owner")
    cid = alpha.company_id
    primary = h.add(T.MstGroup(company_id=cid, name="Primary", nature="Asset"))
    debtors = h.add(T.MstGroup(company_id=cid, name="Sundry Debtors", nature="Asset", parent_group_id=primary.group_id))
    creditors = h.add(T.MstGroup(company_id=cid, name="Sundry Creditors", nature="Liability", parent_group_id=primary.group_id))
    sales_vt = h.add(T.MstVoucherType(company_id=cid, name="Sales", parent_type="Sales"))

    def customer(name, days_ago=None, **kw):
        c = h.add(T.MstLedger(company_id=cid, name=name, group_id=debtors.group_id, **kw))
        if days_ago is not None:
            v = h.add(T.TrnVoucher(company_id=cid, voucher_type_id=sales_vt.voucher_type_id, voucher_number=name[:5],
                                   voucher_date=TODAY - timedelta(days=days_ago), total_amount=Decimal("100"),
                                   is_cancelled=False, is_optional=False, created_by=owner.user_id))
            h.add(T.TrnAccounting(voucher_id=v.voucher_id, ledger_id=c.ledger_id, debit_amount=Decimal("100"), credit_amount=0))
        return c

    customer("Recent Mart", 5)
    customer("Old Traders", 200, mobile="9837011111")
    customer("Quiet Store", 70)
    customer("Never Bought")
    h.add(T.MstLedger(company_id=cid, name="A Supplier", group_id=creditors.group_id))
    client = h.app(auth.router, greetings.router)
    headers = bearer(login(client, "owner@example.com"))

    rows = client.get("/greetings/customers?days=60", headers=headers).json()
    assert [r["name"] for r in rows] == ["Old Traders", "Quiet Store", "Never Bought"]
    assert rows[0]["whatsapp"] == "919837011111" and rows[0]["days_since"] == 200 and rows[2]["last_sale"] is None
    assert len(client.get("/greetings/customers?days=0", headers=headers).json()) == 4  # suppliers never included
    assert [r["name"] for r in client.get("/greetings/customers?days=0&search=mart", headers=headers).json()] == ["Recent Mart"]
