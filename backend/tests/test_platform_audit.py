"""
test_platform_audit.py – Comprehensive test suite for Phase 4:
Tamper-Evident Audit Trail, Cryptographic SHA-256 Hash Chaining,
Integrity Verification, Audited Exports with Step-Up MFA, and Safety Net.
"""

import csv
import io
import json
from datetime import datetime, timedelta, timezone
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select, text, update

from app.core.config import settings
from app.core.database import get_db
from app.core.platform_audit import (
    audit_context_var,
    compute_canonical_row_hash,
    verify_platform_audit_chain,
    write_platform_audit_log,
)
from app.core.platform_catalogue import sync_platform_catalogue
from app.core.platform_security import (
    create_platform_access_token,
    hash_password,
    hash_token,
    utc_now,
)
from app.models.platform import (
    PlatformAdmin,
    PlatformAdminRole,
    PlatformAdminSession,
    PlatformAuditLog,
    PlatformPermission,
    PlatformRole,
    PlatformRolePermission,
)
from app.routers import auth, platform_audit, platform_auth, platform_roles
from tests.conftest import Harness, run


@pytest.fixture
def audit_test_app(tmp_path):
    h = Harness(tmp_path)

    app = FastAPI()
    app.include_router(auth.router)
    app.include_router(platform_auth.router)
    app.include_router(platform_roles.router)
    app.include_router(platform_audit.router)

    async def init():
        async with h.Session() as db:
            await sync_platform_catalogue(db)

    run(init())

    async def override_get_db():
        async with h.Session() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    return h, client


async def setup_operator_with_permissions(
    db,
    permissions: list[str],
    prefix: str = "auditor",
    rank: int = 500,
    mfa_fresh: bool = True,
):
    now = utc_now()
    admin = PlatformAdmin(
        email=f"{prefix}_{int(now.timestamp())}@mytally.com",
        password_hash=hash_password("AuditPassword123!"),
        full_name=f"Operator {prefix}",
        status="active",
        permission_version=1,
    )
    db.add(admin)
    await db.flush()

    role = PlatformRole(
        code=f"r_{prefix}_{int(now.timestamp())}",
        name=f"Role {prefix}",
        rank=rank,
        is_system=False,
    )
    db.add(role)
    await db.flush()

    for p_code in permissions:
        perm_res = await db.execute(
            select(PlatformPermission).where(PlatformPermission.code == p_code)
        )
        p = perm_res.scalar_one_or_none()
        if p:
            db.add(PlatformRolePermission(
                role_id=role.role_id,
                permission_id=p.permission_id,
                granted_by=admin.admin_id,
            ))

    db.add(PlatformAdminRole(admin_id=admin.admin_id, role_id=role.role_id))
    await db.flush()

    mfa_time = now if mfa_fresh else (now - timedelta(minutes=15))
    session = PlatformAdminSession(
        admin_id=admin.admin_id,
        family_id=f"fam_{prefix}",
        refresh_hash=hash_token(f"ref_{prefix}"),
        refresh_used=False,
        mfa_at=mfa_time,
        ip_address="127.0.0.1",
        user_agent="AuditTestAgent",
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(hours=8),
    )
    db.add(session)
    await db.commit()
    await db.refresh(admin)
    await db.refresh(session)

    token = create_platform_access_token(
        admin_id=admin.admin_id,
        session_id=session.session_id,
        permission_version=admin.permission_version,
        amr=["pwd", "mfa"] if mfa_fresh else ["pwd"],
    )
    return admin, token, session


def auth_headers(token: str):
    return {
        "Authorization": f"Bearer {token}",
        "X-CSRF-Token": "audit_csrf_test",
    }


# ─────────────────────────────────────────────────────────────────────────────
# 1. TEST AUDIT LOGS LISTING & KEYSET CURSOR PAGINATION
# ─────────────────────────────────────────────────────────────────────────────

def test_audit_logs_listing_and_filtering(audit_test_app):
    """GET /platform/audit-logs supports keyset cursor pagination and multiple filters."""
    h, client = audit_test_app

    async def run_test():
        async with h.Session() as db:
            admin, token, _ = await setup_operator_with_permissions(
                db, ["audit.read", "users.read_pii"], "auditor_list"
            )

            # Write 5 audit entries with various action types
            for i in range(5):
                await write_platform_audit_log(
                    db=db,
                    action_type="users.create" if i < 2 else "users.suspend",
                    admin_email=admin.email,
                    admin_id=admin.admin_id,
                    target_user_id=100 + i,
                    outcome="success" if i != 4 else "failed",
                    reason=f"Test entry {i}",
                )
            await db.commit()

        # 1. Fetch first page with limit=2
        resp = client.get(
            "/platform/audit-logs?limit=2",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["has_more"] is True
        assert data["next_cursor"] is not None
        assert data["total_count"] >= 5

        # 2. Fetch second page using next_cursor
        cursor1 = data["next_cursor"]
        resp2 = client.get(
            f"/platform/audit-logs?limit=2&cursor={cursor1}",
            headers=auth_headers(token),
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert len(data2["items"]) == 2
        assert data2["has_more"] is True
        # Verify pagination moved forward (descending IDs)
        assert data2["items"][0]["audit_id"] < data["items"][1]["audit_id"]

        # 3. Filter by action_type=users.create
        resp_filter = client.get(
            "/platform/audit-logs?action_type=users.create",
            headers=auth_headers(token),
        )
        assert resp_filter.status_code == 200
        items_create = resp_filter.json()["items"]
        assert len(items_create) == 2
        assert all(it["action_type"] == "users.create" for it in items_create)

        # 4. Filter by outcome=failed
        resp_failed = client.get(
            "/platform/audit-logs?outcome=failed",
            headers=auth_headers(token),
        )
        assert resp_failed.status_code == 200
        items_failed = resp_failed.json()["items"]
        assert len(items_failed) == 1
        assert items_failed[0]["outcome"] == "failed"

        # 5. Search filter
        resp_search = client.get(
            "/platform/audit-logs?search=entry 3",
            headers=auth_headers(token),
        )
        assert resp_search.status_code == 200
        search_items = resp_search.json()["items"]
        assert len(search_items) == 1
        assert "entry 3" in search_items[0]["reason"]

    run(run_test())


# ─────────────────────────────────────────────────────────────────────────────
# 2. TEST AUDIT LOG DETAIL & JSON DIFF
# ─────────────────────────────────────────────────────────────────────────────

def test_audit_log_detail_and_diff(audit_test_app):
    """GET /platform/audit-logs/{id} returns complete old/new values diff."""
    h, client = audit_test_app

    async def run_test():
        async with h.Session() as db:
            admin, token, _ = await setup_operator_with_permissions(
                db, ["audit.read", "users.read_pii"], "auditor_detail"
            )

            entry = await write_platform_audit_log(
                db=db,
                action_type="users.update",
                admin_email=admin.email,
                admin_id=admin.admin_id,
                target_user_id=201,
                old_values={"designation": "Staff", "status": "active"},
                new_values={"designation": "Manager", "status": "active"},
                reason="Promotion approved",
            )
            await db.commit()
            audit_id = entry.audit_id

        # 1. Fetch valid entry
        resp = client.get(f"/platform/audit-logs/{audit_id}", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["audit_id"] == audit_id
        assert data["action_type"] == "users.update"
        assert data["old_values"]["designation"] == "Staff"
        assert data["new_values"]["designation"] == "Manager"
        assert data["row_hash"] is not None

        # 2. Non-existent entry returns 404
        resp_404 = client.get("/platform/audit-logs/999999", headers=auth_headers(token))
        assert resp_404.status_code == 404

    run(run_test())


# ─────────────────────────────────────────────────────────────────────────────
# 3. TEST AUDIT CHAIN INTEGRITY & VERIFICATION
# ─────────────────────────────────────────────────────────────────────────────

def test_audit_chain_integrity_verification(audit_test_app):
    """GET /platform/audit-logs/integrity confirms valid cryptographic SHA-256 chain."""
    h, client = audit_test_app

    async def run_test():
        async with h.Session() as db:
            admin, token, _ = await setup_operator_with_permissions(
                db, ["audit.read"], "auditor_intact"
            )

            for i in range(4):
                await write_platform_audit_log(
                    db=db,
                    action_type=f"test.action_{i}",
                    admin_email=admin.email,
                    admin_id=admin.admin_id,
                    target_id=i,
                    reason=f"Chaining test row {i}",
                )
            await db.commit()

        resp = client.get("/platform/audit-logs/integrity", headers=auth_headers(token))
        assert resp.status_code == 200
        report = resp.json()
        assert report["chain_intact"] is True
        assert report["total_verified"] >= 4
        assert report["broken_at_id"] is None
        assert report["error_detail"] is None

    run(run_test())


# ─────────────────────────────────────────────────────────────────────────────
# 4. TEST TAMPERING DETECTION (ROW CONTENT MODIFIED)
# ─────────────────────────────────────────────────────────────────────────────

def test_audit_chain_tampering_detection(audit_test_app):
    """GET /platform/audit-logs/integrity detects direct row tampering."""
    h, client = audit_test_app

    async def run_test():
        async with h.Session() as db:
            admin, token, _ = await setup_operator_with_permissions(
                db, ["audit.read"], "auditor_tamper"
            )

            rows = []
            for i in range(3):
                row = await write_platform_audit_log(
                    db=db,
                    action_type=f"safe.action_{i}",
                    admin_email=admin.email,
                    admin_id=admin.admin_id,
                    target_id=i,
                )
                rows.append(row)
            await db.commit()
            tamper_target_id = rows[1].audit_id

            # Directly tamper with the second row's action_type in database (bypassing API)
            await db.execute(
                update(PlatformAuditLog)
                .where(PlatformAuditLog.audit_id == tamper_target_id)
                .values(action_type="TAMPERED_ACTION_TYPE")
            )
            await db.commit()

        # Chain verification must immediately flag tampering at tamper_target_id!
        resp = client.get("/platform/audit-logs/integrity", headers=auth_headers(token))
        assert resp.status_code == 200
        report = resp.json()
        assert report["chain_intact"] is False
        assert report["broken_at_id"] == tamper_target_id
        assert "Row content tampered" in report["error_detail"]

    run(run_test())


# ─────────────────────────────────────────────────────────────────────────────
# 5. TEST CHAIN CONTINUITY BREAK DETECTION (LINK CORRUPTED / ROW DELETED)
# ─────────────────────────────────────────────────────────────────────────────

def test_audit_chain_broken_link_detection(audit_test_app):
    """GET /platform/audit-logs/integrity catches broken prev_hash links."""
    h, client = audit_test_app

    async def run_test():
        async with h.Session() as db:
            admin, token, _ = await setup_operator_with_permissions(
                db, ["audit.read"], "auditor_break"
            )

            rows = []
            for i in range(3):
                row = await write_platform_audit_log(
                    db=db,
                    action_type=f"chain.action_{i}",
                    admin_email=admin.email,
                    admin_id=admin.admin_id,
                )
                rows.append(row)
            await db.commit()
            broken_id = rows[2].audit_id

            # Corrupt the prev_hash of row 3 to simulate a deleted or inserted intermediary row
            await db.execute(
                update(PlatformAuditLog)
                .where(PlatformAuditLog.audit_id == broken_id)
                .values(prev_hash="0000000000000000000000000000000000000000000000000000000000000000")
            )
            await db.commit()

        resp = client.get("/platform/audit-logs/integrity", headers=auth_headers(token))
        assert resp.status_code == 200
        report = resp.json()
        assert report["chain_intact"] is False
        assert report["broken_at_id"] == broken_id
        assert "Chain link broken" in report["error_detail"]

    run(run_test())


# ─────────────────────────────────────────────────────────────────────────────
# 6. TEST AUDIT EXPORT WITH STEP-UP MFA ENFORCEMENT
# ─────────────────────────────────────────────────────────────────────────────

def test_audit_export_step_up_and_csv_generation(audit_test_app):
    """POST /platform/audit-logs/exports enforces Step-Up MFA and generates streaming CSV."""
    h, client = audit_test_app

    async def run_test():
        async with h.Session() as db:
            # Operator 1: without fresh MFA
            stale_admin, stale_token, _ = await setup_operator_with_permissions(
                db, ["audit.export"], "auditor_stale", mfa_fresh=False
            )
            # Operator 2: with fresh MFA
            fresh_admin, fresh_token, _ = await setup_operator_with_permissions(
                db, ["audit.export", "users.read_pii"], "auditor_fresh", mfa_fresh=True
            )

            for i in range(3):
                await write_platform_audit_log(
                    db=db,
                    action_type=f"export.test_{i}",
                    admin_email=fresh_admin.email,
                    admin_id=fresh_admin.admin_id,
                )
            await db.commit()

        # 1. Operator without fresh MFA -> 401 X-Step-Up: required
        resp_stale = client.post(
            "/platform/audit-logs/exports",
            json={"format": "csv"},
            headers=auth_headers(stale_token),
        )
        assert resp_stale.status_code == 401
        assert resp_stale.headers.get("X-Step-Up") == "required"

        # 2. Operator with fresh MFA -> 200 text/csv
        resp_csv = client.post(
            "/platform/audit-logs/exports",
            json={"format": "csv"},
            headers=auth_headers(fresh_token),
        )
        assert resp_csv.status_code == 200
        assert "text/csv" in resp_csv.headers["content-type"]
        assert "audit_id,occurred_at,admin_email,action_type" in resp_csv.text

        # 3. Export with format=json
        resp_json = client.post(
            "/platform/audit-logs/exports",
            json={"format": "json"},
            headers=auth_headers(fresh_token),
        )
        assert resp_json.status_code == 200
        export_body = resp_json.json()
        assert "total_records" in export_body
        assert "items" in export_body

        # 4. Verify audit.exported record was written to platform_audit_log
        async with h.Session() as db:
            audit_res = await db.execute(
                select(PlatformAuditLog)
                .where(PlatformAuditLog.action_type == "audit.exported")
            )
            audit_row = audit_res.scalars().first()
            assert audit_row is not None
            assert audit_row.admin_id == fresh_admin.admin_id

    run(run_test())


# ─────────────────────────────────────────────────────────────────────────────
# 7. TEST PII MASKING IN AUDIT LOGS
# ─────────────────────────────────────────────────────────────────────────────

def test_audit_pii_masking(audit_test_app):
    """Operators lacking 'users.read_pii' receive masked emails in audit responses."""
    h, client = audit_test_app

    async def run_test():
        async with h.Session() as db:
            # Auditor with audit.read but NO users.read_pii
            auditor, token, _ = await setup_operator_with_permissions(
                db, ["audit.read"], "no_pii_auditor"
            )

            await write_platform_audit_log(
                db=db,
                action_type="auth.login_success",
                admin_email="sensitive.operator@mytally.com",
            )
            await db.commit()

        resp = client.get("/platform/audit-logs", headers=auth_headers(token))
        assert resp.status_code == 200
        items = resp.json()["items"]
        # Find entry
        target = next((it for it in items if it["action_type"] == "auth.login_success"), None)
        assert target is not None
        # Email must be masked
        assert target["admin_email"] != "sensitive.operator@mytally.com"
        assert "•••••" in target["admin_email"]

    run(run_test())


# ─────────────────────────────────────────────────────────────────────────────
# 8. TEST STRICT APPEND-ONLY RESTRICTIONS (NO UPDATE OR DELETE)
# ─────────────────────────────────────────────────────────────────────────────

def test_audit_logs_strict_append_only_guards(audit_test_app):
    """Attempting PUT, PATCH, or DELETE on /platform/audit-logs returns 405 Method Not Allowed."""
    _, client = audit_test_app

    res_put = client.put("/platform/audit-logs/1")
    assert res_put.status_code == 405

    res_patch = client.patch("/platform/audit-logs/1")
    assert res_patch.status_code == 405

    res_del = client.delete("/platform/audit-logs/1")
    assert res_del.status_code == 405


# ─────────────────────────────────────────────────────────────────────────────
# 9. TEST SAFETY-NET LISTENER VIOLATION DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def test_safety_net_catches_unaudited_operator_writes(audit_test_app):
    """Safety-net listener raises RuntimeError if a watched table is modified without an audit row."""
    h, _ = audit_test_app

    async def run_test():
        async with h.Session() as db:
            # Activate operator context artificially
            audit_context_var.set({
                "admin_id": 999,
                "admin_email": "violator@mytally.com",
                "operator_active": True,
            })

            # Attempt to modify a watched entity (PlatformRole) without calling write_platform_audit_log
            role = PlatformRole(code="rogue_role", name="Rogue Role", rank=10)
            db.add(role)

            with pytest.raises(RuntimeError) as exc_info:
                await db.commit()

            assert "Audit safety-net violation" in str(exc_info.value)
            await db.rollback()

            # Clean context
            audit_context_var.set(None)

    run(run_test())
