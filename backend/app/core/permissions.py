import hashlib
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from app.core.database import get_db
from app.core.config import settings
from app.core.security import decode_access_token
from app.models.portal_core import User, UserSession, UserPermissionOverride, Permission, Module, UserDataScope

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/swagger-login")

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
        
    # Support dynamic company switching via X-Company-ID request header
    header_company_id = request.headers.get("x-company-id") or request.headers.get("X-Company-ID")
    if header_company_id:
        try:
            h_cid = int(header_company_id)
            if h_cid != user.company_id:
                from app.models.portal_core import UserCompanyAccess
                acc_stmt = select(UserCompanyAccess).where(
                    UserCompanyAccess.user_id == user.user_id,
                    UserCompanyAccess.company_id == h_cid
                )
                acc_res = await db.execute(acc_stmt)
                if acc_res.scalars().first():
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
    "ledger_customer",
    "ledger_supplier",
    "vouchers",
    "payments",
    "expenses",
    "attendance",
    "inventory",
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

    return {
        "toggles": toggles,
        "capabilities": capabilities,
        "voucher_action_scope": voucher_action_scope,
        "allowed_voucher_type_ids": allowed_voucher_type_ids,
    }


async def get_effective_permission(
    user_id: int, 
    module_code: str, 
    db: AsyncSession
) -> dict:
    """
    Resolves the effective permission for a user on a given module.
    Delegates to get_all_user_permissions for consistent logic across roles and overrides.
    """
    user_query = await db.execute(
        select(User).options(selectinload(User.role)).where(User.user_id == user_id)
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
    if module_code.lower() == "admin":
        return {
            "can_create": is_admin,
            "can_read": is_admin,
            "can_update": is_admin,
            "can_delete": is_admin,
        }

    all_perms = await get_all_user_permissions(user.user_id, user.role_id, r_name, db)
    default_access = is_admin
    return all_perms["capabilities"].get(
        module_code.lower(),
        {
            "can_create": default_access,
            "can_read": default_access,
            "can_update": default_access,
            "can_delete": default_access,
        }
    )


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
        perms = await get_effective_permission(user.user_id, module_code, db)
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
    for mod_code in ("vouchers", "ledger_customer", "ledger_supplier", "payments"):
        perms = await get_effective_permission(user.user_id, mod_code, db)
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
    Admin unconditionally gets access via get_effective_permission.
    """
    for mod_code in ("customers", "ledger_customer", "orders", "visits"):
        perms = await get_effective_permission(user.user_id, mod_code, db)
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

