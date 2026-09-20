import asyncio
import json
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc, func, update, delete
from pywebpush import webpush, WebPushException

from app.core.database import get_db, AsyncSessionLocal
from app.core.permissions import get_current_user
from app.core.config import settings
from app.models.portal_core import User, Role, Notification, PushSubscription

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


class PushKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscriptionCreate(BaseModel):
    endpoint: str
    keys: PushKeys
    user_agent: Optional[str] = None


class PushSubscriptionDelete(BaseModel):
    endpoint: str


class VapidKeyResponse(BaseModel):
    public_key: str


# ─── Web Push Dispatcher ─────────────────────────────────────────────────────

def _sync_webpush_call(sub_info: dict, payload_str: str) -> tuple[bool, Optional[int]]:
    """Synchronous webpush network call meant to run in an async thread."""
    if not settings.VAPID_PRIVATE_KEY or not settings.VAPID_CLAIM_EMAIL:
        print("[WebPush] Missing VAPID_PRIVATE_KEY or VAPID_CLAIM_EMAIL")
        return False, None
    try:
        webpush(
            subscription_info=sub_info,
            data=payload_str,
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={"sub": settings.VAPID_CLAIM_EMAIL},
            timeout=8,
        )
        return True, None
    except WebPushException as ex:
        status_code = ex.response.status_code if ex.response is not None else None
        return False, status_code
    except Exception as e:
        print(f"[WebPush] Error: {e}")
        return False, None


async def send_push_notification_to_users(
    company_id: int,
    user_ids: List[int],
    title: str,
    body: str,
    url: Optional[str] = None,
    tag: Optional[str] = None,
) -> int:
    """
    Sends Web Push notifications to all active device subscriptions for given user_ids.
    Runs asynchronously and prunes expired/unregistered (404/410) subscriptions.
    """
    if not user_ids:
        return 0

    try:
        async with AsyncSessionLocal() as session:
            stmt = select(PushSubscription).where(
                PushSubscription.company_id == company_id,
                PushSubscription.user_id.in_(user_ids),
            )
            res = await session.execute(stmt)
            subs = res.scalars().all()

            if not subs:
                return 0

            payload_data = {
                "title": title,
                "body": body,
                "icon": "/icon-192.png",
                "badge": "/icon-192.png",
                "vibrate": [100, 50, 100],
                "data": {
                    "url": url or "/admin",
                    "created_at": datetime.now().isoformat(),
                },
                "tag": tag or f"mytally-{int(datetime.now().timestamp())}",
            }
            payload_str = json.dumps(payload_data)

            success_count = 0
            subs_to_delete = []

            for sub in subs:
                sub_info = {
                    "endpoint": sub.endpoint,
                    "keys": {
                        "p256dh": sub.p256dh,
                        "auth": sub.auth,
                    },
                }

                # Dispatch via thread pool to avoid blocking the asyncio loop
                ok, status_code = await asyncio.to_thread(_sync_webpush_call, sub_info, payload_str)
                if ok:
                    success_count += 1
                elif status_code in (404, 410):
                    subs_to_delete.append(sub.id)

            if subs_to_delete:
                del_stmt = delete(PushSubscription).where(PushSubscription.id.in_(subs_to_delete))
                await session.execute(del_stmt)
                await session.commit()

            return success_count
    except Exception as e:
        print(f"[WebPush] Background send error: {e}")
        return 0


# ─── Helper Functions ────────────────────────────────────────────────────────

def _get_target_url(reference_type: Optional[str]) -> str:
    if reference_type == "order":
        return "/temporders"
    elif reference_type == "visit":
        return "/customers"
    elif reference_type == "expense":
        return "/expenses"
    elif reference_type == "attendance":
        return "/attendance"
    return "/admin"


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
    Creates in-app notifications and dispatches mobile push alerts for all admins.
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
        recipient_ids = []
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
            recipient_ids.append(uid)

        if notifications:
            await db.flush()
            if auto_commit:
                await db.commit()

            # Fire & forget mobile push notifications
            if recipient_ids:
                asyncio.create_task(
                    send_push_notification_to_users(
                        company_id=company_id,
                        user_ids=recipient_ids,
                        title=title,
                        body=message,
                        url=_get_target_url(reference_type),
                        tag=f"{type}-{reference_id or 'admin'}",
                    )
                )

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
    Creates an in-app notification and dispatches mobile push alerts for a specific user.
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

        # Fire & forget mobile push notification
        asyncio.create_task(
            send_push_notification_to_users(
                company_id=company_id,
                user_ids=[user_id],
                title=title,
                body=message,
                url=_get_target_url(reference_type),
                tag=f"{type}-{reference_id or 'user'}",
            )
        )

        return notif
    except Exception as e:
        print(f"Warning: Failed to notify user #{user_id}: {e}")
        return None


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/vapid-public-key", response_model=VapidKeyResponse)
async def get_vapid_public_key():
    """
    Public key needed by browser pushManager to subscribe to Web Push.
    """
    if not settings.VAPID_PUBLIC_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="VAPID public key is not configured on the server."
        )
    return {"public_key": settings.VAPID_PUBLIC_KEY}


@router.post("/subscribe")
async def subscribe_push(
    req: PushSubscriptionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Register or update a device Web Push subscription for the active user.
    """
    if not req.endpoint or not req.keys.p256dh or not req.keys.auth:
        raise HTTPException(status_code=400, detail="Invalid push subscription details")

    # Check if this endpoint already exists
    stmt = select(PushSubscription).where(PushSubscription.endpoint == req.endpoint)
    res = await db.execute(stmt)
    existing = res.scalars().first()

    if existing:
        existing.user_id = current_user.user_id
        existing.company_id = current_user.company_id
        existing.p256dh = req.keys.p256dh
        existing.auth = req.keys.auth
        existing.user_agent = req.user_agent
    else:
        new_sub = PushSubscription(
            user_id=current_user.user_id,
            company_id=current_user.company_id,
            endpoint=req.endpoint,
            p256dh=req.keys.p256dh,
            auth=req.keys.auth,
            user_agent=req.user_agent,
        )
        db.add(new_sub)

    await db.commit()
    return {"success": True, "message": "Push notification subscription saved successfully"}


@router.post("/unsubscribe")
async def unsubscribe_push(
    req: PushSubscriptionDelete,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Remove a device Web Push subscription.
    """
    stmt = delete(PushSubscription).where(
        PushSubscription.endpoint == req.endpoint,
        PushSubscription.user_id == current_user.user_id,
    )
    result = await db.execute(stmt)
    await db.commit()
    return {"success": True, "deleted": result.rowcount > 0}


@router.post("/test-push")
async def send_test_push(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger an immediate test push alert to all registered devices of current user.
    """
    count = await send_push_notification_to_users(
        company_id=current_user.company_id,
        user_ids=[current_user.user_id],
        title="MyTally Mobile Alert 🔔",
        body="Push notifications are working! You will now receive alerts even when your phone is locked.",
        url="/admin",
        tag="test-alert",
    )

    if count == 0:
        # Check if user has any subscriptions registered
        stmt = select(func.count(PushSubscription.id)).where(
            PushSubscription.user_id == current_user.user_id,
            PushSubscription.company_id == current_user.company_id,
        )
        res = await db.execute(stmt)
        total_subs = res.scalar() or 0
        if total_subs == 0:
            return {
                "success": False,
                "message": "No push subscriptions found for your account. Please enable notifications on your device first.",
                "devices_notified": 0,
            }
        return {
            "success": False,
            "message": "Push notification could not be delivered to your registered device. Please re-subscribe.",
            "devices_notified": 0,
        }

    return {
        "success": True,
        "message": f"Test alert successfully sent to {count} device(s)!",
        "devices_notified": count,
    }


@router.get("", response_model=List[NotificationOut])
async def list_notifications(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    unread_only: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve in-app notifications for the authenticated user in the current company.
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


@router.delete("/clear-all")
async def clear_all_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Clear/delete all notifications for the current user in active company.
    """
    stmt = (
        delete(Notification)
        .where(
            Notification.user_id == current_user.user_id,
            Notification.company_id == current_user.company_id,
        )
    )
    result = await db.execute(stmt)
    await db.commit()
    return {"success": True, "deleted": result.rowcount}


@router.patch("/{notification_id}/read")
async def mark_as_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Mark a single notification as read for current user.
    """
    stmt = select(Notification).where(
        Notification.id == notification_id,
        Notification.user_id == current_user.user_id,
        Notification.company_id == current_user.company_id,
    )
    res = await db.execute(stmt)
    notif = res.scalars().first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")

    notif.is_read = True
    await db.commit()
    return {"success": True, "id": notification_id, "is_read": True}


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a single notification for the current user.
    """
    stmt = (
        delete(Notification)
        .where(
            Notification.id == notification_id,
            Notification.user_id == current_user.user_id,
            Notification.company_id == current_user.company_id,
        )
    )
    result = await db.execute(stmt)
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"success": True, "id": notification_id}
