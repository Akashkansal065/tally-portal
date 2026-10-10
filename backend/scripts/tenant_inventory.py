"""Print the ownership inventory of the database in .env. Read-only.

    python scripts/tenant_inventory.py            # summary and what blocks enforcing accounts
    python scripts/tenant_inventory.py --json     # the whole report
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import AsyncSessionLocal  # noqa: E402
from app.services.tenant_inventory import blocking_findings, collect_inventory  # noqa: E402


async def main() -> None:
    async with AsyncSessionLocal() as db:
        report = await collect_inventory(db)
    if "--json" in sys.argv:
        print(json.dumps(report, indent=2, default=str))
        return

    print(f"Accounts: {len(report['accounts'])}")
    print(f"Companies: {len(report['companies'])}")
    for c in report["companies"]:
        print(f"  #{c['company_id']} {c['name']!r} account={c['account_id']} guid={c['tally_guid'] or '-'} "
              f"ledgers={c['ledgers']} items={c['stock_items']} vouchers={c['vouchers']}")
    print(f"Users: {len(report['users'])}")
    for u in report["users"]:
        print(f"  #{u['user_id']} {u['email']} role={u['role']} account={u['account_id']} "
              f"home=#{u['home_company_id']} grants={u['granted_company_ids']}")
    print("Unused tables with rows:", {k: v for k, v in report["unused_table_rows"].items() if v} or "none")

    findings = blocking_findings(report)
    print("\nBefore accounts can be enforced:" if findings else "\nNothing blocks enforcing accounts.")
    for finding in findings:
        print(f"  - {finding}")


if __name__ == "__main__":
    asyncio.run(main())
