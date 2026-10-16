"""Restore drill (WS-13): prove that the newest backup of each company can actually be used.

Daily, per company with a stored backup: the file is opened (decrypted when encrypted), its SHA-256 compared with
the checksum the PC gave, the ZIP's CRCs tested, the manifest read and every listed file's object count compared
with it. The result replaces the company's row in backup_drill_results; a failure is shown in sync health and
counts as a sync issue. Nothing is written to the books.
"""
import asyncio
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime_utils import get_ist_now
from app.core.logging_config import get_logger
from app.models.portal_core import BackupDrillResult, CompanyBackup
from app.services import backup_archive, backup_crypto
from app.services import backups as svc

logger = get_logger("app.services.backup_drill")


async def drill_company(db: AsyncSession, company_id: int) -> Optional[BackupDrillResult]:
    """Check the company's newest stored backup. None when it has none (nothing to drill)."""
    backup = (await db.execute(select(CompanyBackup).where(
        CompanyBackup.company_id == company_id, CompanyBackup.status == "stored",
        CompanyBackup.kind.in_(("hourly", "manual"))).order_by(CompanyBackup.taken_at.desc()).limit(1))).scalars().first()
    if backup is None:
        return None
    ok, problem, counts = True, None, None
    try:
        if not svc.file_path(backup).exists():
            raise backup_archive.ArchiveError("The newest backup's file is not on the server.")
        with svc.plaintext_file(backup) as path:
            if backup.sha256 and svc.sha256_of(path) != backup.sha256:
                raise backup_archive.ArchiveError("The newest backup no longer matches its checksum.")
            manifest = await asyncio.to_thread(backup_archive.validate_archive, path)
            counts = manifest.get("records")
    except (backup_archive.ArchiveError, backup_crypto.CryptoError) as e:
        ok, problem = False, str(e)[:500]
    except Exception as e:
        ok, problem = False, f"The check itself failed ({type(e).__name__})."
    row = (await db.execute(select(BackupDrillResult).where(BackupDrillResult.company_id == company_id))).scalars().first()
    if row is None:
        row = BackupDrillResult(company_id=company_id)
        db.add(row)
    row.backup_id, row.backup_key, row.checked_at = backup.backup_id, backup.backup_key, get_ist_now()
    row.ok, row.problem, row.record_counts = ok, problem, counts
    await db.commit()
    return row


async def drill_all(db: AsyncSession) -> int:
    ids = (await db.execute(select(CompanyBackup.company_id).where(CompanyBackup.status == "stored").distinct())).scalars().all()
    done = 0
    for company_id in ids:
        if await drill_company(db, company_id) is not None:
            done += 1
    return done


async def drill_summary(db: AsyncSession, company_id: int) -> Optional[dict]:
    row = (await db.execute(select(BackupDrillResult).where(BackupDrillResult.company_id == company_id))).scalars().first()
    if row is None:
        return None
    return {"ok": bool(row.ok), "checked_at": row.checked_at.isoformat() if row.checked_at else None,
            "backup_key": row.backup_key, "problem": row.problem}


async def drill_worker(interval_seconds: int = 24 * 3600) -> None:
    from app.services.google_drive import session_factory
    await asyncio.sleep(600)
    while True:
        try:
            async with session_factory() as db:
                await drill_all(db)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(f"Backup drill worker: {type(e).__name__}: {e}")
        await asyncio.sleep(interval_seconds)
