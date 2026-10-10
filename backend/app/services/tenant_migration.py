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
