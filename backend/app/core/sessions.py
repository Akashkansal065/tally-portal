"""
Device-aware login sessions.

Every login creates a row in user_sessions describing the device it came from. Clients identify
themselves with optional headers (see frontend src/lib/device.ts and the Desktop Sync Agent):

    X-Device-Id      stable per-install id (web: random UUID in localStorage, app: Capacitor
                     Device.getId(), agent: hash of the machine id); required for blocking
    X-Client-Type    web | android | ios | sync-agent
    X-Device-Name    readable label from native clients (web names are derived from User-Agent)
    X-Device-Type    mobile | tablet | desktop (native clients; otherwise derived from User-Agent)
    X-App-Version    native app / agent version

Device ids come from the client, so blocking is a soft control: clearing app data produces a new id.
To lock a person out, deactivate the user or reset their password.

Timestamps written here are naive UTC. Rows created before device tracking have created_at from
MySQL NOW(), which runs in IST on this server (see database.py init_command).
"""
import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, List, Optional, Sequence, Set

from fastapi import HTTPException, Request, status
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.datetime_utils import IST
from app.core.permissions import ADMIN_ROLE_NAMES, invalidate_auth_cache
from app.core.rate_limiter import get_client_ip
from app.core.security import create_access_token
from app.models.portal_core import AuditLog, BlockedDevice, Role, User, UserSession

logger = logging.getLogger("app.core.sessions")

AUTH_REASON_HEADER = "X-Auth-Reason"
CLIENT_TYPES = {"web", "android", "ios", "sync-agent", "api"}
DEVICE_TYPES = {"mobile", "tablet", "desktop"}
DEVICE_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{8,64}$")

# A device counts as "active now" if it made a request in the last 10 minutes. last_active_at is
# written at most every 5 minutes, so the threshold is twice that to avoid flicker.
ACTIVE_NOW_SECONDS = 600


def utcnow() -> datetime:
    """Naive UTC, matching how the app writes DateTime columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ─── Device description ──────────────────────────────────────────────────────

@dataclass
class DeviceInfo:
    device_id: Optional[str]
    client_type: str
    device_type: Optional[str]
    device_name: str
    os_name: Optional[str]
    browser_name: Optional[str]
    app_version: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]


def _clean(value: Optional[str], max_len: int) -> Optional[str]:
    if not value:
        return None
    value = re.sub(r"[\x00-\x1f\x7f]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:max_len] or None


def _parse_os(ua: str) -> Optional[str]:
    m = re.search(r"iPad.*?OS (\d+)[_.](\d+)", ua)
    if m:
        return f"iPadOS {m.group(1)}.{m.group(2)}"
    m = re.search(r"(?:iPhone|iPod).*?OS (\d+)[_.](\d+)", ua)
    if m:
        return f"iOS {m.group(1)}.{m.group(2)}"
    m = re.search(r"Android (\d+(?:\.\d+)?)", ua)
    if m:
        return f"Android {m.group(1)}"
    if "Windows" in ua:
        return "Windows"
    if "CrOS" in ua:
        return "ChromeOS"
    if "Mac OS X" in ua or "Macintosh" in ua:
        return "macOS"
    if "Linux" in ua:
        return "Linux"
    return None


def _parse_browser(ua: str) -> Optional[str]:
    patterns = (
        (r"Edg(?:A|iOS)?/(\d+)", "Edge"),
        (r"OPR/(\d+)", "Opera"),
        (r"SamsungBrowser/(\d+)", "Samsung Internet"),
        (r"CriOS/(\d+)", "Chrome"),
        (r"FxiOS/(\d+)", "Firefox"),
        (r"Firefox/(\d+)", "Firefox"),
    )
    for pattern, name in patterns:
        m = re.search(pattern, ua)
        if m:
            return f"{name} {m.group(1)}"
    m = re.search(r"Chrome/(\d+)", ua)
    if m:
        # Android WebView (the Capacitor app) marks itself with "; wv)"
        return f"{'Chrome WebView' if '; wv)' in ua else 'Chrome'} {m.group(1)}"
    m = re.search(r"Version/(\d+)(?:\.\d+)*.*Safari/", ua)
    if m:
        return f"Safari {m.group(1)}"
    return None


def _parse_device_type(ua: str) -> Optional[str]:
    if not ua:
        return None
    if "iPad" in ua or "Tablet" in ua or ("Android" in ua and "Mobile" not in ua):
        return "tablet"
    if "Mobi" in ua or "iPhone" in ua or "iPod" in ua:
        return "mobile"
    if any(k in ua for k in ("Windows", "Macintosh", "Mac OS X", "Linux", "CrOS")):
        return "desktop"
    return None


def parse_device(request: Request) -> DeviceInfo:
    """Describe the device a request comes from, using the optional device headers and User-Agent."""
    headers = request.headers
    ua = _clean(headers.get("user-agent"), 500) or ""

    device_id = (headers.get("x-device-id") or "").strip()
    if not DEVICE_ID_RE.match(device_id):
        device_id = None

    client_type = (headers.get("x-client-type") or "").strip().lower()
    if client_type not in CLIENT_TYPES:
        client_type = "api"

    device_type = (headers.get("x-device-type") or "").strip().lower()
    if device_type not in DEVICE_TYPES:
        device_type = "desktop" if client_type == "sync-agent" else _parse_device_type(ua)

    os_name = _parse_os(ua)
    browser_name = _parse_browser(ua) if client_type in ("web", "android", "ios") else None

    device_name = _clean(headers.get("x-device-name"), 120)
    if not device_name:
        if client_type == "web" and (browser_name or os_name):
            family = browser_name.rsplit(" ", 1)[0] if browser_name else "Browser"
            device_name = f"{family} on {os_name}" if os_name else family
        elif client_type == "sync-agent":
            device_name = "Desktop Sync Agent"
        elif client_type in ("android", "ios"):
            device_name = "Android app" if client_type == "android" else "iOS app"
        else:
            device_name = "API client"

    return DeviceInfo(
        device_id=device_id,
        client_type=client_type,
        device_type=device_type,
        device_name=device_name,
        os_name=_clean(os_name, 60),
        browser_name=_clean(browser_name, 60),
        app_version=_clean(headers.get("x-app-version"), 30),
        ip_address=_clean(get_client_ip(request), 45),
        user_agent=ua or None,
    )


# ─── Revocation ──────────────────────────────────────────────────────────────

def live_session_conditions(now: Optional[datetime] = None):
    now = now or utcnow()
    return (UserSession.revoked_at.is_(None), UserSession.expires_at > now)


def stale_legacy_condition():
    """Sessions from before device tracking that haven't been used since (most are abandoned logins
    from when the web app's logout didn't revoke anything). Shown separately as "older sessions"."""
    return and_(UserSession.client_type.is_(None), UserSession.last_active_at.is_(None))


async def revoke_sessions(
    db: AsyncSession,
    *,
    reason: str,
    session_ids: Optional[Sequence[int]] = None,
    user_id: Optional[int] = None,
    device_id: Optional[str] = None,
    by_user_id: Optional[int] = None,
    exclude_session_ids: Iterable[int] = (),
) -> List[str]:
    """Stage revocation of matching unrevoked sessions and return their token hashes.
    The caller commits, then calls forget_tokens() so no request is served from the auth cache."""
    if session_ids is None and user_id is None:
        raise ValueError("revoke_sessions needs session_ids or user_id")
    conditions = [UserSession.revoked_at.is_(None)]
    if session_ids is not None:
        if not session_ids:
            return []
        conditions.append(UserSession.session_id.in_(list(session_ids)))
    if user_id is not None:
        conditions.append(UserSession.user_id == user_id)
    if device_id is not None:
        conditions.append(UserSession.device_id == device_id)
    exclude = list(exclude_session_ids)
    if exclude:
        conditions.append(UserSession.session_id.not_in(exclude))

    rows = (await db.execute(select(UserSession.session_id, UserSession.token_hash).where(*conditions))).all()
    if not rows:
        return []
    await db.execute(
        update(UserSession)
        .where(UserSession.session_id.in_([r[0] for r in rows]))
        .values(revoked_at=utcnow(), revoke_reason=reason, revoked_by_user_id=by_user_id)
        .execution_options(synchronize_session=False)
    )
    return [r[1] for r in rows]


def forget_tokens(token_hashes: Iterable[str]) -> None:
    """Drop revoked tokens from the in-memory auth cache so their next request is checked in the DB."""
    for token_hash in token_hashes:
        invalidate_auth_cache(token_hash=token_hash)


def current_token_hash(request: Request) -> Optional[str]:
    auth = request.headers.get("authorization") or ""
    if not auth.lower().startswith("bearer "):
        return None
    return hashlib.sha256(auth.split(" ", 1)[1].strip().encode()).hexdigest()


def add_audit(db: AsyncSession, *, company_id: int, actor_id: int, action: str, entity_type: str,
              entity_id: int, new_value: Optional[dict] = None) -> None:
    db.add(AuditLog(company_id=company_id, user_id=actor_id, action=action, entity_type=entity_type,
                    entity_id=entity_id, new_value=new_value))


# ─── Login ───────────────────────────────────────────────────────────────────

async def create_user_session(db: AsyncSession, user: User, request: Request) -> str:
    """Create a session for an authenticated user (password already verified) and return the token.

    Refuses a blocked device, replaces older sessions from the same device, applies the role's
    device limit, and alerts admins when a non-admin user signs in from a new device. Commits."""
    info = parse_device(request)
    now = utcnow()
    revoked_hashes: List[str] = []

    role = user.role if "role" in user.__dict__ else await db.get(Role, user.role_id)

    seen_before = tracked_before = False
    if info.device_id:
        blocked = (await db.execute(
            select(BlockedDevice.blocked_device_id).where(
                BlockedDevice.user_id == user.user_id, BlockedDevice.device_id == info.device_id
            )
        )).scalars().first()
        if blocked:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This device has been blocked by your administrator. Contact your administrator.",
                headers={AUTH_REASON_HEADER: "device_blocked"},
            )
        seen_before = (await db.execute(
            select(UserSession.session_id).where(
                UserSession.user_id == user.user_id, UserSession.device_id == info.device_id
            ).limit(1)
        )).scalars().first() is not None
        tracked_before = seen_before or (await db.execute(
            select(UserSession.session_id).where(
                UserSession.user_id == user.user_id, UserSession.device_id.is_not(None)
            ).limit(1)
        )).scalars().first() is not None
        # One live row per device: a new login from the same device replaces the old one
        revoked_hashes += await revoke_sessions(db, reason="replaced", user_id=user.user_id, device_id=info.device_id)

    limit = role.max_active_devices if role is not None else None
    if limit and limit > 0:
        live = (await db.execute(
            select(UserSession.session_id, UserSession.client_type, UserSession.last_active_at)
            .where(UserSession.user_id == user.user_id, *live_session_conditions(now))
            .order_by(func.coalesce(UserSession.last_active_at, UserSession.created_at).asc())
        )).all()
        stale = [r.session_id for r in live if r.client_type is None and r.last_active_at is None]
        in_use = [r.session_id for r in live if r.session_id not in stale]
        if settings.DEVICE_LIMIT_POLICY == "refuse":
            if len(in_use) >= limit:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"You're already signed in on {len(in_use)} device(s), the maximum for your role. "
                           "Sign out on another device first, or ask your administrator.",
                    headers={AUTH_REASON_HEADER: "device_limit"},
                )
        else:
            # Least recently used first (unused pre-tracking sessions sort as the oldest)
            ordered = stale + in_use
            overflow = len(ordered) - (limit - 1)
            if overflow > 0:
                revoked_hashes += await revoke_sessions(db, reason="device_limit", session_ids=ordered[:overflow])

    token = create_access_token(subject=user.user_id)
    db.add(UserSession(
        user_id=user.user_id,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        ip_address=info.ip_address,
        user_agent=info.user_agent,
        device_id=info.device_id,
        client_type=info.client_type,
        device_type=info.device_type,
        device_name=info.device_name,
        os_name=info.os_name,
        browser_name=info.browser_name,
        app_version=info.app_version,
        created_at=now,
        last_active_at=now,
        expires_at=now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    ))
    user.last_login = datetime.now(timezone.utc)

    # Alert only once tracking already knows other devices of this user; otherwise every user's
    # first tracked login after the upgrade would look like a new device.
    is_admin = role is not None and (role.name or "").lower() in ADMIN_ROLE_NAMES
    if info.device_id and tracked_before and not seen_before and not is_admin:
        try:
            from app.routers.notifications import notify_admins
            where = f" from {info.ip_address}" if info.ip_address else ""
            await notify_admins(
                db=db,
                company_id=user.company_id,
                type="security",
                title="New device sign-in",
                message=f"{user.username} signed in on a new device: {info.device_name} ({info.client_type}){where}.",
                reference_id=str(user.user_id),
                reference_type="user_devices",
                exclude_user_id=user.user_id,
            )
        except Exception as e:  # an alert must never block a login
            logger.warning(f"New-device alert failed for user_id={user.user_id}: {e}")

    await db.commit()
    forget_tokens(revoked_hashes)
    return token


async def session_end_reason(db: AsyncSession, user_id: int, token_hash: str) -> str:
    """Why a token no longer works, for the X-Auth-Reason header."""
    row = (await db.execute(
        select(UserSession.revoked_at, UserSession.revoke_reason, UserSession.expires_at).where(
            UserSession.user_id == user_id, UserSession.token_hash == token_hash
        )
    )).first()
    if row is None:
        return "invalid"
    if row.revoked_at is not None:
        return row.revoke_reason or "revoked"
    return "expired"


# ─── Serialization ───────────────────────────────────────────────────────────

def _iso(value: Optional[datetime], tz=timezone.utc) -> Optional[str]:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=tz)
    return value.isoformat()


def to_utc_iso(value: Optional[datetime]) -> Optional[str]:
    return _iso(value)


def is_legacy(s: UserSession) -> bool:
    return s.client_type is None


def session_to_dict(
    s: UserSession,
    *,
    current_token_hash: Optional[str] = None,
    blocked_device_ids: Optional[Set[str]] = None,
    username: Optional[str] = None,
    now: Optional[datetime] = None,
) -> dict:
    now = now or utcnow()
    legacy = is_legacy(s)
    active_now = bool(
        s.revoked_at is None and s.last_active_at is not None
        and (now - s.last_active_at).total_seconds() < ACTIVE_NOW_SECONDS
    )
    data = {
        "session_id": s.session_id,
        "user_id": s.user_id,
        "device_id": s.device_id,
        "client_type": s.client_type,
        "device_type": s.device_type,
        "device_name": s.device_name or ("Unknown device" if legacy else "API client"),
        "os_name": s.os_name,
        "browser_name": s.browser_name,
        "app_version": s.app_version,
        "ip_address": s.ip_address,
        # Pre-tracking rows got created_at from MySQL NOW() in IST
        "created_at": _iso(s.created_at, IST if legacy else timezone.utc),
        "last_active_at": _iso(s.last_active_at),
        "expires_at": _iso(s.expires_at),
        "revoked_at": _iso(s.revoked_at),
        "revoke_reason": s.revoke_reason,
        "revoked_by_user_id": s.revoked_by_user_id,
        "is_current": bool(current_token_hash and s.token_hash == current_token_hash),
        "is_blocked": bool(s.device_id and blocked_device_ids and s.device_id in blocked_device_ids),
        "is_active_now": active_now,
        "legacy": legacy,
    }
    if username is not None:
        data["username"] = username
    return data


def blocked_device_to_dict(b: BlockedDevice, blocked_by: Optional[str] = None) -> dict:
    return {
        "blocked_device_id": b.blocked_device_id,
        "user_id": b.user_id,
        "device_id": b.device_id,
        "device_name": b.device_name,
        "client_type": b.client_type,
        "device_type": b.device_type,
        "reason": b.reason,
        "blocked_by_user_id": b.blocked_by_user_id,
        "blocked_by": blocked_by,
        "created_at": _iso(b.created_at),
    }
