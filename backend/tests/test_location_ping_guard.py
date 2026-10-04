"""Location pings that arrive too soon after the last processed one are answered without touching the database."""
import pytest
from sqlalchemy import select

from app.routers import attendance as att
from app.routers import auth
from tests.conftest import bearer, login

LAT, LON = 28.6139, 77.2090


@pytest.fixture
def field(harness, monkeypatch):
    # No network in tests: reverse geocoding returns a fixed name
    monkeypatch.setattr(att, "reverse_geocode_place", lambda lat, lon: "Connaught Place")
    att._last_processed_ping.clear()
    company = harness.company()
    user = harness.user(company, harness.role("Admin"), "field.user")
    client = harness.app(auth.router, att.router)
    headers = bearer(login(client, user.email))
    yield harness, client, headers, user
    att._last_processed_ping.clear()


def ping(client, headers, metres_north=0.0):
    response = client.post("/attendance/ping-location", headers=headers,
                           json={"latitude": LAT + metres_north / 111_320.0, "longitude": LON, "accuracyMeters": 10})
    assert response.status_code == 200, response.text
    return response.json()


def punch(client, headers, kind):
    response = client.post("/attendance/punch", headers=headers, json={
        "type": kind, "latitude": LAT, "longitude": LON, "accuracyMeters": 8,
        "deviceFingerprint": "test-device", "photoBase64": "x",
    })
    assert response.status_code == 200, response.text


def let_interval_pass():
    for user_id, (processed_at, active) in list(att._last_processed_ping.items()):
        att._last_processed_ping[user_id] = (processed_at - att.PING_MIN_INTERVAL_SECONDS - 1, active)


def test_rapid_ping_is_answered_without_database(field):
    harness, client, headers, _ = field
    punch(client, headers, "in")
    assert ping(client, headers)["active"] is True

    with harness.count_queries() as statements:
        reply = ping(client, headers, metres_north=500)

    assert reply == {"success": True, "active": True, "recorded": False, "throttled": True}
    assert statements == []


def test_ping_after_interval_is_processed(field):
    harness, client, headers, user = field
    punch(client, headers, "in")
    ping(client, headers)
    let_interval_pass()

    reply = ping(client, headers, metres_north=500)

    assert reply["active"] is True and reply.get("throttled") is None
    assert reply["recorded"] is True
    last_lat = harness.scalar(select(att.Attendance.last_known_latitude).where(att.Attendance.user_id == user.user_id))
    assert float(last_lat) == pytest.approx(LAT + 500 / 111_320.0)


def test_punch_out_makes_next_ping_report_inactive(field):
    _, client, headers, _ = field
    punch(client, headers, "in")
    ping(client, headers)
    punch(client, headers, "out")

    reply = ping(client, headers)

    assert reply["active"] is False and reply.get("throttled") is None


def test_no_shift_is_remembered_until_punch_in(field):
    harness, client, headers, _ = field
    assert ping(client, headers)["active"] is False

    with harness.count_queries() as statements:
        assert ping(client, headers) == {"success": True, "active": False, "recorded": False, "throttled": True}
    assert statements == []

    punch(client, headers, "in")
    assert ping(client, headers)["active"] is True
