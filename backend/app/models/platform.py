"""
platform.py – SQLAlchemy models for the MyTally Platform Operator Console.

Architectural isolation:
  Operators are kept in their own tables (platform_*).
  They are never rows in the customer `users` table.
  All platform operator tables live in the portal database schema.
"""

from __future__ import annotations

import json
from typing import Any, List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import VARBINARY
from sqlalchemy.sql import func

from app.core.config import settings
from app.core.database import Base

_DB = settings.PORTAL_DATABASE_NAME


class PlatformAdmin(Base):
    """An operator who runs MyTally. Distinct from tenant users."""
    __tablename__ = "platform_admins"
    __table_args__ = (
        UniqueConstraint("email", name="uq_platform_admins_email"),
        {"schema": _DB},
    )

    admin_id            = Column(BigInteger, primary_key=True, autoincrement=True)
    email               = Column(String(190), nullable=False)
    full_name           = Column(String(120), nullable=False)
    password_hash       = Column(String(255), nullable=False)
    status              = Column(String(20), nullable=False, default="invited")  # invited, active, suspended, disabled
    failed_logins       = Column(Integer, nullable=False, default=0)
    locked_until        = Column(DateTime, nullable=True)
    password_changed_at = Column(DateTime, nullable=True)
    permission_version  = Column(Integer, nullable=False, default=1)  # bumped on any role/perm change
    allowed_ip_cidrs    = Column(Text, nullable=True)  # JSON list of CIDR strings or NULL
    last_login_at       = Column(DateTime, nullable=True)
    last_login_ip       = Column(String(45), nullable=True)
    created_by          = Column(BigInteger, nullable=True)
    created_at          = Column(DateTime, nullable=False, server_default=func.now())
    updated_at          = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    version             = Column(Integer, nullable=False, default=1)  # optimistic locking counter


class PlatformRole(Base):
    """Role definition with rank for platform operators."""
    __tablename__ = "platform_roles"
    __table_args__ = (
        UniqueConstraint("code", name="uq_platform_roles_code"),
        {"schema": _DB},
    )

    role_id     = Column(Integer, primary_key=True, autoincrement=True)
    code        = Column(String(50), nullable=False)   # super_admin, admin, support, billing, auditor
    name        = Column(String(80), nullable=False)
    description = Column(String(255), nullable=True)
    rank        = Column(Integer, nullable=False)      # higher outranks lower; super_admin = 1000
    is_system   = Column(Boolean, nullable=False, default=False)
    version     = Column(Integer, nullable=False, default=1)
    created_at  = Column(DateTime, nullable=False, server_default=func.now())


class PlatformPermission(Base):
    """Granular permission code (resource.action)."""
    __tablename__ = "platform_permissions"
    __table_args__ = (
        UniqueConstraint("code", name="uq_platform_permissions_code"),
        {"schema": _DB},
    )

    permission_id = Column(Integer, primary_key=True, autoincrement=True)
    code          = Column(String(80), nullable=False)  # users.read, admins.assign_roles
    resource      = Column(String(40), nullable=False)  # users, admins, roles, billing, audit
    action        = Column(String(40), nullable=False)  # read, update, hard_delete, etc.
    description   = Column(String(255), nullable=False)
    is_sensitive  = Column(Boolean, nullable=False, default=False)  # needs step-up recheck


class PlatformRolePermission(Base):
    """Mapping between roles and granted permissions."""
    __tablename__ = "platform_role_permissions"
    __table_args__ = (
        {"schema": _DB},
    )

    role_id       = Column(Integer, ForeignKey(f"{_DB}.platform_roles.role_id", ondelete="CASCADE"), primary_key=True)
    permission_id = Column(Integer, ForeignKey(f"{_DB}.platform_permissions.permission_id", ondelete="CASCADE"), primary_key=True)
    granted_by    = Column(BigInteger, nullable=True)
    granted_at    = Column(DateTime, nullable=False, server_default=func.now())


class PlatformAdminRole(Base):
    """Role assignment to an operator, with optional account scoping and expiry."""
    __tablename__ = "platform_admin_roles"
    __table_args__ = (
        {"schema": _DB},
    )

    admin_id          = Column(BigInteger, ForeignKey(f"{_DB}.platform_admins.admin_id", ondelete="CASCADE"), primary_key=True)
    role_id           = Column(Integer, ForeignKey(f"{_DB}.platform_roles.role_id", ondelete="RESTRICT"), primary_key=True)
    scope_account_ids = Column(Text, nullable=True)  # JSON array of account IDs or NULL (all accounts)
    assigned_by       = Column(BigInteger, nullable=True)
    assigned_at       = Column(DateTime, nullable=False, server_default=func.now())
    expires_at        = Column(DateTime, nullable=True)


class PlatformAdminSession(Base):
    """Operator session with rotating refresh tokens and reuse detection."""
    __tablename__ = "platform_admin_sessions"
    __table_args__ = (
        UniqueConstraint("refresh_hash", name="uq_pas_refresh"),
        Index("ix_pas_admin", "admin_id", "revoked_at"),
        Index("ix_pas_family", "family_id"),
        {"schema": _DB},
    )

    session_id     = Column(BigInteger, primary_key=True, autoincrement=True)
    admin_id       = Column(BigInteger, ForeignKey(f"{_DB}.platform_admins.admin_id", ondelete="CASCADE"), nullable=False)
    family_id      = Column(String(36), nullable=False)
    refresh_hash   = Column(String(64), nullable=False)
    refresh_used   = Column(Boolean, nullable=False, default=False)
    mfa_at         = Column(DateTime, nullable=False)  # last passkey or password check
    ip_address     = Column(String(45), nullable=True)
    user_agent     = Column(String(500), nullable=True)
    created_at     = Column(DateTime, nullable=False, server_default=func.now())
    last_seen_at   = Column(DateTime, nullable=False, server_default=func.now())
    expires_at     = Column(DateTime, nullable=False)  # absolute limit (8h)
    revoked_at     = Column(DateTime, nullable=True)
    revoked_reason = Column(String(60), nullable=True)


class PlatformLoginAttempt(Base):
    """Brute force tracking for operator logins (IP & email hashed)."""
    __tablename__ = "platform_login_attempts"
    __table_args__ = (
        Index("ix_pla_ip", "ip_address", "attempted_at"),
        Index("ix_pla_email", "email_hash", "attempted_at"),
        {"schema": _DB},
    )

    attempt_id   = Column(BigInteger, primary_key=True, autoincrement=True)
    email_hash   = Column(String(64), nullable=False)
    ip_address   = Column(String(45), nullable=False)
    succeeded    = Column(Boolean, nullable=False)
    attempted_at = Column(DateTime, nullable=False, server_default=func.now())


class PlatformAdminWebAuthnCredential(Base):
    """Registered WebAuthn passkey / FIDO2 security key credentials."""
    __tablename__ = "platform_admin_webauthn_credentials"
    __table_args__ = (
        UniqueConstraint("credential_id", name="uq_pawc_credential"),
        {"schema": _DB},
    )

    credential_pk = Column(BigInteger, primary_key=True, autoincrement=True)
    admin_id      = Column(BigInteger, ForeignKey(f"{_DB}.platform_admins.admin_id", ondelete="CASCADE"), nullable=False)
    credential_id = Column(LargeBinary(255).with_variant(VARBINARY(255), "mysql"), nullable=False)
    public_key    = Column(LargeBinary, nullable=False)
    sign_count    = Column(BigInteger, nullable=False, default=0)
    aaguid        = Column(String(36), nullable=True)
    transports    = Column(Text, nullable=True)  # JSON array
    rp_id         = Column(String(190), nullable=False)
    nickname      = Column(String(60), nullable=False)
    created_at    = Column(DateTime, nullable=False, server_default=func.now())
    last_used_at  = Column(DateTime, nullable=True)


class PlatformAuditLog(Base):
    """Append-only tamper-evident audit log for operator actions."""
    __tablename__ = "platform_audit_log"
    __table_args__ = (
        Index("ix_pal_time", "occurred_at"),
        Index("ix_pal_admin", "admin_id", "occurred_at"),
        Index("ix_pal_target_user", "target_user_id", "occurred_at"),
        Index("ix_pal_account", "target_account_id", "occurred_at"),
        Index("ix_pal_action", "action_type", "occurred_at"),
        {"schema": _DB},
    )

    audit_id          = Column(BigInteger, primary_key=True, autoincrement=True)
    occurred_at       = Column(DateTime, nullable=False, server_default=func.now())
    admin_id          = Column(BigInteger, nullable=True)
    admin_email       = Column(String(190), nullable=False)
    session_id        = Column(BigInteger, nullable=True)
    action_type       = Column(String(60), nullable=False)
    target_type       = Column(String(40), nullable=True)
    target_id         = Column(BigInteger, nullable=True)
    target_account_id = Column(Integer, nullable=True)
    target_user_id    = Column(Integer, nullable=True)
    old_values        = Column(Text, nullable=True)  # JSON diff
    new_values        = Column(Text, nullable=True)  # JSON diff
    reason            = Column(String(500), nullable=True)
    outcome           = Column(String(20), nullable=False)  # success, denied, failed
    request_id        = Column(String(36), nullable=False)
    ip_address        = Column(String(45), nullable=True)
    user_agent        = Column(String(500), nullable=True)
    prev_hash         = Column(String(64), nullable=True)
    row_hash          = Column(String(64), nullable=False)


class PlatformPurgeRequest(Base):
    """
    Two-person approval request for permanent hard-deletion (anonymisation) of a customer user.
    The requesting operator CANNOT be the approving operator (enforced in API and service layer).
    """
    __tablename__ = "platform_purge_requests"
    __table_args__ = (
        Index("ix_ppr_target_user", "target_user_id", "status"),
        Index("ix_ppr_status", "status"),
        {"schema": _DB},
    )

    purge_request_id       = Column(BigInteger, primary_key=True, autoincrement=True)
    target_user_id         = Column(Integer, ForeignKey(f"{_DB}.users.user_id", ondelete="CASCADE"), nullable=False)
    target_account_id      = Column(Integer, nullable=True)
    target_email_snapshot  = Column(String(190), nullable=False)
    target_username_snapshot = Column(String(120), nullable=True)
    requested_by_admin_id  = Column(BigInteger, ForeignKey(f"{_DB}.platform_admins.admin_id", ondelete="RESTRICT"), nullable=False)
    requested_at           = Column(DateTime, nullable=False, server_default=func.now())
    reason                 = Column(Text, nullable=False)
    status                 = Column(String(20), nullable=False, default="pending")  # pending, approved, rejected, cancelled
    approved_by_admin_id   = Column(BigInteger, ForeignKey(f"{_DB}.platform_admins.admin_id", ondelete="SET NULL"), nullable=True)
    approved_at            = Column(DateTime, nullable=True)
    rejected_by_admin_id   = Column(BigInteger, ForeignKey(f"{_DB}.platform_admins.admin_id", ondelete="SET NULL"), nullable=True)
    rejected_at            = Column(DateTime, nullable=True)
    rejection_reason       = Column(Text, nullable=True)
    executed_at            = Column(DateTime, nullable=True)


class PlatformRetentionPolicy(Base):
    """
    Data retention & statutory compliance policies specifying retention windows and expiry actions.
    """
    __tablename__ = "platform_retention_policies"
    __table_args__ = (
        UniqueConstraint("data_category", name="uq_prp_data_category"),
        {"schema": _DB},
    )

    policy_id             = Column(Integer, primary_key=True, autoincrement=True)
    data_category         = Column(String(80), nullable=False)  # tax_and_accounting, customer_user_accounts, etc.
    title                 = Column(String(120), nullable=False)
    retention_period_days = Column(Integer, nullable=False)
    legal_basis           = Column(String(255), nullable=False)
    action_on_expiry      = Column(String(100), nullable=False)
    description           = Column(Text, nullable=True)
    updated_at            = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class PlatformImpersonationSession(Base):
    """
    Time-boxed tenant impersonation session issued to a platform operator.
    Default is strictly read-only with prohibited sensitive actions (password, billing, deletion).
    """
    __tablename__ = "platform_impersonation_sessions"
    __table_args__ = (
        UniqueConstraint("session_token", name="uq_pis_session_token"),
        Index("ix_pis_target_user", "target_user_id", "terminated_at"),
        Index("ix_pis_admin", "admin_id", "started_at"),
        {"schema": _DB},
    )

    impersonation_id       = Column(BigInteger, primary_key=True, autoincrement=True)
    admin_id               = Column(BigInteger, ForeignKey(f"{_DB}.platform_admins.admin_id", ondelete="CASCADE"), nullable=False)
    admin_email            = Column(String(190), nullable=False)
    target_user_id         = Column(Integer, ForeignKey(f"{_DB}.users.user_id", ondelete="CASCADE"), nullable=False)
    target_account_id      = Column(Integer, nullable=False)
    session_token          = Column(String(64), nullable=False)
    is_write               = Column(Boolean, nullable=False, default=False)
    reason                 = Column(Text, nullable=False)
    duration_minutes       = Column(Integer, nullable=False, default=15)
    started_at             = Column(DateTime, nullable=False, server_default=func.now())
    expires_at             = Column(DateTime, nullable=False)
    terminated_at          = Column(DateTime, nullable=True)
    terminated_by_admin_id = Column(BigInteger, nullable=True)

