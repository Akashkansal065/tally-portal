"""Notifications: who receives them, where tapping one goes, grouping, per-user preferences and push delivery.

Routers call notify_admins / notify_user. Each notification stores a `link` (an app path with query) built here,
so the bell, the Notifications page, browser push and phone push all open the same screen. Push messages open
/notifications/open?id=N, which switches to the notification's company before following the link.
"""
import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlencode

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.permissions import ADMIN_ROLE_NAMES
from app.models.portal_core import Company, DevicePushToken, Notification, NotificationPreference, PushSubscription, Role, User
from app.services import fcm

try:
    from pywebpush import WebPushException, webpush
    PYWEBPUSH_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    webpush = None
    WebPushException = Exception
    PYWEBPUSH_AVAILABLE = False

logger = logging.getLogger("notifications")


# ─── Categories and preferences ──────────────────────────────────────────────

CATEGORY_BY_TYPE = {
    "attendance_approval": "approvals",
    "expense_created": "approvals",
    "attendance": "attendance",
    "attendance_activity": "attendance",
    "order_created": "orders",
    "order_status": "orders",
    "expense_status": "expenses",
    "check_in": "visits",
    "location_denied": "alerts",
    "security": "security",
    "reminder_failed": "collections",
    "voucher_approval": "approvals",
    "voucher_decision": "approvals",
    "backup_failed": "system",
    "sync_unlinked": "system",
    "sync_stale": "system",
    "account_refused": "security",
}

CATEGORIES: Tuple[dict, ...] = (
    {"id": "approvals", "label": "Approvals", "can_turn_off": False,
     "description": "Vouchers, attendance outside the office and expense claims waiting for a decision"},
    {"id": "attendance", "label": "Attendance", "can_turn_off": True,
     "description": "Clock-ins, clock-outs, automatic punch-outs and shift reminders"},
    {"id": "orders", "label": "Orders", "can_turn_off": True,
     "description": "New orders and changes to order status"},
    {"id": "expenses", "label": "Expenses", "can_turn_off": True,
     "description": "Decisions on expense claims"},
    {"id": "visits", "label": "Shop check-ins", "can_turn_off": True,
     "description": "Check-ins by the team, including location mismatches"},
    {"id": "alerts", "label": "Location alerts", "can_turn_off": True,
     "description": "Someone denied location access or sent an invalid location"},
    {"id": "security", "label": "Security", "can_turn_off": False,
     "description": "Sign-ins on new devices, and requests from outside your business that were refused"},
    {"id": "collections", "label": "Collections", "can_turn_off": True,
     "description": "Automatic payment reminders that couldn't be sent or delivered"},
    {"id": "system", "label": "System", "can_turn_off": True,
     "description": "Scheduled backups that couldn't run, and companies that stopped syncing with Tally"},
)
CATEGORY_IDS = {c["id"] for c in CATEGORIES}
DELIVERY_CHOICES = ("all", "in_app", "off")


def category_for(type_: Optional[str]) -> str:
    return CATEGORY_BY_TYPE.get(type_ or "", "other")


def can_turn_off(category: str) -> bool:
    return next((c["can_turn_off"] for c in CATEGORIES if c["id"] == category), True)


async def deliveries_for(db: AsyncSession, user_ids: Sequence[int], category: str) -> Dict[int, str]:
    """Each user's delivery choice for a category ('all' unless they changed it). Categories that can't be turned
    off fall back to in-app only."""
    if not user_ids:
        return {}
    rows = await db.execute(
        select(NotificationPreference.user_id, NotificationPreference.delivery).where(
            NotificationPreference.user_id.in_(list(user_ids)),
            NotificationPreference.category == category,
        )
    )
    chosen = dict(rows.all())
    result = {}
    for uid in user_ids:
        delivery = chosen.get(uid, "all")
        if delivery == "off" and not can_turn_off(category):
            delivery = "in_app"
        result[uid] = delivery
    return result


# ─── Links ───────────────────────────────────────────────────────────────────

def _path(path: str, **params) -> str:
    query = urlencode({k: v for k, v in params.items() if v is not None and v != ""})
    return f"{path}?{query}" if query else path


TEAM_ATTENDANCE_LINK = _path("/attendance", tab="admin", sub="today")


def attendance_approval_link(attendance_id) -> str:
    return _path("/attendance", tab="admin", sub="approvals", id=attendance_id)


def my_attendance_link(attendance_id=None) -> str:
    return _path("/attendance", tab="history", id=attendance_id)


def order_link(order_id, status: str = "all") -> str:
    return _path("/temporders", status=status, order=order_id)


def expense_link(expense_id, status: str = "all") -> str:
    return _path("/expenses", status=status, expense=expense_id)


def visit_log_link(day: Optional[str] = None, user_id=None, visit_id=None) -> str:
    return _path("/check-in/history", date=day, user=user_id, visit=visit_id)


def user_devices_link(user_id) -> str:
    return _path("/admin", tab="users", devices=user_id)


def location_alert_link(reference_type: Optional[str], user_id=None) -> str:
    if reference_type == "attendance":
        return TEAM_ATTENDANCE_LINK
    if reference_type == "payment":
        return "/payments"
    return visit_log_link(user_id=user_id)


def fallback_link(type_: Optional[str], reference_type: Optional[str], reference_id: Optional[str]) -> str:
    """Link for notifications stored before links existed, or created without one."""
    if type_ == "attendance_approval":
        return attendance_approval_link(reference_id)
    if type_ == "attendance_activity":
        return TEAM_ATTENDANCE_LINK
    if type_ == "location_denied":
        return location_alert_link(reference_type)
    if type_ == "security" or reference_type == "user_devices":
        return user_devices_link(reference_id)
    if type_ == "order_created":
        return order_link(reference_id, "pending")
    if reference_type == "order" or (type_ or "").startswith("order"):
        return order_link(reference_id)
    if reference_type == "expense" or (type_ or "").startswith("expense"):
        return expense_link(reference_id)
    if reference_type == "attendance" or type_ == "attendance":
        return "/attendance"
    if type_ == "check_in" or reference_type == "visit":
        return visit_log_link(visit_id=reference_id)
    if reference_type == "payment":
        return "/payments"
    if reference_type in ("customer", "customer_profile") and reference_id:
        return f"/customers/{reference_id}"
    return "/"


def link_of(notification: Notification) -> str:
    return notification.link or fallback_link(notification.type, notification.reference_type, notification.reference_id)


def open_link(notification_id: int) -> str:
    """What push messages open: a small page that switches company, marks it read, then follows the link."""
    return f"/notifications/open?id={notification_id}"


# ─── Unread badge cache ──────────────────────────────────────────────────────

# user_id -> (count, expiry). Counts cover every company the user can open.
_unread_count_cache: Dict[int, Tuple[int, float]] = {}
UNREAD_COUNT_TTL_SECONDS = 30.0


def cached_unread_count(user_id: int) -> Optional[int]:
    cached = _unread_count_cache.get(user_id)
    if cached and cached[1] > time.time():
        return cached[0]
    return None


def store_unread_count(user_id: int, count: int) -> None:
    _unread_count_cache[user_id] = (count, time.time() + UNREAD_COUNT_TTL_SECONDS)


def invalidate_unread_count(user_ids: Optional[Iterable[int]] = None) -> None:
    if user_ids is None:
        _unread_count_cache.clear()
        return
    for uid in user_ids:
        _unread_count_cache.pop(uid, None)


# ─── Creating notifications ──────────────────────────────────────────────────

async def admin_user_ids(db: AsyncSession, company_id: Optional[int] = None) -> List[int]:
    """Active admins of the business a company belongs to. An admin can open every company of their own account
    (see accessible_company_ids), so each hears about all of them, and never about another customer's.
    A company from before accounts has none, and is matched with the admins who have none either."""
    query = (select(User.user_id).join(Role, User.role_id == Role.role_id)
             .where(User.is_active == True, func.lower(Role.name).in_(ADMIN_ROLE_NAMES)))  # noqa: E712
    if company_id is not None:
        account_id = (await db.execute(select(Company.account_id).where(Company.company_id == company_id))).scalar()
        if account_id is not None:
            query = query.where(User.account_id == account_id)
        elif settings.ACCOUNTS_ENFORCED:
            return []
        else:
            query = query.where(User.account_id.is_(None))
    return list((await db.execute(query)).scalars().all())


async def create_notifications(
    db: AsyncSession,
    *,
    company_id: int,
    user_ids: Sequence[int],
    type: str,
    title: str,
    message: str,
    reference_id: Optional[str] = None,
    reference_type: Optional[str] = None,
    link: Optional[str] = None,
    group_key: Optional[str] = None,
    group_title: Optional[Callable[[int], str]] = None,
    group_link: Optional[str] = None,
    auto_commit: bool = False,
) -> List[Notification]:
    """Store one notification per recipient (respecting their preferences) and send push to those who want it.

    With group_key, a recipient's unread notification with the same key is updated instead ("3 staff clocked in
    today"): group_count goes up, the title comes from group_title(count), and the link becomes group_link."""
    category = category_for(type)
    recipients = list(dict.fromkeys(user_ids))
    deliveries = await deliveries_for(db, recipients, category)
    recipients = [uid for uid in recipients if deliveries[uid] != "off"]
    if not recipients:
        return []

    reference_id = str(reference_id) if reference_id is not None else None
    link = link or fallback_link(type, reference_type, reference_id)

    existing: Dict[int, Notification] = {}
    if group_key:
        rows = await db.execute(
            select(Notification).where(
                Notification.company_id == company_id,
                Notification.user_id.in_(recipients),
                Notification.group_key == group_key,
                Notification.is_read == False,
            )
        )
        for row in rows.scalars().all():
            existing.setdefault(row.user_id, row)

    created: List[Notification] = []
    titles: Dict[int, str] = {}
    for uid in recipients:
        notif = existing.get(uid)
        if notif is not None:
            notif.group_count = (notif.group_count or 1) + 1
            notif.title = group_title(notif.group_count) if group_title else title
            notif.message = message
            notif.link = group_link or link
            notif.reference_id = reference_id
            notif.reference_type = reference_type
            notif.created_at = func.now()  # moves the group to the top of the list
        else:
            notif = Notification(
                company_id=company_id,
                user_id=uid,
                type=type,
                category=category,
                title=title,
                message=message,
                reference_id=reference_id,
                reference_type=reference_type,
                link=link,
                group_key=group_key,
                group_count=1,
                is_read=False,
            )
            db.add(notif)
        titles[uid] = notif.title
        created.append(notif)

    await db.flush()
    ids = {n.user_id: n.id for n in created}
    if auto_commit:
        await db.commit()
    invalidate_unread_count(recipients)

    payloads = [
        (uid, push_payload(ids[uid], titles[uid], message, company_id, tag=group_key or f"notif-{ids[uid]}"))
        for uid in recipients
        if deliveries[uid] == "all"
    ]
    if payloads:
        schedule(deliver_push(payloads))
    return created


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
    link: Optional[str] = None,
    group_key: Optional[str] = None,
    group_title: Optional[Callable[[int], str]] = None,
    group_link: Optional[str] = None,
) -> List[Notification]:
    """Notify every admin (except the one who caused the event). Never raises: a failed alert must not fail
    the action that triggered it."""
    try:
        recipients = [uid for uid in await admin_user_ids(db, company_id) if uid != exclude_user_id]
        return await create_notifications(
            db, company_id=company_id, user_ids=recipients, type=type, title=title, message=message,
            reference_id=reference_id, reference_type=reference_type, link=link,
            group_key=group_key, group_title=group_title, group_link=group_link, auto_commit=auto_commit,
        )
    except Exception as e:
        logger.warning(f"Failed to notify admins: {e}")
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
    link: Optional[str] = None,
) -> Optional[Notification]:
    """Notify one user. Never raises (see notify_admins)."""
    try:
        created = await create_notifications(
            db, company_id=company_id, user_ids=[user_id], type=type, title=title, message=message,
            reference_id=reference_id, reference_type=reference_type, link=link, auto_commit=auto_commit,
        )
        return created[0] if created else None
    except Exception as e:
        logger.warning(f"Failed to notify user #{user_id}: {e}")
        return None


# ─── Approve / reject straight from a notification ──────────────────────────

async def pending_decisions(db: AsyncSession, notifications: Sequence[Notification]) -> Dict[int, str]:
    """Current status ('pending', 'approved', 'rejected') of the record behind each approval notification,
    keyed by notification id. Lets the list offer Approve/Reject only while a decision is still needed."""
    def ids_of(type_: str) -> Dict[int, List[int]]:
        found: Dict[int, List[int]] = {}
        for n in notifications:
            if n.type == type_ and n.reference_id and str(n.reference_id).isdigit():
                found.setdefault(int(n.reference_id), []).append(n.id)
        return found

    statuses: Dict[int, str] = {}
    attendance_refs = ids_of("attendance_approval")
    if attendance_refs:
        from app.routers.attendance import Attendance
        rows = await db.execute(select(Attendance.id, Attendance.approval_status).where(Attendance.id.in_(attendance_refs)))
        for record_id, status in rows.all():
            for nid in attendance_refs[record_id]:
                statuses[nid] = status or "approved"
    expense_refs = ids_of("expense_created")
    if expense_refs:
        from app.routers.expenses import Expense
        rows = await db.execute(select(Expense.id, Expense.status).where(Expense.id.in_(expense_refs)))
        for record_id, status in rows.all():
            for nid in expense_refs[record_id]:
                statuses[nid] = status or "pending"
    return statuses


# ─── Push delivery ───────────────────────────────────────────────────────────

_background_tasks: set = set()


def schedule(coro) -> None:
    """Run a coroutine in the background, keeping a reference so it isn't garbage-collected mid-flight."""
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


def push_payload(notification_id: int, title: str, body: str, company_id: int, tag: str) -> dict:
    return {
        "title": title,
        "body": body,
        "icon": "/icon-192.png",
        "badge": "/icon-192.png",
        "vibrate": [100, 50, 100],
        "tag": tag,
        "renotify": True,
        "data": {
            "url": open_link(notification_id),
            "notification_id": notification_id,
            "company_id": company_id,
            "created_at": datetime.now().isoformat(),
        },
    }


def _send_web_push(sub_info: dict, payload_str: str) -> Tuple[bool, Optional[int]]:
    """Blocking web push call; run it in a thread."""
    if not PYWEBPUSH_AVAILABLE or webpush is None:
        return False, None
    if not settings.VAPID_PRIVATE_KEY or not settings.VAPID_CLAIM_EMAIL:
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
        return False, ex.response.status_code if getattr(ex, "response", None) is not None else None
    except Exception as e:
        logger.warning(f"Web push failed: {e}")
        return False, None


async def deliver_push(payloads: Sequence[Tuple[int, dict]], session_factory=None) -> int:
    """Send each user's payload to all of that user's devices, whichever company they subscribed from: browsers
    by web push and the Android app by Firebase. Registrations the services report as gone are deleted.
    Returns how many devices accepted it."""
    if not payloads:
        return 0
    by_user = dict(payloads)
    delivered = 0
    try:
        async with (session_factory or AsyncSessionLocal)() as session:
            subs = (await session.execute(
                select(PushSubscription).where(PushSubscription.user_id.in_(list(by_user)))
            )).scalars().all()
            gone = []
            for sub in subs:
                info = {"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}}
                ok, status_code = await asyncio.to_thread(_send_web_push, info, json.dumps(by_user[sub.user_id]))
                if ok:
                    delivered += 1
                elif status_code in (404, 410):
                    gone.append(sub)

            if fcm.enabled():
                tokens = (await session.execute(
                    select(DevicePushToken).where(DevicePushToken.user_id.in_(list(by_user)))
                )).scalars().all()
                sent, dead = await fcm.send([(t.token, by_user[t.user_id]) for t in tokens])
                delivered += sent
                gone.extend(t for t in tokens if t.token in set(dead))

            for row in gone:
                await session.delete(row)
            if gone:
                await session.commit()
    except Exception as e:
        logger.warning(f"Push delivery failed: {e}")
    return delivered
