"""
coupons.py – Platform coupon management service.

Implements all coupon lifecycle, validation, status determination,
and rule enforcement (Section 6 of Coupon Management Plan):
  1. Codes stored upper-case, alphanumeric + '_' + '-', 3-40 chars.
  2. Code uniqueness enforced forever.
  3. No delete, only switch off (is_active = False).
  4. Money terms frozen once redeemed (kind, value, max_discount_paise).
  5. Orders already placed keep their price.
  6. Audited and idempotent activate / deactivate.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import (
    BillingCoupon,
    BillingCouponRedemption,
    BillingOrder,
    BillingPlan,
    BillingPlanGroup,
)
from app.models.portal_core import Account
from app.services.billing.terms import as_utc, utc_now

CODE_REGEX = re.compile(r"^[A-Z0-9_-]{3,40}$")


def normalize_code(code: str) -> str:
    """Normalize coupon code to upper-case, stripped string and validate format."""
    if not code:
        raise ValueError("Coupon code is required.")
    norm = code.strip().upper()
    if not CODE_REGEX.match(norm):
        raise ValueError(
            "Coupon code must be 3-40 characters and contain only uppercase letters, digits, hyphens, and underscores."
        )
    return norm


def get_coupon_status(
    coupon: BillingCoupon,
    uses: int,
    now: Optional[datetime] = None,
) -> str:
    """
    Compute coupon status dynamically:
      'off'       if not is_active
      'scheduled' if valid_from is in the future
      'expired'   if valid_until is in the past
      'used_up'   if uses (paid and reserved) >= max_redemptions
      'active'    otherwise
    """
    if not coupon.is_active:
        return "off"

    current = as_utc(now or utc_now())

    if coupon.valid_from:
        v_from = as_utc(coupon.valid_from)
        if current < v_from:
            return "scheduled"

    if coupon.valid_until:
        v_until = as_utc(coupon.valid_until)
        if current > v_until:
            return "expired"

    if coupon.max_redemptions is not None and uses >= coupon.max_redemptions:
        return "used_up"

    return "active"


async def get_coupon_usage_counts(
    db: AsyncSession,
    coupon_id: int,
) -> Tuple[int, int, int]:
    """
    Returns (paid_uses, pending_uses, total_redemptions).
    - paid_uses: redemptions whose order is paid
    - pending_uses: redemptions reserved by an order still waiting for payment
    - total_redemptions: every redemption row. This is what checkout counts against the limits, so it is
      also what decides "used up", whether the money terms are frozen, and how low the limit may go.
    """
    total_redemptions = (await db.execute(
        select(func.count(BillingCouponRedemption.id)).where(
            BillingCouponRedemption.coupon_id == coupon_id
        )
    )).scalar() or 0

    paid_uses = (await db.execute(
        select(func.count(BillingCouponRedemption.id))
        .join(BillingOrder, BillingCouponRedemption.order_id == BillingOrder.id)
        .where(
            BillingCouponRedemption.coupon_id == coupon_id,
            BillingOrder.status == "paid",
        )
    )).scalar() or 0

    pending_uses = (await db.execute(
        select(func.count(BillingCouponRedemption.id))
        .join(BillingOrder, BillingCouponRedemption.order_id == BillingOrder.id)
        .where(
            BillingCouponRedemption.coupon_id == coupon_id,
            BillingOrder.status == "pending",
        )
    )).scalar() or 0

    return paid_uses, pending_uses, total_redemptions


async def list_coupons(
    db: AsyncSession,
    status_filter: Optional[str] = None,
    search: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List all coupons with calculated usage counts and status."""
    stmt = select(BillingCoupon).order_by(BillingCoupon.id.desc())

    if search:
        term = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                BillingCoupon.code.ilike(term),
                BillingCoupon.description.ilike(term),
            )
        )

    coupons = (await db.execute(stmt)).scalars().all()
    results: List[Dict[str, Any]] = []

    now = utc_now()
    for c in coupons:
        paid_uses, pending_uses, total_uses = await get_coupon_usage_counts(db, c.id)
        status = get_coupon_status(c, total_uses, now)

        if status_filter and status_filter.lower() != "all" and status != status_filter.lower():
            continue

        plan_codes_list = []
        if c.plan_codes:
            try:
                plan_codes_list = json.loads(c.plan_codes)
            except Exception:
                plan_codes_list = []

        results.append({
            "id": c.id,
            "code": c.code,
            "description": c.description,
            "kind": c.kind,
            "value": c.value,
            "value_rupees": (c.value / 100) if c.kind == "flat" else None,
            "max_discount_paise": c.max_discount_paise,
            "max_discount_rupees": (c.max_discount_paise / 100) if c.max_discount_paise else None,
            "valid_from": c.valid_from.isoformat() if c.valid_from else None,
            "valid_until": c.valid_until.isoformat() if c.valid_until else None,
            "max_redemptions": c.max_redemptions,
            "per_account_limit": c.per_account_limit,
            "plan_codes": plan_codes_list,
            "first_purchase_only": c.first_purchase_only,
            "account_id": c.account_id,
            "is_active": c.is_active,
            "status": status,
            "uses": {
                "paid": paid_uses,
                "pending": pending_uses,
                "total": total_uses,
            },
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })

    return results


async def get_coupon_detail(
    db: AsyncSession,
    coupon_id: int,
) -> Dict[str, Any]:
    """Get coupon details including redemption history."""
    coupon = (await db.execute(
        select(BillingCoupon).where(BillingCoupon.id == coupon_id)
    )).scalars().first()
    if not coupon:
        raise ValueError(f"Coupon with ID {coupon_id} not found.")

    paid_uses, pending_uses, total_uses = await get_coupon_usage_counts(db, coupon.id)
    status = get_coupon_status(coupon, total_uses)

    plan_codes_list = []
    if coupon.plan_codes:
        try:
            plan_codes_list = json.loads(coupon.plan_codes)
        except Exception:
            plan_codes_list = []

    # Query redemptions joined with Account and Order
    redemptions_stmt = (
        select(BillingCouponRedemption, Account, BillingOrder)
        .outerjoin(Account, BillingCouponRedemption.account_id == Account.account_id)
        .outerjoin(BillingOrder, BillingCouponRedemption.order_id == BillingOrder.id)
        .where(BillingCouponRedemption.coupon_id == coupon.id)
        .order_by(BillingCouponRedemption.id.desc())
    )
    rows = (await db.execute(redemptions_stmt)).all()

    redemptions_data = []
    total_discount_given_paise = 0
    for r, acc, ord_row in rows:
        disc = ord_row.discount_paise if ord_row and ord_row.discount_paise else 0
        total_discount_given_paise += disc
        redemptions_data.append({
            "id": r.id,
            "account_id": r.account_id,
            "account_name": acc.name if acc else f"Account #{r.account_id}",
            "order_id": r.order_id,
            "order_reference": ord_row.order_ref if ord_row else None,
            "order_status": ord_row.status if ord_row else None,
            "discount_paise": disc,
            "discount_rupees": round(disc / 100, 2),
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })

    return {
        "id": coupon.id,
        "code": coupon.code,
        "description": coupon.description,
        "kind": coupon.kind,
        "value": coupon.value,
        "value_rupees": (coupon.value / 100) if coupon.kind == "flat" else None,
        "max_discount_paise": coupon.max_discount_paise,
        "max_discount_rupees": (coupon.max_discount_paise / 100) if coupon.max_discount_paise else None,
        "valid_from": coupon.valid_from.isoformat() if coupon.valid_from else None,
        "valid_until": coupon.valid_until.isoformat() if coupon.valid_until else None,
        "max_redemptions": coupon.max_redemptions,
        "per_account_limit": coupon.per_account_limit,
        "plan_codes": plan_codes_list,
        "first_purchase_only": coupon.first_purchase_only,
        "account_id": coupon.account_id,
        "is_active": coupon.is_active,
        "status": status,
        "uses": {
            "paid": paid_uses,
            "pending": pending_uses,
            "total": total_uses,
        },
        "total_discount_given_paise": total_discount_given_paise,
        "total_discount_given_rupees": round(total_discount_given_paise / 100, 2),
        "redemptions": redemptions_data,
        "created_at": coupon.created_at.isoformat() if coupon.created_at else None,
    }


def _naive_utc(value: Optional[datetime]) -> Optional[datetime]:
    """Dates are stored as naive UTC, which is what the quote compares them with."""
    if value is None:
        return None
    return as_utc(value).astimezone(timezone.utc).replace(tzinfo=None)


async def _check_account(db: AsyncSession, account_id: Optional[int]) -> None:
    if account_id is None:
        return
    found = (await db.execute(select(Account.account_id).where(Account.account_id == account_id))).scalar()
    if found is None:
        raise ValueError(f"Account #{account_id} does not exist.")


async def _clean_plan_codes(db: AsyncSession, codes: Optional[List[Any]]) -> Optional[str]:
    """The coupon's plan restriction as stored JSON, or None for every plan. Each code must name a plan,
    a package, or 'addon', so a typo cannot make a coupon that silently never applies."""
    if not codes:
        return None
    cleaned = sorted({str(c).strip().lower() for c in codes if str(c).strip()})
    if not cleaned:
        return None
    known = {"addon"}
    known |= {c.lower() for c in (await db.execute(
        select(BillingPlan.code).where(func.lower(BillingPlan.code).in_(cleaned)))).scalars().all()}
    known |= {c.lower() for c in (await db.execute(
        select(BillingPlanGroup.code).where(func.lower(BillingPlanGroup.code).in_(cleaned)))).scalars().all()}
    unknown = [c for c in cleaned if c not in known]
    if unknown:
        raise ValueError(f"Unknown plan or package code(s): {', '.join(unknown)}.")
    return json.dumps(cleaned)


def _validate_dates(
    valid_from: Optional[datetime],
    valid_until: Optional[datetime],
) -> None:
    if valid_from and valid_until:
        if as_utc(valid_until) <= as_utc(valid_from):
            raise ValueError("valid_until must be after valid_from.")


def _validate_money_terms(
    kind: str,
    value: int,
    max_discount_paise: Optional[int],
) -> None:
    if kind not in ("percent", "flat"):
        raise ValueError("Coupon kind must be 'percent' or 'flat'.")
    if kind == "percent":
        if value < 1 or value > 100:
            raise ValueError("Percentage discount must be a whole number between 1 and 100.")
        if max_discount_paise is not None and max_discount_paise < 0:
            raise ValueError("max_discount_paise cannot be negative.")
    elif kind == "flat":
        if value < 100:
            raise ValueError("Flat discount value must be at least 100 paise (₹1).")


async def create_coupon(
    db: AsyncSession,
    data: Dict[str, Any],
    created_by_admin_id: Optional[int] = None,
) -> BillingCoupon:
    """Create a new coupon."""
    code = normalize_code(data["code"])

    # Uniqueness check (case-insensitive)
    existing = (await db.execute(
        select(BillingCoupon).where(func.upper(BillingCoupon.code) == code)
    )).scalars().first()
    if existing:
        raise ValueError(f"Coupon code '{code}' already exists.")

    kind = data.get("kind", "percent")
    value = int(data.get("value") or 0)
    max_discount_paise = data.get("max_discount_paise")
    if max_discount_paise is not None:
        max_discount_paise = int(max_discount_paise)
    if kind == "flat":
        max_discount_paise = None

    _validate_money_terms(kind, value, max_discount_paise)

    valid_from = _naive_utc(data.get("valid_from"))
    valid_until = _naive_utc(data.get("valid_until"))
    _validate_dates(valid_from, valid_until)

    max_redemptions = data.get("max_redemptions")
    if max_redemptions is not None:
        max_redemptions = int(max_redemptions)
        if max_redemptions < 1:
            raise ValueError("max_redemptions must be at least 1.")

    per_account_limit = int(data.get("per_account_limit") or 1)
    if per_account_limit < 1:
        raise ValueError("per_account_limit must be at least 1.")

    plan_codes_json = await _clean_plan_codes(db, data.get("plan_codes"))
    await _check_account(db, data.get("account_id"))

    coupon = BillingCoupon(
        code=code,
        description=data.get("description"),
        kind=kind,
        value=value,
        max_discount_paise=max_discount_paise,
        valid_from=valid_from,
        valid_until=valid_until,
        max_redemptions=max_redemptions,
        per_account_limit=per_account_limit,
        plan_codes=plan_codes_json,
        first_purchase_only=bool(data.get("first_purchase_only", False)),
        account_id=data.get("account_id"),
        created_by_admin_id=created_by_admin_id,
        is_active=bool(data.get("is_active", True)),
    )
    db.add(coupon)
    await db.flush()
    return coupon


async def update_coupon(
    db: AsyncSession,
    coupon_id: int,
    data: Dict[str, Any],
) -> BillingCoupon:
    """
    Update coupon details. Enforces Rule 4: Money terms (kind, value, max_discount_paise)
    cannot be changed once redeemed.
    """
    coupon = (await db.execute(
        select(BillingCoupon).where(BillingCoupon.id == coupon_id)
    )).scalars().first()
    if not coupon:
        raise ValueError(f"Coupon with ID {coupon_id} not found.")

    # kind, value and the per-account limit always have a value: an empty one means "leave as is"
    data = {k: v for k, v in data.items() if not (k in ("kind", "value", "per_account_limit") and v is None)}

    _, _, uses = await get_coupon_usage_counts(db, coupon.id)
    has_been_used = uses > 0

    # Rule 4: Money terms frozen once redeemed
    if has_been_used:
        if "kind" in data and data["kind"] != coupon.kind:
            raise ValueError(
                "Money terms (kind, value, max_discount) cannot be changed once coupon has been redeemed."
            )
        if "value" in data and int(data["value"]) != coupon.value:
            raise ValueError(
                "Money terms (kind, value, max_discount) cannot be changed once coupon has been redeemed."
            )
        new_max = data.get("max_discount_paise", coupon.max_discount_paise)
        if "max_discount_paise" in data and coupon.kind != "flat" and (
            (int(new_max) if new_max is not None else None) != coupon.max_discount_paise
        ):
            raise ValueError(
                "Money terms (kind, value, max_discount) cannot be changed once coupon has been redeemed."
            )
    else:
        # Not yet used; money terms can be modified
        new_kind = data.get("kind", coupon.kind)
        new_value = int(data.get("value", coupon.value))
        new_max = data.get("max_discount_paise", coupon.max_discount_paise)
        if new_max is not None:
            new_max = int(new_max)
        if new_kind == "flat":
            new_max = None
        _validate_money_terms(new_kind, new_value, new_max)
        coupon.kind = new_kind
        coupon.value = new_value
        coupon.max_discount_paise = new_max

    # Dates
    v_from = _naive_utc(data["valid_from"]) if "valid_from" in data else coupon.valid_from
    v_until = _naive_utc(data["valid_until"]) if "valid_until" in data else coupon.valid_until
    _validate_dates(v_from, v_until)
    coupon.valid_from = v_from
    coupon.valid_until = v_until

    # max_redemptions cannot be set lower than recorded uses
    if "max_redemptions" in data:
        max_red = data["max_redemptions"]
        if max_red is not None:
            max_red = int(max_red)
            if max_red < 1:
                raise ValueError("max_redemptions must be at least 1.")
            if max_red < uses:
                raise ValueError(
                    f"Max redemptions ({max_red}) cannot be less than redemptions already recorded ({uses})."
                )
        coupon.max_redemptions = max_red

    if "per_account_limit" in data:
        pal = int(data["per_account_limit"])
        if pal < 1:
            raise ValueError("per_account_limit must be at least 1.")
        coupon.per_account_limit = pal

    if "description" in data:
        coupon.description = data["description"]

    if "plan_codes" in data:
        coupon.plan_codes = await _clean_plan_codes(db, data["plan_codes"])

    if "first_purchase_only" in data:
        coupon.first_purchase_only = bool(data["first_purchase_only"])

    if "account_id" in data:
        await _check_account(db, data["account_id"])
        coupon.account_id = data["account_id"]

    if "is_active" in data:
        coupon.is_active = bool(data["is_active"])

    await db.flush()
    return coupon


async def set_coupon_active(
    db: AsyncSession,
    coupon_id: int,
    is_active: bool,
) -> BillingCoupon:
    """Activate or deactivate a coupon (idempotent)."""
    coupon = (await db.execute(
        select(BillingCoupon).where(BillingCoupon.id == coupon_id)
    )).scalars().first()
    if not coupon:
        raise ValueError(f"Coupon with ID {coupon_id} not found.")

    if coupon.is_active != is_active:
        coupon.is_active = is_active
        await db.flush()

    return coupon
