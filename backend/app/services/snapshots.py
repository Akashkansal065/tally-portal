"""Daily saved figures (report_snapshots) for numbers Tally only knows as of today, such as how much is overdue
or how much money sits in dead stock, so their trend can be shown. Written by the daily job and, if that hasn't
run yet today, the first time someone opens the report."""
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.portal_core import ReportSnapshot


async def has_snapshot(db: AsyncSession, company_id: int, kind: str, day: date) -> bool:
    return bool((await db.execute(select(ReportSnapshot.id).where(
        ReportSnapshot.company_id == company_id, ReportSnapshot.kind == kind, ReportSnapshot.day == day))).scalar())


async def save_snapshot(db: AsyncSession, company_id: int, kind: str, day: date, data: Dict[str, Any]) -> bool:
    """Store today's figures once; later calls the same day keep the first. Returns True if stored."""
    if await has_snapshot(db, company_id, kind, day):
        return False
    db.add(ReportSnapshot(company_id=company_id, kind=kind, day=day, data=data))
    try:
        await db.commit()
    except IntegrityError:  # another request stored it first
        await db.rollback()
        return False
    return True


async def history(db: AsyncSession, company_id: int, kind: str, since: date) -> List[Dict[str, Any]]:
    rows = await db.execute(
        select(ReportSnapshot.day, ReportSnapshot.data)
        .where(ReportSnapshot.company_id == company_id, ReportSnapshot.kind == kind, ReportSnapshot.day >= since)
        .order_by(ReportSnapshot.day)
    )
    return [{"day": day.isoformat(), **data} for day, data in rows.all()]


def month_ends(today: date, months: int) -> List[date]:
    """The last day of each of the previous `months` months, oldest first, then today."""
    ends: List[date] = []
    first = today.replace(day=1)
    for _ in range(months):
        last = first - timedelta(days=1)
        ends.append(last)
        first = last.replace(day=1)
    return sorted(ends) + [today]


def change(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    if current is None or not previous:
        return None
    return round((current - previous) / previous * 100, 1)
