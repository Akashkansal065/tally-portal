"""Device-aware sessions: capture at login, admin and self-service sign-out, activity, scoping, audit."""
from datetime import timedelta

from sqlalchemy import select, update

import app.models.portal_core as P
from app.core.permissions import clear_all_auth_and_permission_caches
from app.core.sessions import utcnow
from app.routers import admin as admin_router, auth as auth_router
from tests.conftest import ANDROID_APP, CHROME_WINDOWS, SYNC_AGENT, bearer, login


def setup_company(h, name="Alpha"):
    company = h.company(name)
    admin_role = h.scalar(select(P.Role).where(P.Role.name == "Admin")) or h.role("Admin")
    sales_role = h.scalar(select(P.Role).where(P.Role.name == "Sales")) or h.role("Sales")
    admin = h.user(company, admin_role, f"admin_{name.lower()}")
    field = h.user(company, sales_role, f"field_{name.lower()}")
    return company, admin, field


def me(client, token):
    return client.get("/auth/me/sessions", headers=bearer(token))


def test_login_records_device_details(harness):
    client = harness.app(auth_router.router)
    _, _, field = setup_company(harness)
    login(client, field.email, ANDROID_APP)
    login(client, field.email, CHROME_WINDOWS)

    rows = {s.client_type: s for (s,) in harness.query(select(P.UserSession).where(P.UserSession.user_id == field.user_id))}
    android, web = rows["android"], rows["web"]
    assert (android.device_id, android.device_name, android.device_type, android.os_name, android.browser_name, android.app_version) == \
        ("android-7f3e9b2c4d5a6e10", "Samsung SM-A515F", "mobile", "Android 14", "Chrome WebView 129", "1.0")
    assert (web.device_name, web.device_type, web.os_name, web.browser_name) == ("Chrome on Windows", "desktop", "Windows", "Chrome 129")
    assert web.ip_address and web.user_agent.startswith("Mozilla/5.0") and web.last_active_at is not None


def test_login_without_device_headers_still_works(harness):
    client = harness.app(auth_router.router)
    _, _, field = setup_company(harness)
    token = login(client, field.email)
    session = harness.scalar(select(P.UserSession).where(P.UserSession.user_id == field.user_id))
    assert session.client_type == "api" and session.device_id is None
    assert client.get("/auth/me/sessions", headers=bearer(token)).status_code == 200


def test_same_device_login_replaces_previous_session(harness):
    client = harness.app(auth_router.router)
    _, _, field = setup_company(harness)
    first = login(client, field.email, ANDROID_APP)
    second = login(client, field.email, ANDROID_APP)

    live = harness.query(select(P.UserSession).where(P.UserSession.user_id == field.user_id, P.UserSession.revoked_at.is_(None)))
    assert len(live) == 1
    old = me(client, first)
    assert old.status_code == 401 and old.headers["X-Auth-Reason"] == "replaced"
    assert me(client, second).status_code == 200


def test_admin_revoke_is_immediate_and_revoke_all_signs_out_everything(harness):
    """Device A (Android) and device B (Chrome): revoke A -> A is 401 even with a warm cache, B still works;
    revoke-all -> B is 401 too."""
    client = harness.app(auth_router.router, admin_router.router)
    _, admin, field = setup_company(harness)
    admin_token = login(client, admin.email, CHROME_WINDOWS)
    token_a = login(client, field.email, ANDROID_APP)
    token_b = login(client, field.email, {**CHROME_WINDOWS, "X-Device-Id": "web-field-browser-0002"})
    assert me(client, token_a).status_code == 200 and me(client, token_b).status_code == 200  # warm the auth cache

    listing = client.get(f"/admin/users/{field.user_id}/sessions", headers=bearer(admin_token))
    assert listing.status_code == 200
    devices = {s["client_type"]: s for s in listing.json()}
    assert set(devices) == {"android", "web"}
    assert devices["android"]["device_name"] == "Samsung SM-A515F" and devices["android"]["is_active_now"] is True

    revoke = client.post(f"/admin/sessions/{devices['android']['session_id']}/revoke", headers=bearer(admin_token))
    assert revoke.json() == {"revoked": 1}
    a = me(client, token_a)
    assert a.status_code == 401 and a.headers["X-Auth-Reason"] == "admin_revoke"
    assert me(client, token_b).status_code == 200

    revoke_all = client.post(f"/admin/users/{field.user_id}/sessions/revoke-all", headers=bearer(admin_token))
    assert revoke_all.json() == {"revoked": 1}
    b = me(client, token_b)
    assert b.status_code == 401 and b.headers["X-Auth-Reason"] == "admin_revoke_all"

    revoked = harness.query(select(P.UserSession.revoke_reason, P.UserSession.revoked_by_user_id)
                            .where(P.UserSession.user_id == field.user_id))
    assert set(revoked) == {("admin_revoke", admin.user_id), ("admin_revoke_all", admin.user_id)}
    actions = {a for (a,) in harness.query(select(P.AuditLog.action))}
    assert {"SESSION_REVOKE", "SESSION_REVOKE_ALL"} <= actions


def test_admin_revoke_all_on_self_keeps_current_session(harness):
    client = harness.app(auth_router.router, admin_router.router)
    _, admin, _ = setup_company(harness)
    current = login(client, admin.email, CHROME_WINDOWS)
    other = login(client, admin.email, ANDROID_APP)
    result = client.post(f"/admin/users/{admin.user_id}/sessions/revoke-all", headers=bearer(current), json={"keep_current": True})
    assert result.json() == {"revoked": 1}
    assert me(client, current).status_code == 200 and me(client, other).status_code == 401


def test_admins_only_reach_their_own_company(harness):
    client = harness.app(auth_router.router, admin_router.router)
    _, _, field_a = setup_company(harness, "Alpha")
    _, admin_b, field_b = setup_company(harness, "Beta")
    login(client, field_a.email, ANDROID_APP)
    login(client, field_b.email, CHROME_WINDOWS)
    token_b = login(client, admin_b.email, SYNC_AGENT)
    session_a = harness.scalar(select(P.UserSession.session_id).where(P.UserSession.user_id == field_a.user_id))

    assert client.get(f"/admin/users/{field_a.user_id}/sessions", headers=bearer(token_b)).status_code == 404
    assert client.post(f"/admin/sessions/{session_a}/revoke", headers=bearer(token_b)).status_code == 404
    assert client.post(f"/admin/users/{field_a.user_id}/sessions/revoke-all", headers=bearer(token_b)).status_code == 404
    company_wide = client.get("/admin/sessions", headers=bearer(token_b)).json()
    assert {s["username"] for s in company_wide["sessions"]} == {"field_beta", "admin_beta"}


def test_my_devices_self_service(harness):
    client = harness.app(auth_router.router)
    _, _, field = setup_company(harness)
    phone = login(client, field.email, ANDROID_APP)
    laptop = login(client, field.email, CHROME_WINDOWS)
    tablet = login(client, field.email, {**ANDROID_APP, "X-Device-Id": "android-tablet-000099", "X-Device-Type": "tablet"})

    listing = me(client, laptop).json()
    assert len(listing) == 3 and listing[0]["is_current"] is True and listing[0]["client_type"] == "web"

    phone_id = next(s["session_id"] for s in listing if s["device_id"] == ANDROID_APP["X-Device-Id"])
    assert client.post(f"/auth/me/sessions/{phone_id}/revoke", headers=bearer(laptop)).json()["revoked"] == 1
    assert me(client, phone).headers["X-Auth-Reason"] == "self_revoke"

    assert client.post("/auth/me/sessions/revoke-others", headers=bearer(laptop)).json() == {"revoked": 1}
    assert me(client, tablet).status_code == 401 and me(client, laptop).status_code == 200


def test_users_cannot_revoke_other_users_sessions(harness):
    client = harness.app(auth_router.router)
    company, admin, field = setup_company(harness)
    admin_token = login(client, admin.email, CHROME_WINDOWS)
    field_token = login(client, field.email, ANDROID_APP)
    admin_session = harness.scalar(select(P.UserSession.session_id).where(P.UserSession.user_id == admin.user_id))
    assert client.post(f"/auth/me/sessions/{admin_session}/revoke", headers=bearer(field_token)).status_code == 404
    assert me(client, admin_token).status_code == 200


def test_logout_revokes_with_reason(harness):
    client = harness.app(auth_router.router)
    _, _, field = setup_company(harness)
    token = login(client, field.email, CHROME_WINDOWS)
    assert client.post("/auth/logout", headers=bearer(token)).status_code == 200
    after = me(client, token)
    assert after.status_code == 401 and after.headers["X-Auth-Reason"] == "logout"


def test_password_reset_and_deactivation_explain_the_sign_out(harness):
    client = harness.app(auth_router.router, admin_router.router)
    _, admin, field = setup_company(harness)
    admin_token = login(client, admin.email, CHROME_WINDOWS)
    token = login(client, field.email, ANDROID_APP)
    assert client.put(f"/admin/users/{field.user_id}/reset-password", headers=bearer(admin_token), json={"password": "new-pass-123"}).status_code == 200
    assert me(client, token).headers["X-Auth-Reason"] == "password_change"

    harness.execute(update(P.User).where(P.User.user_id == field.user_id).values(password_hash=admin_router.get_password_hash("pw-123456")))
    token = login(client, field.email, ANDROID_APP)
    assert client.put(f"/admin/users/{field.user_id}", headers=bearer(admin_token), json={"is_active": False}).status_code == 200
    assert me(client, token).headers["X-Auth-Reason"] == "deactivated"


def test_last_active_is_tracked_but_throttled(harness):
    client = harness.app(auth_router.router)
    _, _, field = setup_company(harness)
    token = login(client, field.email, ANDROID_APP)
    long_ago = utcnow() - timedelta(hours=2)
    harness.execute(update(P.UserSession).values(last_active_at=long_ago))
    clear_all_auth_and_permission_caches()

    me(client, token)  # cache miss: writes activity
    first = harness.scalar(select(P.UserSession.last_active_at))
    assert first > long_ago + timedelta(hours=1)

    marker = utcnow() - timedelta(minutes=1)
    harness.execute(update(P.UserSession).values(last_active_at=marker))
    me(client, token)  # cache hit within 5 minutes: no write
    assert harness.scalar(select(P.UserSession.last_active_at)) == marker


def test_user_list_counts_devices_and_older_sessions(harness):
    client = harness.app(auth_router.router, admin_router.router)
    _, admin, field = setup_company(harness)
    admin_token = login(client, admin.email, CHROME_WINDOWS)
    login(client, field.email, ANDROID_APP)
    login(client, field.email, CHROME_WINDOWS)
    harness.legacy_session(field)
    harness.legacy_session(field)

    users = {u["username"]: u for u in client.get("/admin/users", headers=bearer(admin_token)).json()}
    assert users["field_alpha"]["active_devices"] == 2
    assert users["field_alpha"]["older_sessions"] == 2
    assert users["field_alpha"]["last_active_at"] is not None


def test_company_sessions_summary_and_filters(harness):
    client = harness.app(auth_router.router, admin_router.router)
    _, admin, field = setup_company(harness)
    admin_token = login(client, admin.email, CHROME_WINDOWS)
    login(client, field.email, ANDROID_APP)
    login(client, admin.email, SYNC_AGENT)
    harness.legacy_session(field)

    body = client.get("/admin/sessions", headers=bearer(admin_token)).json()
    assert body["summary"] == {"total": 3, "active_now": 3, "mobile": 1, "tablet": 0, "desktop": 1,
                               "sync_agent": 1, "older_sessions": 1}
    assert len(body["sessions"]) == 3 and not any(s["legacy"] for s in body["sessions"])

    with_older = client.get("/admin/sessions?include_older=true", headers=bearer(admin_token)).json()["sessions"]
    assert len(with_older) == 4 and any(s["legacy"] and s["device_name"] == "Unknown device" for s in with_older)

    assert [s["client_type"] for s in client.get("/admin/sessions?device_type=mobile", headers=bearer(admin_token)).json()["sessions"]] == ["android"]
    assert [s["client_type"] for s in client.get("/admin/sessions?client_type=sync-agent", headers=bearer(admin_token)).json()["sessions"]] == ["sync-agent"]
    found = client.get("/admin/sessions?q=samsung", headers=bearer(admin_token)).json()["sessions"]
    assert [s["device_name"] for s in found] == ["Samsung SM-A515F"]
    current = [s for s in body["sessions"] if s["is_current"]]
    assert len(current) == 1 and current[0]["client_type"] == "web"
