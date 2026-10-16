"""Google Drive copies of company backups.

After a backup is stored and verified on the server, the same file is copied to the company's linked Google
Drive. It all happens on the server: no Google token ever reaches a PC.

  * Link: OAuth 2.0 authorization-code flow (web application client) from the app's Backup page, with the
    least-privilege scope drive.file (the app sees only files it created) plus openid/email, to show which
    account is linked. `state` is a signed, 10-minute token bound to the user and company.
  * The refresh token is stored encrypted with Fernet (SECRETS_ENCRYPTION_KEY), per company, and is never
    returned by an API or logged.
  * Folder: "MyTally Backups" / "<company name>", created once; its id is stored.
  * Upload: Drive resumable upload, named by the backup key, tagged with appProperties. A retry first looks the
    file up by its stored id, then by name and properties in the folder, so it never makes a second copy; the
    size and MD5 Drive reports are checked against the local file.
  * Retention: the keys_to_keep rule decides here; a Drive file is deleted only when MyTally recorded its id and
    Drive's own appProperties confirm this company and backup made it.
  * A Drive failure never fails the backup: each backup carries drive_status/drive_error, retried with backoff.
    A revoked or expired token marks the link "needs_relink".
"""
import hashlib
import json
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import httpx
import jwt
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.datetime_utils import get_ist_now
from app.core.logging_config import get_logger
from app.models.portal_core import CompanyBackup, DriveFileDeletion, GoogleDriveLink
from app.services import backups as backup_svc

logger = get_logger("app.services.google_drive")

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
DRIVE_FILES = "https://www.googleapis.com/drive/v3/files"
DRIVE_UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
SCOPES = "openid email https://www.googleapis.com/auth/drive.file"
ROOT_FOLDER = "MyTally Backups"
FOLDER_MIME = "application/vnd.google-apps.folder"
STATE_MINUTES = 10
MAX_ATTEMPTS = 8
APP_TAG = "mytally"

REASON_NEEDS_RELINK = "Google no longer accepts the saved sign-in. Reconnect Google Drive on the Backup page."
REASON_QUOTA = "The Google Drive is full. Free some space or use another account; the copy is retried."


class DriveError(Exception):
    """A Drive call failed. retryable=False for a refusal that trying again will not change."""

    def __init__(self, message: str, retryable: bool = True, needs_relink: bool = False):
        super().__init__(message)
        self.message, self.retryable, self.needs_relink = message, retryable, needs_relink


def client_factory() -> httpx.AsyncClient:
    """Replaced in tests so that no request leaves the machine."""
    return httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=15.0, read=600.0, write=600.0))


# ── Configuration, encryption, state ─────────────────────────────────────────

def configured() -> bool:
    return bool(settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET
                and settings.GOOGLE_OAUTH_REDIRECT_URI and _fernet() is not None)


def _fernet() -> Optional[Fernet]:
    key = (settings.SECRETS_ENCRYPTION_KEY or "").strip()
    if not key:
        return None
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError):
        return None


def encrypt_secret(plain: str) -> str:
    f = _fernet()
    if f is None:
        raise DriveError("SECRETS_ENCRYPTION_KEY is not set on the server.", retryable=False)
    return f.encrypt(plain.encode()).decode()


def decrypt_secret(token: str) -> str:
    f = _fernet()
    if f is None:
        raise DriveError("SECRETS_ENCRYPTION_KEY is not set on the server.", retryable=False)
    try:
        return f.decrypt(token.encode()).decode()
    except InvalidToken:
        raise DriveError("The stored Google sign-in cannot be read with this server's key.", retryable=False,
                         needs_relink=True)


def make_state(user_id: int, company_id: int) -> str:
    payload = {"u": user_id, "c": company_id, "n": secrets.token_urlsafe(12), "p": "gdrive",
               "exp": datetime.utcnow() + timedelta(minutes=STATE_MINUTES)}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def read_state(state: str) -> Tuple[int, int]:
    """(user_id, company_id) a state was made for. Raises DriveError for a forged, expired or foreign one."""
    try:
        payload = jwt.decode(state, settings.JWT_SECRET, algorithms=["HS256"])
        if payload.get("p") != "gdrive":
            raise ValueError("wrong purpose")
        return int(payload["u"]), int(payload["c"])
    except Exception:
        raise DriveError("This Google sign-in link has expired or is not valid. Start again from the Backup page.",
                         retryable=False)


def authorization_url(user_id: int, company_id: int) -> str:
    query = urlencode({
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID, "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
        "response_type": "code", "scope": SCOPES, "access_type": "offline", "prompt": "consent",
        "include_granted_scopes": "false", "state": make_state(user_id, company_id),
    })
    return f"{AUTH_URL}?{query}"


# ── Google calls ─────────────────────────────────────────────────────────────

def _problem(resp: httpx.Response) -> DriveError:
    """Turn a failed Google response into a DriveError that says what to do."""
    try:
        body = resp.json()
    except Exception:
        body = {}
    err = body.get("error") if isinstance(body, dict) else None
    reasons = []
    if isinstance(err, dict):
        reasons = [str(e.get("reason", "")) for e in (err.get("errors") or []) if isinstance(e, dict)]
        message = err.get("message") or ""
    else:
        message = str(body.get("error_description") or err or "") if isinstance(body, dict) else ""
    if resp.status_code == 401 or (isinstance(err, str) and err in ("invalid_grant", "invalid_token")):
        return DriveError(REASON_NEEDS_RELINK, retryable=False, needs_relink=True)
    if "storageQuotaExceeded" in reasons:
        return DriveError(REASON_QUOTA, retryable=True)
    if resp.status_code == 429 or any(r in ("rateLimitExceeded", "userRateLimitExceeded") for r in reasons):
        return DriveError("Google is limiting requests; the copy is retried shortly.", retryable=True)
    if resp.status_code == 403:
        return DriveError(f"Google refused the request ({message or '403'}). Reconnect Google Drive and allow access.",
                          retryable=False, needs_relink=True)
    if resp.status_code >= 500:
        return DriveError(f"Google had a problem ({resp.status_code}); the copy is retried.", retryable=True)
    return DriveError(f"Google Drive answered {resp.status_code}: {message[:150]}", retryable=False)


async def exchange_code(code: str) -> Dict[str, Any]:
    async with client_factory() as http:
        resp = await http.post(TOKEN_URL, data={
            "code": code, "client_id": settings.GOOGLE_OAUTH_CLIENT_ID, "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI, "grant_type": "authorization_code"})
        if resp.status_code != 200:
            raise DriveError("Google did not accept the sign-in. Start again from the Backup page.", retryable=False)
        tokens = resp.json()
        email = None
        if tokens.get("access_token"):
            info = await http.get(USERINFO_URL, headers={"Authorization": f"Bearer {tokens['access_token']}"})
            if info.status_code == 200:
                email = info.json().get("email")
    return {"refresh_token": tokens.get("refresh_token"), "access_token": tokens.get("access_token"),
            "scope": tokens.get("scope", ""), "email": email}


async def access_token(link: GoogleDriveLink) -> str:
    refresh = decrypt_secret(link.refresh_token_enc)
    async with client_factory() as http:
        resp = await http.post(TOKEN_URL, data={
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID, "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "refresh_token": refresh, "grant_type": "refresh_token"})
    if resp.status_code != 200:
        raise _problem(resp)
    return resp.json()["access_token"]


async def revoke(refresh_token: str) -> None:
    async with client_factory() as http:
        await http.post(REVOKE_URL, data={"token": refresh_token})


def _q(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


async def _find_folder(http: httpx.AsyncClient, token: str, name: str, parent: Optional[str]) -> Optional[str]:
    q = f"name='{_q(name)}' and mimeType='{FOLDER_MIME}' and trashed=false and appProperties has {{ key='app' and value='{APP_TAG}' }}"
    if parent:
        q += f" and '{parent}' in parents"
    resp = await http.get(DRIVE_FILES, params={"q": q, "fields": "files(id)", "spaces": "drive"},
                          headers={"Authorization": f"Bearer {token}"})
    if resp.status_code != 200:
        raise _problem(resp)
    files = resp.json().get("files") or []
    return files[0]["id"] if files else None


async def _make_folder(http: httpx.AsyncClient, token: str, name: str, parent: Optional[str]) -> str:
    meta: Dict[str, Any] = {"name": name, "mimeType": FOLDER_MIME, "appProperties": {"app": APP_TAG}}
    if parent:
        meta["parents"] = [parent]
    resp = await http.post(DRIVE_FILES, params={"fields": "id"}, json=meta, headers={"Authorization": f"Bearer {token}"})
    if resp.status_code != 200:
        raise _problem(resp)
    return resp.json()["id"]


async def ensure_folder(link: GoogleDriveLink, company_name: str, token: str) -> str:
    """The company's folder id, creating "MyTally Backups/<company>" once. A stored id that Drive no longer
    knows (the user deleted the folder) is made again."""
    async with client_factory() as http:
        if link.folder_id:
            resp = await http.get(f"{DRIVE_FILES}/{link.folder_id}", params={"fields": "id,trashed"},
                                  headers={"Authorization": f"Bearer {token}"})
            if resp.status_code == 200 and not resp.json().get("trashed"):
                return link.folder_id
            if resp.status_code not in (200, 404):
                raise _problem(resp)
        root = await _find_folder(http, token, ROOT_FOLDER, None) or await _make_folder(http, token, ROOT_FOLDER, None)
        name = (company_name or "Company").strip()[:100] or "Company"
        folder = await _find_folder(http, token, name, root) or await _make_folder(http, token, name, root)
    link.folder_id = folder
    return folder


def _props(backup: CompanyBackup) -> Dict[str, str]:
    return {"app": APP_TAG, "company_id": str(backup.company_id), "backup_key": backup.backup_key,
            "sha256": backup.sha256 or ""}


def _md5_of(path) -> str:
    digest = hashlib.md5()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _matches(meta: Dict[str, Any], backup: CompanyBackup) -> bool:
    props = meta.get("appProperties") or {}
    return (not meta.get("trashed") and props.get("app") == APP_TAG
            and props.get("company_id") == str(backup.company_id) and props.get("backup_key") == backup.backup_key)


async def upload_backup(link: GoogleDriveLink, backup: CompanyBackup, company_name: str) -> str:
    """Copy a stored backup to Drive and return the file id. Safe to repeat: an existing copy is recognised and
    kept, never doubled. Raises DriveError."""
    path = backup_svc.file_path(backup)
    if backup.status != "stored" or not path.exists():
        raise DriveError("The backup file is not on the server any more.", retryable=False)
    token = await access_token(link)
    folder = await ensure_folder(link, company_name, token)
    auth = {"Authorization": f"Bearer {token}"}
    size, md5 = path.stat().st_size, _md5_of(path)
    fields = "id,size,md5Checksum,trashed,appProperties"

    async with client_factory() as http:
        # 1. a copy this backup already has
        if backup.drive_file_id:
            resp = await http.get(f"{DRIVE_FILES}/{backup.drive_file_id}", params={"fields": fields}, headers=auth)
            if resp.status_code == 200 and _matches(resp.json(), backup):
                meta = resp.json()
                if int(meta.get("size", -1)) == size and meta.get("md5Checksum") == md5:
                    return meta["id"]
            elif resp.status_code not in (200, 404):
                raise _problem(resp)
        # 2. one a lost answer left behind, found by name and properties in this folder
        q = (f"name='{_q(backup.backup_key + '.zip')}' and '{folder}' in parents and trashed=false and "
             f"appProperties has {{ key='backup_key' and value='{_q(backup.backup_key)}' }} and "
             f"appProperties has {{ key='company_id' and value='{backup.company_id}' }}")
        resp = await http.get(DRIVE_FILES, params={"q": q, "fields": f"files({fields})"}, headers=auth)
        if resp.status_code != 200:
            raise _problem(resp)
        for meta in resp.json().get("files") or []:
            if _matches(meta, backup) and int(meta.get("size", -1)) == size and meta.get("md5Checksum") == md5:
                return meta["id"]
        # 3. upload it: start a resumable session, then send the bytes in one request
        metadata = {"name": f"{backup.backup_key}.zip", "parents": [folder], "appProperties": _props(backup),
                    "mimeType": "application/zip"}
        start = await http.post(DRIVE_UPLOAD, params={"uploadType": "resumable", "fields": fields}, json=metadata,
                                headers={**auth, "X-Upload-Content-Type": "application/zip",
                                         "X-Upload-Content-Length": str(size)})
        if start.status_code != 200 or not start.headers.get("location"):
            raise _problem(start)

        async def body():
            with open(path, "rb") as f:
                for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
                    yield block
        put = await http.put(start.headers["location"], content=body(),
                             headers={"Content-Length": str(size), "Content-Type": "application/zip"})
        if put.status_code not in (200, 201):
            raise _problem(put)
        meta = put.json()
    if int(meta.get("size", -1)) != size or meta.get("md5Checksum") != md5:
        raise DriveError("Google Drive stored a file that does not match the backup; it is tried again.", retryable=True)
    return meta["id"]


async def delete_file(link: GoogleDriveLink, company_id: int, file_id: str, backup_key: str) -> bool:
    """Delete one Drive file, only after Drive's own appProperties say this company's MyTally made it for this
    backup. Returns True when it is gone (or already was). A file that is not ours is left alone and True is
    returned: there is nothing for MyTally to do about it."""
    token = await access_token(link)
    auth = {"Authorization": f"Bearer {token}"}
    async with client_factory() as http:
        got = await http.get(f"{DRIVE_FILES}/{file_id}", params={"fields": "id,appProperties,trashed"}, headers=auth)
        if got.status_code == 404:
            return True
        if got.status_code != 200:
            raise _problem(got)
        props = got.json().get("appProperties") or {}
        if props.get("app") != APP_TAG or props.get("company_id") != str(company_id) or props.get("backup_key") != backup_key:
            logger.warning(f"Drive file {file_id} is not a MyTally backup of company {company_id}; left alone.")
            return True
        resp = await http.delete(f"{DRIVE_FILES}/{file_id}", headers=auth)
        if resp.status_code not in (200, 204, 404):
            raise _problem(resp)
    return True


# ── Link state ───────────────────────────────────────────────────────────────

async def get_link(db: AsyncSession, company_id: int) -> Optional[GoogleDriveLink]:
    return (await db.execute(select(GoogleDriveLink).where(GoogleDriveLink.company_id == company_id))).scalars().first()


def status_of(link: Optional[GoogleDriveLink]) -> str:
    if link is None:
        return "not_linked"
    return "needs_relink" if link.status == "needs_relink" else "linked"


def link_ready(company) -> bool:
    """For the integrations list: the server is configured (the link itself is per company)."""
    return configured()


async def save_link(db: AsyncSession, company_id: int, user_id: int, email: Optional[str], refresh_token: str) -> GoogleDriveLink:
    link = await get_link(db, company_id)
    enc = encrypt_secret(refresh_token)
    if link is None:
        link = GoogleDriveLink(company_id=company_id, refresh_token_enc=enc)
        db.add(link)
    link.refresh_token_enc, link.google_email, link.linked_by_user_id = enc, email, user_id
    link.status, link.last_error = "linked", None
    # a different Google account has none of the old folders
    link.folder_id = None
    return link


# ── Per-backup work, retries, retention ──────────────────────────────────────

def backoff(attempts: int) -> timedelta:
    return timedelta(minutes=min(6 * 60, 5 * (2 ** max(0, attempts - 1))))


async def mark_pending(db: AsyncSession, backup: CompanyBackup) -> None:
    """A newly stored backup of a company with a working link is to be copied."""
    link = await get_link(db, backup.company_id)
    if link is not None and backup.drive_status in (None, "failed") and backup.drive_status != "uploaded":
        backup.drive_status, backup.drive_next_retry_at, backup.drive_error = "pending", get_ist_now(), None


async def push_backup(db: AsyncSession, backup: CompanyBackup, company_name: str) -> str:
    """Try to copy one backup now. Records the outcome on the backup; never raises. Returns its drive_status."""
    link = await get_link(db, backup.company_id)
    if link is None:
        backup.drive_status = None
        return "none"
    if link.status == "needs_relink":
        backup.drive_status, backup.drive_error, backup.drive_next_retry_at = "pending", REASON_NEEDS_RELINK, None
        return "pending"
    try:
        file_id = await upload_backup(link, backup, company_name)
        backup.drive_status, backup.drive_file_id, backup.drive_error = "uploaded", file_id, None
        backup.drive_uploaded_at, backup.drive_next_retry_at = get_ist_now(), None
        link.last_error = None
    except DriveError as e:
        backup.drive_attempts = (backup.drive_attempts or 0) + 1
        backup.drive_error = e.message[:500]
        if e.needs_relink:
            link.status, link.last_error = "needs_relink", e.message[:500]
            backup.drive_status, backup.drive_next_retry_at = "pending", None
        elif e.retryable and backup.drive_attempts < MAX_ATTEMPTS:
            backup.drive_status = "failed"
            backup.drive_next_retry_at = get_ist_now() + backoff(backup.drive_attempts)
        else:
            backup.drive_status, backup.drive_next_retry_at = "failed", None
    except Exception as e:     # a bug or a network error: never takes the backup down with it
        logger.warning(f"Drive copy of backup {backup.backup_key} failed: {type(e).__name__}: {e}")
        backup.drive_attempts = (backup.drive_attempts or 0) + 1
        backup.drive_error = f"Could not reach Google Drive ({type(e).__name__}); the copy is retried."
        backup.drive_status = "failed"
        backup.drive_next_retry_at = get_ist_now() + backoff(backup.drive_attempts) if backup.drive_attempts < MAX_ATTEMPTS else None
    return backup.drive_status or "none"


async def queue_deletions(db: AsyncSession, rows: List[CompanyBackup]) -> int:
    """Remember the Drive copies of backups retention is removing, so they are deleted from Drive too."""
    n = 0
    for row in rows:
        if row.drive_file_id:
            db.add(DriveFileDeletion(company_id=row.company_id, drive_file_id=row.drive_file_id, backup_key=row.backup_key))
            n += 1
    return n


async def run_deletions(db: AsyncSession, company_id: Optional[int] = None, limit: int = 50) -> int:
    q = select(DriveFileDeletion).where(DriveFileDeletion.attempts < MAX_ATTEMPTS)
    if company_id is not None:
        q = q.where(DriveFileDeletion.company_id == company_id)
    done = 0
    for item in (await db.execute(q.limit(limit))).scalars().all():
        link = await get_link(db, item.company_id)
        if link is None or link.status == "needs_relink":
            await db.delete(item)      # no way to reach it: the file stays in the user's Drive
            continue
        try:
            await delete_file(link, item.company_id, item.drive_file_id, item.backup_key)
            await db.delete(item)
            done += 1
        except DriveError as e:
            item.attempts += 1
            if e.needs_relink:
                link.status, link.last_error = "needs_relink", e.message[:500]
        except Exception:
            item.attempts += 1
    await db.commit()
    return done


async def retry_due(db: AsyncSession, limit: int = 20) -> int:
    """The worker's pass: copy backups that are pending or due for a retry, then do queued deletions."""
    from app.models.portal_core import Company
    now = get_ist_now()
    rows = (await db.execute(select(CompanyBackup).where(
        CompanyBackup.status == "stored", CompanyBackup.drive_status.in_(("pending", "failed")),
        CompanyBackup.drive_next_retry_at.isnot(None), CompanyBackup.drive_next_retry_at <= now).limit(limit))).scalars().all()
    for row in rows:
        company = (await db.execute(select(Company).where(Company.company_id == row.company_id))).scalars().first()
        await push_backup(db, row, company.name if company else "Company")
        await db.commit()
    await run_deletions(db)
    return len(rows)


# Replaced in tests, which run on their own database
def session_factory():
    from app.core.database import AsyncSessionLocal
    return AsyncSessionLocal()


async def push_in_background(backup_id: int) -> None:
    """Right after a backup is stored: one try at the copy, in its own session. A failure is only recorded."""
    from app.models.portal_core import Company
    try:
        async with session_factory() as db:
            backup = (await db.execute(select(CompanyBackup).where(CompanyBackup.backup_id == backup_id))).scalars().first()
            if backup is None or backup.drive_status != "pending":
                return
            company = (await db.execute(select(Company).where(Company.company_id == backup.company_id))).scalars().first()
            await push_backup(db, backup, company.name if company else "Company")
            await db.commit()
    except Exception as e:
        logger.warning(f"Drive copy of backup {backup_id} could not be recorded: {type(e).__name__}")


async def drive_worker(interval_seconds: int = 300) -> None:
    import asyncio
    await asyncio.sleep(60)
    while True:
        try:
            if configured():
                async with session_factory() as db:
                    await retry_due(db)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(f"Drive backup worker: {type(e).__name__}: {e}")
        await asyncio.sleep(interval_seconds)
