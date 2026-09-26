import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Optional
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal
from app.core.datetime_utils import get_ist_now
from app.routers.attendance import Attendance
from app.models.portal_core import User
from app.routers.notifications import notify_user, notify_admins

logger = logging.getLogger("attendance_worker")

# Shift parameters
SHIFT_DURATION_HOURS = 9
SHIFT_DURATION_MINUTES = SHIFT_DURATION_HOURS * 60  # 540 minutes
WARNING_MINUTES_BEFORE_END = 5                       # 5 minutes before shift end (at 535 mins)
MIDNIGHT_WARNING_TIME = time(23, 50)                 # Alert at 23:50 IST
MIDNIGHT_CUTOFF_TIME = time(23, 58)                  # Auto punch out at 23:58 IST


async def check_and_process_attendance():
    """
    Evaluates active attendance records and processes:
    1. 9-Hour Auto Punch-Out & 5-minute pre-warning notification.
    2. Day-End (23:58 IST) Cutoff & 23:50 IST pre-midnight warning notification.
    """
    now_ist = get_ist_now()
    today_date = now_ist.date()
    current_time = now_ist.time()

    async with AsyncSessionLocal() as db:
        try:
            # Query all active shifts where user hasn't clocked out yet
            stmt = (
                select(Attendance)
                .options(selectinload(Attendance.user))
                .where(Attendance.check_out_time.is_(None))
            )
            res = await db.execute(stmt)
            active_records = res.scalars().all()

            for rec in active_records:
                try:
                    if not rec.check_in_time:
                        continue

                    user = rec.user
                    if not user:
                        # Fallback query if relationship is not eager loaded
                        user_stmt = select(User).where(User.user_id == rec.user_id)
                        u_res = await db.execute(user_stmt)
                        user = u_res.scalars().first()

                    user_id = rec.user_id
                    company_id = user.company_id if user else 1
                    username = user.username if user else f"User #{user_id}"

                    check_in_dt = rec.check_in_time
                    check_in_date = check_in_dt.date()

                    # Elapsed duration in minutes
                    elapsed_seconds = (now_ist - check_in_dt).total_seconds()
                    elapsed_minutes = elapsed_seconds / 60.0

                    # ─────────────────────────────────────────────────────────────
                    # Priority 1: Shift started on a previous calendar day (Edge case / server restart / overnight)
                    # ─────────────────────────────────────────────────────────────
                    if today_date > check_in_date:
                        cutoff_dt = datetime.combine(check_in_date, MIDNIGHT_CUTOFF_TIME)
                        rec.check_out_time = cutoff_dt
                        rec.is_auto_punch_out = True
                        rec.auto_punch_out_reason = "midnight_boundary"
                        rec.check_out_comments = "[SYSTEM AUTO PUNCH-OUT] Day-end boundary cutoff (23:58 IST)"
                        await db.commit()

                        formatted_date_str = check_in_date.strftime("%d %b %Y")
                        # User notification
                        await notify_user(
                            db=db,
                            company_id=company_id,
                            user_id=user_id,
                            type="attendance",
                            title="Shift Auto Punched Out (Day-End)",
                            message=f"Your shift from {formatted_date_str} was automatically closed at 11:58 PM (IST) at day-end.",
                            reference_id=str(rec.id),
                            reference_type="attendance",
                            auto_commit=True,
                        )
                        # Admin notification
                        await notify_admins(
                            db=db,
                            company_id=company_id,
                            type="attendance",
                            title=f"Auto Punch-Out: {username}",
                            message=f"{username}'s shift from {formatted_date_str} was automatically closed at 11:58 PM (IST) at day-end.",
                            reference_id=str(rec.id),
                            reference_type="attendance",
                            exclude_user_id=user_id,
                            auto_commit=True,
                        )
                        logger.info(f"Closed overnight shift for user #{user_id} ({username}) at {check_in_date} 23:58 IST")
                        continue

                    # ─────────────────────────────────────────────────────────────
                    # Priority 2: Today's Midnight Boundary reached (Time >= 23:58 IST)
                    # ─────────────────────────────────────────────────────────────
                    if current_time >= MIDNIGHT_CUTOFF_TIME:
                        cutoff_dt = datetime.combine(today_date, MIDNIGHT_CUTOFF_TIME)
                        rec.check_out_time = cutoff_dt
                        rec.is_auto_punch_out = True
                        rec.auto_punch_out_reason = "midnight_boundary"
                        rec.check_out_comments = "[SYSTEM AUTO PUNCH-OUT] Day-end boundary cutoff (23:58 IST)"
                        await db.commit()

                        # User notification
                        await notify_user(
                            db=db,
                            company_id=company_id,
                            user_id=user_id,
                            type="attendance",
                            title="Shift Auto Punched Out (Day-End)",
                            message="You have been automatically punched out at 11:58 PM (IST) as the calendar day has ended.",
                            reference_id=str(rec.id),
                            reference_type="attendance",
                            auto_commit=True,
                        )
                        # Admin notification
                        await notify_admins(
                            db=db,
                            company_id=company_id,
                            type="attendance",
                            title=f"Auto Punch-Out: {username}",
                            message=f"{username} was automatically punched out at 11:58 PM (IST) at day-end.",
                            reference_id=str(rec.id),
                            reference_type="attendance",
                            exclude_user_id=user_id,
                            auto_commit=True,
                        )
                        logger.info(f"Auto punched out user #{user_id} ({username}) at 23:58 IST day-end cutoff")
                        continue

                    # ─────────────────────────────────────────────────────────────
                    # Priority 3: 9-Hour Limit Reached (Elapsed >= 540 minutes)
                    # ─────────────────────────────────────────────────────────────
                    if elapsed_minutes >= SHIFT_DURATION_MINUTES:
                        punch_out_dt = check_in_dt + timedelta(hours=SHIFT_DURATION_HOURS)
                        # Ensure punch_out_dt does not exceed today's 23:58
                        day_end_dt = datetime.combine(today_date, MIDNIGHT_CUTOFF_TIME)
                        if punch_out_dt > day_end_dt:
                            punch_out_dt = day_end_dt
                            reason = "midnight_boundary"
                            comment = "[SYSTEM AUTO PUNCH-OUT] Day-end boundary cutoff (23:58 IST)"
                        else:
                            reason = "9h_limit"
                            comment = "[SYSTEM AUTO PUNCH-OUT] 9-hour shift limit reached"

                        rec.check_out_time = punch_out_dt
                        rec.is_auto_punch_out = True
                        rec.auto_punch_out_reason = reason
                        rec.check_out_comments = comment
                        await db.commit()

                        formatted_time_str = punch_out_dt.strftime("%I:%M %p")
                        # User notification
                        await notify_user(
                            db=db,
                            company_id=company_id,
                            user_id=user_id,
                            type="attendance",
                            title="Shift Auto Punched Out",
                            message=f"You have been automatically punched out as your 9-hour shift ended at {formatted_time_str} (IST).",
                            reference_id=str(rec.id),
                            reference_type="attendance",
                            auto_commit=True,
                        )
                        # Admin notification
                        await notify_admins(
                            db=db,
                            company_id=company_id,
                            type="attendance",
                            title=f"Auto Punch-Out: {username}",
                            message=f"{username} was automatically punched out after reaching the 9-hour shift limit at {formatted_time_str} (IST).",
                            reference_id=str(rec.id),
                            reference_type="attendance",
                            exclude_user_id=user_id,
                            auto_commit=True,
                        )
                        logger.info(f"Auto punched out user #{user_id} ({username}) after 9 hours at {punch_out_dt}")
                        continue

                    # ─────────────────────────────────────────────────────────────
                    # Priority 4: 5-Minute Pre-Warning before 9-Hour Limit (535 <= elapsed < 540 mins)
                    # ─────────────────────────────────────────────────────────────
                    warning_threshold = SHIFT_DURATION_MINUTES - WARNING_MINUTES_BEFORE_END
                    if elapsed_minutes >= warning_threshold and rec.warning_notification_sent_at is None:
                        rec.warning_notification_sent_at = now_ist
                        await db.commit()

                        await notify_user(
                            db=db,
                            company_id=company_id,
                            user_id=user_id,
                            type="attendance",
                            title="Attendance Alert: 5 Minutes Remaining",
                            message="Your 9-hour shift will end in 5 minutes and you will be automatically clocked out. Please punch out now with your photo and location.",
                            reference_id=str(rec.id),
                            reference_type="attendance",
                            auto_commit=True,
                        )
                        logger.info(f"Dispatched 5-minute pre-punchout warning to user #{user_id} ({username})")

                    # ─────────────────────────────────────────────────────────────
                    # Priority 5: Pre-Midnight Warning (Time >= 23:50 IST and < 23:58 IST)
                    # ─────────────────────────────────────────────────────────────
                    if current_time >= MIDNIGHT_WARNING_TIME and current_time < MIDNIGHT_CUTOFF_TIME:
                        if rec.midnight_warning_sent_at is None:
                            rec.midnight_warning_sent_at = now_ist
                            await db.commit()

                            await notify_user(
                                db=db,
                                company_id=company_id,
                                user_id=user_id,
                                type="attendance",
                                title="Attendance Alert: Day-End Cutoff Approaching",
                                message="The workday is ending. You will be automatically clocked out at 11:58 PM (IST). Please punch out now if you have completed your shift.",
                                reference_id=str(rec.id),
                                reference_type="attendance",
                                auto_commit=True,
                            )
                            logger.info(f"Dispatched pre-midnight warning to user #{user_id} ({username})")

                except Exception as rec_err:
                    logger.error(f"Error processing auto punch-out for attendance id {rec.id}: {rec_err}", exc_info=True)
                    await db.rollback()

        except Exception as query_err:
            logger.error(f"Error fetching active attendance records in auto checkout worker: {query_err}", exc_info=True)


async def attendance_auto_checkout_worker(interval_seconds: int = 60):
    """
    Background daemon loop that periodically inspects active attendance records.
    """
    logger.info(f"Starting Attendance Auto Punch-Out background worker (interval: {interval_seconds}s)...")
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            await check_and_process_attendance()
        except asyncio.CancelledError:
            logger.info("Attendance Auto Punch-Out background worker stopped.")
            break
        except Exception as e:
            logger.error(f"Unexpected exception in attendance_auto_checkout_worker: {e}", exc_info=True)
