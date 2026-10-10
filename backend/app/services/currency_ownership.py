"""Gives each company its own currencies.

Currencies used to be one list for the whole server, so one business renaming "USD" renamed it for every
other. Each row now belongs to a company. At startup, any row still without a company is handed out: every
company gets its own copy, and that company's exchange rates, ledgers and voucher entries are pointed at
its copy. Safe to run again after an interruption: a copy that already exists is reused, and a row is only
marked as owned once every other company has been given its copy.
"""
import logging

from sqlalchemy import insert, select, text, update
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.config import settings
from app.models.portal_core import Company, Currency, ExchangeRate
from app.models.tally_core import MstLedger, TrnAccounting, TrnVoucher

logger = logging.getLogger("app.services.currency_ownership")

PORTAL = settings.PORTAL_DATABASE_NAME
PER_COMPANY_INDEX = "ix_currencies_company_code"


async def _indexes(conn: AsyncConnection) -> dict:
    """MySQL only: each index on the currencies table as name -> (is unique, [columns])."""
    rows = (await conn.execute(text(
        "SELECT INDEX_NAME, NON_UNIQUE, COLUMN_NAME FROM INFORMATION_SCHEMA.STATISTICS "
        "WHERE TABLE_SCHEMA = :schema AND TABLE_NAME = 'currencies' ORDER BY INDEX_NAME, SEQ_IN_INDEX"
    ), {"schema": PORTAL})).fetchall()
    found: dict = {}
    for name, non_unique, column in rows:
        found.setdefault(name, (not int(non_unique), []))[1].append(column)
    return found


async def _allow_same_code_in_two_companies(conn: AsyncConnection) -> None:
    """Drop the old rule that a currency code exists once on the whole server."""
    if conn.dialect.name != "mysql":
        return
    for name, (unique, columns) in (await _indexes(conn)).items():
        if unique and columns == ["code"]:
            await conn.execute(text(f"ALTER TABLE `{PORTAL}`.`currencies` DROP INDEX `{name}`"))
            logger.info(f"Dropped the server-wide unique index `{name}` on currencies.code.")


async def _one_code_per_company(conn: AsyncConnection) -> None:
    """Add the rule that a currency code exists once per company (new tables are created with it)."""
    if conn.dialect.name != "mysql" or PER_COMPANY_INDEX in await _indexes(conn):
        return
    await conn.execute(text(
        f"CREATE UNIQUE INDEX `{PER_COMPANY_INDEX}` ON `{PORTAL}`.`currencies` (`company_id`, `code`)"))


async def ensure_currencies_per_company(conn: AsyncConnection) -> int:
    """Hand every currency that has no company to the companies. Returns how many rows it handed out."""
    currencies = Currency.__table__
    shared = (await conn.execute(
        select(currencies).where(currencies.c.company_id.is_(None)).order_by(currencies.c.currency_id)
    )).mappings().all()
    company_ids = [row[0] for row in (await conn.execute(
        select(Company.__table__.c.company_id).order_by(Company.__table__.c.company_id))).fetchall()]
    if not shared or not company_ids:
        # Nothing to hand out, or nobody to hand it to yet (a brand-new server): the next start tries again
        if not shared:
            await _one_code_per_company(conn)
        return 0

    await _allow_same_code_in_two_companies(conn)
    keeper, others = company_ids[0], company_ids[1:]
    rates, ledgers, entries, vouchers = (ExchangeRate.__table__, MstLedger.__table__, TrnAccounting.__table__,
                                         TrnVoucher.__table__)

    async def use_instead(company_id: int, old_id: int, own_id: int) -> None:
        """Point what this company holds against the shared currency at its own one."""
        await conn.execute(update(rates).where(rates.c.currency_id == old_id, rates.c.company_id == company_id)
                           .values(currency_id=own_id))
        await conn.execute(update(ledgers).where(ledgers.c.currency_id == old_id, ledgers.c.company_id == company_id)
                           .values(currency_id=own_id))
        await conn.execute(update(entries).where(
            entries.c.forex_currency_id == old_id,
            entries.c.voucher_id.in_(select(vouchers.c.voucher_id).where(vouchers.c.company_id == company_id)),
        ).values(forex_currency_id=own_id))

    async def own(company_id: int, code: str):
        return (await conn.execute(select(currencies.c.currency_id).where(
            currencies.c.company_id == company_id, currencies.c.code == code))).scalar()

    for row in shared:
        old_id = row["currency_id"]
        for company_id in others:
            copy_id = await own(company_id, row["code"])
            if copy_id is None:
                values = {k: v for k, v in row.items() if k != "currency_id"}
                values["company_id"] = company_id
                copy_id = (await conn.execute(insert(currencies).values(**values))).inserted_primary_key[0]
            await use_instead(company_id, old_id, copy_id)
        # Last, so an interrupted run finds this row still unowned and finishes it. The first company takes
        # the row itself, unless it already has that code: then the shared row has no one left and goes.
        keepers_own = await own(keeper, row["code"])
        if keepers_own is None:
            await conn.execute(update(currencies).where(currencies.c.currency_id == old_id).values(company_id=keeper))
        else:
            await use_instead(keeper, old_id, keepers_own)
            await conn.execute(rates.delete().where(rates.c.currency_id == old_id))
            await conn.execute(currencies.delete().where(currencies.c.currency_id == old_id))

    await _one_code_per_company(conn)
    logger.info(f"{len(shared)} shared currencies given to {len(company_ids)} company(ies), one copy each.")
    return len(shared)
