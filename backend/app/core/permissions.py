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

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

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
    Resolves using User permission columns directly, mapping them from tally-web permissions schema.
    """
    from sqlalchemy.orm import selectinload
    
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
    is_admin = False
    if user.role and user.role.name.lower() == "admin":
        is_admin = True
        
    if is_admin:
        return {
            "can_create": True,
            "can_read": True,
            "can_update": True,
            "can_delete": True
        }

    m_code = module_code.lower()
    
    # 1. Ledgers / Customers / Suppliers
    if "ledger" in m_code:
        # showLedger is derived from show_sales_ledgers or show_purchase_ledgers or show_receipts or show_payments
        has_access = user.show_sales_ledgers or user.show_purchase_ledgers or user.show_receipts or user.show_payments
        effective["can_read"] = has_access
        effective["can_create"] = has_access
        effective["can_update"] = has_access
        effective["can_delete"] = has_access
        
    # 2. Inventory / Stocks
    elif "inventory" in m_code or "stock" in m_code:
        effective["can_read"] = user.show_stocks
        effective["can_create"] = user.show_stocks
        effective["can_update"] = user.show_stocks
        effective["can_delete"] = user.show_stocks
        
    # 3. Reports
    elif "report" in m_code:
        effective["can_read"] = user.show_reports
        effective["can_create"] = user.show_reports
        effective["can_update"] = user.show_reports
        effective["can_delete"] = user.show_reports
        
    # 4. Orders
    elif "order" in m_code:
        effective["can_read"] = user.show_orders
        effective["can_create"] = user.show_orders
        effective["can_update"] = user.show_orders
        effective["can_delete"] = user.show_orders
        
    # 5. Check-In / Shop Visits
    elif "visit" in m_code or "check" in m_code:
        effective["can_read"] = user.show_check_in
        effective["can_create"] = user.show_check_in
        effective["can_update"] = user.show_check_in
        effective["can_delete"] = user.show_check_in
        
    # 6. Payments / Receipts / Expenses
    elif "payment" in m_code:
        # User has payments or receipts enabled
        has_access = user.show_payments or user.show_receipts or user.show_expenses
        effective["can_read"] = has_access
        effective["can_create"] = has_access
        effective["can_update"] = has_access
        effective["can_delete"] = has_access
        
    else:
        # Fail-safe read
        effective["can_read"] = True
        
    return effective

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
