"""WS-13: encryption at rest, re-wrap, migration of existing files, restore into a new company, restore drill."""
import hashlib
import io
import json
import os
import zipfile
from datetime import timedelta

import pytest
from sqlalchemy import select

import app.models.portal_core as P
import app.models.tally_core as T
from app.core.config import settings
from app.core.datetime_utils import get_ist_now
from app.routers import auth, backups, sync
from app.services import backup_archive, backup_crypto, backup_drill, backup_encryption_migration as mig
from app.services import backup_restore_new as restore_new
from app.services import backups as svc
from tests.conftest import bearer, login, run

KEY_A, KEY_B = backup_crypto.generate_key(), backup_crypto.generate_key()


@pytest.fixture
def keys(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "BACKUP_STORAGE_DIR", str(tmp_path / "store"))
    monkeypatch.setattr(settings, "BACKUP_ENCRYPTION_KEYS", f"k1:{KEY_A},k2:{KEY_B}")
    monkeypatch.setattr(settings, "BACKUP_ENCRYPTION_ACTIVE_KEY_ID", "k1")


# ── crypto ──

def test_round_trip_across_segment_boundaries(keys, tmp_path, monkeypatch):
    monkeypatch.setattr(backup_crypto, "SEGMENT_BYTES", 1000)
    for size in (0, 1, 999, 1000, 1001, 5000):
        src, enc, back = tmp_path / "a.bin", tmp_path / "a.enc", tmp_path / "a.out"
        data = os.urandom(size)
        src.write_bytes(data)
        backup_crypto.encrypt_file(src, enc, "k1")
        assert backup_crypto.read_header(enc) == "k1" and enc.read_bytes()[:8] == backup_crypto.MAGIC
        backup_crypto.decrypt_to(enc, back)
        assert back.read_bytes() == data


def test_plain_files_have_no_header(keys, tmp_path):
    p = tmp_path / "plain.zip"
    p.write_bytes(b"PK\x03\x04 zip")
    assert backup_crypto.read_header(p) is None


def test_tampering_truncation_and_missing_keys_are_refused(keys, tmp_path, monkeypatch):
    monkeypatch.setattr(backup_crypto, "SEGMENT_BYTES", 100)
    src, enc = tmp_path / "a.bin", tmp_path / "a.enc"
    src.write_bytes(os.urandom(450))
    backup_crypto.encrypt_file(src, enc, "k1")
    raw = enc.read_bytes()

    flipped = tmp_path / "flip.enc"
    flipped.write_bytes(raw[:-20] + bytes([raw[-20] ^ 1]) + raw[-19:])
    with pytest.raises(backup_crypto.CryptoError):
        list(backup_crypto.decrypt_stream(flipped))

    cut = tmp_path / "cut.enc"
    cut.write_bytes(raw[: len(raw) - 130])                      # whole segments missing from the end
    with pytest.raises(backup_crypto.CryptoError):
        list(backup_crypto.decrypt_stream(cut))

    monkeypatch.setattr(settings, "BACKUP_ENCRYPTION_KEYS", f"k2:{KEY_B}")
    with pytest.raises(backup_crypto.CryptoError):
        list(backup_crypto.decrypt_stream(enc))


def test_rewrap_moves_a_file_to_the_new_key_and_is_repeat_safe(keys, tmp_path):
    src, enc = tmp_path / "a.bin", tmp_path / "a.enc"
    src.write_bytes(b"hello backup" * 100)
    backup_crypto.encrypt_file(src, enc, "k1")
    assert backup_crypto.rewrap_file(enc, "k2") is True
    assert backup_crypto.read_header(enc) == "k2"
    assert backup_crypto.rewrap_file(enc, "k2") is False
    assert b"".join(backup_crypto.decrypt_stream(enc)) == src.read_bytes()
    assert not list(tmp_path.glob("*.rewrap.*"))


def test_no_active_key_means_no_encryption(monkeypatch):
    monkeypatch.setattr(settings, "BACKUP_ENCRYPTION_ACTIVE_KEY_ID", None)
    assert backup_crypto.active_key_id() is None
    monkeypatch.setattr(settings, "BACKUP_ENCRYPTION_ACTIVE_KEY_ID", "nope")
    monkeypatch.setattr(settings, "BACKUP_ENCRYPTION_KEYS", f"k1:{KEY_A}")
    with pytest.raises(backup_crypto.CryptoError):
        backup_crypto.active_key_id()


# ── storage integration and migration of existing files ──

def make_zip(records=None, **extra) -> bytes:
    manifest = {"format_version": 1, "backup_key": "bk-x", "kind": "hourly", "taken_at": "2026-04-01T10:00:00",
                "company": {"guid": "guid-src", "name": "Alpha", "fingerprint": "10001|20260401", "books_from": "20260401"},
                "files": {"groups": ["groups.xml"], "ledgers": ["ledgers.xml"], "vouchers": ["vouchers_all.xml"]},
                "records": records or {"groups": 1, "ledgers": 1, "vouchers": 0}}
    manifest.update(extra)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("groups.xml", '<ENVELOPE><GROUP NAME="Sundry Debtors"><PARENT>Primary</PARENT></GROUP></ENVELOPE>')
        zf.writestr("ledgers.xml", '<ENVELOPE><LEDGER NAME="Party One"><PARENT>Sundry Debtors</PARENT><GUID>l-1</GUID></LEDGER></ENVELOPE>')
        zf.writestr("vouchers_all.xml", "<ENVELOPE></ENVELOPE>")
        zf.writestr("manifest.json", json.dumps(manifest))
    return buf.getvalue()


def store(harness, company, content, key="bk-0000000001", taken=None, kind="hourly"):
    row = harness.add(P.CompanyBackup(
        company_id=company.company_id, account_id=company.account_id, backup_key=key, kind=kind, status="stored",
        taken_at=taken or get_ist_now(), stored_at=get_ist_now(), size_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(), chunk_size=65536, received_bytes=len(content)))
    path = svc.file_path(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return row


def test_a_stored_backup_is_encrypted_and_read_back_transparently(harness, keys):
    c = harness.company("Alpha")
    content = make_zip()
    row = harness.add(P.CompanyBackup(company_id=c.company_id, account_id=c.account_id, backup_key="bk-0000000002",
                                      kind="hourly", status="uploading", taken_at=get_ist_now(), size_bytes=len(content),
                                      sha256=hashlib.sha256(content).hexdigest(), chunk_size=65536, received_bytes=len(content)))
    svc.write_chunk(row, 0, content)
    assert svc.finish_file(row) is True
    assert row.encryption_key_id == "k1"
    on_disk = svc.file_path(row).read_bytes()
    assert on_disk[:8] == backup_crypto.MAGIC and content not in on_disk
    assert not svc.part_path(row).exists()
    with svc.plaintext_file(row) as p:
        assert p.read_bytes() == content
    assert not list(svc.temp_dir().glob("*.zip"))


def test_existing_plain_backups_are_encrypted_once_and_only_when_they_verify(harness, keys, monkeypatch):
    c = harness.company("Alpha")
    good = store(harness, c, make_zip(), key="bk-0000000010")
    bad = store(harness, c, make_zip(), key="bk-0000000011")
    harness.execute(P.CompanyBackup.__table__.update().where(P.CompanyBackup.backup_id == bad.backup_id).values(sha256="0" * 64))

    async def go():
        async with harness.Session() as db:
            return await mig.encrypt_existing(db)
    first = run(go())
    assert first["encrypted"] == 1 and first["failed"] == 1
    assert backup_crypto.read_header(svc.file_path(good)) == "k1"
    assert backup_crypto.read_header(svc.file_path(bad)) is None                 # left untouched
    second = run(go())
    assert second["encrypted"] == 0 and second["already"] == 1
    assert harness.query(select(P.CompanyBackup.encryption_key_id).where(P.CompanyBackup.backup_id == good.backup_id))[0][0] == "k1"


def test_a_run_that_stopped_before_the_database_was_updated_heals(harness, keys):
    c = harness.company("Alpha")
    row = store(harness, c, make_zip(), key="bk-0000000012")
    backup_crypto.encrypt_file(svc.file_path(row), svc.file_path(row).with_suffix(".x"), "k1")
    os.replace(svc.file_path(row).with_suffix(".x"), svc.file_path(row))        # file encrypted, row still says plain

    async def go():
        async with harness.Session() as db:
            return await mig.encrypt_existing(db)
    assert run(go())["already"] == 1
    assert harness.query(select(P.CompanyBackup.encryption_key_id).where(P.CompanyBackup.backup_id == row.backup_id))[0][0] == "k1"


def test_rewrap_all_moves_every_backup_to_the_active_key(harness, keys, monkeypatch):
    c = harness.company("Alpha")
    row = store(harness, c, make_zip(), key="bk-0000000013")

    async def go(fn):
        async with harness.Session() as db:
            return await fn(db)
    run(go(mig.encrypt_existing))
    monkeypatch.setattr(settings, "BACKUP_ENCRYPTION_ACTIVE_KEY_ID", "k2")
    assert run(go(mig.rewrap_all))["rewrapped"] == 1
    assert backup_crypto.read_header(svc.file_path(row)) == "k2"
    assert run(go(mig.rewrap_all))["already"] == 1


# ── archive checks and the drill ──

def test_the_archive_is_checked_against_its_manifest(tmp_path):
    ok = tmp_path / "ok.zip"
    ok.write_bytes(make_zip())
    assert backup_archive.validate_archive(ok)["records"]["ledgers"] == 1
    wrong = tmp_path / "wrong.zip"
    wrong.write_bytes(make_zip(records={"groups": 5, "ledgers": 1, "vouchers": 0}))
    with pytest.raises(backup_archive.ArchiveError):
        backup_archive.validate_archive(wrong)
    junk = tmp_path / "junk.zip"
    junk.write_bytes(b"not a zip")
    with pytest.raises(backup_archive.ArchiveError):
        backup_archive.validate_archive(junk)


def test_the_drill_reports_a_good_backup_then_a_damaged_one(harness, keys):
    c = harness.company("Alpha")
    row = store(harness, c, make_zip(), key="bk-0000000020")

    async def drill():
        async with harness.Session() as db:
            return await backup_drill.drill_company(db, c.company_id)
    assert run(drill()).ok is True
    svc.file_path(row).write_bytes(b"corrupt")
    result = run(drill())
    assert result.ok is False and result.problem


def test_a_failed_drill_shows_in_sync_health(harness, keys):
    c = harness.company("Alpha")
    role = harness.role("Admin")
    harness.user(c, role, "owner")
    store(harness, c, b"not a zip at all", key="bk-0000000021")

    async def drill():
        async with harness.Session() as db:
            await backup_drill.drill_all(db)
    run(drill())
    client = harness.app(auth.router, sync.router)
    user = harness.query(select(P.User))[0][0]
    health = client.get("/sync/health", headers=bearer(login(client, user.email))).json()
    assert health["backup_drill"]["ok"] is False and health["status"] == "degraded"


# ── restore into a new company ──

@pytest.fixture
def source(harness, keys):
    c = harness.company("Alpha")
    harness.execute(P.Company.__table__.update().where(P.Company.company_id == c.company_id).values(tally_guid="guid-src"))
    role = harness.role("Admin")
    admin = harness.user(c, role, "owner")
    return c, admin


def restore(harness, backup_row, company, admin, name="Alpha (restored)"):
    async def go():
        async with harness.Session() as db:
            b = (await db.execute(select(P.CompanyBackup).where(P.CompanyBackup.backup_id == backup_row.backup_id))).scalars().first()
            src = (await db.execute(select(P.Company).where(P.Company.company_id == company.company_id))).scalars().first()
            return await restore_new.restore_into_new_company(db, b, src, admin.user_id, name)
    return run(go())


def test_restore_makes_a_verified_new_company_and_binds_it_only_when_the_guid_is_free(harness, source):
    c, admin = source
    row = store(harness, c, make_zip())
    result = restore(harness, row, c, admin)
    assert result["verified"] is True and result["company_id"] != c.company_id
    assert result["bound"] is False                    # the source company still holds guid-src
    names = {n for (n,) in harness.query(select(T.MstLedger.name).where(T.MstLedger.company_id == result["company_id"]))}
    assert "Party One" in names
    new = harness.query(select(P.Company).where(P.Company.company_id == result["company_id"]))[0][0]
    assert new.is_active is True and new.tally_guid is None
    # the source company is untouched
    assert harness.query(select(T.MstLedger).where(T.MstLedger.company_id == c.company_id)) == []


def test_restore_binds_when_the_guid_is_free(harness, source):
    c, admin = source
    harness.execute(P.Company.__table__.update().where(P.Company.company_id == c.company_id).values(tally_guid=None))
    row = store(harness, c, make_zip(), key="bk-0000000030")
    result = restore(harness, row, c, admin)
    assert result["verified"] and result["bound"] is True
    new = harness.query(select(P.Company).where(P.Company.company_id == result["company_id"]))[0][0]
    assert new.tally_guid == "guid-src"


def test_a_count_mismatch_leaves_the_new_company_inactive_and_unbound(harness, source):
    c, admin = source
    row = store(harness, c, make_zip(records={"groups": 1, "ledgers": 3, "vouchers": 0}), key="bk-0000000031")
    # the manifest claims three ledgers but the archive holds one: refused before anything is written
    with pytest.raises(restore_new.RestoreRefused):
        restore(harness, row, c, admin)


def test_restore_refuses_a_backup_that_is_not_stored_and_a_wrong_company(harness, source):
    c, admin = source
    row = store(harness, c, make_zip(), key="bk-0000000032")
    harness.execute(P.CompanyBackup.__table__.update().where(P.CompanyBackup.backup_id == row.backup_id).values(status="failed"))
    with pytest.raises(restore_new.RestoreRefused):
        restore(harness, row, c, admin)
    other = store(harness, c, make_zip(), key="bk-0000000033")
    harness.execute(P.Company.__table__.update().where(P.Company.company_id == c.company_id).values(tally_guid="guid-other"))
    with pytest.raises(restore_new.RestoreRefused):
        restore(harness, other, c, admin)


def test_the_endpoint_is_off_by_default_admin_only_and_needs_the_typed_name(harness, source, monkeypatch):
    c, admin = source
    row = store(harness, c, make_zip(), key="bk-0000000034")
    clerk = harness.user(c, harness.role("Clerk"), "clerk")
    client = harness.app(auth.router, backups.router)
    h = bearer(login(client, admin.email))
    body = {"confirm_company_name": "Alpha"}
    url = f"/backups/{row.backup_id}/restore-new-company"
    assert client.post(url, json=body, headers=h).status_code == 403                       # flag off
    monkeypatch.setattr(settings, "BACKUP_RESTORE_NEW_COMPANY_ENABLED", True)
    assert client.post(url, json=body, headers=bearer(login(client, clerk.email))).status_code == 403
    assert client.post(url, json={"confirm_company_name": "wrong"}, headers=h).status_code == 400
    res = client.post(url, json=body, headers=h)
    assert res.status_code == 200 and res.json()["verified"] is True
