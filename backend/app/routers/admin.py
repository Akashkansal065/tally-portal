from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from pydantic import BaseModel

from app.core.database import get_db
from app.core.permissions import get_current_user
from app.core.security import get_password_hash
from app.models.user import User, Role, Permission, Module
from app.models.voucher import AuditLog

router = APIRouter(prefix="/admin", tags=["Admin Panel"])

class AdminUserResponse(BaseModel):
    user_id: int
    username: str
    email: str
    is_active: bool
    role_id: int
    role_name: str

class AdminUserCreate(BaseModel):
    username: str
    email: str
    password: str
    role_id: int

class UserRoleUpdate(BaseModel):
    role_id: int

class RoleResponse(BaseModel):
    role_id: int
    name: str
    description: str

class ModuleResponse(BaseModel):
    module_id: int
    code: str
    name: str
    description: str

class PermissionItem(BaseModel):
    permission_id: int
    role_id: int
    module_id: int
    can_create: bool
    can_read: bool
    can_update: bool
    can_delete: bool

class PermissionUpdateItem(BaseModel):
    role_id: int
    module_id: int
    can_create: bool
    can_read: bool
    can_update: bool
    can_delete: bool

# Helper to verify current user is Admin
async def require_admin(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> User:
    role_q = await db.execute(select(Role).where(Role.role_id == user.role_id))
    role = role_q.scalars().first()
    if not role or role.name != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Administrator privileges required."
        )
    return user

@router.get("/users", response_model=List[AdminUserResponse])
async def get_users(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    query = await db.execute(
        select(User).where(User.company_id == admin.company_id)
    )
    users = query.scalars().all()
    
    response = []
    for u in users:
        # Load role details
        role_q = await db.execute(select(Role).where(Role.role_id == u.role_id))
        role = role_q.scalars().first()
        response.append(AdminUserResponse(
            user_id=u.user_id,
            username=u.username,
            email=u.email,
            is_active=u.is_active,
            role_id=u.role_id,
            role_name=role.name if role else "Unknown"
        ))
    return response

@router.post("/users", response_model=AdminUserResponse)
async def create_user(
    payload: AdminUserCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    # Check if user already exists
    user_exists_query = await db.execute(select(User).where(User.email == payload.email))
    if user_exists_query.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists."
        )
        
    # Check if role exists
    role_q = await db.execute(select(Role).where(Role.role_id == payload.role_id))
    role = role_q.scalars().first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role not found."
        )
        
    password_hash = get_password_hash(payload.password)
    user = User(
        company_id=admin.company_id,
        username=payload.username,
        email=payload.email,
        password_hash=password_hash,
        role_id=payload.role_id,
        is_active=True
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    return AdminUserResponse(
        user_id=user.user_id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        role_id=user.role_id,
        role_name=role.name
    )

@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: int,
    payload: UserRoleUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    # Verify user belongs to same company
    user_q = await db.execute(
        select(User).where(User.user_id == user_id, User.company_id == admin.company_id)
    )
    user = user_q.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )
        
    # Verify role exists
    role_q = await db.execute(select(Role).where(Role.role_id == payload.role_id))
    role = role_q.scalars().first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role not found."
        )
        
    user.role_id = payload.role_id
    await db.commit()
    return {"detail": f"User role updated to {role.name} successfully."}

@router.get("/roles", response_model=List[RoleResponse])
async def get_roles(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    query = await db.execute(select(Role))
    return query.scalars().all()

@router.get("/modules", response_model=List[ModuleResponse])
async def get_modules(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    query = await db.execute(select(Module))
    return query.scalars().all()

@router.get("/permissions", response_model=List[PermissionItem])
async def get_permissions(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    query = await db.execute(select(Permission))
    return query.scalars().all()

@router.post("/permissions")
async def update_permissions(
    payload: List[PermissionUpdateItem],
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    for item in payload:
        # Find existing permission or create new one
        perm_q = await db.execute(
            select(Permission).where(
                Permission.role_id == item.role_id,
                Permission.module_id == item.module_id
            )
        )
        perm = perm_q.scalars().first()
        if perm:
            perm.can_create = item.can_create
            perm.can_read = item.can_read
            perm.can_update = item.can_update
            perm.can_delete = item.can_delete
        else:
            new_perm = Permission(
                role_id=item.role_id,
                module_id=item.module_id,
                can_create=item.can_create,
                can_read=item.can_read,
                can_update=item.can_update,
                can_delete=item.can_delete
            )
            db.add(new_perm)
            
    await db.commit()
    return {"detail": "Permissions matrix updated successfully."}


from app.models.company import Company
from app.models.user import UserCompanyAccess, UserPermissionOverride

class CompanyResponse(BaseModel):
    company_id: int
    name: str

class UserCompanyUpdate(BaseModel):
    company_ids: List[int]

class UserPermissionOverrideItem(BaseModel):
    module_id: int
    can_create: bool
    can_read: bool
    can_update: bool
    can_delete: bool

@router.get("/companies", response_model=List[CompanyResponse])
async def get_companies(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    query = await db.execute(select(Company))
    return query.scalars().all()

@router.get("/users/{user_id}/companies", response_model=List[int])
async def get_user_companies(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    query = await db.execute(
        select(UserCompanyAccess.company_id).where(UserCompanyAccess.user_id == user_id)
    )
    return query.scalars().all()

@router.put("/users/{user_id}/companies")
async def update_user_companies(
    user_id: int,
    payload: UserCompanyUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    # Clear existing
    await db.execute(
        UserCompanyAccess.__table__.delete().where(UserCompanyAccess.user_id == user_id)
    )
    
    # Insert new
    for cid in payload.company_ids:
        access = UserCompanyAccess(user_id=user_id, company_id=cid)
        db.add(access)
        
    await db.commit()
    return {"detail": "User company access updated successfully."}

@router.get("/users/{user_id}/permissions", response_model=List[UserPermissionOverrideItem])
async def get_user_permissions(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    query = await db.execute(
        select(UserPermissionOverride).where(UserPermissionOverride.user_id == user_id)
    )
    overrides = query.scalars().all()
    return overrides

@router.put("/users/{user_id}/permissions")
async def update_user_permissions(
    user_id: int,
    payload: List[UserPermissionOverrideItem],
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    # Clear existing
    await db.execute(
        UserPermissionOverride.__table__.delete().where(UserPermissionOverride.user_id == user_id)
    )
    
    # Insert new
    for item in payload:
        override = UserPermissionOverride(
            user_id=user_id,
            module_id=item.module_id,
            can_create=item.can_create,
            can_read=item.can_read,
            can_update=item.can_update,
            can_delete=item.can_delete,
            granted_by=admin.user_id
        )
        db.add(override)
        
    await db.commit()
    return {"detail": "User permissions updated successfully."}

@router.get("/audit-logs")
async def get_audit_logs(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    stmt = (
        select(AuditLog)
        .where(AuditLog.company_id == admin.company_id)
        .order_by(AuditLog.created_at.desc())
        .limit(100)
    )
    res = await db.execute(stmt)
    logs = res.scalars().all()

    output = []
    for l in logs:
        # Get user email
        user_q = await db.execute(select(User).where(User.user_id == l.user_id))
        u = user_q.scalars().first()
        output.append({
            "id": l.audit_id,
            "user_email": u.email if u else "System",
            "action": l.action,
            "resource": l.entity_type,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        })
    return output

