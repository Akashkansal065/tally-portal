"""One import at a time for a company.

An import that is still running when the same company's next one arrives (the agent tried again after a
proxy gave up waiting, or two backends share one database) is not queued behind it: the second is refused
at once and tried again later.

Two layers. Inside this process, a set of the companies being imported. Across processes, a MySQL named lock
(GET_LOCK) held on a connection of its own for as long as the import runs: every backend on the same database
sees it, and MySQL frees it by itself if the process or the connection dies. Other databases (the SQLite the
tests run on) have only the first layer.
"""
import logging
from contextlib import asynccontextmanager
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

logger = logging.getLogger("uvicorn.error")

SYNC_BUSY_REASON = "sync_in_progress"

_importing: set = set()   # company ids with an import running in this process


class SyncBusy(Exception):
    """This company already has an import running."""


def lock_name(database: Optional[str], company_id: int) -> str:
    # Named locks are shared by the whole MySQL server, so the database is part of the name. 64 characters at most.
    return f"mytally_sync:{(database or '')[:32]}:{company_id}"


async def _take_database_lock(db: AsyncSession, company_id: int) -> Optional[tuple]:
    engine = db.bind
    if engine is None or engine.dialect.name != "mysql":
        return None
    name = lock_name(engine.url.database, company_id)
    # Autocommit: the connection only holds the lock, and must not keep a transaction open while it waits
    conn: AsyncConnection = await (await engine.connect()).execution_options(isolation_level="AUTOCOMMIT")
    try:
        got = (await conn.execute(text("SELECT GET_LOCK(:name, 0)"), {"name": name})).scalar()
    except BaseException:
        await conn.invalidate()
        await conn.close()
        raise
    if got != 1:
        await conn.close()
        raise SyncBusy()
    return conn, name


async def _release_database_lock(held: Optional[tuple]) -> None:
    if held is None:
        return
    conn, name = held
    try:
        await conn.execute(text("SELECT RELEASE_LOCK(:name)"), {"name": name})
    except BaseException as ex:
        # A connection given back to the pool with the lock still on it would block this company until it is
        # recycled: throw the connection away instead, which makes MySQL free the lock
        logger.warning(f"Sync lock {name} could not be released cleanly ({ex}); dropping its connection.")
        await conn.invalidate()
    finally:
        await conn.close()


@asynccontextmanager
async def company_sync_guard(db: AsyncSession, company_id: Optional[int]):
    """Hold the company's import for the length of the block. Raises SyncBusy when one is already running."""
    key = company_id or 0
    if key in _importing:
        raise SyncBusy()
    _importing.add(key)
    try:
        held = await _take_database_lock(db, key)
        try:
            yield
        finally:
            await _release_database_lock(held)
    finally:
        _importing.discard(key)
