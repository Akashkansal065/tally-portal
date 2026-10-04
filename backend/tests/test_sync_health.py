"""/sync/health: grouped counts give the same numbers, and admins polling it share one result for 30 seconds."""
from datetime import datetime, timedelta

from sqlalchemy import update

import app.models.portal_core as P
from app.routers import auth, sync
from tests.conftest import bearer, login


def seed(harness):
    company = harness.company()
    other = harness.company("Beta")
    admin = harness.user(company, harness.role("Admin"), "owner")
    start = datetime(2026, 10, 1, 9, 0)

    queue = [(True, 3), (False, 3)]  # (is_processed, rows); the last False row becomes NULL below
    sync_id = 1
    for processed, rows in queue:
        for _ in range(rows):
            harness.add(P.SyncQueue(sync_id=sync_id, company_id=company.company_id, record_type="Voucher",
                                    record_id=sync_id, action="Create", is_processed=processed))
            sync_id += 1
    # The ORM applies the column default for None on insert, so set the NULL flag directly
    harness.execute(update(P.SyncQueue).where(P.SyncQueue.is_processed.is_(False), P.SyncQueue.sync_id == 6)
                    .values(is_processed=None))

    statuses = ["SUCCESS"] * 4 + ["FAILED", "TIMEOUT", "EXCEPTION", "CONFLICT"]
    for i, status in enumerate(statuses):
        harness.add(P.SyncTrafficLog(company_id=company.company_id, entity_type="Voucher", entity_name=f"Sales #{i}",
                                     action="Create", status=status, outbound_payload="<ENVELOPE/>" * 100,
                                     created_at=start + timedelta(minutes=i)))
    # Another company's failures must not show up
    harness.add(P.SyncTrafficLog(company_id=other.company_id, entity_type="Voucher", action="Create", status="FAILED"))
    harness.add(P.DeletedRecordAudit(company_id=company.company_id, entity_type="Voucher", record_id=9,
                                     tally_sync_status="NOT_DELETED_IN_TALLY"))
    client = harness.app(auth.router, sync.router)
    return client, bearer(login(client, admin.email))


def test_counts_and_recent_logs(harness):
    client, headers = seed(harness)

    health = client.get("/sync/health", headers=headers).json()

    assert health["pending_queue_count"] == 2
    assert health["synced_queue_count"] == 3
    assert health["total_success_traffic"] == 4
    assert health["total_failed_traffic"] == 2  # FAILED + TIMEOUT
    assert health["total_exception_traffic"] == 1
    assert health["unreconciled_deleted_count"] == 1
    assert health["total_sync_issues"] == 4
    assert health["status"] == "degraded"
    assert [log["entity_name"] for log in health["recent_traffic"]] == [f"Sales #{i}" for i in (7, 6, 5, 4, 3)]
    assert "outbound_payload" not in health["recent_traffic"][0]


def test_second_poll_is_served_from_cache(harness):
    client, headers = seed(harness)
    first = client.get("/sync/health", headers=headers).json()

    with harness.count_queries() as statements:
        second = client.get("/sync/health", headers=headers).json()

    assert second == first
    assert statements == []


def test_clearing_resolved_logs_updates_health_immediately(harness):
    client, headers = seed(harness)
    assert client.get("/sync/health", headers=headers).json()["total_sync_issues"] == 4

    assert client.post("/sync/traffic-logs/clear-resolved", headers=headers).status_code == 200

    health = client.get("/sync/health", headers=headers).json()
    assert health["total_sync_issues"] == 0
    assert health["status"] == "healthy"
