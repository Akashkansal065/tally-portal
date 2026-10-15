"""
entitlements.py – Account entitlements and feature authorization.

Determines an account's effective limits and unlocked features:
  Effective limit = plan limit + purchased extras + operator override
  NULL limit = unlimited

Cached in memory, invalidated whenever an account's subscription or
overrides change.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Set

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import get_current_user, is_platform_admin
from app.models.billing import AccountSubscription, BillingPlan
from app.models.portal_core import User
from app.services.billing.features import FEATURE_REGISTRY
from app.services.billing.subscriptions import ensure_legacy_subscription

logger = logging.getLogger("app.services.billing.entitlements")

_CACHE_TTL_SECONDS = 60
_ENTITLEMENTS_CACHE: dict[int, tuple[float, Entitlements]] = {}


@dataclass
class Entitlements:
    account_id: Optional[int]
    status: str                         # legacy | trialing | active | grace | locked | cancelled
    plan_code: Optional[str]
    plan_name: Optional[str]
    max_users: Optional[int]            # None = unlimited
    max_companies: Optional[int]        # None = unlimited
    max_devices: Optional[int]          # None = unlimited
    features: Set[str]
    current_period_end: Optional[datetime]
    trial_ends_at: Optional[datetime]
    grace_ends_at: Optional[datetime]
    is_locked: bool
    can_sync: bool

    def has_feature(self, key: str) -> bool:
        if self.status == "legacy":
            return True
        if self.is_locked:
            return False
        return key in self.features


def invalidate_entitlements_cache(account_id: Optional[int] = None) -> None:
    """Evict cached entitlements for a single account or all accounts."""
    if account_id is None:
        _ENTITLEMENTS_CACHE.clear()
    else:
        _ENTITLEMENTS_CACHE.pop(account_id, None)


async def get_entitlements(
    db: AsyncSession,
    account_id: Optional[int],
) -> Entitlements:
    """
    Resolve and return effective entitlements for *account_id*.
    Uses a 60-second in-memory cache.
    """
    if account_id is None:
        return Entitlements(
            account_id=None,
            status="unassigned",
            plan_code=None,
            plan_name=None,
            max_users=1,
            max_companies=1,
            max_devices=1,
            features=set(),
            current_period_end=None,
            trial_ends_at=None,
            grace_ends_at=None,
            is_locked=False,
            can_sync=True,
        )

    # Check cache
    now_ts = time.time()
    cached = _ENTITLEMENTS_CACHE.get(account_id)
    if cached and (now_ts - cached[0] < _CACHE_TTL_SECONDS):
        return cached[1]

    # Load subscription row
    sub: Optional[AccountSubscription] = (await db.execute(
        select(AccountSubscription).where(AccountSubscription.account_id == account_id)
    )).scalars().first()

    # If no subscription exists, grandfather as legacy
    if not sub:
        sub = await ensure_legacy_subscription(db, account_id)

    # Load plan
    plan: Optional[BillingPlan] = None
    if sub.plan_id:
        plan = (await db.execute(
            select(BillingPlan).where(BillingPlan.id == sub.plan_id)
        )).scalars().first()

    # Parse operator overrides
    overrides: dict = {}
    if sub.overrides:
        try:
            overrides = json.loads(sub.overrides)
        except Exception:
            overrides = {}

    sub_status = sub.status or "legacy"
    is_locked = sub_status in ("locked", "cancelled")
    can_sync = not is_locked

    all_registered_feature_keys = set(f.key for f in FEATURE_REGISTRY)

    if sub_status == "legacy":
        ent = Entitlements(
            account_id=account_id,
            status="legacy",
            plan_code=None,
            plan_name=None,
            max_users=None,
            max_companies=None,
            max_devices=None,
            features=all_registered_feature_keys,
            current_period_end=None,
            trial_ends_at=None,
            grace_ends_at=None,
            is_locked=False,
            can_sync=True,
        )
    elif is_locked:
        ent = Entitlements(
            account_id=account_id,
            status=sub_status,
            plan_code=plan.code if plan else None,
            plan_name=plan.name if plan else None,
            max_users=0,
            max_companies=0,
            max_devices=0,
            features=set(),
            current_period_end=sub.current_period_end,
            trial_ends_at=sub.trial_ends_at,
            grace_ends_at=sub.grace_ends_at,
            is_locked=True,
            can_sync=False,
        )
    else:
        # trialing, active, grace
        base_users = plan.max_users if plan else 1
        base_companies = plan.max_companies if plan else 1
        base_devices = plan.max_devices if plan else 3

        # Add purchased add-ons
        extra_users = sub.extra_users or 0
        extra_companies = sub.extra_companies or 0

        # Effective limits (NULL stays NULL = unlimited)
        max_users = (base_users + extra_users) if base_users is not None else None
        max_companies = (base_companies + extra_companies) if base_companies is not None else None
        max_devices = base_devices

        # Apply operator overrides if specified
        if "max_users" in overrides:
            max_users = overrides["max_users"]
        if "max_companies" in overrides:
            max_companies = overrides["max_companies"]
        if "max_devices" in overrides:
            max_devices = overrides["max_devices"]

        # Features
        plan_features: set[str] = set()
        if plan and plan.feature_keys:
            try:
                plan_features = set(json.loads(plan.feature_keys))
            except Exception:
                plan_features = set()

        if "extra_features" in overrides:
            plan_features.update(overrides["extra_features"])
        if "revoked_features" in overrides:
            plan_features.difference_update(overrides["revoked_features"])

        ent = Entitlements(
            account_id=account_id,
            status=sub_status,
            plan_code=plan.code if plan else None,
            plan_name=plan.name if plan else None,
            max_users=max_users,
            max_companies=max_companies,
            max_devices=max_devices,
            features=plan_features,
            current_period_end=sub.current_period_end,
            trial_ends_at=sub.trial_ends_at,
            grace_ends_at=sub.grace_ends_at,
            is_locked=False,
            can_sync=True,
        )

    _ENTITLEMENTS_CACHE[account_id] = (now_ts, ent)
    return ent


def require_feature(feature_key: str):
    """
    FastAPI endpoint dependency: verifies that the authenticated caller's account
    is entitled to *feature_key*.

    Raises 403 Forbidden with headers:
      X-Billing-Reason: feature
      X-Billing-Required-Feature: <feature_key>
    """
    async def _dependency(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> None:
        if not user.account_id or is_platform_admin(user):
            return

        ent = await get_entitlements(db, user.account_id)
        if not ent.has_feature(feature_key):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This feature ({feature_key}) requires a plan upgrade.",
                headers={
                    "X-Billing-Reason": "feature",
                    "X-Billing-Required-Feature": feature_key,
                },
            )

    return _dependency
