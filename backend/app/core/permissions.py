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
    Resolution order:
    1. user_permission_overrides: Any non-NULL fields win.
    2. permissions (Role-level): Fall back if override is missing or has NULL fields.
    3. Fail-safe: read-only (can_read=True, others=False).
    """
    effective = {
        "can_create": False,
        "can_read": True,  # Fail-safe read
        "can_update": False,
        "can_delete": False
    }
    
    module_query = await db.execute(select(Module).where(Module.code == module_code))
    module = module_query.scalars().first()
    if not module:
        return effective
        
    # Check override
    override_query = await db.execute(
        select(UserPermissionOverride).where(
            UserPermissionOverride.user_id == user_id,
            UserPermissionOverride.module_id == module.module_id,
            (UserPermissionOverride.expires_at == None) | (UserPermissionOverride.expires_at > datetime.now(timezone.utc))
        )
    )
    override = override_query.scalars().first()
    
    # Check role-level permission
    user_query = await db.execute(
        select(User).where(User.user_id == user_id)
    )
    user = user_query.scalars().first()
    
    permission = None
    if user:
        perm_query = await db.execute(
            select(Permission).where(
                Permission.role_id == user.role_id,
                Permission.module_id == module.module_id
            )
        )
        permission = perm_query.scalars().first()
        
    # Evaluate permissions (Override wins first, then role)
    for field in ["can_create", "can_read", "can_update", "can_delete"]:
        if override and getattr(override, field) is not None:
            effective[field] = getattr(override, field)
        elif permission is not None:
            effective[field] = getattr(permission, field)
            
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
