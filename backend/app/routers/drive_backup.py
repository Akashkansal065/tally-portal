"""Google Drive copies of backups: linking and unlinking from the app's Backup page (app/services/google_drive.py).

GET    /backups/drive            the link's state for the company being worked in (never a token)
POST   /backups/drive/connect    the Google sign-in address to send the browser to
GET    /backups/drive/callback   where Google sends the browser back; settles the link and returns to the app
DELETE /backups/drive            revoke at Google, delete the stored credential (files in Drive stay)
POST   /backups/drive/retry      copy backups that did not make it, now
Only administrators (who may manage backups) link or unlink.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.datetime_utils import get_ist_now, to_ist_iso
from app.core.logging_config import get_logger
from app.models.portal_core import AuditLog, Company, CompanyBackup, Role, User
from app.routers.admin import require_admin
from app.services import google_drive as drive
from app.services.integrations import is_enabled

logger = get_logger("app.routers.drive_backup")
router = APIRouter(prefix="/backups/drive", tags=["Backups (Google Drive)"])
KEY = "google_drive_backup"
ADMIN_ROLES = ("admin", "superadmin", "owner")


async def _state_payload(db: AsyncSession, company_id: int) -> dict:
    link = await drive.get_link(db, company_id)
    enabled = await is_enabled(db, company_id, KEY)
    configured = drive.configured()
    if not enabled:
        state = "off"
    elif not configured:
        state = "needs_setup"
    else:
        state = drive.status_of(link)
    counts = {}
    if link is not None:
        for row in (await db.execute(select(CompanyBackup.drive_status).where(
                CompanyBackup.company_id == company_id, CompanyBackup.status == "stored"))).scalars().all():
            counts[row or "none"] = counts.get(row or "none", 0) + 1
    return {
        "enabled": enabled, "configured": configured, "status": state,
        "google_email": link.google_email if link else None,
        "last_error": link.last_error if link else None,
        "linked_at": to_ist_iso(link.created_at) if link else None,
        "backup_counts": counts,
    }


@router.get("")
async def drive_state(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return await _state_payload(db, admin.company_id)


@router.post("/connect")
async def connect(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    if not await is_enabled(db, admin.company_id, KEY):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Google Drive backup is switched off. Turn it on in Admin → Integrations.")
    if not drive.configured():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Google Drive linking is not set up on this server yet. Ask your MyTally operator.")
    return {"authorization_url": drive.authorization_url(admin.user_id, admin.company_id)}


def _back(result: str, detail: str = "") -> RedirectResponse:
    base = (settings.APP_PUBLIC_URL or "").rstrip("/")
    target = f"{base}/backup?drive={result}"
    if detail:
        from urllib.parse import quote
        target += f"&message={quote(detail[:200])}"
    return RedirectResponse(url=target, status_code=status.HTTP_303_SEE_OTHER)


@router.get("/callback")
async def callback(code: Optional[str] = Query(None), state: Optional[str] = Query(None),
                   error: Optional[str] = Query(None), db: AsyncSession = Depends(get_db)):
    """Google sends the browser here after the person chose an account and allowed (or refused) access. The
    state proves which user and company started it and that it is recent; the user is re-checked here."""
    if error:
        return _back("cancelled", "Google Drive was not connected.")
    if not code or not state:
        return _back("error", "Google did not send what was needed. Start again from the Backup page.")
    try:
        user_id, company_id = drive.read_state(state)
    except drive.DriveError as e:
        return _back("error", e.message)
    user = (await db.execute(select(User).where(User.user_id == user_id))).scalars().first()
    role = (await db.execute(select(Role).where(Role.role_id == user.role_id))).scalars().first() if user else None
    if (user is None or not user.is_active or user.company_id != company_id
            or role is None or role.name.lower() not in ADMIN_ROLES):
        return _back("error", "You can no longer link Google Drive for this company.")
    if not drive.configured() or not await is_enabled(db, company_id, KEY):
        return _back("error", "Google Drive backup is not available for this company.")
    try:
        got = await drive.exchange_code(code)
        if not got.get("refresh_token"):
            return _back("error", "Google did not give lasting access. Remove MyTally from your Google account's "
                                  "connected apps and connect again.")
        if "drive.file" not in (got.get("scope") or ""):
            return _back("error", "Access to Google Drive was not allowed. Connect again and tick the Drive permission.")
        link = await drive.save_link(db, company_id, user_id, got.get("email"), got["refresh_token"])
        db.add(AuditLog(company_id=company_id, user_id=user_id, action="DRIVE_LINKED", entity_type="GoogleDrive",
                        entity_id=0, new_value={"google_email": got.get("email")}))
        # Backups still kept here and not yet on this Drive are copied
        for b in (await db.execute(select(CompanyBackup).where(
                CompanyBackup.company_id == company_id, CompanyBackup.status == "stored",
                CompanyBackup.drive_status.in_((None, "pending", "failed"))))).scalars().all():
            b.drive_status, b.drive_next_retry_at, b.drive_error, b.drive_attempts = "pending", get_ist_now(), None, 0
        await db.commit()
        await drive.retry_due(db, limit=3)
    except drive.DriveError as e:
        await db.rollback()
        return _back("error", e.message)
    except Exception as e:
        await db.rollback()
        logger.warning(f"Google Drive link failed: {type(e).__name__}")
        return _back("error", "Could not connect Google Drive. Try again.")
    return _back("linked")


@router.delete("")
async def unlink(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Revoke the token at Google and delete the stored credential. The files stay in the person's Drive."""
    link = await drive.get_link(db, admin.company_id)
    if link is None:
        return await _state_payload(db, admin.company_id)
    try:
        await drive.revoke(drive.decrypt_secret(link.refresh_token_enc))
    except Exception as e:
        # Revoking is best effort (the person may already have removed access); the credential goes either way
        logger.info(f"Revoking the Google token for company {admin.company_id} did not complete: {type(e).__name__}")
    await db.delete(link)
    for b in (await db.execute(select(CompanyBackup).where(
            CompanyBackup.company_id == admin.company_id, CompanyBackup.drive_status.in_(("pending", "failed"))))).scalars().all():
        b.drive_status, b.drive_next_retry_at, b.drive_error = None, None, None
    db.add(AuditLog(company_id=admin.company_id, user_id=admin.user_id, action="DRIVE_UNLINKED",
                    entity_type="GoogleDrive", entity_id=0, new_value={}))
    await db.commit()
    return await _state_payload(db, admin.company_id)


@router.post("/retry")
async def retry(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Copy the backups that failed or wait, now."""
    link = await drive.get_link(db, admin.company_id)
    if link is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Google Drive is not linked.")
    company = (await db.execute(select(Company).where(Company.company_id == admin.company_id))).scalars().first()
    rows = (await db.execute(select(CompanyBackup).where(
        CompanyBackup.company_id == admin.company_id, CompanyBackup.status == "stored",
        CompanyBackup.drive_status.in_(("pending", "failed"))).limit(10))).scalars().all()
    for row in rows:
        row.drive_attempts = 0
        await drive.push_backup(db, row, company.name if company else "Company")
        await db.commit()
    return await _state_payload(db, admin.company_id)
