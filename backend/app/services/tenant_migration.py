"""Move a server that has served one customer into one account.

Everything that exists (companies, users, roles, field-sales rows, attendance) becomes that account's. No user is
created and no row is deleted: existing users keep their logins and roles, and every admin is given the
"Manage sync agent" permission. Safe to run again: rows that already carry the account are left alone, and the
run stops before changing anything if it finds more than one account.
"""
from typing import Any, Dict, Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

import app.routers.attendance as attendance_models
import app.routers.expenses as expenses_models
import app.routers.orders as orders_models
import app.routers.visits as visits_models
from app.core.config import settings
from app.core.permissions import ADMIN_ROLE_NAMES
from app.models.portal_core import (
    Account, Company, Module, Role, ShopPayment, User, UserPermissionOverride,
)
from app.models.tally_core import MstLedger

SYNC_AGENT_MODULE = "sync_agent"
PORTAL = settings.PORTAL_DATABASE_NAME

# (table, column, parent table, parent column, what happens to the row when the parent goes).
# Startup adds a column that is missing from an existing table as a plain column, so these keys are added here.
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


class MigrationRefused(Exception):
    """The data is not what this migration is for; nothing was changed."""


async def _fill(db: AsyncSession, table, column: str, value) -> int:
    """Set column to value on the rows where it is still empty. Returns how many rows that was."""
    result = await db.execute(update(table).where(table.c[column].is_(None)).values({column: value}))
    return result.rowcount or 0


async def migrate_to_single_account(db: AsyncSession, account_name: Optional[str] = None) -> Dict[str, Any]:
    """Does the work inside the caller's transaction and returns what it changed. The caller commits, or rolls
    back to see what a run would do."""
    accounts = (await db.execute(select(Account).order_by(Account.account_id))).scalars().all()
    if len(accounts) > 1:
        raise MigrationRefused(
            f"{len(accounts)} accounts exist already. This migration is for a server with one customer; "
            "with several, each row's account has to be decided by hand.")
    companies = (await db.execute(select(Company).order_by(Company.company_id))).scalars().all()
    if not companies:
        raise MigrationRefused("There is no company to move into an account.")

    changed: Dict[str, Any] = {}
    if accounts:
        account = accounts[0]
        changed["account"] = f"existing #{account.account_id} {account.name!r}"
    else:
        account = Account(name=(account_name or companies[0].name).strip(), status="active")
        db.add(account)
        await db.flush()
        changed["account"] = f"created #{account.account_id} {account.name!r}"
    account_id = account.account_id
    changed["account_id"] = account_id

    changed["companies"] = await _fill(db, Company.__table__, "account_id", account_id)
    changed["users"] = await _fill(db, User.__table__, "account_id", account_id)
    changed["roles"] = await _fill(db, Role.__table__, "account_id", account_id)
    changed["attendance"] = await _fill(db, attendance_models.Attendance.__table__, "account_id", account_id)
    changed["attendance_locations"] = await _fill(db, attendance_models.AttendanceLocationLog.__table__, "account_id", account_id)

    # Field-sales rows get the company they were made for: the ledger's company where the row names a ledger,
    # otherwise the company its owner has active (which is where the app lists it today)
    owner_company = lambda table: select(User.company_id).where(User.user_id == table.c.user_id).scalar_subquery()  # noqa: E731
    for model in (orders_models.TempOrder, visits_models.SalesVisit, ShopPayment, expenses_models.Expense):
        table = model.__table__
        rows = 0
        if "ledger_id" in table.c:
            rows += (await db.execute(
                update(table).where(table.c.company_id.is_(None), table.c.ledger_id.isnot(None))
                .values(company_id=select(MstLedger.company_id).where(MstLedger.ledger_id == table.c.ledger_id).scalar_subquery())
            )).rowcount or 0
        rows += (await db.execute(
            update(table).where(table.c.company_id.is_(None)).values(company_id=owner_company(table))
        )).rowcount or 0
        changed[table.name] = rows

    # Every admin may run the sync agent; an admin can take that away from another afterwards
    admins = (await db.execute(
        select(User).join(Role, Role.role_id == User.role_id)
        .where(func.lower(Role.name).in_(ADMIN_ROLE_NAMES), User.is_active == True)  # noqa: E712
        .order_by(User.created_at, User.user_id)
    )).scalars().all()
    if not admins:
        raise MigrationRefused("No active user holds an admin role, so the account would have nobody to run it.")
    module = (await db.execute(select(Module).where(Module.code == SYNC_AGENT_MODULE))).scalars().first()
    if module is None:
        module = Module(code=SYNC_AGENT_MODULE, name="Manage sync agent",
                        description="Sign in to the Desktop Sync Agent, link companies and manage synced PCs", is_system=True)
        db.add(module)
        await db.flush()
    already = set((await db.execute(
        select(UserPermissionOverride.user_id).where(UserPermissionOverride.module_id == module.module_id))).scalars().all())
    granted = []
    for admin in admins:
        if admin.user_id in already:
            continue
        db.add(UserPermissionOverride(
            user_id=admin.user_id, module_id=module.module_id, can_create=True, can_read=True, can_update=True,
            can_delete=True, reason="Granted to every admin when the account was created", granted_by=admin.user_id))
        granted.append(admin.email)
    # The business's settings (sales target, credit days) become the account's own
    from app.models.portal_core import AppSetting
    from app.services.app_settings import SETTINGS, stored_key
    copied = 0
    for row in (await db.execute(select(AppSetting).where(AppSetting.key.in_(list(SETTINGS))))).scalars().all():
        own_key = stored_key(row.key, account_id)
        if (await db.execute(select(AppSetting.key).where(AppSetting.key == own_key))).scalar() is None:
            db.add(AppSetting(key=own_key, value=row.value, updated_by_user_id=row.updated_by_user_id))
            copied += 1
    changed["settings"] = copied
    changed["sync_agent_granted_to"] = granted
    changed["admins"] = [admin.email for admin in admins]
    if account.created_by_user_id is None:
        account.created_by_user_id = admins[0].user_id
    await db.flush()
    return changed


async def remaining_problems(db: AsyncSession) -> list:
    """Checks to run after the migration. Empty means every row has its owner."""
    problems = []
    for label, model in (("companies", Company), ("users", User), ("roles", Role)):
        missing = (await db.execute(select(func.count()).select_from(model).where(model.account_id.is_(None)))).scalar() or 0
        if missing:
            problems.append(f"{missing} {label} have no account")
    for model in (orders_models.TempOrder, visits_models.SalesVisit, ShopPayment, expenses_models.Expense):
        table = model.__table__
        missing = (await db.execute(select(func.count()).select_from(table).where(table.c.company_id.is_(None)))).scalar() or 0
        if missing:
            problems.append(f"{missing} {table.name} row(s) have no company (their owner has none either)")
    crossing = (await db.execute(
        select(func.count()).select_from(User).join(Company, Company.company_id == User.company_id)
        .where(User.account_id != Company.account_id))).scalar() or 0
    if crossing:
        problems.append(f"{crossing} user(s) have a home company in another account")
    return problems


async def add_foreign_keys(conn, apply: bool) -> list:
    """MySQL only. Returns one line per key saying what was done or would be done."""
    from sqlalchemy import text
    lines = []
    for table, column, parent, parent_column, on_delete in FOREIGN_KEYS:
        where = {"schema": PORTAL, "table": table, "column": column}
        if not (await conn.execute(text(
                "SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA = :schema AND TABLE_NAME = :table AND COLUMN_NAME = :column"), where)).scalar():
            lines.append(f"skip   {table}.{column}: the column is not there yet (start the backend once first)")
            continue
        if (await conn.execute(text(
                "SELECT COUNT(*) FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE "
                "WHERE TABLE_SCHEMA = :schema AND TABLE_NAME = :table AND COLUMN_NAME = :column "
                "AND REFERENCED_TABLE_NAME = :parent"), {**where, "parent": parent})).scalar():
            lines.append(f"ok     {table}.{column} already has its foreign key")
            continue
        orphans = (await conn.execute(text(
            f"SELECT COUNT(*) FROM `{PORTAL}`.`{table}` t "
            f"LEFT JOIN `{PORTAL}`.`{parent}` p ON p.`{parent_column}` = t.`{column}` "
            f"WHERE t.`{column}` IS NOT NULL AND p.`{parent_column}` IS NULL"))).scalar()
        if orphans:
            lines.append(f"STOP   {table}.{column}: {orphans} row(s) name a {parent} row that does not exist; not added")
            continue
        statement = (
            f"ALTER TABLE `{PORTAL}`.`{table}` ADD CONSTRAINT `fk_{table}_{column}` FOREIGN KEY (`{column}`) "
            f"REFERENCES `{PORTAL}`.`{parent}` (`{parent_column}`) ON DELETE {on_delete}")
        if apply:
            await conn.execute(text(statement))
            lines.append(f"added  {table}.{column} -> {parent}.{parent_column}")
        else:
            lines.append(f"would  add {table}.{column} -> {parent}.{parent_column}")
    return lines


async def allow_role_names_per_account(conn, apply: bool) -> list:
    """MySQL only. Role names used to be unique across the whole server, which stops a second account from having
    its own "Admin". Replaces that with unique-inside-an-account. Needed before a second customer can sign up, so
    it runs with the migration itself, not with the later enforcement. Safe to run again."""
    from sqlalchemy import text
    lines = []
    for (index_name,) in (await conn.execute(text(
            "SELECT INDEX_NAME FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_SCHEMA = :s AND TABLE_NAME = 'roles' "
            "AND NON_UNIQUE = 0 AND INDEX_NAME <> 'PRIMARY' GROUP BY INDEX_NAME "
            "HAVING COUNT(*) = 1 AND MAX(COLUMN_NAME) = 'name'"), {"s": PORTAL})).fetchall():
        if apply:
            await conn.execute(text(f"ALTER TABLE `{PORTAL}`.`roles` DROP INDEX `{index_name}`"))
        lines.append(f"{'done ' if apply else 'would'}  roles: drop the server-wide unique name index `{index_name}`")
    has_own = (await conn.execute(text(
        "SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_SCHEMA = :s AND TABLE_NAME = 'roles' "
        "AND INDEX_NAME = 'uq_roles_account_name'"), {"s": PORTAL})).scalar()
    if has_own:
        lines.append("ok     roles: names already unique inside an account")
    else:
        if apply:
            await conn.execute(text(f"ALTER TABLE `{PORTAL}`.`roles` ADD UNIQUE INDEX `uq_roles_account_name` (`account_id`, `name`)"))
        lines.append(f"{'done ' if apply else 'would'}  roles: names unique inside an account")
    return lines


# ─── Enforcement: run once every row has its owner ───────────────────────────

# Owner columns that must never be empty again. (table, column, parent table, parent column, on delete)
REQUIRED_OWNERS = (
    ("users", "account_id", "accounts", "account_id", "RESTRICT"),
    ("companies", "account_id", "accounts", "account_id", "RESTRICT"),
    ("roles", "account_id", "accounts", "account_id", "RESTRICT"),
    ("portal_attendance", "account_id", "accounts", "account_id", "RESTRICT"),
    ("portal_attendance_locations", "account_id", "accounts", "account_id", "RESTRICT"),
    ("temp_orders", "company_id", "companies", "company_id", "CASCADE"),
    ("sales_visits", "company_id", "companies", "company_id", "CASCADE"),
    ("shop_payments", "company_id", "companies", "company_id", "CASCADE"),
    ("expenses", "company_id", "companies", "company_id", "CASCADE"),
)


# Tables in which a Tally GUID is one record's identity inside its company: the importer finds the row to update
# by (company, GUID). Named one by one on purpose: other tables carry a GUID that is not theirs alone (a bill
# repeats its voucher's, the deletion audit can name one record more than once) and must never be made unique.
TALLY_IDENTITY_TABLES = (
    "account_groups", "attendance_types", "cost_centres", "ledgers", "stock_groups", "stock_items",
    "units_of_measure", "voucher_types", "vouchers",
)


def unique_key_targets() -> list:
    """Every key that becomes unique: a company by (account, Tally GUID), and each Tally record by
    (company, Tally GUID). Returns (schema, table, columns, index name). Rows with no GUID yet (made in the app
    and not in Tally) are not affected: an empty GUID never collides."""
    from app.core.database import Base
    import app.models.tally_core  # noqa: F401
    targets = [(PORTAL, "companies", ("account_id", "tally_guid"), "uq_companies_account_guid"),
               (PORTAL, "roles", ("account_id", "name"), "uq_roles_account_name")]
    tables = {table.name: table for table in Base.metadata.tables.values()}
    for name in TALLY_IDENTITY_TABLES:
        table = tables[name]
        targets.append((table.schema or PORTAL, name, ("company_id", "tally_guid"), f"uq_{name}_company_guid"))
    return targets


async def enforce_account_rules(conn, apply: bool) -> list:
    """MySQL only. Makes the database refuse what the application no longer does: a row with no owner, two rows
    of one company with the same Tally GUID, two roles of one account with the same name. Safe to run again.
    Returns one line per step saying what was done or would be done."""
    from sqlalchemy import text
    lines = []

    async def scalar(sql, **params):
        return (await conn.execute(text(sql), params)).scalar()

    async def run(description: str, sql: str):
        if apply:
            await conn.execute(text(sql))
            lines.append(f"done   {description}")
        else:
            lines.append(f"would  {description}")

    # 1. An empty-string GUID is "no GUID": stored as NULL so it never counts as a duplicate
    for schema, table, columns, _ in unique_key_targets():
        guid = columns[1]
        if guid == "name":
            continue
        blanks = await scalar(f"SELECT COUNT(*) FROM `{schema}`.`{table}` WHERE `{guid}` = ''")
        if blanks:
            await run(f"{table}: {blanks} empty Tally GUID(s) stored as none", f"UPDATE `{schema}`.`{table}` SET `{guid}` = NULL WHERE `{guid}` = ''")

    # 2. Role names were unique across the whole server; they are unique inside an account now
    for (index_name,) in (await conn.execute(text(
            "SELECT INDEX_NAME FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_SCHEMA = :s AND TABLE_NAME = 'roles' "
            "AND NON_UNIQUE = 0 AND INDEX_NAME <> 'PRIMARY' GROUP BY INDEX_NAME "
            "HAVING COUNT(*) = 1 AND MAX(COLUMN_NAME) = 'name'"), {"s": PORTAL})).fetchall():
        await run(f"roles: drop the server-wide unique name index `{index_name}`", f"ALTER TABLE `{PORTAL}`.`roles` DROP INDEX `{index_name}`")

    # 3. Unique keys
    for schema, table, columns, name in unique_key_targets():
        if await scalar("SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_SCHEMA = :s AND TABLE_NAME = :t AND INDEX_NAME = :n",
                        s=schema, t=table, n=name):
            lines.append(f"ok     {table}: {columns} already unique")
            continue
        duplicates = await scalar(
            f"SELECT COUNT(*) FROM (SELECT 1 FROM `{schema}`.`{table}` WHERE `{columns[1]}` IS NOT NULL AND `{columns[1]}` <> '' "
            f"GROUP BY `{columns[0]}`, `{columns[1]}` HAVING COUNT(*) > 1) d")
        if duplicates:
            lines.append(f"STOP   {table}: {duplicates} value(s) of {columns} are held by more than one row; not made unique")
            continue
        column_list = ", ".join(f"`{c}`" for c in columns)
        await run(f"{table}: {columns} unique", f"ALTER TABLE `{schema}`.`{table}` ADD UNIQUE INDEX `{name}` ({column_list})")

    # 4. Owner columns can no longer be empty
    for table, column, parent, parent_column, on_delete in REQUIRED_OWNERS:
        where = {"s": PORTAL, "t": table, "c": column}
        nullable = await scalar("SELECT IS_NULLABLE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = :s AND TABLE_NAME = :t AND COLUMN_NAME = :c", **where)
        if nullable is None:
            lines.append(f"skip   {table}.{column}: the column is not there")
            continue
        if nullable == "NO":
            lines.append(f"ok     {table}.{column} is already required")
            continue
        missing = await scalar(f"SELECT COUNT(*) FROM `{PORTAL}`.`{table}` WHERE `{column}` IS NULL")
        if missing:
            lines.append(f"STOP   {table}.{column}: {missing} row(s) still have no owner; not made required")
            continue
        # A key that empties the column when the parent goes cannot sit on a required column: replace it
        for (constraint,) in (await conn.execute(text(
                "SELECT CONSTRAINT_NAME FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA = :s AND TABLE_NAME = :t "
                "AND COLUMN_NAME = :c AND REFERENCED_TABLE_NAME IS NOT NULL"), where)).fetchall():
            await run(f"{table}.{column}: drop foreign key `{constraint}` to replace it",
                      f"ALTER TABLE `{PORTAL}`.`{table}` DROP FOREIGN KEY `{constraint}`")
        await run(f"{table}.{column} required", f"ALTER TABLE `{PORTAL}`.`{table}` MODIFY COLUMN `{column}` INT NOT NULL")
        await run(f"{table}.{column}: foreign key to {parent} (on delete {on_delete.lower()})",
                  f"ALTER TABLE `{PORTAL}`.`{table}` ADD CONSTRAINT `fk_{table}_{column}_req` FOREIGN KEY (`{column}`) "
                  f"REFERENCES `{PORTAL}`.`{parent}` (`{parent_column}`) ON DELETE {on_delete}")
    return lines
