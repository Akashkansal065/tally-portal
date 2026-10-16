"""Company backups made by the sync agents.

The agent on the PC where a company's Tally runs exports the company every hour (and when asked in the app),
keeps the ZIP on the PC and uploads it here in fixed-size chunks. A backup is identified by the company and the
agent's backup_key, so an upload sent again (after a dropped connection, or twice) carries on with the same row
and file instead of making another. A file only counts as stored once every byte has arrived and its SHA-256
matches what the agent computed.

Files go to BACKUP_STORAGE_DIR, or else to a folder beside the project (storage_root).

How many are kept is the same rule on the PC and here (keys_to_keep): every backup taken today, then for each of
the previous KEEP_DAYS days only the last one of that day, and nothing older. The newest stored backup is always
kept, so a PC that was off for a fortnight does not leave a company with none. Backups taken just before a
restore are kept whole for KEEP_DAYS: they are the way back if a restore went wrong.
"""
import hashlib
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional, Set, Tuple

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.datetime_utils import to_ist_iso
from app.core.logging_config import get_logger
from app.models.portal_core import CompanyBackup, CompanyRestore

logger = get_logger("app.services.backups")

KINDS = ("hourly", "manual", "pre_restore")
KEEP_DAYS = 7
KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
MIN_CHUNK_BYTES = 64 * 1024
MAX_CHUNK_BYTES = 16 * 1024 * 1024
# An upload that never finished (or a backup asked for that no agent made) is given up after this many days
STALE_DAYS = 2


def keys_to_keep(backups: Iterable[Tuple[str, datetime, str]], now: datetime) -> Set[str]:
    """Which of (backup_key, taken_at, kind) to keep: all of today's, the last of each of the previous KEEP_DAYS
    days, every pre-restore backup of those days, and always the newest. Days are calendar days in IST."""
    today = now.date()
    keep: Set[str] = set()
    last_of_day = {}
    newest: Optional[Tuple[str, datetime]] = None
    for key, taken_at, kind in backups:
        if newest is None or taken_at > newest[1]:
            newest = (key, taken_at)
        age = (today - taken_at.date()).days
        if age <= 0:
            keep.add(key)
        elif age <= KEEP_DAYS:
            if kind == "pre_restore":
                keep.add(key)
            elif taken_at.date() not in last_of_day or taken_at > last_of_day[taken_at.date()][1]:
                last_of_day[taken_at.date()] = (key, taken_at)
    keep.update(key for key, _ in last_of_day.values())
    if newest is not None:
        keep.add(newest[0])
    return keep


# ── Files ────────────────────────────────────────────────────────────────────

def storage_root() -> Path:
    """BACKUP_STORAGE_DIR, or else a folder beside the project, never inside it: a redeploy that replaces the
    project folder (backend/../MyTally) leaves <its parent>/MyTally-backups alone."""
    configured = (settings.BACKUP_STORAGE_DIR or "").strip()
    if configured:
        return Path(configured)
    project = Path(__file__).resolve().parents[3]
    return project.parent / f"{project.name}-backups"


def storage_problem() -> Optional[str]:
    """Why backups cannot be written on this server, or None when they can."""
    root = storage_root()
    try:
        root.mkdir(parents=True, exist_ok=True)
        probe = root / ".write_test"
        probe.write_bytes(b"ok")
        probe.unlink()
        return None
    except OSError as e:
        return (f"The server cannot write backups to {root} ({e.strerror or e}). "
                "Set BACKUP_STORAGE_DIR in backend/.env to a folder it can write.")


def _company_dir(backup: CompanyBackup) -> Path:
    return storage_root() / str(backup.account_id or 0) / str(backup.company_id)


def part_path(backup: CompanyBackup) -> Path:
    return _company_dir(backup) / f"{backup.backup_key}.zip.part"


def file_path(backup: CompanyBackup) -> Path:
    return _company_dir(backup) / f"{backup.backup_key}.zip"


def write_chunk(backup: CompanyBackup, offset: int, data: bytes) -> None:
    """Write one chunk where it belongs in the file being uploaded. Writing a chunk again writes the same bytes."""
    path = part_path(backup)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "r+b" if path.exists() else "wb") as f:
        f.seek(offset)
        f.write(data)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def finish_file(backup: CompanyBackup) -> bool:
    """Check the uploaded file against its checksum and, if it matches, make it the stored backup. A file that
    does not match is thrown away so the upload starts again."""
    part = part_path(backup)
    if not part.exists() or part.stat().st_size != backup.size_bytes or sha256_of(part) != backup.sha256:
        discard_files(backup)
        return False
    os.replace(part, file_path(backup))
    return True


def discard_files(backup: CompanyBackup) -> None:
    for path in (part_path(backup), file_path(backup)):
        try:
            path.unlink()
        except FileNotFoundError:
            pass


# ── Keeping the right ones ──────────────────────────────────────────────────

async def prune_company(db: AsyncSession, company_id: int, now: datetime) -> int:
    """Delete the company's stored backups that the keep rule no longer wants, and uploads or requests that went
    stale. A backup an open restore is using is never deleted. Returns how many were deleted. The caller commits."""
    protected: Set[str] = set()
    for key, pre_key in (await db.execute(select(CompanyRestore.backup_key, CompanyRestore.pre_restore_backup_key).where(
            CompanyRestore.company_id == company_id, CompanyRestore.is_open == True))).all():  # noqa: E712
        protected.update(k for k in (key, pre_key) if k)

    rows = (await db.execute(select(CompanyBackup).where(CompanyBackup.company_id == company_id))).scalars().all()
    stored = [r for r in rows if r.status == "stored" and r.taken_at is not None]
    keep = keys_to_keep(((r.backup_key, r.taken_at, r.kind) for r in stored), now) | protected
    doomed = [r for r in stored if r.backup_key not in keep]
    doomed += [r for r in rows if r.status != "stored" and r.backup_key not in protected
               and (now - (r.updated_at or r.created_at or now)).days >= STALE_DAYS]
    for row in doomed:
        discard_files(row)
    if doomed:
        from app.services import google_drive
        await google_drive.queue_deletions(db, doomed)   # their Drive copies go too, once their ids are recorded
        await db.execute(delete(CompanyBackup).where(CompanyBackup.backup_id.in_([r.backup_id for r in doomed])))
        logger.info(f"Company #{company_id}: {len(doomed)} backup(s) no longer kept were deleted.")
    return len(doomed)


def backup_dict(backup: CompanyBackup) -> dict:
    return {
        "backup_id": backup.backup_id, "backup_key": backup.backup_key, "kind": backup.kind, "status": backup.status,
        "taken_at": to_ist_iso(backup.taken_at),
        "stored_at": to_ist_iso(backup.stored_at),
        "size_bytes": backup.size_bytes, "record_counts": backup.record_counts or {},
        "tally_company_name": backup.tally_company_name, "error": backup.error,
        "created_at": to_ist_iso(backup.created_at),
        "drive_status": backup.drive_status, "drive_error": backup.drive_error,
        "drive_uploaded_at": to_ist_iso(backup.drive_uploaded_at),
    }


def restore_dict(restore: CompanyRestore) -> dict:
    return {
        "restore_id": restore.restore_id, "backup_id": restore.backup_id, "backup_key": restore.backup_key,
        "status": restore.status, "pre_restore_backup_key": restore.pre_restore_backup_key,
        "summary": restore.summary or {}, "error": restore.error,
        "created_at": to_ist_iso(restore.created_at),
        "started_at": to_ist_iso(restore.started_at),
        "finished_at": to_ist_iso(restore.finished_at),
    }
