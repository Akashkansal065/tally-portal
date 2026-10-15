"""Tests for the Operator Billing Management Console (/platform/billing)."""

from datetime import datetime, timezone
import pytest
from sqlalchemy import select, update

import app.models.billing as B
import app.models.portal_core as P
from app.routers import auth, platform_billing
from tests.conftest import bearer, login, run, setup_test_operator


def setup_operator_world(harness, monkeypatch):
    # Regular customer tenant
    customer_acc = harness.add(P.Account(name="Acme Corp", status="active"))
    customer_co = harness.company("Acme Corp")
    customer_owner = harness.user(customer_co, harness.role("Admin"), "customer")

    harness.execute(update(P.Company).where(P.Company.company_id == customer_co.company_id).values(account_id=customer_acc.account_id))
    harness.execute(update(P.User).where(P.User.user_id == customer_owner.user_id).values(account_id=customer_acc.account_id))

    client = harness.app(auth.router, platform_billing.router)
    customer_headers = bearer(login(client, customer_owner.email))

    async def make_operator():
        async with harness.Session() as db:
            return await setup_test_operator(db, "super_admin")
    _, operator_token = run(make_operator())
    operator_headers = bearer(operator_token)

    return {
        "client": client,
        "customer_account": customer_acc,
        "customer_user": customer_owner,
        "customer_headers": customer_headers,
        "operator_headers": operator_headers,
    }


def test_operator_routes_require_platform_admin(harness, monkeypatch):
    env = setup_operator_world(harness, monkeypatch)
    client = env["client"]
    cust_h = env["customer_headers"]
    acc_id = env["customer_account"].account_id

    # A customer token is refused by the operator console (it is not an operator session)
    assert client.get("/platform/billing/metrics", headers=cust_h).status_code == 401
    assert client.get("/platform/billing/accounts", headers=cust_h).status_code == 401
    assert client.post(f"/platform/billing/accounts/{acc_id}/assign-plan", json={"plan_code": "gold"}, headers=cust_h).status_code == 401
    assert client.post(f"/platform/billing/accounts/{acc_id}/lock", headers=cust_h).status_code == 401
    assert client.post("/platform/billing/offline-payment", json={"account_id": acc_id, "plan_code": "gold", "reference": "R1"}, headers=cust_h).status_code == 401


def test_customer_token_of_platform_admin_email_is_not_an_operator_session(harness, monkeypatch):
    """PLATFORM_ADMIN_EMAILS never turns a customer-portal token into an operator session: that token was issued
    without a passkey or step-up, so the console refuses it."""
    from app.core.config import settings
    env = setup_operator_world(harness, monkeypatch)
    monkeypatch.setattr(settings, "PLATFORM_ADMIN_EMAILS", env["customer_user"].email)
    client, cust_h = env["client"], env["customer_headers"]

    assert client.get("/platform/billing/metrics", headers=cust_h).status_code == 401
    assert client.get("/platform/billing/metrics", headers=env["operator_headers"]).status_code == 200


def test_operator_metrics_and_accounts(harness, monkeypatch):
    env = setup_operator_world(harness, monkeypatch)
    client = env["client"]
    op_h = env["operator_headers"]
    acc_id = env["customer_account"].account_id

    # 1. Metrics endpoint
    res = client.get("/platform/billing/metrics", headers=op_h)
    assert res.status_code == 200
    metrics = res.json()
    assert metrics["success"] is True
    assert "subscriptions" in metrics
    assert "revenue" in metrics
    assert "alerts" in metrics

    # 2. Accounts endpoint
    res = client.get("/platform/billing/accounts", headers=op_h)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    acc_records = [a for a in data["accounts"] if a["account_id"] == acc_id]
    assert len(acc_records) == 1
    assert acc_records[0]["account_name"] == "Acme Corp"


def test_operator_assign_plan_and_custom_plan(harness, monkeypatch):
    env = setup_operator_world(harness, monkeypatch)
    client = env["client"]
    op_h = env["operator_headers"]
    acc_id = env["customer_account"].account_id

    # 1. Assign standard Gold plan for 2 years
    assign_res = client.post(
        f"/platform/billing/accounts/{acc_id}/assign-plan",
        json={"plan_code": "gold", "duration_years": 2, "extra_users": 3, "extra_companies": 1},
        headers=op_h,
    )
    assert assign_res.status_code == 200
    assert assign_res.json()["success"] is True

    sub = harness.scalar(
        select(B.AccountSubscription).where(B.AccountSubscription.account_id == acc_id)
    )
    assert sub is not None
    assert sub.status == "active"
    assert sub.extra_users == 3
    assert sub.extra_companies == 1

    # 2. Create a custom bespoke plan
    custom_res = client.post(
        f"/platform/billing/accounts/{acc_id}/custom-plan",
        json={
            "name": "Acme VIP Enterprise",
            "tagline": "Special plan for Acme",
            "max_users": 50,
            "max_companies": 10,
            "max_devices": 20,
            "feature_keys": ["einvoice_eway_bill", "bank_reconciliation"],
            "yearly_price_paise": 2500000,
        },
        headers=op_h,
    )
    assert custom_res.status_code == 200
    cdata = custom_res.json()
    assert cdata["success"] is True
    assert "custom_" in cdata["plan_code"]
    assert cdata["amount_rupees"] == 25000.0


def test_operator_lock_and_unlock(harness, monkeypatch):
    env = setup_operator_world(harness, monkeypatch)
    client = env["client"]
    op_h = env["operator_headers"]
    acc_id = env["customer_account"].account_id

    # Assign gold plan first
    client.post(
        f"/platform/billing/accounts/{acc_id}/assign-plan",
        json={"plan_code": "gold", "duration_years": 1},
        headers=op_h,
    )

    # Operator locks account
    lock_res = client.post(f"/platform/billing/accounts/{acc_id}/lock", headers=op_h)
    assert lock_res.status_code == 200
    assert lock_res.json()["success"] is True

    sub = harness.scalar(
        select(B.AccountSubscription).where(B.AccountSubscription.account_id == acc_id)
    )
    assert sub.status == "locked"

    # Operator unlocks account
    unlock_res = client.post(f"/platform/billing/accounts/{acc_id}/unlock", headers=op_h)
    assert unlock_res.status_code == 200
    assert unlock_res.json()["success"] is True

    sub = harness.scalar(
        select(B.AccountSubscription).where(B.AccountSubscription.account_id == acc_id)
    )
    assert sub.status == "active"


def test_operator_record_offline_payment_generates_invoice(harness, monkeypatch):
    env = setup_operator_world(harness, monkeypatch)
    client = env["client"]
    op_h = env["operator_headers"]
    acc_id = env["customer_account"].account_id

    pay_res = client.post(
        "/platform/billing/offline-payment",
        json={
            "account_id": acc_id,
            "plan_code": "silver",
            "duration_years": 1,
            "extra_users": 1,
            "extra_companies": 0,
            "reference": "CHQ-882910",
            "method": "cheque",
            "buyer_state_code": "07",
        },
        headers=op_h,
    )
    assert pay_res.status_code == 200
    data = pay_res.json()
    assert data["success"] is True
    assert data["status"] == "paid"
    assert data["invoice_number"].startswith("MT/")

    # Verify invoice persisted
    inv = harness.scalar(
        select(B.BillingInvoice).where(B.BillingInvoice.invoice_number == data["invoice_number"])
    )
    assert inv is not None
    assert inv.kind == "invoice"
    assert inv.place_of_supply == "07"

    # Verify subscription is now active
    sub = harness.scalar(
        select(B.AccountSubscription).where(B.AccountSubscription.account_id == acc_id)
    )
    assert sub is not None
    assert sub.status == "active"
    assert sub.current_period_end is not None


def test_account_scoped_operator_is_refused_until_scopes_are_enforced(harness, monkeypatch):
    """Routes do not filter by account scope yet, so an operator whose roles are scoped is refused rather than
    let into every account."""
    from app.models.platform import PlatformAdminRole
    env = setup_operator_world(harness, monkeypatch)
    client, op_h = env["client"], env["operator_headers"]
    assert client.get("/platform/billing/metrics", headers=op_h).status_code == 200

    harness.execute(update(PlatformAdminRole).values(scope_account_ids=f"[{env['customer_account'].account_id}]"))
    refused = client.get("/platform/billing/metrics", headers=op_h)
    assert refused.status_code == 403 and "scoped" in refused.json()["detail"]
