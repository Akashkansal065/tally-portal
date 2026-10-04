import hashlib
import time
import copy
from typing import Dict, Any, Optional, Set
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import update
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
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

# In-memory auth and permissions caches with 60s TTL
AUTH_CACHE_TTL_SECONDS = 300
PERMISSIONS_CACHE_TTL_SECONDS = 300

# Cache storage:
# _auth_cache: token_hash -> {"user": User, "user_id": int, "allowed_company_ids": Set[int], "expires_at": float}
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

async def revoke_all_user_sessions(user_id: int, db: AsyncSession) -> None:
    """Stage revocation of every live session for a user (password change, deactivation).
    The caller commits, then calls invalidate_auth_cache(user_id=...) so no request re-caches a revoked session."""
    await db.execute(
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.revoked_at == None)
        .values(revoked_at=datetime.now(timezone.utc))
    )

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
        cached_user = cached_entry["user"]
        # Merge user into current session identity map without querying DB
        user = await db.merge(cached_user, load=False)
        allowed_company_ids = cached_entry["allowed_company_ids"]

        header_company_id = request.headers.get("x-company-id") or request.headers.get("X-Company-ID")
        if header_company_id:
            try:
                h_cid = int(header_company_id)
                if h_cid != user.company_id and h_cid in allowed_company_ids:
                    user.company_id = h_cid
            except ValueError:
                pass
        return user

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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    user_query = await db.execute(
        select(User).options(selectinload(User.role)).where(User.user_id == user_id, User.is_active == True)
    )
    user = user_query.scalars().first()
    if user is None:
        raise credentials_exception

    # Query allowed companies for the user to avoid DB hits on header company switching
    allowed_company_ids: Set[int] = {user.company_id}
    r_name = user.role.name if user.role else ""
    is_admin = bool(r_name and r_name.lower() in ("admin", "superadmin", "owner"))
    if is_admin:
        comp_res = await db.execute(select(Company.company_id).where(Company.is_active == True))
        for cid in comp_res.scalars().all():
            allowed_company_ids.add(cid)
    else:
        acc_stmt = select(UserCompanyAccess.company_id).where(UserCompanyAccess.user_id == user.user_id)
        acc_res = await db.execute(acc_stmt)
        for cid in acc_res.scalars().all():
            allowed_company_ids.add(cid)

    # Determine session expiry timestamp
    sess_exp = db_session.expires_at
    if sess_exp.tzinfo is None:
        sess_exp = sess_exp.replace(tzinfo=timezone.utc)
    cache_expiry = min(now + AUTH_CACHE_TTL_SECONDS, sess_exp.timestamp())

    _auth_cache[token_hash] = {
        "user": user,
        "user_id": user.user_id,
        "allowed_company_ids": allowed_company_ids,
        "expires_at": cache_expiry
    }

    # Support dynamic company switching via X-Company-ID request header
    header_company_id = request.headers.get("x-company-id") or request.headers.get("X-Company-ID")
    if header_company_id:
        try:
            h_cid = int(header_company_id)
            if h_cid != user.company_id and h_cid in allowed_company_ids:
                user.company_id = h_cid
        except ValueError:
            pass

    return user

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
    is_admin = bool(role_name and role_name.lower() in ("admin", "superadmin", "owner"))

    now = time.time()
    cached_perm = _permissions_cache.get(user_id)
    if cached_perm and cached_perm.get("expires_at", 0) > now and cached_perm.get("role_id") == role_id:
        return copy.deepcopy(cached_perm["data"])

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

    # 1. Fetch role permissions joined with Module
    perm_q = await db.execute(
        select(Permission, Module.code)
        .join(Module, Permission.module_id == Module.module_id)
        .where(Permission.role_id == role_id)
    )
    for perm, mod_code in perm_q.all():
        m_code = mod_code.lower()
        capabilities[m_code] = {
            "can_create": bool(perm.can_create),
            "can_read": bool(perm.can_read),
            "can_update": bool(perm.can_update),
            "can_delete": bool(perm.can_delete),
        }

    # 2. Fetch user-specific overrides joined with Module
    override_q = await db.execute(
        select(UserPermissionOverride, Module.code)
        .join(Module, UserPermissionOverride.module_id == Module.module_id)
        .where(UserPermissionOverride.user_id == user_id)
    )
    for override, mod_code in override_q.all():
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

    # 5. Query user_data_scopes for VoucherType scope rows
    scope_query = await db.execute(
        select(UserDataScope.scope_ref_id).where(
            UserDataScope.user_id == user_id,
            UserDataScope.scope_type == 'VoucherType'
        )
    )
    allowed_ids = scope_query.scalars().all()
    allowed_voucher_type_ids = list(allowed_ids) if allowed_ids else None

    result = {
        "toggles": toggles,
        "capabilities": capabilities,
        "voucher_action_scope": voucher_action_scope,
        "allowed_voucher_type_ids": allowed_voucher_type_ids,
    }

    _permissions_cache[user_id] = {
        "data": result,
        "role_id": role_id,
        "expires_at": now + PERMISSIONS_CACHE_TTL_SECONDS
    }

    return copy.deepcopy(result)


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

