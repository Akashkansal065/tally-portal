"""Encryption at rest for server-held backups: operator commands.

    python scripts/backup_crypto.py new-key          print a new 32-byte key (base64) to put in BACKUP_ENCRYPTION_KEYS
    python scripts/backup_crypto.py encrypt-existing encrypt the plain backup files already stored
    python scripts/backup_crypto.py rewrap           re-encrypt every encrypted backup under the active key
    python scripts/backup_crypto.py status           how many backups are on which key

Run from backend/ with the server's .env. Safe to run again and to interrupt.
"""
import asyncio
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


async def main(command: str) -> int:
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.portal_core import CompanyBackup
    from app.services import backup_crypto, backup_encryption_migration as mig

    if command == "new-key":
        print(backup_crypto.generate_key())
        return 0
    async with AsyncSessionLocal() as db:
        if command == "encrypt-existing":
            print(await mig.encrypt_existing(db))
        elif command == "rewrap":
            print(await mig.rewrap_all(db))
        elif command == "status":
            rows = (await db.execute(select(CompanyBackup.encryption_key_id).where(CompanyBackup.status == "stored"))).scalars().all()
            print(dict(Counter(k or "plain" for k in rows)))
        else:
            print(__doc__)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "")))
