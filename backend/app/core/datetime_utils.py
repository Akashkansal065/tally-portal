"""
Centralized Datetime Utilities for Indian Standard Time (IST / Asia/Kolkata, UTC+05:30).
Ensures all datetime creation, storage, and presentation across the codebase is consistently aligned with IST.
"""
from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo
from typing import Optional

IST = ZoneInfo("Asia/Kolkata")


def get_ist_now() -> datetime:
    """
    Returns the current datetime in Indian Standard Time (naive for MySQL storage).
    Guarantees consistency across servers regardless of host system timezone.
    """
    return datetime.now(IST).replace(tzinfo=None)


def get_ist_date() -> date:
    """
    Returns today's current calendar date in Indian Standard Time.
    """
    return datetime.now(IST).date()


def to_ist_datetime(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Converts any datetime to an IST timezone-aware datetime.
    - If dt is already timezone-aware, converts to IST.
    - If dt is naive, assumes it is naive IST (standard for DB storage) or local time.
    """
    if not dt:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=IST)
    return dt.astimezone(IST)


def to_ist_iso(dt: Optional[datetime]) -> Optional[str]:
    """
    Formats a datetime as an ISO-8601 string with explicit IST +05:30 offset for API consumers.
    """
    if not dt:
        return None
    ist_dt = to_ist_datetime(dt)
    return ist_dt.isoformat()
