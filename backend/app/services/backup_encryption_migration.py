"""Bringing the backups already on disk under encryption at rest, and moving them between keys (WS-13).

Both operations are repeat-safe and safe to interrupt: a file is only replaced after the new one has been written
and read back (for a first encryption, after its SHA-256 matched the checksum the PC gave), and the database row
is brought in line with whatever the file's own header says, so a run that stopped between the two heals itself.
"""
import hashlib
import os
from typing import Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_config import get_logger
from app.models.portal_core import CompanyBackup
from app.services import backup_crypto
from app.services import backups as svc

logger = get_logger("app.services.backup_encryption_migration")


def _plain_sha256(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


async def encrypt_existing(db: AsyncSession) -> Dict[str, int]:
    """Encrypt every stored plain backup file with the active key. Returns counts."""
    key_id = backup_crypto.active_key_id()
    result = {"encrypted": 0, "already": 0, "missing": 0, "failed": 0}
    if key_id is None:
        raise backup_crypto.CryptoError("No active backup encryption key is set.")
    rows = (await db.execute(select(CompanyBackup).where(CompanyBackup.status == "stored"))).scalars().all()
    for row in rows:
        path = svc.file_path(row)
        if not path.exists():
            result["missing"] += 1
            continue
        try:
            header_key = backup_crypto.read_header(path)
            if header_key is not None:                 # encrypted already (the row may not know yet)
                if row.encryption_key_id != header_key:
                    row.encryption_key_id = header_key
                result["already"] += 1
                continue
            if row.sha256 and _plain_sha256(path) != row.sha256:
                logger.warning(f"Backup {row.backup_key} does not match its checksum; left as it is.")
                result["failed"] += 1
                continue
            sealed = path.with_suffix(".zip.enc.tmp")
            backup_crypto.encrypt_file(path, sealed, key_id)
            check = hashlib.sha256()
            for block in backup_crypto.decrypt_stream(sealed):
                check.update(block)
            if row.sha256 and check.hexdigest() != row.sha256:
                sealed.unlink(missing_ok=True)
                result["failed"] += 1
                continue
            os.replace(sealed, path)
            row.encryption_key_id = key_id
            result["encrypted"] += 1
        except Exception as e:
            logger.warning(f"Could not encrypt backup {row.backup_key}: {type(e).__name__}")
            result["failed"] += 1
    await db.commit()
    return result


async def rewrap_all(db: AsyncSession) -> Dict[str, int]:
    """Re-encrypt every encrypted backup under the active key (key rotation)."""
    key_id = backup_crypto.active_key_id()
    if key_id is None:
        raise backup_crypto.CryptoError("No active backup encryption key is set.")
    result = {"rewrapped": 0, "already": 0, "missing": 0, "failed": 0}
    rows = (await db.execute(select(CompanyBackup).where(CompanyBackup.status == "stored"))).scalars().all()
    for row in rows:
        path = svc.file_path(row)
        if not path.exists():
            result["missing"] += 1
            continue
        try:
            current = backup_crypto.read_header(path)
            if current is None:
                result["failed"] += 1                  # a plain file: encrypt_existing handles it
                continue
            if backup_crypto.rewrap_file(path, key_id):
                result["rewrapped"] += 1
            else:
                result["already"] += 1
            row.encryption_key_id = key_id
        except Exception as e:
            logger.warning(f"Could not re-wrap backup {row.backup_key}: {type(e).__name__}")
            result["failed"] += 1
    await db.commit()
    return result
