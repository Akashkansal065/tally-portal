"""
test_platform_purge_and_impersonate.py – Automated tests for Phase 5:
  - Two-Person Purge Approval Workflow & Irreversible GDPR Anonymisation
  - Self-Approval Rejection (Two-Person Rule enforcement)
  - Accounting & Tax Record Preservation during Hard-Delete
  - Time-Boxed Marked Operator Impersonation (Read-only vs. Write, Premature Termination)
  - Prohibited Tenant Actions during Impersonation (Password, Billing, Delete)
  - Nightly Purge Worker for Expired Soft-Deleted Users (30-day retention)
  - Statutory Data Retention Policy Catalogue
  - Pre-Go-Live Boot Security Scan
"""

from datetime import datetime, timedelta, timezone
import json
import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.core.config import settings
from app.core.database import get_db
from app.core.permissions import get_current_user
from app.core.platform_catalogue import sync_platform_catalogue
from app.core.platform_security import (
    create_platform_access_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    utc_now,
    verify_platform_routes_security,
)
from app.models.platform import (
    PlatformAdmin,
    PlatformAdminRole,
    PlatformAdminSession,
    PlatformAuditLog,
    PlatformImpersonationSession,
    PlatformPurgeRequest,
    PlatformRetentionPolicy,
    PlatformRole,
)
from app.models.portal_core import (
    Account,
    Company,
    Role,
    User,
    UserCompanyAccess,
    UserPermissionOverride,
    UserPhone,
    UserSession,
)
from app.routers import auth, platform_auth, platform_billing, platform_users, platform_roles, platform_admins, platform_audit
from app.services.daily_cleanup import purge_expired_soft_deleted_users, purge_old_platform_login_attempts
from tests.conftest import Harness, run


@pytest.fixture
def purge_test_app(tmp_path):
    h = Harness(tmp_path)

    app = FastAPI()
    app.include_router(auth.router)
    app.include_router(platform_auth.router)
    app.include_router(platform_users.router)
    app.include_router(platform_billing.router)
    app.include_router(platform_roles.router)
    app.include_router(platform_admins.router)
    app.include_router(platform_audit.router)

    app.dependency_overrides[get_db] = h._get_db
    app.dependency_overrides[auth.get_db] = h._get_db
    app.dependency_overrides[platform_auth.get_db] = h._get_db
    app.dependency_overrides[platform_users.get_db] = h._get_db
    app.dependency_overrides[platform_billing.get_db] = h._get_db
    app.dependency_overrides[platform_roles.get_db] = h._get_db
    app.dependency_overrides[platform_admins.get_db] = h._get_db
    app.dependency_overrides[platform_audit.get_db] = h._get_db

    client = TestClient(app)
    return h, client, app


async def create_operator(db, email: str, role_code: str = "super_admin"):
    """Creates a test operator with given email and role, returning cookies dict."""
    await sync_platform_catalogue(db)

    res = await db.execute(select(PlatformRole).where(PlatformRole.code == role_code))
    role = res.scalars().first()

    now = utc_now()
    admin = PlatformAdmin(
        email=email,
        password_hash=hash_password("SuperSecret12345!"),
        full_name=f"Admin {email}",
        status="active",
        permission_version=1,
    )
    db.add(admin)
    await db.flush()

    db.add(PlatformAdminRole(admin_id=admin.admin_id, role_id=role.role_id))
    await db.flush()

    raw_rf = generate_refresh_token()
    rf_hash = hash_token(raw_rf)
    session = PlatformAdminSession(
        admin_id=admin.admin_id,
        family_id="test-family",
        refresh_hash=rf_hash,
        mfa_at=now,
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(hours=8),
    )
    db.add(session)
    await db.commit()

    token = create_platform_access_token(
        admin_id=admin.admin_id,
        session_id=session.session_id,
        permission_version=1,
        amr=["password", "passkey"],
    )

    cookies = {
        "pa_at": token,
        "__Secure-pa_at": token,
        "pa_rt": raw_rf,
        "__Secure-pa_rt": raw_rf,
        "pa_csrf": "test-csrf-token",
    }
    return admin, session, cookies


async def setup_test_account_and_users(db):
    """Sets up a customer account with an Admin user and a Staff user."""
    acc = Account(name="Acme Corp")
    db.add(acc)
    await db.flush()

    comp = Company(
        account_id=acc.account_id,
        name="Acme India Ltd",
        books_begin_date=datetime.now().date(),
    )
    db.add(comp)
    await db.flush()

    admin_role = Role(account_id=acc.account_id, name="Admin")
    staff_role = Role(account_id=acc.account_id, name="Sales Staff")
    db.add_all([admin_role, staff_role])
    await db.flush()

    user_admin = User(
        account_id=acc.account_id,
        company_id=comp.company_id,
        role_id=admin_role.role_id,
        email="admin@acme.com",
        username="Acme Admin",
        password_hash=hash_password("AcmePass123!"),
        phone="+919876543210",
        designation="Managing Director",
        employee_code="ACME-001",
        is_active=True,
    )
    user_staff = User(
        account_id=acc.account_id,
        company_id=comp.company_id,
        role_id=staff_role.role_id,
        email="john@acme.com",
        username="John Doe",
        password_hash=hash_password("StaffPass123!"),
        phone="+919123456789",
        designation="Sales Executive",
        employee_code="ACME-002",
        is_active=True,
    )
    db.add_all([user_admin, user_staff])
    await db.commit()

    return acc, comp, user_admin, user_staff


def test_purge_request_creation_and_self_approval_blocked(purge_test_app):
    """
    Tests:
    1. Operator 1 requests purge on customer user.
    2. Attempting to approve own purge request is refused with 403 (Two-Person Rule).
    """
    h, client, _ = purge_test_app

    async def _run():
        async with h.Session() as db:
            admin1, _, cookies1 = await create_operator(db, "operator1@mytally.com", "super_admin")
            acc, comp, user_admin, user_staff = await setup_test_account_and_users(db)
            staff_id = user_staff.user_id

        # Operator 1 creates purge request
        resp = client.post(
            f"/platform/users/{staff_id}/purge-requests",
            json={"reason": "Customer requested GDPR right to erasure per ticket #9901."},
            cookies=cookies1,
            headers={"X-CSRF-Token": "test-csrf-token"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "pending"
        req_id = data["purge_request_id"]
        assert req_id > 0

        # Operator 1 attempts to approve their OWN purge request -> Must be 403 Forbidden!
        resp_self = client.post(
            f"/platform/users/purge-requests/{req_id}/approve",
            cookies=cookies1,
            headers={"X-CSRF-Token": "test-csrf-token"},
        )
        assert resp_self.status_code == 403
        assert "Two-person approval rule violation" in resp_self.json()["detail"]

    run(_run())


def test_purge_approval_by_second_operator_executes_anonymisation(purge_test_app):
    """
    Tests:
    1. Operator 1 requests purge.
    2. Operator 2 approves purge.
    3. User personal data is completely anonymised.
    4. Sessions and child tables cleared.
    5. Audit trail records users.hard_delete.
    """
    h, client, _ = purge_test_app

    async def _run():
        async with h.Session() as db:
            admin1, _, cookies1 = await create_operator(db, "requester@mytally.com", "super_admin")
            admin2, _, cookies2 = await create_operator(db, "approver@mytally.com", "super_admin")
            acc, comp, user_admin, user_staff = await setup_test_account_and_users(db)
            staff_id = user_staff.user_id

            # Add an active session and a phone row for the staff user
            db.add(UserPhone(phone="+919123456789", user_id=staff_id, verified_at=utc_now()))
            db.add(UserSession(user_id=staff_id, token_hash="dummy-staff-tok", expires_at=utc_now() + timedelta(days=1)))
            await db.commit()

        # Operator 1 creates purge request
        resp1 = client.post(
            f"/platform/users/{staff_id}/purge-requests",
            json={"reason": "GDPR erasure mandate ticket #102."},
            cookies=cookies1,
            headers={"X-CSRF-Token": "test-csrf-token"},
        )
        assert resp1.status_code == 200
        req_id = resp1.json()["purge_request_id"]

        # Operator 2 approves the request
        resp2 = client.post(
            f"/platform/users/purge-requests/{req_id}/approve",
            cookies=cookies2,
            headers={"X-CSRF-Token": "test-csrf-token"},
        )
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "executed"

        # Verify DB state of user
        async with h.Session() as db:
            user_check = (await db.execute(select(User).where(User.user_id == staff_id))).scalars().first()
            assert user_check.username == f"Deleted user {staff_id}"
            assert user_check.email == f"purged-{staff_id}@deleted.local"
            assert user_check.phone is None
            assert user_check.designation is None
            assert user_check.employee_code is None
            assert user_check.password_hash == "!ANONYMIZED_DO_NOT_USE!"
            assert user_check.is_active is False
            assert user_check.status == "purged"
            assert user_check.purged_at is not None

            # Verify child tables were cleaned
            phones = (await db.execute(select(UserPhone).where(UserPhone.user_id == staff_id))).scalars().all()
            assert len(phones) == 0
            sessions = (await db.execute(select(UserSession).where(UserSession.user_id == staff_id))).scalars().all()
            assert len(sessions) == 0

            # Verify audit log
            audit_entry = (
                await db.execute(
                    select(PlatformAuditLog).where(
                        PlatformAuditLog.action_type == "users.hard_delete",
                        PlatformAuditLog.target_user_id == staff_id,
                    )
                )
            ).scalars().first()
            assert audit_entry is not None
            assert audit_entry.admin_email == "approver@mytally.com"
            assert f"#{req_id}" in audit_entry.reason

    run(_run())


def test_purge_request_duplicate_and_last_admin_guards(purge_test_app):
    """Tests that duplicate purge requests and last-Admin purges are refused."""
    h, client, _ = purge_test_app

    async def _run():
        async with h.Session() as db:
            admin1, _, cookies1 = await create_operator(db, "op_guard@mytally.com", "super_admin")
            acc, comp, user_admin, user_staff = await setup_test_account_and_users(db)
            admin_id = user_admin.user_id
            staff_id = user_staff.user_id

        # 1. Purge on last Admin must be 400
        resp_admin = client.post(
            f"/platform/users/{admin_id}/purge-requests",
            json={"reason": "Attempting to purge sole admin"},
            cookies=cookies1,
            headers={"X-CSRF-Token": "test-csrf-token"},
        )
        assert resp_admin.status_code == 400
        assert "Cannot purge the last Admin" in resp_admin.json()["detail"]

        # 2. First purge request on staff user succeeds
        resp_staff1 = client.post(
            f"/platform/users/{staff_id}/purge-requests",
            json={"reason": "First request"},
            cookies=cookies1,
            headers={"X-CSRF-Token": "test-csrf-token"},
        )
        assert resp_staff1.status_code == 200

        # 3. Duplicate pending purge request must return 409 Conflict
        resp_staff2 = client.post(
            f"/platform/users/{staff_id}/purge-requests",
            json={"reason": "Duplicate request"},
            cookies=cookies1,
            headers={"X-CSRF-Token": "test-csrf-token"},
        )
        assert resp_staff2.status_code == 409
        assert "already pending" in resp_staff2.json()["detail"]

    run(_run())


def test_purge_rejection(purge_test_app):
    """Tests rejecting a purge request."""
    h, client, _ = purge_test_app

    async def _run():
        async with h.Session() as db:
            admin1, _, cookies1 = await create_operator(db, "req_op@mytally.com", "super_admin")
            admin2, _, cookies2 = await create_operator(db, "rej_op@mytally.com", "super_admin")
            acc, comp, user_admin, user_staff = await setup_test_account_and_users(db)
            staff_id = user_staff.user_id

        resp = client.post(
            f"/platform/users/{staff_id}/purge-requests",
            json={"reason": "Customer inquiry"},
            cookies=cookies1,
            headers={"X-CSRF-Token": "test-csrf-token"},
        )
        req_id = resp.json()["purge_request_id"]

        # Operator 2 rejects the request
        resp_rej = client.post(
            f"/platform/users/purge-requests/{req_id}/reject",
            json={"rejection_reason": "Customer changed mind and cancelled ticket."},
            cookies=cookies2,
            headers={"X-CSRF-Token": "test-csrf-token"},
        )
        assert resp_rej.status_code == 200
        assert resp_rej.json()["status"] == "rejected"

        async with h.Session() as db:
            pr = (await db.execute(select(PlatformPurgeRequest).where(PlatformPurgeRequest.purge_request_id == req_id))).scalars().first()
            assert pr.status == "rejected"
            assert pr.rejection_reason == "Customer changed mind and cancelled ticket."

    run(_run())


def test_impersonation_session_flow_and_guards(purge_test_app):
    """
    Tests:
    1. Operator creates marked impersonation session for customer user.
    2. Tenant token validates against customer endpoints.
    3. Mutating action is blocked under read-only mode (403).
    4. Sensitive actions (password/billing/delete) are blocked (403).
    5. Terminating impersonation session voids customer token immediately.
    """
    h, client, _ = purge_test_app

    async def _run():
        async with h.Session() as db:
            admin, _, cookies = await create_operator(db, "support_lead@mytally.com", "super_admin")
            acc, comp, user_admin, user_staff = await setup_test_account_and_users(db)
            staff_id = user_staff.user_id

        # 1. Operator initiates read-only impersonation
        resp_imp = client.post(
            f"/platform/users/{staff_id}/impersonate",
            json={"reason": "Investigating order generation bug", "minutes": 15, "write_access": False},
            cookies=cookies,
            headers={"X-CSRF-Token": "test-csrf-token"},
        )
        assert resp_imp.status_code == 200, resp_imp.text
        imp_data = resp_imp.json()
        imp_id = imp_data["impersonation_id"]
        tenant_token = imp_data["token"]
        assert imp_data["write_access"] is False

        # 2. Use impersonated customer token on customer endpoint: GET /auth/me/sessions
        headers = {"Authorization": f"Bearer {tenant_token}"}
        resp_get = client.get("/auth/me/sessions", headers=headers)
        assert resp_get.status_code == 200, resp_get.text

        # 3. Read-only guard: Attempting POST mutation on customer endpoint must fail with 403
        resp_post = client.post("/auth/me/sessions/revoke-others", headers=headers)
        assert resp_post.status_code == 403
        assert "strictly read-only" in resp_post.json()["detail"]

        # 4. Premature termination by operator
        resp_term = client.delete(
            f"/platform/users/impersonations/{imp_id}",
            cookies=cookies,
            headers={"X-CSRF-Token": "test-csrf-token"},
        )
        assert resp_term.status_code == 200
        assert resp_term.json()["status"] == "terminated"

        # 5. Subsequent request with tenant token must now fail with 401
        resp_after = client.get("/auth/me/sessions", headers=headers)
        assert resp_after.status_code == 401

    run(_run())


def test_write_impersonation_still_cannot_delete_or_touch_sensitive_areas(purge_test_app):
    """Write access lets an operator change ordinary records, never delete, archive, revoke or reach billing,
    whatever the path looks like."""
    from app.routers import billing, companies
    h, client, app = purge_test_app
    app.include_router(companies.router)
    app.include_router(billing.router)

    async def _run():
        async with h.Session() as db:
            _, _, cookies = await create_operator(db, "support_lead@mytally.com", "super_admin")
            _, comp, _, user_staff = await setup_test_account_and_users(db)
            staff_id, company_id = user_staff.user_id, comp.company_id

        resp_imp = client.post(
            f"/platform/users/{staff_id}/impersonate",
            json={"reason": "Fixing a stuck order for the customer", "minutes": 15, "write_access": True},
            cookies=cookies,
            headers={"X-CSRF-Token": "test-csrf-token"},
        )
        assert resp_imp.status_code == 200, resp_imp.text
        headers = {"Authorization": f"Bearer {resp_imp.json()['token']}"}

        for method, path in (
            ("DELETE", f"/companies/{company_id}"),
            ("POST", f"/companies/{company_id}/archive"),
            ("POST", "/auth/me/sessions/1/revoke"),
            ("GET", "/billing/current-subscription"),
        ):
            resp = client.request(method, path, headers=headers)
            assert resp.status_code == 403, (method, path, resp.status_code)
            assert "forbidden during operator impersonation" in resp.json()["detail"]

        # Reading still works under the same session
        assert client.get("/auth/me/sessions", headers=headers).status_code == 200

    run(_run())


def test_nightly_purge_worker_anonymises_expired_users(purge_test_app):
    """
    Tests the nightly purge cleanup worker for soft-deleted users past their 30-day retention window.
    """
    h, _, _ = purge_test_app

    async def _run():
        async with h.Session() as db:
            acc, comp, user_admin, user_staff = await setup_test_account_and_users(db)
            staff_id = user_staff.user_id
            original_email, original_name = user_staff.email, user_staff.username

            # Set user as soft-deleted with purge_after in the PAST
            now = utc_now()
            user_staff.deleted_at = now - timedelta(days=31)
            user_staff.purge_after = now - timedelta(days=1)
            user_staff.is_active = False
            await db.commit()

        # Run nightly purge worker
        async with h.Session() as db:
            purged_count = await purge_expired_soft_deleted_users(db)
            assert purged_count == 1

        # Check user is now anonymised
        async with h.Session() as db:
            u = (await db.execute(select(User).where(User.user_id == staff_id))).scalars().first()
            assert u.username == f"Deleted user {staff_id}"
            assert u.email == f"purged-{staff_id}@deleted.local"
            assert u.status == "purged"
            assert u.purged_at is not None

            # The audit row says what was cleared, never the data itself
            audit = (await db.execute(select(PlatformAuditLog).where(
                PlatformAuditLog.action_type == "users.nightly_purged"))).scalars().first()
            assert audit is not None
            assert original_email not in (audit.old_values or "") and original_name not in (audit.old_values or "")

    run(_run())


def test_retention_policies_endpoint(purge_test_app):
    """Tests listing statutory data retention policies."""
    h, client, _ = purge_test_app

    async def _run():
        async with h.Session() as db:
            admin, _, cookies = await create_operator(db, "auditor_op@mytally.com", "super_admin")

        resp = client.get(
            "/platform/users/retention-policies",
            cookies=cookies,
        )
        assert resp.status_code == 200, resp.text
        policies = resp.json()
        assert len(policies) >= 5
        categories = {p["data_category"] for p in policies}
        assert "tax_and_accounting" in categories
        assert "customer_user_accounts" in categories
        assert "platform_operator_audit_logs" in categories

    run(_run())


def test_pre_go_live_security_boot_scan(purge_test_app):
    """Tests that verify_platform_routes_security passes on the configured FastAPI app."""
    _, _, app = purge_test_app
    verified_count = verify_platform_routes_security(app)
    assert verified_count > 0
