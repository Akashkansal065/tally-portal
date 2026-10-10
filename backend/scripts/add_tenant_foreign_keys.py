"""Add the foreign keys for the owner columns that startup added to tables which already existed.

The startup schema sync adds a missing column as a plain column: no foreign key. This adds the keys, on MySQL
only. Safe to run again: a key that is already there is left alone, and a column holding a value its parent
table does not have is reported and skipped, never changed.

    python scripts/add_tenant_foreign_keys.py            # show what would be done
    python scripts/add_tenant_foreign_keys.py --apply    # do it
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import engine  # noqa: E402

PORTAL = settings.PORTAL_DATABASE_NAME
# (table, column, parent table, parent column, what happens to the row when the parent goes)
FOREIGN_KEYS = (
    ("users", "account_id", "accounts", "account_id", "SET NULL"),
    ("companies", "account_id", "accounts", "account_id", "SET NULL"),
    ("roles", "account_id", "accounts", "account_id", "SET NULL"),
    ("portal_attendance", "account_id", "accounts", "account_id", "SET NULL"),
    ("portal_attendance_locations", "account_id", "accounts", "account_id", "SET NULL"),
    ("temp_orders", "company_id", "companies", "company_id", "CASCADE"),
    ("sales_visits", "company_id", "companies", "company_id", "CASCADE"),
    ("shop_payments", "company_id", "companies", "company_id", "CASCADE"),
    ("expenses", "company_id", "companies", "company_id", "CASCADE"),
)


async def main(apply: bool) -> None:
    if "mysql" not in settings.DATABASE_URL:
        print("This script is for the MySQL database; nothing to do here.")
        return
    async with engine.begin() as conn:
        for table, column, parent, parent_column, on_delete in FOREIGN_KEYS:
            name = f"fk_{table}_{column}"
            has_column = (await conn.execute(text(
                "SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA = :schema AND TABLE_NAME = :table AND COLUMN_NAME = :column"
            ), {"schema": PORTAL, "table": table, "column": column})).scalar()
            if not has_column:
                print(f"skip   {table}.{column}: the column is not there yet (start the backend once first)")
                continue
            existing = (await conn.execute(text(
                "SELECT COUNT(*) FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE "
                "WHERE TABLE_SCHEMA = :schema AND TABLE_NAME = :table AND COLUMN_NAME = :column "
                "AND REFERENCED_TABLE_NAME = :parent"
            ), {"schema": PORTAL, "table": table, "column": column, "parent": parent})).scalar()
            if existing:
                print(f"ok     {table}.{column} -> {parent}.{parent_column} already has its foreign key")
                continue
            orphans = (await conn.execute(text(
                f"SELECT COUNT(*) FROM `{PORTAL}`.`{table}` t "
                f"LEFT JOIN `{PORTAL}`.`{parent}` p ON p.`{parent_column}` = t.`{column}` "
                f"WHERE t.`{column}` IS NOT NULL AND p.`{parent_column}` IS NULL"
            ))).scalar()
            if orphans:
                print(f"STOP   {table}.{column}: {orphans} row(s) name a {parent} row that does not exist; fix those first")
                continue
            statement = (
                f"ALTER TABLE `{PORTAL}`.`{table}` ADD CONSTRAINT `{name}` FOREIGN KEY (`{column}`) "
                f"REFERENCES `{PORTAL}`.`{parent}` (`{parent_column}`) ON DELETE {on_delete}"
            )
            if apply:
                await conn.execute(text(statement))
                print(f"added  {table}.{column} -> {parent}.{parent_column}")
            else:
                print(f"would  {statement}")
    if not apply:
        print("\nNothing was changed. Run again with --apply to add the keys.")


if __name__ == "__main__":
    asyncio.run(main("--apply" in sys.argv))
