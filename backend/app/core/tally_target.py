"""Where the server may reach Tally directly, and for which company.

TALLY_URL is one Tally the server itself can reach (a LAN install, or a tunnel to one office). On a server that
holds several customers that Tally belongs to one of them: sending another company's vouchers to it would put
them in the wrong books if a company of the same name happened to be open there. TALLY_URL_COMPANY_GUID names
the one company it is for; with it set, every other company is told there is no direct Tally, and its changes
wait in the queue for its own Desktop Sync Agent.
"""
import time
from contextvars import ContextVar
from typing import Dict, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.models.portal_core import Company

_UNKNOWN = object()
_request_company_guid: ContextVar = ContextVar("request_company_guid", default=_UNKNOWN)
_guid_cache: Dict[int, Tuple[Optional[str], float]] = {}
_GUID_CACHE_SECONDS = 60


def _only_company_guid() -> str:
    return (getattr(settings, "TALLY_URL_COMPANY_GUID", None) or "").strip()


def current_tally_url() -> Optional[str]:
    """The Tally this request's company may be sent to directly, or nothing."""
    url = settings.TALLY_URL
    only = _only_company_guid()
    if not url or not only:
        return url
    return url if _request_company_guid.get() == only else None


async def note_request_company(db: AsyncSession, company_id: Optional[int]) -> None:
    """Record which company the current request is working in, so current_tally_url() can answer for it."""
    if not (settings.TALLY_URL and _only_company_guid()) or company_id is None:
        return
    cached = _guid_cache.get(company_id)
    if cached is None or cached[1] < time.time():
        guid = (await db.execute(select(Company.tally_guid).where(Company.company_id == company_id))).scalar()
        cached = (guid, time.time() + _GUID_CACHE_SECONDS)
        _guid_cache[company_id] = cached
    _request_company_guid.set(cached[0])
