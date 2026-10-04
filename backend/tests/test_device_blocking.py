"""Blocking a device: it is signed out and can't sign in again as that user until unblocked."""
from sqlalchemy import select

import app.models.portal_core as P
from app.routers import admin as admin_router, auth as auth_router
from tests.conftest import ANDROID_APP, CHROME_WINDOWS, PASSWORD, SYNC_AGENT, bearer, login
from tests.test_device_sessions import me, setup_company


def session_id(h, user, device_id):
    return h.scalar(select(P.UserSession.session_id).where(
        P.UserSession.user_id == user.user_id, P.UserSession.device_id == device_id, P.UserSession.revoked_at.is_(None)))


def test_block_signs_out_and_refuses_that_device_only(harness):
    client = harness.app(auth_router.router, admin_router.router)
    company, admin, field = setup_company(harness)
    other_user = harness.user(company, harness.scalar(select(P.Role).where(P.Role.name == "Sales")), "second_field")
    admin_token = login(client, admin.email, CHROME_WINDOWS)
    phone_token = login(client, field.email, ANDROID_APP)

    blocked = client.post(f"/admin/sessions/{session_id(harness, field, ANDROID_APP['X-Device-Id'])}/block",
                          headers=bearer(admin_token), json={"reason": "Phone reported lost"})
    assert blocked.status_code == 200 and blocked.json()["revoked"] == 1
    after = me(client, phone_token)
    assert after.status_code == 401 and after.headers["X-Auth-Reason"] == "blocked"

    again = client.post("/auth/login", json={"email": field.email, "password": PASSWORD}, headers=ANDROID_APP)
    assert again.status_code == 403 and again.headers["X-Auth-Reason"] == "device_blocked"
    assert "blocked" in again.json()["detail"]

    login(client, field.email, CHROME_WINDOWS)               # same user, other device: allowed
    login(client, other_user.email, ANDROID_APP)             # other user, same device: allowed

    listing = client.get(f"/admin/users/{field.user_id}/blocked-devices", headers=bearer(admin_token)).json()
    assert len(listing) == 1 and listing[0]["device_name"] == "Samsung SM-A515F"
    assert listing[0]["reason"] == "Phone reported lost" and listing[0]["blocked_by"] == admin.username

    sessions = client.get(f"/admin/users/{field.user_id}/sessions?status=all", headers=bearer(admin_token)).json()
    assert any(s["is_blocked"] for s in sessions if s["device_id"] == ANDROID_APP["X-Device-Id"])

    assert client.delete(f"/admin/blocked-devices/{listing[0]['blocked_device_id']}", headers=bearer(admin_token)).status_code == 204
    login(client, field.email, ANDROID_APP)                  # unblocked: allowed again
    actions = [a for (a,) in harness.query(select(P.AuditLog.action))]
    assert "DEVICE_BLOCK" in actions and "DEVICE_UNBLOCK" in actions


def test_wrong_password_from_blocked_device_is_not_told_about_the_block(harness):
    client = harness.app(auth_router.router, admin_router.router)
    _, admin, field = setup_company(harness)
    admin_token = login(client, admin.email, CHROME_WINDOWS)
    login(client, field.email, ANDROID_APP)
    client.post(f"/admin/sessions/{session_id(harness, field, ANDROID_APP['X-Device-Id'])}/block", headers=bearer(admin_token))
    wrong = client.post("/auth/login", json={"email": field.email, "password": "wrong"}, headers=ANDROID_APP)
    assert wrong.status_code == 400 and "X-Auth-Reason" not in wrong.headers


def test_legacy_sessions_cannot_be_blocked_but_can_be_signed_out(harness):
    client = harness.app(auth_router.router, admin_router.router)
    _, admin, field = setup_company(harness)
    admin_token = login(client, admin.email, CHROME_WINDOWS)
    harness.legacy_session(field)
    legacy_id = harness.scalar(select(P.UserSession.session_id).where(P.UserSession.user_id == field.user_id))
    assert client.post(f"/admin/sessions/{legacy_id}/block", headers=bearer(admin_token)).status_code == 409
    assert client.post(f"/admin/sessions/{legacy_id}/revoke", headers=bearer(admin_token)).json() == {"revoked": 1}


def test_admin_cannot_block_the_device_they_are_using(harness):
    client = harness.app(auth_router.router, admin_router.router)
    _, admin, _ = setup_company(harness)
    admin_token = login(client, admin.email, CHROME_WINDOWS)
    own = session_id(harness, admin, CHROME_WINDOWS["X-Device-Id"])
    assert client.post(f"/admin/sessions/{own}/block", headers=bearer(admin_token)).status_code == 400


def test_block_and_unblock_are_company_scoped(harness):
    client = harness.app(auth_router.router, admin_router.router)
    _, admin_a, field_a = setup_company(harness, "Alpha")
    _, admin_b, _ = setup_company(harness, "Beta")
    token_a = login(client, admin_a.email, CHROME_WINDOWS)
    token_b = login(client, admin_b.email, SYNC_AGENT)
    login(client, field_a.email, ANDROID_APP)
    target = session_id(harness, field_a, ANDROID_APP["X-Device-Id"])

    assert client.post(f"/admin/sessions/{target}/block", headers=bearer(token_b)).status_code == 404
    client.post(f"/admin/sessions/{target}/block", headers=bearer(token_a))
    blocked_id = harness.scalar(select(P.BlockedDevice.blocked_device_id))
    assert client.delete(f"/admin/blocked-devices/{blocked_id}", headers=bearer(token_b)).status_code == 404
    assert client.get(f"/admin/users/{field_a.user_id}/blocked-devices", headers=bearer(token_b)).status_code == 404
