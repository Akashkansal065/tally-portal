"""
platform_admins.py – Platform Operator Directory & Access Management Router.

Implements Plan Section 4.2 & Section 5.1:
  • GET /platform/admins – List operators with assigned roles, rank & security state
  • GET /platform/admins/{admin_id} – Single operator detail with effective permissions
  • POST /platform/admins – Create / invite operator (rank check, cannot grant what you lack)
  • PATCH /platform/admins/{admin_id} – Update operator status/allowlist (self-mod guard, rank check, last super-admin guard)
  • PUT /platform/admins/{admin_id}/roles – Assign roles (step-up, rank check, cannot grant what you lack, last super-admin guard)
  • POST /platform/admins/{admin_id}/reset-passkeys – Clear passkeys for locked operator
  • DELETE /platform/admins/{admin_id}/sessions – Revoke all sessions of an operator
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.platform_audit import write_platform_audit_log
from app.core.platform_dependencies import (
    PlatformAdminContext,
    current_admin,
    get_effective_operator_permissions,
    parse_if_match_version,
    require_platform_permission,
    utc_now,
)
from app.core.security import get_password_hash
from app.models.platform import (
    PlatformAdmin,
    PlatformAdminRole,
    PlatformAdminSession,
    PlatformAdminWebAuthnCredential,
    PlatformPermission,
    PlatformRole,
    PlatformRolePermission,
)

router = APIRouter(prefix="/platform/admins", tags=["Platform Operators (Admins)"])


# ─────────────────────────────────────────────────────────────────────────────
# PYDANTIC SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class AdminAssignedRoleItem(BaseModel):
    role_id: int
    code: str
    name: str
    rank: int
    scope_account_ids: Optional[List[int]] = None
    expires_at: Optional[datetime] = None


class PlatformAdminListItem(BaseModel):
    admin_id: int
    email: str
    full_name: str
    status: str
    failed_logins: int
    locked_until: Optional[datetime] = None
    max_rank: int = 0
    roles: List[AdminAssignedRoleItem] = []
    allowed_ip_cidrs: Optional[List[str]] = None
    last_login_at: Optional[datetime] = None
    last_login_ip: Optional[str] = None
    created_at: Optional[datetime] = None
    version: int


class PlatformAdminDetailResponse(BaseModel):
    admin_id: int
    email: str
    full_name: str
    status: str
    failed_logins: int
    locked_until: Optional[datetime] = None
    permission_version: int
    max_rank: int = 0
    roles: List[AdminAssignedRoleItem] = []
    effective_permissions: List[str] = []
    allowed_ip_cidrs: Optional[List[str]] = None
    last_login_at: Optional[datetime] = None
    last_login_ip: Optional[str] = None
    created_at: Optional[datetime] = None
    active_sessions_count: int = 0
    passkeys_count: int = 0
    version: int


class CreateAdminRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=120)
    password: str = Field(..., min_length=14, max_length=128)
    role_ids: List[int] = Field(default_factory=list)
    allowed_ip_cidrs: Optional[List[str]] = None
    status: str = Field("active", pattern="^(invited|active)$")
    reason: Optional[str] = Field(None, max_length=500)


class UpdateAdminRequest(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=120)
    status: Optional[str] = Field(None, pattern="^(active|suspended|disabled)$")
    allowed_ip_cidrs: Optional[List[str]] = None
    unlock: Optional[bool] = None
    version: Optional[int] = None
    reason: Optional[str] = Field(None, max_length=500)


class AssignAdminRolesRequest(BaseModel):
    role_ids: List[int] = Field(default_factory=list)
    scope_account_ids: Optional[List[int]] = None
    version: Optional[int] = None
    reason: Optional[str] = Field(None, max_length=500)


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: OPERATOR MAX RANK & SUPERADMIN CHECK
# ─────────────────────────────────────────────────────────────────────────────

async def _get_operator_rank(db: AsyncSession, admin_id: int) -> int:
    """Calculates highest rank of active roles for an operator."""
    now = utc_now()
    stmt = (
        select(func.coalesce(func.max(PlatformRole.rank), 0))
        .join(PlatformAdminRole, PlatformAdminRole.role_id == PlatformRole.role_id)
        .where(
            PlatformAdminRole.admin_id == admin_id,
            (PlatformAdminRole.expires_at == None) | (PlatformAdminRole.expires_at > now),  # noqa: E711
        )
    )
    res = await db.execute(stmt)
    return res.scalar() or 0


async def _count_active_super_admins(db: AsyncSession) -> int:
    """Counts active operators who possess the super_admin role."""
    super_role = (await db.execute(select(PlatformRole).where(PlatformRole.code == "super_admin"))).scalars().first()
    if not super_role:
        return 0
    now = utc_now()
    stmt = (
        select(func.count(PlatformAdmin.admin_id.distinct()))
        .join(PlatformAdminRole, PlatformAdminRole.admin_id == PlatformAdmin.admin_id)
        .where(
            PlatformAdminRole.role_id == super_role.role_id,
            PlatformAdmin.status == "active",
            (PlatformAdminRole.expires_at == None) | (PlatformAdminRole.expires_at > now),  # noqa: E711
        )
    )
    res = await db.execute(stmt)
    return res.scalar() or 0


# ─────────────────────────────────────────────────────────────────────────────
# 1. LIST OPERATORS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("", response_model=List[PlatformAdminListItem])
async def list_admins(
    ctx: PlatformAdminContext = Depends(require_platform_permission("admins.read")),
    db: AsyncSession = Depends(get_db),
):
    """
    List platform operators with their roles and status.
    """
    admins_stmt = select(PlatformAdmin).order_by(PlatformAdmin.admin_id.asc())
    admins_res = await db.execute(admins_stmt)
    admins = admins_res.scalars().all()

    # Load all roles assignments
    now = utc_now()
    roles_stmt = (
        select(PlatformAdminRole, PlatformRole)
        .join(PlatformRole, PlatformAdminRole.role_id == PlatformRole.role_id)
        .where(
            (PlatformAdminRole.expires_at == None) | (PlatformAdminRole.expires_at > now),  # noqa: E711
        )
    )
    roles_res = await db.execute(roles_stmt)
    all_role_rows = roles_res.all()

    admin_roles_map: Dict[int, List[AdminAssignedRoleItem]] = {}
    for ar, r in all_role_rows:
        scopes = json.loads(ar.scope_account_ids) if ar.scope_account_ids else None
        admin_roles_map.setdefault(ar.admin_id, []).append(
            AdminAssignedRoleItem(
                role_id=r.role_id,
                code=r.code,
                name=r.name,
                rank=r.rank,
                scope_account_ids=scopes,
                expires_at=ar.expires_at,
            )
        )

    items: List[PlatformAdminListItem] = []
    for a in admins:
        assigned = admin_roles_map.get(a.admin_id, [])
        m_rank = max((r.rank for r in assigned), default=0)
        allowed_ips = json.loads(a.allowed_ip_cidrs) if a.allowed_ip_cidrs else None

        items.append(
            PlatformAdminListItem(
                admin_id=a.admin_id,
                email=a.email,
                full_name=a.full_name,
                status=a.status,
                failed_logins=a.failed_logins,
                locked_until=a.locked_until,
                max_rank=m_rank,
                roles=assigned,
                allowed_ip_cidrs=allowed_ips,
                last_login_at=a.last_login_at,
                last_login_ip=a.last_login_ip,
                created_at=a.created_at,
                version=a.version,
            )
        )

    return items


# ─────────────────────────────────────────────────────────────────────────────
# 2. GET SINGLE OPERATOR
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{admin_id}", response_model=PlatformAdminDetailResponse)
async def get_admin(
    admin_id: int,
    response: Response,
    ctx: PlatformAdminContext = Depends(require_platform_permission("admins.read")),
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed profile of a platform operator with effective permissions and ETag.
    """
    admin = (await db.execute(select(PlatformAdmin).where(PlatformAdmin.admin_id == admin_id))).scalars().first()
    if not admin:
        raise HTTPException(status_code=404, detail="Platform operator not found.")

    # Load active roles
    now = utc_now()
    roles_stmt = (
        select(PlatformAdminRole, PlatformRole)
        .join(PlatformRole, PlatformAdminRole.role_id == PlatformRole.role_id)
        .where(
            PlatformAdminRole.admin_id == admin_id,
            (PlatformAdminRole.expires_at == None) | (PlatformAdminRole.expires_at > now),  # noqa: E711
        )
    )
    roles_res = await db.execute(roles_stmt)
    assigned: List[AdminAssignedRoleItem] = []
    for ar, r in roles_res.all():
        scopes = json.loads(ar.scope_account_ids) if ar.scope_account_ids else None
        assigned.append(
            AdminAssignedRoleItem(
                role_id=r.role_id,
                code=r.code,
                name=r.name,
                rank=r.rank,
                scope_account_ids=scopes,
                expires_at=ar.expires_at,
            )
        )

    # Effective permissions
    perms, m_rank, _ = await get_effective_operator_permissions(db, admin_id)

    # Counts
    sess_count = (await db.execute(
        select(func.count(PlatformAdminSession.session_id)).where(
            PlatformAdminSession.admin_id == admin_id,
            PlatformAdminSession.revoked_at.is_(None),
            PlatformAdminSession.expires_at > now,
        )
    )).scalar() or 0

    passkeys_count = (await db.execute(
        select(func.count(PlatformAdminWebAuthnCredential.credential_pk)).where(
            PlatformAdminWebAuthnCredential.admin_id == admin_id,
        )
    )).scalar() or 0

    allowed_ips = json.loads(admin.allowed_ip_cidrs) if admin.allowed_ip_cidrs else None
    response.headers["ETag"] = f'W/"{admin.version}"'

    return PlatformAdminDetailResponse(
        admin_id=admin.admin_id,
        email=admin.email,
        full_name=admin.full_name,
        status=admin.status,
        failed_logins=admin.failed_logins,
        locked_until=admin.locked_until,
        permission_version=admin.permission_version,
        max_rank=m_rank,
        roles=assigned,
        effective_permissions=sorted(list(perms)),
        allowed_ip_cidrs=allowed_ips,
        last_login_at=admin.last_login_at,
        last_login_ip=admin.last_login_ip,
        created_at=admin.created_at,
        active_sessions_count=sess_count,
        passkeys_count=passkeys_count,
        version=admin.version,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3. CREATE OPERATOR
# ─────────────────────────────────────────────────────────────────────────────

@router.post("", response_model=PlatformAdminDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_admin(
    req: CreateAdminRequest,
    ctx: PlatformAdminContext = Depends(require_platform_permission("admins.create")),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new platform operator.
    Rules:
      - If roles are assigned, step-up authentication is required.
      - All assigned roles must have rank < current operator rank (ctx.max_rank).
      - "Cannot grant what you lack": assigner must hold all permissions of assigned roles.
    """
    if req.role_ids:
        ctx.require_step_up()

    email_clean = req.email.strip().lower()
    existing = (await db.execute(select(PlatformAdmin).where(PlatformAdmin.email == email_clean))).scalars().first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Operator email '{email_clean}' already exists.")

    # Validate roles and rank
    assigned_roles: List[PlatformRole] = []
    if req.role_ids:
        roles_stmt = select(PlatformRole).where(PlatformRole.role_id.in_(req.role_ids))
        roles_res = await db.execute(roles_stmt)
        assigned_roles = roles_res.scalars().all()
        if len(assigned_roles) != len(set(req.role_ids)):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more specified role_ids do not exist.")

        for r in assigned_roles:
            if ctx.max_rank >= 1000:
                if r.rank > ctx.max_rank:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Cannot assign role '{r.code}' (rank {r.rank}) > your own rank ({ctx.max_rank}).",
                    )
            else:
                if r.rank >= ctx.max_rank:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Cannot assign role '{r.code}' (rank {r.rank}) >= your own rank ({ctx.max_rank}).",
                    )

        # "Cannot grant what you lack"
        if ctx.max_rank < 1000 and "all" not in ctx.permissions:
            for r in assigned_roles:
                p_res = await db.execute(
                    select(PlatformPermission.code)
                    .join(PlatformRolePermission, PlatformRolePermission.permission_id == PlatformPermission.permission_id)
                    .where(PlatformRolePermission.role_id == r.role_id)
                )
                r_perms = {code for (code,) in p_res.all()}
                unheld = r_perms - ctx.permissions
                if unheld:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Cannot assign role '{r.code}' containing permission(s) you lack: {', '.join(sorted(unheld))}",
                    )

    pw_hash = get_password_hash(req.password)
    ip_json = json.dumps(req.allowed_ip_cidrs) if req.allowed_ip_cidrs else None

    new_admin = PlatformAdmin(
        email=email_clean,
        full_name=req.full_name.strip(),
        password_hash=pw_hash,
        status=req.status,
        allowed_ip_cidrs=ip_json,
        created_by=ctx.admin.admin_id,
        version=1,
    )
    db.add(new_admin)
    await db.flush()

    for r in assigned_roles:
        db.add(PlatformAdminRole(
            admin_id=new_admin.admin_id,
            role_id=r.role_id,
            assigned_by=ctx.admin.admin_id,
        ))

    await write_platform_audit_log(
        db=db,
        action_type="admins.create",
        admin_email=ctx.admin.email,
        admin_id=ctx.admin.admin_id,
        session_id=ctx.session.session_id,
        target_type="admin",
        target_id=new_admin.admin_id,
        new_values={
            "email": new_admin.email,
            "full_name": new_admin.full_name,
            "status": new_admin.status,
            "roles": [r.code for r in assigned_roles],
            "allowed_ip_cidrs": req.allowed_ip_cidrs,
        },
        reason=req.reason,
    )

    await db.commit()

    # Format return
    m_rank = max((r.rank for r in assigned_roles), default=0)
    assigned_items = [
        AdminAssignedRoleItem(role_id=r.role_id, code=r.code, name=r.name, rank=r.rank)
        for r in assigned_roles
    ]

    return PlatformAdminDetailResponse(
        admin_id=new_admin.admin_id,
        email=new_admin.email,
        full_name=new_admin.full_name,
        status=new_admin.status,
        failed_logins=0,
        locked_until=None,
        permission_version=new_admin.permission_version,
        max_rank=m_rank,
        roles=assigned_items,
        effective_permissions=[],
        allowed_ip_cidrs=req.allowed_ip_cidrs,
        last_login_at=None,
        last_login_ip=None,
        created_at=new_admin.created_at,
        active_sessions_count=0,
        passkeys_count=0,
        version=new_admin.version,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 4. UPDATE OPERATOR (Profile, Status, Lockout & IP Allowlist)
# ─────────────────────────────────────────────────────────────────────────────

@router.patch("/{admin_id}", response_model=PlatformAdminDetailResponse)
async def update_admin(
    admin_id: int,
    req: UpdateAdminRequest,
    if_match: Optional[str] = Header(None),
    ctx: PlatformAdminContext = Depends(require_platform_permission("admins.update")),
    db: AsyncSession = Depends(get_db),
):
    """
    Update operator attributes with optimistic concurrency.
    Rules:
      - Self-modification guards: cannot modify own status or IP allowlist.
      - Rank rule: target operator's rank must be strictly less than current operator's rank.
      - Last super-admin guard: cannot deactivate/suspend the sole active super-admin.
      - Status / IP changes bump permission_version and revoke target sessions immediately.
    """
    expected_version = req.version if req.version is not None else parse_if_match_version(if_match)
    if expected_version is None:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="If-Match header with current version is required.",
        )

    target = (await db.execute(select(PlatformAdmin).where(PlatformAdmin.admin_id == admin_id))).scalars().first()
    if not target:
        raise HTTPException(status_code=404, detail="Platform operator not found.")

    if target.version != expected_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Version conflict. Expected version {expected_version}, but operator is at version {target.version}.",
        )

    # Self-modification guard
    is_self = target.admin_id == ctx.admin.admin_id
    if is_self:
        if req.status is not None and req.status != target.status:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot modify your own administrative status.",
            )
        if req.allowed_ip_cidrs is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot modify your own IP allowlist.",
            )
    else:
        # Rank rule: target rank must be < current operator rank
        target_rank = await _get_operator_rank(db, admin_id)
        if ctx.max_rank >= 1000:
            if target_rank > ctx.max_rank:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Cannot modify operator with rank {target_rank} > your own rank ({ctx.max_rank}).",
                )
        else:
            if target_rank >= ctx.max_rank:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Cannot modify operator with rank {target_rank} >= your own rank ({ctx.max_rank}).",
                )

    # Last super-admin guard
    if req.status is not None and req.status != "active" and target.status == "active":
        target_rank = await _get_operator_rank(db, admin_id)
        if target_rank >= 1000:
            active_supers = await _count_active_super_admins(db)
            if active_supers <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot deactivate or suspend the sole active super_admin.",
                )

    old_values = {
        "full_name": target.full_name,
        "status": target.status,
        "allowed_ip_cidrs": target.allowed_ip_cidrs,
        "failed_logins": target.failed_logins,
        "locked_until": target.locked_until.isoformat() if target.locked_until else None,
    }
    new_values: Dict[str, Any] = {}
    security_changed = False

    if req.full_name is not None and req.full_name != target.full_name:
        target.full_name = req.full_name.strip()
        new_values["full_name"] = target.full_name

    if req.status is not None and req.status != target.status:
        target.status = req.status
        new_values["status"] = req.status
        security_changed = True

    if req.allowed_ip_cidrs is not None:
        target.allowed_ip_cidrs = json.dumps(req.allowed_ip_cidrs) if req.allowed_ip_cidrs else None
        new_values["allowed_ip_cidrs"] = req.allowed_ip_cidrs
        security_changed = True

    if req.unlock:
        target.failed_logins = 0
        target.locked_until = None
        new_values["failed_logins"] = 0
        new_values["locked_until"] = None

    target.version += 1

    if security_changed:
        target.permission_version += 1
        now = utc_now()
        sess_stmt = (
            select(PlatformAdminSession)
            .where(
                PlatformAdminSession.admin_id == admin_id,
                PlatformAdminSession.revoked_at.is_(None),
            )
        )
        sess_res = await db.execute(sess_stmt)
        for s in sess_res.scalars().all():
            s.revoked_at = now
            s.revoked_reason = "security_attributes_modified"

    await write_platform_audit_log(
        db=db,
        action_type="admins.update",
        admin_email=ctx.admin.email,
        admin_id=ctx.admin.admin_id,
        session_id=ctx.session.session_id,
        target_type="admin",
        target_id=target.admin_id,
        old_values=old_values,
        new_values=new_values,
        reason=req.reason,
    )

    await db.commit()

    return await get_admin(admin_id, Response(), ctx, db)


# ─────────────────────────────────────────────────────────────────────────────
# 5. ASSIGN ROLES TO OPERATOR
# ─────────────────────────────────────────────────────────────────────────────

@router.put("/{admin_id}/roles", response_model=PlatformAdminDetailResponse)
async def assign_admin_roles(
    admin_id: int,
    req: AssignAdminRolesRequest,
    if_match: Optional[str] = Header(None),
    ctx: PlatformAdminContext = Depends(require_platform_permission("admins.assign_roles")),
    db: AsyncSession = Depends(get_db),
):
    """
    Assign roles to a platform operator.
    Rules:
      - Requires step-up.
      - Self-modification guard: operator CANNOT modify their own roles.
      - Target operator's current rank must be < current operator rank.
      - Every assigned role must have rank < current operator rank.
      - "Cannot grant what you lack": assigner must hold all permissions of assigned roles.
      - Last super-admin guard: cannot strip super_admin from sole active super-admin.
      - Bumps permission_version and revokes target sessions immediately.
      - Account scopes are refused: the console does not yet limit what a scoped operator can reach, so a
        "scoped" role would in fact see every account.
    """
    ctx.require_step_up()
    if req.scope_account_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account-scoped roles are not supported yet: a scoped operator would still see every account.",
        )

    expected_version = req.version if req.version is not None else parse_if_match_version(if_match)
    if expected_version is None:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="If-Match header with current version is required.",
        )

    target = (await db.execute(select(PlatformAdmin).where(PlatformAdmin.admin_id == admin_id))).scalars().first()
    if not target:
        raise HTTPException(status_code=404, detail="Platform operator not found.")

    if target.version != expected_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Version conflict. Expected version {expected_version}, but operator is at version {target.version}.",
        )

    # Self-modification guard
    if target.admin_id == ctx.admin.admin_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify your own administrative roles.",
        )

    # Target operator rank rule
    target_rank = await _get_operator_rank(db, admin_id)
    if ctx.max_rank >= 1000:
        if target_rank > ctx.max_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cannot alter roles of operator with rank {target_rank} > your own rank ({ctx.max_rank}).",
            )
    else:
        if target_rank >= ctx.max_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cannot alter roles of operator with rank {target_rank} >= your own rank ({ctx.max_rank}).",
            )

    # Validate target roles
    requested_roles: List[PlatformRole] = []
    if req.role_ids:
        roles_stmt = select(PlatformRole).where(PlatformRole.role_id.in_(req.role_ids))
        roles_res = await db.execute(roles_stmt)
        requested_roles = roles_res.scalars().all()
        if len(requested_roles) != len(set(req.role_ids)):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more role_ids do not exist.")

        for r in requested_roles:
            if ctx.max_rank >= 1000:
                if r.rank > ctx.max_rank:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Cannot assign role '{r.code}' (rank {r.rank}) > your own rank ({ctx.max_rank}).",
                    )
            else:
                if r.rank >= ctx.max_rank:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Cannot assign role '{r.code}' (rank {r.rank}) >= your own rank ({ctx.max_rank}).",
                    )

        # "Cannot grant what you lack"
        if ctx.max_rank < 1000 and "all" not in ctx.permissions:
            for r in requested_roles:
                p_res = await db.execute(
                    select(PlatformPermission.code)
                    .join(PlatformRolePermission, PlatformRolePermission.permission_id == PlatformPermission.permission_id)
                    .where(PlatformRolePermission.role_id == r.role_id)
                )
                r_perms = {code for (code,) in p_res.all()}
                unheld = r_perms - ctx.permissions
                if unheld:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Cannot assign role '{r.code}' containing permission(s) you lack: {', '.join(sorted(unheld))}",
                    )

    # Last super-admin demotion check
    now = utc_now()
    curr_roles_res = await db.execute(
        select(PlatformRole.code)
        .join(PlatformAdminRole, PlatformAdminRole.role_id == PlatformRole.role_id)
        .where(
            PlatformAdminRole.admin_id == admin_id,
            (PlatformAdminRole.expires_at == None) | (PlatformAdminRole.expires_at > now),  # noqa: E711
        )
    )
    curr_role_codes = [c for (c,) in curr_roles_res.all()]
    new_role_codes = [r.code for r in requested_roles]

    if "super_admin" in curr_role_codes and "super_admin" not in new_role_codes:
        active_supers = await _count_active_super_admins(db)
        if active_supers <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot demote the sole active super_admin.",
            )

    # Sync roles
    await db.execute(delete(PlatformAdminRole).where(PlatformAdminRole.admin_id == admin_id))
    scope_json = json.dumps(req.scope_account_ids) if req.scope_account_ids else None
    for r in requested_roles:
        db.add(PlatformAdminRole(
            admin_id=admin_id,
            role_id=r.role_id,
            scope_account_ids=scope_json,
            assigned_by=ctx.admin.admin_id,
        ))

    target.permission_version += 1
    target.version += 1

    # Revoke sessions
    sess_stmt = (
        select(PlatformAdminSession)
        .where(
            PlatformAdminSession.admin_id == admin_id,
            PlatformAdminSession.revoked_at.is_(None),
        )
    )
    sess_res = await db.execute(sess_stmt)
    for s in sess_res.scalars().all():
        s.revoked_at = now
        s.revoked_reason = "roles_reassigned"

    await write_platform_audit_log(
        db=db,
        action_type="admins.assign_roles",
        admin_email=ctx.admin.email,
        admin_id=ctx.admin.admin_id,
        session_id=ctx.session.session_id,
        target_type="admin",
        target_id=admin_id,
        old_values={"roles": curr_role_codes},
        new_values={"roles": new_role_codes, "scopes": req.scope_account_ids},
        reason=req.reason,
    )

    await db.commit()

    return await get_admin(admin_id, Response(), ctx, db)


# ─────────────────────────────────────────────────────────────────────────────
# 6. RESET OPERATOR PASSKEYS (Hardware MFA Reset)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{admin_id}/reset-passkeys", status_code=status.HTTP_200_OK)
async def reset_admin_passkeys(
    admin_id: int,
    ctx: PlatformAdminContext = Depends(require_platform_permission("admins.reset_mfa")),
    db: AsyncSession = Depends(get_db),
):
    """
    Clear all registered WebAuthn credentials for an operator.
    Rules:
      - Requires step-up.
      - Self-modification guard: cannot reset own passkeys via this endpoint.
      - Target operator rank must be < current operator rank.
    """
    ctx.require_step_up()

    target = (await db.execute(select(PlatformAdmin).where(PlatformAdmin.admin_id == admin_id))).scalars().first()
    if not target:
        raise HTTPException(status_code=404, detail="Platform operator not found.")

    if target.admin_id == ctx.admin.admin_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot reset your own passkeys via this administrative endpoint. Use your profile security settings.",
        )

    target_rank = await _get_operator_rank(db, admin_id)
    if ctx.max_rank >= 1000:
        if target_rank > ctx.max_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cannot reset passkeys of operator with rank {target_rank} > your own rank ({ctx.max_rank}).",
            )
    else:
        if target_rank >= ctx.max_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cannot reset passkeys of operator with rank {target_rank} >= your own rank ({ctx.max_rank}).",
            )

    del_stmt = delete(PlatformAdminWebAuthnCredential).where(PlatformAdminWebAuthnCredential.admin_id == admin_id)
    await db.execute(del_stmt)

    await write_platform_audit_log(
        db=db,
        action_type="admins.reset_mfa",
        admin_email=ctx.admin.email,
        admin_id=ctx.admin.admin_id,
        session_id=ctx.session.session_id,
        target_type="admin",
        target_id=admin_id,
        reason=f"Passkeys cleared by administrator {ctx.admin.email}",
    )

    await db.commit()

    return {"ok": True, "status": "success", "message": f"All passkeys for operator {target.email} have been reset."}


# ─────────────────────────────────────────────────────────────────────────────
# 7. REVOKE OPERATOR SESSIONS
# ─────────────────────────────────────────────────────────────────────────────

@router.delete("/{admin_id}/sessions", status_code=status.HTTP_200_OK)
async def revoke_admin_sessions(
    admin_id: int,
    ctx: PlatformAdminContext = Depends(require_platform_permission("admins.revoke_sessions")),
    db: AsyncSession = Depends(get_db),
):
    """
    Revoke all active sessions for a target operator.
    Rules:
      - Can revoke own sessions or subordinates (target rank <= current operator rank).
    """
    target = (await db.execute(select(PlatformAdmin).where(PlatformAdmin.admin_id == admin_id))).scalars().first()
    if not target:
        raise HTTPException(status_code=404, detail="Platform operator not found.")

    if target.admin_id != ctx.admin.admin_id:
        target_rank = await _get_operator_rank(db, admin_id)
        if target_rank > ctx.max_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cannot revoke sessions of higher-ranked operator ({target_rank} > {ctx.max_rank}).",
            )

    now = utc_now()
    sess_stmt = (
        select(PlatformAdminSession)
        .where(
            PlatformAdminSession.admin_id == admin_id,
            PlatformAdminSession.revoked_at.is_(None),
        )
    )
    sess_res = await db.execute(sess_stmt)
    active_sessions = sess_res.scalars().all()
    count = len(active_sessions)
    for s in active_sessions:
        s.revoked_at = now
        s.revoked_reason = f"revoked_by_{ctx.admin.email}"

    await write_platform_audit_log(
        db=db,
        action_type="admins.revoke_sessions",
        admin_email=ctx.admin.email,
        admin_id=ctx.admin.admin_id,
        session_id=ctx.session.session_id,
        target_type="admin",
        target_id=admin_id,
        old_values={"active_sessions_revoked": count},
        reason=f"Sessions revoked by {ctx.admin.email}",
    )

    await db.commit()

    return {"ok": True, "status": "success", "revoked_count": count}


# ─────────────────────────────────────────────────────────────────────────────
# 8. DELETE OPERATOR
# ─────────────────────────────────────────────────────────────────────────────

@router.delete("/{admin_id}", status_code=status.HTTP_200_OK)
async def delete_admin(
    admin_id: int,
    ctx: PlatformAdminContext = Depends(require_platform_permission("admins.update")),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a platform operator account permanently.
    Rules:
      - Self-deletion guard: cannot delete your own administrative account.
      - Rank hierarchy rule: target rank must be < current operator rank (or <= for super_admin).
      - Last super-admin guard: cannot delete the sole active super_admin.
      - Cascades: revokes and removes all sessions, passkeys, and assigned roles.
      - Emits immutable audit log with action 'admins.delete'.
    """
    stmt = select(PlatformAdmin).where(PlatformAdmin.admin_id == admin_id)
    res = await db.execute(stmt)
    target = res.scalars().first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Platform operator not found.")

    # Self-deletion guard
    if target.admin_id == ctx.admin.admin_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete your own administrative account.",
        )

    # Rank hierarchy rule
    target_rank = await _get_operator_rank(db, admin_id)
    if ctx.max_rank >= 1000:
        if target_rank > ctx.max_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cannot delete operator with rank {target_rank} > your own rank ({ctx.max_rank}).",
            )
    else:
        if target_rank >= ctx.max_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cannot delete operator with rank {target_rank} >= your own rank ({ctx.max_rank}).",
            )

    # Last super-admin guard
    if target_rank >= 1000:
        active_supers = await _count_active_super_admins(db)
        if active_supers <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete the sole active super_admin.",
            )

    # 1. Delete associated credentials, active sessions, and assigned roles
    await db.execute(delete(PlatformAdminWebAuthnCredential).where(PlatformAdminWebAuthnCredential.admin_id == admin_id))
    await db.execute(delete(PlatformAdminSession).where(PlatformAdminSession.admin_id == admin_id))
    await db.execute(delete(PlatformAdminRole).where(PlatformAdminRole.admin_id == admin_id))

    # 2. Write audit log
    await write_platform_audit_log(
        db=db,
        action_type="admins.delete",
        admin_email=ctx.admin.email,
        admin_id=ctx.admin.admin_id,
        session_id=ctx.session.session_id,
        target_type="admin",
        target_id=target.admin_id,
        old_values={
            "email": target.email,
            "full_name": target.full_name,
            "status": target.status,
            "max_rank": target_rank,
        },
        new_values=None,
        reason=f"Operator deleted by {ctx.admin.email}",
    )

    # 3. Delete operator record
    await db.execute(delete(PlatformAdmin).where(PlatformAdmin.admin_id == admin_id))
    await db.commit()

    return {"ok": True, "status": "deleted", "message": f"Operator '{target.email}' deleted successfully."}
