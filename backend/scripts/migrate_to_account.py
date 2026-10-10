"""Move this server's existing data into one account. One script for the whole of step 2.

It uses the database connection in backend/.env, the same one the backend runs on. It creates no user: the
people who sign in today keep their logins and roles, and every admin gets the "Manage sync agent" permission.
It deletes nothing.

    python scripts/migrate_to_account.py                 # show what is there and what would change; changes nothing
    python scripts/migrate_to_account.py --apply         # do it
    python scripts/migrate_to_account.py --json          # the full ownership report, for a closer look

Later, once everything has run on the new version for a while (see the rollout runbook):

    python scripts/migrate_to_account.py --enforce           # show the rules the database would start refusing on
    python scripts/migrate_to_account.py --enforce --apply   # switch them on

If the enforce look reports STOP lines for duplicate Tally records, merge them first:

    python scripts/migrate_to_account.py --merge-duplicates           # show what would be kept and removed
    python scripts/migrate_to_account.py --merge-duplicates --apply   # do it (removes rows from the mirror only;
                                                                      # nothing is sent to Tally)

    --name "Sneh Distributors"    name for the account (default: the first company's name)

Start the backend once on the new code first, so the new columns and tables exist. Running it twice is safe.
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings  # noqa: E402
from app.core.database import AsyncSessionLocal, engine  # noqa: E402
from app.services.tenant_inventory import blocking_findings, collect_inventory  # noqa: E402
from app.services.tenant_migration import (  # noqa: E402
    MigrationRefused, add_foreign_keys, allow_role_names_per_account, enforce_account_rules,
    merge_duplicate_tally_rows, migrate_to_single_account, remaining_problems,
)


def option(name: str):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv and sys.argv.index(name) + 1 < len(sys.argv) else None


def print_inventory(report) -> None:
    print(f"Accounts: {len(report['accounts'])}")
    print(f"Companies: {len(report['companies'])}")
    for c in report["companies"]:
        print(f"  #{c['company_id']} {c['name']!r} account={c['account_id']} guid={c['tally_guid'] or '-'} "
              f"ledgers={c['ledgers']} items={c['stock_items']} vouchers={c['vouchers']}")
    print(f"Users: {len(report['users'])}")
    for u in report["users"]:
        print(f"  #{u['user_id']} {u['email']} role={u['role']} account={u['account_id']} "
              f"home=#{u['home_company_id']} grants={u['granted_company_ids']}")


async def enforce(apply: bool) -> None:
    """Make the database itself refuse ownerless and duplicate rows. Only once the data is ready for it."""
    if "mysql" not in settings.DATABASE_URL:
        print("Enforcement is for the MySQL database; nothing to do here.")
        return
    async with AsyncSessionLocal() as db:
        report = await collect_inventory(db)
        blocking = [f for f in blocking_findings(report) if "no Tally GUID" not in f]
    if blocking:
        print("Not ready to enforce. Deal with these first (run without --enforce to give rows their owner):")
        for finding in blocking:
            print(f"  - {finding}")
        sys.exit(1)
    print("== Switching the rules on ==" if apply else "== What enforcing would do (nothing is changed) ==")
    async with engine.begin() as conn:
        for line in await enforce_account_rules(conn, apply):
            print(f"  {line}")
    if apply:
        print("\nNow set ACCOUNTS_ENFORCED=true in backend/.env and restart the backend.")
    else:
        print("\nNothing was changed. Run again with --enforce --apply to do it. Do it at a quiet time: making a key")
        print("unique on a large table (vouchers) can take minutes and holds the table while it runs.")


async def merge_duplicates(apply: bool) -> None:
    """Keep one row where a company holds the same Tally record twice. Removes rows, so it is its own step."""
    if "mysql" not in settings.DATABASE_URL:
        print("Merging duplicates is for the MySQL database; nothing to do here.")
        return
    print("== Merging duplicate Tally records ==" if apply else "== Duplicate Tally records (nothing is changed) ==")
    async with engine.begin() as conn:
        for line in await merge_duplicate_tally_rows(conn, apply):
            print(f"  {line}")
    if not apply:
        print("\nNothing was changed. Back up the Tally mirror database, then run again with --merge-duplicates --apply.")
        print("Rows are removed from the mirror only: nothing is sent to Tally, which holds each record once already.")


async def main() -> None:
    apply = "--apply" in sys.argv
    if "--merge-duplicates" in sys.argv:
        await merge_duplicates(apply)
        return
    if "--enforce" in sys.argv:
        await enforce(apply)
        return
    async with AsyncSessionLocal() as db:
        if "--json" in sys.argv:
            print(json.dumps(await collect_inventory(db), indent=2, default=str))
            return

        print("== What is there now ==")
        print_inventory(await collect_inventory(db))

        print("\n== Moving everything into one account ==" if apply else "\n== What would change (nothing is saved) ==")
        try:
            changed = await migrate_to_single_account(db, option("--name"))
        except MigrationRefused as refusal:
            await db.rollback()
            print(f"Refused, nothing changed: {refusal}")
            sys.exit(1)
        print(f"  account: {changed['account']}")
        for key in ("companies", "users", "roles", "attendance", "attendance_locations",
                    "temp_orders", "sales_visits", "shop_payments", "expenses"):
            print(f"  {key}: {changed[key]} row(s) given their owner")
        print(f"  settings: {changed['settings']} copied to the account")
        print(f"  admins: {', '.join(changed['admins'])}")
        print(f"  'Manage sync agent' newly granted to: {', '.join(changed['sync_agent_granted_to']) or 'nobody (all had it)'}")

        problems = await remaining_problems(db)
        report_after = await collect_inventory(db)
        if apply and not problems:
            await db.commit()
            print("  Saved.")
        else:
            await db.rollback()
            if apply:
                print("  NOT saved, because the checks below failed:")
        for problem in problems:
            print(f"  ! {problem}")

    print("\n== Foreign keys ==")
    if "mysql" not in settings.DATABASE_URL:
        print("  (MySQL only; skipped on this database)")
    elif apply and problems:
        print("  Skipped: the data was not saved.")
    else:
        async with engine.begin() as conn:
            for line in await add_foreign_keys(conn, apply):
                print(f"  {line}")
            # Lets each account have its own roles: without it a second customer cannot sign up
            for line in await allow_role_names_per_account(conn, apply):
                print(f"  {line}")

    # What is still open after this script: it is for later steps, not a failure here
    later = [f for f in blocking_findings(report_after) if "have no owner yet" not in f]
    print("\n== Still to deal with before the unique keys are switched on ==")
    for finding in later or ["Nothing."]:
        print(f"  - {finding}")
    if not apply:
        print("\nNothing was changed. Run again with --apply to do it.")


if __name__ == "__main__":
    asyncio.run(main())
