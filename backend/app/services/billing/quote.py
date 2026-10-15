"""
quote.py – Pure server-side quote calculation.

All internal arithmetic is in INTEGER PAISE. The returned dict uses paise
too; the API layer converts to rupees (÷ 100) before sending to the client.

Rules:
  • Base price from billing_plan_prices.amount_paise.
  • Add-on price = unit_paise × quantity × years (yearly_paise × qty × years).
  • Coupon: percent or flat; percent cap = max_discount_paise.
  • GST 18%: CGST+SGST when buyer_state == seller_state, else IGST.
  • All rounding done ONCE, at the end, in ROUND_HALF_UP.
  • Amounts are BigInteger paise; no floats in the return value.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Union

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import (
    AccountBillingProfile,
    AccountSubscription,
    BillingAddon, BillingCoupon, BillingCouponRedemption,
    BillingOrder, BillingPlan, BillingPlanPrice,
)
from app.services.billing.invoices import seller_state_code as configured_seller_state
from app.services.billing.terms import as_utc, utc_now

logger = logging.getLogger("app.services.billing.quote")

GST_RATE = Decimal("18")


def _round_paise(d: Decimal) -> int:
    """Round a Decimal to the nearest paisa (integer)."""
    return int(d.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


@dataclass
class QuoteResult:
    # line amounts (paise)
    base_plan_paise: int
    extra_users_paise: int
    extra_companies_paise: int
    subtotal_paise: int       # sum of lines
    discount_paise: int       # coupon discount
    proration_credit_paise: int # upgrade credit for unused days
    taxable_paise: int        # subtotal - discount - proration_credit
    cgst_paise: int
    sgst_paise: int
    igst_paise: int
    total_paise: int

    # metadata
    plan_code: str
    plan_name: str
    interval: str
    interval_count: int
    extra_users: int
    extra_companies: int
    coupon_code: Optional[str]
    coupon_discount_kind: Optional[str]
    years: int                # 1 for monthly plans; interval_count for year plans
    months: int               # total billing months
    buyer_state_code: Optional[str]
    igst_applied: bool
    purpose: str = "new"      # new | renewal | upgrade | downgrade | addon
    price_id: Optional[int] = None

    def as_dict(self) -> dict:
        return {
            "base_plan_paise":      self.base_plan_paise,
            "extra_users_paise":    self.extra_users_paise,
            "extra_companies_paise":self.extra_companies_paise,
            "subtotal_paise":       self.subtotal_paise,
            "discount_paise":       self.discount_paise,
            "proration_credit_paise":self.proration_credit_paise,
            "taxable_paise":        self.taxable_paise,
            "cgst_paise":           self.cgst_paise,
            "sgst_paise":           self.sgst_paise,
            "igst_paise":           self.igst_paise,
            "total_paise":          self.total_paise,
            "plan_code":            self.plan_code,
            "plan_name":            self.plan_name,
            "interval":             self.interval,
            "interval_count":       self.interval_count,
            "extra_users":          self.extra_users,
            "extra_companies":      self.extra_companies,
            "coupon_code":          self.coupon_code,
            "years":                self.years,
            "months":               self.months,
            "buyer_state_code":     self.buyer_state_code,
            "igst_applied":         self.igst_applied,
            "purpose":              self.purpose,
            "price_id":             self.price_id,
        }


async def unused_paid_value(db: AsyncSession, account_id: int, now: datetime) -> int:
    """What the account has paid (before tax) for time it has not used yet: for each paid order, its taxable
    amount times the share of its period still ahead. Orders are given their period when they are fulfilled."""
    orders = (await db.execute(
        select(BillingOrder).where(BillingOrder.account_id == account_id, BillingOrder.status == "paid")
    )).scalars().all()
    unused = Decimal(0)
    for order in orders:
        try:
            data = json.loads(order.quote or "{}")
            start = as_utc(datetime.fromisoformat(data["period_start"]))
            end = as_utc(datetime.fromisoformat(data["period_end"]))
        except (KeyError, TypeError, ValueError):
            continue
        if end <= now or end <= start:
            continue
        ahead = (end - max(now, start)).total_seconds() / (end - start).total_seconds()
        unused += Decimal(order.taxable_paise or 0) * Decimal(str(ahead))
    return _round_paise(unused)


async def calculate_quote(
    db: AsyncSession,
    *,
    plan_id: Union[int, str],
    price_id: Optional[int] = None,
    duration_key: Optional[str] = None,
    extra_users: int = 0,
    extra_companies: int = 0,
    coupon_code: Optional[str] = None,
    account_id: Optional[int] = None,
    buyer_state_code: Optional[str] = None,
    seller_state_code: Optional[str] = None,
) -> QuoteResult:
    """
    Compute an itemised quote for the given plan price + add-ons + coupon.

    Raises ValueError for invalid inputs so callers can return 400.
    """
    if extra_users < 0 or extra_companies < 0:
        raise ValueError("Add-on quantities cannot be negative.")
    if seller_state_code is None:
        seller_state_code = configured_seller_state()

    now = utc_now()
    sub: Optional[AccountSubscription] = None
    if account_id:
        sub = (await db.execute(
            select(AccountSubscription).where(AccountSubscription.account_id == account_id)
        )).scalars().first()
        # The state on the saved billing profile decides the tax, so the invoice and the tax always agree.
        # A state sent with the request is only used while the account has not saved one.
        profile = (await db.execute(
            select(AccountBillingProfile).where(AccountBillingProfile.account_id == account_id)
        )).scalars().first()
        if profile and profile.state_code:
            buyer_state_code = profile.state_code

    sub_end = as_utc(sub.current_period_end) if sub else None
    # A paid term that is still running. A trial, grace, a lapsed or a grandfathered account has none.
    paid_term = bool(sub and sub.status == "active" and sub_end and sub_end > now)

    is_standalone_addon = str(plan_id).lower() in ("addon", "addons")

    plan: Optional[BillingPlan] = None
    price: Optional[BillingPlanPrice] = None

    user_addon = (await db.execute(
        select(BillingAddon).where(BillingAddon.code == "extra_user", BillingAddon.is_active == True)  # noqa: E712
    )).scalars().first()
    company_addon = (await db.execute(
        select(BillingAddon).where(BillingAddon.code == "extra_company", BillingAddon.is_active == True)  # noqa: E712
    )).scalars().first()
    if (extra_users and not user_addon) or (extra_companies and not company_addon):
        raise ValueError("That add-on is not on sale.")

    def addon_unit(addon: Optional[BillingAddon], monthly: bool) -> Decimal:
        if not addon:
            return Decimal(0)
        yearly = Decimal(addon.yearly_paise or 0)
        if not monthly:
            return yearly
        return Decimal(addon.monthly_paise) if addon.monthly_paise else yearly / 12

    if is_standalone_addon:
        # Extra seats on their own: only on top of a running paid term, and only for the days left in it.
        # They never change the plan, the term or whether the account is active.
        if extra_users <= 0 and extra_companies <= 0:
            raise ValueError("At least one add-on user or company seat must be selected.")
        if not paid_term:
            raise ValueError("Add-ons can be bought on their own only while a paid plan is active. "
                             "Choose a plan and add them to it.")
        share = Decimal(str((sub_end - now).total_seconds())) / Decimal(365 * 86400)
        extra_users_paise = _round_paise(addon_unit(user_addon, False) * extra_users * share)
        extra_companies_paise = _round_paise(addon_unit(company_addon, False) * extra_companies * share)
        base_plan_paise = 0
        plan_code, plan_name = "addon", "Add-on Licenses"
        interval, interval_count, years, months = "addon", 0, 0, 0
        purpose = "addon"
    else:
        # ── Load plan ──────────────────────────────────────────────────────────
        if isinstance(plan_id, int):
            plan = (await db.execute(select(BillingPlan).where(BillingPlan.id == plan_id))).scalars().first()
        elif isinstance(plan_id, str):
            if plan_id.isdigit():
                plan = (await db.execute(select(BillingPlan).where(BillingPlan.id == int(plan_id)))).scalars().first()
            if not plan:
                plan = (await db.execute(select(BillingPlan).where(BillingPlan.code == plan_id.lower()))).scalars().first()

        if not plan or not plan.is_active:
            raise ValueError(f"Plan '{plan_id}' not found or inactive.")
        # A plan made for one account can be bought by that account only; other private plans by nobody
        if not plan.is_public and (plan.account_id is None or plan.account_id != account_id):
            raise ValueError(f"Plan '{plan_id}' not found or inactive.")

        # ── Load price ─────────────────────────────────────────────────────────
        if price_id is not None:
            price = (await db.execute(select(BillingPlanPrice).where(BillingPlanPrice.id == price_id))).scalars().first()
            if not price or not price.is_active or price.plan_id != plan.id:
                raise ValueError(f"Price id={price_id} not valid for plan '{plan.code}'.")
        else:
            interval, interval_count = "year", 1
            if duration_key == "monthly":
                interval = "month"
            elif duration_key and "_year" in duration_key:
                first = duration_key.split("_")[0]
                interval_count = int(first) if first.isdigit() else 1
            price = (await db.execute(
                select(BillingPlanPrice).where(
                    BillingPlanPrice.plan_id == plan.id,
                    BillingPlanPrice.interval == interval,
                    BillingPlanPrice.interval_count == interval_count,
                    BillingPlanPrice.is_active == True,  # noqa: E712
                )
            )).scalars().first()
            if not price:
                raise ValueError(f"No price found for plan '{plan.code}' with duration '{duration_key or '1_year'}'.")

        interval, interval_count = price.interval, price.interval_count
        if interval == "year":
            years, months = interval_count, interval_count * 12
        else:
            years, months = 1, interval_count

        # ── What this order is ─────────────────────────────────────────────────
        purpose = "new"
        if paid_term and sub.plan_id:
            if sub.plan_id == plan.id:
                purpose = "renewal"
            else:
                old_plan = (await db.execute(select(BillingPlan).where(BillingPlan.id == sub.plan_id))).scalars().first()
                purpose = "downgrade" if old_plan and plan.sort_order < old_plan.sort_order else "upgrade"
            # Seats already paid for run to the end of the current term, so an order made during it
            # carries them on. They can be dropped once the term has ended.
            extra_users = max(extra_users, sub.extra_users or 0)
            extra_companies = max(extra_companies, sub.extra_companies or 0)

        base_plan_paise = price.amount_paise
        plan_code, plan_name = plan.code, plan.name
        monthly = interval == "month"
        term_units = interval_count if monthly else years
        extra_users_paise = _round_paise(addon_unit(user_addon, monthly) * extra_users * term_units)
        extra_companies_paise = _round_paise(addon_unit(company_addon, monthly) * extra_companies * term_units)

    subtotal_paise = base_plan_paise + extra_users_paise + extra_companies_paise

    # ── Coupon ────────────────────────────────────────────────────────────────
    discount_paise = 0
    coupon_discount_kind: Optional[str] = None
    resolved_coupon: Optional[BillingCoupon] = None

    if coupon_code:
        coupon: Optional[BillingCoupon] = (await db.execute(
            select(BillingCoupon).where(
                BillingCoupon.code == coupon_code,
                BillingCoupon.is_active == True,  # noqa: E712
            )
        )).scalars().first()

        if not coupon:
            raise ValueError(f"Coupon '{coupon_code}' is not valid.")

        now_naive = now.replace(tzinfo=None)
        if coupon.valid_from and now_naive < coupon.valid_from:
            raise ValueError(f"Coupon '{coupon_code}' is not active yet.")

        if coupon.valid_until and now_naive > coupon.valid_until:
            raise ValueError(f"Coupon '{coupon_code}' has expired.")

        # Plan restriction
        if coupon.plan_codes:
            allowed = json.loads(coupon.plan_codes)
            if plan and plan.code not in allowed:
                raise ValueError(f"Coupon '{coupon_code}' is not valid for the {plan.name} plan.")
            elif not plan and "addon" not in allowed:
                raise ValueError(f"Coupon '{coupon_code}' is not valid for add-ons.")

        # First purchase only check
        if coupon.first_purchase_only and account_id:
            prior_order = (await db.execute(
                select(BillingOrder).where(
                    BillingOrder.account_id == account_id,
                    BillingOrder.status == "paid",
                )
            )).scalars().first()
            if prior_order:
                raise ValueError(f"Coupon '{coupon_code}' is only valid for first-time purchases.")

        # Redemption limits
        if coupon.max_redemptions is not None:
            total_redemptions = (await db.execute(
                select(BillingCouponRedemption).where(BillingCouponRedemption.coupon_id == coupon.id)
            )).scalars().all()
            if len(total_redemptions) >= coupon.max_redemptions:
                raise ValueError(f"Coupon '{coupon_code}' has reached its maximum redemptions.")

        if account_id and coupon.per_account_limit:
            account_redemptions = (await db.execute(
                select(BillingCouponRedemption).where(
                    BillingCouponRedemption.coupon_id == coupon.id,
                    BillingCouponRedemption.account_id == account_id,
                )
            )).scalars().all()
            if len(account_redemptions) >= coupon.per_account_limit:
                raise ValueError(f"Coupon '{coupon_code}' has already been used by this account.")

        # Compute discount
        if coupon.kind == "percent":
            raw_discount = Decimal(subtotal_paise) * Decimal(coupon.value) / Decimal(100)
            if coupon.max_discount_paise:
                raw_discount = min(raw_discount, Decimal(coupon.max_discount_paise))
            discount_paise = _round_paise(raw_discount)
        else:  # flat
            discount_paise = min(coupon.value, subtotal_paise)

        coupon_discount_kind = coupon.kind
        resolved_coupon = coupon

    # ── Upgrade credit: the unused part of what was paid for the term being replaced ──
    proration_credit_paise = 0
    if purpose == "upgrade":
        proration_credit_paise = min(await unused_paid_value(db, account_id, now), subtotal_paise - discount_paise)

    taxable_paise = max(0, subtotal_paise - discount_paise - proration_credit_paise)

    # ── Tax split ─────────────────────────────────────────────────────────────
    gst_amount = _round_paise(Decimal(taxable_paise) * GST_RATE / Decimal(100))

    # Same state as the seller: CGST + SGST. Another state, or one we do not know: IGST.
    igst_applied = not (buyer_state_code and seller_state_code and buyer_state_code == seller_state_code)
    if igst_applied:
        igst_paise = gst_amount
        cgst_paise = 0
        sgst_paise = 0
    else:
        igst_paise = 0
        half = _round_paise(Decimal(gst_amount) / 2)
        cgst_paise = half
        sgst_paise = gst_amount - half  # absorb rounding into SGST

    total_paise = taxable_paise + gst_amount

    return QuoteResult(
        base_plan_paise=base_plan_paise,
        extra_users_paise=extra_users_paise,
        extra_companies_paise=extra_companies_paise,
        subtotal_paise=subtotal_paise,
        discount_paise=discount_paise,
        proration_credit_paise=proration_credit_paise,
        taxable_paise=taxable_paise,
        cgst_paise=cgst_paise,
        sgst_paise=sgst_paise,
        igst_paise=igst_paise,
        total_paise=total_paise,
        plan_code=plan_code,
        plan_name=plan_name,
        interval=interval,
        interval_count=interval_count,
        extra_users=extra_users,
        extra_companies=extra_companies,
        coupon_code=coupon_code if resolved_coupon else None,
        coupon_discount_kind=coupon_discount_kind,
        years=years,
        months=months,
        buyer_state_code=buyer_state_code,
        igst_applied=igst_applied,
        purpose=purpose,
        price_id=price.id if price else None,
    )
