"""
test_billing_coupons.py - Comprehensive test suite for operator coupon management,
validation rules, frozen terms, status calculations, audit logging, and security.
"""

import json
import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, update

from app.core.platform_catalogue import sync_platform_catalogue
from app.models.billing import (
    AccountSubscription,
    BillingCoupon,
    BillingCouponRedemption,
    BillingOrder,
    BillingPlan,
    BillingPlanGroup,
    BillingPlanPrice,
)
from app.models.platform import PlatformAuditLog
import app.models.portal_core as P
from app.routers import auth, billing, platform_billing
from app.services.billing.catalog import seed_catalog
from app.services.billing.catalog_admin import migrate_plans_to_groups
from app.services.billing.quote import calculate_quote
from tests.conftest import bearer, login, run, setup_test_operator


def make_account(harness, name="Alpha"):
    account = harness.add(P.Account(name=name, status="active"))
    company = harness.company(name)
    owner = harness.user(company, harness.role("Admin"), f"owner_{name.lower()}")
    harness.execute(update(P.Company).where(P.Company.company_id == company.company_id).values(account_id=account.account_id))
    harness.execute(update(P.User).where(P.User.user_id == owner.user_id).values(account_id=account.account_id))
    return account, company, owner


def in_db(harness, work):
    async def go():
        async with harness.Session() as db:
            return await work(db)
    return run(go())


def auth_headers(token: str, extra: dict = None) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    if extra:
        headers.update(extra)
    return headers


def test_coupon_create_validation_and_uniqueness(harness):
    """Test coupon creation, code upper-casing, duplicate 409 rejection, and validation."""
    client = harness.app(auth.router, billing.router, platform_billing.router)

    async def init(db):
        await sync_platform_catalogue(db)
        op_admin, op_token = await setup_test_operator(db, "super_admin")
        return op_token

    op_token = in_db(harness, init)
    headers = auth_headers(op_token)

    # 1. Create coupon with lowercase code -> normalized to upper-case
    payload = {
        "code": "festive25",
        "description": "Festive season 25% discount",
        "kind": "percent",
        "value": 25,
        "max_discount_paise": 200000,
        "per_account_limit": 1,
    }
    res = client.post("/platform/billing/coupons", json=payload, headers=headers)
    assert res.status_code == 200
    coupon_id = res.json()["id"]
    assert res.json()["code"] == "FESTIVE25"

    # 2. Case-insensitive duplicate is rejected with 409
    res_dup = client.post("/platform/billing/coupons", json={"code": "FESTIVE25", "value": 25}, headers=headers)
    assert res_dup.status_code == 409
    res_dup_lower = client.post("/platform/billing/coupons", json={"code": "festive25", "value": 25}, headers=headers)
    assert res_dup_lower.status_code == 409

    # 3. Bad code format rejected with 400
    res_bad = client.post("/platform/billing/coupons", json={"code": "ab", "value": 10}, headers=headers)
    assert res_bad.status_code == 400
    res_bad_chars = client.post("/platform/billing/coupons", json={"code": "SAVE@20", "value": 10}, headers=headers)
    assert res_bad_chars.status_code == 400

    # 4. Bad values rejected
    res_bad_pct = client.post("/platform/billing/coupons", json={"code": "BIG150", "kind": "percent", "value": 150}, headers=headers)
    assert res_bad_pct.status_code == 400
    res_bad_flat = client.post("/platform/billing/coupons", json={"code": "TINYFLAT", "kind": "flat", "value": 50}, headers=headers)
    assert res_bad_flat.status_code == 400


def test_coupon_money_terms_frozen_after_redemption(harness):
    """Rule 4: Money terms (kind, value, max_discount_paise) cannot be changed once redeemed."""
    client = harness.app(auth.router, billing.router, platform_billing.router)

    async def init(db):
        await sync_platform_catalogue(db)
        op_admin, op_token = await setup_test_operator(db, "super_admin")
        return op_token

    op_token = in_db(harness, init)
    headers = auth_headers(op_token)

    account, _, _ = make_account(harness, "Beta")

    # Create coupon
    payload = {
        "code": "FLAT1000",
        "description": "Flat ₹1000 off",
        "kind": "flat",
        "value": 100000,
        "max_redemptions": 10,
    }
    res = client.post("/platform/billing/coupons", json=payload, headers=headers)
    assert res.status_code == 200
    coupon_id = res.json()["id"]

    # Before redemption: money terms can be edited
    res_edit = client.patch(f"/platform/billing/coupons/{coupon_id}", json={"value": 120000}, headers=headers)
    assert res_edit.status_code == 200

    # Record a redemption
    harness.add(BillingCouponRedemption(
        coupon_id=coupon_id,
        account_id=account.account_id,
        order_id=999,
    ))

    # After redemption: changing value or kind is rejected with 400
    res_frozen_val = client.patch(f"/platform/billing/coupons/{coupon_id}", json={"value": 150000}, headers=headers)
    assert res_frozen_val.status_code == 400
    assert "Money terms" in res_frozen_val.json()["detail"]

    res_frozen_kind = client.patch(f"/platform/billing/coupons/{coupon_id}", json={"kind": "percent"}, headers=headers)
    assert res_frozen_kind.status_code == 400

    # Non-money fields can still be edited
    res_edit_desc = client.patch(f"/platform/billing/coupons/{coupon_id}", json={"description": "Updated notes"}, headers=headers)
    assert res_edit_desc.status_code == 200

    # max_redemptions cannot be set below recorded uses
    res_bad_max = client.patch(f"/platform/billing/coupons/{coupon_id}", json={"max_redemptions": 0}, headers=headers)
    assert res_bad_max.status_code == 400


def test_coupon_activate_deactivate_and_status(harness):
    """Test activate/deactivate endpoints and dynamic status calculation."""
    client = harness.app(auth.router, billing.router, platform_billing.router)

    async def init(db):
        await sync_platform_catalogue(db)
        op_admin, op_token = await setup_test_operator(db, "super_admin")
        return op_token

    op_token = in_db(harness, init)
    headers = auth_headers(op_token)

    now = datetime.now(timezone.utc)
    future = (now + timedelta(days=10)).isoformat()

    # Scheduled coupon
    res_sched = client.post("/platform/billing/coupons", json={
        "code": "FUTURE10",
        "value": 10,
        "valid_from": future,
    }, headers=headers)
    assert res_sched.status_code == 200
    sched_id = res_sched.json()["id"]

    coupons_list = client.get("/platform/billing/coupons", headers=headers).json()
    sched_item = next(c for c in coupons_list if c["id"] == sched_id)
    assert sched_item["status"] == "scheduled"

    # Deactivate coupon
    res_deact = client.post(f"/platform/billing/coupons/{sched_id}/deactivate", headers=headers)
    assert res_deact.status_code == 200
    assert res_deact.json()["is_active"] is False

    coupons_list2 = client.get("/platform/billing/coupons", headers=headers).json()
    off_item = next(c for c in coupons_list2 if c["id"] == sched_id)
    assert off_item["status"] == "off"

    # Activate coupon
    res_act = client.post(f"/platform/billing/coupons/{sched_id}/activate", headers=headers)
    assert res_act.status_code == 200
    assert res_act.json()["is_active"] is True


def test_coupon_targeting_and_account_restriction(harness):
    """Coupon plan code targeting and account restriction checks."""
    client = harness.app(auth.router, billing.router, platform_billing.router)

    async def init(db):
        await sync_platform_catalogue(db)
        await seed_catalog(db)
        await migrate_plans_to_groups(db)
        op_admin, op_token = await setup_test_operator(db, "super_admin")
        return op_token

    op_token = in_db(harness, init)
    headers = auth_headers(op_token)

    acc1, _, _ = make_account(harness, "ClientOne")
    acc2, _, _ = make_account(harness, "ClientTwo")

    # Create coupon restricted to ClientOne
    res_priv = client.post("/platform/billing/coupons", json={
        "code": "PRIVATE1",
        "value": 20,
        "account_id": acc1.account_id,
        "plan_codes": ["gold"],
    }, headers=headers)
    assert res_priv.status_code == 200

    # In quote: ClientOne succeeds, ClientTwo fails, anonymous fails
    async def test_quotes(db):
        # acc1 succeeds
        q1 = await calculate_quote(db, plan_id="gold", duration_key="1_year", coupon_code="PRIVATE1", account_id=acc1.account_id)
        assert q1.discount_paise > 0
        assert q1.coupon_code == "PRIVATE1"

        # acc2 fails
        with pytest.raises(ValueError, match="not valid"):
            await calculate_quote(db, plan_id="gold", duration_key="1_year", coupon_code="PRIVATE1", account_id=acc2.account_id)

        # anonymous fails
        with pytest.raises(ValueError, match="not valid"):
            await calculate_quote(db, plan_id="gold", duration_key="1_year", coupon_code="PRIVATE1", account_id=None)

        # plan mismatch (e.g. silver) fails
        with pytest.raises(ValueError, match="not valid for the"):
            await calculate_quote(db, plan_id="silver", duration_key="1_year", coupon_code="PRIVATE1", account_id=acc1.account_id)

    in_db(harness, test_quotes)


def test_coupon_permissions_and_audit_logging(harness):
    """Operators without billing.manage are rejected; writes write to PlatformAuditLog."""
    client = harness.app(auth.router, billing.router, platform_billing.router)

    async def init(db):
        await sync_platform_catalogue(db)
        _, support_tok = await setup_test_operator(db, "support")
        _, super_tok = await setup_test_operator(db, "super_admin")
        return support_tok, super_tok

    support_token, super_token = in_db(harness, init)

    headers_support = auth_headers(support_token)
    res_forbidden = client.get("/platform/billing/coupons", headers=headers_support)
    assert res_forbidden.status_code == 403

    res_post_forbidden = client.post("/platform/billing/coupons", json={"code": "NOPE20", "value": 20}, headers=headers_support)
    assert res_post_forbidden.status_code == 403

    # Super admin creates coupon and updates it
    headers = auth_headers(super_token)
    res = client.post("/platform/billing/coupons", json={"code": "AUDITME", "value": 15}, headers=headers)
    assert res.status_code == 200
    cid = res.json()["id"]

    client.patch(f"/platform/billing/coupons/{cid}", json={"description": "Audit test"}, headers=headers)

    # Check PlatformAuditLog in DB
    async def check_audit(db):
        logs = (await db.execute(
            select(PlatformAuditLog).where(
                PlatformAuditLog.target_type == "coupon",
                PlatformAuditLog.target_id == cid,
            )
        )).scalars().all()
        assert len(logs) >= 2
        actions = [l.action_type for l in logs]
        assert "billing.coupon.create" in actions
        assert "billing.coupon.update" in actions

    in_db(harness, check_audit)


def test_coupon_plan_codes_and_account_must_exist(harness):
    client = harness.app(auth.router, billing.router, platform_billing.router)

    async def init(db):
        await sync_platform_catalogue(db)
        await seed_catalog(db)
        _, op_token = await setup_test_operator(db, "super_admin")
        return op_token
    headers = auth_headers(in_db(harness, init))

    typo = client.post("/platform/billing/coupons", json={"code": "TYPO10", "value": 10, "plan_codes": ["silvr"]},
                       headers=headers)
    assert typo.status_code == 400 and "silvr" in typo.json()["detail"]
    nobody = client.post("/platform/billing/coupons", json={"code": "NOBODY10", "value": 10, "account_id": 999999},
                         headers=headers)
    assert nobody.status_code == 400
    ok = client.post("/platform/billing/coupons", json={"code": "SILVER10", "value": 10, "plan_codes": ["Silver", "addon"]},
                     headers=headers)
    assert ok.status_code == 200


def test_coupon_dates_are_stored_in_utc(harness):
    client = harness.app(auth.router, billing.router, platform_billing.router)

    async def init(db):
        await sync_platform_catalogue(db)
        _, op_token = await setup_test_operator(db, "super_admin")
        return op_token
    headers = auth_headers(in_db(harness, init))

    res = client.post("/platform/billing/coupons",
                      json={"code": "IST10", "value": 10, "valid_from": "2030-01-01T05:30:00+05:30"}, headers=headers)
    assert res.status_code == 200

    async def check(db):
        coupon = (await db.execute(select(BillingCoupon).where(BillingCoupon.code == "IST10"))).scalars().one()
        assert coupon.valid_from == datetime(2030, 1, 1, 0, 0)
    in_db(harness, check)
