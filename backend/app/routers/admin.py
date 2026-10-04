from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, case, delete, func, or_
from sqlalchemy.orm import selectinload
from typing import List, Literal, Optional
from datetime import date, datetime, timedelta
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.permissions import (
    get_current_user,
    get_all_user_permissions,
    get_permissions_for_users,
    get_user_permission_toggles,
    get_effective_permission,
    get_user_allowed_voucher_type_ids,
    invalidate_auth_cache,
    invalidate_permissions_cache,
    clear_all_auth_and_permission_caches,
    revoke_all_user_sessions,
)
from app.core.security import get_password_hash
from app.core.sessions import (
    ACTIVE_NOW_SECONDS, add_audit, blocked_device_to_dict, current_token_hash, forget_tokens,
    live_session_conditions, revoke_sessions, session_to_dict, stale_legacy_condition, to_utc_iso, utcnow
)
from app.models.portal_core import (
    User, Role, Permission, Module, UserPermissionOverride, UserDataScope, AuditLog,
    Company, UserCompanyAccess, UserSession, BlockedDevice
)

router = APIRouter(prefix="/admin", tags=["Admin Panel"])


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
    showVouchers: bool = False
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
    voucherActionScope: str = "full"
    allowedVoucherTypeIds: Optional[List[int]] = None
    # Device sessions: devices signed in and used since tracking began, unused pre-tracking sessions
    active_devices: int = 0
    older_sessions: int = 0
    last_active_at: Optional[str] = None

class AdminUserCreate(BaseModel):
    username: str
    email: str
    password: str
    role_id: int

class AdminUserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    role_id: Optional[int] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class UserRoleUpdate(BaseModel):
    role_id: Optional[int] = None
    role: Optional[str] = None

class RolePermissionItem(BaseModel):
    module_id: int
    code: str
    name: str
    description: Optional[str] = None
    can_create: bool
    can_read: bool
    can_update: bool
    can_delete: bool

class RoleResponse(BaseModel):
    role_id: int
    name: str
    description: Optional[str] = None
    user_count: int = 0
    is_system: bool = False
    max_active_devices: Optional[int] = None
    permissions: List[RolePermissionItem] = []

class RoleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    clone_from_role_id: Optional[int] = None

class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    # Max simultaneously signed-in devices per user of this role; null or 0 = unlimited
    max_active_devices: Optional[int] = Field(None, ge=0, le=50)

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
        select(User).options(selectinload(User.role)).where(User.company_id == admin.company_id)
    )
    users = query.scalars().all()
    device_stats = await _device_stats_by_user(db, [u.user_id for u in users])
    perms_by_user = await get_permissions_for_users(users, db)

    response = []
    for u in users:
        stats = device_stats.get(u.user_id, {})
        r_name = u.role.name if u.role else "Unknown"
        user_perms = perms_by_user[u.user_id]
        toggles = user_perms["toggles"]
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
            showVouchers=toggles.get("showVouchers", toggles["showReceipts"]),
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
            voucherActionScope=user_perms["voucher_action_scope"],
            allowedVoucherTypeIds=user_perms["allowed_voucher_type_ids"],
            active_devices=stats.get("active_devices", 0),
            older_sessions=stats.get("older_sessions", 0),
            last_active_at=stats.get("last_active_at"),
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
    
    # Ensure default company access
    access = UserCompanyAccess(user_id=user.user_id, company_id=user.company_id)
    db.add(access)
    await db.commit()
    
    user_perms = await get_all_user_permissions(user.user_id, user.role_id, role.name, db)
    toggles = user_perms["toggles"]
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
        showVouchers=toggles.get("showVouchers", toggles["showReceipts"]),
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
        voucherActionScope=user_perms["voucher_action_scope"],
        allowedVoucherTypeIds=user_perms["allowed_voucher_type_ids"],
    )


@router.put("/users/{user_id}", response_model=AdminUserResponse)
async def update_user(
    user_id: int,
    payload: AdminUserUpdate,
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

    # 1. Update email if changed
    if payload.email is not None and payload.email.strip():
        new_email = payload.email.strip().lower()
        if new_email != user.email.lower():
            exists_q = await db.execute(
                select(User).where(User.email == new_email, User.user_id != user_id)
            )
            if exists_q.scalars().first():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="A user with this email address already exists."
                )
            user.email = new_email

    # 2. Update username if changed
    if payload.username is not None and payload.username.strip():
        user.username = payload.username.strip()

    # 3. Update role_id if changed
    if payload.role_id is not None and payload.role_id != user.role_id:
        if user_id == admin.user_id:
            target_role_q = await db.execute(select(Role).where(Role.role_id == payload.role_id))
            target_role = target_role_q.scalars().first()
            if not target_role or target_role.name.lower() not in ("admin", "superadmin", "owner"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="You cannot remove your own administrator role."
                )
            user.role_id = payload.role_id
        else:
            role_check = (await db.execute(select(Role).where(Role.role_id == payload.role_id))).scalars().first()
            if not role_check:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Selected role does not exist."
                )
            user.role_id = payload.role_id

    # 4. Update active status if changed
    if payload.is_active is not None:
        if user_id == admin.user_id and not payload.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot deactivate your own administrator account."
            )
        user.is_active = payload.is_active

    # 5. Update password if provided
    password_changed = False
    if payload.password and payload.password.strip():
        if len(payload.password.strip()) < 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 6 characters long."
            )
        user.password_hash = get_password_hash(payload.password.strip())
        password_changed = True

    # A new password or deactivation must log the user out everywhere, including old tokens
    credentials_revoked = password_changed or payload.is_active is False
    if credentials_revoked:
        await revoke_all_user_sessions(
            user.user_id, db,
            reason="deactivated" if payload.is_active is False else "password_change",
            by_user_id=admin.user_id,
        )

    await db.commit()
    await db.refresh(user)
    if credentials_revoked:
        invalidate_auth_cache(user_id=user.user_id)

    # Fetch role info for response
    role_q = await db.execute(select(Role).where(Role.role_id == user.role_id))
    role = role_q.scalars().first()
    r_name = role.name if role else "Unknown"
    user_perms = await get_all_user_permissions(user.user_id, user.role_id, r_name, db)
    toggles = user_perms["toggles"]

    return AdminUserResponse(
        user_id=user.user_id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        role_id=user.role_id,
        role_name=r_name,
        showLedger=toggles["showLedger"],
        showSalesLedgers=toggles["showSalesLedgers"],
        showPurchaseLedgers=toggles["showPurchaseLedgers"],
        showVouchers=toggles.get("showVouchers", toggles["showReceipts"]),
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
        voucherActionScope=user_perms["voucher_action_scope"],
        allowedVoucherTypeIds=user_perms["allowed_voucher_type_ids"],
    )

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    if user_id == admin.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own administrator account."
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
    await db.delete(user)
    await db.commit()
    return {"success": True, "message": f"User {user.username} deleted successfully."}


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
    await revoke_all_user_sessions(user_id, db, reason="password_change", by_user_id=admin.user_id)
    await db.commit()
    invalidate_auth_cache(user_id=user_id)
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
    invalidate_auth_cache(user_id=user_id)
    invalidate_permissions_cache(user_id=user_id)
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

    # Eagerly load all modules and permissions for all roles
    all_mods = (await db.execute(select(Module).order_by(Module.module_id.asc()))).scalars().all()
    all_perms = (await db.execute(select(Permission))).scalars().all()
    perm_by_role_mod = {(p.role_id, p.module_id): p for p in all_perms}
    
    result = []
    for r in roles:
        is_sys = r.name.lower() in ("admin", "sales")
        is_adm = r.name.lower() in ("admin", "superadmin", "owner")

        role_perms = []
        for m in all_mods:
            if is_adm:
                role_perms.append(RolePermissionItem(
                    module_id=m.module_id,
                    code=m.code,
                    name=m.name,
                    description=m.description,
                    can_create=True,
                    can_read=True,
                    can_update=True,
                    can_delete=True
                ))
            else:
                p = perm_by_role_mod.get((r.role_id, m.module_id))
                role_perms.append(RolePermissionItem(
                    module_id=m.module_id,
                    code=m.code,
                    name=m.name,
                    description=m.description,
                    can_create=bool(p.can_create) if p else False,
                    can_read=bool(p.can_read) if p else False,
                    can_update=bool(p.can_update) if p else False,
                    can_delete=bool(p.can_delete) if p else False
                ))

        result.append(RoleResponse(
            role_id=r.role_id,
            name=r.name,
            description=r.description or "",
            user_count=counts.get(r.role_id, 0),
            is_system=is_sys,
            max_active_devices=r.max_active_devices,
            permissions=role_perms
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

    if "max_active_devices" in payload.model_fields_set:
        role.max_active_devices = payload.max_active_devices or None
        
    await db.commit()
    await db.refresh(role)
    
    cnt = (await db.execute(select(func.count(User.user_id)).where(User.role_id == role_id))).scalar() or 0
    return RoleResponse(
        role_id=role.role_id,
        name=role.name,
        description=role.description or "",
        user_count=cnt,
        is_system=role.name.lower() in ("admin", "sales"),
        max_active_devices=role.max_active_devices
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
    
    existing_perms = (await db.execute(
        select(Permission).where(Permission.role_id == role_id)
    )).scalars().all()
    perm_map = {p.module_id: p for p in existing_perms}
    
    result = []
    is_admin_role = role.name.lower() == "admin"
    for m in all_mods:
        p = perm_map.get(m.module_id)
        default_val = True if is_admin_role else False
        result.append(RolePermissionItem(
            module_id=m.module_id,
            code=m.code,
            name=m.name,
            description=m.description,
            can_create=bool(p.can_create) if p is not None else default_val,
            can_read=bool(p.can_read) if p is not None else default_val,
            can_update=bool(p.can_update) if p is not None else default_val,
            can_delete=bool(p.can_delete) if p is not None else default_val
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
        
    # Allow customizing permissions for all roles including Admin
        
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
            
    # Clean up stale toggle overrides for users belonging to this role for updated modules
    user_ids_q = await db.execute(select(User.user_id).where(User.role_id == role_id))
    user_ids = user_ids_q.scalars().all()
    if user_ids:
        updated_module_ids = [item.module_id for item in payload]
        await db.execute(
            delete(UserPermissionOverride).where(
                UserPermissionOverride.user_id.in_(user_ids),
                UserPermissionOverride.module_id.in_(updated_module_ids),
                UserPermissionOverride.reason.in_(["Admin Panel Toggle", "Admin Voucher Scope Configuration"])
            )
        )

    await db.commit()
    clear_all_auth_and_permission_caches()
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
            
    # Clean up stale toggle overrides for affected roles
    role_ids = list(set([item.role_id for item in payload if item.role_id]))
    if role_ids:
        user_ids_q = await db.execute(select(User.user_id).where(User.role_id.in_(role_ids)))
        user_ids = user_ids_q.scalars().all()
        if user_ids:
            updated_module_ids = list(set([item.module_id for item in payload]))
            await db.execute(
                delete(UserPermissionOverride).where(
                    UserPermissionOverride.user_id.in_(user_ids),
                    UserPermissionOverride.module_id.in_(updated_module_ids),
                    UserPermissionOverride.reason == "Admin Panel Toggle"
                )
            )

    await db.commit()
    clear_all_auth_and_permission_caches()
    return {"detail": "Permissions matrix updated successfully."}


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
    query = await db.execute(
        select(Company)
        .join(UserCompanyAccess, Company.company_id == UserCompanyAccess.company_id)
        .where(UserCompanyAccess.user_id == admin.user_id)
    )
    return query.scalars().all()

@router.get("/users/{user_id}/companies", response_model=List[int])
async def get_user_companies(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    target_user = (await db.execute(select(User).where(User.user_id == user_id))).scalars().first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found.")

    admin_companies_res = await db.execute(
        select(UserCompanyAccess.company_id).where(UserCompanyAccess.user_id == admin.user_id)
    )
    admin_company_ids = set(admin_companies_res.scalars().all())
    if target_user.company_id not in admin_company_ids:
        raise HTTPException(status_code=403, detail="You do not have access to manage this user.")

    query = await db.execute(
        select(UserCompanyAccess.company_id).where(
            UserCompanyAccess.user_id == user_id,
            UserCompanyAccess.company_id.in_(admin_company_ids)
        )
    )
    return query.scalars().all()

@router.put("/users/{user_id}/companies")
async def update_user_companies(
    user_id: int,
    payload: UserCompanyUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    target_user = (await db.execute(select(User).where(User.user_id == user_id))).scalars().first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found.")

    admin_companies_res = await db.execute(
        select(UserCompanyAccess.company_id).where(UserCompanyAccess.user_id == admin.user_id)
    )
    admin_company_ids = set(admin_companies_res.scalars().all())
    if target_user.company_id not in admin_company_ids:
        raise HTTPException(status_code=403, detail="You do not have access to manage this user.")

    for cid in payload.company_ids:
        if cid not in admin_company_ids:
            raise HTTPException(status_code=403, detail=f"You do not have access to company {cid}.")

    # Clear existing within admin's accessible companies
    if admin_company_ids:
        await db.execute(
            UserCompanyAccess.__table__.delete().where(
                UserCompanyAccess.user_id == user_id,
                UserCompanyAccess.company_id.in_(admin_company_ids)
            )
        )
    
    # Insert new
    for cid in payload.company_ids:
        access = UserCompanyAccess(user_id=user_id, company_id=cid)
        db.add(access)
        
    # Ensure target user active company_id is valid
    if payload.company_ids:
        if target_user.company_id not in payload.company_ids:
            target_user.company_id = payload.company_ids[0]

    await db.commit()
    invalidate_auth_cache(user_id=user_id)
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
    showVouchers: Optional[bool] = None
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

class VoucherScopesPayload(BaseModel):
    actionScope: str  # 'view_only' | 'can_create' | 'full'
    allowedVoucherTypeIds: Optional[List[int]] = None

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
        
    vouchers_toggle_val = payload.showVouchers if payload.showVouchers is not None else payload.showReceipts
    mapping = {
        "ledger_customer": payload.showSalesLedgers,
        "ledger_supplier": payload.showPurchaseLedgers,
        "vouchers": vouchers_toggle_val,
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

        # Master Role authority: If the master role has disabled this module (default_read == False),
        # individual user overrides cannot enable it. Clean up any stale overrides.
        if not default_read:
            ov_q = await db.execute(
                select(UserPermissionOverride).where(
                    UserPermissionOverride.user_id == user_id,
                    UserPermissionOverride.module_id == module.module_id
                )
            )
            override = ov_q.scalars().first()
            if override:
                await db.delete(override)
            continue

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
    invalidate_permissions_cache(user_id=user_id)
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
    invalidate_auth_cache(user_id=user_id)
    invalidate_permissions_cache(user_id=user_id)
    return {"success": True}

@router.put("/users/{user_id}/voucher-scopes")
async def update_user_voucher_scopes(
    user_id: int,
    payload: VoucherScopesPayload,
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

    # 1. Update action control in user_permission_overrides for module 'vouchers'
    mod_q = await db.execute(select(Module).where(Module.code == 'vouchers'))
    module = mod_q.scalars().first()
    if module:
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
                reason="Admin Voucher Scope Configuration"
            )
            db.add(override)

        if payload.actionScope == 'view_only':
            override.can_read = True
            override.can_create = False
            override.can_update = False
            override.can_delete = False
        elif payload.actionScope == 'can_create':
            override.can_read = True
            override.can_create = True
            override.can_update = False
            override.can_delete = False
        else:  # 'full'
            override.can_read = True
            override.can_create = True
            override.can_update = True
            override.can_delete = True

    # 2. Update allowed voucher types in user_data_scopes
    await db.execute(
        delete(UserDataScope).where(
            UserDataScope.user_id == user_id,
            UserDataScope.scope_type == 'VoucherType'
        )
    )
    if payload.allowedVoucherTypeIds is not None:
        for vid in payload.allowedVoucherTypeIds:
            db.add(UserDataScope(
                user_id=user_id,
                scope_type='VoucherType',
                scope_ref_id=vid
            ))

    await db.commit()
    invalidate_permissions_cache(user_id=user_id)
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
    invalidate_auth_cache(user_id=user_id)
    invalidate_permissions_cache(user_id=user_id)
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


# ─── Device sessions ─────────────────────────────────────────────────────────
# Admins only ever see and act on users of their own (active) company, like the rest of this router.

class RevokeAllSessionsRequest(BaseModel):
    keep_current: bool = True

class BlockDeviceRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=255)


async def _device_stats_by_user(db: AsyncSession, user_ids: List[int]) -> dict:
    """Per user: live devices in use, unused pre-tracking sessions, and last activity on any session."""
    if not user_ids:
        return {}
    now = utcnow()
    stale = stale_legacy_condition()
    stats = {uid: {"active_devices": 0, "older_sessions": 0, "last_active_at": None} for uid in user_ids}
    live_rows = (await db.execute(
        select(
            UserSession.user_id,
            func.sum(case((stale, 0), else_=1)),
            func.sum(case((stale, 1), else_=0)),
        )
        .where(UserSession.user_id.in_(user_ids), *live_session_conditions(now))
        .group_by(UserSession.user_id)
    )).all()
    for uid, active, older in live_rows:
        stats[uid]["active_devices"] = int(active or 0)
        stats[uid]["older_sessions"] = int(older or 0)
    last_rows = (await db.execute(
        select(UserSession.user_id, func.max(UserSession.last_active_at))
        .where(UserSession.user_id.in_(user_ids))
        .group_by(UserSession.user_id)
    )).all()
    for uid, last in last_rows:
        stats[uid]["last_active_at"] = to_utc_iso(last)
    return stats


async def _company_user(db: AsyncSession, admin: User, user_id: int) -> User:
    user = (await db.execute(
        select(User).where(User.user_id == user_id, User.company_id == admin.company_id)
    )).scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return user


async def _company_session(db: AsyncSession, admin: User, session_id: int):
    row = (await db.execute(
        select(UserSession, User)
        .join(User, User.user_id == UserSession.user_id)
        .where(UserSession.session_id == session_id, User.company_id == admin.company_id)
    )).first()
    if not row:
        raise HTTPException(status_code=404, detail="Device session not found.")
    return row[0], row[1]


async def _blocked_device_ids(db: AsyncSession, user_ids: List[int]) -> dict:
    if not user_ids:
        return {}
    rows = (await db.execute(
        select(BlockedDevice.user_id, BlockedDevice.device_id).where(BlockedDevice.user_id.in_(user_ids))
    )).all()
    blocked: dict = {}
    for uid, device_id in rows:
        blocked.setdefault(uid, set()).add(device_id)
    return blocked


@router.get("/users/{user_id}/sessions")
async def list_user_sessions(
    user_id: int,
    request: Request,
    status_filter: Literal["active", "all"] = Query("active", alias="status"),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """A user's devices: signed-in ones (status=active) or the full history including signed-out ones."""
    target = await _company_user(db, admin, user_id)
    now = utcnow()
    query = select(UserSession).where(UserSession.user_id == target.user_id)
    if status_filter == "active":
        query = query.where(*live_session_conditions(now))
    query = query.order_by(
        case((UserSession.revoked_at.is_(None), 0), else_=1),
        func.coalesce(UserSession.last_active_at, UserSession.created_at).desc(),
    ).limit(limit)
    sessions = (await db.execute(query)).scalars().all()
    blocked = (await _blocked_device_ids(db, [target.user_id])).get(target.user_id, set())
    current = current_token_hash(request)
    return [
        session_to_dict(s, current_token_hash=current, blocked_device_ids=blocked, username=target.username, now=now)
        for s in sessions
    ]


@router.post("/sessions/{session_id}/revoke")
async def admin_revoke_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Sign out one device. Its next request gets 401 with X-Auth-Reason: admin_revoke."""
    session, target = await _company_session(db, admin, session_id)
    revoked = await revoke_sessions(db, reason="admin_revoke", session_ids=[session.session_id], by_user_id=admin.user_id)
    if revoked:
        add_audit(db, company_id=admin.company_id, actor_id=admin.user_id, action="SESSION_REVOKE",
                  entity_type="UserSession", entity_id=session.session_id,
                  new_value={"user_id": target.user_id, "device_name": session.device_name, "device_id": session.device_id})
    await db.commit()
    forget_tokens(revoked)
    return {"revoked": len(revoked)}


@router.post("/users/{user_id}/sessions/revoke-all")
async def admin_revoke_all_sessions(
    user_id: int,
    request: Request,
    payload: Optional[RevokeAllSessionsRequest] = None,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Sign out every device of a user. Admins acting on themselves keep the current session by default."""
    target = await _company_user(db, admin, user_id)
    keep_current = payload.keep_current if payload else True
    exclude: List[int] = []
    if keep_current and target.user_id == admin.user_id:
        exclude = list((await db.execute(
            select(UserSession.session_id).where(
                UserSession.user_id == admin.user_id, UserSession.token_hash == current_token_hash(request)
            )
        )).scalars().all())
    revoked = await revoke_sessions(db, reason="admin_revoke_all", user_id=target.user_id,
                                    by_user_id=admin.user_id, exclude_session_ids=exclude)
    if revoked:
        add_audit(db, company_id=admin.company_id, actor_id=admin.user_id, action="SESSION_REVOKE_ALL",
                  entity_type="User", entity_id=target.user_id, new_value={"revoked": len(revoked)})
    await db.commit()
    forget_tokens(revoked)
    return {"revoked": len(revoked)}


@router.get("/sessions")
async def list_company_sessions(
    request: Request,
    user_id: Optional[int] = None,
    client_type: Optional[str] = Query(None, max_length=20),
    device_type: Optional[str] = Query(None, max_length=20),
    q: Optional[str] = Query(None, max_length=100),
    active_now: bool = False,
    include_older: bool = False,
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Every signed-in device in the admin's company, with a summary for the Active Devices tab.
    Unused pre-tracking sessions are left out unless include_older=true."""
    now = utcnow()
    stale = stale_legacy_condition()
    active_cutoff = now - timedelta(seconds=ACTIVE_NOW_SECONDS)
    base = [User.company_id == admin.company_id, *live_session_conditions(now)]

    in_use = ~stale
    summary_row = (await db.execute(
        select(
            func.sum(case((in_use, 1), else_=0)),
            func.sum(case((and_(in_use, UserSession.last_active_at >= active_cutoff), 1), else_=0)),
            func.sum(case((and_(in_use, UserSession.device_type == "mobile"), 1), else_=0)),
            func.sum(case((and_(in_use, UserSession.device_type == "tablet"), 1), else_=0)),
            func.sum(case((and_(in_use, UserSession.device_type == "desktop", UserSession.client_type != "sync-agent"), 1), else_=0)),
            func.sum(case((and_(in_use, UserSession.client_type == "sync-agent"), 1), else_=0)),
            func.sum(case((stale, 1), else_=0)),
        )
        .select_from(UserSession)
        .join(User, User.user_id == UserSession.user_id)
        .where(*base)
    )).first()
    keys = ("total", "active_now", "mobile", "tablet", "desktop", "sync_agent", "older_sessions")
    summary = {k: int(v or 0) for k, v in zip(keys, summary_row or ())}

    conditions = list(base)
    if not include_older:
        conditions.append(in_use)
    if user_id is not None:
        conditions.append(UserSession.user_id == user_id)
    if client_type:
        conditions.append(UserSession.client_type == client_type)
    if device_type:
        conditions.append(UserSession.device_type == device_type)
    if active_now:
        conditions.append(UserSession.last_active_at >= active_cutoff)
    if q:
        like = f"%{q.strip()}%"
        conditions.append(or_(
            User.username.ilike(like), User.email.ilike(like),
            UserSession.device_name.ilike(like), UserSession.ip_address.ilike(like),
        ))

    rows = (await db.execute(
        select(UserSession, User.username)
        .join(User, User.user_id == UserSession.user_id)
        .where(*conditions)
        .order_by(func.coalesce(UserSession.last_active_at, UserSession.created_at).desc())
        .offset(offset)
        .limit(limit)
    )).all()
    blocked = await _blocked_device_ids(db, list({s.user_id for s, _ in rows}))
    current = current_token_hash(request)
    return {
        "summary": summary,
        "sessions": [
            session_to_dict(s, current_token_hash=current, blocked_device_ids=blocked.get(s.user_id, set()),
                            username=username, now=now)
            for s, username in rows
        ],
    }


@router.post("/sessions/{session_id}/block")
async def admin_block_device(
    session_id: int,
    request: Request,
    payload: Optional[BlockDeviceRequest] = None,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Sign out this device and stop it signing in again as this user (until unblocked)."""
    session, target = await _company_session(db, admin, session_id)
    if not session.device_id:
        raise HTTPException(
            status_code=409,
            detail="This device signed in before device tracking, so it can't be identified for blocking. Sign it out instead.",
        )
    if session.token_hash == current_token_hash(request):
        raise HTTPException(status_code=400, detail="You can't block the device you're using right now.")

    blocked = (await db.execute(
        select(BlockedDevice).where(BlockedDevice.user_id == target.user_id, BlockedDevice.device_id == session.device_id)
    )).scalars().first()
    if not blocked:
        blocked = BlockedDevice(
            company_id=admin.company_id,
            user_id=target.user_id,
            device_id=session.device_id,
            device_name=session.device_name,
            client_type=session.client_type,
            device_type=session.device_type,
            reason=(payload.reason.strip() or None) if payload and payload.reason else None,
            blocked_by_user_id=admin.user_id,
            created_at=utcnow(),
        )
        db.add(blocked)
        await db.flush()
    revoked = await revoke_sessions(db, reason="blocked", user_id=target.user_id, device_id=session.device_id,
                                    by_user_id=admin.user_id)
    add_audit(db, company_id=admin.company_id, actor_id=admin.user_id, action="DEVICE_BLOCK",
              entity_type="BlockedDevice", entity_id=blocked.blocked_device_id,
              new_value={"user_id": target.user_id, "device_id": session.device_id,
                         "device_name": session.device_name, "reason": blocked.reason})
    await db.commit()
    forget_tokens(revoked)
    return {"revoked": len(revoked), "blocked_device_id": blocked.blocked_device_id}


@router.get("/users/{user_id}/blocked-devices")
async def list_blocked_devices(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    target = await _company_user(db, admin, user_id)
    rows = (await db.execute(
        select(BlockedDevice, User.username)
        .outerjoin(User, User.user_id == BlockedDevice.blocked_by_user_id)
        .where(BlockedDevice.user_id == target.user_id)
        .order_by(BlockedDevice.created_at.desc())
    )).all()
    return [blocked_device_to_dict(b, blocked_by=name) for b, name in rows]


@router.delete("/blocked-devices/{blocked_device_id}", status_code=204)
async def unblock_device(
    blocked_device_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    blocked = (await db.execute(
        select(BlockedDevice).where(
            BlockedDevice.blocked_device_id == blocked_device_id,
            BlockedDevice.company_id == admin.company_id,
        )
    )).scalars().first()
    if not blocked:
        raise HTTPException(status_code=404, detail="Blocked device not found.")
    add_audit(db, company_id=admin.company_id, actor_id=admin.user_id, action="DEVICE_UNBLOCK",
              entity_type="BlockedDevice", entity_id=blocked.blocked_device_id,
              new_value={"user_id": blocked.user_id, "device_id": blocked.device_id, "device_name": blocked.device_name})
    await db.delete(blocked)
    await db.commit()

