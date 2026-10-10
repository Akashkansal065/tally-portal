"""How fresh each company's data is, as the app shows it.

Read from what the Desktop Sync Agent last reported for the company (company_sync_state). "Last synced" is the
last cycle that finished for that company with no errors; a report that the company is closed, or that a cycle
failed, does not move it.
"""
from datetime import datetime, timedelta
from typing import Dict, Iterable, Optional

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.agent_auth import now_utc
from app.models.portal_core import AgentDevice, CompanySyncState, SyncQueue

# The agent reports every inbound interval (a minute by default). No report for this long means it is not running.
AGENT_OFFLINE_AFTER = timedelta(minutes=3)
# A clean cycle within this is "live"; older, with the agent running, is "behind"
BEHIND_AFTER = timedelta(minutes=15)


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() + "Z" if value else None


def freshness(state: Optional[str], last_success_at: Optional[datetime], last_attempt_at: Optional[datetime],
              now: Optional[datetime] = None) -> str:
    """One word for the dot beside a company:
    never      no agent has ever reported for it
    offline    the agent has stopped reporting
    closed     the agent is running but the company is not open in Tally
    attention  the last cycle failed, or two open companies share its name
    behind     the agent is running but the last clean cycle is old
    live       synced recently
    """
    now = now or now_utc()
    if last_attempt_at is None:
        return "never"
    if now - last_attempt_at > AGENT_OFFLINE_AFTER:
        return "offline"
    if state == "closed":
        return "closed"
    if state in ("error", "ambiguous"):
        return "attention"
    if last_success_at is None or now - last_success_at > BEHIND_AFTER:
        return "behind"
    return "live"


async def company_sync_status(db: AsyncSession, company_ids: Iterable[int]) -> Dict[int, dict]:
    """Sync status for each of the given companies, including ones no agent has reported for."""
    ids = sorted(set(company_ids))
    if not ids:
        return {}
    now = now_utc()
    pending = dict((await db.execute(
        select(SyncQueue.company_id, func.count(SyncQueue.sync_id))
        .where(SyncQueue.company_id.in_(ids), SyncQueue.is_processed == False)  # noqa: E712
        .group_by(SyncQueue.company_id))).all())
    rows = {row.company_id: (row, device_name) for row, device_name in (await db.execute(
        select(CompanySyncState, AgentDevice.name)
        .join(AgentDevice, AgentDevice.device_id == CompanySyncState.device_id, isouter=True)
        .where(CompanySyncState.company_id.in_(ids)))).all()}
    status = {}
    for company_id in ids:
        row, device_name = rows.get(company_id, (None, None))
        status[company_id] = {
            "company_id": company_id,
            "freshness": freshness(row.state if row else None, row.last_success_at if row else None,
                                   row.last_attempt_at if row else None, now),
            "last_synced_at": _iso(row.last_success_at) if row else None,
            "last_checked_at": _iso(row.last_attempt_at) if row else None,
            "agent_online": bool(row and row.last_attempt_at and now - row.last_attempt_at <= AGENT_OFFLINE_AFTER),
            "last_error": row.last_error if row else None,
            "synced_from": device_name,
            # Entries made in the app that have not reached Tally yet: a separate fact from how fresh the data is
            "pending_to_tally": int(pending.get(company_id, 0)),
        }
    return status
