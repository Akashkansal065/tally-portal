"""The standalone backup server (backup_module/main.py) needs its key. The app no longer mounts that module:
company backups are made by the sync agents (tests/test_company_backups.py)."""

import pytest
from fastapi.testclient import TestClient


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
