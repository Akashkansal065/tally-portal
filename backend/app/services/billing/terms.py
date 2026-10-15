"""terms.py – Billing periods by the calendar, and the UTC clock every billing date is kept in."""

from __future__ import annotations

import calendar
from datetime import datetime, timezone
from typing import Optional


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: Optional[datetime]) -> Optional[datetime]:
    """Billing dates are stored as naive UTC; give one its timezone back so it can be compared."""
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def add_term(start: datetime, interval: str, count: int) -> datetime:
    """The same day `count` years or months later (the month's last day when that day does not exist),
    so a yearly plan bought on 14 March always renews on 14 March."""
    months = max(1, count) * (12 if interval == "year" else 1)
    years_on, month_index = divmod(start.month - 1 + months, 12)
    year, month = start.year + years_on, month_index + 1
    return start.replace(year=year, month=month, day=min(start.day, calendar.monthrange(year, month)[1]))
