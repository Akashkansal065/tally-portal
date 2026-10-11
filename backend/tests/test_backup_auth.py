"""Every backup route needs the login of someone who runs the server (an account Admin is not enough: anyone who
signs up is the Admin of their own account), and the standalone server needs its key."""
import re

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings as app_settings
from app.core.database import get_db
from tests.conftest import bearer, login

RECORD = {
    "id": "b1", "company_name": "Sneh Distributors", "file_name": "sneh_backup.zip", "file_size_bytes": 4,
    "status": "completed", "created_at": "2026-10-04T10:00:00",
}


@pytest.fixture
def backups(monkeypatch, tmp_path):
    """No real Tally or backup files: the service returns one finished backup."""
    from backup_module import router as backup_routes
    archive = tmp_path / "sneh_backup.zip"
    archive.write_bytes(b"PK\x03\x04")
    record = {**RECORD, "file_path": str(archive)}
    monkeypatch.setattr(backup_routes.backup_service, "list_all_backups", lambda: [record])
    monkeypatch.setattr(backup_routes.backup_service, "get_backup_record", lambda backup_id: record)
    monkeypatch.setattr(backup_routes.backup_service, "delete_backup", lambda backup_id: True)
    return record


@pytest.fixture
def main_app(harness, backups):
    """The production app (routers and mounts exactly as in app/main.py) on the test database."""
    from app.main import app
    app.dependency_overrides[get_db] = harness._get_db
    yield app, TestClient(app)  # no "with": the startup tasks (schema sync, workers) don't run
    app.dependency_overrides.clear()


def backup_routes(app):
    """(method, path) for every backup route, from the OpenAPI schema, with path parameters filled in."""
    for path, operations in app.openapi()["paths"].items():
        if path.startswith("/backup"):
            for method in operations:
                yield method.upper(), re.sub(r"\{[^}]+\}", "b1", path)


def test_every_backup_route_rejects_anonymous_requests(main_app):
    app, client = main_app
    routes = sorted(backup_routes(app))
    assert ("GET", "/backup/b1/download") in routes and ("POST", "/backup/restore") in routes

    for method, path in routes:
        assert client.request(method, path).status_code == 401, (method, path)


def test_non_admin_is_refused(harness, main_app):
    _, client = main_app
    company = harness.company()
    clerk = harness.user(company, harness.role("Sales"), "sales.clerk")
    headers = bearer(login(client, clerk.email))

    assert client.get("/backup/list", headers=headers).status_code == 403
    assert client.get("/backup/b1/download", headers=headers).status_code == 403


def test_account_admin_is_refused(harness, main_app):
    """The Admin of an account (every sign-up makes one) must not reach the server's backups of other customers."""
    app, client = main_app
    company = harness.company()
    owner = harness.user(company, harness.role("Admin"), "owner")
    headers = bearer(login(client, owner.email))

    for method, path in sorted(backup_routes(app)):
        assert client.request(method, path, headers=headers).status_code == 403, (method, path)


def test_server_admin_can_list_and_download(monkeypatch, harness, main_app):
    _, client = main_app
    company = harness.company()
    operator = harness.user(company, harness.role("Admin"), "operator")
    monkeypatch.setattr(app_settings, "PLATFORM_ADMIN_EMAILS", " someone@else.test, OPERATOR@example.com ")
    headers = bearer(login(client, operator.email))

    listing = client.get("/backup/list", headers=headers)
    download = client.get("/backup/b1/download", headers=headers)

    assert listing.status_code == 200 and listing.json()[0]["file_name"] == "sneh_backup.zip"
    assert download.status_code == 200 and download.content == b"PK\x03\x04"


def test_no_server_admins_configured_means_nobody(monkeypatch, harness, main_app):
    _, client = main_app
    owner = harness.user(harness.company(), harness.role("Admin"), "owner")
    monkeypatch.setattr(app_settings, "PLATFORM_ADMIN_EMAILS", "")

    assert client.get("/backup/list", headers=bearer(login(client, owner.email))).status_code == 403


def test_standalone_server_requires_its_key(monkeypatch, backups):
    from backup_module.config import settings
    from backup_module.main import app as standalone
    client = TestClient(standalone)

    monkeypatch.setattr(settings, "API_KEY", "")
    assert client.get("/backup/list").status_code == 503

    monkeypatch.setattr(settings, "API_KEY", "a-long-random-key")
    assert client.get("/backup/list").status_code == 401
    assert client.get("/list", headers={"X-Backup-Key": "wrong"}).status_code == 401
    assert client.get("/backup/list", headers={"X-Backup-Key": "a-long-random-key"}).status_code == 200
    assert client.get("/health").json() == {"status": "online", "service": "Tally Backup & Restore Module"}
