"""
platform_roles.py – Platform Operator Role and Permission Management Router.

Implements Plan Section 4.2 & Section 5.1:
  • GET /platform/permissions – Complete system permission catalogue
  • GET /platform/roles – List operator roles with member counts & assigned permissions
  • GET /platform/roles/{role_id} – Single role detail with ETag
  • POST /platform/roles – Create custom role (rank < current_admin rank, cannot grant what you lack)
  • PATCH /platform/roles/{role_id} – Modify role (optimistic locking, rank rule, system role protection)
  • DELETE /platform/roles/{role_id} – Remove role (system role protection, rank rule, member check)
  • PUT /platform/roles/{role_id}/permissions – Replace permissions (bumps permission_version and revokes sessions)
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.platform_audit import write_platform_audit_log
from app.core.platform_dependencies import (
    PlatformAdminContext,
    current_admin,
    parse_if_match_version,
    require_platform_permission,
    utc_now,
)
from app.models.platform import (
    PlatformAdmin,
    PlatformAdminRole,
    PlatformAdminSession,
    PlatformPermission,
    PlatformRole,
    PlatformRolePermission,
)

router = APIRouter(prefix="/platform", tags=["Platform Roles & Permissions"])


# ─────────────────────────────────────────────────────────────────────────────
# PYDANTIC SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class PermissionItem(BaseModel):
    permission_id: int
    code: str
    resource: str
    action: str
    description: str
    is_sensitive: bool


class RoleItem(BaseModel):
    role_id: int
    code: str
    name: str
    description: Optional[str] = None
    rank: int
    is_system: bool
    version: int
    created_at: Optional[datetime] = None
    member_count: int = 0
    permissions: List[str] = []


class CreateRoleRequest(BaseModel):
    code: str = Field(..., min_length=2, max_length=50, pattern="^[a-z0-9_]+$")
    name: str = Field(..., min_length=2, max_length=80)
    description: Optional[str] = Field(None, max_length=255)
    rank: int = Field(..., ge=1, le=999)
    permission_codes: List[str] = Field(default_factory=list)
    permissions: Optional[List[str]] = None
    reason: Optional[str] = Field(None, max_length=500)


class UpdateRoleRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=80)
    description: Optional[str] = Field(None, max_length=255)
    rank: Optional[int] = Field(None, ge=1, le=999)
    version: Optional[int] = None
    reason: Optional[str] = Field(None, max_length=500)


class SetRolePermissionsRequest(BaseModel):
    permission_codes: List[str] = Field(default_factory=list)
    permissions: Optional[List[str]] = None
    version: Optional[int] = None
    reason: Optional[str] = Field(None, max_length=500)


# ─────────────────────────────────────────────────────────────────────────────
# 1. PERMISSIONS CATALOGUE
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/permissions", response_model=List[PermissionItem])
async def list_permissions(
    ctx: PlatformAdminContext = Depends(require_platform_permission("roles.read")),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the complete catalogue of platform permissions.
    """
    stmt = select(PlatformPermission).order_by(PlatformPermission.resource.asc(), PlatformPermission.code.asc())
    res = await db.execute(stmt)
    perms = res.scalars().all()
    return [
        PermissionItem(
            permission_id=p.permission_id,
            code=p.code,
            resource=p.resource,
            action=p.action,
            description=p.description,
            is_sensitive=p.is_sensitive,
        )
        for p in perms
    ]


# ─────────────────────────────────────────────────────────────────────────────
# 2. LIST ROLES
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/roles", response_model=List[RoleItem])
async def list_roles(
    ctx: PlatformAdminContext = Depends(require_platform_permission("roles.read")),
    db: AsyncSession = Depends(get_db),
):
    """
    List all platform operator roles, ordered by rank descending.
    Includes active operator counts and granted permission lists.
    """
    roles_stmt = select(PlatformRole).order_by(PlatformRole.rank.desc(), PlatformRole.role_id.asc())
    roles_res = await db.execute(roles_stmt)
    roles = roles_res.scalars().all()

    # Query member counts per role
    member_counts_stmt = (
        select(PlatformAdminRole.role_id, func.count(PlatformAdminRole.admin_id))
        .group_by(PlatformAdminRole.role_id)
    )
    counts_res = await db.execute(member_counts_stmt)
    member_map = {role_id: count for role_id, count in counts_res.all()}

    # Query assigned permissions per role
    role_perms_stmt = (
        select(PlatformRolePermission.role_id, PlatformPermission.code)
        .join(PlatformPermission, PlatformRolePermission.permission_id == PlatformPermission.permission_id)
    )
    perms_res = await db.execute(role_perms_stmt)
    perms_map: Dict[int, List[str]] = {}
    for r_id, p_code in perms_res.all():
        perms_map.setdefault(r_id, []).append(p_code)

    items: List[RoleItem] = []
    for r in roles:
        items.append(
            RoleItem(
                role_id=r.role_id,
                code=r.code,
                name=r.name,
                description=r.description,
                rank=r.rank,
                is_system=r.is_system,
                version=r.version,
                created_at=r.created_at,
                member_count=member_map.get(r.role_id, 0),
                permissions=sorted(perms_map.get(r.role_id, [])),
            )
        )

    return items


# ─────────────────────────────────────────────────────────────────────────────
# 3. GET SINGLE ROLE
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/roles/{role_id}", response_model=RoleItem)
async def get_role(
    role_id: int,
    response: Response,
    ctx: PlatformAdminContext = Depends(require_platform_permission("roles.read")),
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed role record with ETag.
    """
    role = (await db.execute(select(PlatformRole).where(PlatformRole.role_id == role_id))).scalars().first()
    if not role:
        raise HTTPException(status_code=404, detail="Platform role not found.")

    # Member count
    m_count = (await db.execute(
        select(func.count(PlatformAdminRole.admin_id)).where(PlatformAdminRole.role_id == role_id)
    )).scalar() or 0

    # Permissions
    perm_res = await db.execute(
        select(PlatformPermission.code)
        .join(PlatformRolePermission, PlatformRolePermission.permission_id == PlatformPermission.permission_id)
        .where(PlatformRolePermission.role_id == role_id)
    )
    p_codes = [code for (code,) in perm_res.all()]

    response.headers["ETag"] = f'W/"{role.version}"'

    return RoleItem(
        role_id=role.role_id,
        code=role.code,
        name=role.name,
        description=role.description,
        rank=role.rank,
        is_system=role.is_system,
        version=role.version,
        created_at=role.created_at,
        member_count=m_count,
        permissions=sorted(p_codes),
    )


# ─────────────────────────────────────────────────────────────────────────────
# 4. CREATE ROLE
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/roles", response_model=RoleItem, status_code=status.HTTP_201_CREATED)
async def create_role(
    req: CreateRoleRequest,
    ctx: PlatformAdminContext = Depends(require_platform_permission("roles.manage")),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new platform operator role.
    Rules:
      - Requires step-up (MFA freshness within 5 minutes).
      - Rank rule: rank must be strictly less than current operator's rank (ctx.max_rank).
      - "Cannot grant what you lack": all granted permissions must be held by the creator.
    """
    ctx.require_step_up()

    # Rank check
    if req.rank >= ctx.max_rank:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cannot create role with rank {req.rank} >= your own rank ({ctx.max_rank}).",
        )

    # Code uniqueness
    existing = (await db.execute(select(PlatformRole).where(PlatformRole.code == req.code))).scalars().first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Role code '{req.code}' already exists.")

    # Validate permissions exist
    requested_codes = set(req.permission_codes if req.permission_codes else (req.permissions or []))
    if requested_codes:
        perms_res = await db.execute(select(PlatformPermission).where(PlatformPermission.code.in_(requested_codes)))
        found_perms = perms_res.scalars().all()
        found_codes = {p.code for p in found_perms}
        missing_in_db = requested_codes - found_codes
        if missing_in_db:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown permission code(s): {', '.join(sorted(missing_in_db))}",
            )

        # "Cannot grant what you lack" rule
        if ctx.max_rank < 1000 and "all" not in ctx.permissions:
            unheld = requested_codes - ctx.permissions
            if unheld:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Cannot grant permission(s) you do not hold: {', '.join(sorted(unheld))}",
                )

    # Create role
    new_role = PlatformRole(
        code=req.code,
        name=req.name,
        description=req.description,
        rank=req.rank,
        is_system=False,
        version=1,
    )
    db.add(new_role)
    await db.flush()

    # Assign permissions
    if requested_codes:
        for p in found_perms:
            db.add(PlatformRolePermission(
                role_id=new_role.role_id,
                permission_id=p.permission_id,
                granted_by=ctx.admin.admin_id,
            ))

    # Audit log
    await write_platform_audit_log(
        db=db,
        action_type="roles.create",
        admin_email=ctx.admin.email,
        admin_id=ctx.admin.admin_id,
        session_id=ctx.session.session_id,
        target_type="role",
        target_id=new_role.role_id,
        new_values={
            "code": new_role.code,
            "name": new_role.name,
            "rank": new_role.rank,
            "permissions": sorted(list(requested_codes)),
        },
        reason=req.reason,
    )

    await db.commit()

    return RoleItem(
        role_id=new_role.role_id,
        code=new_role.code,
        name=new_role.name,
        description=new_role.description,
        rank=new_role.rank,
        is_system=new_role.is_system,
        version=new_role.version,
        created_at=new_role.created_at,
        member_count=0,
        permissions=sorted(list(requested_codes)),
    )


# ─────────────────────────────────────────────────────────────────────────────
# 5. UPDATE ROLE
# ─────────────────────────────────────────────────────────────────────────────

@router.patch("/roles/{role_id}", response_model=RoleItem)
async def update_role(
    role_id: int,
    req: UpdateRoleRequest,
    response: Response,
    if_match: Optional[str] = Header(None),
    ctx: PlatformAdminContext = Depends(require_platform_permission("roles.manage")),
    db: AsyncSession = Depends(get_db),
):
    """
    Update role metadata and rank with optimistic concurrency.
    Rules:
      - Requires step-up.
      - Target role rank must be < current operator rank.
      - System roles cannot have their rank altered.
      - New rank must be < current operator rank.
      - Optimistic locking: If-Match header required.
    """
    ctx.require_step_up()

    # Precondition required check
    expected_version = req.version if req.version is not None else parse_if_match_version(if_match)
    if expected_version is None:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="If-Match header with current version is required.",
        )

    role = (await db.execute(select(PlatformRole).where(PlatformRole.role_id == role_id))).scalars().first()
    if not role:
        raise HTTPException(status_code=404, detail="Platform role not found.")

    # Concurrency check
    if role.version != expected_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Version conflict. Expected version {expected_version}, but role is at version {role.version}.",
        )

    # Rank rules: cannot touch a role of equal or higher rank
    if role.rank >= ctx.max_rank:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cannot modify role '{role.code}' with rank {role.rank} >= your own rank ({ctx.max_rank}).",
        )

    old_values = {"name": role.name, "description": role.description, "rank": role.rank}
    new_values: Dict[str, Any] = {}

    if req.name is not None and req.name != role.name:
        role.name = req.name
        new_values["name"] = req.name

    if req.description is not None and req.description != role.description:
        role.description = req.description
        new_values["description"] = req.description

    rank_changed = False
    if req.rank is not None and req.rank != role.rank:
        if role.is_system:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot alter rank of system role '{role.code}'.",
            )
        if req.rank >= ctx.max_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cannot elevate role to rank {req.rank} >= your own rank ({ctx.max_rank}).",
            )
        role.rank = req.rank
        new_values["rank"] = req.rank
        rank_changed = True

    role.version += 1

    # If rank changed, bump permission_version and revoke sessions for all assigned operators
    if rank_changed:
        admin_ids_stmt = select(PlatformAdminRole.admin_id).where(PlatformAdminRole.role_id == role.role_id)
        admin_ids_res = await db.execute(admin_ids_stmt)
        affected_admin_ids = [aid for (aid,) in admin_ids_res.all()]
        if affected_admin_ids:
            admins_stmt = select(PlatformAdmin).where(PlatformAdmin.admin_id.in_(affected_admin_ids))
            admins_res = await db.execute(admins_stmt)
            for adm in admins_res.scalars().all():
                adm.permission_version += 1
            now = utc_now()
            sess_stmt = (
                select(PlatformAdminSession)
                .where(
                    PlatformAdminSession.admin_id.in_(affected_admin_ids),
                    PlatformAdminSession.revoked_at.is_(None),
                )
            )
            sess_res = await db.execute(sess_stmt)
            for sess in sess_res.scalars().all():
                sess.revoked_at = now
                sess.revoked_reason = "role_rank_modified"

    # Audit log
    await write_platform_audit_log(
        db=db,
        action_type="roles.update",
        admin_email=ctx.admin.email,
        admin_id=ctx.admin.admin_id,
        session_id=ctx.session.session_id,
        target_type="role",
        target_id=role.role_id,
        old_values=old_values,
        new_values=new_values,
        reason=req.reason,
    )

    await db.commit()

    # Return updated role
    m_count = (await db.execute(
        select(func.count(PlatformAdminRole.admin_id)).where(PlatformAdminRole.role_id == role.role_id)
    )).scalar() or 0
    perm_res = await db.execute(
        select(PlatformPermission.code)
        .join(PlatformRolePermission, PlatformRolePermission.permission_id == PlatformPermission.permission_id)
        .where(PlatformRolePermission.role_id == role.role_id)
    )
    p_codes = [code for (code,) in perm_res.all()]
    response.headers["ETag"] = f'"{role.version}"'

    return RoleItem(
        role_id=role.role_id,
        code=role.code,
        name=role.name,
        description=role.description,
        rank=role.rank,
        is_system=role.is_system,
        version=role.version,
        created_at=role.created_at,
        member_count=m_count,
        permissions=sorted(p_codes),
    )


# ─────────────────────────────────────────────────────────────────────────────
# 6. DELETE ROLE
# ─────────────────────────────────────────────────────────────────────────────

@router.delete("/roles/{role_id}", status_code=status.HTTP_200_OK)
async def delete_role(
    role_id: int,
    ctx: PlatformAdminContext = Depends(require_platform_permission("roles.manage")),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a platform role.
    Rules:
      - Requires step-up.
      - System roles cannot be deleted.
      - Role rank must be < current operator rank.
      - Cannot delete role if assigned to any operators.
    """
    ctx.require_step_up()

    role = (await db.execute(select(PlatformRole).where(PlatformRole.role_id == role_id))).scalars().first()
    if not role:
        raise HTTPException(status_code=404, detail="Platform role not found.")

    if role.is_system:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"System role '{role.code}' cannot be deleted.",
        )

    if role.rank >= ctx.max_rank:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cannot delete role with rank {role.rank} >= your own rank ({ctx.max_rank}).",
        )

    # Member check
    m_count = (await db.execute(
        select(func.count(PlatformAdminRole.admin_id)).where(PlatformAdminRole.role_id == role_id)
    )).scalar() or 0
    if m_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete role '{role.code}' because it is assigned to {m_count} operator(s). Remove assignments first.",
        )

    role_code = role.code
    role_name = role.name
    await db.delete(role)

    await write_platform_audit_log(
        db=db,
        action_type="roles.delete",
        admin_email=ctx.admin.email,
        admin_id=ctx.admin.admin_id,
        session_id=ctx.session.session_id,
        target_type="role",
        target_id=role_id,
        old_values={"code": role_code, "name": role_name},
        reason=f"Role '{role_code}' deleted by operator",
    )

    await db.commit()

    return {"ok": True, "status": "deleted", "role_id": role_id, "code": role_code}


# ─────────────────────────────────────────────────────────────────────────────
# 7. SET ROLE PERMISSIONS (Synchronize & Revoke Sessions)
# ─────────────────────────────────────────────────────────────────────────────

@router.put("/roles/{role_id}/permissions", response_model=RoleItem)
async def set_role_permissions(
    role_id: int,
    req: SetRolePermissionsRequest,
    if_match: Optional[str] = Header(None),
    ctx: PlatformAdminContext = Depends(require_platform_permission("roles.manage")),
    db: AsyncSession = Depends(get_db),
):
    """
    Set permissions for a role.
    Rules:
      - Requires step-up.
      - Role rank must be < current operator rank.
      - Cannot strip permissions from super_admin.
      - "Cannot grant what you lack": newly granted permissions must be held by assigner.
      - Any permission update bumps permission_version for all assigned operators
        and revokes their active sessions immediately.
    """
    ctx.require_step_up()

    expected_version = req.version if req.version is not None else parse_if_match_version(if_match)
    if expected_version is None:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="If-Match header with current version is required.",
        )

    role = (await db.execute(select(PlatformRole).where(PlatformRole.role_id == role_id))).scalars().first()
    if not role:
        raise HTTPException(status_code=404, detail="Platform role not found.")

    if role.version != expected_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Version conflict. Expected version {expected_version}, but role is at version {role.version}.",
        )

    if role.code == "super_admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify permissions of super_admin role.",
        )

    if role.rank >= ctx.max_rank:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cannot modify permissions of role with rank {role.rank} >= your own rank ({ctx.max_rank}).",
        )

    requested_codes = set(req.permission_codes if req.permission_codes else (req.permissions or []))

    # Validate permission codes exist in DB
    found_perms: List[PlatformPermission] = []
    if requested_codes:
        perms_res = await db.execute(select(PlatformPermission).where(PlatformPermission.code.in_(requested_codes)))
        found_perms = perms_res.scalars().all()
        found_codes = {p.code for p in found_perms}
        missing = requested_codes - found_codes
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown permission code(s): {', '.join(sorted(missing))}",
            )

        # "Cannot grant what you lack" rule
        if ctx.max_rank < 1000 and "all" not in ctx.permissions:
            unheld = requested_codes - ctx.permissions
            if unheld:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Cannot grant permission(s) you do not hold: {', '.join(sorted(unheld))}",
                )

    # Current permissions for diff
    curr_res = await db.execute(
        select(PlatformPermission.code)
        .join(PlatformRolePermission, PlatformRolePermission.permission_id == PlatformPermission.permission_id)
        .where(PlatformRolePermission.role_id == role_id)
    )
    old_codes = sorted([code for (code,) in curr_res.all()])

    # Clear old permissions and write new ones
    await db.execute(delete(PlatformRolePermission).where(PlatformRolePermission.role_id == role_id))
    for p in found_perms:
        db.add(PlatformRolePermission(
            role_id=role_id,
            permission_id=p.permission_id,
            granted_by=ctx.admin.admin_id,
        ))

    role.version += 1

    # Revoke sessions & bump permission_version for all operators holding this role
    admin_ids_stmt = select(PlatformAdminRole.admin_id).where(PlatformAdminRole.role_id == role_id)
    admin_ids_res = await db.execute(admin_ids_stmt)
    affected_admin_ids = [aid for (aid,) in admin_ids_res.all()]
    if affected_admin_ids:
        admins_stmt = select(PlatformAdmin).where(PlatformAdmin.admin_id.in_(affected_admin_ids))
        admins_res = await db.execute(admins_stmt)
        for adm in admins_res.scalars().all():
            adm.permission_version += 1
        now = utc_now()
        sess_stmt = (
            select(PlatformAdminSession)
            .where(
                PlatformAdminSession.admin_id.in_(affected_admin_ids),
                PlatformAdminSession.revoked_at.is_(None),
            )
        )
        sess_res = await db.execute(sess_stmt)
        for sess in sess_res.scalars().all():
            sess.revoked_at = now
            sess.revoked_reason = "role_permissions_modified"

    # Audit log
    await write_platform_audit_log(
        db=db,
        action_type="roles.permissions_updated",
        admin_email=ctx.admin.email,
        admin_id=ctx.admin.admin_id,
        session_id=ctx.session.session_id,
        target_type="role",
        target_id=role_id,
        old_values={"permissions": old_codes},
        new_values={"permissions": sorted(list(requested_codes))},
        reason=req.reason,
    )

    await db.commit()

    m_count = (await db.execute(
        select(func.count(PlatformAdminRole.admin_id)).where(PlatformAdminRole.role_id == role_id)
    )).scalar() or 0

    return RoleItem(
        role_id=role.role_id,
        code=role.code,
        name=role.name,
        description=role.description,
        rank=role.rank,
        is_system=role.is_system,
        version=role.version,
        created_at=role.created_at,
        member_count=m_count,
        permissions=sorted(list(requested_codes)),
    )
