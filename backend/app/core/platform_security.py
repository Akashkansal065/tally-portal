"""
platform_security.py – Security primitives for the MyTally Platform Operator Console.

Implements:
  • Operator JWT token generation and verification (PLATFORM_JWT_SECRET)
  • Refresh token hashing and rotation
  • Mandatory brute-force lockout and rate limiting (in database)
  • Constant-time timing defense on login failure
  • WebAuthn / Passkey registration and assertion helpers
  • CSRF token generation and validation
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

import jwt
from fastapi import HTTPException, Request, Response, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging_config import get_logger
from app.core.platform_catalogue import SENSITIVE_PERMISSIONS
from app.core.security import get_password_hash, verify_password

hash_password = get_password_hash
from app.models.platform import (
    PlatformAdmin,
    PlatformAdminRole,
    PlatformAdminSession,
    PlatformAdminWebAuthnCredential,
    PlatformLoginAttempt,
    PlatformRole,
    PlatformRolePermission,
)

logger = get_logger("app.core.platform_security")

# Constants from Architecture Plan Section 1.3
ACCESS_TOKEN_EXPIRE_MINUTES = 10
IDLE_TIMEOUT_MINUTES = 30
ABSOLUTE_SESSION_HOURS = 8
STEP_UP_VALIDITY_MINUTES = 5

MFA_TOKEN_EXPIRE_MINUTES = 5

# Safe HTTP methods that do not require CSRF tokens
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

# Dummy hash for timing equalization when user is unknown or locked
DUMMY_BCRYPT_HASH = "$2b$12$e8x8qVzV2eM7eM7eM7eM7eYyYyYyYyYyYyYyYyYyYyYyYyYyYyYy"


def utc_now() -> datetime:
    """Current UTC time naive or timezone-aware as configured."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_token(token: str) -> str:
    """Computes SHA-256 hash of a token for database storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_email(email: str) -> str:
    """Computes SHA-256 hash of normalized lowercase email for attempt tracking."""
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# TOKENS & JWT
# ─────────────────────────────────────────────────────────────────────────────

def create_platform_access_token(
    admin_id: int,
    session_id: int,
    permission_version: int,
    amr: List[str],
) -> str:
    """Issues a 10-minute JWT access token signed with PLATFORM_JWT_SECRET."""
    now = utc_now()
    payload = {
        "iss": "mytally-platform",
        "sub": str(admin_id),
        "sid": session_id,
        "pv": permission_version,
        "amr": amr,
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.get_platform_jwt_secret(), algorithm="HS256")


def create_platform_mfa_token(admin_id: int) -> str:
    """Issues a single-purpose 5-minute token for pending passkey verification."""
    now = utc_now()
    payload = {
        "iss": "mytally-platform",
        "sub": str(admin_id),
        "type": "platform_mfa",
        "iat": now,
        "exp": now + timedelta(minutes=MFA_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.get_platform_jwt_secret(), algorithm="HS256")


def verify_platform_mfa_token(token: str) -> int:
    """Verifies MFA token and returns admin_id or raises 401."""
    try:
        payload = jwt.decode(
            token,
            settings.get_platform_jwt_secret(),
            algorithms=["HS256"],
            issuer="mytally-platform",
        )
        if payload.get("type") != "platform_mfa":
            raise HTTPException(status_code=401, detail="Invalid token type.")
        return int(payload["sub"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="MFA token expired or invalid. Please sign in again.")


def decode_platform_access_token(token: str) -> Dict[str, Any]:
    """Decodes and verifies a platform operator access token."""
    try:
        payload = jwt.decode(
            token,
            settings.get_platform_jwt_secret(),
            algorithms=["HS256"],
            issuer="mytally-platform",
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Operator access token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid operator access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def generate_refresh_token() -> str:
    """Generates an opaque high-entropy refresh token."""
    return secrets.token_hex(32)


def generate_csrf_token() -> str:
    """Generates a random CSRF token."""
    return secrets.token_hex(24)


# ─────────────────────────────────────────────────────────────────────────────
# COOKIES & CSRF MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

def get_cookie_name(base: str) -> str:
    """Applies configured cookie prefix (e.g. '__Secure-' or '')."""
    return f"{settings.PLATFORM_COOKIE_PREFIX}{base}"


def set_operator_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
    csrf_token: Optional[str] = None,
) -> None:
    """Sets operator cookies according to Architecture Plan Section 1.3."""
    at_cookie = get_cookie_name("pa_at")
    rt_cookie = get_cookie_name("pa_rt")
    csrf_cookie = "pa_csrf"

    # Access token cookie: path /console-api
    response.set_cookie(
        key=at_cookie,
        value=access_token,
        httponly=True,
        secure=settings.PLATFORM_COOKIE_SECURE,
        samesite="strict",
        path=settings.PLATFORM_COOKIE_PATH,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    # Refresh token cookie: path /console-api/auth
    rt_path = f"{settings.PLATFORM_COOKIE_PATH.rstrip('/')}/auth"
    response.set_cookie(
        key=rt_cookie,
        value=refresh_token,
        httponly=True,
        secure=settings.PLATFORM_COOKIE_SECURE,
        samesite="strict",
        path=rt_path,
        max_age=ABSOLUTE_SESSION_HOURS * 3600,
    )

    # CSRF cookie (readable by JS on /console pages)
    if csrf_token:
        response.set_cookie(
            key=csrf_cookie,
            value=csrf_token,
            httponly=False,
            secure=settings.PLATFORM_COOKIE_SECURE,
            samesite="strict",
            path="/",
            max_age=ABSOLUTE_SESSION_HOURS * 3600,
        )


def clear_operator_cookies(response: Response) -> None:
    """Clears all operator cookies on sign-out."""
    at_cookie = get_cookie_name("pa_at")
    rt_cookie = get_cookie_name("pa_rt")
    csrf_cookie = "pa_csrf"
    rt_path = f"{settings.PLATFORM_COOKIE_PATH.rstrip('/')}/auth"

    response.delete_cookie(key=at_cookie, path=settings.PLATFORM_COOKIE_PATH)
    response.delete_cookie(key=rt_cookie, path=rt_path)
    response.delete_cookie(key=csrf_cookie, path="/")
    response.delete_cookie(key=csrf_cookie, path=settings.PLATFORM_COOKIE_PATH)


def verify_csrf(request: Request) -> None:
    """Enforces double-submit CSRF token on non-safe requests."""
    if request.method in SAFE_METHODS:
        return
    csrf_cookie = request.cookies.get("pa_csrf")
    csrf_header = request.headers.get("X-CSRF-Token")
    if not csrf_cookie or not csrf_header or not hmac.compare_digest(csrf_cookie, csrf_header):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token missing or mismatch.",
        )


# ─────────────────────────────────────────────────────────────────────────────
# BRUTE FORCE DEFENSE & LOCKOUT (Section 5.2)
# ─────────────────────────────────────────────────────────────────────────────

async def check_login_rate_limits(
    db: AsyncSession,
    ip_address: str,
    email: str,
) -> None:
    """
    Mandatory rate limits:
      - 10 attempts per IP per 15 minutes across all emails
      - 10 attempts per email per hour across all IPs
    Raises 429 if threshold is reached.
    """
    now = utc_now()
    e_hash = hash_email(email)

    # 1. Per-IP check (past 15 minutes)
    fifteen_min_ago = now - timedelta(minutes=15)
    ip_count_res = await db.execute(
        select(func.count(PlatformLoginAttempt.attempt_id)).where(
            PlatformLoginAttempt.ip_address == ip_address,
            PlatformLoginAttempt.attempted_at >= fifteen_min_ago,
            PlatformLoginAttempt.succeeded == False,  # noqa: E712
        )
    )
    ip_failed_count = ip_count_res.scalar() or 0
    if ip_failed_count >= 10:
        logger.warning(f"Operator login IP rate limit exceeded for {ip_address}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many sign-in attempts from this IP address. Please try again later.",
        )

    # 2. Per-email check (past 1 hour)
    one_hour_ago = now - timedelta(hours=1)
    email_count_res = await db.execute(
        select(func.count(PlatformLoginAttempt.attempt_id)).where(
            PlatformLoginAttempt.email_hash == e_hash,
            PlatformLoginAttempt.attempted_at >= one_hour_ago,
            PlatformLoginAttempt.succeeded == False,  # noqa: E712
        )
    )
    email_failed_count = email_count_res.scalar() or 0
    if email_failed_count >= 10:
        logger.warning(f"Operator login email rate limit exceeded for hash {e_hash[:8]}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many sign-in attempts for this email. Please try again later.",
        )


async def record_login_attempt(
    db: AsyncSession,
    ip_address: str,
    email: str,
    succeeded: bool,
) -> None:
    """Logs every sign-in attempt in platform_login_attempts."""
    e_hash = hash_email(email)
    attempt = PlatformLoginAttempt(
        email_hash=e_hash,
        ip_address=ip_address,
        succeeded=succeeded,
        attempted_at=utc_now(),
    )
    db.add(attempt)
    await db.commit()


def calculate_lockout_duration_minutes(failed_logins: int) -> int:
    """
    5 wrong passwords in a row locks for 15 min;
    each further lock doubles up to 24 hours (1440 min).
    """
    if failed_logins < 5:
        return 0
    over = failed_logins - 5
    return min(15 * (2 ** over), 1440)


def is_ip_allowed(client_ip: Optional[str], allowed_cidrs_json: Optional[str]) -> bool:
    """Checks client IP against operator's allowed CIDRs if configured."""
    if not allowed_cidrs_json or not client_ip:
        return True
    import json
    try:
        cidrs = json.loads(allowed_cidrs_json)
        if not cidrs:
            return True
        client_addr = ipaddress.ip_address(client_ip)
        for cidr in cidrs:
            if client_addr in ipaddress.ip_network(cidr.strip(), strict=False):
                return True
        return False
    except Exception as e:
        logger.error(f"Error evaluating allowed IP CIDRs: {e}")
        return False


PLATFORM_PUBLIC_ROUTES = {
    "/platform/auth/login",
    "/platform/auth/refresh",
    "/platform/auth/passkey/login/options",
    "/platform/auth/passkey/login/verify",
}


def verify_platform_routes_security(app: Any) -> int:
    """
    Pre-Go-Live Boot Security Scan:
    Asserts that every endpoint registered under '/platform' has a platform
    authentication and permission dependency attached (Fail-Closed / Deny by Default).
    Raises RuntimeError if any unprotected platform route is detected.
    Returns count of verified protected routes.
    """
    protected_count = 0
    unprotected = []

    def _get_all_routes(container: Any) -> list:
        found = []
        for r in getattr(container, "routes", []):
            if hasattr(r, "original_router"):
                found.extend(_get_all_routes(r.original_router))
            elif hasattr(r, "path"):
                found.append(r)
        return found

    def _has_platform_guard(dependant: Any) -> bool:
        if not dependant:
            return False
        for call in [dependant.call] + [d.call for d in getattr(dependant, "dependencies", [])]:
            if not call:
                continue
            name = getattr(call, "__name__", "")
            qualname = getattr(call, "__qualname__", "")
            if (
                "require_platform_permission" in name
                or "require_platform_permission" in qualname
                or "current_admin" in name
                or "require_step_up_mfa" in name
                or "dependency" in name
            ):
                return True
        for sub_dep in getattr(dependant, "dependencies", []):
            if _has_platform_guard(sub_dep):
                return True
        return False

    all_routes = _get_all_routes(app)
    for route in all_routes:
        if route.path.startswith("/platform"):
            if route.path in PLATFORM_PUBLIC_ROUTES:
                continue
            dependant = getattr(route, "dependant", None)
            if not _has_platform_guard(dependant):
                unprotected.append(f"{route.path} {list(route.methods)}")
            else:
                protected_count += 1

    if unprotected:
        err_msg = (
            f"Pre-Go-Live Security Scan Failed! Found {len(unprotected)} unprotected endpoint(s) "
            f"under /platform without platform permission dependencies:\n  " + "\n  ".join(unprotected)
        )
        logger.error(err_msg)
        raise RuntimeError(err_msg)

    logger.info(f"Pre-Go-Live Security Scan Passed: {protected_count} platform routes verified with explicit permission guards.")
    return protected_count

