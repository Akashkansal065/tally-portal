"""
catalog_admin.py – Validation, management, and writes for plans, packages, prices, add-ons, and trial settings.

Implements Plan Section 3, 4.1 & 4.2:
- Plan group & package hierarchical CRUD
- In-use protection (package limits frozen once ordered/subscribed, price amount frozen once ordered)
- Dynamic label and code generation
- Idempotent startup migration from legacy single-tier plans to plan groups + packages
- AppSetting-based trial package and trial days management
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from app.core.config import settings

from app.models.billing import (
    AccountSubscription,
    BillingAddon,
    BillingOrder,
    BillingPlan,
    BillingPlanGroup,
    BillingPlanPrice,
)
from app.models.portal_core import Account, AppSetting
from app.services.billing.features import FEATURE_REGISTRY

logger = logging.getLogger("app.services.billing.catalog_admin")

DEFAULT_TRIAL_PLAN_CODE = "gold"
DEFAULT_TRIAL_DAYS = 7
APP_SETTING_TRIAL_KEY = "billing_trial_config"


# ─────────────────────────────────────────────────────────────────────────────
# Helper Generators & Labeling
# ─────────────────────────────────────────────────────────────────────────────

def generate_package_label(max_companies: Optional[int], max_users: Optional[int]) -> str:
    """Generate human-readable package label, e.g., '1 company + 3 users'."""
    if max_companies is None:
        comp_str = "Unlimited companies"
    elif max_companies == 1:
        comp_str = "1 company"
    else:
        comp_str = f"{max_companies} companies"

    if max_users is None:
        user_str = "unlimited users"
    elif max_users == 1:
        user_str = "1 user"
    else:
        user_str = f"{max_users} users"

    return f"{comp_str} + {user_str}"


def generate_package_code(group_code: str, max_companies: Optional[int], max_users: Optional[int]) -> str:
    """Generate standard package code slug, e.g., 'silver_1c_3u'."""
    comp_part = "uc" if max_companies is None else f"{max_companies}c"
    user_part = "uu" if max_users is None else f"{max_users}u"
    return f"{group_code.strip().lower()}_{comp_part}_{user_part}"


def sanitize_code(code: str) -> str:
    """Normalize code to lowercase letters, numbers, and underscores."""
    code = code.strip().lower()
    code = re.sub(r"[^a-z0-9_]+", "_", code).strip("_")
    if not code:
        raise ValueError("Code must contain valid alphanumeric characters.")
    return code


# ─────────────────────────────────────────────────────────────────────────────
# In-Use & Dependency Checks
# ─────────────────────────────────────────────────────────────────────────────

async def is_package_in_use(db: AsyncSession, package_id: int) -> Tuple[bool, int, int]:
    """
    Check if a package is used by any active subscription or paid order.
    Returns (in_use, active_subscribers_count, paid_orders_count).
    """
    subs_count = (await db.execute(
        select(func.count(AccountSubscription.id)).where(
            AccountSubscription.plan_id == package_id,
            AccountSubscription.status.in_(["active", "trialing", "grace"]),
        )
    )).scalar() or 0

    orders_count = (await db.execute(
        select(func.count(BillingOrder.id)).where(
            BillingOrder.plan_id == package_id,
            BillingOrder.status == "paid",
        )
    )).scalar() or 0

    return (subs_count > 0 or orders_count > 0), subs_count, orders_count


async def is_price_ordered(db: AsyncSession, price_id: int) -> bool:
    """Return True if any order was paid using this price point or subscription references it."""
    order_exists = (await db.execute(
        select(BillingOrder.id).where(
            BillingOrder.price_id == price_id,
            BillingOrder.status == "paid",
        ).limit(1)
    )).scalars().first()
    if order_exists:
        return True

    sub_exists = (await db.execute(
        select(AccountSubscription.id).where(
            AccountSubscription.price_id == price_id
        ).limit(1)
    )).scalars().first()
    return bool(sub_exists)


# ─────────────────────────────────────────────────────────────────────────────
# Migration Step: a retired price may sit beside the active one for the same term
# ─────────────────────────────────────────────────────────────────────────────

async def drop_unique_price_term_index(conn: AsyncConnection) -> bool:
    """Drop the old rule that a package has one price row per term, ever. Replacing a price that customers
    have paid keeps the old row (retired) and adds a new one, so the rule has to go. MySQL only; does nothing
    once done. Returns True when it dropped the index."""
    if conn.dialect.name != "mysql":
        return False
    schema = settings.PORTAL_DATABASE_NAME
    found = (await conn.execute(text(
        "SELECT 1 FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_SCHEMA = :schema "
        "AND TABLE_NAME = 'billing_plan_prices' AND INDEX_NAME = 'uq_plan_prices_plan_interval' LIMIT 1"
    ), {"schema": schema})).first()
    if not found:
        return False
    await conn.execute(text(f"ALTER TABLE `{schema}`.`billing_plan_prices` DROP INDEX `uq_plan_prices_plan_interval`"))
    logger.info("Dropped the unique index uq_plan_prices_plan_interval on billing_plan_prices.")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Migration Step: Existing Single-Tier Plans -> Plan Groups + Packages
# ─────────────────────────────────────────────────────────────────────────────

async def migrate_plans_to_groups(db: AsyncSession) -> None:
    """
    Idempotent startup migration:
    For every BillingPlan row without a group_id, create or link a BillingPlanGroup.
    - Public plans (silver, gold, diamond) create public plan groups.
    - Legacy plan creates hidden legacy group.
    - Custom plans (account_id set) create private plan groups for that account.
    """
    plans = (await db.execute(
        select(BillingPlan).where(BillingPlan.group_id.is_(None))
    )).scalars().all()

    if not plans:
        return

    for plan in plans:
        # Determine group code
        group_code = plan.code.lower()
        if plan.account_id is not None:
            # Custom account plan
            group_code = f"{plan.code}_grp"

        # Check if group already exists
        group = (await db.execute(
            select(BillingPlanGroup).where(BillingPlanGroup.code == group_code)
        )).scalars().first()

        if not group:
            is_legacy = (plan.code.lower() == "legacy")
            group = BillingPlanGroup(
                code=group_code,
                name=plan.name,
                tagline=plan.tagline,
                badge=plan.badge if not is_legacy else None,
                display=plan.display,
                feature_keys=plan.feature_keys,
                trial_days=plan.trial_days or 0,
                allow_extra_users=True,
                allow_extra_companies=True,
                is_public=plan.is_public and (plan.account_id is None) and (not is_legacy),
                is_active=plan.is_active,
                account_id=plan.account_id,
                sort_order=plan.sort_order,
            )
            db.add(group)
            await db.flush()

        plan.group_id = group.id
        if not plan.label:
            if plan.code.lower() == "legacy":
                plan.label = "Grandfathered Unlimited"
            else:
                plan.label = generate_package_label(plan.max_companies, plan.max_users)

    await db.commit()
    logger.info("Successfully verified/migrated billing plans to hierarchical plan groups.")


# ─────────────────────────────────────────────────────────────────────────────
# Full Catalog Listing (Operator Console)
# ─────────────────────────────────────────────────────────────────────────────

async def get_catalog_admin_tree(db: AsyncSession) -> List[Dict[str, Any]]:
    """Return all plan groups with nested packages, prices, and in-use subscriber counts."""
    groups = (await db.execute(
        select(BillingPlanGroup).order_by(BillingPlanGroup.sort_order, BillingPlanGroup.id)
    )).scalars().all()

    tree: List[Dict[str, Any]] = []
    for g in groups:
        packages = (await db.execute(
            select(BillingPlan).where(BillingPlan.group_id == g.id).order_by(BillingPlan.sort_order, BillingPlan.id)
        )).scalars().all()

        packages_data: List[Dict[str, Any]] = []
        for pkg in packages:
            prices = (await db.execute(
                select(BillingPlanPrice).where(BillingPlanPrice.plan_id == pkg.id).order_by(
                    BillingPlanPrice.interval, BillingPlanPrice.interval_count
                )
            )).scalars().all()

            in_use, active_subs, paid_orders = await is_package_in_use(db, pkg.id)

            prices_data = []
            for pr in prices:
                ordered = await is_price_ordered(db, pr.id)
                months = pr.interval_count * 12 if pr.interval == "year" else pr.interval_count
                per_month = round(pr.amount_paise / (months if months > 0 else 1))
                prices_data.append({
                    "id": pr.id,
                    "interval": pr.interval,
                    "interval_count": pr.interval_count,
                    "amount_paise": pr.amount_paise,
                    "amount_rupees": pr.amount_paise / 100,
                    "compare_at_paise": pr.compare_at_paise,
                    "compare_at_rupees": (pr.compare_at_paise / 100) if pr.compare_at_paise else None,
                    "per_month_paise": per_month,
                    "per_month_rupees": per_month / 100,
                    "autopay_allowed": pr.autopay_allowed,
                    "is_active": pr.is_active,
                    "is_ordered": ordered,
                })

            packages_data.append({
                "id": pkg.id,
                "code": pkg.code,
                "label": pkg.label or generate_package_label(pkg.max_companies, pkg.max_users),
                "max_companies": pkg.max_companies,
                "max_users": pkg.max_users,
                "max_devices": pkg.max_devices,
                "is_active": pkg.is_active,
                "sort_order": pkg.sort_order,
                "in_use": in_use,
                "active_subscribers": active_subs,
                "paid_orders": paid_orders,
                "prices": prices_data,
            })

        features = []
        if g.feature_keys:
            try:
                features = json.loads(g.feature_keys)
            except Exception:
                features = []

        tree.append({
            "id": g.id,
            "code": g.code,
            "name": g.name,
            "tagline": g.tagline,
            "badge": g.badge,
            "display": json.loads(g.display) if g.display else {},
            "features": features,
            "trial_days": g.trial_days,
            "allow_extra_users": g.allow_extra_users,
            "allow_extra_companies": g.allow_extra_companies,
            "is_public": g.is_public,
            "is_active": g.is_active,
            "account_id": g.account_id,
            "sort_order": g.sort_order,
            "packages": packages_data,
        })

    return tree


# ─────────────────────────────────────────────────────────────────────────────
# Plan Group CRUD
# ─────────────────────────────────────────────────────────────────────────────

async def create_plan_group(db: AsyncSession, data: Dict[str, Any]) -> BillingPlanGroup:
    code = sanitize_code(data["code"])
    existing = (await db.execute(
        select(BillingPlanGroup).where(BillingPlanGroup.code == code)
    )).scalars().first()
    if existing:
        raise ValueError(f"Plan group with code '{code}' already exists.")

    account_id = data.get("account_id")
    if account_id is not None and (await db.execute(
        select(Account.account_id).where(Account.account_id == account_id))).scalar() is None:
        raise ValueError(f"Account #{account_id} does not exist.")

    features = data.get("features")
    feature_keys_json = json.dumps(features) if isinstance(features, list) else None
    display_json = json.dumps(data.get("display")) if isinstance(data.get("display"), dict) else None

    group = BillingPlanGroup(
        code=code,
        name=data["name"].strip(),
        tagline=data.get("tagline"),
        badge=data.get("badge"),
        display=display_json,
        feature_keys=feature_keys_json,
        trial_days=int(data.get("trial_days") or 0),
        allow_extra_users=bool(data.get("allow_extra_users", True)),
        allow_extra_companies=bool(data.get("allow_extra_companies", True)),
        # A plan made for one account is never public
        is_public=bool(data.get("is_public", True)) and account_id is None,
        is_active=bool(data.get("is_active", True)),
        account_id=account_id,
        sort_order=int(data.get("sort_order") or 0),
    )
    db.add(group)
    await db.flush()
    return group


async def update_plan_group(db: AsyncSession, group_id: int, data: Dict[str, Any]) -> BillingPlanGroup:
    group = (await db.execute(
        select(BillingPlanGroup).where(BillingPlanGroup.id == group_id)
    )).scalars().first()
    if not group:
        raise ValueError(f"Plan group {group_id} not found.")

    if "name" in data and data["name"]:
        group.name = data["name"].strip()
        for pkg in (await db.execute(select(BillingPlan).where(BillingPlan.group_id == group.id))).scalars().all():
            if pkg.label:
                pkg.name = f"{group.name} - {pkg.label}"
    if "tagline" in data:
        group.tagline = data["tagline"]
    if "badge" in data:
        group.badge = data["badge"]
    if "trial_days" in data:
        group.trial_days = int(data["trial_days"] or 0)
    if "allow_extra_users" in data:
        group.allow_extra_users = bool(data["allow_extra_users"])
    if "allow_extra_companies" in data:
        group.allow_extra_companies = bool(data["allow_extra_companies"])
    if "is_public" in data and data["is_public"] is not None:
        if data["is_public"] and group.account_id is not None:
            raise ValueError("A plan made for one account cannot be made public.")
        group.is_public = bool(data["is_public"])
        # Packages carry their own copy, which older code paths read: keep it in step with the plan
        for pkg in (await db.execute(select(BillingPlan).where(BillingPlan.group_id == group.id))).scalars().all():
            pkg.is_public = group.is_public
    if "sort_order" in data and data["sort_order"] is not None:
        group.sort_order = int(data["sort_order"])
    if "display" in data:
        group.display = json.dumps(data["display"]) if isinstance(data["display"], dict) else data["display"]
    if "features" in data:
        group.feature_keys = json.dumps(data["features"]) if isinstance(data["features"], list) else data["features"]

    await db.flush()
    return group


async def set_plan_group_active(db: AsyncSession, group_id: int, is_active: bool) -> BillingPlanGroup:
    group = (await db.execute(
        select(BillingPlanGroup).where(BillingPlanGroup.id == group_id)
    )).scalars().first()
    if not group:
        raise ValueError(f"Plan group {group_id} not found.")
    group.is_active = is_active
    await db.flush()
    return group


# ─────────────────────────────────────────────────────────────────────────────
# Package CRUD
# ─────────────────────────────────────────────────────────────────────────────

async def _package_code_taken(db: AsyncSession, code: str) -> bool:
    return (await db.execute(select(BillingPlan.id).where(BillingPlan.code == code).limit(1))).scalar() is not None


async def _free_package_code(db: AsyncSession, base: str) -> str:
    """`base`, or `base_2`, `base_3` … when a retired package already holds it."""
    if not await _package_code_taken(db, base):
        return base
    for n in range(2, 1000):
        candidate = f"{base}_{n}"
        if not await _package_code_taken(db, candidate):
            return candidate
    raise ValueError(f"Could not find a free package code starting '{base}'.")


async def _active_combination_exists(
    db: AsyncSession,
    group_id: int,
    max_companies: Optional[int],
    max_users: Optional[int],
    max_devices: Optional[int],
    exclude_id: Optional[int] = None,
) -> bool:
    def same(column, value):
        return column.is_(None) if value is None else column == value

    stmt = select(BillingPlan.id).where(
        BillingPlan.group_id == group_id,
        same(BillingPlan.max_companies, max_companies),
        same(BillingPlan.max_users, max_users),
        same(BillingPlan.max_devices, max_devices),
        BillingPlan.is_active == True,  # noqa: E712
    )
    if exclude_id is not None:
        stmt = stmt.where(BillingPlan.id != exclude_id)
    return (await db.execute(stmt.limit(1))).scalar() is not None


async def create_package(db: AsyncSession, group_id: int, data: Dict[str, Any]) -> BillingPlan:
    group = (await db.execute(
        select(BillingPlanGroup).where(BillingPlanGroup.id == group_id)
    )).scalars().first()
    if not group:
        raise ValueError(f"Plan group {group_id} not found.")

    max_companies = data.get("max_companies")
    max_users = data.get("max_users")
    max_devices = data.get("max_devices")

    # Rule: Refuse duplicate active combination in the same plan group
    if await _active_combination_exists(db, group_id, max_companies, max_users, max_devices):
        raise ValueError("An active package with this company, user, and device combination already exists in this plan.")

    if data.get("code"):
        # A code the operator typed is used as given, and refused if taken (codes are never reused)
        code = sanitize_code(data["code"])
        if await _package_code_taken(db, code):
            raise ValueError(f"A package with code '{code}' already exists.")
    else:
        code = await _free_package_code(db, generate_package_code(group.code, max_companies, max_users))

    label = data.get("label") or generate_package_label(max_companies, max_users)

    package = BillingPlan(
        group_id=group.id,
        code=code,
        name=f"{group.name} - {label}",
        label=label,
        tagline=group.tagline,
        badge=group.badge,
        max_companies=max_companies,
        max_users=max_users,
        max_devices=max_devices,
        feature_keys=group.feature_keys,
        display=group.display,
        trial_days=group.trial_days,
        is_public=group.is_public,
        is_active=bool(data.get("is_active", True)),
        account_id=group.account_id,
        sort_order=int(data.get("sort_order") or 0),
    )
    db.add(package)
    await db.flush()
    return package


async def _check_can_activate(db: AsyncSession, package: BillingPlan, is_active: bool) -> None:
    """Two active packages in one plan may not offer the same limits (a duplicate starts inactive)."""
    if is_active and not package.is_active and package.group_id and await _active_combination_exists(
        db, package.group_id, package.max_companies, package.max_users, package.max_devices, exclude_id=package.id,
    ):
        raise ValueError(
            "Another active package in this plan has the same company, user, and device limits. "
            "Change this package's limits or retire the other one first."
        )


async def _refresh_package_name(db: AsyncSession, package: BillingPlan) -> None:
    if not package.group_id or not package.label:
        return
    group = (await db.execute(select(BillingPlanGroup).where(BillingPlanGroup.id == package.group_id))).scalars().first()
    if group:
        package.name = f"{group.name} - {package.label}"


async def update_package(db: AsyncSession, package_id: int, data: Dict[str, Any]) -> BillingPlan:
    package = (await db.execute(
        select(BillingPlan).where(BillingPlan.id == package_id)
    )).scalars().first()
    if not package:
        raise ValueError(f"Package {package_id} not found.")

    in_use, active_subs, paid_orders = await is_package_in_use(db, package_id)

    # Check if limits are being changed
    limits_changed = False
    for field in ("max_companies", "max_users", "max_devices"):
        if field in data and data[field] != getattr(package, field):
            limits_changed = True
            break

    if limits_changed and in_use:
        raise ValueError(
            f"Package limits cannot be changed because it has {active_subs} active subscriber(s) "
            f"and {paid_orders} paid order(s). Duplicate this package to offer new limits."
        )

    if limits_changed:
        new_limits = {f: data.get(f, getattr(package, f)) for f in ("max_companies", "max_users", "max_devices")}
        for f, v in new_limits.items():
            if v is not None and int(v) < 1:
                raise ValueError(f"{f} must be at least 1.")
        will_be_active = bool(data.get("is_active", package.is_active))
        if will_be_active and package.group_id and await _active_combination_exists(
            db, package.group_id, new_limits["max_companies"], new_limits["max_users"], new_limits["max_devices"],
            exclude_id=package.id,
        ):
            raise ValueError("An active package with this company, user, and device combination already exists in this plan.")
        old_auto_label = generate_package_label(package.max_companies, package.max_users)
        package.max_companies = new_limits["max_companies"]
        package.max_users = new_limits["max_users"]
        package.max_devices = new_limits["max_devices"]
        # A label that was generated from the limits follows them; one the operator wrote is kept
        if not data.get("label") and (not package.label or package.label == old_auto_label):
            package.label = generate_package_label(package.max_companies, package.max_users)

    if data.get("label"):
        package.label = data["label"].strip()
    if data.get("sort_order") is not None:
        package.sort_order = int(data["sort_order"])
    if data.get("is_active") is not None:
        await _check_can_activate(db, package, bool(data["is_active"]))
        package.is_active = bool(data["is_active"])
    await _refresh_package_name(db, package)

    await db.flush()
    return package


async def duplicate_package(db: AsyncSession, package_id: int) -> BillingPlan:
    """Duplicate a package and copy all its prices."""
    orig = (await db.execute(
        select(BillingPlan).where(BillingPlan.id == package_id)
    )).scalars().first()
    if not orig:
        raise ValueError(f"Package {package_id} not found.")

    new_code = await _free_package_code(db, f"{orig.code}_copy")

    new_pkg = BillingPlan(
        group_id=orig.group_id,
        code=new_code,
        name=f"{orig.name} (Copy)",
        label=f"{orig.label or ''} (Copy)",
        tagline=orig.tagline,
        badge=orig.badge,
        max_companies=orig.max_companies,
        max_users=orig.max_users,
        max_devices=orig.max_devices,
        feature_keys=orig.feature_keys,
        display=orig.display,
        trial_days=orig.trial_days,
        is_public=orig.is_public,
        is_active=False,  # Start inactive so operator can adjust prices before offering
        account_id=orig.account_id,
        sort_order=orig.sort_order + 1,
    )
    db.add(new_pkg)
    await db.flush()

    # Copy prices
    prices = (await db.execute(
        select(BillingPlanPrice).where(BillingPlanPrice.plan_id == orig.id)
    )).scalars().all()

    for p in prices:
        copy_price = BillingPlanPrice(
            plan_id=new_pkg.id,
            interval=p.interval,
            interval_count=p.interval_count,
            amount_paise=p.amount_paise,
            compare_at_paise=p.compare_at_paise,
            autopay_allowed=p.autopay_allowed,
            is_active=p.is_active,
        )
        db.add(copy_price)

    await db.flush()
    return new_pkg


async def set_package_active(db: AsyncSession, package_id: int, is_active: bool) -> BillingPlan:
    package = (await db.execute(
        select(BillingPlan).where(BillingPlan.id == package_id)
    )).scalars().first()
    if not package:
        raise ValueError(f"Package {package_id} not found.")
    await _check_can_activate(db, package, is_active)
    package.is_active = is_active
    await db.flush()
    return package


# ─────────────────────────────────────────────────────────────────────────────
# Price CRUD
# ─────────────────────────────────────────────────────────────────────────────

def validate_term(interval: str, count: int) -> None:
    if interval not in ("month", "year"):
        raise ValueError("Interval must be 'month' or 'year'.")
    if interval == "month" and not (1 <= count <= 11):
        raise ValueError("Month count must be between 1 and 11.")
    if interval == "year" and not (1 <= count <= 5):
        raise ValueError("Year count must be between 1 and 5.")


async def add_price(db: AsyncSession, package_id: int, data: Dict[str, Any]) -> BillingPlanPrice:
    package = (await db.execute(
        select(BillingPlan).where(BillingPlan.id == package_id)
    )).scalars().first()
    if not package:
        raise ValueError(f"Package {package_id} not found.")

    interval = data["interval"]
    count = int(data.get("interval_count", 1))
    validate_term(interval, count)

    amount_paise = int(data["amount_paise"])
    if amount_paise <= 0:
        raise ValueError("Amount must be greater than zero.")

    compare_at_paise = int(data["compare_at_paise"]) if data.get("compare_at_paise") else None
    if compare_at_paise is not None and compare_at_paise <= amount_paise:
        raise ValueError("Compare-at price must be greater than the standard amount.")

    autopay_allowed = bool(data.get("autopay_allowed", False))
    if autopay_allowed and (interval != "month" or count != 1):
        raise ValueError("Autopay can only be enabled on monthly 1-month terms.")

    # Check for existing active price for this term
    existing = (await db.execute(
        select(BillingPlanPrice).where(
            BillingPlanPrice.plan_id == package_id,
            BillingPlanPrice.interval == interval,
            BillingPlanPrice.interval_count == count,
            BillingPlanPrice.is_active == True,
        )
    )).scalars().first()

    replace = bool(data.get("replace", False))
    if existing:
        if not replace:
            raise ValueError(
                f"An active price for {interval} × {count} already exists. "
                "Specify replace=True to retire the current price and create the new one."
            )
        # Retire old price
        existing.is_active = False
        await db.flush()

    new_price = BillingPlanPrice(
        plan_id=package_id,
        interval=interval,
        interval_count=count,
        amount_paise=amount_paise,
        compare_at_paise=compare_at_paise,
        autopay_allowed=autopay_allowed,
        is_active=True,
    )
    db.add(new_price)
    await db.flush()
    return new_price


async def update_price(db: AsyncSession, price_id: int, data: Dict[str, Any]) -> BillingPlanPrice:
    price = (await db.execute(
        select(BillingPlanPrice).where(BillingPlanPrice.id == price_id)
    )).scalars().first()
    if not price:
        raise ValueError(f"Price {price_id} not found.")

    ordered = await is_price_ordered(db, price_id)

    if ("amount_paise" in data or "compare_at_paise" in data) and ordered:
        raise ValueError(
            "This price point has already been ordered by customers and cannot be edited. "
            "Retire it and add a new price for this term."
        )

    if "amount_paise" in data and not ordered:
        amt = int(data["amount_paise"])
        if amt <= 0:
            raise ValueError("Amount must be greater than zero.")
        price.amount_paise = amt

    if "compare_at_paise" in data and not ordered:
        cat = int(data["compare_at_paise"]) if data["compare_at_paise"] else None
        if cat is not None and cat <= price.amount_paise:
            raise ValueError("Compare-at price must be greater than standard amount.")
        price.compare_at_paise = cat

    if "autopay_allowed" in data:
        autopay = bool(data["autopay_allowed"])
        if autopay and (price.interval != "month" or price.interval_count != 1):
            raise ValueError("Autopay can only be enabled on monthly 1-month terms.")
        price.autopay_allowed = autopay

    await db.flush()
    return price


async def deactivate_price(db: AsyncSession, price_id: int) -> BillingPlanPrice:
    price = (await db.execute(
        select(BillingPlanPrice).where(BillingPlanPrice.id == price_id)
    )).scalars().first()
    if not price:
        raise ValueError(f"Price {price_id} not found.")
    price.is_active = False
    await db.flush()
    return price


# ─────────────────────────────────────────────────────────────────────────────
# Add-on CRUD
# ─────────────────────────────────────────────────────────────────────────────

async def update_addon(db: AsyncSession, addon_id: int, data: Dict[str, Any]) -> BillingAddon:
    addon = (await db.execute(
        select(BillingAddon).where(BillingAddon.id == addon_id)
    )).scalars().first()
    if not addon:
        raise ValueError(f"Addon {addon_id} not found.")

    for field in ("yearly_paise", "monthly_paise"):
        if field in data:
            value = int(data[field]) if data[field] is not None else None
            if value is not None and value < 0:
                raise ValueError(f"{field} cannot be negative.")
            setattr(addon, field, value)
    if "is_active" in data:
        addon.is_active = bool(data["is_active"])
    if "description" in data:
        addon.description = data["description"]

    await db.flush()
    return addon


# ─────────────────────────────────────────────────────────────────────────────
# Trial Settings
# ─────────────────────────────────────────────────────────────────────────────

async def _check_trial_package(db: AsyncSession, pkg: BillingPlan) -> None:
    """A trial package must be on sale to everyone: active, public, not the grandfathered legacy one."""
    group = None
    if pkg.group_id:
        group = (await db.execute(select(BillingPlanGroup).where(BillingPlanGroup.id == pkg.group_id))).scalars().first()
    if pkg.code == "legacy" or not pkg.is_active or pkg.account_id is not None or not pkg.is_public:
        raise ValueError("The trial package must be an active public package (not legacy or a custom plan).")
    if group and (not group.is_active or not group.is_public or group.account_id is not None):
        raise ValueError("The trial package's plan must be active and public.")


async def trial_package_usable(db: AsyncSession, pkg: Optional[BillingPlan]) -> bool:
    if not pkg:
        return False
    try:
        await _check_trial_package(db, pkg)
        return True
    except ValueError:
        return False


async def get_trial_setting(db: AsyncSession) -> Dict[str, Any]:
    """Retrieve trial package configuration from AppSetting or return fallback defaults."""
    row = (await db.execute(
        select(AppSetting).where(AppSetting.key == APP_SETTING_TRIAL_KEY)
    )).scalars().first()

    fallback_package_id = None
    gold_pkg = (await db.execute(
        select(BillingPlan).where(BillingPlan.code == DEFAULT_TRIAL_PLAN_CODE)
    )).scalars().first()
    if gold_pkg:
        fallback_package_id = gold_pkg.id

    if row and row.value:
        try:
            cfg = json.loads(row.value)
            pkg_id = cfg.get("package_id") or fallback_package_id
            days = cfg.get("trial_days") or DEFAULT_TRIAL_DAYS
            return {"package_id": pkg_id, "trial_days": days}
        except Exception:
            pass

    return {"package_id": fallback_package_id, "trial_days": DEFAULT_TRIAL_DAYS}


async def set_trial_setting(
    db: AsyncSession, package_id: int, trial_days: int, user_id: Optional[int] = None
) -> Dict[str, Any]:
    """Set the package and trial duration granted to new accounts."""
    pkg = (await db.execute(
        select(BillingPlan).where(BillingPlan.id == package_id)
    )).scalars().first()
    if not pkg:
        raise ValueError(f"Package {package_id} not found.")
    await _check_trial_package(db, pkg)
    if trial_days <= 0 or trial_days > 90:
        raise ValueError("Trial duration must be between 1 and 90 days.")

    val = json.dumps({"package_id": package_id, "trial_days": trial_days})
    row = (await db.execute(
        select(AppSetting).where(AppSetting.key == APP_SETTING_TRIAL_KEY)
    )).scalars().first()

    if row:
        row.value = val
        row.updated_by_user_id = user_id
    else:
        row = AppSetting(key=APP_SETTING_TRIAL_KEY, value=val, updated_by_user_id=user_id)
        db.add(row)

    await db.flush()
    return {"package_id": package_id, "trial_days": trial_days}
