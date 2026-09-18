from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from datetime import date
from pydantic import BaseModel

from app.core.database import get_db
from app.core.permissions import get_current_user, get_user_permission_toggles
from app.core.security import get_password_hash
from app.models.portal_core import User, Role, Permission, Module, UserPermissionOverride
from app.models.portal_core import AuditLog

router = APIRouter(prefix="/admin", tags=["Admin Panel"])

from typing import Optional

class AdminUserResponse(BaseModel):
    user_id: int
    username: str
    email: str
    is_active: bool
    role_id: int
    role_name: str
    showLedger: bool
    showSalesLedgers: bool
    showPurchaseLedgers: bool
    showReceipts: bool
    showPayments: bool
    showExpenses: bool
    showAttendance: bool
    showStocks: bool
    showReports: bool
    showOrders: bool
    showCheckIn: bool
    showGst: bool
    showCustomers: bool = True
    ledgerScope: str
    stockScope: str
    allowedStockGroups: Optional[str] = None
    allowedLedgerGroups: Optional[str] = None
    allowedReportCategories: Optional[str] = None

class AdminUserCreate(BaseModel):
    username: str
    email: str
    password: str
    role_id: int

from sqlalchemy import delete, func

class UserRoleUpdate(BaseModel):
    role_id: Optional[int] = None
    role: Optional[str] = None

class RoleResponse(BaseModel):
    role_id: int
    name: str
    description: Optional[str] = None
    user_count: int = 0
    is_system: bool = False

class RoleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    clone_from_role_id: Optional[int] = None

class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class RolePermissionItem(BaseModel):
    module_id: int
    code: str
    name: str
    description: Optional[str] = None
    can_create: bool
    can_read: bool
    can_update: bool
    can_delete: bool

class ModuleResponse(BaseModel):
    module_id: int
    code: str
    name: str
    description: Optional[str] = None

class PermissionItem(BaseModel):
    permission_id: int
    role_id: int
    module_id: int
    can_create: bool
    can_read: bool
    can_update: bool
    can_delete: bool

class PermissionUpdateItem(BaseModel):
    role_id: Optional[int] = None
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
    if not role or role.name.lower() not in ("admin", "superadmin", "owner"):
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
        r_name = role.name if role else "Unknown"
        toggles = await get_user_permission_toggles(u.user_id, u.role_id, r_name, db)
        response.append(AdminUserResponse(
            user_id=u.user_id,
            username=u.username,
            email=u.email,
            is_active=u.is_active,
            role_id=u.role_id,
            role_name=r_name,
            showLedger=toggles["showLedger"],
            showSalesLedgers=toggles["showSalesLedgers"],
            showPurchaseLedgers=toggles["showPurchaseLedgers"],
            showReceipts=toggles["showReceipts"],
            showPayments=toggles["showPayments"],
            showExpenses=toggles["showExpenses"],
            showAttendance=toggles["showAttendance"],
            showStocks=toggles["showStocks"],
            showReports=toggles["showReports"],
            showOrders=toggles["showOrders"],
            showCheckIn=toggles["showCheckIn"],
            showGst=toggles["showGst"],
            showCustomers=toggles.get("showCustomers", True),
            ledgerScope=u.ledger_scope,
            stockScope=u.stock_scope,
            allowedStockGroups=u.allowed_stock_groups,
            allowedLedgerGroups=u.allowed_ledger_groups,
            allowedReportCategories=u.allowed_report_categories,
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
    is_new_admin = role.name == "Admin"
    user = User(
        company_id=admin.company_id,
        username=payload.username,
        email=payload.email,
        password_hash=password_hash,
        role_id=payload.role_id,
        is_active=True,
        ledger_scope='full' if is_new_admin else 'none',
        stock_scope='full' if is_new_admin else 'none'
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    toggles = await get_user_permission_toggles(user.user_id, user.role_id, role.name, db)
    return AdminUserResponse(
        user_id=user.user_id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        role_id=user.role_id,
        role_name=role.name,
        showLedger=toggles["showLedger"],
        showSalesLedgers=toggles["showSalesLedgers"],
        showPurchaseLedgers=toggles["showPurchaseLedgers"],
        showReceipts=toggles["showReceipts"],
        showPayments=toggles["showPayments"],
        showExpenses=toggles["showExpenses"],
        showAttendance=toggles["showAttendance"],
        showStocks=toggles["showStocks"],
        showReports=toggles["showReports"],
        showOrders=toggles["showOrders"],
        showCheckIn=toggles["showCheckIn"],
        showGst=toggles["showGst"],
        showCustomers=toggles.get("showCustomers", True),
        ledgerScope=user.ledger_scope,
        stockScope=user.stock_scope,
        allowedStockGroups=user.allowed_stock_groups,
        allowedLedgerGroups=user.allowed_ledger_groups,
        allowedReportCategories=user.allowed_report_categories,
    )


class UserPasswordReset(BaseModel):
    password: str

@router.put("/users/{user_id}/reset-password")
async def reset_user_password(
    user_id: int,
    payload: UserPasswordReset,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    if len(payload.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters long."
        )

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

    password_hash = get_password_hash(payload.password)
    user.password_hash = password_hash
    await db.commit()
    return {"success": True, "message": f"Password reset successfully for user: {user.username}"}

class UserRoleToggle(BaseModel):
    role_id: Optional[int] = None
    role: Optional[str] = None

@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: int,
    payload: UserRoleToggle,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    if user_id == admin.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot change your own admin role."
        )
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
        
    role = None
    if payload.role_id is not None:
        role = (await db.execute(select(Role).where(Role.role_id == payload.role_id))).scalars().first()
    elif payload.role:
        role_str = payload.role.strip()
        role = (await db.execute(select(Role).where(Role.name.ilike(role_str)))).scalars().first()

    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role not found."
        )
        
    user.role_id = role.role_id
    # Reset any explicit user overrides so the user inherits their role's permissions cleanly
    await db.execute(delete(UserPermissionOverride).where(UserPermissionOverride.user_id == user_id))
    await db.commit()
    return {"detail": f"User role updated to {role.name} successfully."}

@router.get("/roles", response_model=List[RoleResponse])
async def get_roles(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    roles_q = await db.execute(select(Role).order_by(Role.role_id.asc()))
    roles = roles_q.scalars().all()
    
    # Calculate user count per role
    counts_q = await db.execute(
        select(User.role_id, func.count(User.user_id)).group_by(User.role_id)
    )
    counts = {r[0]: r[1] for r in counts_q.all()}
    
    result = []
    for r in roles:
        is_sys = r.name.lower() in ("admin", "sales")
        result.append(RoleResponse(
            role_id=r.role_id,
            name=r.name,
            description=r.description or "",
            user_count=counts.get(r.role_id, 0),
            is_system=is_sys
        ))
    return result

@router.post("/roles", response_model=RoleResponse)
async def create_role(
    payload: RoleCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Role name is required.")
        
    existing = (await db.execute(select(Role).where(func.lower(Role.name) == name.lower()))).scalars().first()
    if existing:
        raise HTTPException(status_code=400, detail=f"A role with name '{name}' already exists.")
        
    new_role = Role(name=name, description=payload.description)
    db.add(new_role)
    await db.flush()  # Populates new_role.role_id
    
    # Clone permissions if requested
    if payload.clone_from_role_id:
        base_perms = (await db.execute(
            select(Permission).where(Permission.role_id == payload.clone_from_role_id)
        )).scalars().all()
        for bp in base_perms:
            np = Permission(
                role_id=new_role.role_id,
                module_id=bp.module_id,
                can_create=bp.can_create,
                can_read=bp.can_read,
                can_update=bp.can_update,
                can_delete=bp.can_delete
            )
            db.add(np)
    else:
        # Default: seed default permission rows for all registered modules
        all_mods = (await db.execute(select(Module))).scalars().all()
        for m in all_mods:
            np = Permission(
                role_id=new_role.role_id,
                module_id=m.module_id,
                can_create=False,
                can_read=False,
                can_update=False,
                can_delete=False
            )
            db.add(np)
            
    await db.commit()
    await db.refresh(new_role)
    return RoleResponse(
        role_id=new_role.role_id,
        name=new_role.name,
        description=new_role.description or "",
        user_count=0,
        is_system=False
    )

@router.put("/roles/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: int,
    payload: RoleUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    role = (await db.execute(select(Role).where(Role.role_id == role_id))).scalars().first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found.")
        
    if role.name.lower() == "admin" and payload.name and payload.name.lower() != "admin":
        raise HTTPException(status_code=400, detail="The Administrator role name cannot be changed.")
        
    if payload.name:
        name = payload.name.strip()
        dup = (await db.execute(
            select(Role).where(func.lower(Role.name) == name.lower(), Role.role_id != role_id)
        )).scalars().first()
        if dup:
            raise HTTPException(status_code=400, detail=f"Another role with name '{name}' already exists.")
        role.name = name
        
    if payload.description is not None:
        role.description = payload.description
        
    await db.commit()
    await db.refresh(role)
    
    cnt = (await db.execute(select(func.count(User.user_id)).where(User.role_id == role_id))).scalar() or 0
    return RoleResponse(
        role_id=role.role_id,
        name=role.name,
        description=role.description or "",
        user_count=cnt,
        is_system=role.name.lower() in ("admin", "sales")
    )

@router.delete("/roles/{role_id}")
async def delete_role(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    role = (await db.execute(select(Role).where(Role.role_id == role_id))).scalars().first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found.")
        
    if role.name.lower() in ("admin", "sales"):
        raise HTTPException(status_code=400, detail="System roles (Admin, Sales) cannot be deleted.")
        
    user_count = (await db.execute(
        select(func.count(User.user_id)).where(User.role_id == role_id)
    )).scalar() or 0
    
    if user_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete role '{role.name}' because {user_count} user(s) are currently assigned to it. Please reassign those users first."
        )
        
    # Delete associated permissions
    await db.execute(delete(Permission).where(Permission.role_id == role_id))
    await db.delete(role)
    await db.commit()
    return {"success": True, "detail": f"Role '{role.name}' deleted successfully."}

@router.get("/roles/{role_id}/permissions", response_model=List[RolePermissionItem])
async def get_role_permissions(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    role = (await db.execute(select(Role).where(Role.role_id == role_id))).scalars().first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found.")
        
    all_mods = (await db.execute(select(Module).order_by(Module.module_id.asc()))).scalars().all()
    
    # If Admin, return full permissions for all modules
    if role.name.lower() == "admin":
        return [
            RolePermissionItem(
                module_id=m.module_id,
                code=m.code,
                name=m.name,
                description=m.description,
                can_create=True,
                can_read=True,
                can_update=True,
                can_delete=True
            ) for m in all_mods
        ]
        
    existing_perms = (await db.execute(
        select(Permission).where(Permission.role_id == role_id)
    )).scalars().all()
    perm_map = {p.module_id: p for p in existing_perms}
    
    result = []
    for m in all_mods:
        p = perm_map.get(m.module_id)
        result.append(RolePermissionItem(
            module_id=m.module_id,
            code=m.code,
            name=m.name,
            description=m.description,
            can_create=bool(p.can_create) if p else False,
            can_read=bool(p.can_read) if p else False,
            can_update=bool(p.can_update) if p else False,
            can_delete=bool(p.can_delete) if p else False
        ))
    return result

@router.put("/roles/{role_id}/permissions")
async def update_role_permissions(
    role_id: int,
    payload: List[PermissionUpdateItem],
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    role = (await db.execute(select(Role).where(Role.role_id == role_id))).scalars().first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found.")
        
    if role.name.lower() == "admin":
        raise HTTPException(
            status_code=400,
            detail="Administrator permissions cannot be restricted. Admin always retains full access to all features."
        )
        
    for item in payload:
        perm = (await db.execute(
            select(Permission).where(
                Permission.role_id == role_id,
                Permission.module_id == item.module_id
            )
        )).scalars().first()
        if perm:
            perm.can_create = item.can_create
            perm.can_read = item.can_read
            perm.can_update = item.can_update
            perm.can_delete = item.can_delete
        else:
            new_perm = Permission(
                role_id=role_id,
                module_id=item.module_id,
                can_create=item.can_create,
                can_read=item.can_read,
                can_update=item.can_update,
                can_delete=item.can_delete
            )
            db.add(new_perm)
            
    await db.commit()
    return {"success": True, "detail": f"Permissions for role '{role.name}' updated successfully."}

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


from app.models.portal_core import Company
from app.models.portal_core import UserCompanyAccess, UserPermissionOverride

class CompanyResponse(BaseModel):
    company_id: int
    name: str
    gstin: Optional[str] = None
    pan: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    country: Optional[str] = None
    telephone: Optional[str] = None
    mobile: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    financial_year_start: Optional[date] = None
    books_begin_date: Optional[date] = None

    class Config:
        from_attributes = True

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
        
    # Ensure target user active company_id is valid
    target_user = (await db.execute(select(User).where(User.user_id == user_id))).scalars().first()
    if target_user and payload.company_ids:
        if target_user.company_id not in payload.company_ids:
            target_user.company_id = payload.company_ids[0]

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

class UserPermissionsToggle(BaseModel):
    showSalesLedgers: bool
    showPurchaseLedgers: bool
    showReceipts: bool
    showPayments: bool
    showExpenses: bool
    showAttendance: bool
    showStocks: bool
    showReports: bool
    showOrders: bool
    showCheckIn: bool
    showGst: bool
    showCustomers: Optional[bool] = None

class UserScopesToggle(BaseModel):
    ledgerScope: str
    stockScope: str
    allowedLedgerGroups: Optional[str] = None
    allowedStockGroups: Optional[str] = None
    allowedReportCategories: Optional[str] = None

class UserStatusToggle(BaseModel):
    isActive: bool

@router.put("/users/{user_id}/permissions")
async def update_user_permissions(
    user_id: int,
    payload: UserPermissionsToggle,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    user_q = await db.execute(
        select(User).where(User.user_id == user_id, User.company_id == admin.company_id)
    )
    user = user_q.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )
        
    mapping = {
        "ledger_customer": payload.showSalesLedgers,
        "ledger_supplier": payload.showPurchaseLedgers,
        "vouchers": payload.showReceipts,
        "payments": payload.showPayments,
        "expenses": payload.showExpenses,
        "attendance": payload.showAttendance,
        "inventory": payload.showStocks,
        "reports": payload.showReports,
        "orders": payload.showOrders,
        "visits": payload.showCheckIn,
        "gst": payload.showGst
    }
    if payload.showCustomers is not None:
        mapping["customers"] = payload.showCustomers
    
    for mod_code, requested_val in mapping.items():
        # Find module
        mod_q = await db.execute(select(Module).where(Module.code == mod_code))
        module = mod_q.scalars().first()
        if not module:
            continue
            
        # Get default permission for user role
        perm_q = await db.execute(
            select(Permission).where(
                Permission.role_id == user.role_id,
                Permission.module_id == module.module_id
            )
        )
        perm = perm_q.scalars().first()
        default_read = perm.can_read if perm else False
        
        # Upsert or Delete override
        if requested_val != default_read:
            ov_q = await db.execute(
                select(UserPermissionOverride).where(
                    UserPermissionOverride.user_id == user_id,
                    UserPermissionOverride.module_id == module.module_id
                )
            )
            override = ov_q.scalars().first()
            if not override:
                override = UserPermissionOverride(
                    user_id=user_id,
                    module_id=module.module_id,
                    granted_by=admin.user_id,
                    reason="Admin Panel Toggle"
                )
                db.add(override)
            override.can_read = requested_val
            override.can_create = requested_val
            override.can_update = requested_val
            override.can_delete = requested_val
        else:
            ov_q = await db.execute(
                select(UserPermissionOverride).where(
                    UserPermissionOverride.user_id == user_id,
                    UserPermissionOverride.module_id == module.module_id
                )
            )
            override = ov_q.scalars().first()
            if override:
                await db.delete(override)
                
    await db.commit()
    return {"success": True}

@router.put("/users/{user_id}/scopes")
async def update_user_scopes(
    user_id: int,
    payload: UserScopesToggle,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    user_q = await db.execute(
        select(User).where(User.user_id == user_id, User.company_id == admin.company_id)
    )
    user = user_q.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )
        
    user.ledger_scope = payload.ledgerScope
    user.stock_scope = payload.stockScope
    user.allowed_ledger_groups = payload.allowedLedgerGroups
    user.allowed_stock_groups = payload.allowedStockGroups
    user.allowed_report_categories = payload.allowedReportCategories
    
    await db.commit()
    return {"success": True}

@router.put("/users/{user_id}/status")
async def update_user_status(
    user_id: int,
    payload: UserStatusToggle,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    if user_id == admin.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot toggle active status on your own admin account."
        )
    user_q = await db.execute(
        select(User).where(User.user_id == user_id, User.company_id == admin.company_id)
    )
    user = user_q.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )
        
    user.is_active = payload.isActive
    await db.commit()
    return {"success": True}

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

