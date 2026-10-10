"""Alerts to a business's admins about its sync and its boundaries: a company that no PC syncs any more, a
company that has not synced for a day, and a request from outside the business that was refused.

Each is an ordinary notification (bell, Notifications page, push), raised at most once a day per company and
kind, so a PC that stays off or a caller that keeps trying does not fill the list. None of them ever raises:
an alert that cannot be sent must not fail the action that caused it.
"""
import asyncio
import logging
from datetime import timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.datetime_utils import get_ist_now
from app.models.portal_core import AgentCompanyLink, Company, CompanySyncState, Notification, User
from app.services import notifications

logger = logging.getLogger("app.services.alerts")

COMPANIES_LINK = "/companies"
STALE_AFTER = timedelta(hours=24)


async def _alert_once_today(db: AsyncSession, company_id: int, kind: str, type_: str, title: str, message: str,
                            link: str, exclude_user_id: Optional[int] = None) -> bool:
    """Notify the company's admins unless this kind of alert was already raised for it today. Commits."""
    key = f"{kind}-{company_id}-{get_ist_now():%Y%m%d}"
    already = (await db.execute(select(Notification.id).where(
        Notification.company_id == company_id, Notification.group_key == key).limit(1))).scalar()
    if already is not None:
        return False
    created = await notifications.notify_admins(db, company_id, type_, title, message, reference_id=str(company_id),
                                                reference_type="company", link=link, group_key=key,
                                                exclude_user_id=exclude_user_id, auto_commit=True)
    return bool(created)


async def company_unlinked(db: AsyncSession, company_id: int, by_user_id: Optional[int] = None) -> bool:
    """A company's link to its PC ended. Says so unless another PC has it now."""
    try:
        still_linked = (await db.execute(select(AgentCompanyLink.link_id).where(
            AgentCompanyLink.company_id == company_id, AgentCompanyLink.is_active == True).limit(1))).scalar()  # noqa: E712
        if still_linked is not None:
            return False
        name = (await db.execute(select(Company.name).where(Company.company_id == company_id))).scalar() or "A company"
        return await _alert_once_today(
            db, company_id, "sync-unlinked", "sync_unlinked", f"{name} is no longer synced",
            f"No PC is syncing {name} with Tally any more. Changes made in Tally will not reach the app, and entries made "
            "here will wait, until it is linked again from the Desktop Sync Agent.", COMPANIES_LINK, exclude_user_id=by_user_id)
    except Exception as e:
        logger.warning(f"Could not raise the unlinked alert for company {company_id}: {e}")
        return False


async def alert_stale_companies(db: AsyncSession) -> int:
    """Every company that a sync agent has reported for and that has gone a day without a clean sync."""
    raised = 0
    try:
        cutoff = get_ist_now() - STALE_AFTER
        rows = (await db.execute(
            select(Company.company_id, Company.name, CompanySyncState.last_success_at, CompanySyncState.state,
                   CompanySyncState.updated_at)
            .join(CompanySyncState, CompanySyncState.company_id == Company.company_id)
            .where(Company.is_active == True))).all()  # noqa: E712
        for company_id, name, last_success_at, state, first_seen in rows:
            since = last_success_at or first_seen
            if since is None or since > cutoff:
                continue
            when = f"since {last_success_at:%d %b, %I:%M %p}" if last_success_at else "yet"
            why = ("It is not open in Tally on the PC that syncs it." if state == "closed"
                   else "Check that the PC running the Desktop Sync Agent is on and that Tally is open.")
            if await _alert_once_today(db, company_id, "sync-stale", "sync_stale", f"{name} has not synced for a day",
                                       f"{name} has not synced {when}. {why}", COMPANIES_LINK):
                raised += 1
    except Exception as e:
        logger.warning(f"Could not check for companies that stopped syncing: {e}")
    return raised


async def outside_request_refused(bind, company_id: int, what: str) -> bool:
    """Someone who does not belong to a company's business asked for it and was refused. Its admins are told
    that it happened, never who it was: the caller belongs to another customer. Uses its own short
    transaction, so it can be called from a request that will not commit."""
    try:
        async with AsyncSession(bind, expire_on_commit=False) as db:
            name = (await db.execute(select(Company.name).where(Company.company_id == company_id))).scalar()
            if name is None:
                return False
            logger.warning(f"Refused a request from outside the account for company {company_id}: {what}.")
            return await _alert_once_today(
                db, company_id, "outside-refused", "account_refused", "A request from outside your business was refused",
                f"Someone who is not part of your business tried to {what} of {name}. It was refused and nothing was "
                "shown or changed. No action is needed unless this keeps happening.", "/notifications")
    except Exception as e:
        logger.warning(f"Could not raise the refused-request alert for company {company_id}: {e}")
        return False


async def company_of_account(db: AsyncSession, account_id: Optional[int]) -> Optional[int]:
    """A company to file an account-wide alert under (a notification always belongs to a company)."""
    if account_id is None:
        return None
    return (await db.execute(select(Company.company_id).where(Company.account_id == account_id)
                             .order_by(Company.company_id).limit(1))).scalar()


async def company_of_user(db: AsyncSession, user_id: int) -> Optional[int]:
    return (await db.execute(select(User.company_id).where(User.user_id == user_id))).scalar()


async def sync_alert_worker(interval_seconds: int = 3600, initial_delay_seconds: int = 600):
    """Looks once an hour for companies that have gone a day without syncing."""
    await asyncio.sleep(initial_delay_seconds)
    while True:
        try:
            async with AsyncSessionLocal() as db:
                raised = await alert_stale_companies(db)
            if raised:
                logger.info(f"Raised {raised} not-synced alert(s).")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(f"Sync alert check failed: {e}")
        await asyncio.sleep(interval_seconds)
