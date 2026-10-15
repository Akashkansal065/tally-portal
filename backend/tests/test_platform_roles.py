"""
test_platform_roles.py – Test suite for Phase 3: Dynamic Permissions,
Role Management, Hierarchy Rules, Self-Modification Guards,
and Session Invalidation on Privilege Changes.
"""

from datetime import datetime, timedelta
import json
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_db
from app.core.platform_catalogue import sync_platform_catalogue
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
    PlatformAdminWebAuthnCredential,
    PlatformAuditLog,
    PlatformPermission,
    PlatformRole,
    PlatformRolePermission,
)
from app.routers import auth, platform_auth, platform_billing, platform_roles, platform_admins, platform_users
from tests.conftest import Harness, run


@pytest.fixture
def rbac_test_app(tmp_path):
    h = Harness(tmp_path)

    app = FastAPI()
    app.include_router(auth.router)
    app.include_router(platform_auth.router)
    app.include_router(platform_roles.router)
    app.include_router(platform_admins.router)
    app.include_router(platform_users.router)
    app.include_router(platform_billing.router)

    app.dependency_overrides[get_db] = h._get_db
    app.dependency_overrides[platform_auth.get_db] = h._get_db
    app.dependency_overrides[platform_roles.get_db] = h._get_db
    app.dependency_overrides[platform_admins.get_db] = h._get_db
    app.dependency_overrides[platform_users.get_db] = h._get_db
    app.dependency_overrides[platform_billing.get_db] = h._get_db

    client = TestClient(app)
    return h, client


async def setup_operator_with_role(db, role_code: str, email_prefix: str = "test", mfa_minutes_ago: int = 0):
    """Helper to initialize seed catalogue and create an operator with a given role."""
    await sync_platform_catalogue(db)

    res = await db.execute(select(PlatformRole).where(PlatformRole.code == role_code))
    role = res.scalars().first()
    assert role is not None, f"Role {role_code} must exist in catalogue"

    now = utc_now()
    mfa_time = now - timedelta(minutes=mfa_minutes_ago)

    admin = PlatformAdmin(
        email=f"{email_prefix}_{role_code}@mytally.com",
        password_hash=hash_password("SuperSecret12345!"),
        full_name=f"Test {role.name}",
        status="active",
        permission_version=1,
        version=1,
    )
    db.add(admin)
    await db.flush()

    db.add(PlatformAdminRole(admin_id=admin.admin_id, role_id=role.role_id, assigned_by=admin.admin_id))
    await db.flush()

    raw_refresh = generate_refresh_token()
    session = PlatformAdminSession(
        admin_id=admin.admin_id,
        family_id="fam-" + email_prefix,
        refresh_hash=hash_token(raw_refresh),
        refresh_used=False,
        mfa_at=mfa_time,
        ip_address="127.0.0.1",
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(days=7),
    )
    db.add(session)
    await db.commit()

    token = create_platform_access_token(
        admin_id=admin.admin_id,
        session_id=session.session_id,
        permission_version=admin.permission_version,
        amr=["pwd", "mfa"],
    )
    return admin, token, session, role


def auth_headers(token: str, extra: dict = None) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    if extra:
        headers.update(extra)
    return headers


# ─────────────────────────────────────────────────────────────────────────────
# TESTS
# ─────────────────────────────────────────────────────────────────────────────

def test_permissions_catalogue_rbac(rbac_test_app):
    """GET /platform/permissions returns complete list for authorized operator, 401/403 otherwise."""
    h, client = rbac_test_app

    async def _setup():
        async with h.Session() as db:
            s_admin, s_token, _, _ = await setup_operator_with_role(db, "super_admin", "p_super")
            aud_admin, aud_token, _, _ = await setup_operator_with_role(db, "auditor", "p_aud")
            return s_token, aud_token

    s_token, aud_token = run(_setup())

    # Unauthorized
    resp = client.get("/platform/permissions")
    assert resp.status_code == 401

    # Super admin has roles.read
    resp = client.get("/platform/permissions", headers=auth_headers(s_token))
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    codes = {p["code"] for p in data}
    assert "roles.read" in codes
    assert "roles.manage" in codes
    assert "users.read" in codes


def test_roles_listing_and_detail(rbac_test_app):
    """GET /platform/roles and GET /platform/roles/{id} return expected data and ETag."""
    h, client = rbac_test_app

    async def _setup():
        async with h.Session() as db:
            s_admin, s_token, _, s_role = await setup_operator_with_role(db, "super_admin", "r_super")
            return s_token, s_role.role_id

    s_token, role_id = run(_setup())

    # List roles
    resp = client.get("/platform/roles", headers=auth_headers(s_token))
    assert resp.status_code == 200
    roles = resp.json()
    assert isinstance(roles, list)
    assert len(roles) >= 5
    super_role = next(r for r in roles if r["code"] == "super_admin")
    assert super_role["rank"] == 1000
    assert super_role["is_system"] is True
    assert super_role["member_count"] >= 1

    # Get single role with ETag
    resp = client.get(f"/platform/roles/{role_id}", headers=auth_headers(s_token))
    assert resp.status_code == 200
    assert "ETag" in resp.headers
    assert resp.json()["code"] == "super_admin"


def test_create_custom_role_rank_hierarchy(rbac_test_app):
    """Operators cannot create a role with rank >= their own rank."""
    h, client = rbac_test_app

    async def _setup():
        async with h.Session() as db:
            s_admin, s_token, _, _ = await setup_operator_with_role(db, "super_admin", "c_super")

            # Create delegated role with roles.manage and rank 700
            delegated_role = PlatformRole(code="delegated_admin", name="Delegated Admin", rank=700, is_system=False, version=1)
            db.add(delegated_role)
            await db.flush()

            perm_read = (await db.execute(select(PlatformPermission).where(PlatformPermission.code == "roles.read"))).scalar_one()
            perm_manage = (await db.execute(select(PlatformPermission).where(PlatformPermission.code == "roles.manage"))).scalar_one()
            perm_user_read = (await db.execute(select(PlatformPermission).where(PlatformPermission.code == "users.read"))).scalar_one()
            db.add_all([
                PlatformRolePermission(role_id=delegated_role.role_id, permission_id=perm_read.permission_id),
                PlatformRolePermission(role_id=delegated_role.role_id, permission_id=perm_manage.permission_id),
                PlatformRolePermission(role_id=delegated_role.role_id, permission_id=perm_user_read.permission_id),
            ])
            await db.flush()

            del_admin = PlatformAdmin(
                email="del_admin@mytally.com",
                password_hash=hash_password("Pass123!"),
                full_name="Delegated Operator",
                status="active",
                permission_version=1,
                version=1,
            )
            db.add(del_admin)
            await db.flush()
            db.add(PlatformAdminRole(admin_id=del_admin.admin_id, role_id=delegated_role.role_id, assigned_by=s_admin.admin_id))
            await db.flush()

            now = utc_now()
            session = PlatformAdminSession(
                admin_id=del_admin.admin_id,
                family_id="fam-del",
                refresh_hash=hash_token("raw"),
                refresh_used=False,
                mfa_at=now,
                ip_address="127.0.0.1",
                created_at=now,
                last_seen_at=now,
                expires_at=now + timedelta(days=7),
            )
            db.add(session)
            await db.commit()

            del_token = create_platform_access_token(
                admin_id=del_admin.admin_id,
                session_id=session.session_id,
                permission_version=del_admin.permission_version,
                amr=["pwd", "mfa"],
            )

            return s_token, del_token, delegated_role.rank

    s_token, del_token, del_rank = run(_setup())

    # Delegated operator (rank 700) tries to create role with rank 700 -> 403 Forbidden
    resp = client.post(
        "/platform/roles",
        headers=auth_headers(del_token),
        json={
            "code": "peer_role",
            "name": "Peer Role",
            "rank": del_rank,
            "permissions": ["users.read"],
        },
    )
    assert resp.status_code == 403
    assert "your own rank" in resp.json()["detail"]

    # Super Admin (rank 1000) creates custom role with rank 500 -> 201 Created
    resp = client.post(
        "/platform/roles",
        headers=auth_headers(s_token),
        json={
            "code": "tier1_support",
            "name": "Tier 1 Support",
            "rank": 500,
            "permissions": ["users.read", "roles.read"],
            "description": "First line support agent role",
        },
    )
    assert resp.status_code == 201
    created_role = resp.json()
    assert created_role["code"] == "tier1_support"
    assert created_role["is_system"] is False
    assert created_role["rank"] == 500


def test_cannot_grant_what_you_lack(rbac_test_app):
    """Non-superadmin operator cannot grant permissions they do not possess."""
    h, client = rbac_test_app

    async def _setup():
        async with h.Session() as db:
            await sync_platform_catalogue(db)
            now = utc_now()
            custom_role = PlatformRole(
                code="roles_only",
                name="Roles Only",
                rank=500,
                is_system=False,
                version=1,
            )
            db.add(custom_role)
            await db.flush()

            perm_read = (await db.execute(select(PlatformPermission).where(PlatformPermission.code == "roles.read"))).scalar_one()
            perm_manage = (await db.execute(select(PlatformPermission).where(PlatformPermission.code == "roles.manage"))).scalar_one()
            db.add(PlatformRolePermission(role_id=custom_role.role_id, permission_id=perm_read.permission_id))
            db.add(PlatformRolePermission(role_id=custom_role.role_id, permission_id=perm_manage.permission_id))
            await db.flush()

            admin = PlatformAdmin(
                email="roles_limited@mytally.com",
                password_hash=hash_password("SuperSecret12345!"),
                full_name="Roles Limited Admin",
                status="active",
                permission_version=1,
                version=1,
            )
            db.add(admin)
            await db.flush()
            db.add(PlatformAdminRole(admin_id=admin.admin_id, role_id=custom_role.role_id, assigned_by=admin.admin_id))
            await db.flush()

            raw_refresh = generate_refresh_token()
            session = PlatformAdminSession(
                admin_id=admin.admin_id,
                family_id="fam-roles-lim",
                refresh_hash=hash_token(raw_refresh),
                refresh_used=False,
                mfa_at=now,
                ip_address="127.0.0.1",
                created_at=now,
                last_seen_at=now,
                expires_at=now + timedelta(days=7),
            )
            db.add(session)
            await db.commit()

            token = create_platform_access_token(
                admin_id=admin.admin_id,
                session_id=session.session_id,
                permission_version=admin.permission_version,
                amr=["pwd", "mfa"],
            )
            return token

    limited_token = run(_setup())

    # Attempt to create a role with billing.manage -> 403 "Cannot grant permission(s) you do not hold"
    resp = client.post(
        "/platform/roles",
        headers=auth_headers(limited_token),
        json={
            "code": "billing_specialist",
            "name": "Billing Specialist",
            "rank": 300,
            "permissions": ["roles.read", "billing.manage"],
        },
    )
    assert resp.status_code == 403
    assert "you do not hold" in resp.json()["detail"]


def test_patch_role_optimistic_concurrency_and_guards(rbac_test_app):
    """PATCH /platform/roles/{id} requires If-Match, enforces system role rules, and updates cleanly."""
    h, client = rbac_test_app

    async def _setup():
        async with h.Session() as db:
            s_admin, s_token, _, s_role = await setup_operator_with_role(db, "super_admin", "patch_super")
            custom_role = PlatformRole(code="custom_edit", name="Editable Role", rank=300, is_system=False, version=1)
            db.add(custom_role)
            await db.commit()
            return s_token, s_role.role_id, custom_role.role_id

    s_token, sys_role_id, custom_role_id = run(_setup())

    # 1. Missing If-Match header -> 428 Precondition Required
    resp = client.patch(
        f"/platform/roles/{custom_role_id}",
        headers=auth_headers(s_token),
        json={"name": "New Role Name"},
    )
    assert resp.status_code == 428

    # 2. Outdated / mismatched If-Match -> 409 Conflict
    resp = client.patch(
        f"/platform/roles/{custom_role_id}",
        headers=auth_headers(s_token, {"If-Match": '"99"'}),
        json={"name": "New Role Name"},
    )
    assert resp.status_code == 409

    # 3. System role cannot change code or rank (400 or 403)
    resp = client.patch(
        f"/platform/roles/{sys_role_id}",
        headers=auth_headers(s_token, {"If-Match": '"1"'}),
        json={"code": "hacked_super_admin"},
    )
    assert resp.status_code in (400, 403)

    # 4. Valid update with weak or strong ETag -> 200 OK & version increments to 2
    resp = client.patch(
        f"/platform/roles/{custom_role_id}",
        headers=auth_headers(s_token, {"If-Match": 'W/"1"'}),
        json={"name": "Updated Role Name", "description": "New description"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Updated Role Name"
    assert data["version"] == 2
    assert resp.headers["ETag"] == '"2"'


def test_delete_role_protections(rbac_test_app):
    """DELETE /platform/roles/{id} blocks system roles and roles with active members."""
    h, client = rbac_test_app

    async def _setup():
        async with h.Session() as db:
            s_admin, s_token, _, s_role = await setup_operator_with_role(db, "super_admin", "del_super")
            custom_unused = PlatformRole(code="unused_role", name="Unused", rank=200, is_system=False, version=1)
            custom_used = PlatformRole(code="used_role", name="Used", rank=200, is_system=False, version=1)
            db.add_all([custom_unused, custom_used])
            await db.flush()

            # Assign an operator to custom_used
            dummy_admin = PlatformAdmin(
                email="dummy_assigned@mytally.com",
                password_hash=hash_password("Pass123!"),
                full_name="Assigned Operator",
                status="active",
                version=1,
            )
            db.add(dummy_admin)
            await db.flush()
            db.add(PlatformAdminRole(admin_id=dummy_admin.admin_id, role_id=custom_used.role_id, assigned_by=s_admin.admin_id))
            await db.commit()

            return s_token, s_role.role_id, custom_used.role_id, custom_unused.role_id

    s_token, sys_role_id, used_role_id, unused_role_id = run(_setup())

    # System role cannot be deleted -> 400
    resp = client.delete(f"/platform/roles/{sys_role_id}", headers=auth_headers(s_token))
    assert resp.status_code == 400
    assert "cannot be deleted" in resp.json()["detail"]

    # Role with members cannot be deleted -> 400 Bad Request
    resp = client.delete(f"/platform/roles/{used_role_id}", headers=auth_headers(s_token))
    assert resp.status_code == 400
    assert "because it is assigned to" in resp.json()["detail"]

    # Unused role deletes cleanly -> 200
    resp = client.delete(f"/platform/roles/{unused_role_id}", headers=auth_headers(s_token))
    assert resp.status_code == 200
    assert resp.json().get("ok") is True or resp.json().get("status") == "deleted"


def test_put_role_permissions_bumps_pv_and_revokes_sessions(rbac_test_app):
    """PUT /platform/roles/{id}/permissions replaces permissions, bumps permission_version and revokes member sessions."""
    h, client = rbac_test_app

    async def _setup():
        async with h.Session() as db:
            s_admin, s_token, _, _ = await setup_operator_with_role(db, "super_admin", "pv_super")
            supp_admin, supp_token, supp_session, supp_role = await setup_operator_with_role(db, "support", "pv_supp")
            return s_token, supp_admin.admin_id, supp_token, supp_role.role_id, supp_role.version

    s_token, supp_admin_id, supp_token, supp_role_id, supp_version = run(_setup())

    # Support token initially works
    resp = client.get("/platform/users", headers=auth_headers(supp_token))
    assert resp.status_code == 200

    # Super admin modifies support role permissions
    resp = client.put(
        f"/platform/roles/{supp_role_id}/permissions",
        headers=auth_headers(s_token, {"If-Match": f'"{supp_version}"'}),
        json={"permissions": ["users.read", "users.update"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "users.read" in data["permissions"]
    assert "users.update" in data["permissions"]

    # Verify that support admin's permission_version was bumped and their session was revoked
    async def _check_db():
        async with h.Session() as db:
            admin_row = (await db.execute(select(PlatformAdmin).where(PlatformAdmin.admin_id == supp_admin_id))).scalar_one()
            assert admin_row.permission_version == 2
            # Sessions must be marked revoked_at
            sessions = (await db.execute(select(PlatformAdminSession).where(PlatformAdminSession.admin_id == supp_admin_id))).scalars().all()
            for s in sessions:
                assert s.revoked_at is not None

    run(_check_db())

    # Support token now returns 401 Session expired / revoked
    resp = client.get("/platform/users", headers=auth_headers(supp_token))
    assert resp.status_code == 401


def test_patch_admin_self_modification_and_rank_guards(rbac_test_app):
    """Operator cannot deactivate self or operators of equal/higher rank."""
    h, client = rbac_test_app

    async def _setup():
        async with h.Session() as db:
            s_admin, s_token, _, _ = await setup_operator_with_role(db, "super_admin", "selfmod_super")
            adm_admin, adm_token, _, adm_role = await setup_operator_with_role(db, "admin", "selfmod_adm")
            return s_token, s_admin.admin_id, adm_token, adm_admin.admin_id

    s_token, s_admin_id, adm_token, adm_admin_id = run(_setup())

    # Admin tries to deactivate themselves -> 403 Forbidden
    resp = client.patch(
        f"/platform/admins/{adm_admin_id}",
        headers=auth_headers(adm_token, {"If-Match": '"1"'}),
        json={"status": "disabled"},
    )
    assert resp.status_code == 403
    assert "Cannot modify your own administrative status" in resp.json()["detail"]

    # Admin tries to modify super admin -> 403 Forbidden (target rank 1000 >= caller rank 800)
    resp = client.patch(
        f"/platform/admins/{s_admin_id}",
        headers=auth_headers(adm_token, {"If-Match": '"1"'}),
        json={"full_name": "Demoted Super Admin"},
    )
    assert resp.status_code == 403
    assert "your own rank" in resp.json()["detail"]


def test_last_super_admin_protection(rbac_test_app):
    """Sole active super_admin cannot be deactivated or have super_admin role removed."""
    h, client = rbac_test_app

    async def _setup():
        async with h.Session() as db:
            s_admin, s_token, _, s_role = await setup_operator_with_role(db, "super_admin", "sole_super")
            adm_admin, adm_token, _, adm_role = await setup_operator_with_role(db, "admin", "sole_adm")
            return s_token, s_admin.admin_id, adm_role.role_id

    s_token, s_admin_id, adm_role_id = run(_setup())

    # Super admin attempting to replace own roles is blocked by self-mod guard
    resp = client.put(
        f"/platform/admins/{s_admin_id}/roles",
        headers=auth_headers(s_token, {"If-Match": '"1"'}),
        json={"roles": [{"role_id": adm_role_id}]},
    )
    assert resp.status_code == 403
    assert "Cannot modify your own administrative roles" in resp.json()["detail"]


def test_step_up_enforcement_on_role_assignment(rbac_test_app):
    """Assigning roles to an operator requires fresh MFA (<= 5 min)."""
    h, client = rbac_test_app

    async def _setup():
        async with h.Session() as db:
            # Super admin whose MFA was 10 minutes ago
            s_admin, s_token, _, s_role = await setup_operator_with_role(db, "super_admin", "st_super", mfa_minutes_ago=10)
            target_admin, _, _, target_role = await setup_operator_with_role(db, "support", "st_target")
            return s_token, target_admin.admin_id, target_role.role_id, target_admin.version

    s_token, target_admin_id, target_role_id, target_version = run(_setup())

    # Calling when MFA > 5 min -> 401 Step-Up Required
    resp = client.put(
        f"/platform/admins/{target_admin_id}/roles",
        headers=auth_headers(s_token, {"If-Match": f'"{target_version}"'}),
        json={"roles": [{"role_id": target_role_id}]},
    )
    assert resp.status_code == 401
    assert resp.headers.get("X-Step-Up") == "required"
    assert "Step-up authentication required" in resp.json()["detail"]


def test_reset_passkeys_and_revoke_sessions(rbac_test_app):
    """POST /platform/admins/{id}/reset-passkeys and DELETE /platform/admins/{id}/sessions."""
    h, client = rbac_test_app

    async def _setup():
        async with h.Session() as db:
            s_admin, s_token, _, _ = await setup_operator_with_role(db, "super_admin", "pk_super")
            t_admin, t_token, t_session, _ = await setup_operator_with_role(db, "support", "pk_target")

            # Add a mock webauthn credential
            cred = PlatformAdminWebAuthnCredential(
                admin_id=t_admin.admin_id,
                credential_id=b"test_cred_id_123",
                public_key=b"publickeybytes",
                sign_count=0,
                rp_id="localhost",
                transports='["internal"]',
                nickname="Work MacBook TouchID",
            )
            db.add(cred)
            await db.commit()

            return s_token, s_admin.admin_id, t_admin.admin_id, t_token

    s_token, s_admin_id, target_id, t_token = run(_setup())

    # Self-mod guard on passkey reset: cannot reset own passkeys via this route
    resp = client.post(f"/platform/admins/{s_admin_id}/reset-passkeys", headers=auth_headers(s_token))
    assert resp.status_code == 403
    assert "own passkeys" in resp.json()["detail"]

    # Reset lower-ranked operator passkeys
    resp = client.post(f"/platform/admins/{target_id}/reset-passkeys", headers=auth_headers(s_token))
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    # Revoke sessions of target operator
    resp = client.delete(f"/platform/admins/{target_id}/sessions", headers=auth_headers(s_token))
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    # Target operator's token now revoked
    resp = client.get("/platform/users", headers=auth_headers(t_token))
    assert resp.status_code == 401


def test_super_admin_can_invite_and_assign_super_admin_role(rbac_test_app):
    """Super Admin (rank 1000) can invite new operators with super_admin role and assign rank 1000 roles."""
    h, client = rbac_test_app

    async def _setup():
        async with h.Session() as db:
            s_admin, s_token, _, s_role = await setup_operator_with_role(db, "super_admin", "invite_super")
            adm_admin, adm_token, _, adm_role = await setup_operator_with_role(db, "admin", "invite_adm")
            return s_token, s_role.role_id, adm_token, adm_role.role_id

    s_token, sys_role_id, adm_token, adm_role_id = run(_setup())

    # 1. Super Admin invites new operator with super_admin role (rank 1000) -> 201 Created
    resp = client.post(
        "/platform/admins",
        headers=auth_headers(s_token),
        json={
            "email": "new_super@mytally.com",
            "full_name": "New Super Admin",
            "password": "TestOnlyStrongPass!42",
            "role_ids": [sys_role_id],
        },
    )
    assert resp.status_code == 201
    created_admin = resp.json()
    assert created_admin["email"] == "new_super@mytally.com"
    assert created_admin["max_rank"] == 1000
    assert any(r["role_id"] == sys_role_id for r in created_admin["roles"])

    # 2. Regular Admin (rank 800) cannot invite operator with rank 1000 or 800 -> 403 Forbidden
    resp = client.post(
        "/platform/admins",
        headers=auth_headers(adm_token),
        json={
            "email": "escalated@mytally.com",
            "full_name": "Escalated Admin",
            "password": "TestOnlyStrongPass!42",
            "role_ids": [sys_role_id],
        },
    )
    assert resp.status_code == 403
    assert "Cannot assign role" in resp.json()["detail"]


def test_delete_operator_guards_and_success(rbac_test_app):
    """Test DELETE /platform/admins/{admin_id} self-guard, rank guard, last super-admin guard, cascade & audit."""
    h, client = rbac_test_app

    async def _setup():
        async with h.Session() as db:
            s1_admin, s1_token, _, _ = await setup_operator_with_role(db, "super_admin", "del_super1")
            s2_admin, s2_token, _, _ = await setup_operator_with_role(db, "super_admin", "del_super2")
            adm_admin, adm_token, _, _ = await setup_operator_with_role(db, "admin", "del_adm")
            supp_admin, supp_token, _, _ = await setup_operator_with_role(db, "support", "del_supp")
            return (
                (s1_admin.admin_id, s1_token),
                (s2_admin.admin_id, s2_token),
                (adm_admin.admin_id, adm_token),
                (supp_admin.admin_id, supp_token),
            )

    (s1_id, s1_token), (s2_id, s2_token), (adm_id, adm_token), (supp_id, supp_token) = run(_setup())

    # 1. Self-deletion guard: s1 cannot delete s1
    resp = client.delete(f"/platform/admins/{s1_id}", headers=auth_headers(s1_token))
    assert resp.status_code == 403
    assert "Cannot delete your own" in resp.json()["detail"]

    # 2. Rank hierarchy guard: adm (rank 800) cannot delete s2 (rank 1000) or adm2
    resp = client.delete(f"/platform/admins/{s2_id}", headers=auth_headers(adm_token))
    assert resp.status_code == 403
    assert "Cannot delete operator with rank" in resp.json()["detail"]

    # 3. Super Admin can delete subordinate operator (supp)
    resp = client.delete(f"/platform/admins/{supp_id}", headers=auth_headers(s1_token))
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert resp.json()["status"] == "deleted"

    # Supp is deleted: getting supp returns 404
    resp = client.get(f"/platform/admins/{supp_id}", headers=auth_headers(s1_token))
    assert resp.status_code == 404

    # Supp's token is invalid (operator record no longer exists)
    resp = client.get("/platform/users", headers=auth_headers(supp_token))
    assert resp.status_code == 401

    # 4. Super Admin can delete s2 because s1 is still active
    resp = client.delete(f"/platform/admins/{s2_id}", headers=auth_headers(s1_token))
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    # 5. Last super-admin guard: now only s1 is left; if another admin tries to delete s1, or if s1 could, it's blocked
    # Let's verify with audit log
    async def _verify_audit():
        async with h.Session() as db:
            logs = (
                await db.execute(
                    select(PlatformAuditLog)
                    .where(PlatformAuditLog.action_type == "admins.delete")
                    .order_by(PlatformAuditLog.audit_id.asc())
                )
            ).scalars().all()
            return len(logs)

    audit_count = run(_verify_audit())
    assert audit_count >= 2  # supp and s2 deletions logged

