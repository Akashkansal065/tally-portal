"""Daily purge of old login sessions so device history stays useful and user_sessions stays small."""
import asyncio
import logging
from datetime import timedelta

from sqlalchemy import delete, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.sessions import utcnow
from app.models.portal_core import UserSession

logger = logging.getLogger("session_cleanup")


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


async def session_cleanup_worker(interval_seconds: int = 24 * 60 * 60, initial_delay_seconds: int = 300):
    """Runs purge_old_sessions shortly after startup and then once a day."""
    await asyncio.sleep(initial_delay_seconds)
    while True:
        try:
            async with AsyncSessionLocal() as db:
                removed = await purge_old_sessions(db)
            if removed:
                logger.info(f"Session cleanup removed {removed} old session(s).")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(f"Session cleanup failed: {e}")
        await asyncio.sleep(interval_seconds)
