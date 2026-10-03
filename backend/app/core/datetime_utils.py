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


def get_current_fy_start(ref_date: Optional[date] = None) -> date:
    """
    Returns the start date (April 1st) of the current Indian Financial Year.
    For example:
    - Any date between 2026-04-01 and 2027-03-31 returns 2026-04-01.
    - Any date between 2026-01-01 and 2026-03-31 returns 2025-04-01.
    """
    d = ref_date or get_ist_date()
    if d.month >= 4:
        return date(d.year, 4, 1)
    else:
        return date(d.year - 1, 4, 1)


def is_historical_period(
    to_date_str: Optional[str] = None,
    date_str: Optional[str] = None,
    check_date: Optional[date] = None,
    ref_date: Optional[date] = None
) -> bool:
    """
    Determines if a requested voucher date or date range strictly falls in a closed past financial year.
    Returns True if to_date, single date, or check_date is strictly earlier than current FY start (April 1st).
    """
    target_date: Optional[date] = check_date
    if not target_date and to_date_str:
        try:
            target_date = datetime.strptime(to_date_str, "%Y-%m-%d").date()
        except ValueError:
            pass
    elif not target_date and date_str:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            pass

    if not target_date:
        return False

    fy_start = get_current_fy_start(ref_date)
    return target_date < fy_start
