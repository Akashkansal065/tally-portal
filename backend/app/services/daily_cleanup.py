"""Daily jobs: purge old login sessions, successful sync logs and notifications so tables stay small, and save each
company's overdue and dead-stock totals so their trend can be shown."""
import asyncio
import logging
from datetime import timedelta

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.sessions import utcnow
from app.models.portal_core import Notification, SyncTrafficLog, UserSession

logger = logging.getLogger("daily_cleanup")

# Rows per DELETE when purging sync logs, so a large first run never holds one long lock
SYNC_LOG_DELETE_BATCH = 5000


async def purge_old_sessions(db: AsyncSession) -> int:
    """Delete sessions that expired more than SESSION_PURGE_EXPIRED_AFTER_DAYS ago or were revoked more
    than SESSION_PURGE_REVOKED_AFTER_DAYS ago. Blocked devices and audit log entries are kept."""
    now = utcnow()
    result = await db.execute(
        delete(UserSession).where(or_(
            UserSession.expires_at < now - timedelta(days=settings.SESSION_PURGE_EXPIRED_AFTER_DAYS),
            UserSession.revoked_at < now - timedelta(days=settings.SESSION_PURGE_REVOKED_AFTER_DAYS),
        ))
    )
    await db.commit()
    return result.rowcount or 0


def sync_log_purge_batch(cutoff):
    """One batch of the purge: DELETE ... LIMIT on MySQL (other databases ignore the limit)."""
    return (
        delete(SyncTrafficLog)
        .where(SyncTrafficLog.status == "SUCCESS", SyncTrafficLog.created_at < cutoff)
        .with_dialect_options(mysql_limit=SYNC_LOG_DELETE_BATCH)
    )


async def purge_old_sync_logs(db: AsyncSession) -> int:
    """Delete successful sync traffic logs older than SYNC_LOG_PURGE_SUCCESS_AFTER_DAYS. Each row stores the
    outbound XML, a cURL command and Tally's reply, so the table grows quickly. Failed, timed-out, exception and
    conflict logs are kept until an admin clears them from the sync screen."""
    cutoff = utcnow() - timedelta(days=settings.SYNC_LOG_PURGE_SUCCESS_AFTER_DAYS)
    removed = 0
    while True:
        result = await db.execute(sync_log_purge_batch(cutoff))
        await db.commit()
        batch = result.rowcount or 0
        removed += batch
        if batch < SYNC_LOG_DELETE_BATCH:
            return removed


def notification_purge_batch(now):
    """One batch: read notifications past NOTIFICATION_RETENTION_DAYS, and unread ones past twice that."""
    days = settings.NOTIFICATION_RETENTION_DAYS
    return (
        delete(Notification)
        .where(or_(
            and_(Notification.is_read == True, Notification.created_at < now - timedelta(days=days)),
            Notification.created_at < now - timedelta(days=days * 2),
        ))
        .with_dialect_options(mysql_limit=SYNC_LOG_DELETE_BATCH)
    )


async def purge_old_notifications(db: AsyncSession) -> int:
    """Delete old notifications in batches (see notification_purge_batch)."""
    now = utcnow()
    removed = 0
    while True:
        result = await db.execute(notification_purge_batch(now))
        await db.commit()
        batch = result.rowcount or 0
        removed += batch
        if batch < SYNC_LOG_DELETE_BATCH:
            return removed


async def save_report_snapshots(db: AsyncSession) -> int:
    """Save today's overdue and dead-stock totals for every active company. Returns how many companies."""
    from app.models.portal_core import Company
    from app.routers.report_insights import record_daily_snapshots

    company_ids = (await db.execute(select(Company.company_id).where(Company.is_active == True))).scalars().all()  # noqa: E712
    for company_id in company_ids:
        await record_daily_snapshots(db, company_id)
    return len(company_ids)


async def daily_cleanup_worker(interval_seconds: int = 24 * 60 * 60, initial_delay_seconds: int = 300):
    """Runs the purges shortly after startup and then once a day. One failing purge doesn't stop the others."""
    await asyncio.sleep(initial_delay_seconds)
    while True:
        for name, purge in (
            ("old session(s)", purge_old_sessions),
            ("old successful sync log(s)", purge_old_sync_logs),
            ("old notification(s)", purge_old_notifications),
            ("report snapshot(s)", save_report_snapshots),
        ):
            try:
                async with AsyncSessionLocal() as db:
                    removed = await purge(db)
                if removed:
                    logger.info(f"Daily job: {removed} {name}.")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(f"Daily cleanup of {name} failed: {e}")
        await asyncio.sleep(interval_seconds)
