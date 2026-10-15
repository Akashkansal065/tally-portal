"""
Unit tests for entitlements: user, company and device limits; legacy unlimited;
extra add-ons and operator overrides; feature gating.
"""
import json
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select, update

import app.models.portal_core as P
from app.models.billing import AccountSubscription, BillingPlan
from app.routers import auth, team
from app.services.billing.entitlements import get_entitlements, invalidate_entitlements_cache, require_feature
from app.services.billing.subscriptions import ensure_legacy_subscription, start_trial
from tests.conftest import bearer, login


def world(harness):
    account = harness.add(P.Account(name="Alpha", status="active"))
    company = harness.company("Alpha")
    role = harness.role("Admin")
    owner = harness.user(company, role, "owner")
    harness.execute(update(P.Company).values(account_id=account.account_id))
    harness.execute(update(P.User).values(account_id=account.account_id))
    harness.execute(update(P.Role).values(account_id=account.account_id))
    return account, company, owner


def test_legacy_subscription_is_unlimited(harness):
    account, _, _ = world(harness)

    async def check():
        async with harness.Session() as db:
            ent = await get_entitlements(db, account.account_id)
            assert ent.status == "legacy"
            assert ent.max_users is None
            assert ent.max_companies is None
            assert ent.max_devices is None
            assert ent.is_locked is False
            assert ent.can_sync is True
            # All features allowed for legacy
            assert ent.has_feature("einvoice_eway_bill") is True
            assert ent.has_feature("bank_reconciliation") is True
    from tests.conftest import run
    run(check())


def test_trial_subscription_enforces_gold_limits_and_features(harness):
    account, _, _ = world(harness)

    async def check():
        async with harness.Session() as db:
            sub = await start_trial(db, account.account_id, trial_days=7)
            invalidate_entitlements_cache(account.account_id)
            ent = await get_entitlements(db, account.account_id)

            assert ent.status == "trialing"
            assert ent.plan_code == "gold"
            assert ent.max_users == 3
            assert ent.max_companies == 5
            assert ent.max_devices == 5
            assert ent.trial_ends_at is not None
            # Gold includes salesman check-in & orders, but not enterprise e-invoicing
            assert ent.has_feature("salesman_checkin_orders") is True
            assert ent.has_feature("einvoice_eway_bill") is False
    from tests.conftest import run
    run(check())


def test_purchased_addons_increase_limits(harness):
    account, _, _ = world(harness)

    async def check():
        async with harness.Session() as db:
            silver_plan = (await db.execute(
                select(BillingPlan).where(BillingPlan.code == "silver")
            )).scalars().first()

            sub = AccountSubscription(
                account_id=account.account_id,
                plan_id=silver_plan.id,
                status="active",
                extra_users=2,        # 1 base + 2 extra = 3
                extra_companies=3,    # 1 base + 3 extra = 4
            )
            db.add(sub)
            await db.commit()

            invalidate_entitlements_cache(account.account_id)
            ent = await get_entitlements(db, account.account_id)

            assert ent.status == "active"
            assert ent.plan_code == "silver"
            assert ent.max_users == 3
            assert ent.max_companies == 4
    from tests.conftest import run
    run(check())


def test_operator_overrides_adjust_limits_and_features(harness):
    account, _, _ = world(harness)

    async def check():
        async with harness.Session() as db:
            silver_plan = (await db.execute(
                select(BillingPlan).where(BillingPlan.code == "silver")
            )).scalars().first()

            sub = AccountSubscription(
                account_id=account.account_id,
                plan_id=silver_plan.id,
                status="active",
                extra_users=0,
                extra_companies=0,
                overrides=json.dumps({
                    "max_users": 10,
                    "extra_features": ["einvoice_eway_bill"],
                }),
            )
            db.add(sub)
            await db.commit()

            invalidate_entitlements_cache(account.account_id)
            ent = await get_entitlements(db, account.account_id)

            assert ent.max_users == 10
            assert ent.has_feature("einvoice_eway_bill") is True
    from tests.conftest import run
    run(check())


def test_user_limit_enforced_on_invite(harness):
    account, company, owner = world(harness)
    client = harness.app(auth.router, team.router)
    token = bearer(login(client, owner.email))

    # Give the account Silver subscription (max_users = 1)
    async def set_silver():
        async with harness.Session() as db:
            silver = (await db.execute(
                select(BillingPlan).where(BillingPlan.code == "silver")
            )).scalars().first()
            sub = AccountSubscription(
                account_id=account.account_id,
                plan_id=silver.id,
                status="active",
                extra_users=0,
            )
            db.add(sub)
            await db.commit()
    from tests.conftest import run
    run(set_silver())
    invalidate_entitlements_cache(account.account_id)

    # 1 user (owner) already active. Inviting a 2nd user must return 403 Forbidden!
    role = harness.scalar(select(P.Role.role_id).where(P.Role.name == "Admin"))
    res = client.post(
        "/admin/invites",
        json={"email": "second@example.com", "role_id": role, "company_ids": [company.company_id]},
        headers=token,
    )
    assert res.status_code == 403
    assert "allows 1 user(s)" in res.json()["detail"]


def test_require_feature_dependency_rejects_missing_feature(harness):
    account, _, owner = world(harness)

    from fastapi import APIRouter
    test_router = APIRouter()
    @test_router.get("/guarded-einvoice", dependencies=[Depends(require_feature("einvoice_eway_bill"))])
    def guarded():
        return {"ok": True}

    client = harness.app(auth.router, test_router)
    token = bearer(login(client, owner.email))

    # Put account on Silver (which does not have einvoice_eway_bill)
    async def set_silver():
        async with harness.Session() as db:
            silver = (await db.execute(
                select(BillingPlan).where(BillingPlan.code == "silver")
            )).scalars().first()
            sub = AccountSubscription(
                account_id=account.account_id,
                plan_id=silver.id,
                status="active",
            )
            db.add(sub)
            await db.commit()
    from tests.conftest import run
    run(set_silver())
    invalidate_entitlements_cache(account.account_id)

    res = client.get("/guarded-einvoice", headers=token)
    assert res.status_code == 403
    assert res.headers["x-billing-reason"] == "feature"
    assert res.headers["x-billing-required-feature"] == "einvoice_eway_bill"
