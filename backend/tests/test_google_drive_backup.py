"""Google Drive copies of backups, against a fake Google: no request leaves the machine."""
import hashlib
import json
import re
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

import app.models.portal_core as P
from app.core.config import settings
from app.core.datetime_utils import get_ist_now
from app.routers import auth, backups, drive_backup, integrations
from app.services import backups as backup_svc
from app.services import google_drive as drive
from tests.conftest import bearer, login, run

REFRESH = "1//refresh-token-secret-value"
ACCESS = "ya29.access-token"


class FakeGoogle:
    def __init__(self):
        self.files = {}              # id -> dict(name, parents, appProperties, content(bytes), mimeType, trashed)
        self.calls = []
        self.refresh_error = None    # e.g. "invalid_grant"
        self.upload_status = 200     # set to 403 with quota to simulate a full Drive
        self.upload_reason = "storageQuotaExceeded"
        self.revoked = []
        self.scope = "openid email https://www.googleapis.com/auth/drive.file"
        self.give_refresh_token = True
        self.sessions = {}
        self.n = 0

    def _id(self):
        self.n += 1
        return f"file{self.n:04d}"

    def meta(self, fid, fields=None):
        f = self.files[fid]
        return {"id": fid, "name": f["name"], "size": str(len(f["content"])) if f.get("content") is not None else None,
                "md5Checksum": hashlib.md5(f["content"]).hexdigest() if f.get("content") is not None else None,
                "trashed": f.get("trashed", False), "appProperties": f.get("appProperties", {}),
                "mimeType": f["mimeType"]}

    def handler(self, request: httpx.Request) -> httpx.Response:
        url, method = str(request.url), request.method
        self.calls.append((method, urlparse(url).path))
        path = urlparse(url).path
        if url.startswith("https://oauth2.googleapis.com/token"):
            form = parse_qs(request.content.decode())
            if form["grant_type"] == ["authorization_code"]:
                if form["code"] != ["good-code"]:
                    return httpx.Response(400, json={"error": "invalid_grant"})
                body = {"access_token": ACCESS, "scope": self.scope, "expires_in": 3600}
                if self.give_refresh_token:
                    body["refresh_token"] = REFRESH
                return httpx.Response(200, json=body)
            if self.refresh_error:
                return httpx.Response(400, json={"error": self.refresh_error, "error_description": "Token has been revoked"})
            return httpx.Response(200, json={"access_token": ACCESS, "expires_in": 3600})
        if url.startswith("https://openidconnect.googleapis.com"):
            return httpx.Response(200, json={"email": "owner@example.com"})
        if url.startswith("https://oauth2.googleapis.com/revoke"):
            self.revoked.append(parse_qs(request.content.decode())["token"][0])
            return httpx.Response(200)
        if request.headers.get("authorization") != f"Bearer {ACCESS}" and "upload-session" not in url:
            return httpx.Response(401, json={"error": {"code": 401, "message": "Invalid Credentials"}})
        if path == "/upload/drive/v3/files" and method == "POST":
            if self.upload_status != 200:
                return httpx.Response(self.upload_status, json={"error": {"code": self.upload_status, "message": "quota",
                                                                          "errors": [{"reason": self.upload_reason}]}})
            sid = f"s{len(self.sessions)}"
            self.sessions[sid] = json.loads(request.content)
            return httpx.Response(200, headers={"location": f"https://upload.example/upload-session/{sid}"})
        if "upload-session" in url and method == "PUT":
            meta = self.sessions[url.rsplit("/", 1)[1]]
            fid = self._id()
            self.files[fid] = {"name": meta["name"], "parents": meta["parents"], "appProperties": meta["appProperties"],
                               "content": request.content, "mimeType": meta["mimeType"]}
            return httpx.Response(200, json=self.meta(fid))
        if path == "/drive/v3/files" and method == "GET":
            q = dict(request.url.params)["q"]
            name = re.search(r"name='((?:[^'\\]|\\.)*)'", q).group(1).replace("\\'", "'")
            hits = [fid for fid, f in self.files.items() if f["name"] == name and not f.get("trashed")
                    and (f["mimeType"] != drive.FOLDER_MIME or f["appProperties"].get("app") == "mytally")]
            parent = re.search(r"'([^']+)' in parents", q)
            if parent:
                hits = [h for h in hits if parent.group(1) in self.files[h].get("parents", [])]
            for key in re.findall(r"key='(\w+)' and value='([^']*)'", q):
                hits = [h for h in hits if self.files[h]["appProperties"].get(key[0]) == key[1]]
            return httpx.Response(200, json={"files": [self.meta(h) for h in hits]})
        if path == "/drive/v3/files" and method == "POST":
            body = json.loads(request.content)
            fid = self._id()
            self.files[fid] = {"name": body["name"], "parents": body.get("parents", []),
                               "appProperties": body.get("appProperties", {}), "content": None,
                               "mimeType": body["mimeType"]}
            return httpx.Response(200, json={"id": fid})
        m = re.match(r"/drive/v3/files/([^/]+)$", path)
        if m and method == "GET":
            return httpx.Response(200, json=self.meta(m.group(1))) if m.group(1) in self.files else httpx.Response(404, json={"error": {"code": 404}})
        if m and method == "DELETE":
            self.files.pop(m.group(1), None)
            return httpx.Response(204)
        return httpx.Response(500, json={"error": "unhandled " + path})

    def user_files(self):
        return {fid: f for fid, f in self.files.items() if f["mimeType"] != drive.FOLDER_MIME}


@pytest.fixture
def google(monkeypatch, tmp_path):
    g = FakeGoogle()
    monkeypatch.setattr(drive, "client_factory", lambda: httpx.AsyncClient(transport=httpx.MockTransport(g.handler)))
    monkeypatch.setattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "client-id.apps.googleusercontent.com")
    monkeypatch.setattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", "client-secret")
    monkeypatch.setattr(settings, "GOOGLE_OAUTH_REDIRECT_URI", "https://api.example/backups/drive/callback")
    monkeypatch.setattr(settings, "SECRETS_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "BACKUP_STORAGE_DIR", str(tmp_path / "store"))
    monkeypatch.setattr(settings, "APP_PUBLIC_URL", "https://app.example")
    return g


class World:
    pass


@pytest.fixture
def world(harness, google):
    w = World()
    w.harness, w.google = harness, google
    w.company = harness.company("Alpha")
    other = harness.company("Beta")
    w.other = other
    role = harness.role("Admin")
    w.admin = harness.user(w.company, role, "owner")
    w.admin_b = harness.user(other, role, "ownerb")
    clerk_role = harness.role("Clerk")
    w.clerk = harness.user(w.company, clerk_role, "clerk")
    for c in (w.company, other):
        harness.add(P.CompanyIntegration(company_id=c.company_id, key="google_drive_backup", enabled=True))
    w.client = harness.app(auth.router, backups.router, backups.agent_router, drive_backup.router, integrations.router)
    w.h = bearer(login(w.client, w.admin.email))
    w.hb = bearer(login(w.client, w.admin_b.email))
    w.hc = bearer(login(w.client, w.clerk.email))

    async def factory_session():
        return harness.Session()
    drive.session_factory = lambda: harness.Session()

    def stored_backup(key="bk-0000000001", company=None, content=b"zip-bytes" * 5000, taken=None):
        company = company or w.company
        row = P.CompanyBackup(company_id=company.company_id, account_id=company.account_id, backup_key=key, kind="hourly",
                              status="stored", taken_at=taken or get_ist_now(), stored_at=get_ist_now(),
                              size_bytes=len(content), sha256=hashlib.sha256(content).hexdigest(), chunk_size=65536,
                              received_bytes=len(content))
        row = harness.add(row)
        path = backup_svc.file_path(row)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return row.backup_id
    w.stored_backup = stored_backup

    def link(company=None, user=None):
        async def go():
            async with harness.Session() as db:
                await drive.save_link(db, (company or w.company).company_id, (user or w.admin).user_id,
                                      "owner@example.com", REFRESH)
                await db.commit()
        run(go())
    w.link = link

    def backup(bid):
        return harness.query(select(P.CompanyBackup).where(P.CompanyBackup.backup_id == bid))[0][0]
    w.backup = backup

    def push(bid, name="Alpha"):
        async def go():
            async with harness.Session() as db:
                row = (await db.execute(select(P.CompanyBackup).where(P.CompanyBackup.backup_id == bid))).scalars().first()
                result = await drive.push_backup(db, row, name)
                await db.commit()
                return result
        return run(go())
    w.push = push
    return w


def callback(w, state, code="good-code", **extra):
    return w.client.get("/backups/drive/callback", params={"code": code, "state": state, **extra}, follow_redirects=False)


def state_for(w, user=None, company=None):
    return drive.make_state((user or w.admin).user_id, (company or w.company).company_id)


# ── linking ──

def test_connect_gives_a_google_address_with_least_privilege_and_a_bound_state(world):
    res = world.client.post("/backups/drive/connect", headers=world.h)
    assert res.status_code == 200
    url = urlparse(res.json()["authorization_url"])
    q = parse_qs(url.query)
    assert url.netloc == "accounts.google.com"
    assert q["scope"] == ["openid email https://www.googleapis.com/auth/drive.file"]
    assert q["access_type"] == ["offline"] and q["prompt"] == ["consent"] and q["response_type"] == ["code"]
    assert drive.read_state(q["state"][0]) == (world.admin.user_id, world.company.company_id)


def test_only_an_administrator_can_connect_or_unlink(world):
    assert world.client.post("/backups/drive/connect", headers=world.hc).status_code == 403
    assert world.client.delete("/backups/drive", headers=world.hc).status_code == 403


def test_connecting_is_refused_until_the_server_is_configured(world, monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_OAUTH_CLIENT_ID", None)
    assert world.client.post("/backups/drive/connect", headers=world.h).status_code == 503
    assert world.client.get("/backups/drive", headers=world.h).json()["status"] == "needs_setup"


def test_a_forged_expired_or_foreign_state_links_nothing(world):
    forged = callback(world, "not-a-state")
    assert forged.status_code == 303 and "drive=error" in forged.headers["location"]
    import jwt
    expired = jwt.encode({"u": world.admin.user_id, "c": world.company.company_id, "p": "gdrive",
                          "exp": datetime.utcnow() - timedelta(hours=1)}, settings.JWT_SECRET, algorithm="HS256")
    assert "drive=error" in callback(world, expired).headers["location"]
    # a state made for the wrong company for that user, and one with a different purpose
    assert "drive=error" in callback(world, state_for(world, company=world.other)).headers["location"]
    wrong = jwt.encode({"u": world.admin.user_id, "c": world.company.company_id, "p": "other",
                        "exp": datetime.utcnow() + timedelta(minutes=5)}, settings.JWT_SECRET, algorithm="HS256")
    assert "drive=error" in callback(world, wrong).headers["location"]
    assert world.harness.query(select(P.GoogleDriveLink)) == []


def test_a_clerk_cannot_complete_a_link_with_a_state_made_for_them(world):
    res = callback(world, state_for(world, user=world.clerk))
    assert "drive=error" in res.headers["location"]
    assert world.harness.query(select(P.GoogleDriveLink)) == []


def test_the_callback_stores_the_token_encrypted_and_no_response_ever_shows_it(world):
    res = callback(world, state_for(world))
    assert res.status_code == 303 and res.headers["location"].endswith("/backup?drive=linked")
    (link,) = [r[0] for r in world.harness.query(select(P.GoogleDriveLink))]
    assert link.google_email == "owner@example.com" and link.company_id == world.company.company_id
    assert REFRESH not in link.refresh_token_enc and drive.decrypt_secret(link.refresh_token_enc) == REFRESH
    for resp in (world.client.get("/backups/drive", headers=world.h), world.client.get("/backups", headers=world.h),
                 world.client.get("/integrations", headers=world.h)):
        assert REFRESH not in resp.text and link.refresh_token_enc not in resp.text and ACCESS not in resp.text
    assert world.client.get("/backups/drive", headers=world.h).json()["status"] == "linked"


def test_no_refresh_token_or_missing_scope_is_not_a_link(world):
    world.google.give_refresh_token = False
    assert "drive=error" in callback(world, state_for(world)).headers["location"]
    world.google.give_refresh_token, world.google.scope = True, "openid email"
    assert "drive=error" in callback(world, state_for(world)).headers["location"]
    assert world.harness.query(select(P.GoogleDriveLink)) == []


def test_declining_at_google_is_reported_not_linked(world):
    res = world.client.get("/backups/drive/callback", params={"error": "access_denied", "state": state_for(world)},
                           follow_redirects=False)
    assert "drive=cancelled" in res.headers["location"]


# ── copying ──

def test_a_stored_backup_is_copied_to_the_company_folder(world):
    world.link()
    bid = world.stored_backup()
    assert world.push(bid) == "uploaded"
    row = world.backup(bid)
    assert row.drive_status == "uploaded" and row.drive_file_id and row.drive_error is None
    (fid, f), = world.google.user_files().items()
    assert fid == row.drive_file_id and f["name"] == "bk-0000000001.zip"
    assert f["appProperties"]["company_id"] == str(world.company.company_id) and f["appProperties"]["app"] == "mytally"
    parent = world.google.files[f["parents"][0]]
    root = world.google.files[parent["parents"][0]]
    assert (root["name"], parent["name"]) == ("MyTally Backups", "Alpha")
    assert world.harness.query(select(P.GoogleDriveLink.folder_id))[0][0] == f["parents"][0]


def test_repeating_the_copy_never_makes_a_second_file(world):
    world.link()
    bid = world.stored_backup()
    world.push(bid)
    world.push(bid)
    # the answer of the first upload was lost: the backup does not know its file id
    world.harness.execute(P.CompanyBackup.__table__.update().where(P.CompanyBackup.backup_id == bid)
                          .values(drive_file_id=None, drive_status="failed"))
    assert world.push(bid) == "uploaded"
    assert len(world.google.user_files()) == 1
    assert world.backup(bid).drive_file_id in world.google.user_files()
    assert len([c for c in world.google.calls if c == ("POST", "/upload/drive/v3/files")]) == 1


def test_a_revoked_token_marks_the_link_needs_relink(world):
    world.link()
    bid = world.stored_backup()
    world.google.refresh_error = "invalid_grant"
    assert world.push(bid) == "pending"
    link = world.harness.query(select(P.GoogleDriveLink))[0][0]
    assert link.status == "needs_relink"
    assert "Reconnect" in (world.backup(bid).drive_error or "")
    state = world.client.get("/backups/drive", headers=world.h).json()
    assert state["status"] == "needs_relink" and state["last_error"]
    # no further attempts are made while the link needs reconnecting
    calls = len(world.google.calls)
    world.push(bid)
    assert len(world.google.calls) == calls


def test_a_full_drive_fails_clearly_and_is_retried_later(world):
    world.link()
    bid = world.stored_backup()
    world.google.upload_status = 403
    assert world.push(bid) == "failed"
    row = world.backup(bid)
    assert "full" in row.drive_error and row.drive_attempts == 1 and row.drive_next_retry_at is not None
    world.google.upload_status = 200
    assert world.push(bid) == "uploaded"


def test_rate_limits_and_server_errors_are_retried_and_a_backup_is_never_failed_by_drive(world):
    world.link()
    bid = world.stored_backup()
    world.google.upload_status, world.google.upload_reason = 429, "rateLimitExceeded"
    assert world.push(bid) == "failed"
    assert world.backup(bid).status == "stored"                 # the backup itself is untouched


def test_the_retry_sweep_picks_up_what_is_due(world):
    world.link()
    bid = world.stored_backup()
    world.google.upload_status = 403
    world.push(bid)
    world.google.upload_status = 200
    world.harness.execute(P.CompanyBackup.__table__.update().where(P.CompanyBackup.backup_id == bid)
                          .values(drive_next_retry_at=get_ist_now() - timedelta(minutes=1)))

    async def go():
        async with world.harness.Session() as db:
            return await drive.retry_due(db)
    assert run(go()) == 1
    assert world.backup(bid).drive_status == "uploaded"


# ── unlink, tenants, retention ──

def test_unlinking_revokes_at_google_deletes_the_credential_and_keeps_the_files(world):
    world.link()
    bid = world.stored_backup()
    world.push(bid)
    res = world.client.delete("/backups/drive", headers=world.h)
    assert res.status_code == 200 and res.json()["status"] == "not_linked"
    assert world.google.revoked == [REFRESH]
    assert world.harness.query(select(P.GoogleDriveLink)) == []
    assert len(world.google.user_files()) == 1                  # the user's files are theirs


def test_companies_are_isolated(world):
    world.link()
    bid = world.stored_backup()
    assert world.client.get("/backups/drive", headers=world.hb).json()["status"] == "not_linked"
    assert world.client.post("/backups/drive/retry", headers=world.hb).status_code == 409
    other_bid = world.stored_backup(key="bk-0000000002", company=world.other)
    assert world.push(other_bid, "Beta") == "none"             # Beta has no link: nothing is sent anywhere
    assert world.google.user_files() == {}
    assert world.backup(other_bid).drive_status is None
    # and Beta's admin cannot unlink Alpha's Drive
    world.client.delete("/backups/drive", headers=world.hb)
    assert len(world.harness.query(select(P.GoogleDriveLink))) == 1
    assert bid


def test_retention_deletes_only_files_mytally_recorded_and_made(world):
    world.link()
    old = world.stored_backup(key="bk-0000000010", taken=get_ist_now() - timedelta(days=30))
    new = world.stored_backup(key="bk-0000000011")
    world.push(old)
    world.push(new)
    old_id, new_id = world.backup(old).drive_file_id, world.backup(new).drive_file_id
    # a file in the user's Drive that is not ours, and one whose id was recorded wrongly for another backup
    world.google.files["stranger"] = {"name": "holiday.jpg", "parents": [], "appProperties": {}, "content": b"x", "mimeType": "image/jpeg"}
    world.harness.add(P.DriveFileDeletion(company_id=world.company.company_id, drive_file_id="stranger", backup_key="bk-0000000010"))

    async def go():
        async with world.harness.Session() as db:
            await backup_svc.prune_company(db, world.company.company_id, get_ist_now())
            await db.commit()
            return await drive.run_deletions(db)
    run(go())
    remaining = world.google.user_files()
    assert old_id not in remaining and new_id in remaining and "stranger" in remaining
    assert world.harness.query(select(P.DriveFileDeletion)) == []


def test_integration_status_is_connected_only_once_linked(world):
    status = lambda: {i["key"]: i["status"] for i in world.client.get("/integrations", headers=world.h).json()}["google_drive_backup"]
    assert status() == "needs_setup"
    world.link()
    assert status() == "connected"


def test_a_newly_stored_backup_is_queued_then_copied_in_the_background(world):
    world.link()
    bid = world.stored_backup()

    async def go():
        async with world.harness.Session() as db:
            row = (await db.execute(select(P.CompanyBackup).where(P.CompanyBackup.backup_id == bid))).scalars().first()
            await drive.mark_pending(db, row)
            await db.commit()
            return row.drive_status
    assert run(go()) == "pending"
    run(drive.push_in_background(bid))
    assert world.backup(bid).drive_status == "uploaded"
