"""Company backups made by the sync agent: chunked, checked uploads that are safe to repeat, the keep rule, "back up
now" from the app, and restores with their safeguards. Two businesses sign up from their own PCs, so every check
also runs against someone who must not get in."""
import hashlib
import math
import os
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select

import app.models.portal_core as P
from app.core.config import settings
from app.core.datetime_utils import get_ist_now
from app.routers import agent, auth, backups, sync
from app.services import backups as svc
from tests.conftest import bearer, login
from tests.test_agent_onboarding import PC_ONE, PC_TWO, SIGNUP, code_from, mail  # noqa: F401  (mail is a fixture)

CHUNK = 64 * 1024
ALPHA = {"tally_guid": "guid-alpha", "name": "ABC Corp", "books_from": "20250401", "fingerprint": "1|20250401"}
RAVI = {"tally_guid": "guid-ravi", "name": "Ravi Traders", "books_from": "20250401"}


@pytest.fixture
def world(harness, mail, monkeypatch, tmp_path):  # noqa: F811
    monkeypatch.setattr(settings, "BACKUP_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "BACKUP_RESTORE_ENABLED", False)
    client = harness.app(auth.router, agent.router, sync.router, backups.agent_router, backups.router)

    def sign_up(signup, device, company):
        assert client.post("/agent/signup", json=signup).status_code == 200
        res = client.post("/agent/signup/verify", json={"email": signup["email"], "code": code_from(mail), "company": company, **device})
        assert res.status_code == 200, res.text
        return res.json()["device_token"]

    asha_pc = sign_up(SIGNUP, PC_ONE, ALPHA)
    ravi_pc = sign_up({**SIGNUP, "email": "ravi@example.com", "business_name": "Ravi & Co"}, PC_TWO, RAVI)
    return dict(
        harness=harness, client=client, tmp=tmp_path,
        asha_pc={**bearer(asha_pc), "X-Tally-Company-GUID": "guid-alpha"},
        ravi_pc={**bearer(ravi_pc), "X-Tally-Company-GUID": "guid-ravi"},
        ravi_pc_on_alpha={**bearer(ravi_pc), "X-Tally-Company-GUID": "guid-alpha"},
        asha=bearer(login(client, "asha@example.com")), ravi=bearer(login(client, "ravi@example.com")),
    )


def announce(client, pc, key, data, kind="hourly", taken_at=None, sha=None, fingerprint="1|20250401"):
    return client.post("/agent/backups", headers=pc, json={
        "backup_key": key, "kind": kind, "taken_at": (taken_at or get_ist_now()).isoformat(), "size_bytes": len(data),
        "sha256": sha or hashlib.sha256(data).hexdigest(), "chunk_size": CHUNK, "company_name": "ABC Corp",
        "fingerprint": fingerprint, "record_counts": {"ledgers": 3, "vouchers": 12}})


def send_chunk(client, pc, key, data, index):
    return client.put(f"/agent/backups/{key}/chunks/{index}", headers={**pc, "Content-Type": "application/octet-stream"},
                      content=data[index * CHUNK:(index + 1) * CHUNK])


def upload(client, pc, key, data, **kwargs):
    assert announce(client, pc, key, data, **kwargs).status_code == 200
    for index in range(math.ceil(len(data) / CHUNK)):
        assert send_chunk(client, pc, key, data, index).status_code == 200
    done = client.post(f"/agent/backups/{key}/complete", headers=pc)
    assert done.status_code == 200, done.text
    return done.json()


def listed(world, who="asha"):
    return world["client"].get("/backups", headers=world[who]).json()


# ── Uploading ────────────────────────────────────────────────────────────────

def test_a_backup_is_uploaded_in_chunks_checked_stored_and_downloadable(world):
    c, data = world["client"], os.urandom(150_000)          # three chunks, the last one short
    announce(c, world["asha_pc"], "hourly-0001", data)
    nexts = [send_chunk(c, world["asha_pc"], "hourly-0001", data, i).json()["next_chunk"] for i in range(3)]
    assert nexts == [1, 2, 3]                               # after the short last chunk: all three are in

    stored = upload(c, world["asha_pc"], "hourly-0001", data)

    assert stored["status"] == "stored" and stored["size_bytes"] == len(data)
    assert [b["backup_key"] for b in listed(world)["backups"]] == ["hourly-0001"]
    download = c.get(f"/backups/{stored['backup_id']}/download", headers=world["asha"])
    assert download.status_code == 200 and download.content == data
    assert download.headers["content-type"] == "application/zip"


def test_an_upload_carries_on_where_it_stopped_and_repeats_change_nothing(world):
    c, pc, data = world["client"], world["asha_pc"], os.urandom(150_000)
    assert announce(c, pc, "hourly-0002", data).json()["next_chunk"] == 0
    assert send_chunk(c, pc, "hourly-0002", data, 0).json()["next_chunk"] == 1

    skipped = send_chunk(c, pc, "hourly-0002", data, 2)
    assert skipped.status_code == 409 and skipped.headers["X-Next-Chunk"] == "1"
    assert announce(c, pc, "hourly-0002", data).json()["next_chunk"] == 1     # the connection dropped: carry on
    assert send_chunk(c, pc, "hourly-0002", data, 0).json()["next_chunk"] == 1  # a chunk sent twice is harmless
    early = c.post("/agent/backups/hourly-0002/complete", headers=pc)
    assert early.status_code == 409 and early.headers["X-Next-Chunk"] == "1"
    for index in (1, 2):
        send_chunk(c, pc, "hourly-0002", data, index)

    first = c.post("/agent/backups/hourly-0002/complete", headers=pc).json()
    again = c.post("/agent/backups/hourly-0002/complete", headers=pc).json()
    announced_again = announce(c, pc, "hourly-0002", data).json()

    assert first == again and announced_again["status"] == "stored"
    assert world["harness"].scalar(select(func.count()).select_from(P.CompanyBackup)) == 1
    assert announce(c, pc, "hourly-0002", os.urandom(1000)).status_code == 409   # another file under a stored key


def test_a_file_that_does_not_match_its_checksum_is_not_kept(world):
    c, pc, data = world["client"], world["asha_pc"], os.urandom(100_000)
    announce(c, pc, "hourly-0003", data, sha="0" * 64)
    for index in (0, 1):
        send_chunk(c, pc, "hourly-0003", data, index)

    refused = c.post("/agent/backups/hourly-0003/complete", headers=pc)

    assert refused.status_code == 422 and refused.headers["X-Next-Chunk"] == "0"
    assert listed(world)["backups"][0]["status"] == "uploading"
    assert not any(world["tmp"].rglob("*.zip*"))


def test_chunks_of_the_wrong_size_are_refused(world):
    c, pc, data = world["client"], world["asha_pc"], os.urandom(100_000)
    announce(c, pc, "hourly-0004", data)
    short = c.put("/agent/backups/hourly-0004/chunks/0", headers={**pc, "Content-Type": "application/octet-stream"}, content=data[:100])
    assert short.status_code == 400


# ── Who may ──────────────────────────────────────────────────────────────────

def test_another_business_cannot_reach_a_backup(world):
    c = world["client"]
    stored = upload(c, world["asha_pc"], "hourly-0005", os.urandom(70_000))

    # Ravi's PC naming Asha's company: not linked to it
    assert c.get("/agent/backups/jobs", headers=world["ravi_pc_on_alpha"]).status_code == 409
    assert c.get("/agent/backups/hourly-0005/download", headers=world["ravi_pc_on_alpha"]).status_code == 409
    # Ravi's PC on its own company does not find Asha's backup, and Ravi's admin sees none of Asha's
    assert c.get("/agent/backups/hourly-0005/download", headers=world["ravi_pc"]).status_code == 404
    assert c.get(f"/backups/{stored['backup_id']}/download", headers=world["ravi"]).status_code == 404
    assert listed(world, "ravi")["backups"] == []


def test_only_a_signed_in_pc_uploads_and_only_an_admin_sees_backups(world):
    c, harness = world["client"], world["harness"]
    person = {**world["asha"], "X-Tally-Company-GUID": "guid-alpha"}
    assert announce(c, person, "hourly-0006", os.urandom(1000)).status_code == 403

    sales_role = harness.scalar(select(P.Role).where(P.Role.name == "Sales"))
    company = harness.scalar(select(P.Company).where(P.Company.tally_guid == "guid-alpha"))
    clerk = harness.user(company, sales_role, "clerk")
    harness.execute(P.User.__table__.update().where(P.User.user_id == clerk.user_id).values(account_id=company.account_id))
    clerk_headers = bearer(login(c, clerk.email))
    assert c.get("/backups", headers=clerk_headers).status_code == 403
    assert c.post("/backups", headers=clerk_headers).status_code == 403


# ── Keeping the right ones ───────────────────────────────────────────────────

def test_keep_rule():
    now = get_ist_now().replace(hour=15, minute=30)
    day = lambda n, hour: (now - timedelta(days=n)).replace(hour=hour, minute=0)  # noqa: E731
    backups = [
        ("today-09", day(0, 9), "hourly"), ("today-14", day(0, 14), "hourly"),
        ("yday-10", day(1, 10), "hourly"), ("yday-23", day(1, 23), "hourly"), ("yday-manual", day(1, 12), "manual"),
        ("d3-pre", day(3, 11), "pre_restore"), ("d3-18", day(3, 18), "hourly"), ("d3-08", day(3, 8), "hourly"),
        ("d7-20", day(7, 20), "hourly"), ("d8-20", day(8, 20), "hourly"),
    ]

    assert svc.keys_to_keep(backups, now) == {"today-09", "today-14", "yday-23", "d3-pre", "d3-18", "d7-20"}
    # A PC that was off for a fortnight: the newest is kept, nothing else that old
    old = [("d20-09", day(20, 9), "hourly"), ("d21-09", day(21, 9), "hourly")]
    assert svc.keys_to_keep(old, now) == {"d20-09"}


def test_the_server_keeps_only_what_the_rule_wants_after_each_upload(world):
    c, pc = world["client"], world["asha_pc"]
    now = get_ist_now()
    for key, days, hour in (("old-d9-xx", 9, 10), ("d2-early", 2, 9), ("d2-later", 2, 20), ("today-one", 0, 0)):
        upload(c, pc, key, os.urandom(1000), taken_at=(now - timedelta(days=days)).replace(hour=hour, minute=0))

    assert sorted(b["backup_key"] for b in listed(world)["backups"]) == ["d2-later", "today-one"]
    assert sorted(p.name for p in world["tmp"].rglob("*.zip")) == ["d2-later.zip", "today-one.zip"]


# ── Back up now ──────────────────────────────────────────────────────────────

def test_back_up_now_is_made_by_the_agent_under_the_key_the_app_gave(world):
    c, pc = world["client"], world["asha_pc"]
    asked = c.post("/backups", headers=world["asha"]).json()
    again = c.post("/backups", headers=world["asha"]).json()
    assert asked["backup_key"] == again["backup_key"] and asked["status"] == "requested"
    assert c.get("/agent/backups/jobs", headers=pc).json()["backups"] == [{"backup_key": asked["backup_key"], "kind": "manual"}]
    assert c.get("/agent/backups/jobs", headers=world["ravi_pc"]).json()["backups"] == []

    stored = upload(c, pc, asked["backup_key"], os.urandom(5000), kind="hourly")

    assert stored["kind"] == "manual" and stored["status"] == "stored"
    assert c.get("/agent/backups/jobs", headers=pc).json()["backups"] == []


def test_a_backup_the_agent_could_not_make_says_why(world):
    c = world["client"]
    asked = c.post("/backups", headers=world["asha"]).json()
    c.post(f"/agent/backups/{asked['backup_key']}/failed", headers=world["asha_pc"], json={"error": "ABC Corp is not open in Tally"})

    row = listed(world)["backups"][0]
    assert (row["status"], row["error"]) == ("failed", "ABC Corp is not open in Tally")


# ── Restore ──────────────────────────────────────────────────────────────────

def test_restore_is_off_until_switched_on(world):
    c = world["client"]
    stored = upload(c, world["asha_pc"], "hourly-0007", os.urandom(2000))

    refused = c.post(f"/backups/{stored['backup_id']}/restore", headers=world["asha"], json={"confirm_company_name": "ABC Corp"})

    assert refused.status_code == 403 and "not switched on" in refused.json()["detail"]
    assert c.get("/agent/backups/jobs", headers=world["asha_pc"]).json()["restores"] == []
    assert listed(world)["restore_enabled"] is False


def test_restore_safeguards_and_steps(world, monkeypatch):
    monkeypatch.setattr(settings, "BACKUP_RESTORE_ENABLED", True)
    c, pc, admin, harness = world["client"], world["asha_pc"], world["asha"], world["harness"]
    data = os.urandom(3000)
    target = upload(c, pc, "hourly-0008", data)
    restore_url = f"/backups/{target['backup_id']}/restore"

    # Typed the wrong name: not restored
    assert c.post(restore_url, headers=admin, json={"confirm_company_name": "ABC"}).status_code == 400
    # A different copy of the books is synced now: not restored
    harness.execute(P.Company.__table__.update().where(P.Company.tally_guid == "guid-alpha").values(tally_fingerprint="2|20240401"))
    assert c.post(restore_url, headers=admin, json={"confirm_company_name": "abc corp"}).status_code == 409
    harness.execute(P.Company.__table__.update().where(P.Company.tally_guid == "guid-alpha").values(tally_fingerprint="1|20250401"))

    asked = c.post(restore_url, headers=admin, json={"confirm_company_name": " abc corp "}).json()
    assert c.post(restore_url, headers=admin, json={"confirm_company_name": "ABC Corp"}).json() == asked   # asked twice: one restore
    other = upload(c, pc, "hourly-0009", os.urandom(100))
    assert c.post(f"/backups/{other['backup_id']}/restore", headers=admin, json={"confirm_company_name": "ABC Corp"}).status_code == 409

    job = c.get("/agent/backups/jobs", headers=pc).json()["restores"]
    assert job == [{"restore_id": asked["restore_id"], "backup_key": "hourly-0008", "sha256": hashlib.sha256(data).hexdigest(),
                    "size_bytes": len(data), "fingerprint": "1|20250401", "company_name": "ABC Corp"}]
    start_url = f"/agent/backups/restores/{asked['restore_id']}/start"
    # The agent must store a backup of the company as it is first
    assert c.post(start_url, headers=pc, json={"pre_restore_backup_key": "before-0008"}).status_code == 404
    upload(c, pc, "before-0008", os.urandom(4000), kind="pre_restore")
    running = c.post(start_url, headers=pc, json={"pre_restore_backup_key": "before-0008"}).json()
    assert running["status"] == "running"
    assert c.post(start_url, headers=pc, json={"pre_restore_backup_key": "before-0008"}).json() == running
    assert c.post(f"/backups/restores/{asked['restore_id']}/cancel", headers=admin).status_code == 409

    done = c.post(f"/agent/backups/restores/{asked['restore_id']}/finish", headers=pc,
                  json={"ok": True, "summary": {"ledgers": {"sent": 3, "created": 0, "altered": 3, "errors": 0}}}).json()
    assert done["status"] == "completed" and done["summary"]["ledgers"]["altered"] == 3
    # Finished: another restore can be asked for
    assert c.post(f"/backups/{other['backup_id']}/restore", headers=admin, json={"confirm_company_name": "ABC Corp"}).status_code == 202


def test_a_restore_not_started_can_be_cancelled_and_its_backup_is_kept_meanwhile(world, monkeypatch):
    monkeypatch.setattr(settings, "BACKUP_RESTORE_ENABLED", True)
    c, pc, admin = world["client"], world["asha_pc"], world["asha"]
    now = get_ist_now()
    early = upload(c, pc, "d2-early", os.urandom(500), taken_at=(now - timedelta(days=2)).replace(hour=9))
    asked = c.post(f"/backups/{early['backup_id']}/restore", headers=admin, json={"confirm_company_name": "ABC Corp"}).json()

    upload(c, pc, "d2-later", os.urandom(500), taken_at=(now - timedelta(days=2)).replace(hour=20))   # would replace it
    assert "d2-early" in [b["backup_key"] for b in listed(world)["backups"]]

    cancelled = c.post(f"/backups/restores/{asked['restore_id']}/cancel", headers=admin).json()
    assert cancelled["status"] == "cancelled"
    assert c.get("/agent/backups/jobs", headers=pc).json()["restores"] == []


def test_a_restore_the_agent_turns_down_is_closed_with_its_reason(world, monkeypatch):
    monkeypatch.setattr(settings, "BACKUP_RESTORE_ENABLED", True)
    c, pc, admin = world["client"], world["asha_pc"], world["asha"]
    stored = upload(c, pc, "hourly-0010", os.urandom(800))
    asked = c.post(f"/backups/{stored['backup_id']}/restore", headers=admin, json={"confirm_company_name": "ABC Corp"}).json()

    refused = c.post(f"/agent/backups/restores/{asked['restore_id']}/finish", headers=pc,
                     json={"ok": False, "error": "A different copy of the books is open in Tally."}).json()

    assert (refused["status"], refused["error"]) == ("failed", "A different copy of the books is open in Tally.")
    assert c.get("/agent/backups/jobs", headers=pc).json()["restores"] == []
    # It cannot be reported as done without having started
    again = c.post(f"/backups/{stored['backup_id']}/restore", headers=admin, json={"confirm_company_name": "ABC Corp"}).json()
    assert c.post(f"/agent/backups/restores/{again['restore_id']}/finish", headers=pc, json={"ok": True}).status_code == 409


def test_a_restore_the_pc_never_finished_can_be_closed_after_six_hours(world, monkeypatch):
    monkeypatch.setattr(settings, "BACKUP_RESTORE_ENABLED", True)
    c, pc, admin, harness = world["client"], world["asha_pc"], world["asha"], world["harness"]
    stored = upload(c, pc, "hourly-0011", os.urandom(800))
    asked = c.post(f"/backups/{stored['backup_id']}/restore", headers=admin, json={"confirm_company_name": "ABC Corp"}).json()
    upload(c, pc, "before-0011", os.urandom(800), kind="pre_restore")
    c.post(f"/agent/backups/restores/{asked['restore_id']}/start", headers=pc, json={"pre_restore_backup_key": "before-0011"})
    cancel = f"/backups/restores/{asked['restore_id']}/cancel"
    assert c.post(cancel, headers=admin).status_code == 409

    harness.execute(P.CompanyRestore.__table__.update().values(started_at=get_ist_now() - timedelta(hours=7)))
    closed = c.post(cancel, headers=admin).json()

    assert closed["status"] == "failed" and "did not report back" in closed["error"]
    assert c.post(f"/backups/{stored['backup_id']}/restore", headers=admin, json={"confirm_company_name": "ABC Corp"}).status_code == 202


def test_backups_go_beside_the_project_unless_a_folder_is_set(monkeypatch):
    monkeypatch.setattr(settings, "BACKUP_STORAGE_DIR", "")
    project = Path(svc.__file__).resolve().parents[3]
    assert svc.storage_root() == project.parent / f"{project.name}-backups"
    monkeypatch.setattr(settings, "BACKUP_STORAGE_DIR", "/srv/backups")
    assert svc.storage_root() == Path("/srv/backups")


def test_a_server_that_cannot_write_backups_says_where_and_what_to_set(world, monkeypatch, tmp_path):
    blocked = tmp_path / "not-a-folder"
    blocked.write_text("a file where the folder should be")
    monkeypatch.setattr(settings, "BACKUP_STORAGE_DIR", str(blocked / "backups"))

    refused = announce(world["client"], world["asha_pc"], "hourly-0012", os.urandom(100))

    assert refused.status_code == 507
    assert str(blocked / "backups") in refused.json()["detail"] and "BACKUP_STORAGE_DIR" in refused.json()["detail"]
