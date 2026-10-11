"""Phase 5: scheduled backups with a fake backup module (no Tally)."""
from datetime import date, datetime

import pytest
from sqlalchemy import select

import app.models.portal_core as P
from app.core.config import settings
from app.routers import auth, backup_schedule as router
from app.services import backup_schedule as svc
from tests.conftest import bearer, login, run


class FakeBackups:
    def __init__(self):
        self.records, self.deleted, self.n = {}, [], 0

    def start_backup(self, company_name, notes=None):
        self.n += 1
        bid = f"b{self.n}"
        self.records[bid] = {"id": bid, "status": "completed", "company_name": company_name, "file_path": "/nope.zip",
                             "file_size_bytes": 10, "created_at": "2026-10-06T21:00:00"}
        return bid

    def get_backup_record(self, bid):
        return self.records.get(bid)

    def delete_backup(self, bid):
        self.deleted.append(bid)
        return True


class FakeTally:
    def __init__(self, connected=True):
        self.connected = connected

    def check_health(self):
        return (self.connected, "ok" if self.connected else "connection refused", [{"name": "Alpha"}])


@pytest.fixture
def world(harness, monkeypatch):
    backups, tally = FakeBackups(), FakeTally()
    monkeypatch.setattr(svc, "_backup_module", lambda: (backups, tally))
    h = harness
    alpha = h.company("Alpha")
    h.company("Beta")  # not open in Tally
    admin_role = h.role("Admin")
    h.user(alpha, admin_role, "owner")
    partner = h.user(alpha, admin_role, "partner")
    # The schedule is the whole server's: the owner runs this server, the partner is only an Admin of the account
    monkeypatch.setattr(settings, "PLATFORM_ADMIN_EMAILS", "owner@example.com")
    client = h.app(auth.router, router.router)
    return dict(h=h, client=client, headers=bearer(login(client, "owner@example.com")), backups=backups, tally=tally, partner=partner)


async def _tick(h, now):
    async for db in h._get_db():
        await svc.tick(db, now)


def test_schedule_runs_once_a_day_keeps_last_n_and_reports_problems(world):
    c, headers, h, backups = world["client"], world["headers"], world["h"], world["backups"]
    assert c.put("/backup-schedule", json={"enabled": True, "time": "25:00"}, headers=headers).status_code == 422
    assert c.put("/backup-schedule", json={"enabled": True, "time": "21:00", "keep": 2}, headers=headers).status_code == 200

    run(_tick(h, datetime(2026, 10, 6, 20, 0)))  # before the time
    assert backups.n == 0
    for day in (6, 7, 8):
        run(_tick(h, datetime(2026, 10, day, 21, 5)))
        run(_tick(h, datetime(2026, 10, day, 21, 15)))  # finishes; never a second run the same day
    assert backups.n == 3 and backups.deleted == ["b1"]  # only the last 2 kept
    state = c.get("/backup-schedule", headers=headers).json()
    assert state["last_run_day"] == "2026-10-08" and state["last_result"]["not_open_in_tally"] == ["Beta"]

    world["tally"].connected = False
    run(_tick(h, datetime(2026, 10, 9, 21, 5)))
    assert backups.n == 3
    # Problems are grouped into one notification per admin, showing the latest
    rows = h.query(select(P.Notification.title, P.Notification.message, P.Notification.user_id))
    assert {r[2] for r in rows} == {1, world["partner"].user_id}
    assert all(r[0] == "4 backup problems" and "isn't reachable" in r[1] for r in rows)


def test_off_and_idle_writes_nothing(world):
    run(_tick(world["h"], datetime(2026, 10, 6, 22, 0)))
    assert world["h"].query(select(P.AppSetting.key)) == []


def test_only_the_people_who_run_the_server_may_see_or_change_it(world):
    """An account Admin (anyone who signs up) could otherwise send every company's backup to their own email."""
    c, partner = world["client"], world["partner"]
    headers = bearer(login(c, partner.email))

    assert c.get("/backup-schedule", headers=headers).status_code == 403
    assert c.put("/backup-schedule", json={"enabled": True, "time": "21:00", "email_to": "thief@example.com"},
                 headers=headers).status_code == 403
    assert c.post("/backup-schedule/run-now", headers=headers).status_code == 403
    assert world["backups"].records == {}
    assert c.get("/backup-schedule", headers=world["headers"]).json()["email_to"] == ""
