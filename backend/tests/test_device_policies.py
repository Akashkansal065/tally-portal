"""Role device limits, new-device alerts and the session cleanup job."""
from datetime import timedelta

from sqlalchemy import select, update

import app.models.portal_core as P
from app.core.config import settings
from app.core.datetime_utils import get_ist_now
from app.routers import admin as admin_router, auth as auth_router
from app.services.daily_cleanup import purge_old_sessions
from tests.conftest import ANDROID_APP, CHROME_WINDOWS, PASSWORD, bearer, login, run
from tests.test_device_sessions import me, setup_company

PHONE_2 = {**ANDROID_APP, "X-Device-Id": "android-replacement-phone-02", "X-Device-Name": "Redmi Note 13"}


def limit_sales_role(h, limit):
    h.execute(update(P.Role).where(P.Role.name == "Sales").values(max_active_devices=limit))


def test_device_limit_signs_out_the_least_recently_used_device(harness):
    client = harness.app(auth_router.router)
    _, _, field = setup_company(harness)
    limit_sales_role(harness, 1)
    harness.legacy_session(field)                      # unused pre-tracking session goes first
    old_phone = login(client, field.email, ANDROID_APP)
    new_phone = login(client, field.email, PHONE_2)

    gone = me(client, old_phone)
    assert gone.status_code == 401 and gone.headers["X-Auth-Reason"] == "device_limit"
    assert me(client, new_phone).status_code == 200
    live = harness.query(select(P.UserSession.session_id).where(
        P.UserSession.user_id == field.user_id, P.UserSession.revoked_at.is_(None)))
    assert len(live) == 1


def test_device_limit_refuse_policy(harness, monkeypatch):
    monkeypatch.setattr(settings, "DEVICE_LIMIT_POLICY", "refuse")
    client = harness.app(auth_router.router)
    _, _, field = setup_company(harness)
    limit_sales_role(harness, 1)
    harness.legacy_session(field)                      # stale sessions never count against the limit
    login(client, field.email, ANDROID_APP)
    refused = client.post("/auth/login", json={"email": field.email, "password": PASSWORD}, headers=PHONE_2)
    assert refused.status_code == 403 and refused.headers["X-Auth-Reason"] == "device_limit"
    login(client, field.email, ANDROID_APP)            # the same device may always sign in again


def test_role_device_limit_is_editable(harness):
    client = harness.app(auth_router.router, admin_router.router)
    _, admin, _ = setup_company(harness)
    token = login(client, admin.email, CHROME_WINDOWS)
    sales_id = harness.scalar(select(P.Role.role_id).where(P.Role.name == "Sales"))
    assert client.put(f"/admin/roles/{sales_id}", headers=bearer(token), json={"max_active_devices": 2}).json()["max_active_devices"] == 2
    roles = {r["name"]: r for r in client.get("/admin/roles", headers=bearer(token)).json()}
    assert roles["Sales"]["max_active_devices"] == 2
    assert client.put(f"/admin/roles/{sales_id}", headers=bearer(token), json={"description": "Field"}).json()["max_active_devices"] == 2
    assert client.put(f"/admin/roles/{sales_id}", headers=bearer(token), json={"max_active_devices": 0}).json()["max_active_devices"] is None
    assert client.put(f"/admin/roles/{sales_id}", headers=bearer(token), json={"max_active_devices": -1}).status_code == 422


def test_new_device_alert_goes_to_admins_only_for_genuinely_new_devices(harness):
    client = harness.app(auth_router.router)
    _, admin, field = setup_company(harness)
    alerts = lambda: harness.query(select(P.Notification.user_id, P.Notification.message).where(P.Notification.type == "security"))

    login(client, field.email, ANDROID_APP)            # first tracked login: nothing to compare against
    assert alerts() == []
    login(client, field.email, ANDROID_APP)            # known device
    assert alerts() == []
    login(client, field.email, CHROME_WINDOWS)         # new device
    sent = alerts()
    assert len(sent) == 1 and sent[0][0] == admin.user_id and "Chrome on Windows" in sent[0][1]

    login(client, admin.email, ANDROID_APP)            # admins' own logins don't alert
    login(client, admin.email, CHROME_WINDOWS)
    assert len(alerts()) == 1


def test_cleanup_purges_only_old_sessions(harness):
    client = harness.app(auth_router.router)
    _, _, field = setup_company(harness)
    for _ in range(4):
        login(client, field.email, {**ANDROID_APP, "X-Device-Id": f"android-device-{_:010d}"})
    ids = [i for (i,) in harness.query(select(P.UserSession.session_id).order_by(P.UserSession.session_id))]
    now = get_ist_now()
    harness.execute(update(P.UserSession).where(P.UserSession.session_id == ids[0]).values(expires_at=now - timedelta(days=31)))
    harness.execute(update(P.UserSession).where(P.UserSession.session_id == ids[1]).values(revoked_at=now - timedelta(days=91)))
    harness.execute(update(P.UserSession).where(P.UserSession.session_id == ids[2]).values(revoked_at=now - timedelta(days=10)))

    async def purge():
        async with harness.Session() as db:
            return await purge_old_sessions(db)
    assert run(purge()) == 2
    remaining = [i for (i,) in harness.query(select(P.UserSession.session_id))]
    assert sorted(remaining) == [ids[2], ids[3]]
