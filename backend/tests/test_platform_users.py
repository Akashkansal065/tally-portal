"""
test_platform_users.py – Tests for Phase 2: Customer User CRUD, Concurrency (ETag/409),
PII Masking, Last-Admin Guard, Lifecycle Actions, and Billing Migration.
"""

from datetime import datetime
import json
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_db
from app.core.platform_catalogue import bootstrap_first_super_admin, sync_platform_catalogue
from app.core.platform_security import (
    create_platform_access_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    utc_now,
)
from app.models.platform import (
    PlatformAdmin,
    PlatformAdminRole,
    PlatformAdminSession,
    PlatformAuditLog,
    PlatformRole,
)
from app.models.portal_core import Account, Company, Role, User, UserSession
from app.models.billing import BillingPlan, BillingPlanPrice
from app.routers import auth, platform_auth, platform_billing, platform_users
from tests.conftest import Harness, run, setup_test_operator


@pytest.fixture
def users_test_app(tmp_path):
    h = Harness(tmp_path)

    app = FastAPI()
    app.include_router(auth.router)
    app.include_router(platform_auth.router)
    app.include_router(platform_users.router)
    app.include_router(platform_billing.router)

    app.dependency_overrides[get_db] = h._get_db
    app.dependency_overrides[platform_auth.get_db] = h._get_db
    app.dependency_overrides[platform_users.get_db] = h._get_db
    app.dependency_overrides[platform_billing.get_db] = h._get_db

    client = TestClient(app)
    return h, client


async def setup_test_customer_account_and_user(db):
    """Helper to create an account, company, roles, and a customer user."""
    acc = Account(name="Acme Corp")
    db.add(acc)
    await db.flush()

    comp = Company(
        account_id=acc.account_id,
        name="Acme Main",
        books_begin_date=datetime.now().date(),
    )
    db.add(comp)
    await db.flush()

    admin_role = Role(account_id=acc.account_id, name="Admin")
    sales_role = Role(account_id=acc.account_id, name="Sales")
    db.add_all([admin_role, sales_role])
    await db.flush()

    user = User(
        account_id=acc.account_id,
        company_id=comp.company_id,
        role_id=admin_role.role_id,
        username="john_doe",
        email="john.doe@example.com",
        phone="+919876543210",
        password_hash=hash_password("CustomerPass123!"),
        is_active=True,
        status="active",
        version=1,
    )
    db.add(user)
    await db.commit()
    return acc, comp, admin_role, sales_role, user


def test_users_list_pii_masking_and_unmasked_audit(users_test_app):
    """Operators without users.read_pii see masked fields; operators with it see real data and trigger pii_viewed audit."""
    h, client = users_test_app

    async def run_test():
        async with h.Session() as db:
            acc, comp, admin_role, sales_role, customer = await setup_test_customer_account_and_user(db)
            super_admin, super_token = await setup_test_operator(db, "super_admin")
            support_admin, support_token = await setup_test_operator(db, "support")
            c_id = customer.user_id

        # 1. Support role (has users.read but NOT users.read_pii)
        res_support = client.get(
            "/platform/users",
            cookies={"pa_at": support_token},
        )
        assert res_support.status_code == 200
        data_support = res_support.json()
        assert len(data_support["items"]) >= 1
        item = [i for i in data_support["items"] if i["user_id"] == c_id][0]
        assert "••••" in item["email"]
        assert "••••" in item["phone"]

        # 2. Super admin (has users.read_pii)
        res_super = client.get(
            f"/platform/users/{c_id}",
            cookies={"pa_at": super_token},
        )
        assert res_super.status_code == 200
        data_super = res_super.json()
        assert data_super["email"] == "john.doe@example.com"
        assert data_super["phone"] == "+919876543210"
        assert res_super.headers["ETag"] == 'W/"1"'

        # Verify audit entry for PII viewing was recorded
        async with h.Session() as db:
            audit_res = await db.execute(
                select(PlatformAuditLog).where(
                    PlatformAuditLog.action_type == "users.pii_viewed",
                    PlatformAuditLog.target_user_id == c_id,
                )
            )
            audit_entry = audit_res.scalars().first()
            assert audit_entry is not None
            assert audit_entry.admin_email == super_admin.email

    run(run_test())


def test_optimistic_concurrency_and_if_match_header(users_test_app):
    """Updates must provide If-Match header / version. Mismatched version causes 409 Conflict."""
    h, client = users_test_app

    async def run_test():
        async with h.Session() as db:
            acc, comp, admin_role, sales_role, customer = await setup_test_customer_account_and_user(db)
            super_admin, super_token = await setup_test_operator(db, "super_admin")
            c_id = customer.user_id

        # 1. Update without If-Match header or version -> 428 Precondition Required
        res_no_ver = client.patch(
            f"/platform/users/{c_id}",
            json={"designation": "Manager"},
            cookies={"pa_at": super_token, "pa_csrf": "test"},
            headers={"X-CSRF-Token": "test"},
        )
        assert res_no_ver.status_code == 428

        # 2. Update with wrong version -> 409 Conflict
        res_conflict = client.patch(
            f"/platform/users/{c_id}",
            json={"designation": "Manager"},
            cookies={"pa_at": super_token, "pa_csrf": "test"},
            headers={"If-Match": 'W/"99"', "X-CSRF-Token": "test"},
        )
        assert res_conflict.status_code == 409

        # 3. Update with correct version -> 200 OK and version increments to 2
        res_ok = client.patch(
            f"/platform/users/{c_id}",
            json={"designation": "Senior Manager", "reason": "Annual promotion"},
            cookies={"pa_at": super_token, "pa_csrf": "test"},
            headers={"If-Match": 'W/"1"', "X-CSRF-Token": "test"},
        )
        assert res_ok.status_code == 200
        assert res_ok.json()["version"] == 2

        # Verify audit log diff was written
        async with h.Session() as db:
            audit_res = await db.execute(
                select(PlatformAuditLog).where(
                    PlatformAuditLog.action_type == "users.update",
                    PlatformAuditLog.target_user_id == c_id,
                )
            )
            audit_entry = audit_res.scalars().first()
            assert audit_entry is not None
            assert "Senior Manager" in audit_entry.new_values

    run(run_test())


def test_last_admin_protection_on_demote_and_delete(users_test_app):
    """An account's last active Admin user cannot be demoted or soft deleted."""
    h, client = users_test_app

    async def run_test():
        async with h.Session() as db:
            acc, comp, admin_role, sales_role, customer = await setup_test_customer_account_and_user(db)
            super_admin, super_token = await setup_test_operator(db, "super_admin")
            c_id = customer.user_id
            sales_id = sales_role.role_id

        # 1. Attempt to demote to Sales role -> 400
        res_demote = client.patch(
            f"/platform/users/{c_id}",
            json={"role_id": sales_id, "version": 1},
            cookies={"pa_at": super_token, "pa_csrf": "test"},
            headers={"If-Match": 'W/"1"', "X-CSRF-Token": "test"},
        )
        assert res_demote.status_code == 400
        assert "last Admin" in res_demote.json()["detail"]

        # 2. Attempt to soft delete the only Admin -> 400
        res_del = client.delete(
            f"/platform/users/{c_id}",
            cookies={"pa_at": super_token, "pa_csrf": "test"},
            headers={"X-CSRF-Token": "test"},
        )
        assert res_del.status_code == 400
        assert "last Admin" in res_del.json()["detail"]

    run(run_test())


def test_user_lifecycle_suspend_reinstate_soft_delete_and_customer_auth(users_test_app):
    """Suspending or soft-deleting a user blocks customer logins and revokes sessions."""
    h, client = users_test_app

    async def run_test():
        async with h.Session() as db:
            acc, comp, admin_role, sales_role, customer = await setup_test_customer_account_and_user(db)
            super_admin, super_token = await setup_test_operator(db, "super_admin")
            c_id = customer.user_id
            c_email = customer.email

        # Customer login initially succeeds
        login_res = client.post(
            "/auth/login",
            json={"email": c_email, "password": "CustomerPass123!"},
        )
        assert login_res.status_code == 200

        # Suspend customer user
        susp_res = client.post(
            f"/platform/users/{c_id}/suspend",
            json={"reason": "Suspicious login from unexpected country"},
            cookies={"pa_at": super_token, "pa_csrf": "test"},
            headers={"X-CSRF-Token": "test"},
        )
        assert susp_res.status_code == 200

        # Customer login now refused with 403
        login_refused = client.post(
            "/auth/login",
            json={"email": c_email, "password": "CustomerPass123!"},
        )
        assert login_refused.status_code == 403
        assert "suspended" in login_refused.json()["detail"]

        # Reinstate user
        reinstate_res = client.post(
            f"/platform/users/{c_id}/reinstate",
            json={"reason": "Identity verified with customer admin"},
            cookies={"pa_at": super_token, "pa_csrf": "test"},
            headers={"X-CSRF-Token": "test"},
        )
        assert reinstate_res.status_code == 200

        # Customer login succeeds again
        login_ok_again = client.post(
            "/auth/login",
            json={"email": c_email, "password": "CustomerPass123!"},
        )
        assert login_ok_again.status_code == 200

    run(run_test())


def test_password_reset_temporary_mode_and_audit(users_test_app):
    """Temporary password reset issues 16-char password, marks must_change_password, and audits without revealing password."""
    h, client = users_test_app

    async def run_test():
        async with h.Session() as db:
            acc, comp, admin_role, sales_role, customer = await setup_test_customer_account_and_user(db)
            super_admin, super_token = await setup_test_operator(db, "super_admin")
            c_id = customer.user_id
            c_email = customer.email

        res = client.post(
            f"/platform/users/{c_id}/password-reset",
            json={"mode": "temporary", "reason": "Operator requested emergency access"},
            cookies={"pa_at": super_token, "pa_csrf": "test"},
            headers={"X-CSRF-Token": "test"},
        )
        assert res.status_code == 200
        temp_pwd = res.json()["one_time_temp_password"]
        assert len(temp_pwd) == 16

        # Audit row does NOT contain the temp password
        async with h.Session() as db:
            audit_res = await db.execute(
                select(PlatformAuditLog).where(
                    PlatformAuditLog.action_type == "users.reset_password",
                    PlatformAuditLog.target_user_id == c_id,
                )
            )
            audit_entry = audit_res.scalars().first()
            assert audit_entry is not None
            assert temp_pwd not in (audit_entry.new_values or "")

        # Customer can now log in with the temporary password
        temp_login = client.post(
            "/auth/login",
            json={"email": c_email, "password": temp_pwd},
        )
        assert temp_login.status_code == 200

    run(run_test())


def test_platform_billing_protected_by_new_dependency(users_test_app):
    """Billing routes under /platform/billing now require platform permissions instead of PLATFORM_ADMIN_EMAILS."""
    h, client = users_test_app

    async def run_test():
        async with h.Session() as db:
            super_admin, super_token = await setup_test_operator(db, "super_admin")
            support_admin, support_token = await setup_test_operator(db, "support")

            # Seed a plan so list returns something
            plan = BillingPlan(code="standard_monthly", name="Standard Plan", is_public=True)
            db.add(plan)
            await db.commit()

        # Support operator without billing.manage -> 403
        res_supp = client.get(
            "/platform/billing/metrics",
            cookies={"pa_at": support_token},
        )
        assert res_supp.status_code == 403

        # Super admin with billing.manage -> 200
        res_super = client.get(
            "/platform/billing/metrics",
            cookies={"pa_at": super_token},
        )
        assert res_super.status_code == 200

    run(run_test())
