"""
subscriptions.py – Subscription lifecycle and state management.

States:
  legacy   – grandfathered unlimited access, no expiry date
  trialing – 7-day unrestricted trial of Gold
  active   – paid term
  grace    – 7 days past period end; reminders sent, full lock imminent
  locked   – 402 full lock; sync paused, portal locked to billing page
  cancelled – cancelled by customer or operator
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import (
    AccountSubscription, BillingPlan, BillingSubscriptionEvent,
)
from app.models.portal_core import Account

logger = logging.getLogger("app.services.billing.subscriptions")


async def get_plan_by_code(db: AsyncSession, code: str) -> Optional[BillingPlan]:
    return (await db.execute(
        select(BillingPlan).where(BillingPlan.code == code)
    )).scalars().first()


async def start_trial(
    db: AsyncSession,
    account_id: int,
    trial_days: int = 7,
    actor_user_id: Optional[int] = None,
) -> AccountSubscription:
    """
    Start a trial for a newly registered account. Defaults to Gold tier for 7 days.
    """
    # Find trial plan (prefer gold, fallback to silver or first active public plan)
    trial_plan = await get_plan_by_code(db, "gold")
    if not trial_plan:
        trial_plan = await get_plan_by_code(db, "silver")
    if not trial_plan:
        trial_plan = (await db.execute(
            select(BillingPlan).where(BillingPlan.is_active == True, BillingPlan.is_public == True)  # noqa: E712
            .order_by(BillingPlan.sort_order)
        )).scalars().first()

    plan_id = trial_plan.id if trial_plan else None
    days = trial_plan.trial_days if (trial_plan and trial_plan.trial_days > 0) else trial_days

    now = datetime.now(timezone.utc)
    ends_at = now + timedelta(days=days)

    existing = (await db.execute(
        select(AccountSubscription).where(AccountSubscription.account_id == account_id)
    )).scalars().first()

    if existing:
        old_status = existing.status
        existing.plan_id = plan_id
        existing.status = "trialing"
        existing.trial_ends_at = ends_at
        existing.current_period_start = now
        existing.current_period_end = ends_at
        existing.grace_ends_at = None
        sub = existing
    else:
        old_status = None
        sub = AccountSubscription(
            account_id=account_id,
            plan_id=plan_id,
            status="trialing",
            trial_ends_at=ends_at,
            current_period_start=now,
            current_period_end=ends_at,
            extra_users=0,
            extra_companies=0,
        )
        db.add(sub)

    await db.flush()

    event = BillingSubscriptionEvent(
        account_id=account_id,
        event_type="trial_started",
        from_state=old_status,
        to_state="trialing",
        actor_user_id=actor_user_id,
        detail=json.dumps({"plan_code": trial_plan.code if trial_plan else None, "days": days}),
    )
    db.add(event)
    await db.flush()

    logger.info(f"Started {days}-day trial for account #{account_id} on plan {trial_plan.code if trial_plan else 'none'}")
    return sub


async def ensure_legacy_subscription(
    db: AsyncSession,
    account_id: int,
) -> AccountSubscription:
    """
    Ensure an account has a legacy subscription row (unlimited grandfathered access).
    """
    existing = (await db.execute(
        select(AccountSubscription).where(AccountSubscription.account_id == account_id)
    )).scalars().first()

    if existing:
        return existing

    legacy_plan = await get_plan_by_code(db, "legacy")

    sub = AccountSubscription(
        account_id=account_id,
        plan_id=legacy_plan.id if legacy_plan else None,
        status="legacy",
        trial_ends_at=None,
        current_period_start=None,
        current_period_end=None,
        grace_ends_at=None,
        extra_users=0,
        extra_companies=0,
    )
    db.add(sub)
    await db.flush()

    event = BillingSubscriptionEvent(
        account_id=account_id,
        event_type="legacy_grandfathered",
        from_state=None,
        to_state="legacy",
        actor_user_id=None,
        detail=json.dumps({"reason": "backfill_or_migration"}),
    )
    db.add(event)
    await db.flush()

    logger.info(f"Created legacy subscription for account #{account_id}")
    return sub


async def backfill_legacy_subscriptions(db: AsyncSession) -> int:
    """
    Idempotent startup step: give every account without an account_subscriptions row
    a legacy subscription row. Existing customers are completely unaffected.
    """
    # Find accounts with no subscription row
    sub_accounts = select(AccountSubscription.account_id)
    unassigned_accounts = (await db.execute(
        select(Account).where(Account.account_id.not_in(sub_accounts))
    )).scalars().all()

    if not unassigned_accounts:
        return 0

    count = 0
    for acc in unassigned_accounts:
        await ensure_legacy_subscription(db, acc.account_id)
        count += 1

    await db.commit()
    logger.info(f"Backfilled legacy subscriptions for {count} account(s)")
    return count


async def process_subscription_lifecycle(
    db: AsyncSession,
    grace_days: int = 7,
) -> dict[str, int]:
    """
    Lifecycle background worker loop:
    - Moves trialing accounts with trial_ends_at < now to grace.
    - Moves active accounts with current_period_end < now to grace.
    - Moves grace accounts with grace_ends_at < now to locked (full 402 lock).
    - Applies pending plan downgrades when current period has ended.
    """
    from app.services.billing.entitlements import invalidate_entitlements_cache

    now = datetime.now(timezone.utc)
    counts = {
        "trial_to_grace": 0,
        "active_to_grace": 0,
        "grace_to_locked": 0,
        "downgrades_applied": 0,
    }
    changed: list[tuple[int, str, Optional[datetime]]] = []
    # Accounts whose cached entitlements go stale. Cleared only after the commit: cleared before it, a request in
    # between would cache the old state again for a whole cache lifetime.
    touched: set[int] = set()

    # 0. A downgrade that was paid for takes over when the term it was bought in ends. The account stays
    # active: the new plan's own term has already been added to the period.
    due_stmt = select(AccountSubscription).where(
        AccountSubscription.status == "active",
        AccountSubscription.pending_plan_id.is_not(None),
        AccountSubscription.pending_effective_at <= now,
    )
    for sub in (await db.execute(due_stmt)).scalars().all():
        old_plan_id = sub.plan_id
        sub.plan_id = sub.pending_plan_id
        sub.price_id = sub.pending_price_id
        sub.current_period_start = sub.pending_effective_at
        sub.pending_plan_id = sub.pending_price_id = sub.pending_effective_at = None
        db.add(BillingSubscriptionEvent(
            account_id=sub.account_id,
            event_type="downgrade_applied",
            from_state="active",
            to_state="active",
            detail=json.dumps({"from_plan_id": old_plan_id, "to_plan_id": sub.plan_id}),
        ))
        counts["downgrades_applied"] += 1
        touched.add(sub.account_id)

    # 1. Trialing accounts past trial_ends_at -> grace
    trial_stmt = select(AccountSubscription).where(
        AccountSubscription.status == "trialing",
        AccountSubscription.trial_ends_at <= now,
    )
    trial_subs = (await db.execute(trial_stmt)).scalars().all()
    for sub in trial_subs:
        old_status = sub.status
        sub.status = "grace"
        sub.grace_ends_at = now + timedelta(days=grace_days)
        event = BillingSubscriptionEvent(
            account_id=sub.account_id,
            event_type="trial_expired_to_grace",
            from_state=old_status,
            to_state="grace",
            detail=json.dumps({"grace_ends_at": sub.grace_ends_at.isoformat()}),
        )
        db.add(event)
        counts["trial_to_grace"] += 1
        changed.append((sub.account_id, "grace", sub.grace_ends_at))
        touched.add(sub.account_id)

    # 2. Active accounts past current_period_end -> grace
    active_stmt = select(AccountSubscription).where(
        AccountSubscription.status == "active",
        AccountSubscription.current_period_end <= now,
    )
    active_subs = (await db.execute(active_stmt)).scalars().all()
    for sub in active_subs:
        old_status = sub.status
        if sub.pending_plan_id:
            sub.plan_id = sub.pending_plan_id
            sub.price_id = sub.pending_price_id
            sub.pending_plan_id = None
            sub.pending_price_id = None
            sub.pending_effective_at = None
            counts["downgrades_applied"] += 1

        sub.status = "grace"
        sub.grace_ends_at = now + timedelta(days=grace_days)
        event = BillingSubscriptionEvent(
            account_id=sub.account_id,
            event_type="period_expired_to_grace",
            from_state=old_status,
            to_state="grace",
            detail=json.dumps({"grace_ends_at": sub.grace_ends_at.isoformat()}),
        )
        db.add(event)
        counts["active_to_grace"] += 1
        changed.append((sub.account_id, "grace", sub.grace_ends_at))
        touched.add(sub.account_id)

    # 3. Grace accounts past grace_ends_at -> locked
    grace_stmt = select(AccountSubscription).where(
        AccountSubscription.status == "grace",
        AccountSubscription.grace_ends_at <= now,
    )
    grace_subs = (await db.execute(grace_stmt)).scalars().all()
    for sub in grace_subs:
        old_status = sub.status
        sub.status = "locked"
        event = BillingSubscriptionEvent(
            account_id=sub.account_id,
            event_type="grace_expired_to_locked",
            from_state=old_status,
            to_state="locked",
            detail=json.dumps({"locked_at": now.isoformat()}),
        )
        db.add(event)
        counts["grace_to_locked"] += 1
        changed.append((sub.account_id, "locked", None))
        touched.add(sub.account_id)

    if any(counts.values()):
        await db.commit()
        for account_id in touched:
            invalidate_entitlements_cache(account_id)
        logger.info(f"Subscription lifecycle processed: {counts}")

    from app.services.billing.notices import send_expiry_reminders, state_changed
    for account_id, to_state, grace_ends_at in changed:
        await state_changed(db, account_id, to_state, grace_ends_at)
    counts["reminders_sent"] = await send_expiry_reminders(db, now)

    return counts


async def billing_lifecycle_worker(interval_seconds: int = 300) -> None:
    """Periodically check and process subscription expiration, grace, and lock."""
    import asyncio
    from app.core.database import AsyncSessionLocal
    from app.services.billing.orders import expire_stale_orders

    while True:
        try:
            await asyncio.sleep(interval_seconds)
            async with AsyncSessionLocal() as db:
                await process_subscription_lifecycle(db)
                await expire_stale_orders(db)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error(f"Billing lifecycle worker error: {exc}", exc_info=True)
