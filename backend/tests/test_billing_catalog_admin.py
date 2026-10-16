"""
test_billing_catalog_admin.py - Comprehensive test suite for hierarchical Plan Group,
Package, Price, Add-on, Trial catalog admin endpoints, audit logging, and security.
"""

import json
import pytest
from datetime import datetime, timezone
from sqlalchemy import select

from app.core.platform_catalogue import sync_platform_catalogue
from app.models.billing import (
    AccountSubscription,
    BillingAddon,
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
from app.services.billing.subscriptions import start_trial
from sqlalchemy import select, update
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


def test_migration_seed_plans_to_groups(harness):
    """Running migrate_plans_to_groups creates groups for all seeded plans and is idempotent."""
    async def work(db):
        await seed_catalog(db)
        await migrate_plans_to_groups(db)

        # Check groups
        silver_grp = (await db.execute(
            select(BillingPlanGroup).where(BillingPlanGroup.code == "silver")
        )).scalars().first()
        assert silver_grp is not None
        assert silver_grp.is_public is True
        assert silver_grp.allow_extra_users is True

        # Check package linked
        silver_pkg = (await db.execute(
            select(BillingPlan).where(BillingPlan.code == "silver")
        )).scalars().first()
        assert silver_pkg.group_id == silver_grp.id
        assert silver_pkg.label is not None

        # Running migration again causes no duplicates or errors
        count_before = len((await db.execute(select(BillingPlanGroup))).scalars().all())
        await migrate_plans_to_groups(db)
        count_after = len((await db.execute(select(BillingPlanGroup))).scalars().all())
        assert count_before == count_after

    in_db(harness, work)


def test_plan_group_and_package_endpoints_and_audit(harness):
    """Operator can create, edit, activate/deactivate plans and packages with audit logs."""
    client = harness.app(auth.router, billing.router, platform_billing.router)

    async def init(db):
        await sync_platform_catalogue(db)
        await seed_catalog(db)
        op_admin, op_token = await setup_test_operator(db, "super_admin")
        return op_token

    op_token = in_db(harness, init)
    headers = auth_headers(op_token)

    # 1. GET /platform/billing/catalog
    res = client.get("/platform/billing/catalog", headers=headers)
    assert res.status_code == 200
    catalog = res.json()
    assert isinstance(catalog, list)
    assert any(g["code"] == "silver" for g in catalog)

    # 2. POST /platform/billing/plans (create new plan group)
    create_payload = {
        "code": "enterprise_test",
        "name": "Enterprise Test",
        "tagline": "For large businesses",
        "badge": "Popular",
        "display": {"accent": "purple"},
        "features": ["tally_sync", "multi_company"],
        "trial_days": 14,
        "allow_extra_users": True,
        "allow_extra_companies": False,
        "is_public": True,
        "sort_order": 10,
    }
    res_plan = client.post("/platform/billing/plans", json=create_payload, headers=headers)
    assert res_plan.status_code == 200
    plan_data = res_plan.json()
    plan_id = plan_data["id"]
    assert plan_data["code"] == "enterprise_test"

    # 3. PATCH /platform/billing/plans/{id}
    res_patch = client.patch(f"/platform/billing/plans/{plan_id}", json={"name": "Enterprise Pro"}, headers=headers)
    assert res_patch.status_code == 200
    assert res_patch.json()["name"] == "Enterprise Pro"

    # 4. POST /platform/billing/plans/{id}/deactivate & activate
    assert client.post(f"/platform/billing/plans/{plan_id}/deactivate", headers=headers).json()["is_active"] is False
    assert client.post(f"/platform/billing/plans/{plan_id}/activate", headers=headers).json()["is_active"] is True

    # 5. POST /platform/billing/plans/{id}/packages (create package)
    pkg_payload = {
        "max_companies": 5,
        "max_users": 10,
        "max_devices": 15,
        "label": "5 companies + 10 users",
    }
    res_pkg = client.post(f"/platform/billing/plans/{plan_id}/packages", json=pkg_payload, headers=headers)
    assert res_pkg.status_code == 200
    pkg_id = res_pkg.json()["id"]
    assert res_pkg.json()["label"] == "5 companies + 10 users"

    # Creating duplicate combination in same group is rejected with 409
    res_dup = client.post(f"/platform/billing/plans/{plan_id}/packages", json=pkg_payload, headers=headers)
    assert res_dup.status_code == 409

    # 6. PATCH /platform/billing/packages/{id} (editable before use)
    res_pkg_edit = client.patch(f"/platform/billing/packages/{pkg_id}", json={"max_devices": 20}, headers=headers)
    assert res_pkg_edit.status_code == 200

    # 7. POST /platform/billing/packages/{id}/prices (add price)
    price_payload = {
        "interval": "year",
        "interval_count": 1,
        "amount_paise": 4999900,
        "compare_at_paise": 5999900,
        "autopay_allowed": False,
    }
    res_price = client.post(f"/platform/billing/packages/{pkg_id}/prices", json=price_payload, headers=headers)
    assert res_price.status_code == 200
    price_id = res_price.json()["id"]

    # Adding same term again without replace raises 409
    res_price_dup = client.post(f"/platform/billing/packages/{pkg_id}/prices", json=price_payload, headers=headers)
    assert res_price_dup.status_code == 409

    # Adding same term with replace=True succeeds and deactivates old price
    replace_payload = dict(price_payload, amount_paise=4599900, replace=True)
    res_price_replace = client.post(f"/platform/billing/packages/{pkg_id}/prices", json=replace_payload, headers=headers)
    assert res_price_replace.status_code == 200
    new_price_id = res_price_replace.json()["id"]
    assert new_price_id != price_id

    # 8. POST /platform/billing/packages/{id}/duplicate
    res_copy = client.post(f"/platform/billing/packages/{pkg_id}/duplicate", headers=headers)
    assert res_copy.status_code == 200
    copy_pkg_id = res_copy.json()["id"]
    assert copy_pkg_id != pkg_id

    # 9. Check audit log entries were created
    async def check_audits(db):
        audits = (await db.execute(
            select(PlatformAuditLog).order_by(PlatformAuditLog.audit_id.asc())
        )).scalars().all()
        action_types = [a.action_type for a in audits]
        assert "billing.plan_group.create" in action_types
        assert "billing.plan_group.update" in action_types
        assert "billing.plan_group.activate" in action_types
        assert "billing.package.create" in action_types
        assert "billing.price.create" in action_types
        assert "billing.package.duplicate" in action_types

    in_db(harness, check_audits)


def test_package_limits_frozen_once_in_use(harness):
    """Once a package has an active subscription or paid order, limit changes are refused."""
    client = harness.app(auth.router, billing.router, platform_billing.router)
    account, _, _ = make_account(harness, "Corp")

    async def init(db):
        await sync_platform_catalogue(db)
        await seed_catalog(db)
        op_admin, op_token = await setup_test_operator(db, "super_admin")

        # Get silver package
        silver = (await db.execute(select(BillingPlan).where(BillingPlan.code == "silver"))).scalars().first()
        # Add active subscription
        db.add(AccountSubscription(
            account_id=account.account_id,
            plan_id=silver.id,
            status="active",
            current_period_start=datetime.now(timezone.utc),
            current_period_end=datetime.now(timezone.utc),
        ))
        await db.commit()
        return op_token, silver.id

    op_token, silver_pkg_id = in_db(harness, init)
    headers = auth_headers(op_token)

    # Attempting to edit limits on in-use package must fail with 400
    res = client.patch(
        f"/platform/billing/packages/{silver_pkg_id}",
        json={"max_users": 99},
        headers=headers,
    )
    assert res.status_code == 400
    assert "Duplicate this package" in res.json()["detail"]


def test_trial_setting_operator_endpoint_and_usage(harness):
    """Trial settings can be retrieved, updated via operator endpoint, and used by start_trial."""
    client = harness.app(auth.router, billing.router, platform_billing.router)
    account, _, _ = make_account(harness, "TrialAccount")

    async def init(db):
        await sync_platform_catalogue(db)
        await seed_catalog(db)
        op_admin, op_token = await setup_test_operator(db, "super_admin")
        diamond = (await db.execute(select(BillingPlan).where(BillingPlan.code == "diamond"))).scalars().first()
        return op_token, diamond.id

    op_token, diamond_id = in_db(harness, init)
    headers = auth_headers(op_token)

    # 1. GET /platform/billing/settings/trial
    res_get = client.get("/platform/billing/settings/trial", headers=headers)
    assert res_get.status_code == 200

    # 2. PUT /platform/billing/settings/trial
    res_put = client.put(
        "/platform/billing/settings/trial",
        json={"package_id": diamond_id, "trial_days": 21},
        headers=headers,
    )
    assert res_put.status_code == 200
    assert res_put.json()["package_id"] == diamond_id
    assert res_put.json()["trial_days"] == 21

    # 3. start_trial on new account grants Diamond for 21 days
    async def verify(db):
        sub = await start_trial(db, account.account_id)
        assert sub.plan_id == diamond_id
        days = (sub.trial_ends_at.date() - sub.current_period_start.date()).days
        assert days == 21

    in_db(harness, verify)


def test_operator_permission_enforcement(harness):
    """Non-operator or operator without billing.manage cannot access /platform/billing routes."""
    client = harness.app(auth.router, billing.router, platform_billing.router)
    account, _, _ = make_account(harness, "Customer")

    async def init(db):
        await sync_platform_catalogue(db)
        await seed_catalog(db)
        # Operator with support role (no billing.manage permission)
        _, l1_token = await setup_test_operator(db, "support")
        return l1_token

    l1_token = in_db(harness, init)

    # Operator with insufficient permissions gets 403
    res_forbidden = client.get("/platform/billing/catalog", headers=auth_headers(l1_token))
    assert res_forbidden.status_code == 403

    # Customer token (not an operator token) gets 401 or 403
    res_unauth = client.get("/platform/billing/catalog", headers={"Authorization": "Bearer fake_token"})
    assert res_unauth.status_code in (401, 403)


def _operator_with_catalog(harness):
    async def init(db):
        await sync_platform_catalogue(db)
        await seed_catalog(db)
        _, op_token = await setup_test_operator(db, "super_admin")
        return op_token
    return auth_headers(in_db(harness, init))


def _silver(harness):
    async def work(db):
        return (await db.execute(select(BillingPlan).where(BillingPlan.code == "silver"))).scalars().first()
    return in_db(harness, work)


def test_recreating_a_retired_combination_gets_a_free_code_and_a_typed_code_is_never_reused(harness):
    client = harness.app(auth.router, billing.router, platform_billing.router)
    headers = _operator_with_catalog(harness)
    plan_id = client.post("/platform/billing/plans", json={"code": "pro", "name": "Pro"}, headers=headers).json()["id"]
    limits = {"max_companies": 1, "max_users": 1, "max_devices": 2}

    first = client.post(f"/platform/billing/plans/{plan_id}/packages", json=limits, headers=headers).json()
    assert first["code"] == "pro_1c_1u"
    # Same limits twice in one plan: refused while the first is active
    assert client.post(f"/platform/billing/plans/{plan_id}/packages", json=limits, headers=headers).status_code == 409
    client.post(f"/platform/billing/packages/{first['id']}/deactivate", headers=headers)
    second = client.post(f"/platform/billing/plans/{plan_id}/packages", json=limits, headers=headers)
    assert second.status_code == 200 and second.json()["code"] == "pro_1c_1u_2"
    # The retired one cannot come back while the new one offers the same limits
    assert client.post(f"/platform/billing/packages/{first['id']}/activate", headers=headers).status_code == 400

    typed = client.post(f"/platform/billing/plans/{plan_id}/packages",
                        json={"max_companies": 1, "max_users": 3, "max_devices": 2, "code": "pro_1c_1u"}, headers=headers)
    assert typed.status_code == 409


def test_replacing_an_ordered_price_keeps_the_old_row_retired(harness):
    client = harness.app(auth.router, billing.router, platform_billing.router)
    headers = _operator_with_catalog(harness)
    silver = _silver(harness)
    term = {"interval": "year", "interval_count": 1}

    assert client.post(f"/platform/billing/packages/{silver.id}/prices", json={**term, "amount_paise": 500000},
                       headers=headers).status_code == 409
    res = client.post(f"/platform/billing/packages/{silver.id}/prices",
                      json={**term, "amount_paise": 500000, "replace": True}, headers=headers)
    assert res.status_code == 200

    async def check(db):
        rows = (await db.execute(select(BillingPlanPrice).where(
            BillingPlanPrice.plan_id == silver.id, BillingPlanPrice.interval == "year",
            BillingPlanPrice.interval_count == 1))).scalars().all()
        assert sorted(r.is_active for r in rows) == [False, True]
        audit = (await db.execute(select(PlatformAuditLog).where(
            PlatformAuditLog.action_type == "billing.price.replace"))).scalars().one()
        assert json.loads(audit.old_values)["is_active"] is True
    in_db(harness, check)


def test_addons_can_be_listed_and_edited(harness):
    client = harness.app(auth.router, billing.router, platform_billing.router)
    headers = _operator_with_catalog(harness)
    addons = client.get("/platform/billing/addons", headers=headers)
    assert addons.status_code == 200
    user_addon = next(a for a in addons.json() if a["code"] == "extra_user")
    assert user_addon["kind"] == "seat_user"

    res = client.patch(f"/platform/billing/addons/{user_addon['id']}", json={"yearly_paise": 99900}, headers=headers)
    assert res.status_code == 200 and res.json()["yearly_paise"] == 99900
    assert client.patch(f"/platform/billing/addons/{user_addon['id']}", json={"yearly_paise": -1},
                        headers=headers).status_code == 400


def test_a_switched_off_plan_cannot_be_bought_by_any_route(harness):
    client = harness.app(auth.router, billing.router, platform_billing.router)
    headers = _operator_with_catalog(harness)
    account, _, _ = make_account(harness, "Buyer")
    silver = _silver(harness)

    async def price_id(db):
        return (await db.execute(select(BillingPlanPrice.id).where(
            BillingPlanPrice.plan_id == silver.id, BillingPlanPrice.is_active == True))).scalars().first()  # noqa: E712
    pid = in_db(harness, price_id)

    client.post(f"/platform/billing/plans/{silver.group_id}/deactivate", headers=headers)

    async def try_buy(db):
        for kwargs in ({"price_id": pid, "plan_id": None}, {"plan_id": "silver"}):
            with pytest.raises(ValueError, match="not found or inactive"):
                await calculate_quote(db, account_id=account.account_id, **kwargs)
    in_db(harness, try_buy)

    # Back on sale, then made private: still not for sale to the public
    client.post(f"/platform/billing/plans/{silver.group_id}/activate", headers=headers)
    client.patch(f"/platform/billing/plans/{silver.group_id}", json={"is_public": False}, headers=headers)
    in_db(harness, try_buy)


def test_same_package_on_another_term_is_a_renewal(harness):
    headers = _operator_with_catalog(harness)
    client = harness.app(auth.router, billing.router, platform_billing.router)
    account, _, _ = make_account(harness, "Renewer")
    silver = _silver(harness)

    async def setup(db):
        prices = (await db.execute(select(BillingPlanPrice).where(
            BillingPlanPrice.plan_id == silver.id, BillingPlanPrice.interval == "year",
            BillingPlanPrice.is_active == True))).scalars().all()  # noqa: E712
        one_year = next(p for p in prices if p.interval_count == 1)
        three_years = next(p for p in prices if p.interval_count == 3)
        now = datetime.now(timezone.utc)
        db.add(AccountSubscription(account_id=account.account_id, plan_id=silver.id, price_id=one_year.id,
                                   status="active", current_period_start=now,
                                   current_period_end=now.replace(year=now.year + 1)))
        await db.commit()
        return one_year.id, three_years.id
    one_year_id, three_years_id = in_db(harness, setup)

    # 3 years of the same package is cheaper per month, but it is still the same package: a renewal
    async def quote(db, pid):
        return (await calculate_quote(db, plan_id=None, price_id=pid, account_id=account.account_id)).purpose
    assert in_db(harness, lambda db: quote(db, three_years_id)) == "renewal"

    # A new price for the same term after the old one was replaced: still a renewal
    new_id = client.post(f"/platform/billing/packages/{silver.id}/prices",
                         json={"interval": "year", "interval_count": 1, "amount_paise": 1, "replace": True},
                         headers=headers).json()["id"]
    assert in_db(harness, lambda db: quote(db, new_id)) == "renewal"


def test_trial_package_must_be_on_sale(harness):
    client = harness.app(auth.router, billing.router, platform_billing.router)
    headers = _operator_with_catalog(harness)

    async def legacy_id(db):
        return (await db.execute(select(BillingPlan.id).where(BillingPlan.code == "legacy"))).scalar()
    res = client.put("/platform/billing/settings/trial",
                     json={"package_id": in_db(harness, legacy_id), "trial_days": 7}, headers=headers)
    assert res.status_code == 400


def test_switching_on_what_is_already_on_writes_no_audit_row(harness):
    client = harness.app(auth.router, billing.router, platform_billing.router)
    headers = _operator_with_catalog(harness)
    silver = _silver(harness)

    async def count(db):
        return len((await db.execute(select(PlatformAuditLog).where(
            PlatformAuditLog.action_type == "billing.package.activate"))).scalars().all())
    before = in_db(harness, count)
    assert client.post(f"/platform/billing/packages/{silver.id}/activate", headers=headers).status_code == 200
    assert in_db(harness, count) == before
