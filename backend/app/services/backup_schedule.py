"""Scheduled backups (Phase 5): once a day at a chosen time, back up each company that's open in Tally, keep the last
N scheduled backups per company, and optionally email the file (Gmail switch). Uses the isolated backup module,
which reads straight from Tally (TALLY_URL), so it only works where this server can reach the Tally PC; otherwise
the run is skipped and admins are told.

Settings and state live in app_settings under "backup_schedule" (JSON), so no new tables are needed.
"""
import asyncio
import json
import os
from datetime import datetime, time
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.datetime_utils import get_ist_now
from app.core.logging_config import get_logger
from app.models.portal_core import AppSetting, Company

logger = get_logger("app.services.backup_schedule")

KEY = "backup_schedule"
DEFAULTS: Dict[str, Any] = {"enabled": False, "time": "21:00", "keep": 7, "email_to": "",
                            "last_run_day": None, "pending": [], "kept": {}, "last_result": None}
MAX_EMAIL_BYTES = 20 * 1024 * 1024


def _backup_module():
    """The backup module's service and Tally client (imported lazily: it's optional in some deployments)."""
    from backup_module.backup_service import backup_service
    from backup_module.tally_client import tally_client
    return backup_service, tally_client


async def load(db: AsyncSession) -> Dict[str, Any]:
    row = (await db.execute(select(AppSetting).where(AppSetting.key == KEY))).scalars().first()
    data = dict(DEFAULTS)
    if row:
        try:
            data.update(json.loads(row.value))
        except ValueError:
            pass
    return data


async def store(db: AsyncSession, data: Dict[str, Any], user_id: Optional[int] = None) -> None:
    row = (await db.execute(select(AppSetting).where(AppSetting.key == KEY))).scalars().first()
    if row:
        row.value, row.updated_by_user_id = json.dumps(data), user_id or row.updated_by_user_id
    else:
        db.add(AppSetting(key=KEY, value=json.dumps(data), updated_by_user_id=user_id))


def parse_time(value: str) -> time:
    hour, minute = (int(x) for x in value.split(":"))
    return time(hour, minute)


async def _notify(db: AsyncSession, title: str, message: str) -> None:
    from app.services.notifications import notify_admins
    companies = (await db.execute(select(Company.company_id).where(Company.is_active.is_(True)))).scalars().all()
    for cid in companies[:1]:  # admins see every company; one notification is enough
        await notify_admins(db, cid, "backup_failed", title=title, message=message[:300], link="/backup",
                            group_key="backup_failed", group_title=lambda n: f"{n} backup problems")


async def start_backups(db: AsyncSession, data: Dict[str, Any], now: datetime) -> List[str]:
    """Back up every active company that's open in Tally. Returns what was started (company names)."""
    backup_service, tally_client = _backup_module()
    connected, message, open_companies = await asyncio.to_thread(tally_client.check_health)
    data["last_run_day"] = now.date().isoformat()
    if not connected:
        data["last_result"] = {"at": now.isoformat(), "ok": False, "message": f"Tally isn't reachable from the server: {message}"}
        await _notify(db, "Scheduled backup skipped", f"Tally isn't reachable from the server ({settings.TALLY_URL or 'TALLY_URL not set'}). "
                      "Backups read straight from Tally, so they run only where the server can reach the Tally PC.")
        return []
    open_names = {str(c.get("name", "")).strip().lower(): str(c.get("name", "")).strip() for c in open_companies}
    ours = (await db.execute(select(Company.name).where(Company.is_active.is_(True)))).scalars().all()
    started, missing = [], []
    for name in ours:
        tally_name = open_names.get(name.strip().lower())
        if not tally_name:
            missing.append(name)
            continue
        backup_id = await asyncio.to_thread(backup_service.start_backup, tally_name, "Scheduled daily backup")
        data["pending"].append({"id": backup_id, "company": tally_name})
        started.append(tally_name)
    data["last_result"] = {"at": now.isoformat(), "ok": bool(started), "started": started, "not_open_in_tally": missing,
                           "message": f"Started {len(started)} backup(s)" + (f"; not open in Tally: {', '.join(missing)}" if missing else "")}
    if missing:
        await _notify(db, "Some companies weren't backed up", f"Not open in Tally: {', '.join(missing)}. Open them in Tally to include them.")
    return started


async def finish_backups(db: AsyncSession, data: Dict[str, Any]) -> None:
    """For each finished scheduled backup: keep the last N per company, email it if asked, report failures."""
    backup_service, _ = _backup_module()
    still_running = []
    for item in data.get("pending", []):
        record = await asyncio.to_thread(backup_service.get_backup_record, item["id"])
        status = (record or {}).get("status")
        if status in ("pending", "running", "in_progress"):
            still_running.append(item)
            continue
        if status != "completed":
            error = (record or {}).get("error_message") or "unknown error"
            await _notify(db, f"Scheduled backup of {item['company']} failed", error)
            continue
        kept = data.setdefault("kept", {}).setdefault(item["company"], [])
        kept.append(item["id"])
        while len(kept) > int(data.get("keep") or 7):
            await asyncio.to_thread(backup_service.delete_backup, kept.pop(0))
        if data.get("email_to"):
            await _email(db, data["email_to"], item["company"], record)
    data["pending"] = still_running


async def _email(db: AsyncSession, to: str, company_name: str, record: dict) -> None:
    from app.services import messaging
    from app.services.integrations import is_enabled
    company = (await db.execute(select(Company).where(Company.name == company_name))).scalars().first()
    if not company or not await is_enabled(db, company.company_id, "email") or not (settings.SMTP_USER and settings.SMTP_PASS):
        return
    path, size = record.get("file_path"), int(record.get("file_size_bytes") or 0)
    subject = f"Tally backup: {company_name} ({record.get('created_at', '')[:10]})"
    if path and os.path.exists(path) and size <= MAX_EMAIL_BYTES:
        with open(path, "rb") as f:
            content = f.read()
        result = await messaging.send_email(to, subject, f"Attached is today's scheduled backup of {company_name} from MyTally.",
                                            attachments=[(os.path.basename(path), content, "application/zip")])
    else:
        result = await messaging.send_email(to, subject, f"Today's backup of {company_name} is {size / 1024 / 1024:.1f} MB, too large to "
                                            "email. Download it from MyTally → Backup.")
    if not result.ok:
        await _notify(db, "Backup email failed", result.error or "Gmail refused it.")


async def tick(db: AsyncSession, now: Optional[datetime] = None) -> None:
    """One pass of the worker: finish what's running, then start today's backups if it's time."""
    now = now or get_ist_now()
    data = await load(db)
    before = json.dumps(data, sort_keys=True)
    if data.get("pending"):
        await finish_backups(db, data)
    if data.get("enabled") and data.get("last_run_day") != now.date().isoformat() and now.time() >= parse_time(data.get("time") or "21:00"):
        await start_backups(db, data, now)
    if json.dumps(data, sort_keys=True) != before:  # nothing is written while the schedule is off and idle
        await store(db, data)
    await db.commit()


async def backup_worker(interval_seconds: int = 600, initial_delay_seconds: int = 120):
    from app.core.database import AsyncSessionLocal
    await asyncio.sleep(initial_delay_seconds)
    while True:
        try:
            async with AsyncSessionLocal() as db:
                await tick(db)
        except asyncio.CancelledError:
            raise
        except ImportError:
            logger.info("Backup module not available; scheduled backups are off")
            return
        except Exception:
            logger.exception("Scheduled backup run failed")
        await asyncio.sleep(interval_seconds)
