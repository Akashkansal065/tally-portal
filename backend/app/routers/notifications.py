from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc, func, update

from app.core.database import get_db
from app.core.permissions import get_current_user
from app.models.portal_core import User, Role, Notification

router = APIRouter(prefix="/notifications", tags=["Notifications"])


# ─── Schemas ─────────────────────────────────────────────────────────────────

class NotificationOut(BaseModel):
    id: int
    company_id: int
    user_id: int
    type: str
    title: str
    message: str
    reference_id: Optional[str] = None
    reference_type: Optional[str] = None
    is_read: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UnreadCountResponse(BaseModel):
    count: int


# ─── Helper Functions ────────────────────────────────────────────────────────

async def notify_admins(
    db: AsyncSession,
    company_id: int,
    type: str,
    title: str,
    message: str,
    reference_id: Optional[str] = None,
    reference_type: Optional[str] = None,
    exclude_user_id: Optional[int] = None,
    auto_commit: bool = False,
) -> List[Notification]:
    """
    Creates notifications for all admin/superadmin/owner users in the given company.
    """
    try:
        stmt = (
            select(User.user_id)
            .join(Role, User.role_id == Role.role_id)
            .where(
                User.company_id == company_id,
                User.is_active == True,
                func.lower(Role.name).in_(["admin", "superadmin", "owner"]),
            )
        )
        res = await db.execute(stmt)
        admin_user_ids = res.scalars().all()

        notifications = []
        for uid in admin_user_ids:
            if exclude_user_id and uid == exclude_user_id:
                continue
            notif = Notification(
                company_id=company_id,
                user_id=uid,
                type=type,
                title=title,
                message=message,
                reference_id=str(reference_id) if reference_id is not None else None,
                reference_type=reference_type,
                is_read=False,
            )
            db.add(notif)
            notifications.append(notif)

        if notifications:
            await db.flush()
            if auto_commit:
                await db.commit()
        return notifications
    except Exception as e:
        print(f"Warning: Failed to notify admins: {e}")
        return []


async def notify_user(
    db: AsyncSession,
    company_id: int,
    user_id: int,
    type: str,
    title: str,
    message: str,
    reference_id: Optional[str] = None,
    reference_type: Optional[str] = None,
    auto_commit: bool = False,
) -> Optional[Notification]:
    """
    Creates a notification for a specific user (e.g. salesperson whose order/expense was approved or rejected).
    """
    try:
        notif = Notification(
            company_id=company_id,
            user_id=user_id,
            type=type,
            title=title,
            message=message,
            reference_id=str(reference_id) if reference_id is not None else None,
            reference_type=reference_type,
            is_read=False,
        )
        db.add(notif)
        await db.flush()
        if auto_commit:
            await db.commit()
        return notif
    except Exception as e:
        print(f"Warning: Failed to notify user #{user_id}: {e}")
        return None


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("", response_model=List[NotificationOut])
async def list_notifications(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    unread_only: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve notifications for the authenticated user in the current company.
    """
    stmt = (
        select(Notification)
        .where(
            Notification.user_id == current_user.user_id,
            Notification.company_id == current_user.company_id,
        )
    )
    if unread_only:
        stmt = stmt.where(Notification.is_read == False)

    stmt = stmt.order_by(desc(Notification.created_at)).offset(offset).limit(limit)
    res = await db.execute(stmt)
    notifications = res.scalars().all()
    return notifications


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the count of unread notifications for the active user badge.
    """
    stmt = (
        select(func.count(Notification.id))
        .where(
            Notification.user_id == current_user.user_id,
            Notification.company_id == current_user.company_id,
            Notification.is_read == False,
        )
    )
    res = await db.execute(stmt)
    count = res.scalar() or 0
    return {"count": count}


@router.patch("/{notification_id}/read")
async def mark_as_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Mark a single notification as read.
    """
    stmt = select(Notification).where(
        Notification.id == notification_id,
        Notification.user_id == current_user.user_id,
    )
    res = await db.execute(stmt)
    notif = res.scalars().first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")

    notif.is_read = True
    await db.commit()
    return {"success": True, "id": notification_id, "is_read": True}


@router.patch("/read-all")
async def mark_all_as_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Mark all unread notifications for current user as read.
    """
    stmt = (
        update(Notification)
        .where(
            Notification.user_id == current_user.user_id,
            Notification.company_id == current_user.company_id,
            Notification.is_read == False,
        )
        .values(is_read=True)
    )
    result = await db.execute(stmt)
    await db.commit()
    return {"success": True, "updated": result.rowcount}
