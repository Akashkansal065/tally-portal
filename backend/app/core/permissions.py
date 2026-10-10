import hashlib
import logging
import time
import copy
from collections import defaultdict
from typing import Dict, Any, Optional, Sequence, Set
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import update, and_, or_
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import set_committed_value
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from app.core.database import get_db
from app.core.config import settings
from app.core.security import decode_access_token
from app.models.portal_core import (
    User, UserSession, UserPermissionOverride, Permission, Module, UserDataScope,
    UserCompanyAccess, Company
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/swagger-login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/auth/swagger-login", auto_error=False)

ADMIN_ROLE_NAMES = ("admin", "superadmin", "owner")

def same_account_as_user(user_id: int):
    """SQL condition: the company belongs to this user's account (rows without an account match each other)."""
    own_account = select(User.account_id).where(User.user_id == user_id).scalar_subquery()
    return or_(Company.account_id == own_account, and_(Company.account_id.is_(None), own_account.is_(None)))


def is_admin_user(user: Optional[User]) -> bool:
    """True if the user's role is one of the administrator roles (role must be loaded)."""
    return bool(user is not None and user.role is not None and user.role.name and user.role.name.lower() in ADMIN_ROLE_NAMES)


async def accessible_company_ids(db: AsyncSession, user_id: int, home_company_id: int, role_name: Optional[str]) -> Set[int]:
    """Companies a user may open: admins get every active company of their own account, others their home
    company plus granted ones. No role reaches a company of another account."""
    allowed: Set[int] = {home_company_id}
    if role_name and role_name.lower() in ADMIN_ROLE_NAMES:
        rows = await db.execute(select(Company.company_id).where(Company.is_active == True, same_account_as_user(user_id)))
    else:
        rows = await db.execute(select(UserCompanyAccess.company_id).where(UserCompanyAccess.user_id == user_id))
    allowed.update(rows.scalars().all())
    return allowed

logger = logging.getLogger("app.core.permissions")

# The Desktop Sync Agent names the Tally company it is syncing on every call, by Tally's company GUID
SYNC_COMPANY_GUID_HEADER = "x-tally-company-guid"
# user_id -> when an agent call without the header was last logged (the agent polls every few seconds)
_legacy_sync_warned: Dict[int, float] = {}
LEGACY_SYNC_WARN_INTERVAL_SECONDS = 600


async def company_for_tally_guid(db: AsyncSession, user: User, tally_guid: str) -> Optional[Company]:
    """The company this user may access that is linked to the Tally company GUID, or None when no company
    is linked to it yet. Two accessible companies claiming one GUID is refused: neither can be trusted."""
    allowed = await accessible_company_ids(db, user.user_id, user.company_id, user.role.name if user.role else "")
    rows = (await db.execute(
        select(Company).where(Company.tally_guid == tally_guid, Company.company_id.in_(allowed))
    )).scalars().all()
    if len(rows) > 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"More than one company is linked to Tally company GUID {tally_guid}. Sync is stopped until only one is.",
            headers={"X-Sync-Reason": "company_ambiguous"},
        )
    return rows[0] if rows else None


# How often a session's last_active_at is written while it's in use
LAST_ACTIVE_WRITE_INTERVAL_SECONDS = 300

# In-memory auth and permissions caches with 60s TTL
AUTH_CACHE_TTL_SECONDS = 300
PERMISSIONS_CACHE_TTL_SECONDS = 300

# Cache storage:
# _auth_cache: token_hash -> {"user": User, "user_id": int, "allowed_company_ids": Set[int], "expires_at": float,
#                             "session_id": int, "last_active_written": float}
# "user" is a detached snapshot that is only ever merged (copied) into request sessions, never mutated.
_auth_cache: Dict[str, Dict[str, Any]] = {}

# _permissions_cache: user_id -> {"role_id": int, "data": dict, "expires_at": float}
_permissions_cache: Dict[int, Dict[str, Any]] = {}

def _prune_expired_caches(now: float):
    global _auth_cache, _permissions_cache
    if len(_auth_cache) > 100:
        expired_tokens = [k for k, v in _auth_cache.items() if v.get("expires_at", 0) <= now]
        for k in expired_tokens:
            _auth_cache.pop(k, None)
    if len(_permissions_cache) > 100:
        expired_users = [k for k, v in _permissions_cache.items() if v.get("expires_at", 0) <= now]
        for k in expired_users:
            _permissions_cache.pop(k, None)

def invalidate_auth_cache(token_hash: Optional[str] = None, user_id: Optional[int] = None):
    """Invalidate cached session/user entry for a given token hash or user_id."""
    global _auth_cache
    if token_hash:
        _auth_cache.pop(token_hash, None)
    if user_id is not None:
        to_del = [th for th, entry in _auth_cache.items() if entry.get("user_id") == user_id]
        for th in to_del:
            _auth_cache.pop(th, None)

async def revoke_all_user_sessions(user_id: int, db: AsyncSession, reason: str = "password_change",
                                   by_user_id: Optional[int] = None) -> None:
    """Stage revocation of every live session for a user (password change, deactivation).
    The caller commits, then calls invalidate_auth_cache(user_id=...) so no request re-caches a revoked session."""
    from app.core.sessions import revoke_sessions
    await revoke_sessions(db, reason=reason, user_id=user_id, by_user_id=by_user_id)


async def _touch_session(db: AsyncSession, session_id: int) -> None:
    """Record activity on a session in its own short transaction, so the request's work is never committed here."""
    try:
        async with AsyncSession(db.bind, expire_on_commit=False) as touch_db:
            await touch_db.execute(
                update(UserSession)
                .where(UserSession.session_id == session_id)
                .values(last_active_at=datetime.now(timezone.utc).replace(tzinfo=None))
            )
            await touch_db.commit()
    except Exception as e:  # activity tracking must never fail a request
        logger.warning(f"Could not update last_active_at for session {session_id}: {e}")

def invalidate_permissions_cache(user_id: Optional[int] = None):
    """Invalidate cached permissions for a given user_id or all users."""
    global _permissions_cache
    if user_id is not None:
        _permissions_cache.pop(user_id, None)
    else:
        _permissions_cache.clear()

def clear_all_auth_and_permission_caches():
    """Clear all cached sessions and permissions."""
    global _auth_cache, _permissions_cache
    _auth_cache.clear()
    _permissions_cache.clear()

async def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme), 
    db: AsyncSession = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = decode_access_token(token)
    # Covers malformed and JWT-expired tokens (the JWT expires together with its session)
    credentials_exception.headers["X-Auth-Reason"] = "invalid"
    user_id_str = payload.get("sub")
    if user_id_str is None:
        raise credentials_exception
        
    try:
        user_id = int(user_id_str)
    except ValueError:
        raise credentials_exception
        
    # Hash the token to compare with database token_hash
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    
    now = time.time()
    _prune_expired_caches(now)

    # 1. Check in-memory auth cache (0 DB queries on cache hit)
    cached_entry = _auth_cache.get(token_hash)
    if cached_entry and cached_entry.get("expires_at", 0) > now:
        if cached_entry.get("session_id") and now - cached_entry.get("last_active_written", 0) >= LAST_ACTIVE_WRITE_INTERVAL_SECONDS:
            cached_entry["last_active_written"] = now
            await _touch_session(db, cached_entry["session_id"])
        return await _request_user(db, request, cached_entry["user"], cached_entry["allowed_company_ids"])

    # 2. Cache miss: Validate active session from DB
    session_query = await db.execute(
        select(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.token_hash == token_hash,
            UserSession.revoked_at == None,
            UserSession.expires_at > datetime.now(timezone.utc)
        )
    )
    db_session = session_query.scalars().first()
    if not db_session:
        from app.core.sessions import session_end_reason
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or revoked",
            # Lets clients explain the sign-out (and the Sync Agent decide whether to log in again)
            headers={"WWW-Authenticate": "Bearer", "X-Auth-Reason": await session_end_reason(db, user_id, token_hash)},
        )
        
    user_query = await db.execute(
        select(User).options(selectinload(User.role)).where(User.user_id == user_id, User.is_active == True)
    )
    user = user_query.scalars().first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer", "X-Auth-Reason": "deactivated"},
        )

    # Throttled activity heartbeat (also on the cached path above)
    last_active = db_session.last_active_at
    last_active_epoch = last_active.replace(tzinfo=timezone.utc).timestamp() if last_active else 0.0
    if now - last_active_epoch >= LAST_ACTIVE_WRITE_INTERVAL_SECONDS:
        await _touch_session(db, db_session.session_id)
        last_active_epoch = now

    # Query allowed companies for the user to avoid DB hits on header company switching
    allowed_company_ids = await accessible_company_ids(db, user.user_id, user.company_id, user.role.name if user.role else "")

    # Determine session expiry timestamp
    sess_exp = db_session.expires_at
    if sess_exp.tzinfo is None:
        sess_exp = sess_exp.replace(tzinfo=timezone.utc)
    cache_expiry = min(now + AUTH_CACHE_TTL_SECONDS, sess_exp.timestamp())

    # Detach the loaded user (and role) so the cached snapshot can't be changed by this request
    if user.role is not None:
        db.expunge(user.role)
    db.expunge(user)
    _auth_cache[token_hash] = {
        "user": user,
        "user_id": user.user_id,
        "allowed_company_ids": allowed_company_ids,
        "expires_at": cache_expiry,
        "session_id": db_session.session_id,
        "last_active_written": last_active_epoch,
    }

    return await _request_user(db, request, user, allowed_company_ids)


async def get_optional_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """Like get_current_user (including session/revocation checks) but returns None when the
    caller is anonymous or the token is invalid, for endpoints that also allow anonymous use."""
    if not token:
        return None
    try:
        return await get_current_user(request, token, db)
    except HTTPException:
        return None


async def _request_user(db: AsyncSession, request: Request, snapshot: User, allowed_company_ids: Set[int]) -> User:
    """Copy the cached user snapshot into this request's session (no DB query) and apply X-Company-ID.

    The header only re-targets this request: set_committed_value changes company_id without marking it
    dirty, so a commit elsewhere in the request never writes it to users.company_id. Persisting the
    default company is PUT /auth/me/active-company's job."""
    user = await db.merge(snapshot, load=False)
    header_company_id = request.headers.get("x-company-id")
    if header_company_id:
        try:
            h_cid = int(header_company_id)
        except ValueError:
            h_cid = None
        if h_cid is not None and h_cid != user.company_id and h_cid in allowed_company_ids:
            set_committed_value(user, "company_id", h_cid)
    return user


async def bind_sync_company(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Point a Desktop Sync Agent request at the company the agent names, never at the company the account
    happens to have active (someone switching company in the app must not move the agent's queue or
    watermark to another company).

    Like X-Company-ID, this re-targets the one request and writes nothing to users.company_id. An agent
    from before the header existed still gets its account's active company, with a warning in the log."""
    tally_guid = (request.headers.get(SYNC_COMPANY_GUID_HEADER) or "").strip()
    if not tally_guid:
        now = time.time()
        if now - _legacy_sync_warned.get(user.user_id, 0) >= LEGACY_SYNC_WARN_INTERVAL_SECONDS:
            _legacy_sync_warned[user.user_id] = now
            logger.warning(
                f"Sync request to {request.url.path} from user_id={user.user_id} names no Tally company; using the "
                f"account's active company #{user.company_id}. Update the Desktop Sync Agent."
            )
        return
    company = await company_for_tally_guid(db, user, tally_guid)
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"No company you can access is linked to Tally company GUID {tally_guid} yet. "
                   "Run a full sync of that company from the Desktop Sync Agent to link it.",
            headers={"X-Sync-Reason": "company_not_linked"},
        )
    if company.company_id != user.company_id:
        set_committed_value(user, "company_id", company.company_id)


MODULE_TOGGLE_MAPPING = {
    "ledgers": "showLedger",
    "ledger_customer": "showSalesLedgers",
    "ledger_supplier": "showPurchaseLedgers",
    "vouchers": "showVouchers",
    "payments": "showPayments",
    "expenses": "showExpenses",
    "attendance": "showAttendance",
    "inventory": "showStocks",
    "reports": "showReports",
    "orders": "showOrders",
    "visits": "showCheckIn",
    "gst": "showGst",
    "customers": "showCustomers",
}

ALL_KNOWN_MODULES = [
    "ledgers",
    "ledger_groups",
    "cost_categories",
    "cost_centres",
    "cost_centre_classes",
    "currencies",
    "voucher_types",
    "ledger_customer",
    "ledger_supplier",
    "vouchers",
    "payments",
    "outstanding",
    "expenses",
    "attendance",
    "inventory",
    "stock_groups",
    "stock_categories",
    "stock_items",
    "units",
    "godowns",
    "price_lists",
    "bom",
    "reports",
    "orders",
    "visits",
    "gst",
    "customers",
    "users",
    "roles",
    "settings",
    "payroll",
    "admin",
    "sync",
]

SUB_MODULE_PARENT_MAP = {
    "ledger_groups": "ledgers",
    "cost_categories": "ledgers",
    "cost_centres": "ledgers",
    "cost_centre_classes": "ledgers",
    "currencies": "settings",
    "voucher_types": "settings",
    "stock_groups": "inventory",
    "stock_categories": "inventory",
    "stock_items": "inventory",
    "units": "inventory",
    "godowns": "inventory",
    "price_lists": "inventory",
    "bom": "inventory",
}

async def get_all_user_permissions(
    user_id: int,
    role_id: int,
    role_name: str,
    db: AsyncSession
) -> dict:
    """
    Single unified method to resolve all permissions for a user:
    - UI visibility toggles
    - Module CRUD capabilities
    - Voucher action scope ('full', 'can_create', 'view_only')
    - Allowed voucher type IDs (from UserDataScope)

    Admin/Superadmin/Owner queries database permissions and user overrides too,
    allowing granular removal/customization of permissions for admin users if desired.
    """
    now = time.time()
    cached_perm = _permissions_cache.get(user_id)
    if cached_perm and cached_perm.get("expires_at", 0) > now and cached_perm.get("role_id") == role_id:
        return copy.deepcopy(cached_perm["data"])

    # 1. Role permissions joined with Module
    role_perms = (await db.execute(
        select(Permission, Module.code)
        .join(Module, Permission.module_id == Module.module_id)
        .where(Permission.role_id == role_id)
    )).all()

    # 2. User-specific overrides joined with Module
    overrides = (await db.execute(
        select(UserPermissionOverride, Module.code)
        .join(Module, UserPermissionOverride.module_id == Module.module_id)
        .where(UserPermissionOverride.user_id == user_id)
    )).all()

    # 3. user_data_scopes rows for VoucherType
    allowed_ids = (await db.execute(
        select(UserDataScope.scope_ref_id).where(
            UserDataScope.user_id == user_id,
            UserDataScope.scope_type == 'VoucherType'
        )
    )).scalars().all()

    result = _resolve_permissions(role_name, role_perms, overrides, allowed_ids)
    _store_permissions(user_id, role_id, result, now)
    return copy.deepcopy(result)


async def get_permissions_for_users(users: Sequence[User], db: AsyncSession) -> Dict[int, dict]:
    """get_all_user_permissions for many users with three queries in total instead of three per user.
    Users with a fresh cache entry are served from it; the rest are resolved and cached."""
    now = time.time()
    results: Dict[int, dict] = {}
    to_load = []
    for user in users:
        cached_perm = _permissions_cache.get(user.user_id)
        if cached_perm and cached_perm.get("expires_at", 0) > now and cached_perm.get("role_id") == user.role_id:
            results[user.user_id] = copy.deepcopy(cached_perm["data"])
        else:
            to_load.append(user)
    if not to_load:
        return results

    user_ids = [u.user_id for u in to_load]
    perms_by_role: Dict[int, list] = defaultdict(list)
    for perm, code in (await db.execute(
        select(Permission, Module.code)
        .join(Module, Permission.module_id == Module.module_id)
        .where(Permission.role_id.in_({u.role_id for u in to_load}))
    )).all():
        perms_by_role[perm.role_id].append((perm, code))
    overrides_by_user: Dict[int, list] = defaultdict(list)
    for override, code in (await db.execute(
        select(UserPermissionOverride, Module.code)
        .join(Module, UserPermissionOverride.module_id == Module.module_id)
        .where(UserPermissionOverride.user_id.in_(user_ids))
    )).all():
        overrides_by_user[override.user_id].append((override, code))
    scopes_by_user: Dict[int, list] = defaultdict(list)
    for scope_user_id, ref_id in (await db.execute(
        select(UserDataScope.user_id, UserDataScope.scope_ref_id).where(
            UserDataScope.user_id.in_(user_ids),
            UserDataScope.scope_type == 'VoucherType'
        )
    )).all():
        scopes_by_user[scope_user_id].append(ref_id)

    for user in to_load:
        role_name = user.role.name if user.role else "Unknown"
        result = _resolve_permissions(role_name, perms_by_role[user.role_id], overrides_by_user[user.user_id],
                                      scopes_by_user[user.user_id])
        _store_permissions(user.user_id, user.role_id, result, now)
        results[user.user_id] = copy.deepcopy(result)
    return results


def _store_permissions(user_id: int, role_id: int, result: dict, now: float) -> None:
    _permissions_cache[user_id] = {
        "data": result,
        "role_id": role_id,
        "expires_at": now + PERMISSIONS_CACHE_TTL_SECONDS
    }


def _resolve_permissions(role_name: str, role_perms, overrides, allowed_ids) -> dict:
    """Capabilities, UI toggles, voucher action scope and voucher-type scope from a user's rows.
    role_perms and overrides are (row, module code) pairs in query order."""
    is_admin = bool(role_name and role_name.lower() in ("admin", "superadmin", "owner"))

    # Initialize capabilities with defaults (admin defaults to True, others to False)
    capabilities = {}
    default_bool = True if is_admin else False
    for mod in ALL_KNOWN_MODULES:
        capabilities[mod] = {
            "can_create": default_bool,
            "can_read": default_bool,
            "can_update": default_bool,
            "can_delete": default_bool,
        }

    # 1. Role permissions
    for perm, mod_code in role_perms:
        m_code = mod_code.lower()
        capabilities[m_code] = {
            "can_create": bool(perm.can_create),
            "can_read": bool(perm.can_read),
            "can_update": bool(perm.can_update),
            "can_delete": bool(perm.can_delete),
        }

    # 2. User-specific overrides
    for override, mod_code in overrides:
        m_code = mod_code.lower()
        if m_code not in capabilities:
            capabilities[m_code] = {
                "can_create": False,
                "can_read": False,
                "can_update": False,
                "can_delete": False,
            }

        # Role ceiling: non-admin users cannot have access granted if master role has can_read=False
        # For admin users, or if role allowed read, or if override explicitly restricts (can_read=False):
        role_allowed_read = capabilities[m_code].get("can_read", False)
        if is_admin or role_allowed_read or override.can_read is False:
            if override.can_create is not None:
                capabilities[m_code]["can_create"] = bool(override.can_create)
            if override.can_read is not None:
                capabilities[m_code]["can_read"] = bool(override.can_read)
            if override.can_update is not None:
                capabilities[m_code]["can_update"] = bool(override.can_update)
            if override.can_delete is not None:
                capabilities[m_code]["can_delete"] = bool(override.can_delete)

    # 3. Derive UI toggles
    toggles = {
        "showLedger": False,
        "showSalesLedgers": False,
        "showPurchaseLedgers": False,
        "showVouchers": False,
        "showReceipts": False,
        "showPayments": False,
        "showExpenses": False,
        "showAttendance": False,
        "showStocks": False,
        "showReports": False,
        "showOrders": False,
        "showCheckIn": False,
        "showGst": False,
        "showCustomers": False,
        "isAdmin": is_admin,
    }

    for m_code, toggle_key in MODULE_TOGGLE_MAPPING.items():
        if m_code in capabilities:
            toggles[toggle_key] = bool(capabilities[m_code]["can_read"])

    if "vouchers" in capabilities:
        toggles["showReceipts"] = bool(capabilities["vouchers"]["can_read"])

    toggles["showLedger"] = bool(
        toggles.get("showLedger", False) or
        toggles.get("showSalesLedgers", False) or
        toggles.get("showPurchaseLedgers", False)
    )

    # 4. Resolve voucher action scope
    v_perms = capabilities.get("vouchers", {})
    if v_perms.get("can_update") and v_perms.get("can_delete"):
        voucher_action_scope = "full"
    elif v_perms.get("can_create"):
        voucher_action_scope = "can_create"
    else:
        voucher_action_scope = "view_only"

    # 5. Voucher-type scope: None means every voucher type is allowed
    allowed_voucher_type_ids = list(allowed_ids) if allowed_ids else None

    return {
        "toggles": toggles,
        "capabilities": capabilities,
        "voucher_action_scope": voucher_action_scope,
        "allowed_voucher_type_ids": allowed_voucher_type_ids,
    }


async def get_effective_permission(
    user_or_id: User | int, 
    module_code: str, 
    db: AsyncSession,
    user_perms: dict | None = None
) -> dict:
    """
    Resolves the effective permission for a user on a given module.
    Delegates to get_all_user_permissions for consistent logic across roles and overrides.
    If user_perms is provided, extracts capabilities directly without querying the DB.
    """
    m_lower = module_code.lower()

    if user_perms is not None:
        caps = user_perms.get("capabilities", {})
        if m_lower in caps:
            return caps[m_lower]
        parent_mod = SUB_MODULE_PARENT_MAP.get(m_lower)
        if parent_mod and parent_mod in caps:
            return caps[parent_mod]
        return {
            "can_create": False,
            "can_read": False,
            "can_update": False,
            "can_delete": False,
        }

    if isinstance(user_or_id, User):
        user = user_or_id
    else:
        user_query = await db.execute(
            select(User).options(selectinload(User.role)).where(User.user_id == user_or_id)
        )
        user = user_query.scalars().first()

    if not user:
        return {
            "can_create": False,
            "can_read": False,
            "can_update": False,
            "can_delete": False
        }

    r_name = user.role.name if user.role else "Unknown"
    is_admin = bool(r_name and r_name.lower() in ("admin", "superadmin", "owner"))

    # "admin" virtual module check: if checking "admin" access, any admin user passes
    if m_lower == "admin":
        return {
            "can_create": is_admin,
            "can_read": is_admin,
            "can_update": is_admin,
            "can_delete": is_admin,
        }

    all_perms = await get_all_user_permissions(user.user_id, user.role_id, r_name, db)
    caps = all_perms.get("capabilities", {})
    if m_lower in caps:
        return caps[m_lower]

    parent_mod = SUB_MODULE_PARENT_MAP.get(m_lower)
    if parent_mod and parent_mod in caps:
        return caps[parent_mod]

    return {
        "can_create": False,
        "can_read": False,
        "can_update": False,
        "can_delete": False,
    }


async def get_user_permission_toggles(
    user_id: int,
    role_id: int,
    role_name: str,
    db: AsyncSession
) -> dict:
    """
    Returns the UI visibility toggles dynamically resolved for a given user.
    """
    all_perms = await get_all_user_permissions(user_id, role_id, role_name, db)
    return all_perms["toggles"]

def require_permission(module_code: str, action: str):
    """
    FastAPI dependency wrapper for checking permissions.
    action: 'create', 'read', 'update', 'delete'
    """
    async def dependency(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        perms = await get_effective_permission(user, module_code, db)
        field = f"can_{action}"
        if not perms.get(field, False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You do not have permission to {action} in module {module_code}."
            )
        return user
    return dependency

async def require_voucher_read_permission(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    User is allowed to read vouchers if they have read permission for ANY voucher-related module:
    vouchers (Receipts), ledger_customer (Sales), ledger_supplier (Purchases), or payments.
    """
    r_name = user.role.name if user.role else "Unknown"
    all_perms = await get_all_user_permissions(user.user_id, user.role_id, r_name, db)
    for mod_code in ("vouchers", "ledger_customer", "ledger_supplier", "payments"):
        perms = await get_effective_permission(user, mod_code, db, user_perms=all_perms)
        if perms.get("can_read", False):
            return user
            
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have permission to read any voucher categories."
    )

async def require_customer_read_permission(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    User is allowed to read customers/directory if they have read permission for ANY customer-related feature:
    customers (Store), ledger_customer (Customer Statement), orders (Orders), or visits (Check-In).
    Permissions are evaluated strictly against capability records without hardcoded role bypasses.
    """
    r_name = user.role.name if user.role else "Unknown"
    all_perms = await get_all_user_permissions(user.user_id, user.role_id, r_name, db)
    for mod_code in ("customers", "ledger_customer", "orders", "visits"):
        perms = await get_effective_permission(user, mod_code, db, user_perms=all_perms)
        if perms.get("can_read", False):
            return user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have permission to access the customer directory or profile."
    )


async def get_user_allowed_voucher_type_ids(
    user_id: int,
    db: AsyncSession,
    user: User | None = None
) -> list[int] | None:
    """
    Returns the list of allowed voucher_type_ids for the given user from user_data_scopes.
    Returns None if the user has unrestricted access to all voucher types (no scope configured).
    """
    now = time.time()
    cached_perm = _permissions_cache.get(user_id)
    if cached_perm and cached_perm.get("expires_at", 0) > now:
        return copy.deepcopy(cached_perm["data"]["allowed_voucher_type_ids"])

    # Query user_data_scopes for VoucherType scope rows
    scope_query = await db.execute(
        select(UserDataScope.scope_ref_id).where(
            UserDataScope.user_id == user_id,
            UserDataScope.scope_type == 'VoucherType'
        )
    )
    allowed_ids = scope_query.scalars().all()
    if not allowed_ids:
        # None means no restrictions configured -> all voucher types allowed
        return None

    return list(allowed_ids)

