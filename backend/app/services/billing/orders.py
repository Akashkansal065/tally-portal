"""
orders.py – Order lifecycle, gateway orchestration, and the single fulfil_order activation path.

What an order does when it is paid is fixed by its `purpose`, and the purpose is decided by the server when
the order is priced (quote.py). Nothing a customer sends can turn an add-on order into a plan term.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.billing import (
    AccountBillingProfile, AccountSubscription, BillingCoupon, BillingCouponRedemption,
    BillingOrder, BillingPayment, BillingPlan, BillingPlanPrice, BillingSubscriptionEvent,
)
from app.models.portal_core import Company, User
from app.services.billing.credits import grant_credits
from app.services.billing.entitlements import invalidate_entitlements_cache
from app.services.billing.gateways.base import GatewayPaymentResult
from app.services.billing.gateways.registry import get_gateway
from app.services.billing.invoices import issue_invoice_for_order, require_seller_configured
from app.services.billing.quote import calculate_quote
from app.services.billing.terms import add_term, as_utc, utc_now

logger = logging.getLogger("app.services.billing.orders")

# The smallest amount a gateway will take
MIN_PAYABLE_PAISE = 100
# Orders that put the account on a plan for a term
PLAN_PURPOSES = ("new", "renewal", "upgrade", "downgrade", "autopay_charge")
BUYER_FIELDS = ("legal_name", "gstin", "address", "state_code", "email", "phone")


def _json(text: Optional[str]) -> dict:
    try:
        return json.loads(text) if text else {}
    except (TypeError, ValueError):
        return {}


async def _buyer_for(db: AsyncSession, account_id: int, given: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Who the invoice is made out to: the saved billing profile, else what came with the order."""
    profile = (await db.execute(
        select(AccountBillingProfile).where(AccountBillingProfile.account_id == account_id)
    )).scalars().first()
    if profile:
        return {field: getattr(profile, field) for field in BUYER_FIELDS}
    return {field: (given or {}).get(field) for field in BUYER_FIELDS if (given or {}).get(field) is not None}


async def _refuse_downgrade_over_limits(db: AsyncSession, account_id: int, plan: BillingPlan,
                                        extra_users: int, extra_companies: int) -> None:
    """A smaller plan cannot be bought while the account uses more than it allows."""
    users = (await db.execute(select(func.count()).select_from(User).where(
        User.account_id == account_id, User.is_active == True))).scalar() or 0  # noqa: E712
    companies = (await db.execute(select(func.count()).select_from(Company).where(
        Company.account_id == account_id, Company.is_active == True))).scalar() or 0  # noqa: E712
    over = []
    if plan.max_users is not None and users > plan.max_users + extra_users:
        over.append(f"{users} active users (the plan allows {plan.max_users + extra_users})")
    if plan.max_companies is not None and companies > plan.max_companies + extra_companies:
        over.append(f"{companies} companies (the plan allows {plan.max_companies + extra_companies})")
    if over:
        raise ValueError(f"The {plan.name} plan is too small for this account: it has {' and '.join(over)}. "
                         "Remove the extra ones or add seats, then try again.")


async def create_order(
    db: AsyncSession,
    *,
    account_id: int,
    plan_id: int | str,
    price_id: Optional[int] = None,
    duration_key: Optional[str] = None,
    extra_users: int = 0,
    extra_companies: int = 0,
    coupon_code: Optional[str] = None,
    gateway_code: str = "razorpay",
    client_request_key: Optional[str] = None,
    buyer_state_code: Optional[str] = None,
    buyer_snapshot: Optional[Dict[str, Any]] = None,
    autopay: bool = False,
    allow_offline: bool = False,
) -> tuple[BillingOrder, Dict[str, Any]]:
    """
    Compute quote, initialize order row, and create order with the payment gateway.
    Returns (order, checkout_config).
    """
    if gateway_code.lower() == "offline" and not allow_offline:
        raise ValueError("Offline gateway is restricted to operator-recorded payments.")
    require_seller_configured()
    if autopay and not settings.BILLING_AUTOPAY_ENABLED:
        raise ValueError("Autopay is not available yet. Please pay for the term and renew before it ends.")

    # 1. The same request sent again gets the order it already made
    if client_request_key:
        existing = (await db.execute(
            select(BillingOrder).where(
                BillingOrder.account_id == account_id,
                BillingOrder.client_request_key == client_request_key,
            )
        )).scalars().first()
        if existing and existing.status == "pending":
            gw = get_gateway(existing.gateway or gateway_code)
            cfg = gw.checkout_config(existing)
            cfg.update(_json(existing.quote).get("checkout_payload") or {})
            return existing, cfg
        if existing:
            raise ValueError("This order has already been completed. Start a new one.")

    # 2. A coupon with a use limit is locked until this order is saved with its reservation, so two orders
    # made at once cannot both take its last use (the quote counts reservations as uses)
    if coupon_code:
        await db.execute(select(BillingCoupon.id).where(BillingCoupon.code == coupon_code).with_for_update())

    # 3. Server-side quote. It also says what the order is: new, renewal, upgrade, downgrade or addon.
    quote = await calculate_quote(
        db,
        plan_id=plan_id,
        price_id=price_id,
        duration_key=duration_key,
        extra_users=extra_users,
        extra_companies=extra_companies,
        coupon_code=coupon_code,
        account_id=account_id,
        buyer_state_code=buyer_state_code,
    )
    if quote.total_paise < MIN_PAYABLE_PAISE:
        raise ValueError("There is nothing to pay for this order. Please contact our team to have it applied.")

    plan: Optional[BillingPlan] = None
    if quote.purpose != "addon":
        plan = (await db.execute(select(BillingPlan).where(BillingPlan.code == quote.plan_code))).scalars().first()
        if not plan:
            raise ValueError(f"Plan '{quote.plan_code}' not found.")
        if quote.purpose == "downgrade":
            await _refuse_downgrade_over_limits(db, account_id, plan, quote.extra_users, quote.extra_companies)
    if autopay:
        price = (await db.execute(
            select(BillingPlanPrice).where(BillingPlanPrice.id == quote.price_id))).scalars().first()
        if not price or not price.autopay_allowed:
            raise ValueError("Recurring autopay is not permitted for the selected plan price.")

    buyer = await _buyer_for(db, account_id, buyer_snapshot)
    # The state the tax was worked out for, so the invoice can never show another
    buyer["state_code"] = quote.buyer_state_code

    quote_dict = quote.as_dict()
    quote_dict["autopay"] = autopay
    now = utc_now()

    order = BillingOrder(
        order_ref=f"MT_{uuid.uuid4().hex[:12].upper()}",
        account_id=account_id,
        purpose=quote.purpose,
        quote=json.dumps(quote_dict),
        subtotal_paise=quote.subtotal_paise,
        discount_paise=quote.discount_paise,
        taxable_paise=quote.taxable_paise,
        cgst_paise=quote.cgst_paise,
        sgst_paise=quote.sgst_paise,
        igst_paise=quote.igst_paise,
        total_paise=quote.total_paise,
        status="pending",
        gateway=gateway_code,
        client_request_key=client_request_key,
        buyer_snapshot=json.dumps(buyer),
        plan_id=plan.id if plan else None,
        price_id=quote.price_id,
        expires_at=now + timedelta(minutes=30),
    )
    db.add(order)
    await db.flush()
    if quote.coupon_code:
        # Reserved now, released if the order expires unpaid (expire_stale_orders)
        coupon_id = (await db.execute(select(BillingCoupon.id).where(BillingCoupon.code == quote.coupon_code))).scalar()
        if coupon_id:
            db.add(BillingCouponRedemption(coupon_id=coupon_id, account_id=account_id, order_id=order.id))
            await db.flush()

    # 4. Create gateway order
    gw = get_gateway(gateway_code)
    gw_res = await gw.create_order(order)
    order.gateway_order_id = gw_res.gateway_order_id
    if gw_res.client_payload:
        # Kept so a repeated request can open the same checkout (Cashfree's payment session)
        quote_dict["checkout_payload"] = gw_res.client_payload
        order.quote = json.dumps(quote_dict)
    await db.commit()

    logger.info(f"Created {order.purpose} order {order.order_ref} (#{order.id}) via {gateway_code} "
                f"(total={order.total_paise} paise)")
    cfg = gw.checkout_config(order)
    cfg.update(gw_res.client_payload or {})
    return order, cfg


async def confirm_order(
    db: AsyncSession,
    order_ref: str,
    client_payload: Dict[str, Any],
) -> BillingOrder:
    """
    Verify client-submitted payment details server-side and trigger fulfil_order.
    """
    order = (await db.execute(
        select(BillingOrder).where(BillingOrder.order_ref == order_ref)
    )).scalars().first()

    if not order:
        raise ValueError(f"Order '{order_ref}' not found.")

    if order.status == "paid":
        return order

    gw = get_gateway(order.gateway or "razorpay")
    payment_result = await gw.confirm_payment(order, client_payload)

    return await fulfil_order(db, order.id, gateway_payment=payment_result)


async def _close_replaced_periods(db: AsyncSession, upgrade: BillingOrder, now: datetime) -> None:
    """An upgrade replaces the running term, and its price already had the unused part of every earlier paid
    order taken off (quote.unused_paid_value). Those orders' periods end now, so a later upgrade cannot credit
    the same money a second time."""
    earlier = (await db.execute(
        select(BillingOrder).where(
            BillingOrder.account_id == upgrade.account_id,
            BillingOrder.status == "paid",
            BillingOrder.id != upgrade.id,
        )
    )).scalars().all()
    for paid in earlier:
        data = _json(paid.quote)
        try:
            end = as_utc(datetime.fromisoformat(data["period_end"]))
        except (KeyError, TypeError, ValueError):
            continue
        if end > now:
            data["period_end"] = now.isoformat()
            data["replaced_by_order"] = upgrade.order_ref
            paid.quote = json.dumps(data)


def _apply_to_subscription(sub: Optional[AccountSubscription], order: BillingOrder, quote_data: dict,
                           plan_id: Optional[int], now: datetime) -> tuple[AccountSubscription, datetime, datetime]:
    """Change the subscription as the paid order says. Returns (subscription, start, end) where start and end
    are the period this order's money covers."""
    purpose = order.purpose
    extra_users = int(quote_data.get("extra_users") or 0)
    extra_companies = int(quote_data.get("extra_companies") or 0)
    sub_end = as_utc(sub.current_period_end) if sub else None
    running = bool(sub and sub.status == "active" and sub_end and sub_end > now)

    if purpose == "addon":
        # Extra seats only: the plan, the term and the status are left exactly as they are
        if not sub:
            raise ValueError("Add-ons need a subscription to be added to.")
        sub.extra_users = (sub.extra_users or 0) + extra_users
        sub.extra_companies = (sub.extra_companies or 0) + extra_companies
        return sub, now, (sub_end if sub_end and sub_end > now else now)

    if purpose not in PLAN_PURPOSES:
        raise ValueError(f"Order {order.order_ref} has an unknown purpose '{purpose}'.")
    if not plan_id:
        raise ValueError(f"Order {order.order_ref} names no plan, so it cannot start a term.")

    interval = "month" if quote_data.get("interval") == "month" else "year"
    count = int(quote_data.get("interval_count") or quote_data.get("years") or 1)
    is_autopay = bool(quote_data.get("autopay") or purpose == "autopay_charge")

    if purpose == "downgrade" and running:
        # Paid now, in force when the running term ends. Until then the account keeps the plan it paid for.
        start, end = sub_end, add_term(sub_end, interval, count)
        sub.pending_plan_id = plan_id
        sub.pending_price_id = order.price_id
        sub.pending_effective_at = start.replace(tzinfo=None)
        sub.current_period_end = end.replace(tzinfo=None)
        return sub, start, end

    # A renewal (or a recurring charge) made while the term runs is added to its end. Everything else
    # starts now: a first purchase, a lapsed account coming back, and an upgrade, which replaces the
    # running term (its unused value was taken off the price).
    stacks = purpose in ("renewal", "autopay_charge") and running
    start = sub_end if stacks else now
    end = add_term(start, interval, count)

    if sub is None:
        sub = AccountSubscription(account_id=order.account_id, extra_users=0, extra_companies=0,
                                  cancel_at_period_end=False, autopay=False)
    if not stacks:
        sub.current_period_start = now.replace(tzinfo=None)
        sub.plan_id = plan_id
        sub.price_id = order.price_id
        sub.pending_plan_id = sub.pending_price_id = sub.pending_effective_at = None
    elif purpose == "renewal":
        sub.price_id = order.price_id or sub.price_id
    sub.status = "active"
    sub.current_period_end = end.replace(tzinfo=None)
    sub.grace_ends_at = None
    sub.trial_ends_at = None
    if purpose != "autopay_charge":
        # The quote already carried on the seats of a running term, so this never takes paid seats away
        sub.extra_users = extra_users
        sub.extra_companies = extra_companies
    sub.gateway = order.gateway or sub.gateway
    if is_autopay:
        sub.autopay = True
        sub.cancel_at_period_end = False
    return sub, start, end


async def fulfil_order(
    db: AsyncSession,
    order_id: int,
    gateway_payment: Optional[GatewayPaymentResult] = None,
) -> BillingOrder:
    """
    The SINGLE activation path for any order. Idempotent.
    Called by confirm endpoint, webhooks, reconciliation worker, and offline actions.

    Nothing is committed unless every step succeeded. A caller that catches an error from here must roll
    the session back before using it again.
    """
    # 1. Lock the order row (SELECT ... FOR UPDATE)
    stmt = select(BillingOrder).where(BillingOrder.id == order_id).with_for_update()
    order = (await db.execute(stmt)).scalars().first()

    if not order:
        raise ValueError(f"Order #{order_id} not found.")

    if order.fulfilled_at is not None or order.status == "paid":
        logger.info(f"Order #{order_id} ({order.order_ref}) already fulfilled at {order.fulfilled_at}")
        return order

    now = utc_now()

    # 2. Ensure payment record and verify amount & status
    if gateway_payment:
        if gateway_payment.status not in ("captured", "paid"):
            raise ValueError(
                f"Cannot fulfil order #{order_id}: payment {gateway_payment.gateway_payment_id} "
                f"is in status '{gateway_payment.status}'; must be 'captured' or 'paid'."
            )
        if (gateway_payment.currency or "INR") != "INR":
            raise ValueError(f"Cannot fulfil order #{order_id}: paid in {gateway_payment.currency}, not INR.")
        if gateway_payment.amount_paise is None or gateway_payment.amount_paise < order.total_paise:
            raise ValueError(
                f"Cannot fulfil order #{order_id}: paid amount ({gateway_payment.amount_paise} paise) "
                f"is less than order total ({order.total_paise} paise)."
            )

        existing_pmt = (await db.execute(
            select(BillingPayment).where(
                BillingPayment.gateway == (order.gateway or "razorpay"),
                BillingPayment.gateway_payment_id == gateway_payment.gateway_payment_id,
            )
        )).scalars().first()

        if existing_pmt:
            if existing_pmt.order_id != order.id:
                logger.error(
                    f"Payment replay attempt! Payment {gateway_payment.gateway_payment_id} "
                    f"already attached to order #{existing_pmt.order_id}, cannot be reused for order #{order.id}"
                )
                raise ValueError(
                    f"Payment {gateway_payment.gateway_payment_id} has already been applied to another order."
                )
        else:
            db.add(BillingPayment(
                order_id=order.id,
                gateway=order.gateway or "razorpay",
                gateway_payment_id=gateway_payment.gateway_payment_id,
                amount_paise=gateway_payment.amount_paise,
                status=gateway_payment.status,
                method=gateway_payment.method,
                raw=json.dumps(gateway_payment.raw or {}),
            ))
            await db.flush()
    elif order.total_paise > 0:
        raise ValueError(f"Cannot fulfil unpaid order #{order_id} without a verified payment record.")

    # 3. Apply subscription change
    quote_data = _json(order.quote)
    sub = (await db.execute(
        select(AccountSubscription).where(AccountSubscription.account_id == order.account_id)
        .with_for_update()
    )).scalars().first()
    old_status = sub.status if sub else None

    plan_id = order.plan_id
    if not plan_id and order.purpose != "addon" and quote_data.get("plan_code"):
        p = (await db.execute(select(BillingPlan).where(BillingPlan.code == quote_data["plan_code"]))).scalars().first()
        plan_id = p.id if p else None

    sub, period_start, period_end = _apply_to_subscription(sub, order, quote_data, plan_id, now)
    db.add(sub)
    if order.purpose == "upgrade":
        await _close_replaced_periods(db, order, now)
    # The period this order's money covers: an upgrade later credits whatever part of it is unused
    quote_data["period_start"] = period_start.isoformat()
    quote_data["period_end"] = period_end.isoformat()
    order.quote = json.dumps(quote_data)
    await db.flush()

    # Credit pack fulfillment
    if order.purpose == "credit_pack" or quote_data.get("credit_type"):
        ctype = quote_data.get("credit_type")
        cqty = quote_data.get("credit_qty") or 0
        if ctype and cqty > 0:
            await grant_credits(
                db,
                account_id=order.account_id,
                credit_type=ctype,
                qty=cqty,
                reason=f"Order {order.order_ref} pack credit",
                reference=order.order_ref,
            )

    # 4. Coupon redemption: normally reserved when the order was made; recorded here when it was not (an order
    # paid after it expired and released its reservation)
    coupon_code = quote_data.get("coupon_code")
    if coupon_code:
        coupon = (await db.execute(
            select(BillingCoupon).where(BillingCoupon.code == coupon_code)
        )).scalars().first()
        reserved = (await db.execute(
            select(BillingCouponRedemption.id).where(BillingCouponRedemption.order_id == order.id)
        )).scalar()
        if coupon and not reserved:
            db.add(BillingCouponRedemption(coupon_id=coupon.id, account_id=order.account_id, order_id=order.id))
            await db.flush()

    # 5. Issue GST Tax Invoice
    invoice = await issue_invoice_for_order(db, order, kind="invoice")

    # 6. Audit event
    event_type = {"addon": "addons_purchased", "downgrade": "downgrade_scheduled"}.get(order.purpose, "plan_purchased")
    db.add(BillingSubscriptionEvent(
        account_id=order.account_id,
        event_type=event_type,
        from_state=old_status,
        to_state=sub.status,
        order_id=order.id,
        detail=json.dumps({
            "order_ref": order.order_ref,
            "invoice_number": invoice.invoice_number,
            "period_end": period_end.isoformat(),
            "total_paise": order.total_paise,
        }),
    ))

    # 7. Mark order fulfilled
    order.status = "paid"
    order.paid_at = now
    order.fulfilled_at = now
    receipt = {"account_id": order.account_id, "order_ref": order.order_ref, "purpose": order.purpose,
               "invoice_number": invoice.invoice_number, "total_paise": order.total_paise,
               "valid_until": as_utc(sub.current_period_end), "email": _json(order.buyer_snapshot).get("email")}
    await db.commit()

    # 8. Post-commit: clear entitlement cache, tell the customer
    invalidate_entitlements_cache(order.account_id)
    logger.info(f"Order {receipt['order_ref']} ({receipt['purpose']}) fulfilled: account #{receipt['account_id']} "
                f"paid until {receipt['valid_until']}")
    from app.services.billing.notices import payment_received
    await payment_received(db, **receipt)
    return order


async def expire_stale_orders(db: AsyncSession) -> int:
    """Mark pending orders whose expires_at is past as expired, and give back the coupon uses they reserved."""
    now = utc_now()
    stale = select(BillingOrder.id).where(BillingOrder.status == "pending", BillingOrder.expires_at < now)
    stale_ids = list((await db.execute(stale)).scalars().all())
    if stale_ids:
        await db.execute(delete(BillingCouponRedemption).where(BillingCouponRedemption.order_id.in_(stale_ids)))
    stmt = (
        update(BillingOrder)
        .where(BillingOrder.id.in_(stale_ids), BillingOrder.status == "pending")
        .values(status="expired")
    )
    result = await db.execute(stmt)
    await db.commit()
    count = result.rowcount or 0
    if count > 0:
        logger.info(f"Expired {count} stale pending billing orders.")
    return count
