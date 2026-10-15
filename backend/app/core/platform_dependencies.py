"""
platform_dependencies.py – FastAPI dependencies for Platform Operator authorization.

Enforces:
  • Operator session loading, idle/absolute expiry checks, revocation check
  • Permission version synchronization (immediate revocation on role change)
  • Operator vs. customer token isolation (tenant tokens are strictly refused)
  • CSRF token check on state-changing requests
  • Step-up authentication enforcement on sensitive permissions
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging_config import get_logger
from app.core.rate_limiter import get_client_ip
from app.core.platform_catalogue import SENSITIVE_PERMISSIONS
from app.core.platform_security import (
    decode_platform_access_token,
    get_cookie_name,
    is_ip_allowed,
    utc_now,
    verify_csrf,
    STEP_UP_VALIDITY_MINUTES,
    IDLE_TIMEOUT_MINUTES,
)
from app.models.platform import (
    PlatformAdmin,
    PlatformAdminRole,
    PlatformAdminSession,
    PlatformPermission,
    PlatformRole,
    PlatformRolePermission,
)

logger = get_logger("app.core.platform_dependencies")


@dataclass
class PlatformAdminContext:
    admin: PlatformAdmin
    session: PlatformAdminSession
    permissions: Set[str]
    max_rank: int
    scope_account_ids: Optional[List[int]]

    def has_permission(self, perm: str) -> bool:
        return self.max_rank >= 1000 or "all" in self.permissions or perm in self.permissions

    def require_step_up(self, max_age_minutes: int = STEP_UP_VALIDITY_MINUTES) -> None:
        now = utc_now()
        if not self.session.mfa_at or (now - self.session.mfa_at).total_seconds() > max_age_minutes * 60:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Step-up authentication required.",
                headers={"X-Step-Up": "true"},
            )


def _extract_access_token(request: Request) -> str:
    """Extracts operator access token from HTTP-only cookie or Bearer header."""
    cookie_key = get_cookie_name("pa_at")
    token = request.cookies.get(cookie_key)
    if not token:
        # Check standard Authorization header (support for test client / automation)
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Platform operator sign-in required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


async def get_effective_operator_permissions(
    db: AsyncSession,
    admin_id: int,
) -> Tuple[Set[str], int, Optional[List[int]]]:
    """Computes union of permissions, highest rank, and account scopes for an operator."""
    now = utc_now()
    # Query active role assignments
    admin_roles_stmt = (
        select(PlatformAdminRole, PlatformRole)
        .join(PlatformRole, PlatformAdminRole.role_id == PlatformRole.role_id)
        .where(
            PlatformAdminRole.admin_id == admin_id,
            (PlatformAdminRole.expires_at == None) | (PlatformAdminRole.expires_at > now),  # noqa: E711
        )
    )
    res = await db.execute(admin_roles_stmt)
    rows = res.all()

    if not rows:
        return set(), 0, None

    max_rank = max(r.rank for _, r in rows)
    role_ids = [ar.role_id for ar, _ in rows]

    # Combine scopes if any (None means unscoped / all accounts)
    combined_scopes: Optional[Set[int]] = None
    has_unscoped = False
    for ar, _ in rows:
        if ar.scope_account_ids:
            try:
                acc_ids = set(json.loads(ar.scope_account_ids))
                if combined_scopes is None:
                    combined_scopes = acc_ids
                else:
                    combined_scopes.update(acc_ids)
            except Exception:
                pass
        else:
            has_unscoped = True

    final_scope = None if has_unscoped else (list(combined_scopes) if combined_scopes is not None else None)

    # Fetch permissions for all assigned roles
    perm_stmt = (
        select(PlatformPermission.code)
        .join(PlatformRolePermission, PlatformRolePermission.permission_id == PlatformPermission.permission_id)
        .where(PlatformRolePermission.role_id.in_(role_ids))
    )
    perm_res = await db.execute(perm_stmt)
    permissions = {code for (code,) in perm_res.all()}

    return permissions, max_rank, final_scope


async def current_admin(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> PlatformAdminContext:
    """
    Main dependency for Platform Operator endpoints.
    Verifies JWT token, session status, permissions version, IP restrictions and CSRF.
    """
    raw_token = _extract_access_token(request)
    # Only operator-console tokens are accepted. A customer-portal token is refused even for an email in
    # PLATFORM_ADMIN_EMAILS: it was issued without a passkey or step-up, so it must never carry operator rights.
    claims = decode_platform_access_token(raw_token)

    admin_id = int(claims["sub"])
    session_id = int(claims["sid"])
    permission_version = int(claims.get("pv", 1))

    # Load session
    sess_res = await db.execute(
        select(PlatformAdminSession).where(PlatformAdminSession.session_id == session_id)
    )
    session = sess_res.scalars().first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session not found or invalidated.",
        )

    now = utc_now()

    # Session revocation check
    if session.revoked_at:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has been revoked.",
        )

    # Absolute session lifetime check (8 hours)
    if session.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired. Please sign in again.",
        )

    # Idle timeout check (30 minutes)
    if session.last_seen_at < (now - timedelta(minutes=IDLE_TIMEOUT_MINUTES)):
        session.revoked_at = now
        session.revoked_reason = "idle_timeout"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session timed out due to inactivity.",
        )

    # Load operator
    admin_res = await db.execute(
        select(PlatformAdmin).where(PlatformAdmin.admin_id == admin_id)
    )
    admin = admin_res.scalars().first()
    if not admin:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Operator account not found.")

    if admin.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Operator account is {admin.status}.",
        )

    # Permission version sync (bumps on any role or permission change revokes immediately)
    if permission_version != admin.permission_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Permissions have changed. Please refresh your session.",
        )

    # IP Allowlisting
    client_ip = get_client_ip(request)
    if not is_ip_allowed(client_ip, admin.allowed_ip_cidrs):
        logger.warning(f"Operator {admin.email} access denied from unauthorized IP {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden from this IP address.",
        )

    # CSRF check on cookie-authenticated write operations
    cookie_key = get_cookie_name("pa_at")
    if request.cookies.get(cookie_key):
        verify_csrf(request)

    # Touch last_seen_at (throttled to at most once every 10 seconds to reduce DB load)
    if (now - session.last_seen_at).total_seconds() > 10:
        session.last_seen_at = now
        await db.commit()

    permissions, max_rank, scopes = await get_effective_operator_permissions(db, admin_id)
    if scopes is not None:
        # The console's routes do not filter by account scope yet, so a scoped operator would reach every
        # account. Refused until they do (assigning a scope is refused too, in platform_admins).
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account-scoped operator access is not supported yet. Ask a super admin to change your roles.",
        )

    # Populate audit context var for automatic audit logging and safety net
    from app.core.platform_audit import audit_context_var
    req_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID") or f"req-{admin_id}-{int(now.timestamp())}"
    audit_context_var.set({
        "admin_id": admin_id,
        "admin_email": admin.email,
        "session_id": session_id,
        "operator_active": True,
        "request_id": req_id,
        "ip_address": client_ip,
        "user_agent": request.headers.get("user-agent", ""),
    })

    return PlatformAdminContext(
        admin=admin,
        session=session,
        permissions=permissions,
        max_rank=max_rank,
        scope_account_ids=scopes,
    )


def require_platform_permission(
    permission_code: str,
    *,
    step_up: bool = False,
) -> Callable:
    """
    Dependency factory checking operator permission code.
    If sensitive or step_up is requested, enforces mfa_at freshness within 5 minutes.
    """
    async def dependency(
        ctx: PlatformAdminContext = Depends(current_admin),
    ) -> PlatformAdminContext:
        if not ctx.has_permission(permission_code):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: requires '{permission_code}'.",
            )

        is_sensitive = step_up or (permission_code in SENSITIVE_PERMISSIONS)
        if is_sensitive:
            now = utc_now()
            threshold = now - timedelta(minutes=STEP_UP_VALIDITY_MINUTES)
            if ctx.session.mfa_at < threshold:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Step-up authentication required for this sensitive action.",
                    headers={"X-Step-Up": "required"},
                )

        return ctx

    return dependency


def parse_if_match_version(if_match: Optional[str]) -> Optional[int]:
    """Parses integer version from If-Match header with weak validator support (e.g. W/\"1\")."""
    if not if_match:
        return None
    clean = if_match.strip()
    if clean.startswith(("W/", "w/")):
        clean = clean[2:].strip()
    clean = clean.strip('"').strip("'").strip()
    try:
        return int(clean)
    except ValueError:
        return None
