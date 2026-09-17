import asyncio
import sys
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import func

from app.core.database import AsyncSessionLocal
from app.models.portal_core import User, Role, Notification
from app.routers.notifications import (
    notify_admins,
    notify_user,
    list_notifications,
    get_unread_count,
    mark_as_read,
    mark_all_as_read,
)

async def test_notifications():
    print("--- Starting Notifications System Verification ---")
    async with AsyncSessionLocal() as db:
        # 1. Fetch an admin user and non-admin user
        admin_res = await db.execute(
            select(User)
            .join(Role, User.role_id == Role.role_id)
            .options(selectinload(User.role))
            .where(
                User.is_active == True,
                func.lower(Role.name).in_(["admin", "superadmin", "owner"]),
            )
        )
        admin_user = admin_res.scalars().first()
        assert admin_user is not None, "No active admin user found in database!"
        print(f"Found Admin User: id={admin_user.user_id}, username={admin_user.username}, role={admin_user.role.name}")

        # Fetch non-admin user (or another user)
        other_res = await db.execute(
            select(User)
            .options(selectinload(User.role))
            .where(
                User.is_active == True,
                User.user_id != admin_user.user_id,
            )
        )
        other_user = other_res.scalars().first()
        if not other_user:
            other_user = admin_user
        print(f"Found Other User: id={other_user.user_id}, username={other_user.username}")

        # 2. Test notify_admins
        print("\nTesting notify_admins...")
        admin_notifs = await notify_admins(
            db=db,
            company_id=admin_user.company_id,
            type="check_in",
            title="New Check-In Test",
            message=f"{other_user.username} checked in at Test Motors",
            reference_id="9999",
            reference_type="visit",
            auto_commit=True,
        )
        print(f"Notified {len(admin_notifs)} admin(s)")
        assert len(admin_notifs) > 0, "Failed to notify admin!"
        first_notif = admin_notifs[0]
        assert first_notif.user_id == admin_user.user_id
        assert first_notif.type == "check_in"
        assert first_notif.is_read == False

        # 3. Test notify_user
        print("\nTesting notify_user (e.g. order approval)...")
        user_notif = await notify_user(
            db=db,
            company_id=other_user.company_id,
            user_id=other_user.user_id,
            type="order_status",
            title="Order #55 Approved",
            message="Your order #55 has been approved.",
            reference_id="55",
            reference_type="order",
            auto_commit=True,
        )
        assert user_notif is not None, "Failed to create user notification!"
        print(f"Created notification id={user_notif.id} for user_id={user_notif.user_id}")

        # 4. Test endpoints: get_unread_count
        print("\nTesting get_unread_count...")
        unread_res = await get_unread_count(current_user=admin_user, db=db)
        print(f"Admin unread count: {unread_res['count']}")
        assert unread_res["count"] > 0

        # 5. Test endpoints: list_notifications
        print("\nTesting list_notifications...")
        notif_list = await list_notifications(
            limit=10,
            offset=0,
            unread_only=False,
            current_user=admin_user,
            db=db,
        )
        print(f"Fetched {len(notif_list)} notifications for admin")
        assert len(notif_list) > 0
        latest = notif_list[0]
        print(f"Latest notification: title='{latest.title}', type='{latest.type}', is_read={latest.is_read}")

        # 6. Test endpoints: mark_as_read
        print("\nTesting mark_as_read...")
        mark_res = await mark_as_read(
            notification_id=first_notif.id,
            current_user=admin_user,
            db=db,
        )
        assert mark_res["success"] is True
        print(f"Marked notification #{first_notif.id} as read: {mark_res}")

        # Verify unread count decreased or changed
        unread_after = await get_unread_count(current_user=admin_user, db=db)
        print(f"Unread count after reading one: {unread_after['count']}")

        # 7. Test endpoints: mark_all_as_read
        print("\nTesting mark_all_as_read...")
        read_all_res = await mark_all_as_read(current_user=admin_user, db=db)
        print(f"Mark all as read result: {read_all_res}")
        assert read_all_res["success"] is True

        unread_final = await get_unread_count(current_user=admin_user, db=db)
        print(f"Admin final unread count: {unread_final['count']}")
        assert unread_final["count"] == 0

        print("\n--- All Notification System Tests Passed Successfully! ---")

if __name__ == "__main__":
    asyncio.run(test_notifications())
