"""One-time move of stored device-session times from UTC to IST.

Device sessions used to write UTC while everything else in the app writes IST. The code now writes IST; this
moves what is already stored across, once, at startup, and records that it did so it never runs twice. Both
happen in one transaction: either the times are moved and marked, or nothing changed.
"""
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.config import settings

logger = logging.getLogger("app.services.session_times")

MARKER = "session_times_are_ist"
PORTAL = settings.PORTAL_DATABASE_NAME

# (table, column, extra condition). Sessions from before device tracking got created_at from MySQL NOW(),
# which was already IST, so only tracked sessions (client_type set) have a UTC created_at.
UTC_COLUMNS = (
    ("user_sessions", "created_at", "client_type IS NOT NULL"),
    ("user_sessions", "last_active_at", None),
    ("user_sessions", "expires_at", None),
    ("user_sessions", "revoked_at", None),
    ("blocked_devices", "created_at", None),
    ("users", "last_login", None),
)


async def ensure_session_times_ist(conn: AsyncConnection) -> bool:
    """Move the stored session times to IST if that has not been done. True when it did it now."""
    dialect = conn.dialect.name
    if dialect == "mysql":
        shifted = "DATE_ADD(`{c}`, INTERVAL 330 MINUTE)"
    elif dialect == "postgresql":
        shifted = "\"{c}\" + INTERVAL '330 minutes'"
    else:
        return False   # SQLite is only the test database, which starts empty
    done = (await conn.execute(text(f"SELECT COUNT(*) FROM {PORTAL}.app_settings WHERE `key` = :k" if dialect == "mysql"
                                    else f"SELECT COUNT(*) FROM {PORTAL}.app_settings WHERE key = :k"), {"k": MARKER})).scalar()
    if done:
        return False
    moved = 0
    for table, column, condition in UTC_COLUMNS:
        quoted = f"`{column}`" if dialect == "mysql" else f'"{column}"'
        where = f"{quoted} IS NOT NULL" + (f" AND {condition}" if condition else "")
        result = await conn.execute(text(f"UPDATE {PORTAL}.{table} SET {quoted} = {shifted.format(c=column)} WHERE {where}"))
        moved += result.rowcount or 0
    await conn.execute(text(f"INSERT INTO {PORTAL}.app_settings (`key`, value) VALUES (:k, '1')" if dialect == "mysql"
                            else f"INSERT INTO {PORTAL}.app_settings (key, value) VALUES (:k, '1')"), {"k": MARKER})
    logger.info(f"Device-session times moved from UTC to IST ({moved} value(s)).")
    return True
