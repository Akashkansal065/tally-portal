"""The daily cleanup deletes old successful sync logs and keeps everything an admin still needs."""
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.dialects import mysql

import app.models.portal_core as P
from app.core.datetime_utils import get_ist_now
from app.services.daily_cleanup import SYNC_LOG_DELETE_BATCH, purge_old_sync_logs, sync_log_purge_batch
from tests.conftest import run


def test_old_successful_logs_are_purged_and_failures_kept(harness):
    company = harness.company()
    now = get_ist_now()

    def log(name, status, days_ago):
        harness.add(P.SyncTrafficLog(company_id=company.company_id, entity_type="Voucher", action="Create",
                                     entity_name=name, status=status, created_at=now - timedelta(days=days_ago)))
    log("old success", "SUCCESS", 40)
    log("older success", "SUCCESS", 90)
    log("recent success", "SUCCESS", 5)
    log("old failure", "FAILED", 40)
    log("old exception", "EXCEPTION", 120)

    async def purge():
        async with harness.Session() as db:
            return await purge_old_sync_logs(db)

    assert run(purge()) == 2
    remaining = {row[0] for row in harness.query(select(P.SyncTrafficLog.entity_name))}
    assert remaining == {"recent success", "old failure", "old exception"}


def test_mysql_purge_deletes_in_limited_batches():
    statement = sync_log_purge_batch(get_ist_now()).compile(dialect=mysql.dialect(), compile_kwargs={"literal_binds": True})
    assert str(statement).endswith(f"LIMIT {SYNC_LOG_DELETE_BATCH}")
