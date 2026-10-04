"""Daily purge of old login sessions and old successful sync logs, so history stays useful and tables stay small."""
import asyncio
import logging
from datetime import timedelta

from sqlalchemy import delete, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.sessions import utcnow
from app.models.portal_core import SyncTrafficLog, UserSession

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


async def daily_cleanup_worker(interval_seconds: int = 24 * 60 * 60, initial_delay_seconds: int = 300):
    """Runs the purges shortly after startup and then once a day. One failing purge doesn't stop the other."""
    await asyncio.sleep(initial_delay_seconds)
    while True:
        for name, purge in (("old session(s)", purge_old_sessions), ("old successful sync log(s)", purge_old_sync_logs)):
            try:
                async with AsyncSessionLocal() as db:
                    removed = await purge(db)
                if removed:
                    logger.info(f"Daily cleanup removed {removed} {name}.")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(f"Daily cleanup of {name} failed: {e}")
        await asyncio.sleep(interval_seconds)
