"""A company has one import running at a time: a second one arriving meanwhile is refused at once, not queued
behind the first, and another company's import is not held up by the refusal."""
import pytest
from app.core import sync_guard
from app.core.sync_guard import SyncBusy, company_sync_guard, lock_name
from tests.conftest import run
from tests.test_sync_company_binding import GUID_A, GUID_B, LEDGER_EXPORT, groups_by_company, seed

XML = {"Content-Type": "text/xml"}


def test_a_second_import_of_the_same_company_is_refused_while_one_runs(harness):
    async def scenario():
        async with harness.Session() as db:
            async with company_sync_guard(db, 7):
                with pytest.raises(SyncBusy):
                    async with company_sync_guard(db, 7):
                        pass
                async with company_sync_guard(db, 8):      # another company is not in its way
                    pass
            async with company_sync_guard(db, 7):          # free again once the first has finished
                pass
    run(scenario())
    assert sync_guard._importing == set()


def test_the_hold_ends_when_the_import_fails(harness):
    async def scenario():
        async with harness.Session() as db:
            with pytest.raises(RuntimeError):
                async with company_sync_guard(db, 7):
                    raise RuntimeError("import blew up")
            async with company_sync_guard(db, 7):
                pass
    run(scenario())
    assert sync_guard._importing == set()


def test_inbound_answers_busy_instead_of_importing_twice(harness):
    client, headers, _, alpha, beta = seed(harness)
    sync_guard._importing.add(alpha.company_id)            # Alpha's earlier push is still being imported
    try:
        busy = client.post("/sync/inbound", content=LEDGER_EXPORT, headers={**headers, **XML, "X-Tally-Company-GUID": GUID_A})
        other = client.post("/sync/inbound", content=LEDGER_EXPORT, headers={**headers, **XML, "X-Tally-Company-GUID": GUID_B})
    finally:
        sync_guard._importing.discard(alpha.company_id)

    assert busy.status_code == 409 and busy.headers["X-Sync-Reason"] == "sync_in_progress"
    assert other.status_code == 200 and other.json()["status"] == "success"
    assert groups_by_company(harness) == {beta.company_id}  # nothing of the refused push was stored

    again = client.post("/sync/inbound", content=LEDGER_EXPORT, headers={**headers, **XML, "X-Tally-Company-GUID": GUID_A})
    assert again.status_code == 200 and again.json()["status"] == "success"
    assert groups_by_company(harness) == {alpha.company_id, beta.company_id}
    assert sync_guard._importing == set()


def test_lock_names_keep_databases_and_companies_apart():
    assert lock_name("defaultdb", 1) != lock_name("defaultdb", 2) != lock_name("mytally_db", 2)
    assert len(lock_name("d" * 200, 10 ** 12)) <= 64
