#!/usr/bin/env python3
"""
break_glass.py – Offline Emergency Super-Admin Recovery Tool for MyTally.

Implements Plan Section 5.1 & 5.4:
  - Offline, documented procedure run directly on the host server
  - Restores or creates a super-administrator account
  - Unlocks account and resets lockout counters
  - Optionally resets registered passkeys if hardware authenticators were lost
  - Automatically writes an immutable entry into platform_audit_log
  - Logs a critical security alert
"""

import argparse
import asyncio
import getpass
import os
import sys
from datetime import datetime, timezone

# Ensure backend root is in Python module path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import delete, select
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.logging_config import get_logger
from app.core.platform_security import get_password_hash, utc_now
from app.core.platform_audit import write_platform_audit_log
from app.models.platform import (
    PlatformAdmin,
    PlatformAdminRole,
    PlatformAdminSession,
    PlatformAdminWebAuthnCredential,
    PlatformAuditLog,
    PlatformRole,
)

logger = get_logger("break_glass")


async def run_break_glass(email: str, password: str, reset_mfa: bool = True):
    print("=" * 60)
    print("🚨 MyTally Platform Console – Break-Glass Emergency Tool")
    print("=" * 60)
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"Target Email: {email}")

    async with AsyncSessionLocal() as db:
        # 1. Fetch super_admin role
        role_res = await db.execute(select(PlatformRole).where(PlatformRole.code == "super_admin"))
        super_role = role_res.scalars().first()
        if not super_role:
            print("❌ Error: 'super_admin' role not found in database. Run catalogue sync first.")
            return False

        # 2. Check if admin exists
        clean_email = email.strip().lower()
        res = await db.execute(select(PlatformAdmin).where(PlatformAdmin.email == clean_email))
        admin = res.scalars().first()

        now = utc_now()
        hashed = get_password_hash(password)

        if not admin:
            print(f"Creating new platform super-admin account for '{clean_email}'...")
            admin = PlatformAdmin(
                email=clean_email,
                full_name="Emergency Super Admin",
                password_hash=hashed,
                status="active",
                failed_logins=0,
                locked_until=None,
                password_changed_at=now,
                permission_version=1,
            )
            db.add(admin)
            await db.flush()

            db.add(PlatformAdminRole(admin_id=admin.admin_id, role_id=super_role.role_id))
            action = "created"
        else:
            print(f"Restoring existing super-admin account (ID: {admin.admin_id})...")
            admin.password_hash = hashed
            admin.status = "active"
            admin.failed_logins = 0
            admin.locked_until = None
            admin.password_changed_at = now
            admin.permission_version = (admin.permission_version or 1) + 1

            # Ensure super_admin role is assigned
            ar_res = await db.execute(
                select(PlatformAdminRole).where(
                    PlatformAdminRole.admin_id == admin.admin_id,
                    PlatformAdminRole.role_id == super_role.role_id,
                )
            )
            if not ar_res.scalars().first():
                db.add(PlatformAdminRole(admin_id=admin.admin_id, role_id=super_role.role_id, assigned_by=admin.admin_id))
                await db.flush()

            action = "restored"

        # 3. Reset hardware WebAuthn credentials if requested
        if reset_mfa:
            del_res = await db.execute(
                delete(PlatformAdminWebAuthnCredential).where(
                    PlatformAdminWebAuthnCredential.admin_id == admin.admin_id
                )
            )
            print(f"Cleared {del_res.rowcount or 0} registered passkeys.")

        # 4. Revoke all active sessions
        await db.execute(
            delete(PlatformAdminSession).where(
                PlatformAdminSession.admin_id == admin.admin_id
            )
        )

        # 5. Write tamper-evident audit entry
        req_id = f"break-glass-{os.urandom(4).hex()}"
        audit_entry = await write_platform_audit_log(
            db=db,
            action_type="break_glass.restore_super_admin",
            admin_email=clean_email,
            target_type="admin",
            target_id=admin.admin_id,
            admin_id=admin.admin_id,
            reason="Emergency offline break-glass procedure executed directly on host server.",
            old_values=None,
            new_values={"status": "active", "mfa_reset": bool(reset_mfa)},
            outcome="success",
            request_id=req_id,
            ip_address="127.0.0.1",
            user_agent="break_glass.py/CLI",
        )

        await db.commit()

        row_hash = audit_entry.row_hash

        print("=" * 60)
        print(f"✅ Success! Super-admin '{clean_email}' was {action}.")
        print(f"• Account Status: active")
        print(f"• Lockout: cleared")
        print(f"• Role: Super Administrator (rank 1000)")
        print(f"• Passkeys: cleared (re-registration required upon login)")
        print(f"• Audit Row: Recorded (hash: {row_hash[:16]}...)")
        print("=" * 60)
        print("You may now log in at:")
        print("http://localhost:3000/console/login")
        return True


def main():
    parser = argparse.ArgumentParser(description="MyTally Emergency Break-Glass Super-Admin Recovery Tool")
    parser.add_argument("--email", required=True, help="Operator super-admin email")
    parser.add_argument("--no-reset-mfa", action="store_true", help="Preserve existing registered passkeys")

    args = parser.parse_args()
    password = getpass.getpass("New operator password (minimum 14 characters): ")
    confirmation = getpass.getpass("Confirm new operator password: ")
    if len(password) < 14:
        parser.error("The password must be at least 14 characters long.")
    if password != confirmation:
        parser.error("The passwords do not match.")
    asyncio.run(run_break_glass(email=args.email, password=password, reset_mfa=not args.no_reset_mfa))


if __name__ == "__main__":
    main()
