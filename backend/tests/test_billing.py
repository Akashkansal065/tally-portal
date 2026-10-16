"""Billing, phase 0: nobody can give their own account a plan, and what the server reports about a
subscription is what it enforces."""
from sqlalchemy import select, update

import app.models.portal_core as P
from app.routers import auth, billing
from tests.conftest import bearer, login


def world(harness):
    account = harness.add(P.Account(name="Alpha", status="active"))
    company = harness.company("Alpha")
    owner = harness.user(company, harness.role("Admin"), "owner")
    harness.execute(update(P.Company).values(account_id=account.account_id))
    harness.execute(update(P.User).values(account_id=account.account_id))
    client = harness.app(auth.router, billing.router)
    return account, client, bearer(login(client, owner.email))


def test_no_endpoint_lets_a_user_activate_a_plan(harness, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "BILLING_CHECKOUT_ENABLED", False)
    account, client, headers = world(harness)
    body = {"order_id": "x", "payment_id": "DEMO_PAY_1", "signature": "TEST_SIG", "plan_id": "diamond", "duration_key": "1_year"}

    assert client.post("/billing/verify-payment", json=body, headers=headers).status_code == 404
    assert client.post("/billing/create-order", json=body, headers=headers).status_code == 404
    assert client.get("/billing/plans").json()["checkout_enabled"] is False
    assert harness.scalar(select(P.Account.plan).where(P.Account.account_id == account.account_id)) is None


def test_subscription_reports_the_enforced_limits_without_guessing(harness):
    _, client, headers = world(harness)
    data = client.get("/billing/current-subscription", headers=headers).json()

    assert data["plan"] is None and data["tier"] is None and data["valid_until"] is None
    assert data["usage"] == {"companies_linked": 1, "max_companies": None, "users_active": 1, "max_users": None}


def test_quote_is_exact_and_refuses_negative_quantities(harness):
    _, client, _ = world(harness)
    quote = client.post("/billing/calculate-quote", json={"plan_id": "silver", "duration_key": "2_year", "extra_users": 1}).json()

    assert quote["net_taxable"] == 4199 + 999 * 2
    assert quote["gst_amount"] == 1115.46 and quote["grand_total"] == 7312.46
    for field in ("extra_users", "extra_companies"):
        assert client.post("/billing/calculate-quote", json={"plan_id": "silver", field: -1}).status_code == 422
    assert client.post("/billing/calculate-quote", json={"plan_id": "nope"}).status_code == 400
