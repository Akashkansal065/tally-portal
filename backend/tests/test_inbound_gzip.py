"""WS-8: /sync/inbound takes gzip, with a hard cap on what it will hold after decompression."""
import gzip
import zlib

from app.core.config import settings
from tests.test_sync_company_binding import GUID_A, LEDGER_EXPORT, groups_by_company, seed

XML = {"Content-Type": "text/xml"}


def post(client, headers, content, extra=None):
    return client.post("/sync/inbound", content=content,
                       headers={**headers, **XML, "X-Tally-Company-GUID": GUID_A, **(extra or {})})


def test_a_gzip_upload_imports_like_the_plain_one(harness):
    client, headers, _, alpha, _ = seed(harness)
    res = post(client, headers, gzip.compress(LEDGER_EXPORT.encode()), {"Content-Encoding": "gzip"})
    assert res.status_code == 200 and res.json()["status"] == "success"
    assert groups_by_company(harness) == {alpha.company_id}


def test_plain_uploads_still_work(harness):
    client, headers, _, alpha, _ = seed(harness)
    assert post(client, headers, LEDGER_EXPORT.encode()).status_code == 200
    assert groups_by_company(harness) == {alpha.company_id}


def test_the_server_says_it_takes_gzip(harness):
    client, headers, *_ = seed(harness)
    body = client.get("/sync/last-alter-id", headers={**headers, "X-Tally-Company-GUID": GUID_A}).json()
    assert body["inbound"]["gzip"] is True and body["inbound"]["max_bytes"] == settings.SYNC_INBOUND_MAX_BYTES


def test_a_decompression_bomb_is_refused_at_the_cap(harness, monkeypatch):
    monkeypatch.setattr(settings, "SYNC_INBOUND_MAX_BYTES", 100_000)
    client, headers, _, alpha, _ = seed(harness)
    bomb = gzip.compress(b"<ENVELOPE>" + b"A" * 50_000_000 + b"</ENVELOPE>")      # tiny on the wire
    assert len(bomb) < 100_000
    res = post(client, headers, bomb, {"Content-Encoding": "gzip"})
    assert res.status_code == 413 and "smaller date ranges" in res.json()["detail"]
    assert groups_by_company(harness) == set()


def test_an_oversized_plain_upload_is_refused(harness, monkeypatch):
    monkeypatch.setattr(settings, "SYNC_INBOUND_MAX_BYTES", 1000)
    client, headers, *_ = seed(harness)
    assert post(client, headers, b"<ENVELOPE>" + b"x" * 5000 + b"</ENVELOPE>").status_code == 413


def test_damaged_or_unknown_encodings_are_refused(harness):
    client, headers, *_ = seed(harness)
    assert post(client, headers, b"not gzip at all", {"Content-Encoding": "gzip"}).status_code == 400
    truncated = gzip.compress(LEDGER_EXPORT.encode())[:-8]
    assert post(client, headers, truncated, {"Content-Encoding": "gzip"}).status_code == 400
    assert post(client, headers, zlib.compress(b"x"), {"Content-Encoding": "br"}).status_code == 415
