"""WS-9: durable receipts for /sync/inbound."""
from datetime import timedelta

import pytest
from sqlalchemy import select

import app.models.portal_core as P
from app.core import sync_guard
from app.core.datetime_utils import get_ist_now
from app.services import inbound_receipts
from tests.conftest import run
from tests.test_sync_company_binding import GUID_A, GUID_B, LEDGER_EXPORT, groups_by_company, seed

XML = {"Content-Type": "text/xml"}
KEY = "guid-aaaa:Ledgers:0-5:abc123def456"


def post(client, headers, key=KEY, body=LEDGER_EXPORT, guid=GUID_A, extra=None):
    h = {**headers, **XML, "X-Tally-Company-GUID": guid, **(extra or {})}
    if key:
        h["Idempotency-Key"] = key
    return client.post("/sync/inbound", content=body, headers=h)


def receipts(harness):
    return [r[0] for r in harness.query(select(P.SyncInboundReceipt).order_by(P.SyncInboundReceipt.receipt_id))]


def count_imports(monkeypatch):
    from app.routers import sync
    calls = []
    real = sync.import_tally_xml

    async def counting(*a, **kw):
        calls.append(1)
        return await real(*a, **kw)
    monkeypatch.setattr(sync, "import_tally_xml", counting)
    return calls


def test_a_lost_response_is_replayed_without_importing_again(harness, monkeypatch):
    client, headers, _, alpha, _ = seed(harness)
    calls = count_imports(monkeypatch)
    first = post(client, headers)
    again = post(client, headers)                       # the agent never saw the first answer
    assert first.status_code == again.status_code == 200
    assert again.headers["Idempotent-Replay"] == "true" and again.json() == first.json()
    assert len(calls) == 1
    (r,) = receipts(harness)
    assert (r.state, r.company_id, r.attempts) == ("DONE", alpha.company_id, 1)


def test_a_key_reused_with_a_different_body_is_refused(harness, monkeypatch):
    client, headers, *_ = seed(harness)
    calls = count_imports(monkeypatch)
    post(client, headers)
    other = post(client, headers, body=LEDGER_EXPORT.replace("Imported Group", "Another Group"))
    assert other.status_code == 422 and len(calls) == 1
    # force is part of what the key stands for
    assert post(client, headers, extra={"x-force-sync": "true"}).status_code == 422


def test_keys_are_private_to_a_company(harness, monkeypatch):
    client, headers, _, alpha, beta = seed(harness)
    calls = count_imports(monkeypatch)
    assert post(client, headers, guid=GUID_A).status_code == 200
    res = post(client, headers, guid=GUID_B)            # same key, another company: not a replay
    assert res.status_code == 200 and "Idempotent-Replay" not in res.headers and len(calls) == 2
    assert {r.company_id for r in receipts(harness)} == {alpha.company_id, beta.company_id}


def test_a_duplicate_while_the_first_is_processing_is_told_to_wait(harness, monkeypatch):
    client, headers, _, alpha, _ = seed(harness)
    calls = count_imports(monkeypatch)
    sha = inbound_receipts.payload_hash(LEDGER_EXPORT.encode(), False)
    harness.add(P.SyncInboundReceipt(company_id=alpha.company_id, idempotency_key=KEY, payload_sha256=sha,
                                     state="PROCESSING", started_at=get_ist_now()))
    res = post(client, headers)
    assert res.status_code == 409 and res.headers["X-Sync-Reason"] == "sync_in_progress" and calls == []


def test_an_interrupted_processing_receipt_is_taken_over(harness, monkeypatch):
    client, headers, _, alpha, _ = seed(harness)
    calls = count_imports(monkeypatch)
    sha = inbound_receipts.payload_hash(LEDGER_EXPORT.encode(), False)
    harness.add(P.SyncInboundReceipt(company_id=alpha.company_id, idempotency_key=KEY, payload_sha256=sha,
                                     state="PROCESSING", started_at=get_ist_now() - timedelta(hours=1)))
    res = post(client, headers)
    assert res.status_code == 200 and res.json()["status"] == "success" and len(calls) == 1
    (r,) = receipts(harness)
    assert (r.state, r.attempts) == ("DONE", 2)
    assert groups_by_company(harness) == {alpha.company_id}


def test_a_failed_import_can_be_retried_with_the_same_key(harness, monkeypatch):
    client, headers, _, alpha, _ = seed(harness)
    from app.routers import sync
    real = sync.import_tally_xml
    state = {"fail": True}

    async def flaky(*a, **kw):
        if state["fail"]:
            raise RuntimeError("database went away")
        return await real(*a, **kw)
    monkeypatch.setattr(sync, "import_tally_xml", flaky)
    assert post(client, headers).status_code == 500
    assert [r.state for r in receipts(harness)] == ["FAILED"]
    state["fail"] = False
    ok = post(client, headers)
    assert ok.status_code == 200 and ok.json()["status"] == "success"
    assert [r.state for r in receipts(harness)] == ["DONE"]


def test_a_busy_company_leaves_the_receipt_free_to_retry(harness):
    client, headers, _, alpha, _ = seed(harness)
    sync_guard._importing.add(alpha.company_id)
    try:
        busy = post(client, headers)
    finally:
        sync_guard._importing.discard(alpha.company_id)
    assert busy.status_code == 409
    assert [r.state for r in receipts(harness)] == ["FAILED"]
    assert post(client, headers).status_code == 200


def test_an_old_receipt_is_not_replayed_and_a_forced_upload_always_imports(harness, monkeypatch):
    client, headers, _, alpha, _ = seed(harness)
    calls = count_imports(monkeypatch)
    post(client, headers)
    harness.execute(P.SyncInboundReceipt.__table__.update().values(
        finished_at=get_ist_now() - inbound_receipts.REPLAY_WINDOW - timedelta(minutes=1)))
    assert "Idempotent-Replay" not in post(client, headers).headers      # past the window: imported again
    assert len(calls) == 2
    forced = post(client, headers, key="forced-key-0001", extra={"x-force-sync": "true"})
    forced2 = post(client, headers, key="forced-key-0001", extra={"x-force-sync": "true"})
    assert forced.status_code == forced2.status_code == 200 and len(calls) == 4


def test_no_key_means_no_receipt_and_a_bad_key_is_ignored(harness):
    client, headers, *_ = seed(harness)
    assert post(client, headers, key=None).status_code == 200
    assert post(client, headers, key="short").status_code == 200
    assert receipts(harness) == []


def test_two_concurrent_requests_with_one_key_import_once(harness, monkeypatch):
    """The unique key lets one request in; the other finds its row and is told to wait."""
    client, headers, _, alpha, _ = seed(harness)
    sha = inbound_receipts.payload_hash(LEDGER_EXPORT.encode(), False)

    async def race():
        async with harness.Session() as a, harness.Session() as b:
            first = await inbound_receipts.begin(a, alpha.company_id, KEY, sha, False)
            second = await inbound_receipts.begin(b, alpha.company_id, KEY, sha, False)
            return first, second
    first, second = run(race())
    assert first[0] == inbound_receipts.RUN and second[0] == inbound_receipts.BUSY
