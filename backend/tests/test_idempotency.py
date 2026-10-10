"""A write is carried out once however often it is sent, and the sync queue holds one pending row per record."""
import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.idempotency import IdempotencyMiddleware
from app.models.portal_core import SyncQueue


def _counting_app():
    app = FastAPI()
    calls = {"n": 0}

    @app.post("/things")
    async def create_thing(payload: dict):
        calls["n"] += 1
        await asyncio.sleep(0.05)
        return {"created": calls["n"], "name": payload.get("name")}

    @app.post("/broken")
    async def broken():
        calls["n"] += 1
        raise RuntimeError("boom")

    app.add_middleware(IdempotencyMiddleware)
    return app, calls


def test_same_idempotency_key_runs_the_write_once():
    app, calls = _counting_app()
    client = TestClient(app)
    headers = {"Idempotency-Key": "k1", "Authorization": "Bearer a"}

    first = client.post("/things", json={"name": "x"}, headers=headers)
    second = client.post("/things", json={"name": "x"}, headers=headers)

    assert first.json() == second.json() == {"created": 1, "name": "x"}
    assert second.headers["idempotent-replay"] == "true"
    assert calls["n"] == 1
    # Another key, or another caller with the same key, is a different write
    assert client.post("/things", json={"name": "x"}, headers={**headers, "Idempotency-Key": "k2"}).json()["created"] == 2
    assert client.post("/things", json={"name": "x"}, headers={**headers, "Authorization": "Bearer b"}).json()["created"] == 3


def test_identical_overlapping_writes_run_once_without_a_key():
    import httpx
    app, calls = _counting_app()

    async def go():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            replies = await asyncio.gather(*[client.post("/things", json={"name": "x"}) for _ in range(3)])
            later = await client.post("/things", json={"name": "x"})
            return replies, later

    replies, later = asyncio.run(go())
    assert [r.json() for r in replies] == [{"created": 1, "name": "x"}] * 3
    # Without a key nothing is remembered once the request has finished
    assert later.json()["created"] == 2
    assert calls["n"] == 2


def test_failed_write_is_not_remembered():
    app, calls = _counting_app()
    client = TestClient(app, raise_server_exceptions=False)
    headers = {"Idempotency-Key": "k1"}
    assert client.post("/broken", headers=headers).status_code == 500
    assert client.post("/broken", headers=headers).status_code == 500
    assert calls["n"] == 2


def test_a_key_reused_with_a_different_body_is_refused():
    app, calls = _counting_app()
    client = TestClient(app)
    headers = {"Idempotency-Key": "k1"}
    assert client.post("/things", json={"name": "x"}, headers=headers).json() == {"created": 1, "name": "x"}

    other = client.post("/things", json={"name": "y"}, headers=headers)

    assert other.status_code == 422 and "idempotent-replay" not in other.headers
    assert calls["n"] == 1


def test_a_refused_write_is_not_replayed_for_its_key():
    app, calls = _counting_app()

    @app.post("/picky")
    async def picky():
        from fastapi import HTTPException
        calls["n"] += 1
        if calls["n"] == 1:
            raise HTTPException(status_code=409, detail="not yet")
        return {"ok": True}

    client = TestClient(app)
    headers = {"Idempotency-Key": "k1"}
    assert client.post("/picky", headers=headers).status_code == 409
    assert client.post("/picky", headers=headers).json() == {"ok": True}


def _pending(harness, record_id):
    rows = harness.query(select(SyncQueue).where(SyncQueue.record_id == record_id).order_by(SyncQueue.sync_id))
    return [(r[0].action, r[0].is_processed, r[0].status, (r[0].snapshot_data or {}).get("tally_name")) for r in rows]


def test_sync_queue_keeps_one_pending_row_per_record_and_action(harness):
    company = harness.company()
    cid = company.company_id

    harness.add(SyncQueue(company_id=cid, record_type="StockItem", record_id=7, action="Alter",
                          snapshot_data={"tally_name": "Old Name"}))
    harness.add(SyncQueue(company_id=cid, record_type="StockItem", record_id=7, action="Alter"))
    # Another record, and the same record id of another type, are untouched
    harness.add(SyncQueue(company_id=cid, record_type="StockItem", record_id=8, action="Alter"))
    harness.add(SyncQueue(company_id=cid, record_type="Unit", record_id=7, action="Alter"))

    rows = harness.query(select(SyncQueue).where(SyncQueue.record_type == "StockItem", SyncQueue.record_id == 7)
                         .order_by(SyncQueue.sync_id))
    first, second = rows[0][0], rows[1][0]
    assert (first.is_processed, first.status) == (True, "SUPERSEDED")
    # The second edit still has to rename from the name Tally was left with
    assert (bool(second.is_processed), second.snapshot_data) == (False, {"tally_name": "Old Name"})
    others = harness.query(select(SyncQueue).where(SyncQueue.is_processed == True))
    assert len(others) == 1

    # A delete makes the pending alter pointless and inherits the name to delete in Tally
    harness.add(SyncQueue(company_id=cid, record_type="StockItem", record_id=7, action="Delete",
                          snapshot_data={"tally_name": "New Name"}))
    rows = [r[0] for r in harness.query(select(SyncQueue).where(SyncQueue.record_type == "StockItem", SyncQueue.record_id == 7)
                                        .order_by(SyncQueue.sync_id))]
    assert [(r.action, bool(r.is_processed)) for r in rows] == [("Alter", True), ("Alter", True), ("Delete", False)]
    assert rows[2].snapshot_data == {"tally_name": "Old Name"}
