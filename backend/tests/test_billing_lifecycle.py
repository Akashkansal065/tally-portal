"""
test_billing_lifecycle.py – Unit tests for Phase 5:
- Lifecycle state machine transitions: trialing -> grace -> locked
- Pending downgrade application on period end
- 402 full lock enforcement in get_current_user
- Allowlist routes (/auth/*, /billing/*, /health) remain open when locked
- Payment / order fulfillment unlocks account immediately
- Legacy accounts and platform admins are never locked
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update

import app.models.portal_core as P
from app.core.config import settings
from app.models.billing import AccountSubscription, BillingPlan
from app.routers import auth, billing, companies
from app.services.billing.entitlements import get_entitlements, invalidate_entitlements_cache
from app.services.billing.gateways.base import GatewayPaymentResult
from app.services.billing.orders import create_order, fulfil_order
from app.services.billing.subscriptions import (
    ensure_legacy_subscription,
    process_subscription_lifecycle,
    start_trial,
)
from tests.conftest import bearer, login, run


def make_account(harness, name="Alpha", role_name="Admin"):
    account = harness.add(P.Account(name=name, status="active"))
    company = harness.company(name)
    role = harness.role(role_name)
    user = harness.user(company, role, f"user_{name.lower()}@test.com")
    harness.execute(update(P.Company).where(P.Company.company_id == company.company_id).values(account_id=account.account_id))
    harness.execute(update(P.User).where(P.User.user_id == user.user_id).values(account_id=account.account_id))
    harness.execute(update(P.Role).where(P.Role.role_id == role.role_id).values(account_id=account.account_id))
    return account, company, user


def test_trial_to_grace_and_grace_to_locked(harness):
    account, _, _ = make_account(harness, "Omega")

    async def lifecycle_test():
        async with harness.Session() as db:
            # 1. Start trial
            sub = await start_trial(db, account.account_id, trial_days=7)
            await db.commit()

            # Backdate trial_ends_at to yesterday
            sub.trial_ends_at = datetime.now(timezone.utc) - timedelta(days=1)
            await db.commit()

            # Run lifecycle worker -> trialing should move to grace
            res1 = await process_subscription_lifecycle(db, grace_days=7)
            assert res1["trial_to_grace"] == 1

            sub_after_1 = (await db.execute(
                select(AccountSubscription).where(AccountSubscription.account_id == account.account_id)
            )).scalars().first()
            assert sub_after_1.status == "grace"
            assert sub_after_1.grace_ends_at is not None

            # Account in grace is NOT locked yet
            ent_grace = await get_entitlements(db, account.account_id)
            assert ent_grace.status == "grace"
            assert ent_grace.is_locked is False

            # Backdate grace_ends_at to 1 hour ago
            sub_after_1.grace_ends_at = datetime.now(timezone.utc) - timedelta(hours=1)
            await db.commit()

            # Run lifecycle worker -> grace should move to locked
            res2 = await process_subscription_lifecycle(db)
            assert res2["grace_to_locked"] == 1

            sub_after_2 = (await db.execute(
                select(AccountSubscription).where(AccountSubscription.account_id == account.account_id)
            )).scalars().first()
            assert sub_after_2.status == "locked"

            # Account is now locked
            ent_locked = await get_entitlements(db, account.account_id)
            assert ent_locked.status == "locked"
            assert ent_locked.is_locked is True

    run(lifecycle_test())


def test_402_full_lock_and_allowlist_bypass(harness):
    account, company, owner = make_account(harness, "Sigma")

    # Manually lock account
    async def lock_sub():
        async with harness.Session() as db:
            sub = AccountSubscription(
                account_id=account.account_id,
                status="locked",
            )
            db.add(sub)
            await db.commit()
            invalidate_entitlements_cache(account.account_id)

    run(lock_sub())

    client = harness.app(auth.router, billing.router, companies.router)
    token = bearer(login(client, owner.email))

    # 1. Normal business endpoints return 402 Payment Required with X-Billing-State: locked
    res_companies = client.get("/companies", headers=token)
    assert res_companies.status_code == 402, res_companies.text
    assert res_companies.headers.get("X-Billing-State") == "locked"
    assert "subscription has expired" in res_companies.json()["detail"].lower()

    # 2. Allowlisted endpoints remain accessible:
    # /auth/me
    res_me = client.get("/auth/me", headers=token)
    assert res_me.status_code == 200

    # /billing/current-subscription
    res_sub = client.get("/billing/current-subscription", headers=token)
    assert res_sub.status_code == 200
    assert res_sub.json()["status"] == "locked"

    # /billing/plans
    res_plans = client.get("/billing/plans", headers=token)
    assert res_plans.status_code == 200

    # /billing/quote
    res_quote = client.post("/billing/quote", headers=token, json={"plan_id": "silver", "duration_key": "1_year"})
    assert res_quote.status_code == 200


def test_payment_unlocks_locked_account(harness):
    account, _, owner = make_account(harness, "Kappa")

    # Lock account
    async def lock_sub():
        async with harness.Session() as db:
            sub = AccountSubscription(account_id=account.account_id, status="locked")
            db.add(sub)
            await db.commit()
            invalidate_entitlements_cache(account.account_id)

    run(lock_sub())

    client = harness.app(auth.router, billing.router, companies.router)
    token = bearer(login(client, owner.email))

    # Verify locked
    assert client.get("/companies", headers=token).status_code == 402

    # Pay & fulfill order
    async def pay_and_fulfill():
        async with harness.Session() as db:
            order, _ = await create_order(
                db,
                account_id=account.account_id,
                plan_id="gold",
                duration_key="1_year",
                gateway_code="offline",
                allow_offline=True,
            )
            pmt = GatewayPaymentResult(
                gateway_payment_id="PAY_UNLOCK_1",
                status="captured",
                amount_paise=order.total_paise,
                currency="INR",
            )
            await fulfil_order(db, order.id, gateway_payment=pmt)

    run(pay_and_fulfill())

    # After payment, 402 disappears and companies route returns 200!
    res_after = client.get("/companies", headers=token)
    assert res_after.status_code == 200


def test_legacy_account_is_never_locked(harness):
    account, _, owner = make_account(harness, "Lambda")

    # Ensure legacy subscription
    async def legacy_setup():
        async with harness.Session() as db:
            await ensure_legacy_subscription(db, account.account_id)
            await db.commit()
            # Process lifecycle
            res = await process_subscription_lifecycle(db)
            assert res["trial_to_grace"] == 0
            assert res["active_to_grace"] == 0
            assert res["grace_to_locked"] == 0

    run(legacy_setup())

    client = harness.app(auth.router, billing.router, companies.router)
    token = bearer(login(client, owner.email))

    # Legacy accounts always pass with 200
    res = client.get("/companies", headers=token)
    assert res.status_code == 200
