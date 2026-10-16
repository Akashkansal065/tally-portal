"""Company backups and restores (app/services/backups.py).

/agent/backups/...  called by the sync agent signed in as a PC, for a company linked to that PC: what it should
                    do (backups asked for in the app, restores), uploading a backup in chunks, and a restore's
                    start and finish.
/backups/...        called from the app by an Admin, for the company they are working in: the list, "back up
                    now", download, restore (off until BACKUP_RESTORE_ENABLED) and cancelling a restore that has
                    not started.
"""
import math
import secrets
from datetime import datetime, timedelta
from typing import Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agent_auth import agent_device
from app.core.config import settings
from app.core.database import get_db
from app.core.datetime_utils import IST, get_ist_now
from app.core.permissions import bind_sync_company, get_current_user
from app.models.portal_core import Company, CompanyBackup, CompanyRestore, User
from app.routers.admin import require_admin
from app.core.logging_config import get_logger
from app.services import backups as svc

logger = get_logger("app.routers.backups")

agent_router = APIRouter(prefix="/agent/backups", tags=["Backups (sync agent)"], dependencies=[Depends(bind_sync_company)])
router = APIRouter(prefix="/backups", tags=["Backups"])

STUCK_RESTORE_HOURS = 6
RESTORE_OFF = ("Restoring a backup is not switched on yet. It writes into Tally, so it is switched on once a "
               "restore has been checked on a test company.")


class BackupIn(BaseModel):
    backup_key: str = Field(min_length=8, max_length=64)
    kind: str
    taken_at: datetime
    size_bytes: int = Field(gt=0)
    sha256: str = Field(min_length=64, max_length=64)
    chunk_size: int
    company_name: Optional[str] = Field(default=None, max_length=255)
    fingerprint: Optional[str] = Field(default=None, max_length=200)
    record_counts: Dict[str, int] = Field(default_factory=dict)


class FailedIn(BaseModel):
    error: str = Field(max_length=2000)


class RestoreStartIn(BaseModel):
    pre_restore_backup_key: str = Field(min_length=8, max_length=64)


class RestoreFinishIn(BaseModel):
    ok: bool
    summary: Dict[str, Dict[str, int]] = Field(default_factory=dict)
    error: Optional[str] = Field(default=None, max_length=4000)


class RestoreIn(BaseModel):
    confirm_company_name: str = Field(max_length=255)


# ── Shared ───────────────────────────────────────────────────────────────────

async def _company(db: AsyncSession, user: User) -> Company:
    company = (await db.execute(select(Company).where(Company.company_id == user.company_id))).scalars().first()
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found.")
    return company


def _check_key(key: str) -> None:
    if not svc.KEY_PATTERN.match(key or ""):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That is not a backup key.")


async def _backup_by_key(db: AsyncSession, company_id: int, key: str) -> CompanyBackup:
    _check_key(key)
    backup = (await db.execute(select(CompanyBackup).where(
        CompanyBackup.company_id == company_id, CompanyBackup.backup_key == key))).scalars().first()
    if backup is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup not found.")
    return backup


def _require_device(request: Request):
    device = agent_device(request)
    if device is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only a signed-in sync agent PC can do this.")
    return device


def _next_chunk(backup: CompanyBackup) -> int:
    """The first chunk not received yet; once all have arrived, the number of chunks (the last one is shorter, so
    received // chunk_size alone would ask for it again and again)."""
    if not backup.chunk_size:
        return 0
    if (backup.received_bytes or 0) >= (backup.size_bytes or 0):
        return math.ceil(backup.size_bytes / backup.chunk_size)
    return (backup.received_bytes or 0) // backup.chunk_size


def _download(backup: CompanyBackup, company: Company) -> FileResponse:
    path = svc.file_path(backup)
    if backup.status != "stored" or not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This backup's file is not on the server.")
    stamp = backup.taken_at.strftime("%Y%m%d-%H%M") if backup.taken_at else backup.backup_key
    safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in (company.name or "company"))[:60]
    from app.services import backup_crypto
    try:
        readable = svc.plaintext_copy(backup)
    except backup_crypto.CryptoError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    cleanup = BackgroundTask(lambda: readable.unlink(missing_ok=True)) if readable != path else None
    return FileResponse(path=str(readable), media_type="application/zip", filename=f"{safe_name}-{stamp}.zip",
                        background=cleanup)


# ── The sync agent ───────────────────────────────────────────────────────────

@agent_router.get("/jobs")
async def agent_jobs(request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """What the agent should do for this company: backups asked for in the app, and a restore."""
    _require_device(request)
    company = await _company(db, user)
    asked = (await db.execute(select(CompanyBackup).where(
        CompanyBackup.company_id == company.company_id, CompanyBackup.status == "requested"))).scalars().all()
    restore = (await db.execute(select(CompanyRestore).where(
        CompanyRestore.company_id == company.company_id, CompanyRestore.status == "requested"))).scalars().first()
    restores = []
    if restore is not None and settings.BACKUP_RESTORE_ENABLED:
        backup = (await db.execute(select(CompanyBackup).where(CompanyBackup.backup_id == restore.backup_id))).scalars().first()
        if backup is not None and backup.status == "stored":
            restores.append({"restore_id": restore.restore_id, "backup_key": backup.backup_key, "sha256": backup.sha256,
                             "size_bytes": backup.size_bytes, "fingerprint": backup.tally_fingerprint,
                             "company_name": backup.tally_company_name})
    return {"backups": [{"backup_key": b.backup_key, "kind": b.kind} for b in asked], "restores": restores}


@agent_router.post("")
async def register_backup(req: BackupIn, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Announce a backup the agent has made and is about to upload, or carry on with one it uploaded before.
    Answers where the upload stands: next_chunk is the first chunk the server does not have yet."""
    device = _require_device(request)
    company = await _company(db, user)
    _check_key(req.backup_key)
    if req.kind not in svc.KINDS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown kind of backup.")
    if req.size_bytes > settings.BACKUP_MAX_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="This backup is larger than the server accepts.")
    if not (svc.MIN_CHUNK_BYTES <= req.chunk_size <= svc.MAX_CHUNK_BYTES):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chunk size out of range.")
    sha = req.sha256.lower()
    if any(ch not in "0123456789abcdef" for ch in sha):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That is not a SHA-256 checksum.")

    problem = svc.storage_problem()
    if problem:
        raise HTTPException(status_code=status.HTTP_507_INSUFFICIENT_STORAGE, detail=problem)
    backup = (await db.execute(select(CompanyBackup).where(
        CompanyBackup.company_id == company.company_id, CompanyBackup.backup_key == req.backup_key))).scalars().first()
    if backup is not None and backup.status == "stored":
        if backup.sha256 != sha:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A different backup is already stored under this key.")
        return {"status": "stored", "next_chunk": math.ceil(backup.size_bytes / backup.chunk_size)}
    if backup is None:
        backup = CompanyBackup(company_id=company.company_id, account_id=company.account_id, backup_key=req.backup_key,
                               kind=req.kind, status="uploading", received_bytes=0)
        db.add(backup)
    elif (backup.sha256, backup.size_bytes, backup.chunk_size) != (sha, req.size_bytes, req.chunk_size):
        svc.discard_files(backup)   # another file under the same key (made again): what arrived so far is not of it
        backup.received_bytes = 0
    if backup.kind == "manual" and req.kind != "manual":
        req.kind = "manual"         # asked for in the app: it stays the backup that was asked for
    backup.kind, backup.status, backup.device_id, backup.error = req.kind, "uploading", device.device_id, None
    # Stored like every time here: IST without a zone. A time sent with its zone is moved to IST first.
    taken_at = req.taken_at.astimezone(IST).replace(tzinfo=None) if req.taken_at.tzinfo else req.taken_at
    backup.taken_at, backup.size_bytes, backup.sha256, backup.chunk_size = taken_at, req.size_bytes, sha, req.chunk_size
    backup.tally_company_name, backup.tally_fingerprint, backup.record_counts = req.company_name, req.fingerprint, req.record_counts
    await db.commit()
    return {"status": "uploading", "next_chunk": _next_chunk(backup)}


@agent_router.put("/{backup_key}/chunks/{index}")
async def upload_chunk(backup_key: str, index: int, request: Request, user: User = Depends(get_current_user),
                       db: AsyncSession = Depends(get_db)):
    """One chunk of the file, as raw bytes. Chunks arrive in order; sending one again is harmless."""
    _require_device(request)
    company = await _company(db, user)
    backup = await _backup_by_key(db, company.company_id, backup_key)
    if backup.status == "stored":
        return {"next_chunk": math.ceil(backup.size_bytes / backup.chunk_size)}
    if backup.status != "uploading":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This backup is not being uploaded.")
    chunks = math.ceil(backup.size_bytes / backup.chunk_size)
    if index < 0 or index >= chunks:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No such chunk.")
    expected = backup.chunk_size if index < chunks - 1 else backup.size_bytes - index * backup.chunk_size
    data = await request.body()
    if len(data) != expected:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Chunk {index} must be {expected} bytes.")
    following = _next_chunk(backup)
    if index > following:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Send chunk {following} first.",
                            headers={"X-Next-Chunk": str(following)})
    svc.write_chunk(backup, index * backup.chunk_size, data)
    if index == following:
        backup.received_bytes = index * backup.chunk_size + len(data)
        await db.commit()
    return {"next_chunk": _next_chunk(backup)}


@agent_router.post("/{backup_key}/complete")
async def complete_backup(backup_key: str, request: Request, background: BackgroundTasks,
                          user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Every chunk has been sent: check the file against its checksum and keep it."""
    _require_device(request)
    company = await _company(db, user)
    backup = await _backup_by_key(db, company.company_id, backup_key)
    if backup.status == "stored":
        return svc.backup_dict(backup)
    if backup.status != "uploading":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This backup is not being uploaded.")
    if (backup.received_bytes or 0) < backup.size_bytes:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Chunks are missing; send chunk {_next_chunk(backup)}.",
                            headers={"X-Next-Chunk": str(_next_chunk(backup))})
    if not svc.finish_file(backup):
        backup.received_bytes = 0
        await db.commit()
        raise HTTPException(status_code=422,
                            detail="The uploaded file does not match its checksum. Upload it again.",
                            headers={"X-Next-Chunk": "0"})
    now = get_ist_now()
    backup.status, backup.stored_at = "stored", now
    # A copy for the company's linked Google Drive, if it has one. Never part of whether the backup is stored.
    from app.services import google_drive
    from app.services.integrations import is_enabled
    wants_drive = False
    try:
        if google_drive.configured() and await is_enabled(db, company.company_id, "google_drive_backup"):
            await google_drive.mark_pending(db, backup)
            wants_drive = backup.drive_status == "pending"
    except Exception as e:
        logger.warning(f"Drive copy not queued for backup {backup.backup_key}: {type(e).__name__}")
    await svc.prune_company(db, company.company_id, now)
    await db.commit()
    if wants_drive:
        background.add_task(google_drive.push_in_background, backup.backup_id)
    return svc.backup_dict(backup)


@agent_router.post("/{backup_key}/failed")
async def backup_failed(backup_key: str, req: FailedIn, request: Request, user: User = Depends(get_current_user),
                        db: AsyncSession = Depends(get_db)):
    """The agent could not make a backup that was asked for in the app: say why, so the app stops waiting."""
    _require_device(request)
    company = await _company(db, user)
    backup = await _backup_by_key(db, company.company_id, backup_key)
    if backup.status != "stored":
        backup.status, backup.error = "failed", req.error
        await db.commit()
    return svc.backup_dict(backup)


@agent_router.get("/{backup_key}/download")
async def agent_download(backup_key: str, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """A stored backup of this company, for a restore on a PC that no longer has its own copy."""
    _require_device(request)
    company = await _company(db, user)
    return _download(await _backup_by_key(db, company.company_id, backup_key), company)


async def _agent_restore(db: AsyncSession, company_id: int, restore_id: int) -> CompanyRestore:
    restore = (await db.execute(select(CompanyRestore).where(
        CompanyRestore.restore_id == restore_id, CompanyRestore.company_id == company_id))).scalars().first()
    if restore is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restore not found.")
    return restore


@agent_router.post("/restores/{restore_id}/start")
async def start_restore(restore_id: int, req: RestoreStartIn, request: Request, user: User = Depends(get_current_user),
                        db: AsyncSession = Depends(get_db)):
    """The agent is about to write the backup into Tally. It must first have stored a backup of the company as it
    is now, which is the way back."""
    device = _require_device(request)
    if not settings.BACKUP_RESTORE_ENABLED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=RESTORE_OFF)
    company = await _company(db, user)
    restore = await _agent_restore(db, company.company_id, restore_id)
    if restore.status == "running" and restore.pre_restore_backup_key == req.pre_restore_backup_key and restore.device_id == device.device_id:
        return svc.restore_dict(restore)
    if restore.status != "requested":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"This restore is {restore.status}.")
    pre = await _backup_by_key(db, company.company_id, req.pre_restore_backup_key)
    if pre.status != "stored" or pre.kind != "pre_restore":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Store the backup taken before the restore first.")
    restore.status, restore.started_at, restore.device_id = "running", get_ist_now(), device.device_id
    restore.pre_restore_backup_key = pre.backup_key
    await db.commit()
    return svc.restore_dict(restore)


@agent_router.post("/restores/{restore_id}/finish")
async def finish_restore(restore_id: int, req: RestoreFinishIn, request: Request, user: User = Depends(get_current_user),
                         db: AsyncSession = Depends(get_db)):
    _require_device(request)
    company = await _company(db, user)
    restore = await _agent_restore(db, company.company_id, restore_id)
    if restore.status in ("completed", "failed"):
        return svc.restore_dict(restore)
    # A restore the agent turned down before writing anything (a different copy of the books open in Tally, or the
    # backup before it could not be stored) ends here too, so it is not handed out again
    if restore.status != "running" and not (restore.status == "requested" and not req.ok):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"This restore is {restore.status}.")
    restore.status = "completed" if req.ok else "failed"
    restore.summary, restore.error, restore.finished_at, restore.is_open = req.summary, req.error, get_ist_now(), None
    await db.commit()
    return svc.restore_dict(restore)


# ── The app ──────────────────────────────────────────────────────────────────

@router.get("")
async def list_backups(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    company = await _company(db, admin)
    rows = (await db.execute(select(CompanyBackup).where(CompanyBackup.company_id == company.company_id)
                             .order_by(CompanyBackup.created_at.desc(), CompanyBackup.backup_id.desc()))).scalars().all()
    restores = (await db.execute(select(CompanyRestore).where(CompanyRestore.company_id == company.company_id)
                                 .order_by(CompanyRestore.restore_id.desc()).limit(10))).scalars().all()
    return {"company": {"company_id": company.company_id, "name": company.name},
            "restore_enabled": settings.BACKUP_RESTORE_ENABLED, "keep_days": svc.KEEP_DAYS,
            "backups": [svc.backup_dict(r) for r in rows], "restores": [svc.restore_dict(r) for r in restores]}


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def request_backup(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Back up now: the company's sync agent makes it within a minute or so. Asking again while one is waiting
    answers with that one."""
    company = await _company(db, admin)
    waiting = (await db.execute(select(CompanyBackup).where(
        CompanyBackup.company_id == company.company_id, CompanyBackup.kind == "manual",
        CompanyBackup.status.in_(("requested", "uploading"))))).scalars().first()
    if waiting is not None:
        return svc.backup_dict(waiting)
    backup = CompanyBackup(company_id=company.company_id, account_id=company.account_id, backup_key="app-" + secrets.token_hex(12),
                           kind="manual", status="requested", requested_by_user_id=admin.user_id, received_bytes=0)
    db.add(backup)
    await db.commit()
    await db.refresh(backup)
    return svc.backup_dict(backup)


async def _company_backup(db: AsyncSession, company_id: int, backup_id: int) -> CompanyBackup:
    backup = (await db.execute(select(CompanyBackup).where(
        CompanyBackup.backup_id == backup_id, CompanyBackup.company_id == company_id))).scalars().first()
    if backup is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup not found.")
    return backup


@router.get("/{backup_id}/download")
async def download_backup(backup_id: int, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    company = await _company(db, admin)
    return _download(await _company_backup(db, company.company_id, backup_id), company)


@router.post("/{backup_id}/restore", status_code=status.HTTP_202_ACCEPTED)
async def request_restore(backup_id: int, req: RestoreIn, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Ask the company's sync agent to write this backup back into Tally. Only into the company it was taken
    from, and only from the same copy of the books; the agent backs up the company as it is before it starts."""
    if not settings.BACKUP_RESTORE_ENABLED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=RESTORE_OFF)
    company = await _company(db, admin)
    backup = await _company_backup(db, company.company_id, backup_id)
    if backup.status != "stored":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only a stored backup can be restored.")
    if req.confirm_company_name.strip().lower() != (company.name or "").strip().lower():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Type the company's name exactly to confirm.")
    if backup.tally_fingerprint and company.tally_fingerprint and backup.tally_fingerprint.strip() != company.tally_fingerprint.strip():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="This backup is of a different copy of the books than the one now synced, so it is not restored.")
    open_restore = (await db.execute(select(CompanyRestore).where(
        CompanyRestore.company_id == company.company_id, CompanyRestore.is_open == True))).scalars().first()  # noqa: E712
    if open_restore is not None:
        if open_restore.backup_id == backup.backup_id:
            return svc.restore_dict(open_restore)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Another restore of this company is waiting or running.")
    restore = CompanyRestore(company_id=company.company_id, backup_id=backup.backup_id, backup_key=backup.backup_key,
                             status="requested", is_open=True, requested_by_user_id=admin.user_id)
    db.add(restore)
    await db.commit()
    await db.refresh(restore)
    return svc.restore_dict(restore)


class RestoreNewIn(BaseModel):
    confirm_company_name: str = Field(max_length=255)
    new_company_name: Optional[str] = Field(default=None, max_length=150)


@router.post("/{backup_id}/restore-new-company")
async def restore_into_new_company(backup_id: int, req: RestoreNewIn, admin: User = Depends(require_admin),
                                   db: AsyncSession = Depends(get_db)):
    """Make a NEW MyTally company from a stored backup, written from the archive on the server (nothing goes to
    Tally). Administrators only, behind BACKUP_RESTORE_NEW_COMPANY_ENABLED; the company's name must be typed."""
    from app.services import backup_restore_new as restore_new
    if not settings.BACKUP_RESTORE_NEW_COMPANY_ENABLED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Restoring into a new company is not switched on yet.")
    company = await _company(db, admin)
    backup = await _company_backup(db, company.company_id, backup_id)
    if req.confirm_company_name.strip().lower() != (company.name or "").strip().lower():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Type the company's name exactly to confirm.")
    from app.services.billing.entitlements import get_entitlements
    from sqlalchemy import func
    ent = await get_entitlements(db, company.account_id)
    if ent.max_companies is not None:
        held = (await db.execute(select(func.count()).select_from(Company).where(
            Company.account_id == company.account_id))).scalar() or 0
        if held >= ent.max_companies:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Your plan allows {ent.max_companies} company(ies).")
    name = (req.new_company_name or f"{company.name} (restored {get_ist_now().strftime('%d %b %Y')})").strip()
    try:
        return await restore_new.restore_into_new_company(db, backup, company, admin.user_id, name)
    except restore_new.RestoreRefused as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post("/restores/{restore_id}/cancel")
async def cancel_restore(restore_id: int, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Withdraw a restore the agent has not started. One that is running finishes, unless it has run for more
    than STUCK_RESTORE_HOURS: then the PC stopped without saying (switched off mid-way), and it is closed as failed
    so the company can be restored again. Check the company in Tally before restoring again."""
    company = await _company(db, admin)
    restore = (await db.execute(select(CompanyRestore).where(
        CompanyRestore.restore_id == restore_id, CompanyRestore.company_id == company.company_id))).scalars().first()
    if restore is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restore not found.")
    now = get_ist_now()
    if restore.status == "requested":
        restore.status, restore.is_open, restore.finished_at = "cancelled", None, now
        await db.commit()
    elif restore.status == "running":
        if restore.started_at is None or now - restore.started_at < timedelta(hours=STUCK_RESTORE_HOURS):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The restore has started and cannot be stopped.")
        restore.status, restore.is_open, restore.finished_at = "failed", None, now
        restore.error = (f"The sync agent did not report back within {STUCK_RESTORE_HOURS} hours; it may have stopped "
                         "part-way. Check the company in Tally; the backup taken before the restore is kept.")
        await db.commit()
    return svc.restore_dict(restore)
