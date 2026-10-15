"""
platform_audit.py – Platform Operator Audit Trail, Verification & Export Router.

Prefix: /platform/audit-logs
Implements Plan Section 3.5 & Section 4:
  • GET /platform/audit-logs – Keyset paginated listing with rich filters
  • GET /platform/audit-logs/{id} – Single log entry with complete old/new state diffs
  • GET /platform/audit-logs/integrity – Cryptographic SHA-256 hash-chain verification
  • POST /platform/audit-logs/exports – Audited export with Step-Up MFA enforcement
  • STRICT APPEND-ONLY: No PUT, PATCH, or DELETE endpoints exist.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.platform_audit import (
    verify_platform_audit_chain,
    write_platform_audit_log,
)
from app.core.platform_dependencies import (
    PlatformAdminContext,
    require_platform_permission,
)
from app.models.platform import PlatformAuditLog

router = APIRouter(
    prefix="/platform/audit-logs",
    tags=["Platform Audit Logs"],
)


# ─────────────────────────────────────────────────────────────────────────────
# SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class AuditLogItem(BaseModel):
    audit_id: int
    occurred_at: datetime
    admin_id: Optional[int] = None
    admin_email: str
    session_id: Optional[int] = None
    action_type: str
    target_type: Optional[str] = None
    target_id: Optional[int] = None
    target_account_id: Optional[int] = None
    target_user_id: Optional[int] = None
    reason: Optional[str] = None
    outcome: str
    request_id: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    prev_hash: Optional[str] = None
    row_hash: str
    has_diff: bool = False

    class Config:
        from_attributes = True


class AuditLogDetail(BaseModel):
    audit_id: int
    occurred_at: datetime
    admin_id: Optional[int] = None
    admin_email: str
    session_id: Optional[int] = None
    action_type: str
    target_type: Optional[str] = None
    target_id: Optional[int] = None
    target_account_id: Optional[int] = None
    target_user_id: Optional[int] = None
    old_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None
    outcome: str
    request_id: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    prev_hash: Optional[str] = None
    row_hash: str

    class Config:
        from_attributes = True


class AuditLogsPage(BaseModel):
    items: List[AuditLogItem]
    next_cursor: Optional[str] = None
    has_more: bool
    total_count: int


class AuditIntegrityResponse(BaseModel):
    chain_intact: bool
    total_verified: int
    broken_at_id: Optional[int] = None
    error_detail: Optional[str] = None
    last_verified_at: str


class AuditExportRequest(BaseModel):
    format: str = Field("csv", pattern="^(csv|json)$")
    admin_id: Optional[int] = None
    action_type: Optional[str] = None
    target_user_id: Optional[int] = None
    target_account_id: Optional[int] = None
    outcome: Optional[str] = None
    from_date: Optional[datetime] = Field(None, alias="from")
    to_date: Optional[datetime] = Field(None, alias="to")
    limit: int = Field(2000, ge=1, le=5000)


def _mask_email(email: str) -> str:
    """Masks email address if caller lacks users.read_pii."""
    if "@" not in email:
        return "•••••"
    local, domain = email.split("@", 1)
    if len(local) <= 1:
        return f"{local}•••••@{domain}"
    return f"{local[0]}•••••@{domain}"


# ─────────────────────────────────────────────────────────────────────────────
# 1. LIST AUDIT LOGS (KEYSET PAGINATION & FILTERS)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("", response_model=AuditLogsPage)
async def list_audit_logs(
    cursor: Optional[str] = Query(None, description="Opaque keyset cursor (last seen audit_id)"),
    limit: int = Query(50, ge=1, le=100),
    admin_id: Optional[int] = Query(None),
    action_type: Optional[str] = Query(None),
    target_user_id: Optional[int] = Query(None),
    target_account_id: Optional[int] = Query(None),
    outcome: Optional[str] = Query(None),
    from_date: Optional[datetime] = Query(None, alias="from"),
    to_date: Optional[datetime] = Query(None, alias="to"),
    search: Optional[str] = Query(None, description="Search email, action, reason, IP, request ID"),
    ctx: PlatformAdminContext = Depends(require_platform_permission("audit.read")),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns keyset-paginated audit trail logs matching query filters.
    Applies PII masking if operator lacks 'users.read_pii'.
    """
    can_read_pii = ctx.has_permission("users.read_pii")

    # Base query for counting total
    count_stmt = select(func.count(PlatformAuditLog.audit_id))
    query_stmt = select(PlatformAuditLog).order_by(PlatformAuditLog.audit_id.desc())

    # Build filters
    filters = []

    if admin_id is not None:
        filters.append(PlatformAuditLog.admin_id == admin_id)
    if action_type:
        filters.append(PlatformAuditLog.action_type == action_type)
    if target_user_id is not None:
        filters.append(PlatformAuditLog.target_user_id == target_user_id)
    if target_account_id is not None:
        filters.append(PlatformAuditLog.target_account_id == target_account_id)
    if outcome:
        filters.append(PlatformAuditLog.outcome == outcome)
    if from_date:
        filters.append(PlatformAuditLog.occurred_at >= from_date)
    if to_date:
        filters.append(PlatformAuditLog.occurred_at <= to_date)
    if search:
        search_pattern = f"%{search.strip()}%"
        filters.append(
            or_(
                PlatformAuditLog.admin_email.ilike(search_pattern),
                PlatformAuditLog.action_type.ilike(search_pattern),
                PlatformAuditLog.reason.ilike(search_pattern),
                PlatformAuditLog.request_id.ilike(search_pattern),
                PlatformAuditLog.ip_address.ilike(search_pattern),
            )
        )

    if filters:
        count_stmt = count_stmt.where(*filters)
        query_stmt = query_stmt.where(*filters)

    # Keyset cursor pagination (descending audit_id)
    if cursor:
        try:
            cursor_id = int(cursor)
            query_stmt = query_stmt.where(PlatformAuditLog.audit_id < cursor_id)
        except ValueError:
            pass

    # Fetch total count
    total_res = await db.execute(count_stmt)
    total_count = total_res.scalar() or 0

    # Fetch limit + 1 to check for next page
    query_stmt = query_stmt.limit(limit + 1)
    res = await db.execute(query_stmt)
    rows = res.scalars().all()

    has_more = len(rows) > limit
    items_to_return = rows[:limit]
    next_cursor = str(items_to_return[-1].audit_id) if (has_more and items_to_return) else None

    items = []
    for r in items_to_return:
        admin_email = r.admin_email if can_read_pii else _mask_email(r.admin_email)
        has_diff = bool(r.old_values or r.new_values)
        items.append(
            AuditLogItem(
                audit_id=r.audit_id,
                occurred_at=r.occurred_at,
                admin_id=r.admin_id,
                admin_email=admin_email,
                session_id=r.session_id,
                action_type=r.action_type,
                target_type=r.target_type,
                target_id=r.target_id,
                target_account_id=r.target_account_id,
                target_user_id=r.target_user_id,
                reason=r.reason,
                outcome=r.outcome,
                request_id=r.request_id,
                ip_address=r.ip_address,
                user_agent=r.user_agent,
                prev_hash=r.prev_hash,
                row_hash=r.row_hash,
                has_diff=has_diff,
            )
        )

    return AuditLogsPage(
        items=items,
        next_cursor=next_cursor,
        has_more=has_more,
        total_count=total_count,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. AUDIT INTEGRITY CHECK (SHA-256 HASH-CHAIN VERIFICATION)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/integrity", response_model=AuditIntegrityResponse)
async def check_audit_chain_integrity(
    from_id: Optional[int] = Query(None, description="Start verification from audit_id"),
    max_rows: int = Query(10000, ge=1, le=50000),
    ctx: PlatformAdminContext = Depends(require_platform_permission("audit.read")),
    db: AsyncSession = Depends(get_db),
):
    """
    Cryptographically verifies the SHA-256 hash chain of the audit trail.
    Ensures no records have been altered, inserted, deleted, or backdated.
    """
    report = await verify_platform_audit_chain(db, from_id=from_id, max_rows=max_rows)
    return AuditIntegrityResponse(**report)


# ─────────────────────────────────────────────────────────────────────────────
# 3. AUDIT LOG EXPORT (REQUIRES 'audit.export' + STEP-UP MFA)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/exports")
async def export_audit_logs(
    body: AuditExportRequest,
    ctx: PlatformAdminContext = Depends(require_platform_permission("audit.export", step_up=True)),
    db: AsyncSession = Depends(get_db),
):
    """
    Generates a secure export of audit logs in CSV or JSON format.
    Requires 'audit.export' permission and fresh Step-Up MFA authentication.
    Applies PII masking if operator lacks 'users.read_pii'.
    Writes an immutable audit entry recording the export.
    """
    can_read_pii = ctx.has_permission("users.read_pii")

    query_stmt = select(PlatformAuditLog).order_by(PlatformAuditLog.audit_id.asc())
    filters = []

    if body.admin_id is not None:
        filters.append(PlatformAuditLog.admin_id == body.admin_id)
    if body.action_type:
        filters.append(PlatformAuditLog.action_type == body.action_type)
    if body.target_user_id is not None:
        filters.append(PlatformAuditLog.target_user_id == body.target_user_id)
    if body.target_account_id is not None:
        filters.append(PlatformAuditLog.target_account_id == body.target_account_id)
    if body.outcome:
        filters.append(PlatformAuditLog.outcome == body.outcome)
    if body.from_date:
        filters.append(PlatformAuditLog.occurred_at >= body.from_date)
    if body.to_date:
        filters.append(PlatformAuditLog.occurred_at <= body.to_date)

    if filters:
        query_stmt = query_stmt.where(*filters)

    query_stmt = query_stmt.limit(body.limit)
    res = await db.execute(query_stmt)
    rows = res.scalars().all()

    # Record export in audit log
    filter_summary = {
        "format": body.format,
        "count": len(rows),
        "admin_id": body.admin_id,
        "action_type": body.action_type,
        "target_user_id": body.target_user_id,
        "target_account_id": body.target_account_id,
        "outcome": body.outcome,
    }
    await write_platform_audit_log(
        db=db,
        action_type="audit.exported",
        admin_email=ctx.admin.email,
        admin_id=ctx.admin.admin_id,
        session_id=ctx.session.session_id,
        new_values=filter_summary,
        reason=f"Exported {len(rows)} audit records in {body.format.upper()} format",
        outcome="success",
    )
    await db.commit()

    if body.format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "audit_id",
            "occurred_at",
            "admin_email",
            "action_type",
            "target_type",
            "target_id",
            "outcome",
            "reason",
            "request_id",
            "ip_address",
            "prev_hash",
            "row_hash",
        ])

        for r in rows:
            admin_email = r.admin_email if can_read_pii else _mask_email(r.admin_email)
            writer.writerow([
                r.audit_id,
                r.occurred_at.isoformat() if r.occurred_at else "",
                admin_email,
                r.action_type,
                r.target_type or "",
                r.target_id or "",
                r.outcome,
                r.reason or "",
                r.request_id,
                r.ip_address or "",
                r.prev_hash or "",
                r.row_hash,
            ])

        csv_content = output.getvalue()
        filename = f"audit-logs-{int(datetime.now(timezone.utc).timestamp())}.csv"
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )

    # JSON export
    json_items = []
    for r in rows:
        admin_email = r.admin_email if can_read_pii else _mask_email(r.admin_email)
        json_items.append({
            "audit_id": r.audit_id,
            "occurred_at": r.occurred_at.isoformat() if r.occurred_at else "",
            "admin_email": admin_email,
            "action_type": r.action_type,
            "target_type": r.target_type,
            "target_id": r.target_id,
            "target_account_id": r.target_account_id,
            "target_user_id": r.target_user_id,
            "outcome": r.outcome,
            "reason": r.reason,
            "request_id": r.request_id,
            "ip_address": r.ip_address,
            "prev_hash": r.prev_hash,
            "row_hash": r.row_hash,
        })

    return {
        "total_records": len(json_items),
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "items": json_items,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4. GET AUDIT LOG ENTRY DETAIL (OLD / NEW STATE DIFFS)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{audit_id}", response_model=AuditLogDetail)
async def get_audit_log_detail(
    audit_id: int,
    ctx: PlatformAdminContext = Depends(require_platform_permission("audit.read")),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns full detail of a single audit log row, including JSON diffs
    of old_values and new_values for state transition investigations.
    """
    can_read_pii = ctx.has_permission("users.read_pii")

    res = await db.execute(
        select(PlatformAuditLog).where(PlatformAuditLog.audit_id == audit_id)
    )
    row = res.scalars().first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit record {audit_id} not found.",
        )

    admin_email = row.admin_email if can_read_pii else _mask_email(row.admin_email)

    old_parsed = None
    if row.old_values:
        try:
            old_parsed = json.loads(row.old_values)
        except Exception:
            old_parsed = {"raw": row.old_values}

    new_parsed = None
    if row.new_values:
        try:
            new_parsed = json.loads(row.new_values)
        except Exception:
            new_parsed = {"raw": row.new_values}

    return AuditLogDetail(
        audit_id=row.audit_id,
        occurred_at=row.occurred_at,
        admin_id=row.admin_id,
        admin_email=admin_email,
        session_id=row.session_id,
        action_type=row.action_type,
        target_type=row.target_type,
        target_id=row.target_id,
        target_account_id=row.target_account_id,
        target_user_id=row.target_user_id,
        old_values=old_parsed,
        new_values=new_parsed,
        reason=row.reason,
        outcome=row.outcome,
        request_id=row.request_id,
        ip_address=row.ip_address,
        user_agent=row.user_agent,
        prev_hash=row.prev_hash,
        row_hash=row.row_hash,
    )
