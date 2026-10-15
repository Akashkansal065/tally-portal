"""
platform_catalogue.py – Canonical definition of platform operator permissions and system roles.

Syncs the catalogue to the database at startup.
Operators assign permissions via roles; they cannot invent them.
"""

from __future__ import annotations

from typing import Dict, List, NamedTuple, Set
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging_config import get_logger
from app.core.security import get_password_hash
from app.models.platform import (
    PlatformAdmin,
    PlatformAdminRole,
    PlatformPermission,
    PlatformRetentionPolicy,
    PlatformRole,
    PlatformRolePermission,
)

logger = get_logger("app.core.platform_catalogue")


class PermissionDef(NamedTuple):
    code: str
    resource: str
    action: str
    description: str
    is_sensitive: bool = False


# Canonical catalogue of all platform operator permissions
PERMISSIONS_CATALOGUE: List[PermissionDef] = [
    # ── Users Resource ──
    PermissionDef("users.read", "users", "read", "List and open customer user records, PII masked", False),
    PermissionDef("users.read_pii", "users", "read_pii", "View customer email and phone unmasked", False),
    PermissionDef("users.create", "users", "create", "Create a user in a customer account", False),
    PermissionDef("users.update", "users", "update", "Edit user profile, role in account, company access", False),
    PermissionDef("users.suspend", "users", "suspend", "Suspend, reinstate, lock and unlock customer users", False),
    PermissionDef("users.reset_password", "users", "reset_password", "Force password reset or issue temporary password", False),
    PermissionDef("users.revoke_sessions", "users", "revoke_sessions", "Revoke customer user sessions and agent devices", False),
    PermissionDef("users.soft_delete", "users", "soft_delete", "Soft-delete customer user with retention recovery", False),
    PermissionDef("users.hard_delete", "users", "hard_delete", "Permanently anonymise user personal data (step-up)", True),
    PermissionDef("users.impersonate", "users", "impersonate", "Time-boxed read-only tenant impersonation (step-up)", True),
    PermissionDef("users.impersonate_write", "users", "impersonate_write", "Allow write mutations during tenant impersonation (step-up)", True),
    PermissionDef("users.export", "users", "export", "Download customer user list export (step-up)", True),

    # ── Platform Operators Resource ──
    PermissionDef("admins.read", "admins", "read", "List and view platform operator profiles", False),
    PermissionDef("admins.create", "admins", "create", "Invite or create new platform operator", False),
    PermissionDef("admins.update", "admins", "update", "Update operator status, details or IP allowlist", False),
    PermissionDef("admins.assign_roles", "admins", "assign_roles", "Assign roles to operators (step-up)", True),
    PermissionDef("admins.reset_mfa", "admins", "reset_mfa", "Reset operator registered passkeys (step-up)", True),
    PermissionDef("admins.revoke_sessions", "admins", "revoke_sessions", "Revoke operator sessions", False),
    PermissionDef("admins.delete", "admins", "delete", "Delete or remove a platform operator", True),

    # ── Platform Roles Resource ──
    PermissionDef("roles.read", "roles", "read", "View platform roles and permission catalogue", False),
    PermissionDef("roles.manage", "roles", "manage", "Create, modify or delete platform roles (step-up)", True),

    # ── Audit Log Resource ──
    PermissionDef("audit.read", "audit", "read", "View operator audit logs and verify hash chain", False),
    PermissionDef("audit.export", "audit", "export", "Export operator audit log records (step-up)", True),

    # ── Data Retention & Compliance ──
    PermissionDef("retention.read", "retention", "read", "View platform data retention policies and legal schedules", False),

    # ── Platform Billing Resource ──
    PermissionDef("billing.manage", "billing", "manage", "Manage billing subscriptions, orders and invoices", False),

    # ── Console Page Access ──
    PermissionDef("page.users", "page", "users", "Access Users console UI", False),
    PermissionDef("page.admins", "page", "admins", "Access Operators console UI", False),
    PermissionDef("page.roles", "page", "roles", "Access Roles & Permissions console UI", False),
    PermissionDef("page.audit", "page", "audit", "Access Audit Log console UI", False),
    PermissionDef("page.billing", "page", "billing", "Access Billing console UI", False),
    PermissionDef("page.retention", "page", "retention", "Access Data Retention console UI", False),
]

SENSITIVE_PERMISSIONS: Set[str] = {p.code for p in PERMISSIONS_CATALOGUE if p.is_sensitive}


class RoleDef(NamedTuple):
    code: str
    name: str
    description: str
    rank: int
    permissions: List[str]


SYSTEM_ROLES: List[RoleDef] = [
    RoleDef(
        code="super_admin",
        name="Super Administrator",
        description="Full platform operator control including role assignments and security",
        rank=1000,
        permissions=[p.code for p in PERMISSIONS_CATALOGUE],
    ),
    RoleDef(
        code="admin",
        name="Platform Administrator",
        description="Platform operations excluding sensitive role changes and passkey resets",
        rank=800,
        permissions=[
            p.code for p in PERMISSIONS_CATALOGUE
            if p.code not in {"admins.assign_roles", "admins.reset_mfa", "roles.manage"}
        ],
    ),
    RoleDef(
        code="support",
        name="Customer Support",
        description="Customer user support: view, suspend, reset password, revoke sessions",
        rank=400,
        permissions=[
            "users.read",
            "users.suspend",
            "users.reset_password",
            "users.revoke_sessions",
            "page.users",
        ],
    ),
    RoleDef(
        code="billing",
        name="Platform Billing Operator",
        description="Access operator billing console and subscription management",
        rank=400,
        permissions=[
            "billing.manage",
            "page.billing",
        ],
    ),
    RoleDef(
        code="auditor",
        name="Platform Auditor",
        description="Read-only access to customer users, operators, roles, and audit trail",
        rank=300,
        permissions=[
            "users.read",
            "admins.read",
            "roles.read",
            "audit.read",
            "retention.read",
            "page.users",
            "page.admins",
            "page.roles",
            "page.audit",
            "page.retention",
        ],
    ),
]


async def sync_platform_catalogue(db: AsyncSession) -> None:
    """Synchronises the permission catalogue and system roles with the database."""
    # 1. Sync permissions
    existing_perms_res = await db.execute(select(PlatformPermission))
    existing_perms = {p.code: p for p in existing_perms_res.scalars().all()}

    for p_def in PERMISSIONS_CATALOGUE:
        if p_def.code in existing_perms:
            perm = existing_perms[p_def.code]
            perm.resource = p_def.resource
            perm.action = p_def.action
            perm.description = p_def.description
            perm.is_sensitive = p_def.is_sensitive
        else:
            new_perm = PlatformPermission(
                code=p_def.code,
                resource=p_def.resource,
                action=p_def.action,
                description=p_def.description,
                is_sensitive=p_def.is_sensitive,
            )
            db.add(new_perm)

    await db.flush()

    # Reload permissions mapping code -> permission_id
    all_perms_res = await db.execute(select(PlatformPermission))
    perm_id_by_code = {p.code: p.permission_id for p in all_perms_res.scalars().all()}

    # 2. Sync system roles
    existing_roles_res = await db.execute(select(PlatformRole))
    existing_roles = {r.code: r for r in existing_roles_res.scalars().all()}

    for r_def in SYSTEM_ROLES:
        role = existing_roles.get(r_def.code)
        if role:
            role.name = r_def.name
            role.description = r_def.description
            role.rank = r_def.rank
            role.is_system = True
        else:
            role = PlatformRole(
                code=r_def.code,
                name=r_def.name,
                description=r_def.description,
                rank=r_def.rank,
                is_system=True,
            )
            db.add(role)
            await db.flush()
            existing_roles[r_def.code] = role

        # Reconcile role permissions for this system role
        wanted_perm_ids = {perm_id_by_code[code] for code in r_def.permissions if code in perm_id_by_code}
        current_rps_res = await db.execute(
            select(PlatformRolePermission).where(PlatformRolePermission.role_id == role.role_id)
        )
        current_rps = current_rps_res.scalars().all()
        current_perm_ids = {rp.permission_id for rp in current_rps}

        # Add missing
        for pid in wanted_perm_ids - current_perm_ids:
            db.add(PlatformRolePermission(role_id=role.role_id, permission_id=pid))

        # Delete obsolete (only for system roles to maintain strictness)
        for rp in current_rps:
            if rp.permission_id not in wanted_perm_ids:
                await db.delete(rp)

    await db.commit()
    logger.info("Platform permissions and system roles synced successfully.")

    # 3. Sync default retention policies
    await sync_default_retention_policies(db)


DEFAULT_RETENTION_POLICIES = [
    {
        "data_category": "tax_and_accounting",
        "title": "Tax, Invoices, Vouchers & Financial Ledgers",
        "retention_period_days": 2920,
        "legal_basis": "Companies Act 2013 (Sec 128) & CGST Act 2017 (Sec 36)",
        "action_on_expiry": "Statutory Archive (Immutable)",
        "description": "Financial ledgers, transactions, vouchers, tax invoices, and credit notes preserved for mandatory regulatory audit.",
    },
    {
        "data_category": "customer_user_accounts",
        "title": "Customer User Accounts & Identifiers",
        "retention_period_days": 30,
        "legal_basis": "GDPR Art. 17 (Right to Erasure) & DPDP Act",
        "action_on_expiry": "Irreversible Anonymisation",
        "description": "Soft-deleted user personal data is retained for a 30-day recovery grace period, after which PII is permanently redacted.",
    },
    {
        "data_category": "platform_operator_audit_logs",
        "title": "Platform Operator Audit Trail",
        "retention_period_days": 2555,
        "legal_basis": "SOC 2 Type II & ISO/IEC 27001 Security Management",
        "action_on_expiry": "Immutable Chained Storage",
        "description": "Tamper-evident cryptographically chained audit logs tracking all operator access and sensitive mutations.",
    },
    {
        "data_category": "device_and_user_sessions",
        "title": "Authentication Sessions & Tokens",
        "retention_period_days": 90,
        "legal_basis": "IT Security Best Practices & Token Hygiene",
        "action_on_expiry": "Purge Expired Sessions",
        "description": "Revoked or expired device and web authentication session records pruned periodically.",
    },
    {
        "data_category": "login_security_attempts",
        "title": "Login Attempts & Brute-Force Forensics",
        "retention_period_days": 7,
        "legal_basis": "Intrusion Prevention & Rate Limiting Verification",
        "action_on_expiry": "Nightly Automated Purge",
        "description": "Hashed email and IP address login attempt tracking records pruned after 7 days.",
    },
]


async def sync_default_retention_policies(db: AsyncSession) -> None:
    """Synchronises statutory data retention policies into the database."""
    try:
        existing_res = await db.execute(select(PlatformRetentionPolicy))
        existing = {p.data_category: p for p in existing_res.scalars().all()}
        for pol_data in DEFAULT_RETENTION_POLICIES:
            cat = pol_data["data_category"]
            if cat not in existing:
                p = PlatformRetentionPolicy(
                    data_category=cat,
                    title=pol_data["title"],
                    retention_period_days=pol_data["retention_period_days"],
                    legal_basis=pol_data["legal_basis"],
                    action_on_expiry=pol_data["action_on_expiry"],
                    description=pol_data["description"],
                )
                db.add(p)
        await db.commit()
    except Exception as exc:
        logger.warning(f"Default retention policy sync failed (non-fatal): {exc}")



async def bootstrap_first_super_admin(
    db: AsyncSession,
    email: Optional[str] = None,
    password: Optional[str] = None,
    full_name: str = "Super Admin",
) -> Optional[PlatformAdmin]:
    """
    One-time bootstrap of the first super-admin.
    Per Section 1.1: If platform_admins is completely empty, names from PLATFORM_ADMIN_EMAILS
    may claim or receive the first super-admin.
    """
    count_res = await db.execute(select(PlatformAdmin))
    if count_res.scalars().first() is not None:
        # Table already has operators, bootstrap is a no-op
        return None

    target_email = email
    if not target_email:
        configured = [e.strip().lower() for e in settings.PLATFORM_ADMIN_EMAILS.split(",") if e.strip()]
        if not configured:
            return None
        target_email = configured[0]

    target_email = target_email.strip().lower()
    initial_password = password or settings.PLATFORM_ADMIN_INITIAL_PASSWORD
    if not initial_password:
        logger.warning(
            "Platform operator bootstrap was skipped because no initial password is configured. "
            "Set PLATFORM_ADMIN_INITIAL_PASSWORD in the deployment secret store or use the break-glass tool."
        )
        return None

    # Find super_admin role
    role_res = await db.execute(select(PlatformRole).where(PlatformRole.code == "super_admin"))
    super_role = role_res.scalars().first()
    if not super_role:
        await sync_platform_catalogue(db)
        role_res = await db.execute(select(PlatformRole).where(PlatformRole.code == "super_admin"))
        super_role = role_res.scalars().first()

    admin = PlatformAdmin(
        email=target_email,
        full_name=full_name,
        password_hash=get_password_hash(initial_password),
        status="active",
        failed_logins=0,
        permission_version=1,
    )
    db.add(admin)
    await db.flush()

    if super_role:
        db.add(PlatformAdminRole(admin_id=admin.admin_id, role_id=super_role.role_id))

    await db.commit()
    logger.warning(
        f"Bootstrapped first platform super-admin '{target_email}'. "
        "Remember to change password and register passkey upon first login."
    )
    return admin
