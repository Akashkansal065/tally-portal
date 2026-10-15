"""
platform_audit.py – Append-only, tamper-evident audit logging engine for MyTally Platform Console.

Implements Plan Section 3.5:
  - Writes audit rows in the SAME database transaction as the operator action.
  - Computes SHA-256 tamper-evident hash chaining: row_hash = SHA256(prev_hash || canonical_data).
  - Redacts passwords, tokens, hashes, and secrets in old/new state diffs.
  - Automatically captures request_id, client IP, and user-agent via ContextVar.
"""

from __future__ import annotations

import hashlib
import json
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform import PlatformAuditLog

# Context variable populated by RequestLoggingMiddleware or Platform dependencies
audit_context_var: ContextVar[Optional[Dict[str, Any]]] = ContextVar("audit_context_var", default=None)

SENSITIVE_KEYS = {
    "password",
    "password_hash",
    "raw_password",
    "temp_password",
    "token",
    "access_token",
    "refresh_token",
    "refresh_hash",
    "secret",
    "public_key",
    "credential_id",
}


def sanitize_audit_diff(data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Recursively redacts sensitive fields before storing in audit log."""
    if not data or not isinstance(data, dict):
        return None

    sanitized: Dict[str, Any] = {}
    for key, value in data.items():
        key_lower = key.lower()
        if any(sens in key_lower for sens in SENSITIVE_KEYS):
            sanitized[key] = "[redacted]"
        elif isinstance(value, dict):
            sanitized[key] = sanitize_audit_diff(value)
        elif isinstance(value, (datetime,)):
            sanitized[key] = value.isoformat()
        else:
            sanitized[key] = value
    return sanitized


def format_audit_timestamp(dt: datetime) -> str:
    """
    Standardizes timestamp for deterministic canonical hashing.
    Converts aware datetimes to UTC, strips tzinfo, and normalizes
    to second precision so storage in standard MySQL DATETIME matches memory.
    """
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    dt = dt.replace(microsecond=0)
    return dt.isoformat()


def compute_canonical_row_hash(
    prev_hash: Optional[str],
    occurred_at: datetime,
    admin_email: str,
    action_type: str,
    target_type: Optional[str],
    target_id: Optional[int],
    outcome: str,
    request_id: str,
    old_json: Optional[str],
    new_json: Optional[str],
) -> str:
    """Computes SHA-256 hash chaining over canonical fields."""
    canonical = (
        f"{prev_hash or ''}|"
        f"{format_audit_timestamp(occurred_at)}|"
        f"{admin_email}|"
        f"{action_type}|"
        f"{target_type or ''}|"
        f"{target_id or ''}|"
        f"{outcome}|"
        f"{request_id}|"
        f"{old_json or ''}|"
        f"{new_json or ''}"
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def write_platform_audit_log(
    db: AsyncSession,
    action_type: str,
    admin_email: str,
    admin_id: Optional[int] = None,
    session_id: Optional[int] = None,
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    target_account_id: Optional[int] = None,
    target_user_id: Optional[int] = None,
    old_values: Optional[Dict[str, Any]] = None,
    new_values: Optional[Dict[str, Any]] = None,
    reason: Optional[str] = None,
    outcome: str = "success",
    request_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> PlatformAuditLog:
    """
    Writes a single audit record into platform_audit_log in the CURRENT transaction.
    If the caller's transaction rolls back, this audit log rolls back with it.
    """
    ctx = audit_context_var.get() or {}
    req_id = request_id or ctx.get("request_id") or "sys-" + hashlib.md5(str(datetime.now(timezone.utc)).encode()).hexdigest()[:8]
    ip = ip_address or ctx.get("ip_address") or "127.0.0.1"
    ua = user_agent or ctx.get("user_agent") or ""

    clean_old = sanitize_audit_diff(old_values)
    clean_new = sanitize_audit_diff(new_values)
    old_json = json.dumps(clean_old, sort_keys=True) if clean_old else None
    new_json = json.dumps(clean_new, sort_keys=True) if clean_new else None

    # Fetch previous row hash for tamper-evident blockchain-style chaining
    last_res = await db.execute(
        select(PlatformAuditLog.row_hash)
        .order_by(PlatformAuditLog.audit_id.desc())
        .limit(1)
    )
    prev_hash = last_res.scalar_one_or_none()

    occurred_at = datetime.now(timezone.utc).replace(microsecond=0)
    row_hash = compute_canonical_row_hash(
        prev_hash=prev_hash,
        occurred_at=occurred_at,
        admin_email=admin_email,
        action_type=action_type,
        target_type=target_type,
        target_id=target_id,
        outcome=outcome,
        request_id=req_id,
        old_json=old_json,
        new_json=new_json,
    )

    entry = PlatformAuditLog(
        occurred_at=occurred_at,
        admin_id=admin_id,
        admin_email=admin_email,
        session_id=session_id,
        action_type=action_type,
        target_type=target_type,
        target_id=target_id,
        target_account_id=target_account_id,
        target_user_id=target_user_id,
        old_values=old_json,
        new_values=new_json,
        reason=reason[:500] if reason else None,
        outcome=outcome,
        request_id=req_id[:36],
        ip_address=ip[:45],
        user_agent=ua[:500],
        prev_hash=prev_hash,
        row_hash=row_hash,
    )
    db.add(entry)
    return entry


async def verify_platform_audit_chain(
    db: AsyncSession,
    from_id: Optional[int] = None,
    max_rows: int = 10000,
) -> Dict[str, Any]:
    """
    Sequentially traverses PlatformAuditLog in ascending audit_id order.
    Verifies that:
      1. Every row's prev_hash strictly matches the previous row's row_hash.
      2. Every row's row_hash strictly matches the re-computed SHA-256 of its canonical fields.
    Returns integrity report with chain_intact=True/False, broken_at_id, etc.
    """
    query = select(PlatformAuditLog).order_by(PlatformAuditLog.audit_id.asc())
    if from_id is not None:
        query = query.where(PlatformAuditLog.audit_id >= from_id)
    query = query.limit(max_rows)

    result = await db.execute(query)
    rows = result.scalars().all()

    total_verified = 0
    expected_prev_hash: Optional[str] = None

    if from_id is not None and rows:
        pre_res = await db.execute(
            select(PlatformAuditLog.row_hash)
            .where(PlatformAuditLog.audit_id < rows[0].audit_id)
            .order_by(PlatformAuditLog.audit_id.desc())
            .limit(1)
        )
        expected_prev_hash = pre_res.scalar_one_or_none()

    for row in rows:
        # Check 1: prev_hash link continuity
        if row.prev_hash != expected_prev_hash:
            return {
                "chain_intact": False,
                "total_verified": total_verified,
                "broken_at_id": row.audit_id,
                "error_detail": (
                    f"Chain link broken at audit_id {row.audit_id}: "
                    f"prev_hash '{row.prev_hash}' does not match expected '{expected_prev_hash}'."
                ),
                "last_verified_at": datetime.now(timezone.utc).isoformat(),
            }

        # Check 2: row_hash computation validity
        computed_hash = compute_canonical_row_hash(
            prev_hash=row.prev_hash,
            occurred_at=row.occurred_at,
            admin_email=row.admin_email,
            action_type=row.action_type,
            target_type=row.target_type,
            target_id=row.target_id,
            outcome=row.outcome,
            request_id=row.request_id,
            old_json=row.old_values,
            new_json=row.new_values,
        )

        if row.row_hash != computed_hash:
            return {
                "chain_intact": False,
                "total_verified": total_verified,
                "broken_at_id": row.audit_id,
                "error_detail": (
                    f"Row content tampered at audit_id {row.audit_id}: "
                    f"stored hash '{row.row_hash}' does not match computed hash '{computed_hash}'."
                ),
                "last_verified_at": datetime.now(timezone.utc).isoformat(),
            }

        expected_prev_hash = row.row_hash
        total_verified += 1

    return {
        "chain_intact": True,
        "total_verified": total_verified,
        "broken_at_id": None,
        "error_detail": None,
        "last_verified_at": datetime.now(timezone.utc).isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# SQLALCHEMY SAFETY-NET LISTENER (Plan Section 3.5)
# ─────────────────────────────────────────────────────────────────────────────

from sqlalchemy import event
from sqlalchemy.orm import Session

WATCHED_MODEL_NAMES = {
    "User",
    "PlatformAdmin",
    "PlatformRole",
    "PlatformPermission",
    "PlatformRolePermission",
    "PlatformAdminRole",
    "PlatformAdminWebAuthnCredential",
    "PlatformPurgeRequest",
    "PlatformRetentionPolicy",
    "PlatformImpersonationSession",
}


@event.listens_for(Session, "before_flush")
def audit_safety_net_before_flush(session: Session, flush_context: Any, instances: Any) -> None:
    """Tracks whether watched entities or audit logs are modified during intermediate flushes."""
    ctx = audit_context_var.get()
    if not ctx or not ctx.get("operator_active") or ctx.get("skip_safety_net"):
        return

    for obj in list(session.new) + list(session.dirty) + list(session.deleted):
        cls_name = obj.__class__.__name__
        if cls_name in WATCHED_MODEL_NAMES:
            if obj in session.dirty and not session.is_modified(obj, include_collections=True):
                continue
            session.info["audit_watched_modified"] = True

    if any(obj.__class__.__name__ == "PlatformAuditLog" for obj in session.new):
        session.info["audit_log_queued"] = True


@event.listens_for(Session, "before_commit")
def audit_safety_net_before_commit(session: Session) -> None:
    """
    SQLAlchemy safety net:
    If an operator context is active and not explicitly bypassed, any transaction that
    modifies watched entities (User, PlatformAdmin, PlatformRole, etc.) MUST have a
    PlatformAuditLog instance committed in the same transaction. Otherwise, raises RuntimeError.
    """
    ctx = audit_context_var.get()
    if not ctx or not ctx.get("operator_active") or ctx.get("skip_safety_net"):
        return

    has_watched = session.info.get("audit_watched_modified") or any(
        obj.__class__.__name__ in WATCHED_MODEL_NAMES
        for obj in list(session.new) + list(session.dirty) + list(session.deleted)
        if not (obj in session.dirty and not session.is_modified(obj, include_collections=True))
    )

    has_audit = session.info.get("audit_log_queued") or any(
        obj.__class__.__name__ == "PlatformAuditLog" for obj in session.new
    )

    if has_watched and not has_audit:
        raise RuntimeError(
            "Audit safety-net violation: Watched entities were modified while operator "
            "context was active, but no platform_audit_log entry was queued in the transaction."
        )


@event.listens_for(Session, "after_commit")
@event.listens_for(Session, "after_rollback")
def audit_safety_net_cleanup(session: Session) -> None:
    """Resets tracking flags after transaction finishes."""
    session.info.pop("audit_watched_modified", None)
    session.info.pop("audit_log_queued", None)
