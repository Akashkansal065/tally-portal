"""Read-only report of how the data is owned, for moving existing rows into accounts.

Nothing here writes. It answers: which companies and users exist and which account each is in, which rows have
no owner yet, which rows would break the keys that are about to become unique, and which tables hold data that
no code reads any more.
"""
from typing import Any, Dict, List

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

import app.models.tally_core  # noqa: F401  (registers the tables)
import app.routers.attendance  # noqa: F401
import app.routers.expenses  # noqa: F401
import app.routers.orders  # noqa: F401
import app.routers.visits  # noqa: F401
from app.core.database import Base
from app.models.portal_core import Account, Company, Role, User, UserCompanyAccess
from app.models.tally_core import MstLedger

# Tables no code reads or writes any more (checked 10 Oct 2026); their row counts decide whether they can go
UNUSED_TABLES = (
    "mst_gst_effective_rate", "mst_opening_batch_allocation", "mst_opening_bill_allocation",
    "mst_stockitem_standard_cost", "mst_stockitem_standard_price", "trn_closingstock_ledger",
    "trn_cost_category_centre", "trn_cost_centre", "trn_cost_inventory_category_centre",
    "trn_employee", "trn_inventory_additional_cost",
)
# Field-sales rows that point at a ledger, and so at exactly one company
LEDGER_OWNED_TABLES = ("temp_orders", "sales_visits", "shop_payments")


def _tables() -> Dict[str, Any]:
    return {table.name: table for table in Base.metadata.tables.values()}


async def _count(db: AsyncSession, stmt) -> int:
    return int((await db.execute(stmt)).scalar() or 0)


async def collect_inventory(db: AsyncSession) -> Dict[str, Any]:
    tables = _tables()
    report: Dict[str, Any] = {}

    report["accounts"] = [
        {"account_id": a.account_id, "name": a.name, "status": a.status}
        for a in (await db.execute(select(Account).order_by(Account.account_id))).scalars()
    ]

    companies = (await db.execute(select(Company).order_by(Company.company_id))).scalars().all()
    row_counts = {}
    for name in ("ledgers", "stock_items", "vouchers"):
        table = tables[name]
        row_counts[name] = dict((await db.execute(
            select(table.c.company_id, func.count()).group_by(table.c.company_id))).all())
    report["companies"] = [
        {"company_id": c.company_id, "name": c.name, "account_id": c.account_id, "tally_guid": c.tally_guid,
         "is_active": bool(c.is_active), **{name: row_counts[name].get(c.company_id, 0) for name in row_counts}}
        for c in companies
    ]
    report["companies_without_guid"] = [c.company_id for c in companies if not c.tally_guid]

    grants: Dict[int, List[int]] = {}
    for user_id, company_id in (await db.execute(
            select(UserCompanyAccess.user_id, UserCompanyAccess.company_id).order_by(UserCompanyAccess.company_id))).all():
        grants.setdefault(user_id, []).append(company_id)
    report["users"] = [
        {"user_id": user_id, "email": email, "role": role, "account_id": account_id, "is_active": bool(is_active),
         "home_company_id": company_id, "granted_company_ids": grants.get(user_id, [])}
        for user_id, email, role, account_id, is_active, company_id in (await db.execute(
            select(User.user_id, User.email, Role.name, User.account_id, User.is_active, User.company_id)
            .join(Role, Role.role_id == User.role_id, isouter=True).order_by(User.user_id))).all()
    ]

    # A grant whose user and company are in different accounts (one of them having none counts as different)
    report["cross_account_grants"] = [
        {"user_id": user_id, "company_id": company_id}
        for user_id, company_id in (await db.execute(
            select(UserCompanyAccess.user_id, UserCompanyAccess.company_id)
            .join(User, User.user_id == UserCompanyAccess.user_id)
            .join(Company, Company.company_id == UserCompanyAccess.company_id)
            .where(or_(User.account_id != Company.account_id,
                       and_(User.account_id.is_(None), Company.account_id.isnot(None)),
                       and_(User.account_id.isnot(None), Company.account_id.is_(None))))
            .order_by(UserCompanyAccess.user_id, UserCompanyAccess.company_id))).all()
    ]

    # Rows that share (company_id, Tally GUID): the key that becomes unique
    duplicates = {}
    for name, table in sorted(tables.items()):
        guid = table.c.get("tally_guid") if "tally_guid" in table.c else table.c.get("guid")
        if guid is None or "company_id" not in table.c or name == "companies":
            continue
        groups = (await db.execute(
            select(table.c.company_id, guid, func.count())
            .where(guid.isnot(None), guid != "")
            .group_by(table.c.company_id, guid).having(func.count() > 1)
            .order_by(table.c.company_id, guid))).all()
        if groups:
            duplicates[name] = [{"company_id": c, "tally_guid": g, "rows": n} for c, g, n in groups]
    report["duplicate_tally_guids"] = duplicates
    report["duplicate_company_guids"] = [
        {"account_id": account_id, "tally_guid": guid, "rows": n}
        for account_id, guid, n in (await db.execute(
            select(Company.account_id, Company.tally_guid, func.count())
            .where(Company.tally_guid.isnot(None), Company.tally_guid != "")
            .group_by(Company.account_id, Company.tally_guid).having(func.count() > 1))).all()
    ]

    # Rows still waiting for an owner, per table that has the column
    unowned = {}
    for name, table in sorted(tables.items()):
        for column in ("account_id", "company_id"):
            if column in table.c and table.c[column].nullable and name != "accounts":
                missing = await _count(db, select(func.count()).select_from(table).where(table.c[column].is_(None)))
                total = await _count(db, select(func.count()).select_from(table))
                if total:
                    unowned[f"{name}.{column}"] = {"missing": missing, "total": total}
    report["rows_without_owner"] = unowned

    # Field-sales rows whose ledger is in another company than the one their owner has active: these are the
    # rows the app lists under the wrong company today
    misplaced = {}
    for name in LEDGER_OWNED_TABLES:
        table = tables[name]
        misplaced[name] = await _count(db, select(func.count()).select_from(table)
                                       .join(MstLedger, MstLedger.ledger_id == table.c.ledger_id)
                                       .join(User, User.user_id == table.c.user_id)
                                       .where(MstLedger.company_id != User.company_id))
    report["sales_rows_under_another_company"] = misplaced

    report["unused_table_rows"] = {
        name: await _count(db, select(func.count()).select_from(tables[name])) for name in UNUSED_TABLES if name in tables
    }
    return report


def blocking_findings(report: Dict[str, Any]) -> List[str]:
    """What has to be dealt with before accounts can be enforced. Empty means the data is ready."""
    findings = []
    if report["companies_without_guid"]:
        findings.append(f"{len(report['companies_without_guid'])} company(ies) have no Tally GUID: {report['companies_without_guid']}")
    if report["cross_account_grants"]:
        findings.append(f"{len(report['cross_account_grants'])} access grant(s) cross accounts")
    for name, groups in report["duplicate_tally_guids"].items():
        findings.append(f"{name}: {len(groups)} Tally GUID(s) held by more than one row in a company")
    if report["duplicate_company_guids"]:
        findings.append(f"{len(report['duplicate_company_guids'])} Tally GUID(s) held by more than one company in an account")
    for key, counts in report["rows_without_owner"].items():
        if counts["missing"]:
            findings.append(f"{key}: {counts['missing']} of {counts['total']} row(s) have no owner yet")
    for name, rows in report["sales_rows_under_another_company"].items():
        if rows:
            findings.append(f"{name}: {rows} row(s) point at a ledger of another company than their owner's active one")
    return findings
