"""One-off clean-up (2026-10-11): remove the test sign-up made from the sync agent on 2026-10-10 14:15.

Account 4 "Bhrama Enterprises", its one user "Akash test" (akashkansal065@yopmail.com, user 9), its two roles
(3, 4), its PC sign-in (device 2) and its company #5. Company #5 is a second copy of Bhrama Enterprises (same Tally
GUID as company #1 in account 3); it holds no ledgers, vouchers or app-entered records, only the default currencies,
4 report snapshots, its sync status and its link to device 2. Nothing is sent to Tally.

Run from backend/:
    venv/bin/python scripts/remove_test_account_4.py            checks and saves the rows, deletes nothing
    venv/bin/python scripts/remove_test_account_4.py --apply    the same, then deletes them in one transaction

Every row is saved first to ../../MyTally-backups/db-cleanup/account-4-test-signup-20261011.json. If any count
differs from what was found when this was written, nothing is deleted.
"""
import asyncio
import datetime
import decimal
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import engine  # noqa: E402

P = settings.PORTAL_DATABASE_NAME
# (table, rows to remove, how many there were) in the order they are deleted: rows that point at others first
STEPS = [
    ("permissions", "role_id IN (3, 4)", 25),
    ("user_permission_overrides", "user_id = 9 OR granted_by = 9", 1),
    ("user_company_access", "user_id = 9 OR company_id = 5", 1),
    ("agent_company_links", "company_id = 5 OR device_id = 2", 1),
    ("company_sync_state", "company_id = 5", 1),
    ("report_snapshots", "company_id = 5", 4),
    ("currencies", "company_id = 5", 87),
    ("agent_devices", "device_id = 2", 1),
    ("users", "user_id = 9", 1),
    ("roles", "role_id IN (3, 4) AND account_id = 4", 2),
    ("companies", "company_id = 5 AND account_id = 4", 1),
    ("accounts", "account_id = 4", 1),
]
SAVED_TO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "MyTally-backups", "db-cleanup",
                                        "account-4-test-signup-20261011.json"))


def plain(value):
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return str(value)
    if isinstance(value, bytes):
        return value.hex()
    return value


class Stop(Exception):
    pass


async def main(apply: bool) -> None:
    try:
        async with engine.begin() as c:   # one transaction: nothing is kept unless every check holds
            who = (await c.execute(text(
                f"SELECT u.email, a.name, c.tally_guid FROM `{P}`.users u JOIN `{P}`.accounts a ON a.account_id = u.account_id "
                f"JOIN `{P}`.companies c ON c.company_id = 5 AND c.account_id = 4 WHERE u.user_id = 9 AND a.account_id = 4"))).first()
            if who is None or who[0] != "akashkansal065@yopmail.com" or who[2] != "f0347998-2c19-4a5e-a4ed-01f589cb92a5":
                raise Stop(f"Account 4 is not the test sign-up this script was written for ({who}). Nothing deleted.")
            if (await c.execute(text(f"SELECT COUNT(*) FROM `{P}`.users WHERE role_id IN (3, 4) AND user_id <> 9"))).scalar():
                raise Stop("Someone else holds one of account 4's roles. Nothing deleted.")
            if (await c.execute(text(f"SELECT COUNT(*) FROM `{P}`.sync_queue WHERE company_id = 5"))).scalar():
                raise Stop("Company 5 has changes waiting for Tally. Nothing deleted.")

            saved = {}
            for table, where, expected in STEPS:
                rows = (await c.execute(text(f"SELECT * FROM `{P}`.`{table}` WHERE {where}"))).mappings().all()
                if len(rows) != expected:
                    raise Stop(f"{table}: {len(rows)} rows, expected {expected}. Nothing deleted.")
                saved[table] = [{k: plain(v) for k, v in row.items()} for row in rows]
            os.makedirs(os.path.dirname(SAVED_TO), exist_ok=True)
            with open(SAVED_TO, "w") as f:
                json.dump(saved, f, indent=1)
            print(f"Checks passed. {sum(len(v) for v in saved.values())} rows saved to {SAVED_TO}")

            if not apply:
                raise Stop("Nothing deleted (run again with --apply to delete).")
            await c.execute(text(f"UPDATE `{P}`.accounts SET created_by_user_id = NULL WHERE account_id = 4"))
            for table, where, expected in STEPS:
                deleted = (await c.execute(text(f"DELETE FROM `{P}`.`{table}` WHERE {where}"))).rowcount
                if deleted != expected:
                    raise Stop(f"{table}: deleting removed {deleted} rows, expected {expected}. All undone.")
                print(f"  deleted {deleted:3d} from {table}")
        print("Done: account 4 is removed.")
    except Stop as why:
        print(why)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main("--apply" in sys.argv[1:]))
