"""Notifications: each one links to the right screen, similar ones group, preferences are honoured, admins hear
about every company, the badge updates at once, approval state is reported, and old ones are purged."""
import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import func, select, update

import app.models.portal_core as P
from app.core.sessions import utcnow
from app.routers import auth, notifications
from app.services import daily_cleanup
from app.services import notifications as service
from tests.conftest import bearer, login, run


@pytest.fixture
def pushes(monkeypatch):
    """Records push payloads instead of sending them."""
    sent = []

    async def fake_deliver(payloads):
        sent.extend(payloads)
        return len(payloads)

    monkeypatch.setattr(service, "deliver_push", fake_deliver)
    return sent


@pytest.fixture
def world(harness):
    alpha = harness.company("Alpha")
    beta = harness.company("Beta")
    admin_role = harness.role("Admin")
    sales_role = harness.role("Sales")
    owner = harness.user(alpha, admin_role, "owner")         # home company Alpha
    sales = harness.user(beta, sales_role, "sales")           # works in Beta
    client = harness.app(auth.router, notifications.router)
    return dict(harness=harness, alpha=alpha, beta=beta, owner=owner, sales=sales, client=client)


def notify(harness, fn, **kwargs):
    async def go():
        async with harness.Session() as db:
            created = await fn(db, auto_commit=True, **kwargs)
            await asyncio.sleep(0)  # let the scheduled push task run
            return created
    return run(go())


def test_admins_hear_about_every_company_and_links_point_at_the_record(world, pushes):
    h, beta, owner = world["harness"], world["beta"], world["owner"]
    notify(h, service.notify_admins, company_id=beta.company_id, type="order_created", title="New Order Created",
           message="sales placed order #7", reference_id="7", reference_type="order",
           link=service.order_link(7, "pending"), exclude_user_id=world["sales"].user_id)

    token = login(world["client"], "owner@example.com")
    items = world["client"].get("/notifications", headers=bearer(token)).json()
    assert len(items) == 1
    assert items[0]["company_id"] == beta.company_id      # owner's home company is Alpha
    assert items[0]["link"] == "/temporders?status=pending&order=7"
    assert items[0]["category"] == "orders"
    # Push opens the notification itself, which switches company before following the link
    assert pushes == [(owner.user_id, pushes[0][1])]
    assert pushes[0][1]["data"]["url"] == f"/notifications/open?id={items[0]['id']}"


def test_legacy_rows_without_a_link_get_one(world):
    h, owner = world["harness"], world["owner"]
    h.add(P.Notification(company_id=world["alpha"].company_id, user_id=owner.user_id, type="security",
                         title="New device sign-in", message="x", reference_id="42", reference_type="user_devices"))
    h.add(P.Notification(company_id=world["alpha"].company_id, user_id=owner.user_id, type="order_status",
                         title="Order #9 Approved", message="x", reference_id="9", reference_type="order"))
    token = login(world["client"], "owner@example.com")
    links = {n["type"]: n["link"] for n in world["client"].get("/notifications", headers=bearer(token)).json()}
    assert links["security"] == "/admin?tab=users&devices=42"   # used to fall through to Home
    assert links["order_status"] == "/temporders?status=all&order=9"  # not hidden by the Pending filter


def test_similar_unread_notifications_group_into_one(world, pushes):
    h, alpha = world["harness"], world["alpha"]
    for name in ("asha", "ravi", "meena"):
        notify(h, service.notify_admins, company_id=alpha.company_id, type="attendance_activity",
               title="Attendance: Clock-In", message=f"{name} clocked in", reference_type="attendance",
               link=service.TEAM_ATTENDANCE_LINK, group_key="clock_in:2026-10-05",
               group_title=lambda n: f"{n} staff clocked in today")

    rows = h.query(select(P.Notification.title, P.Notification.message, P.Notification.group_count))
    assert rows == [("3 staff clocked in today", "meena clocked in", 3)]
    # Each push replaces the previous one on the device (same tag)
    assert {p["tag"] for _, p in pushes} == {"clock_in:2026-10-05"}

    # Once read, the next clock-in starts a new entry
    h.execute(update(P.Notification).values(is_read=True))
    notify(h, service.notify_admins, company_id=alpha.company_id, type="attendance_activity",
           title="Attendance: Clock-In", message="late clocked in", reference_type="attendance",
           group_key="clock_in:2026-10-05", group_title=lambda n: f"{n} staff clocked in today")
    assert h.scalar(select(func.count(P.Notification.id))) == 2


def test_preferences_mute_or_limit_a_category(world, pushes):
    h, alpha, owner = world["harness"], world["alpha"], world["owner"]
    client = world["client"]
    token = login(client, "owner@example.com")

    prefs = client.get("/notifications/preferences", headers=bearer(token)).json()
    assert {p["category"]: p["delivery"] for p in prefs}["attendance"] == "all"

    assert client.put("/notifications/preferences", json={"category": "attendance", "delivery": "off"},
                      headers=bearer(token)).status_code == 200
    assert client.put("/notifications/preferences", json={"category": "orders", "delivery": "in_app"},
                      headers=bearer(token)).status_code == 200
    # Approvals can be limited to in-app but not switched off
    assert client.put("/notifications/preferences", json={"category": "approvals", "delivery": "off"},
                      headers=bearer(token)).status_code == 400

    notify(h, service.notify_admins, company_id=alpha.company_id, type="attendance_activity",
           title="Clock-In", message="x", reference_type="attendance")
    notify(h, service.notify_admins, company_id=alpha.company_id, type="order_created",
           title="New Order", message="y", reference_id="1", reference_type="order")

    types = [n["type"] for n in client.get("/notifications", headers=bearer(token)).json()]
    assert types == ["order_created"]   # attendance is off
    assert pushes == []                 # orders are in-app only


def test_badge_updates_as_soon_as_a_notification_arrives(world, pushes):
    h, client = world["harness"], world["client"]
    token = login(client, "owner@example.com")
    assert client.get("/notifications/unread-count", headers=bearer(token)).json() == {"count": 0}

    notify(h, service.notify_admins, company_id=world["alpha"].company_id, type="order_created",
           title="New Order", message="y", reference_id="1", reference_type="order")
    assert client.get("/notifications/unread-count", headers=bearer(token)).json() == {"count": 1}

    nid = client.get("/notifications", headers=bearer(token)).json()[0]["id"]
    client.patch(f"/notifications/{nid}/read", headers=bearer(token))
    assert client.get("/notifications/unread-count", headers=bearer(token)).json() == {"count": 0}


def test_approval_notifications_report_whether_a_decision_is_still_needed(world, pushes):
    from app.routers.attendance import Attendance
    h, client = world["harness"], world["client"]
    record = h.add(Attendance(user_id=world["sales"].user_id, approval_status="pending"))
    notify(h, service.notify_admins, company_id=world["beta"].company_id, type="attendance_approval",
           title="Attendance Approval Required: Clock-In", message="sales clocked in outside",
           reference_id=str(record.id), reference_type="attendance",
           link=service.attendance_approval_link(record.id))

    token = login(client, "owner@example.com")
    item = client.get("/notifications?category=approvals", headers=bearer(token)).json()[0]
    assert item["decision"] == "pending"
    assert item["link"] == f"/attendance?tab=admin&sub=approvals&id={record.id}"

    h.execute(update(Attendance).where(Attendance.id == record.id).values(approval_status="approved"))
    assert client.get(f"/notifications/{item['id']}", headers=bearer(token)).json()["decision"] == "approved"


def test_people_only_see_their_own_notifications(world, pushes):
    h, client = world["harness"], world["client"]
    notify(h, service.notify_user, company_id=world["beta"].company_id, user_id=world["sales"].user_id,
           type="order_status", title="Order #3 Approved", message="ok", reference_id="3", reference_type="order")
    nid = h.scalar(select(P.Notification.id))

    owner_token = login(client, "owner@example.com")
    assert client.get(f"/notifications/{nid}", headers=bearer(owner_token)).status_code == 404
    assert client.patch(f"/notifications/{nid}/read", headers=bearer(owner_token)).status_code == 404
    assert client.delete(f"/notifications/{nid}", headers=bearer(owner_token)).status_code == 404

    sales_token = login(client, "sales@example.com")
    assert client.get(f"/notifications/{nid}", headers=bearer(sales_token)).status_code == 200


def test_daily_cleanup_purges_old_notifications(world):
    h, owner, alpha = world["harness"], world["owner"], world["alpha"]
    now = utcnow()

    def add(days_old, is_read):
        h.add(P.Notification(company_id=alpha.company_id, user_id=owner.user_id, type="order_created",
                             title=f"{days_old}d read={is_read}", message="x", is_read=is_read,
                             created_at=now - timedelta(days=days_old)))

    add(100, True)    # read and past 90 days: removed
    add(100, False)   # unread: kept until 180 days
    add(200, False)   # unread past 180 days: removed
    add(10, True)     # recent: kept

    async def purge():
        async with h.Session() as db:
            return await daily_cleanup.purge_old_notifications(db)

    assert run(purge()) == 2
    assert sorted(t for (t,) in h.query(select(P.Notification.title))) == ["100d read=False", "10d read=True"]
