import hashlib
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from app.core.database import get_db
from app.core.config import settings
from app.core.security import decode_access_token
from app.models.user import User, UserSession, UserPermissionOverride, Permission, Module

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/swagger-login")

async def get_current_user(
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
        
    user_query = await db.execute(select(User).where(User.user_id == user_id, User.is_active == True))
    user = user_query.scalars().first()
    if user is None:
        raise credentials_exception
        
    return user

async def get_effective_permission(
    user_id: int, 
    module_code: str, 
    db: AsyncSession
) -> dict:
    """
    Resolves the effective permission for a user on a given module.
    Queries the database roles, permissions, and user_permission_overrides tables.
    """
    from sqlalchemy.orm import selectinload
    from sqlalchemy import func
    
    effective = {
        "can_create": False,
        "can_read": False,
        "can_update": False,
        "can_delete": False
    }
    
    # Eagerly load user and role
    user_query = await db.execute(
        select(User).options(selectinload(User.role)).where(User.user_id == user_id)
    )
    user = user_query.scalars().first()
    
    if not user:
        return effective

    # Admin role gets full access to everything
    if user.role and user.role.name.lower() == "admin":
        return {
            "can_create": True,
            "can_read": True,
            "can_update": True,
            "can_delete": True
        }

    # Find the module by code
    module_query = await db.execute(select(Module).where(func.lower(Module.code) == module_code.lower()))
    module = module_query.scalars().first()
    if not module:
        # Fallback if module is not found
        return effective

    # Get role permission for this module
    perm_query = await db.execute(
        select(Permission).where(
            Permission.role_id == user.role_id,
            Permission.module_id == module.module_id
        )
    )
    perm = perm_query.scalars().first()
    if perm:
        effective["can_create"] = perm.can_create
        effective["can_read"] = perm.can_read
        effective["can_update"] = perm.can_update
        effective["can_delete"] = perm.can_delete

    # Check for user-specific overrides
    override_query = await db.execute(
        select(UserPermissionOverride).where(
            UserPermissionOverride.user_id == user_id,
            UserPermissionOverride.module_id == module.module_id
        )
    )
    override = override_query.scalars().first()
    if override:
        if override.can_create is not None:
            effective["can_create"] = override.can_create
        if override.can_read is not None:
            effective["can_read"] = override.can_read
        if override.can_update is not None:
            effective["can_update"] = override.can_update
        if override.can_delete is not None:
            effective["can_delete"] = override.can_delete

    return effective

async def get_user_permission_toggles(
    user_id: int,
    role_id: int,
    role_name: str,
    db: AsyncSession
) -> dict:
    """
    Returns the UI visibility toggles dynamically resolved for a given user.
    """
    toggles = {
        "showLedger": False,
        "showSalesLedgers": False,
        "showPurchaseLedgers": False,
        "showReceipts": False,
        "showPayments": False,
        "showExpenses": False,
        "showAttendance": False,
        "showStocks": False,
        "showReports": False,
        "showOrders": False,
        "showCheckIn": False,
        "showGst": False
    }

        
    # Mapping of module codes to toggles
    mapping = {
        "ledger_customer": "showSalesLedgers",
        "ledger_supplier": "showPurchaseLedgers",
        "vouchers": "showReceipts",
        "payments": "showPayments",
        "expenses": "showExpenses",
        "attendance": "showAttendance",
        "inventory": "showStocks",
        "reports": "showReports",
        "orders": "showOrders",
        "visits": "showCheckIn",
        "gst": "showGst"
    }
    
    # 1. Fetch role permissions joined with Module
    perm_q = await db.execute(
        select(Permission, Module.code)
        .join(Module, Permission.module_id == Module.module_id)
        .where(Permission.role_id == role_id)
    )
    for perm, mod_code in perm_q.all():
        m_code = mod_code.lower()
        if m_code in mapping:
            toggle_key = mapping[m_code]
            toggles[toggle_key] = perm.can_read

    # 2. Fetch user overrides joined with Module
    override_q = await db.execute(
        select(UserPermissionOverride, Module.code)
        .join(Module, UserPermissionOverride.module_id == Module.module_id)
        .where(UserPermissionOverride.user_id == user_id)
    )
    for override, mod_code in override_q.all():
        m_code = mod_code.lower()
        if m_code in mapping:
            toggle_key = mapping[m_code]
            if override.can_read is not None:
                toggles[toggle_key] = override.can_read
                
    # 3. Derive showLedger
    toggles["showLedger"] = (
        toggles["showSalesLedgers"] or 
        toggles["showPurchaseLedgers"] or 
        toggles["showReceipts"] or 
        toggles["showPayments"]
    )
    return toggles

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
