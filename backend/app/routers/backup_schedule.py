"""Admin → Backup: the daily backup schedule (app/services/backup_schedule.py).

There is one schedule for the whole server and it backs up every company open in the server's Tally, emailing
the files where it is told to, so only the people who run the server may see or change it."""
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.datetime_utils import get_ist_now
from app.models.portal_core import User
from app.core.permissions import require_platform_admin
from app.services import backup_schedule as svc
from app.services.messaging import clean_email

router = APIRouter(prefix="/backup-schedule", tags=["Backup & Restore"])


class ScheduleIn(BaseModel):
    enabled: bool
    time: str = "21:00"
    keep: int = Field(7, ge=1, le=60)
    email_to: str = ""


def _out(data: dict) -> dict:
    return {k: data.get(k) for k in ("enabled", "time", "keep", "email_to", "last_run_day", "last_result")} | {"running": len(data.get("pending") or [])}


@router.get("")
async def get_schedule(user: User = Depends(require_platform_admin), db: AsyncSession = Depends(get_db)):
    return _out(await svc.load(db))


@router.put("")
async def save_schedule(req: ScheduleIn, user: User = Depends(require_platform_admin), db: AsyncSession = Depends(get_db)):
    if not re.match(r"^([01]\d|2[0-3]):[0-5]\d$", req.time):
        raise HTTPException(status_code=422, detail="Time must look like 21:00.")
    if req.email_to and not clean_email(req.email_to):
        raise HTTPException(status_code=422, detail="That doesn't look like an email address.")
    data = await svc.load(db)
    data.update(enabled=req.enabled, time=req.time, keep=req.keep, email_to=clean_email(req.email_to) or "")
    await svc.store(db, data, user.user_id)
    await db.commit()
    return _out(data)


@router.post("/run-now")
async def run_now(user: User = Depends(require_platform_admin), db: AsyncSession = Depends(get_db)):
    """Back up now with the scheduled settings (keep-last and email), whatever the time."""
    try:
        data = await svc.load(db)
        started = await svc.start_backups(db, data, get_ist_now())
        await svc.store(db, data, user.user_id)
        await db.commit()
    except ImportError:
        raise HTTPException(status_code=503, detail="The backup module isn't available on this server.")
    return _out(data) | {"started": started}
