"""
platform_users.py – Operator Customer User CRUD & Lifecycle Router for MyTally Console.

Implements Plan Section 3 & Section 4.2:
  - Cursor-based key pagination on indexed columns (never slow offsets).
  - PII masking driven by `users.read_pii` permission (email/phone redacted).
  - Audited PII viewing (`users.pii_viewed`).
  - Strict optimistic concurrency control (version checks, If-Match header / 409 conflict).
  - Last Admin protection (cannot delete or demote the last active Admin of an account).
  - Suspend, reinstate, unlock, session revocation, soft delete and restore.
  - Password reset with temporary password (requires step-up) or link modes.
  - Transaction-bound audit log entries for every mutation.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.datetime_utils import get_ist_now
from app.core.permissions import invalidate_auth_cache, invalidate_permissions_cache
from app.core.platform_audit import write_platform_audit_log
from app.core.platform_dependencies import PlatformAdminContext, require_platform_permission
from app.core.platform_security import hash_password, utc_now
from app.core.security import ALGORITHM
from app.models.platform import (
    PlatformAdmin,
    PlatformImpersonationSession,
    PlatformPurgeRequest,
    PlatformRetentionPolicy,
)
from app.models.portal_core import (
    Account,
    Company,
    Role,
    User,
    UserCompanyAccess,
    UserPermissionOverride,
    UserPhone,
    UserSession,
)
from app.services.billing.entitlements import get_entitlements

router = APIRouter(
    prefix="/platform/users",
    tags=["Platform Customer Users"],
)


# ─────────────────────────────────────────────────────────────────────────────
# PII MASKING HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def mask_email(email: str) -> str:
    """Masks email like a•••••@gmail.com."""
    if not email or "@" not in email:
        return "••••"
    user_part, domain_part = email.split("@", 1)
    if len(user_part) <= 1:
        masked_user = user_part + "••••"
    else:
        masked_user = user_part[0] + "•" * (len(user_part) - 1)
    return f"{masked_user}@{domain_part}"


def mask_phone(phone: Optional[str]) -> Optional[str]:
    """Masks phone like ••••••4321."""
    if not phone:
        return None
    clean = phone.strip()
    if len(clean) <= 4:
        return "••••"
    return "•" * (len(clean) - 4) + clean[-4:]


def generate_temp_password(length: int = 16) -> str:
    """Generates a high-entropy random temporary password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


# ─────────────────────────────────────────────────────────────────────────────
# CURSOR ENCODING / DECODING
# ─────────────────────────────────────────────────────────────────────────────

def encode_cursor(sort_val: Any, user_id: int) -> str:
    payload = {
        "val": sort_val.isoformat() if isinstance(sort_val, datetime) else str(sort_val),
        "id": user_id,
    }
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()


def decode_cursor(cursor_str: str) -> Optional[Dict[str, Any]]:
    try:
        raw = base64.urlsafe_b64decode(cursor_str.encode()).decode()
        return json.loads(raw)
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# PYDANTIC SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class UserListItem(BaseModel):
    user_id: int
    account_id: Optional[int]
    company_id: int
    company_name: Optional[str] = None
    role_id: int
    role_name: Optional[str] = None
    username: str
    email: str
    phone: Optional[str] = None
    designation: Optional[str] = None
    status: str
    is_active: bool
    email_verified_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    version: int


class UserListResponse(BaseModel):
    items: List[UserListItem]
    next_cursor: Optional[str] = None
    has_more: bool
    approx_count: Optional[int] = None


class UserDetailResponse(BaseModel):
    user_id: int
    account_id: Optional[int]
    account_name: Optional[str] = None
    company_id: int
    company_name: Optional[str] = None
    role_id: int
    role_name: Optional[str] = None
    username: str
    email: str
    phone: Optional[str] = None
    alternate_phone: Optional[str] = None
    employee_code: Optional[str] = None
    designation: Optional[str] = None
    status: str
    suspended_at: Optional[datetime] = None
    suspended_reason: Optional[str] = None
    must_change_password: bool
    temp_password_expires: Optional[datetime] = None
    is_active: bool
    email_verified_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    deleted_by_admin_id: Optional[int] = None
    purge_after: Optional[datetime] = None
    purged_at: Optional[datetime] = None
    active_sessions_count: int = 0
    version: int


class CreatePurgeRequestPayload(BaseModel):
    reason: str = Field(..., min_length=5, max_length=500, description="Mandatory reason for user hard-delete / purge")


class RejectPurgeRequestPayload(BaseModel):
    rejection_reason: str = Field(..., min_length=5, max_length=500, description="Reason for rejecting the purge request")


class PurgeRequestItem(BaseModel):
    purge_request_id: int
    target_user_id: int
    target_account_id: Optional[int] = None
    target_email: str
    target_username: Optional[str] = None
    requested_by_admin_id: int
    requester_email: Optional[str] = None
    requested_at: datetime
    reason: str
    status: str
    approved_by_admin_id: Optional[int] = None
    approver_email: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejected_by_admin_id: Optional[int] = None
    rejected_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    executed_at: Optional[datetime] = None
    can_approve: bool = False


class ImpersonateUserPayload(BaseModel):
    reason: str = Field(..., min_length=5, max_length=500, description="Mandatory audit reason for impersonation")
    minutes: int = Field(default=15, ge=5, le=60, description="Duration of impersonation window in minutes")
    write_access: bool = Field(default=False, description="Whether write mutations are permitted (requires users.impersonate_write)")


class ImpersonationSessionItem(BaseModel):
    impersonation_id: int
    admin_id: int
    admin_email: str
    target_user_id: int
    target_account_id: int
    reason: str
    duration_minutes: int
    is_write: bool
    started_at: datetime
    expires_at: datetime
    terminated_at: Optional[datetime] = None
    is_active: bool


class RetentionPolicyItem(BaseModel):
    policy_id: int
    data_category: str
    title: str
    retention_period_days: int
    legal_basis: str
    action_on_expiry: str
    description: Optional[str] = None
    updated_at: Optional[datetime] = None



class CreateUserRequest(BaseModel):
    account_id: int
    company_id: int
    role_id: int
    email: EmailStr
    username: str = Field(..., min_length=2, max_length=50)
    phone: Optional[str] = Field(None, max_length=20)
    designation: Optional[str] = Field(None, max_length=100)
    employee_code: Optional[str] = Field(None, max_length=50)
    generate_temp_password: bool = False
    verified_by_us: bool = False
    reason: Optional[str] = Field(None, max_length=500)


class UpdateUserRequest(BaseModel):
    username: Optional[str] = Field(None, min_length=2, max_length=50)
    phone: Optional[str] = Field(None, max_length=20)
    designation: Optional[str] = Field(None, max_length=100)
    employee_code: Optional[str] = Field(None, max_length=50)
    role_id: Optional[int] = None
    version: Optional[int] = None
    reason: Optional[str] = Field(None, max_length=500)


class SuspendRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


class ReinstateRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=500)


class PasswordResetRequest(BaseModel):
    mode: str = Field("temporary", pattern="^(temporary|link)$")
    reason: Optional[str] = Field(None, max_length=500)


class UserMetaLookupsResponse(BaseModel):
    accounts: List[Dict[str, Any]]
    companies: List[Dict[str, Any]]
    roles: List[Dict[str, Any]]


# ─────────────────────────────────────────────────────────────────────────────
# 1. LIST USERS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("", response_model=UserListResponse)
async def list_users(
    cursor: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    sort: str = Query("created_at", pattern="^(created_at|last_login|username)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    q: Optional[str] = None,
    account_id: Optional[int] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    role_id: Optional[int] = None,
    verified: Optional[bool] = None,
    created_from: Optional[datetime] = None,
    created_to: Optional[datetime] = None,
    include_deleted: bool = False,
    include_approx_count: bool = False,
    ctx: PlatformAdminContext = Depends(require_platform_permission("users.read")),
    db: AsyncSession = Depends(get_db),
):
    """
    List customer users with opaque cursor-based key pagination, indexed filtering,
    and automatic PII masking based on operator permissions.
    """
    can_read_pii = ctx.has_permission("users.read_pii")

    # Base query joined with Company and Role
    query = (
        select(
            User,
            Company.name.label("company_name"),
            Role.name.label("role_name"),
        )
        .outerjoin(Company, User.company_id == Company.company_id)
        .outerjoin(Role, User.role_id == Role.role_id)
    )

    # Deletion filter
    if not include_deleted:
        query = query.where(User.deleted_at.is_(None))

    # Indexed filters
    if account_id is not None:
        query = query.where(User.account_id == account_id)
    if status_filter:
        query = query.where(User.status == status_filter)
    if role_id is not None:
        query = query.where(User.role_id == role_id)
    if verified is not None:
        if verified:
            query = query.where(User.email_verified_at.is_not(None))
        else:
            query = query.where(User.email_verified_at.is_(None))
    if created_from:
        query = query.where(User.created_at >= created_from)
    if created_to:
        query = query.where(User.created_at <= created_to)

    # Search filter (anchored prefix / exact match)
    if q and q.strip():
        term = q.strip()
        if "@" in term:
            query = query.where(User.email == term.lower())
        elif term.startswith("+") or term.isdigit():
            query = query.where(or_(User.phone.like(f"{term}%"), User.phone == term))
        else:
            query = query.where(
                or_(
                    User.username.like(f"{term}%"),
                    User.email.like(f"{term}%"),
                )
            )

    # Approximate count if requested
    approx_count: Optional[int] = None
    if include_approx_count:
        count_stmt = select(func.count(User.user_id))
        if not include_deleted:
            count_stmt = count_stmt.where(User.deleted_at.is_(None))
        if account_id is not None:
            count_stmt = count_stmt.where(User.account_id == account_id)
        approx_res = await db.execute(count_stmt)
        approx_count = approx_res.scalar() or 0

    # Sort column selection
    sort_col = getattr(User, sort)

    # Apply cursor filter
    if cursor:
        decoded = decode_cursor(cursor)
        if decoded:
            c_val = decoded.get("val")
            c_id = decoded.get("id")
            if sort in ("created_at", "last_login") and c_val:
                try:
                    c_dt = datetime.fromisoformat(c_val)
                    if order == "desc":
                        query = query.where(
                            or_(
                                sort_col < c_dt,
                                (sort_col == c_dt) & (User.user_id < c_id),
                            )
                        )
                    else:
                        query = query.where(
                            or_(
                                sort_col > c_dt,
                                (sort_col == c_dt) & (User.user_id > c_id),
                            )
                        )
                except Exception:
                    pass
            elif sort == "username" and c_val:
                if order == "desc":
                    query = query.where(
                        or_(
                            sort_col < str(c_val),
                            (sort_col == str(c_val)) & (User.user_id < c_id),
                        )
                    )
                else:
                    query = query.where(
                        or_(
                            sort_col > str(c_val),
                            (sort_col == str(c_val)) & (User.user_id > c_id),
                        )
                    )

    # Ordering
    if order == "desc":
        query = query.order_by(sort_col.desc(), User.user_id.desc())
    else:
        query = query.order_by(sort_col.asc(), User.user_id.asc())

    query = query.limit(limit + 1)
    res = await db.execute(query)
    rows = res.all()

    has_more = len(rows) > limit
    results = rows[:limit]

    items: List[UserListItem] = []
    next_cursor: Optional[str] = None

    for user, comp_name, r_name in results:
        # PII Masking
        display_email = user.email if can_read_pii else mask_email(user.email)
        display_phone = user.phone if can_read_pii else mask_phone(user.phone)

        items.append(
            UserListItem(
                user_id=user.user_id,
                account_id=user.account_id,
                company_id=user.company_id,
                company_name=comp_name,
                role_id=user.role_id,
                role_name=r_name,
                username=user.username,
                email=display_email,
                phone=display_phone,
                designation=user.designation,
                status=user.status or "active",
                is_active=bool(user.is_active),
                email_verified_at=user.email_verified_at,
                created_at=user.created_at,
                last_login=user.last_login,
                deleted_at=user.deleted_at,
                version=user.version or 1,
            )
        )

    if has_more and results:
        last_u, _, _ = results[-1]
        last_val = getattr(last_u, sort)
        next_cursor = encode_cursor(last_val, last_u.user_id)

    return UserListResponse(
        items=items,
        next_cursor=next_cursor,
        has_more=has_more,
        approx_count=approx_count,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1.1 META LOOKUPS (Accounts, Companies, Roles)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/meta/lookups", response_model=UserMetaLookupsResponse)
async def get_user_meta_lookups(
    account_id: Optional[int] = None,
    ctx: PlatformAdminContext = Depends(require_platform_permission("users.read")),
    db: AsyncSession = Depends(get_db),
):
    """
    Fetch lightweight lookups for accounts, companies, and roles to populate
    filters and assignment dropdowns in the operator console.
    """
    acc_q = select(Account.account_id, Account.name, Account.status).order_by(Account.name.asc())
    comp_q = select(Company.company_id, Company.name, Company.account_id).order_by(Company.name.asc())
    role_q = select(Role.role_id, Role.name, Role.account_id).order_by(Role.name.asc())

    if account_id is not None:
        comp_q = comp_q.where(Company.account_id == account_id)
        role_q = role_q.where(or_(Role.account_id == account_id, Role.account_id.is_(None)))

    acc_rows = (await db.execute(acc_q)).all()
    comp_rows = (await db.execute(comp_q)).all()
    role_rows = (await db.execute(role_q)).all()

    return UserMetaLookupsResponse(
        accounts=[{"account_id": r.account_id, "name": r.name, "status": r.status} for r in acc_rows],
        companies=[{"company_id": r.company_id, "name": r.name, "account_id": r.account_id} for r in comp_rows],
        roles=[{"role_id": r.role_id, "name": r.name, "account_id": r.account_id} for r in role_rows],
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. GET SINGLE USER
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{user_id:int}", response_model=UserDetailResponse)
async def get_user(
    user_id: int,
    response: Response,
    ctx: PlatformAdminContext = Depends(require_platform_permission("users.read")),
    db: AsyncSession = Depends(get_db),
):
    """
    Fetch detailed user record. If operator possesses `users.read_pii`, unmasked data
    is returned and an audited entry is recorded (`users.pii_viewed`).
    Sets ETag: W/"<version>".
    """
    can_read_pii = ctx.has_permission("users.read_pii")

    res = await db.execute(
        select(
            User,
            Company.name.label("company_name"),
            Role.name.label("role_name"),
            Account.name.label("account_name"),
        )
        .outerjoin(Company, User.company_id == Company.company_id)
        .outerjoin(Role, User.role_id == Role.role_id)
        .outerjoin(Account, User.account_id == Account.account_id)
        .where(User.user_id == user_id)
    )
    row = res.first()
    if not row:
        raise HTTPException(status_code=404, detail="Customer user not found.")

    user, comp_name, r_name, acc_name = row

    now = utc_now()
    sess_res = await db.execute(
        select(func.count(UserSession.session_id)).where(
            UserSession.user_id == user_id,
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now,
        )
    )
    sess_count = sess_res.scalar() or 0

    # If unmasked PII is viewed, audit it immediately
    if can_read_pii:
        await write_platform_audit_log(
            db=db,
            action_type="users.pii_viewed",
            admin_email=ctx.admin.email,
            admin_id=ctx.admin.admin_id,
            session_id=ctx.session.session_id,
            target_type="user",
            target_id=user.user_id,
            target_account_id=user.account_id,
            target_user_id=user.user_id,
            reason="Unmasked PII view by authorized operator",
            outcome="success",
        )
        await db.commit()

    ver = user.version or 1
    response.headers["ETag"] = f'W/"{ver}"'

    display_email = user.email if can_read_pii else mask_email(user.email)
    display_phone = user.phone if can_read_pii else mask_phone(user.phone)
    display_alt_phone = user.alternate_phone if can_read_pii else mask_phone(user.alternate_phone)

    return UserDetailResponse(
        user_id=user.user_id,
        account_id=user.account_id,
        account_name=acc_name,
        company_id=user.company_id,
        company_name=comp_name,
        role_id=user.role_id,
        role_name=r_name,
        username=user.username,
        email=display_email,
        phone=display_phone,
        alternate_phone=display_alt_phone,
        employee_code=user.employee_code,
        designation=user.designation,
        status=user.status or "active",
        suspended_at=user.suspended_at,
        suspended_reason=user.suspended_reason,
        must_change_password=bool(user.must_change_password),
        temp_password_expires=user.temp_password_expires,
        is_active=bool(user.is_active),
        email_verified_at=user.email_verified_at,
        created_at=user.created_at,
        last_login=user.last_login,
        deleted_at=user.deleted_at,
        deleted_by_admin_id=user.deleted_by_admin_id,
        purge_after=user.purge_after,
        purged_at=user.purged_at,
        active_sessions_count=sess_count,
        version=ver,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3. CREATE USER
# ─────────────────────────────────────────────────────────────────────────────

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_user(
    body: CreateUserRequest,
    ctx: PlatformAdminContext = Depends(require_platform_permission("users.create")),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new customer user within an account and company.
    Validates account entitlement seats, uniqueness, and role membership.
    """
    clean_email = body.email.strip().lower()

    # 1. Uniqueness checks
    existing_user_res = await db.execute(
        select(User.user_id).where(User.email == clean_email)
    )
    if existing_user_res.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail=f"Email '{clean_email}' is already registered.",
        )

    if body.phone:
        existing_phone_res = await db.execute(
            select(User.user_id).where(User.phone == body.phone.strip())
        )
        if existing_phone_res.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail=f"Phone number '{body.phone.strip()}' is already in use.",
            )

    # 2. Account existence & Role validation
    acc_res = await db.execute(
        select(Account).where(Account.account_id == body.account_id)
    )
    acc = acc_res.scalars().first()
    if not acc:
        raise HTTPException(status_code=404, detail="Target customer account not found.")

    role_res = await db.execute(
        select(Role).where(Role.role_id == body.role_id)
    )
    role = role_res.scalars().first()
    if not role or role.account_id != body.account_id:
        raise HTTPException(
            status_code=400,
            detail="The specified role does not belong to this account.",
        )

    # 3. Subscription seats check
    entitlements = await get_entitlements(db, body.account_id)
    allowed_seats = entitlements.users_allowed
    active_users_cnt_res = await db.execute(
        select(func.count(User.user_id)).where(
            User.account_id == body.account_id,
            User.deleted_at.is_(None),
            User.is_active == True,
        )
    )
    current_seats = active_users_cnt_res.scalar() or 0

    if current_seats >= allowed_seats:
        raise HTTPException(
            status_code=400,
            detail=f"Account seat limit reached ({current_seats}/{allowed_seats} users). Upgrade plan to add more seats.",
        )

    # 4. Password handling
    temp_pwd: Optional[str] = None
    must_change = False
    temp_exp = None
    now = utc_now()

    if body.generate_temp_password:
        if not ctx.has_permission("users.reset_password"):
            raise HTTPException(
                status_code=403,
                detail="Permission 'users.reset_password' is required to generate temporary passwords.",
            )
        temp_pwd = generate_temp_password(16)
        pwd_hash = hash_password(temp_pwd)
        must_change = True
        temp_exp = now + timedelta(hours=24)
    else:
        # Generate an unusable placeholder until user sets it via invitation link
        pwd_hash = hash_password(secrets.token_urlsafe(32))

    # 5. Insert User
    new_user = User(
        account_id=body.account_id,
        company_id=body.company_id,
        role_id=body.role_id,
        username=body.username.strip(),
        email=clean_email,
        phone=body.phone.strip() if body.phone else None,
        designation=body.designation.strip() if body.designation else None,
        employee_code=body.employee_code.strip() if body.employee_code else None,
        password_hash=pwd_hash,
        status="active",
        must_change_password=must_change,
        temp_password_expires=temp_exp,
        email_verified_at=now if body.verified_by_us else None,
        is_active=True,
        version=1,
    )
    db.add(new_user)
    await db.flush()

    # 6. Write Audit Log in same transaction
    await write_platform_audit_log(
        db=db,
        action_type="users.create",
        admin_email=ctx.admin.email,
        admin_id=ctx.admin.admin_id,
        session_id=ctx.session.session_id,
        target_type="user",
        target_id=new_user.user_id,
        target_account_id=body.account_id,
        target_user_id=new_user.user_id,
        new_values={
            "username": new_user.username,
            "email": new_user.email,
            "account_id": body.account_id,
            "role_id": body.role_id,
            "has_temp_password": bool(temp_pwd),
        },
        reason=body.reason,
        outcome="success",
    )
    await db.commit()

    return {
        "status": "created",
        "user_id": new_user.user_id,
        "email": new_user.email,
        "one_time_temp_password": temp_pwd,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4. UPDATE USER (OPTIMISTIC LOCKING)
# ─────────────────────────────────────────────────────────────────────────────

@router.patch("/{user_id}")
async def update_user(
    user_id: int,
    body: UpdateUserRequest,
    if_match: Optional[str] = Header(None, alias="if-match"),
    ctx: PlatformAdminContext = Depends(require_platform_permission("users.update")),
    db: AsyncSession = Depends(get_db),
):
    """
    Update user with optimistic locking (If-Match header or body version).
    Prevents mass-assignment, verifies role ownership, and protects last admin.
    """
    res = await db.execute(select(User).where(User.user_id == user_id))
    user = res.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="Customer user not found.")

    # 1. Version enforcement
    expected_version: Optional[int] = None
    if if_match:
        clean_match = if_match.strip()
        if clean_match.startswith("W/") or clean_match.startswith("w/"):
            clean_match = clean_match[2:].strip()
        clean_match = clean_match.strip('"').strip("'").strip()
        if clean_match.isdigit():
            expected_version = int(clean_match)
    if expected_version is None and body.version is not None:
        expected_version = body.version

    if expected_version is None:
        raise HTTPException(
            status_code=428,
            detail="If-Match header or body version required for optimistic concurrency.",
        )

    current_version = user.version or 1
    if current_version != expected_version:
        raise HTTPException(
            status_code=409,
            detail=f"Conflict: Record was modified by another operator. Current version: {current_version}.",
        )

    # 2. Check role change & Last Admin rule
    old_values: Dict[str, Any] = {}
    new_values: Dict[str, Any] = {}

    if body.role_id is not None and body.role_id != user.role_id:
        new_role_res = await db.execute(
            select(Role).where(Role.role_id == body.role_id)
        )
        new_role = new_role_res.scalars().first()
        if not new_role or new_role.account_id != user.account_id:
            raise HTTPException(
                status_code=400,
                detail="New role does not belong to user's account.",
            )

        # Check if user is currently an Admin
        curr_role_res = await db.execute(select(Role).where(Role.role_id == user.role_id))
        curr_role = curr_role_res.scalars().first()
        if curr_role and curr_role.name.lower() == "admin" and new_role.name.lower() != "admin":
            # Demotion from admin: check remaining admins
            admin_roles_stmt = select(Role.role_id).where(
                Role.account_id == user.account_id,
                func.lower(Role.name) == "admin",
            )
            other_admins_cnt = await db.scalar(
                select(func.count(User.user_id)).where(
                    User.account_id == user.account_id,
                    User.role_id.in_(admin_roles_stmt),
                    User.deleted_at.is_(None),
                    User.is_active == True,
                    User.user_id != user.user_id,
                )
            ) or 0
            if other_admins_cnt == 0:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot remove the last Admin of this account. Assign another Admin first.",
                )

        old_values["role_id"] = user.role_id
        new_values["role_id"] = body.role_id
        user.role_id = body.role_id

    # 3. Update fields
    if body.username is not None and body.username.strip() != user.username:
        old_values["username"] = user.username
        new_values["username"] = body.username.strip()
        user.username = body.username.strip()

    if body.phone is not None:
        clean_phone = body.phone.strip() if body.phone else None
        if clean_phone != user.phone:
            if clean_phone:
                dup_phone = await db.scalar(
                    select(User.user_id).where(
                        User.phone == clean_phone,
                        User.user_id != user.user_id,
                    )
                )
                if dup_phone:
                    raise HTTPException(status_code=400, detail="Phone number already in use.")
            old_values["phone"] = user.phone
            new_values["phone"] = clean_phone
            user.phone = clean_phone

    if body.designation is not None and body.designation.strip() != (user.designation or ""):
        old_values["designation"] = user.designation
        new_values["designation"] = body.designation.strip()
        user.designation = body.designation.strip()

    if body.employee_code is not None and body.employee_code.strip() != (user.employee_code or ""):
        old_values["employee_code"] = user.employee_code
        new_values["employee_code"] = body.employee_code.strip()
        user.employee_code = body.employee_code.strip()

    if not new_values:
        return {"status": "unchanged", "version": current_version}

    # Increment version
    user.version = current_version + 1

    # 4. Audit
    await write_platform_audit_log(
        db=db,
        action_type="users.update",
        admin_email=ctx.admin.email,
        admin_id=ctx.admin.admin_id,
        session_id=ctx.session.session_id,
        target_type="user",
        target_id=user.user_id,
        target_account_id=user.account_id,
        target_user_id=user.user_id,
        old_values=old_values,
        new_values=new_values,
        reason=body.reason,
        outcome="success",
    )
    await db.commit()

    return {"status": "updated", "version": user.version}


# ─────────────────────────────────────────────────────────────────────────────
# 5. SUSPEND, REINSTATE, UNLOCK
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{user_id}/suspend")
async def suspend_user(
    user_id: int,
    body: SuspendRequest,
    ctx: PlatformAdminContext = Depends(require_platform_permission("users.suspend")),
    db: AsyncSession = Depends(get_db),
):
    """Suspends customer user and immediately revokes all active sessions."""
    res = await db.execute(select(User).where(User.user_id == user_id))
    user = res.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="Customer user not found.")

    now = utc_now()
    user.status = "suspended"
    user.suspended_at = now
    user.suspended_reason = body.reason
    user.version = (user.version or 1) + 1

    # Revoke sessions
    await db.execute(
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=now, revoke_reason="operator_suspended")
    )

    await write_platform_audit_log(
        db=db,
        action_type="users.suspend",
        admin_email=ctx.admin.email,
        admin_id=ctx.admin.admin_id,
        session_id=ctx.session.session_id,
        target_type="user",
        target_id=user.user_id,
        target_account_id=user.account_id,
        target_user_id=user.user_id,
        reason=body.reason,
        outcome="success",
    )
    await db.commit()
    return {"status": "suspended", "user_id": user_id}


@router.post("/{user_id}/reinstate")
async def reinstate_user(
    user_id: int,
    body: ReinstateRequest,
    ctx: PlatformAdminContext = Depends(require_platform_permission("users.suspend")),
    db: AsyncSession = Depends(get_db),
):
    """Reinstates suspended or locked customer user."""
    res = await db.execute(select(User).where(User.user_id == user_id))
    user = res.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="Customer user not found.")

    user.status = "active"
    user.suspended_at = None
    user.suspended_reason = None
    user.version = (user.version or 1) + 1

    await write_platform_audit_log(
        db=db,
        action_type="users.reinstate",
        admin_email=ctx.admin.email,
        admin_id=ctx.admin.admin_id,
        session_id=ctx.session.session_id,
        target_type="user",
        target_id=user.user_id,
        target_account_id=user.account_id,
        target_user_id=user.user_id,
        reason=body.reason,
        outcome="success",
    )
    await db.commit()
    return {"status": "active", "user_id": user_id}


@router.post("/{user_id}/unlock")
async def unlock_user(
    user_id: int,
    ctx: PlatformAdminContext = Depends(require_platform_permission("users.suspend")),
    db: AsyncSession = Depends(get_db),
):
    """Lifts brute-force lock on user."""
    res = await db.execute(select(User).where(User.user_id == user_id))
    user = res.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="Customer user not found.")

    user.status = "active"
    user.version = (user.version or 1) + 1

    await write_platform_audit_log(
        db=db,
        action_type="users.unlock",
        admin_email=ctx.admin.email,
        admin_id=ctx.admin.admin_id,
        session_id=ctx.session.session_id,
        target_type="user",
        target_id=user.user_id,
        target_account_id=user.account_id,
        target_user_id=user.user_id,
        outcome="success",
    )
    await db.commit()
    return {"status": "unlocked", "user_id": user_id}


# ─────────────────────────────────────────────────────────────────────────────
# 6. PASSWORD RESET
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{user_id}/password-reset")
async def reset_user_password(
    user_id: int,
    body: PasswordResetRequest,
    ctx: PlatformAdminContext = Depends(require_platform_permission("users.reset_password")),
    db: AsyncSession = Depends(get_db),
):
    """
    Resets user password. Temporary mode generates 16-char random password
    (requires fresh step-up check) and revokes all active sessions.
    """
    res = await db.execute(select(User).where(User.user_id == user_id))
    user = res.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="Customer user not found.")

    now = utc_now()
    # Invalidate existing user sessions immediately
    await db.execute(
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=now, revoke_reason="operator_pwd_reset")
    )

    temp_password: Optional[str] = None

    if body.mode == "temporary":
        # Step-up check required for operator issuing plain temporary password
        ctx.require_step_up(max_age_minutes=5)

        temp_password = generate_temp_password(16)
        user.password_hash = hash_password(temp_password)
        user.must_change_password = True
        user.temp_password_expires = now + timedelta(hours=24)
        user.version = (user.version or 1) + 1

    await write_platform_audit_log(
        db=db,
        action_type="users.reset_password",
        admin_email=ctx.admin.email,
        admin_id=ctx.admin.admin_id,
        session_id=ctx.session.session_id,
        target_type="user",
        target_id=user.user_id,
        target_account_id=user.account_id,
        target_user_id=user.user_id,
        new_values={"mode": body.mode},
        reason=body.reason,
        outcome="success",
    )
    await db.commit()

    return {
        "status": "success",
        "mode": body.mode,
        "one_time_temp_password": temp_password,
        "message": "Temporary password generated." if temp_password else "Password reset link sent to user.",
    }


# ─────────────────────────────────────────────────────────────────────────────
# 7. SESSIONS REVOCATION
# ─────────────────────────────────────────────────────────────────────────────

@router.delete("/{user_id}/sessions")
async def revoke_user_sessions(
    user_id: int,
    ctx: PlatformAdminContext = Depends(require_platform_permission("users.revoke_sessions")),
    db: AsyncSession = Depends(get_db),
):
    """Revokes all active sessions for a customer user."""
    res = await db.execute(select(User).where(User.user_id == user_id))
    user = res.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="Customer user not found.")

    now = utc_now()
    await db.execute(
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=now, revoke_reason="operator_revoked")
    )

    await write_platform_audit_log(
        db=db,
        action_type="users.revoke_sessions",
        admin_email=ctx.admin.email,
        admin_id=ctx.admin.admin_id,
        session_id=ctx.session.session_id,
        target_type="user",
        target_id=user.user_id,
        target_account_id=user.account_id,
        target_user_id=user.user_id,
        outcome="success",
    )
    await db.commit()
    return {"status": "sessions_revoked", "user_id": user_id}


# ─────────────────────────────────────────────────────────────────────────────
# 8. SOFT DELETE & RESTORE
# ─────────────────────────────────────────────────────────────────────────────

@router.delete("/{user_id:int}")
async def soft_delete_user(
    user_id: int,
    ctx: PlatformAdminContext = Depends(require_platform_permission("users.soft_delete")),
    db: AsyncSession = Depends(get_db),
):
    """
    Soft-deletes user (sets deleted_at, purge_after=30d, is_active=False).
    Refused if the user is the last active Admin of the account.
    """
    res = await db.execute(select(User).where(User.user_id == user_id))
    user = res.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="Customer user not found.")

    if user.deleted_at is not None:
        return {"status": "already_deleted", "user_id": user_id}

    # Check last Admin rule
    curr_role_res = await db.execute(select(Role).where(Role.role_id == user.role_id))
    curr_role = curr_role_res.scalars().first()
    if curr_role and curr_role.name.lower() == "admin":
        admin_roles_stmt = select(Role.role_id).where(
            Role.account_id == user.account_id,
            func.lower(Role.name) == "admin",
        )
        other_admins_cnt = await db.scalar(
            select(func.count(User.user_id)).where(
                User.account_id == user.account_id,
                User.role_id.in_(admin_roles_stmt),
                User.deleted_at.is_(None),
                User.is_active == True,
                User.user_id != user.user_id,
            )
        ) or 0
        if other_admins_cnt == 0:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete the last Admin of this account. Assign another Admin first.",
            )

    now = utc_now()
    user.deleted_at = now
    user.deleted_by_admin_id = ctx.admin.admin_id
    user.purge_after = now + timedelta(days=30)
    user.is_active = False
    user.version = (user.version or 1) + 1

    # Revoke sessions
    await db.execute(
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=now, revoke_reason="operator_deleted")
    )

    await write_platform_audit_log(
        db=db,
        action_type="users.soft_delete",
        admin_email=ctx.admin.email,
        admin_id=ctx.admin.admin_id,
        session_id=ctx.session.session_id,
        target_type="user",
        target_id=user.user_id,
        target_account_id=user.account_id,
        target_user_id=user.user_id,
        outcome="success",
    )
    await db.commit()
    return {"status": "soft_deleted", "user_id": user_id, "purge_after": user.purge_after}


@router.post("/{user_id}/restore")
async def restore_user(
    user_id: int,
    ctx: PlatformAdminContext = Depends(require_platform_permission("users.soft_delete")),
    db: AsyncSession = Depends(get_db),
):
    """Restores a soft-deleted user before the 30-day purge deadline."""
    res = await db.execute(select(User).where(User.user_id == user_id))
    user = res.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="Customer user not found.")

    user.deleted_at = None
    user.deleted_by_admin_id = None
    user.purge_after = None
    user.is_active = True
    user.version = (user.version or 1) + 1

    await write_platform_audit_log(
        db=db,
        action_type="users.restore",
        admin_email=ctx.admin.email,
        admin_id=ctx.admin.admin_id,
        session_id=ctx.session.session_id,
        target_type="user",
        target_id=user.user_id,
        target_account_id=user.account_id,
        target_user_id=user.user_id,
        outcome="success",
    )
    await db.commit()
    return {"status": "restored", "user_id": user_id}


# ─────────────────────────────────────────────────────────────────────────────
# 9. TWO-PERSON PURGE & HARD DELETE WORKFLOW (GDPR ANONYMISATION)
# ─────────────────────────────────────────────────────────────────────────────

async def execute_user_anonymisation(db: AsyncSession, user: User, now: datetime) -> Dict[str, Any]:
    """
    Executes irreversible GDPR personal data anonymisation (Hard Delete).
    Personal data is wiped, while accounting vouchers, ledgers, and transactions
    are strictly preserved for statutory compliance.

    Returns what was cleared for the audit log: the names of the fields that held data, never their values. An
    audit row that kept the old values would keep the very data the purge removes.
    """
    pii_fields = ("username", "email", "phone", "alternate_phone", "designation", "employee_code")
    old_state = {"cleared_fields": [f for f in pii_fields if getattr(user, f, None)]}

    # 1. Overwrite personal identifiers
    user.username = f"Deleted user {user.user_id}"
    user.email = f"purged-{user.user_id}@deleted.local"
    user.phone = None
    user.alternate_phone = None
    user.employee_code = None
    user.designation = None
    user.password_hash = "!ANONYMIZED_DO_NOT_USE!"
    user.is_active = False
    user.status = "purged"
    user.deleted_at = user.deleted_at or now
    user.purged_at = now
    user.version = (user.version or 1) + 1

    # 2. Delete outright: sessions, device registrations, phone-login rows, permission overrides, company access
    await db.execute(delete(UserSession).where(UserSession.user_id == user.user_id))
    await db.execute(delete(UserPhone).where(UserPhone.user_id == user.user_id))
    await db.execute(delete(UserPermissionOverride).where(UserPermissionOverride.user_id == user.user_id))
    await db.execute(delete(UserCompanyAccess).where(UserCompanyAccess.user_id == user.user_id))

    # 3. Clear auth and permissions caches
    invalidate_auth_cache(user_id=user.user_id)
    invalidate_permissions_cache(user.user_id)

    return old_state


@router.post("/{user_id}/purge-requests")
async def create_purge_request(
    user_id: int,
    payload: CreatePurgeRequestPayload,
    ctx: PlatformAdminContext = Depends(require_platform_permission("users.hard_delete")),
    db: AsyncSession = Depends(get_db),
):
    """
    Submits a request for irreversible user hard-delete (anonymisation).
    Requires 'users.hard_delete' + Step-Up MFA.
    Enforces the Two-Person Approval Rule: The requesting operator CANNOT approve this request.
    """
    user_res = await db.execute(select(User).where(User.user_id == user_id))
    user = user_res.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="Customer user not found.")

    if user.purged_at is not None:
        raise HTTPException(status_code=400, detail="Customer user has already been purged and personal data anonymised.")

    # Check last Admin rule
    curr_role_res = await db.execute(select(Role).where(Role.role_id == user.role_id))
    curr_role = curr_role_res.scalars().first()
    if curr_role and curr_role.name.lower() == "admin":
        admin_roles_stmt = select(Role.role_id).where(
            Role.account_id == user.account_id,
            func.lower(Role.name) == "admin",
        )
        other_admins_cnt = await db.scalar(
            select(func.count(User.user_id)).where(
                User.account_id == user.account_id,
                User.role_id.in_(admin_roles_stmt),
                User.purged_at.is_(None),
                User.is_active == True,
                User.user_id != user.user_id,
            )
        ) or 0
        if other_admins_cnt == 0:
            raise HTTPException(
                status_code=400,
                detail="Cannot purge the last Admin of this account. Assign another Admin first.",
            )

    # Check for existing pending purge request
    existing_pending = (
        await db.execute(
            select(PlatformPurgeRequest).where(
                PlatformPurgeRequest.target_user_id == user_id,
                PlatformPurgeRequest.status == "pending",
            )
        )
    ).scalars().first()
    if existing_pending:
        raise HTTPException(
            status_code=409,
            detail=f"A purge request is already pending for this user (Request #{existing_pending.purge_request_id}).",
        )

    now = utc_now()
    purge_req = PlatformPurgeRequest(
        target_user_id=user.user_id,
        target_account_id=user.account_id,
        target_email_snapshot=user.email,
        target_username_snapshot=user.username,
        requested_by_admin_id=ctx.admin.admin_id,
        requested_at=now,
        reason=payload.reason,
        status="pending",
    )
    db.add(purge_req)
    await db.flush()

    await write_platform_audit_log(
        db=db,
        action_type="users.purge_requested",
        admin_email=ctx.admin.email,
        admin_id=ctx.admin.admin_id,
        session_id=ctx.session.session_id,
        target_type="user",
        target_id=user.user_id,
        target_account_id=user.account_id,
        target_user_id=user.user_id,
        reason=payload.reason,
        new_values={"purge_request_id": purge_req.purge_request_id, "status": "pending"},
        outcome="success",
    )
    await db.commit()

    return {
        "status": "pending",
        "purge_request_id": purge_req.purge_request_id,
        "message": "Purge request submitted. Under the Two-Person Approval Rule, a second operator must approve it before anonymisation is executed.",
    }


@router.get("/purge-requests", response_model=List[PurgeRequestItem])
async def list_purge_requests(
    status_filter: Optional[str] = Query(None, alias="status"),
    ctx: PlatformAdminContext = Depends(require_platform_permission("users.read")),
    db: AsyncSession = Depends(get_db),
):
    """Lists all user purge requests with approval eligibility flags."""
    can_read_pii = ctx.has_permission("users.read_pii")
    has_hard_delete = ctx.has_permission("users.hard_delete")

    stmt = select(PlatformPurgeRequest).order_by(PlatformPurgeRequest.requested_at.desc())
    if status_filter:
        stmt = stmt.where(PlatformPurgeRequest.status == status_filter)

    requests = (await db.execute(stmt)).scalars().all()

    admin_ids = set()
    for r in requests:
        admin_ids.add(r.requested_by_admin_id)
        if r.approved_by_admin_id:
            admin_ids.add(r.approved_by_admin_id)
        if r.rejected_by_admin_id:
            admin_ids.add(r.rejected_by_admin_id)

    admins_by_id: Dict[int, str] = {}
    if admin_ids:
        admin_rows = (await db.execute(select(PlatformAdmin).where(PlatformAdmin.admin_id.in_(admin_ids)))).scalars().all()
        admins_by_id = {a.admin_id: a.email for a in admin_rows}

    items = []
    for r in requests:
        display_email = r.target_email_snapshot if can_read_pii else mask_email(r.target_email_snapshot)
        items.append(
            PurgeRequestItem(
                purge_request_id=r.purge_request_id,
                target_user_id=r.target_user_id,
                target_account_id=r.target_account_id,
                target_email=display_email,
                target_username=r.target_username_snapshot,
                requested_by_admin_id=r.requested_by_admin_id,
                requester_email=admins_by_id.get(r.requested_by_admin_id),
                requested_at=r.requested_at,
                reason=r.reason,
                status=r.status,
                approved_by_admin_id=r.approved_by_admin_id,
                approver_email=admins_by_id.get(r.approved_by_admin_id) if r.approved_by_admin_id else None,
                approved_at=r.approved_at,
                rejected_by_admin_id=r.rejected_by_admin_id,
                rejected_at=r.rejected_at,
                rejection_reason=r.rejection_reason,
                executed_at=r.executed_at,
                can_approve=(r.status == "pending" and r.requested_by_admin_id != ctx.admin.admin_id and has_hard_delete),
            )
        )
    return items


@router.post("/purge-requests/{purge_request_id}/approve")
async def approve_purge_request(
    purge_request_id: int,
    ctx: PlatformAdminContext = Depends(require_platform_permission("users.hard_delete")),
    db: AsyncSession = Depends(get_db),
):
    """
    Approves and executes a user purge request.
    Strictly enforces Two-Person Rule: Approver CANNOT be the requesting operator.
    Executes irreversible anonymisation.
    """
    req_res = await db.execute(select(PlatformPurgeRequest).where(PlatformPurgeRequest.purge_request_id == purge_request_id))
    purge_req = req_res.scalars().first()
    if not purge_req or purge_req.status != "pending":
        raise HTTPException(status_code=404, detail="Pending purge request not found.")

    # TWO-PERSON APPROVAL RULE ENFORCEMENT
    if purge_req.requested_by_admin_id == ctx.admin.admin_id:
        raise HTTPException(
            status_code=403,
            detail="Two-person approval rule violation: an operator cannot approve their own purge request. A second distinct operator is required.",
        )

    user_res = await db.execute(select(User).where(User.user_id == purge_req.target_user_id))
    user = user_res.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="Target customer user not found.")

    now = utc_now()
    old_state = await execute_user_anonymisation(db, user, now)

    purge_req.status = "approved"
    # The request kept the email so operators could see whose purge it was; once purged, only a masked form stays
    purge_req.target_email_snapshot = mask_email(purge_req.target_email_snapshot)
    purge_req.approved_by_admin_id = ctx.admin.admin_id
    purge_req.approved_at = now
    purge_req.executed_at = now

    await write_platform_audit_log(
        db=db,
        action_type="users.hard_delete",
        admin_email=ctx.admin.email,
        admin_id=ctx.admin.admin_id,
        session_id=ctx.session.session_id,
        target_type="user",
        target_id=user.user_id,
        target_account_id=user.account_id,
        target_user_id=user.user_id,
        reason=f"Approved purge request #{purge_req.purge_request_id} (requested by Admin #{purge_req.requested_by_admin_id}): {purge_req.reason}",
        old_values=old_state,
        new_values={
            "username": user.username,
            "email": user.email,
            "purged_at": now.isoformat(),
            "status": "purged",
        },
        outcome="success",
    )
    await db.commit()

    return {
        "status": "executed",
        "purge_request_id": purge_req.purge_request_id,
        "user_id": user.user_id,
        "message": f"User {user.user_id} has been permanently anonymised under the Two-Person Purge rule. Accounting and tax records preserved.",
    }


@router.post("/purge-requests/{purge_request_id}/reject")
async def reject_purge_request(
    purge_request_id: int,
    payload: RejectPurgeRequestPayload,
    ctx: PlatformAdminContext = Depends(require_platform_permission("users.hard_delete")),
    db: AsyncSession = Depends(get_db),
):
    """Rejects a user purge request."""
    req_res = await db.execute(select(PlatformPurgeRequest).where(PlatformPurgeRequest.purge_request_id == purge_request_id))
    purge_req = req_res.scalars().first()
    if not purge_req or purge_req.status != "pending":
        raise HTTPException(status_code=404, detail="Pending purge request not found.")

    now = utc_now()
    purge_req.status = "rejected"
    purge_req.rejected_by_admin_id = ctx.admin.admin_id
    purge_req.rejected_at = now
    purge_req.rejection_reason = payload.rejection_reason

    await write_platform_audit_log(
        db=db,
        action_type="users.purge_rejected",
        admin_email=ctx.admin.email,
        admin_id=ctx.admin.admin_id,
        session_id=ctx.session.session_id,
        target_type="user",
        target_id=purge_req.target_user_id,
        target_account_id=purge_req.target_account_id,
        target_user_id=purge_req.target_user_id,
        reason=payload.rejection_reason,
        new_values={"purge_request_id": purge_req.purge_request_id, "status": "rejected"},
        outcome="success",
    )
    await db.commit()

    return {"status": "rejected", "purge_request_id": purge_req.purge_request_id}


# ─────────────────────────────────────────────────────────────────────────────
# 10. OPERATOR IMPERSONATION WORKFLOW
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{user_id}/impersonate")
async def impersonate_user(
    user_id: int,
    payload: ImpersonateUserPayload,
    ctx: PlatformAdminContext = Depends(require_platform_permission("users.impersonate")),
    db: AsyncSession = Depends(get_db),
):
    """
    Creates a time-boxed, marked tenant impersonation session for troubleshooting.
    Requires 'users.impersonate' + Step-Up MFA.
    Enforces read-only access by default unless 'users.impersonate_write' is held.
    Sensitive tenant actions (password change, billing, account deletion) are strictly blocked.
    """
    if payload.write_access and not ctx.has_permission("users.impersonate_write"):
        raise HTTPException(
            status_code=403,
            detail="Operator lacks 'users.impersonate_write' permission. Impersonation must be read-only.",
        )

    user_res = await db.execute(select(User).where(User.user_id == user_id))
    user = user_res.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="Customer user not found.")

    if not user.is_active or user.purged_at is not None:
        raise HTTPException(status_code=400, detail="Cannot impersonate an inactive or purged user.")

    now_utc = utc_now()
    expires_utc = now_utc + timedelta(minutes=payload.minutes)
    now_ist = get_ist_now()
    expires_ist = now_ist + timedelta(minutes=payload.minutes)

    # 1. Create Platform Impersonation Record
    imp_session = PlatformImpersonationSession(
        admin_id=ctx.admin.admin_id,
        admin_email=ctx.admin.email,
        target_user_id=user.user_id,
        target_account_id=user.account_id or 0,
        session_token="",
        is_write=payload.write_access,
        reason=payload.reason,
        duration_minutes=payload.minutes,
        started_at=now_utc,
        expires_at=expires_utc,
    )
    db.add(imp_session)
    await db.flush()

    # 2. Mint customer JWT with impersonation claims
    to_encode = {
        "exp": expires_utc,
        "sub": str(user.user_id),
        "jti": secrets.token_urlsafe(16),
        "is_impersonation": True,
        "impersonated_by_admin_id": ctx.admin.admin_id,
        "impersonator_email": ctx.admin.email,
        "impersonation_session_id": imp_session.impersonation_id,
        "is_write": payload.write_access,
    }
    customer_token = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=ALGORITHM)
    cust_tok_hash = hashlib.sha256(customer_token.encode()).hexdigest()
    imp_session.session_token = cust_tok_hash

    # 3. Create corresponding customer portal UserSession with IST expiration matching permissions.py
    portal_sess = UserSession(
        user_id=user.user_id,
        token_hash=cust_tok_hash,
        client_type="impersonation",
        device_name=f"Impersonation by operator {ctx.admin.email} (ID #{ctx.admin.admin_id})",
        created_at=now_ist,
        expires_at=expires_ist,
        last_active_at=now_ist,
    )
    db.add(portal_sess)
    await db.flush()

    await write_platform_audit_log(
        db=db,
        action_type="users.impersonated",
        admin_email=ctx.admin.email,
        admin_id=ctx.admin.admin_id,
        session_id=ctx.session.session_id,
        target_type="user",
        target_id=user.user_id,
        target_account_id=user.account_id,
        target_user_id=user.user_id,
        reason=payload.reason,
        new_values={
            "impersonation_id": imp_session.impersonation_id,
            "duration_minutes": payload.minutes,
            "write_access": payload.write_access,
            "expires_at": expires_utc.isoformat(),
        },
        outcome="success",
    )
    await db.commit()

    return {
        "impersonation_id": imp_session.impersonation_id,
        "token": customer_token,
        "session_token": cust_tok_hash,
        "target_user_id": user.user_id,
        "target_username": user.username,
        "target_email": user.email,
        "expires_at": expires_utc,
        "write_access": payload.write_access,
        "redirect_url": "/dashboard",
    }


@router.delete("/impersonations/{impersonation_id}")
async def terminate_impersonation(
    impersonation_id: int,
    ctx: PlatformAdminContext = Depends(require_platform_permission("users.impersonate")),
    db: AsyncSession = Depends(get_db),
):
    """Prematurely terminates an active tenant impersonation session."""
    imp_res = await db.execute(
        select(PlatformImpersonationSession).where(PlatformImpersonationSession.impersonation_id == impersonation_id)
    )
    imp = imp_res.scalars().first()
    if not imp:
        raise HTTPException(status_code=404, detail="Impersonation session not found.")

    if imp.terminated_at is not None:
        return {"status": "already_terminated", "impersonation_id": impersonation_id}

    now_utc = utc_now()
    now_ist = get_ist_now()
    imp.terminated_at = now_utc
    imp.terminated_by_admin_id = ctx.admin.admin_id

    # Revoke portal user session matching token hash
    tok_hashes = [imp.session_token]
    try:
        tok_hashes.append(hashlib.sha256(imp.session_token.encode()).hexdigest())
    except Exception:
        pass

    await db.execute(
        update(UserSession)
        .where(UserSession.token_hash.in_(tok_hashes), UserSession.revoked_at.is_(None))
        .values(revoked_at=now_ist, revoke_reason="operator_terminated_impersonation")
    )
    invalidate_auth_cache(token_hash=imp.session_token, user_id=imp.target_user_id)

    await write_platform_audit_log(
        db=db,
        action_type="users.impersonation_ended",
        admin_email=ctx.admin.email,
        admin_id=ctx.admin.admin_id,
        session_id=ctx.session.session_id,
        target_type="user",
        target_id=imp.target_user_id,
        target_account_id=imp.target_account_id,
        target_user_id=imp.target_user_id,
        reason=f"Operator ended impersonation session #{imp.impersonation_id}",
        new_values={"terminated_at": now_utc.isoformat()},
        outcome="success",
    )
    await db.commit()

    return {"status": "terminated", "impersonation_id": impersonation_id}


@router.get("/impersonations/active", response_model=List[ImpersonationSessionItem])
async def list_active_impersonations(
    ctx: PlatformAdminContext = Depends(require_platform_permission("users.impersonate")),
    db: AsyncSession = Depends(get_db),
):
    """Lists currently active tenant impersonation sessions."""
    now = utc_now()
    sessions = (
        await db.execute(
            select(PlatformImpersonationSession)
            .where(
                PlatformImpersonationSession.terminated_at.is_(None),
                PlatformImpersonationSession.expires_at > now,
            )
            .order_by(PlatformImpersonationSession.started_at.desc())
        )
    ).scalars().all()

    return [
        ImpersonationSessionItem(
            impersonation_id=s.impersonation_id,
            admin_id=s.admin_id,
            admin_email=s.admin_email,
            target_user_id=s.target_user_id,
            target_account_id=s.target_account_id,
            reason=s.reason,
            duration_minutes=s.duration_minutes,
            is_write=s.is_write,
            started_at=s.started_at,
            expires_at=s.expires_at,
            terminated_at=s.terminated_at,
            is_active=True,
        )
        for s in sessions
    ]


# ─────────────────────────────────────────────────────────────────────────────
# 11. DATA RETENTION & COMPLIANCE
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/retention-policies", response_model=List[RetentionPolicyItem])
async def get_retention_policies(
    ctx: PlatformAdminContext = Depends(require_platform_permission("users.read")),
    db: AsyncSession = Depends(get_db),
):
    """Returns statutory data retention policies and legal schedules."""
    policies = (
        await db.execute(select(PlatformRetentionPolicy).order_by(PlatformRetentionPolicy.policy_id.asc()))
    ).scalars().all()

    return [
        RetentionPolicyItem(
            policy_id=p.policy_id,
            data_category=p.data_category,
            title=p.title,
            retention_period_days=p.retention_period_days,
            legal_basis=p.legal_basis,
            action_on_expiry=p.action_on_expiry,
            description=p.description,
            updated_at=p.updated_at,
        )
        for p in policies
    ]

