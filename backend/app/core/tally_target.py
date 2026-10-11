"""Where the server may reach Tally directly, and for which company.

TALLY_URL is one Tally the server itself can reach (a LAN install, or a tunnel to one office). It belongs to one
customer: sending another company's vouchers to it would put them in that customer's books. Only one company, "the
direct company", may use it; every other company is told there is no direct Tally, and its changes wait in the
queue for its own Desktop Sync Agent. The direct company is, in this order:

  TALLY_URL_COMPANY_ID    that company. An id cannot be copied, so this is the setting to use.
  TALLY_URL_COMPANY_GUID  the earliest company with that Tally GUID. A GUID is only unique inside an account: anyone
                          who signs up can give a company of theirs the same GUID, and must not get the Tally by it.
  neither                 the server's first customer: companies of the earliest account, and companies from before
                          accounts (until ACCOUNTS_ENFORCED). Someone who signs up later never gets it.

A request with no company recorded (a background job) has no direct Tally.
"""
import logging
import time
from contextvars import ContextVar
from typing import Dict, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.models.portal_core import Account, Company

logger = logging.getLogger("app.core.tally_target")

_request_company_direct: ContextVar[bool] = ContextVar("request_company_direct", default=False)
_direct_cache: Dict[int, Tuple[bool, float]] = {}
_DIRECT_CACHE_SECONDS = 60
_unpinned_warned_at = 0.0


def _only_company_guid() -> str:
    return (getattr(settings, "TALLY_URL_COMPANY_GUID", None) or "").strip()


def current_tally_url() -> Optional[str]:
    """The Tally this request's company may be sent to directly, or nothing."""
    url = settings.TALLY_URL
    return url if url and _request_company_direct.get() else None


def forget_direct_companies() -> None:
    """Drop the cached answers (after the settings change, and between tests)."""
    _direct_cache.clear()


async def note_request_company(db: AsyncSession, company_id: Optional[int]) -> None:
    """Record which company the current request is working in, so current_tally_url() can answer for it."""
    if not settings.TALLY_URL or company_id is None:
        return
    cached = _direct_cache.get(company_id)
    if cached is None or cached[1] < time.time():
        cached = (await _is_direct_company(db, company_id), time.time() + _DIRECT_CACHE_SECONDS)
        _direct_cache[company_id] = cached
    _request_company_direct.set(cached[0])


async def _is_direct_company(db: AsyncSession, company_id: int) -> bool:
    pinned_id = getattr(settings, "TALLY_URL_COMPANY_ID", None)
    if pinned_id is not None:
        return company_id == pinned_id
    guid = _only_company_guid()
    if guid:
        first = (await db.execute(select(func.min(Company.company_id)).where(Company.tally_guid == guid))).scalar()
        return company_id == first

    row = (await db.execute(select(Company.account_id).where(Company.company_id == company_id))).first()
    if row is None:
        return False
    if row[0] is None:
        return not settings.ACCOUNTS_ENFORCED   # from before accounts: the server's own customer
    first_account, accounts = (await db.execute(select(func.min(Account.account_id), func.count(Account.account_id)))).one()
    if accounts > 1:
        _warn_unpinned(accounts)
    return row[0] == first_account


def _warn_unpinned(accounts: int) -> None:
    global _unpinned_warned_at
    if time.time() - _unpinned_warned_at < 3600:
        return
    _unpinned_warned_at = time.time()
    logger.warning(
        f"TALLY_URL is set but not pinned to a company, and this server holds {accounts} accounts: only the first "
        "account's companies use it. Set TALLY_URL_COMPANY_ID in backend/.env to the company that Tally belongs to.")
