"""notices.py – What customers are told about their subscription: a receipt when a payment lands, reminders
before a trial or a paid term ends, and a notice when the account enters grace or is locked.

Each goes to the account's admins in the app and, when a billing email is on file, by email. Nothing here ever
raises: a notice that cannot be sent must not undo or block the billing change it is about.
"""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import AccountBillingProfile, AccountSubscription, BillingSubscriptionEvent
from app.models.portal_core import Company
from app.services.billing.terms import as_utc

logger = logging.getLogger("app.services.billing.notices")

BILLING_LINK = "/admin?tab=billing"
# Days before the end of a trial or a paid term on which a reminder goes out, nearest first
REMINDER_DAYS = (1, 3, 7)
IST = timedelta(hours=5, minutes=30)


def ist_date(value: Optional[datetime]) -> str:
    return (as_utc(value) + IST).strftime("%d %b %Y") if value else ""


async def tell_account(db: AsyncSession, account_id: int, title: str, message: str, email: Optional[str] = None) -> None:
    try:
        from app.services import messaging
        from app.services.notifications import notify_admins

        company_id = (await db.execute(
            select(Company.company_id).where(Company.account_id == account_id, Company.is_active == True)  # noqa: E712
            .order_by(Company.company_id)
        )).scalars().first()
        if company_id:
            await notify_admins(db, company_id, type="billing", title=title, message=message,
                                link=BILLING_LINK, auto_commit=True)
        if email is None:
            email = (await db.execute(
                select(AccountBillingProfile.email).where(AccountBillingProfile.account_id == account_id)
            )).scalars().first()
        if email:
            sent = await messaging.send_email(email, title, message, from_name="MyTally Billing")
            if not sent.ok:
                logger.info(f"Billing email to account #{account_id} not sent: {sent.error}")
    except Exception as exc:
        logger.warning(f"Billing notice for account #{account_id} failed: {exc}")
        try:
            await db.rollback()
        except Exception:
            pass


async def payment_received(db: AsyncSession, *, account_id: int, order_ref: str, purpose: str, invoice_number: str,
                           total_paise: int, valid_until: Optional[datetime], email: Optional[str]) -> None:
    amount = f"₹{total_paise / 100:,.2f}"
    what = {"addon": "Your extra seats are active.",
            "downgrade": f"Your new plan starts when the current term ends. You are paid up until {ist_date(valid_until)}."
            }.get(purpose, f"Your plan is active until {ist_date(valid_until)}.")
    await tell_account(db, account_id, f"Payment of {amount} received",
                       f"We received {amount} for order {order_ref}. {what} Tax invoice {invoice_number} "
                       "is in Admin > Subscription & Plans.", email)


async def state_changed(db: AsyncSession, account_id: int, to_state: str, grace_ends_at: Optional[datetime]) -> None:
    if to_state == "grace":
        await tell_account(db, account_id, "Your MyTally plan has ended",
                           f"Your plan has ended. Everything keeps working until {ist_date(grace_ends_at)}; after "
                           "that the account is locked and Tally sync stops until you renew.")
    elif to_state == "locked":
        await tell_account(db, account_id, "Your MyTally account is locked",
                           "Your plan was not renewed, so the account is locked and Tally sync has stopped. "
                           "Your data is safe. Renew to pick up where you left off.")


async def send_expiry_reminders(db: AsyncSession, now: datetime) -> int:
    """One reminder each at 7, 3 and 1 days before a trial or a paid term ends. A reminder is recorded as an
    event, so it is sent once however often this runs."""
    subs = (await db.execute(
        select(AccountSubscription).where(
            AccountSubscription.status.in_(("trialing", "active")),
            AccountSubscription.current_period_end > now,
            AccountSubscription.current_period_end <= now + timedelta(days=max(REMINDER_DAYS)),
        )
    )).scalars().all()
    due = []
    for sub in subs:
        end = as_utc(sub.current_period_end)
        days_left = max(1, math.ceil((end - now).total_seconds() / 86400))
        offset = next((d for d in REMINDER_DAYS if days_left <= d), None)
        if offset is None:
            continue
        key = json.dumps({"ends": end.date().isoformat(), "days_before": offset})
        already = (await db.execute(
            select(BillingSubscriptionEvent.id).where(
                BillingSubscriptionEvent.account_id == sub.account_id,
                BillingSubscriptionEvent.event_type == "expiry_reminder_sent",
                BillingSubscriptionEvent.detail == key,
            )
        )).scalars().first()
        if already:
            continue
        db.add(BillingSubscriptionEvent(account_id=sub.account_id, event_type="expiry_reminder_sent",
                                        from_state=sub.status, to_state=sub.status, detail=key))
        due.append((sub.account_id, sub.status, end, days_left))
    if due:
        await db.commit()
    for account_id, status, end, days_left in due:
        kind = "free trial" if status == "trialing" else "plan"
        when = "tomorrow" if days_left <= 1 else f"in {days_left} days"
        await tell_account(db, account_id, f"Your MyTally {kind} ends {when}",
                           f"Your {kind} ends on {ist_date(end)}. Renew before then to keep the app and Tally sync "
                           "running without a break.")
    return len(due)
