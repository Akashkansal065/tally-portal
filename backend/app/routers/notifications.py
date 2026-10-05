import time
from typing import List, Literal, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import delete, desc, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.core.database import get_db
from app.core.permissions import accessible_company_ids, get_current_user
from app.core.sessions import parse_device
from app.models.portal_core import DevicePushToken, Notification, NotificationPreference, PushSubscription, Role, User
from app.services import notifications as service
# Routers and workers import these from here
from app.services.notifications import notify_admins, notify_user  # noqa: F401

router = APIRouter(prefix="/notifications", tags=["Notifications"])


# ─── Schemas ─────────────────────────────────────────────────────────────────

class NotificationOut(BaseModel):
    id: int
    company_id: int
    user_id: int
    type: str
    category: str
    title: str
    message: str
    reference_id: Optional[str] = None
    reference_type: Optional[str] = None
    link: str
    group_count: int = 1
    is_read: bool
    created_at: Optional[datetime] = None
    # For approval notifications: 'pending' while a decision is needed, then 'approved' or 'rejected'
    decision: Optional[str] = None


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


class NativePushToken(BaseModel):
    token: str
    platform: Literal["android", "ios"] = "android"


class VapidKeyResponse(BaseModel):
    public_key: str


class LocationDeniedAlertRequest(BaseModel):
    activity: str  # e.g., "Shop Check-In", "Attendance Punch", "Payment Collection"
    shop_name: Optional[str] = None
    details: Optional[str] = None
    reference_id: Optional[str] = None
    reference_type: Optional[str] = "visit"
    browser_name: Optional[str] = None
    is_mobile: Optional[bool] = None


class PreferenceOut(BaseModel):
    category: str
    label: str
    description: str
    can_turn_off: bool
    delivery: str


class PreferenceUpdate(BaseModel):
    category: str
    delivery: Literal["all", "in_app", "off"]


def to_out(n: Notification, decision: Optional[str] = None) -> NotificationOut:
    return NotificationOut(
        id=n.id,
        company_id=n.company_id,
        user_id=n.user_id,
        type=n.type,
        category=n.category or service.category_for(n.type),
        title=n.title,
        message=n.message,
        reference_id=n.reference_id,
        reference_type=n.reference_type,
        link=service.link_of(n),
        group_count=n.group_count or 1,
        is_read=bool(n.is_read),
        created_at=n.created_at,
        decision=decision,
    )


async def _visible_companies(db: AsyncSession, user: User) -> set:
    """Companies whose notifications this user may see (they could have lost access since)."""
    role_name = (await db.execute(select(Role.name).where(Role.role_id == user.role_id))).scalar()
    return await accessible_company_ids(db, user.user_id, user.company_id, role_name)


def _mine(user: User, companies: set):
    return (Notification.user_id == user.user_id, Notification.company_id.in_(companies))


_LOCATION_ALERT_CACHE: dict = {}
ONE_WEEK_SECONDS = 7 * 86400


def _cleanup_location_alert_cache(now: float):
    """Evict entries older than 1 week from the location alert debounce cache."""
    expired_keys = [k for k, ts in _LOCATION_ALERT_CACHE.items() if (now - ts) > ONE_WEEK_SECONDS]
    for k in expired_keys:
        _LOCATION_ALERT_CACHE.pop(k, None)


# ─── Push subscriptions ──────────────────────────────────────────────────────

@router.get("/vapid-public-key", response_model=VapidKeyResponse)
async def get_vapid_public_key():
    """Public key needed by browser pushManager to subscribe to Web Push."""
    if not settings.VAPID_PUBLIC_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="VAPID public key is not configured on the server."
        )
    return {"public_key": settings.VAPID_PUBLIC_KEY}


@router.post("/subscribe")
async def subscribe_push(
    req: PushSubscriptionCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Register or update a browser's Web Push subscription for the active user. Push goes to the user's devices
    for every company they can open, so the company stored here is only informational. The device id lets
    signing out on this browser remove the subscription."""
    if not req.endpoint or not req.keys.p256dh or not req.keys.auth:
        raise HTTPException(status_code=400, detail="Invalid push subscription details")

    device_id = parse_device(request).device_id
    existing = (await db.execute(select(PushSubscription).where(PushSubscription.endpoint == req.endpoint))).scalars().first()
    if existing:
        existing.user_id = current_user.user_id
        existing.company_id = current_user.company_id
        existing.p256dh = req.keys.p256dh
        existing.auth = req.keys.auth
        existing.user_agent = req.user_agent
        existing.device_id = device_id
    else:
        db.add(PushSubscription(
            user_id=current_user.user_id,
            company_id=current_user.company_id,
            endpoint=req.endpoint,
            p256dh=req.keys.p256dh,
            auth=req.keys.auth,
            user_agent=req.user_agent,
            device_id=device_id,
        ))
    await db.commit()
    return {"success": True, "message": "Push notification subscription saved successfully"}


@router.post("/unsubscribe")
async def unsubscribe_push(
    req: PushSubscriptionDelete,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a device Web Push subscription."""
    result = await db.execute(delete(PushSubscription).where(
        PushSubscription.endpoint == req.endpoint,
        PushSubscription.user_id == current_user.user_id,
    ))
    await db.commit()
    return {"success": True, "deleted": result.rowcount > 0}


@router.post("/native-token")
async def register_native_token(
    req: NativePushToken,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Register the installed app's Firebase token for the signed-in user. A token already registered to someone
    else (another person signed in on this phone) moves to the current user."""
    token = req.token.strip()
    if not token or len(token) > 512:
        raise HTTPException(status_code=400, detail="Invalid push token")
    device_id = parse_device(request).device_id
    row = (await db.execute(select(DevicePushToken).where(DevicePushToken.token == token))).scalars().first()
    if row:
        row.user_id = current_user.user_id
        row.platform = req.platform
        row.device_id = device_id
    else:
        db.add(DevicePushToken(user_id=current_user.user_id, token=token, platform=req.platform, device_id=device_id))
    await db.commit()
    return {"success": True}


@router.delete("/native-token")
async def unregister_native_token(
    req: NativePushToken,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Stop app push for this token (e.g. the person turned notifications off)."""
    result = await db.execute(delete(DevicePushToken).where(
        DevicePushToken.token == req.token.strip(),
        DevicePushToken.user_id == current_user.user_id,
    ))
    await db.commit()
    return {"success": True, "deleted": result.rowcount > 0}


@router.post("/test-push")
async def send_test_push(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send a test alert to every registered device of the current user."""
    payload = {
        "title": "MyTally Mobile Alert 🔔",
        "body": "Push notifications are working! You will now receive alerts even when your phone is locked.",
        "icon": "/icon-192.png",
        "badge": "/icon-192.png",
        "tag": "test-alert",
        "data": {"url": "/notifications", "created_at": datetime.now().isoformat()},
    }
    count = await service.deliver_push([(current_user.user_id, payload)])
    if count == 0:
        total_subs = (await db.execute(
            select(func.count(PushSubscription.id)).where(PushSubscription.user_id == current_user.user_id)
        )).scalar() or 0
        total_subs += (await db.execute(
            select(func.count(DevicePushToken.id)).where(DevicePushToken.user_id == current_user.user_id)
        )).scalar() or 0
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
    return {"success": True, "message": f"Test alert successfully sent to {count} device(s)!", "devices_notified": count}


@router.post("/location-denied-alert")
async def report_location_denied_alert(
    req: LocationDeniedAlertRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Alert admins when someone denies location access during a required activity, at most once per 2 minutes
    per user and activity."""
    now = time.time()
    _cleanup_location_alert_cache(now)
    cache_key = (current_user.company_id, current_user.user_id, req.activity)
    if now - _LOCATION_ALERT_CACHE.get(cache_key, 0) < 120:
        return {"success": True, "debounced": True, "message": "Alert was already dispatched recently to admins."}
    _LOCATION_ALERT_CACHE[cache_key] = now

    user_display = current_user.username or current_user.email
    activity_desc = req.activity + (f" at '{req.shop_name}'" if req.shop_name else "")
    device_info = ""
    if req.browser_name:
        device_info = f" on {req.browser_name} ({'mobile' if req.is_mobile else 'desktop'})"

    notifs = await notify_admins(
        db=db,
        company_id=current_user.company_id,
        type="location_denied",
        title=f"⚠️ Location Denied: {user_display}",
        message=(
            f"{user_display} ({current_user.email}) denied browser location access during {activity_desc}{device_info}. "
            f"The action was blocked until GPS access is granted."
        ),
        reference_id=req.reference_id,
        reference_type=req.reference_type or "visit",
        link=service.location_alert_link(req.reference_type, current_user.user_id),
        auto_commit=True,
    )
    return {
        "success": True,
        "debounced": False,
        "admins_notified": len(notifs),
        "message": f"Alert dispatched to {len(notifs)} admin(s)."
    }


# ─── Preferences ─────────────────────────────────────────────────────────────

@router.get("/preferences", response_model=List[PreferenceOut])
async def get_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Every category with how the current user wants it delivered."""
    rows = await db.execute(
        select(NotificationPreference.category, NotificationPreference.delivery)
        .where(NotificationPreference.user_id == current_user.user_id)
    )
    chosen = dict(rows.all())

    def delivery(c: dict) -> str:
        value = chosen.get(c["id"], "all")
        return "in_app" if value == "off" and not c["can_turn_off"] else value

    return [
        PreferenceOut(category=c["id"], label=c["label"], description=c["description"],
                      can_turn_off=c["can_turn_off"], delivery=delivery(c))
        for c in service.CATEGORIES
    ]


@router.put("/preferences", response_model=List[PreferenceOut])
async def update_preference(
    req: PreferenceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change how one category is delivered: all (in-app and push), in_app, or off."""
    if req.category not in service.CATEGORY_IDS:
        raise HTTPException(status_code=404, detail="Unknown notification category")
    if req.delivery == "off" and not service.can_turn_off(req.category):
        raise HTTPException(status_code=400, detail="This category can't be turned off, only limited to in-app")
    pref = (await db.execute(select(NotificationPreference).where(
        NotificationPreference.user_id == current_user.user_id,
        NotificationPreference.category == req.category,
    ))).scalars().first()
    if pref:
        pref.delivery = req.delivery
    else:
        db.add(NotificationPreference(user_id=current_user.user_id, category=req.category, delivery=req.delivery))
    await db.commit()
    return await get_preferences(current_user, db)


# ─── Reading and managing notifications ──────────────────────────────────────

@router.get("", response_model=List[NotificationOut])
async def list_notifications(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    unread_only: bool = Query(False),
    category: Optional[str] = Query(None, description="Only this category, e.g. 'approvals'"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """The current user's notifications from every company they can open, newest first."""
    companies = await _visible_companies(db, current_user)
    stmt = select(Notification).where(*_mine(current_user, companies))
    if unread_only:
        stmt = stmt.where(Notification.is_read == False)
    if category:
        legacy_types = [t for t, c in service.CATEGORY_BY_TYPE.items() if c == category]
        stmt = stmt.where((Notification.category == category) | (Notification.category.is_(None) & Notification.type.in_(legacy_types)))
    stmt = stmt.order_by(desc(Notification.created_at), desc(Notification.id)).offset(offset).limit(limit)
    notifications = (await db.execute(stmt)).scalars().all()
    decisions = await service.pending_decisions(db, notifications)
    return [to_out(n, decisions.get(n.id)) for n in notifications]


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Unread notifications across the user's companies, for the bell badge. Cached for 30s and cleared
    whenever the user gets a new notification or reads one."""
    cached = service.cached_unread_count(current_user.user_id)
    if cached is not None:
        return {"count": cached}
    companies = await _visible_companies(db, current_user)
    count = (await db.execute(
        select(func.count(Notification.id)).where(*_mine(current_user, companies), Notification.is_read == False)
    )).scalar() or 0
    service.store_unread_count(current_user.user_id, count)
    return {"count": count}


@router.patch("/read-all")
async def mark_all_as_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark all of the current user's notifications as read."""
    companies = await _visible_companies(db, current_user)
    result = await db.execute(
        update(Notification).where(*_mine(current_user, companies), Notification.is_read == False).values(is_read=True)
    )
    await db.commit()
    service.invalidate_unread_count([current_user.user_id])
    return {"success": True, "updated": result.rowcount}


@router.delete("/clear-all")
async def clear_all_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete all of the current user's notifications."""
    companies = await _visible_companies(db, current_user)
    result = await db.execute(delete(Notification).where(*_mine(current_user, companies)))
    await db.commit()
    service.invalidate_unread_count([current_user.user_id])
    return {"success": True, "deleted": result.rowcount}


async def _get_mine(db: AsyncSession, user: User, notification_id: int) -> Notification:
    companies = await _visible_companies(db, user)
    notif = (await db.execute(
        select(Notification).where(Notification.id == notification_id, *_mine(user, companies))
    )).scalars().first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notif


@router.get("/{notification_id}", response_model=NotificationOut)
async def get_notification(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """One notification, used when a push message is tapped (to find its company and link)."""
    notif = await _get_mine(db, current_user, notification_id)
    decisions = await service.pending_decisions(db, [notif])
    return to_out(notif, decisions.get(notif.id))


@router.patch("/{notification_id}/read")
async def mark_as_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark one notification as read."""
    notif = await _get_mine(db, current_user, notification_id)
    notif.is_read = True
    await db.commit()
    service.invalidate_unread_count([current_user.user_id])
    return {"success": True, "id": notification_id, "is_read": True}


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete one notification."""
    notif = await _get_mine(db, current_user, notification_id)
    await db.delete(notif)
    await db.commit()
    service.invalidate_unread_count([current_user.user_id])
    return {"success": True, "id": notification_id}
