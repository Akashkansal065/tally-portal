"""
platform_billing.py – Operator billing management console router.
All routes require an operator console session holding the matching platform permission.

Prefix: /platform/billing
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging_config import get_logger
from app.core.platform_dependencies import PlatformAdminContext, current_admin, require_platform_permission
from app.models.billing import (
    AccountSubscription,
    BillingInvoice,
    BillingLead,
    BillingOrder,
    BillingPayment,
    BillingPlan,
    BillingPlanPrice,
    BillingSubscriptionEvent,
    BillingWebhookEvent,
)
from app.models.portal_core import Account, User
from app.services.billing.entitlements import (
    get_entitlements,
    invalidate_entitlements_cache,
)
from app.services.billing.gateways.base import GatewayPaymentResult
from app.services.billing.orders import create_order, fulfil_order
from app.services.billing.terms import add_term, as_utc, utc_now

router = APIRouter(
    prefix="/platform/billing",
    tags=["Operator Billing Console"],
    dependencies=[Depends(require_platform_permission("billing.manage"))],
)
logger = get_logger("app.routers.platform_billing")


# ─────────────────────────────────────────────────────────────────────────────
# SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class AssignPlanRequest(BaseModel):
    plan_code: str
    duration_years: int = Field(1, ge=1, le=10)
    extra_users: int = Field(0, ge=0, le=500)
    extra_companies: int = Field(0, ge=0, le=500)


class CustomPlanRequest(BaseModel):
    name: str = Field(..., max_length=100)
    tagline: Optional[str] = Field(None, max_length=255)
    max_users: Optional[int] = Field(None, ge=1)
    max_companies: Optional[int] = Field(None, ge=1)
    max_devices: Optional[int] = Field(5, ge=1)
    feature_keys: List[str] = []
    yearly_price_paise: int = Field(..., ge=0)


class SetOverridesRequest(BaseModel):
    overrides: Dict[str, Any]


_LIMIT_OVERRIDES = ("max_users", "max_companies", "max_devices")
_FEATURE_OVERRIDES = ("extra_features", "revoked_features")


def _checked_overrides(overrides: Dict[str, Any]) -> Dict[str, Any]:
    """Only the keys entitlements read, in the shape they are read in. Anything else would be silently
    ignored or, worse, break every request of the account."""
    for key, value in overrides.items():
        if key in _LIMIT_OVERRIDES:
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
                raise HTTPException(status_code=400, detail=f"'{key}' must be a whole number, or null for unlimited.")
        elif key in _FEATURE_OVERRIDES:
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                raise HTTPException(status_code=400, detail=f"'{key}' must be a list of feature keys.")
        else:
            raise HTTPException(status_code=400, detail=f"Unknown override '{key}'.")
    return overrides


async def _account_or_404(db: AsyncSession, account_id: int) -> Account:
    account = (await db.execute(select(Account).where(Account.account_id == account_id))).scalars().first()
    if not account:
        raise HTTPException(status_code=404, detail=f"Account #{account_id} not found.")
    return account


class RecordOfflinePaymentRequest(BaseModel):
    account_id: int
    plan_code: str
    duration_years: int = Field(1, ge=1, le=10)
    extra_users: int = Field(0, ge=0, le=500)
    extra_companies: int = Field(0, ge=0, le=500)
    reference: str = Field(..., max_length=100)
    method: str = Field("neft", max_length=30)
    buyer_state_code: Optional[str] = Field(None, max_length=2)


# ─────────────────────────────────────────────────────────────────────────────
# METRICS & DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/metrics")
async def get_billing_metrics(db: AsyncSession = Depends(get_db)):
    """Aggregate business metrics for platform operators."""
    now = datetime.now(timezone.utc)
    in_30_days = now + timedelta(days=30)
    in_7_days = now + timedelta(days=7)

    # Subscriptions count by status
    status_counts = dict(
        (await db.execute(
            select(AccountSubscription.status, func.count(AccountSubscription.id)).group_by(
                AccountSubscription.status
            )
        )).all()
    )

    # Total orders and revenue
    revenue_paise = (await db.execute(
        select(func.sum(BillingOrder.total_paise)).where(BillingOrder.status == "paid")
    )).scalar() or 0

    paid_orders_count = (await db.execute(
        select(func.count(BillingOrder.id)).where(BillingOrder.status == "paid")
    )).scalar() or 0

    # Subscriptions expiring in next 30 days
    expiring_soon_count = (await db.execute(
        select(func.count(AccountSubscription.id)).where(
            AccountSubscription.status == "active",
            AccountSubscription.current_period_end <= in_30_days,
            AccountSubscription.current_period_end >= now,
        )
    )).scalar() or 0

    # Trials ending in next 7 days
    trials_ending_soon = (await db.execute(
        select(func.count(AccountSubscription.id)).where(
            AccountSubscription.status == "trialing",
            AccountSubscription.trial_ends_at <= in_7_days,
            AccountSubscription.trial_ends_at >= now,
        )
    )).scalar() or 0

    return {
        "success": True,
        "subscriptions": {
            "legacy": status_counts.get("legacy", 0),
            "trialing": status_counts.get("trialing", 0),
            "active": status_counts.get("active", 0),
            "grace": status_counts.get("grace", 0),
            "locked": status_counts.get("locked", 0),
            "cancelled": status_counts.get("cancelled", 0),
        },
        "revenue": {
            "total_paise": revenue_paise,
            "total_rupees": round(revenue_paise / 100, 2),
            "paid_orders": paid_orders_count,
        },
        "alerts": {
            "expiring_in_30_days": expiring_soon_count,
            "trials_ending_in_7_days": trials_ending_soon,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# ACCOUNTS MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/accounts")
async def list_accounts_billing(db: AsyncSession = Depends(get_db)):
    """List all customer accounts with their subscription tier, limits, and lock status."""
    stmt = (
        select(Account, AccountSubscription, BillingPlan)
        .outerjoin(AccountSubscription, Account.account_id == AccountSubscription.account_id)
        .outerjoin(BillingPlan, AccountSubscription.plan_id == BillingPlan.id)
        .order_by(Account.account_id.desc())
    )
    rows = (await db.execute(stmt)).all()

    results = []
    for acc, sub, plan in rows:
        valid_until = None
        if sub and sub.current_period_end:
            valid_until = sub.current_period_end.isoformat()
        elif sub and sub.trial_ends_at:
            valid_until = sub.trial_ends_at.isoformat()

        results.append({
            "account_id": acc.account_id,
            "account_name": acc.name,
            "company_name": acc.name,
            "account_status": acc.status,
            "status": acc.status,
            "subscription_status": sub.status if sub else "unassigned",
            "current_plan": plan.code if plan else "trial",
            "plan_code": plan.code if plan else "trial",
            "plan_name": plan.name if plan else (plan.code.capitalize() if plan else "Trial"),
            "valid_until": valid_until,
            "current_period_end": valid_until,
            "extra_users": sub.extra_users if sub else 0,
            "extra_companies": sub.extra_companies if sub else 0,
            "is_locked": sub.status == "locked" if sub else False,
            "max_users": acc.max_users,
            "max_companies": acc.max_companies,
            "active_users": 0,
            "active_companies": 0,
            "admin_email": "",
        })

    return {"success": True, "accounts": results}


@router.post("/accounts/{account_id}/assign-plan")
async def assign_plan_to_account(
    account_id: int,
    req: AssignPlanRequest,
    ctx: PlatformAdminContext = Depends(current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Operator action: assign or upgrade an account to a specific plan and period."""
    plan = (await db.execute(
        select(BillingPlan).where(BillingPlan.code == req.plan_code)
    )).scalars().first()
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan '{req.plan_code}' not found.")
    await _account_or_404(db, account_id)
    if plan.account_id is not None and plan.account_id != account_id:
        raise HTTPException(status_code=400, detail=f"Plan '{req.plan_code}' was made for another account.")

    sub = (await db.execute(
        select(AccountSubscription).where(AccountSubscription.account_id == account_id)
    )).scalars().first()

    now = utc_now()
    period_end = add_term(now, "year", req.duration_years)
    old_status = sub.status if sub else None

    if sub:
        sub.plan_id = plan.id
        sub.status = "active"
        sub.current_period_start = now
        sub.current_period_end = period_end
        sub.grace_ends_at = None
        sub.trial_ends_at = None
        sub.extra_users = req.extra_users
        sub.extra_companies = req.extra_companies
    else:
        sub = AccountSubscription(
            account_id=account_id,
            plan_id=plan.id,
            status="active",
            current_period_start=now,
            current_period_end=period_end,
            extra_users=req.extra_users,
            extra_companies=req.extra_companies,
        )
        db.add(sub)

    event = BillingSubscriptionEvent(
        account_id=account_id,
        event_type="plan_assigned_by_operator",
        from_state=old_status,
        to_state="active",
        actor_user_id=None,
        detail=json.dumps({
            "plan_code": plan.code,
            "years": req.duration_years,
            "period_end": period_end.isoformat(),
        }),
    )
    db.add(event)
    await db.commit()

    invalidate_entitlements_cache(account_id)
    logger.info(f"Operator {ctx.admin.email} assigned {plan.code} plan to account #{account_id}")

    return {
        "success": True,
        "message": f"Successfully assigned {plan.name} plan for {req.duration_years} year(s).",
        "current_period_end": period_end.isoformat(),
    }


@router.post("/accounts/{account_id}/custom-plan")
async def create_custom_plan_for_account(
    account_id: int,
    req: CustomPlanRequest,
    ctx: PlatformAdminContext = Depends(current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Operator action: create a private tailored plan visible and applicable only to this account."""
    await _account_or_404(db, account_id)
    code = f"custom_{account_id}_{req.name.lower().replace(' ', '_')[:20]}"
    if (await db.execute(select(BillingPlan.id).where(BillingPlan.code == code))).scalars().first():
        raise HTTPException(status_code=409, detail=f"This account already has a custom plan named '{req.name}'.")
    plan = BillingPlan(
        code=code,
        name=req.name,
        tagline=req.tagline or f"Custom plan for account #{account_id}",
        badge="Custom",
        max_users=req.max_users,
        max_companies=req.max_companies,
        max_devices=req.max_devices,
        feature_keys=json.dumps(req.feature_keys),
        display=json.dumps({"color": "from-teal-600 to-emerald-700", "accent": "teal"}),
        trial_days=0,
        is_public=False,
        is_active=True,
        account_id=account_id,
        sort_order=999,
    )
    db.add(plan)
    await db.flush()

    price = BillingPlanPrice(
        plan_id=plan.id,
        interval="year",
        interval_count=1,
        amount_paise=req.yearly_price_paise,
        is_active=True,
    )
    db.add(price)
    await db.commit()

    logger.info(f"Operator {ctx.admin.email} created custom plan '{plan.name}' (#{plan.id}) for account #{account_id}")
    return {
        "success": True,
        "plan_id": plan.id,
        "plan_code": plan.code,
        "price_id": price.id,
        "amount_rupees": round(req.yearly_price_paise / 100, 2),
    }


@router.post("/accounts/{account_id}/overrides")
async def set_account_overrides(
    account_id: int,
    req: SetOverridesRequest,
    ctx: PlatformAdminContext = Depends(current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Operator action: adjust limits or features for one specific account."""
    sub = (await db.execute(
        select(AccountSubscription).where(AccountSubscription.account_id == account_id)
    )).scalars().first()

    if not sub:
        raise HTTPException(status_code=404, detail=f"Subscription for account #{account_id} not found.")

    sub.overrides = json.dumps(_checked_overrides(req.overrides))
    event = BillingSubscriptionEvent(
        account_id=account_id,
        event_type="overrides_updated_by_operator",
        from_state=sub.status,
        to_state=sub.status,
        actor_user_id=None,
        detail=json.dumps(req.overrides),
    )
    db.add(event)
    await db.commit()

    invalidate_entitlements_cache(account_id)
    return {"success": True, "message": "Overrides applied successfully."}


@router.post("/accounts/{account_id}/lock")
async def lock_account_subscription(
    account_id: int,
    ctx: PlatformAdminContext = Depends(current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Operator action: explicitly lock an account (triggers 402 on business routes)."""
    sub = (await db.execute(
        select(AccountSubscription).where(AccountSubscription.account_id == account_id)
    )).scalars().first()

    if not sub:
        raise HTTPException(status_code=404, detail=f"Subscription for account #{account_id} not found.")

    old_status = sub.status
    sub.status = "locked"
    event = BillingSubscriptionEvent(
        account_id=account_id,
        event_type="locked_by_operator",
        from_state=old_status,
        to_state="locked",
        actor_user_id=None,
        detail=json.dumps({"reason": "manual_lock", "operator": ctx.admin.email}),
    )
    db.add(event)
    await db.commit()

    invalidate_entitlements_cache(account_id)
    logger.info(f"Operator {ctx.admin.email} locked account #{account_id}")
    return {"success": True, "message": f"Account #{account_id} is now locked."}


@router.post("/accounts/{account_id}/unlock")
async def unlock_account_subscription(
    account_id: int,
    ctx: PlatformAdminContext = Depends(current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Operator action: unlock a locked account."""
    sub = (await db.execute(
        select(AccountSubscription).where(AccountSubscription.account_id == account_id)
    )).scalars().first()

    if not sub:
        raise HTTPException(status_code=404, detail=f"Subscription for account #{account_id} not found.")

    old_status = sub.status
    # Back to what the account has paid for: active while its term runs, grace once it has ended (the
    # lifecycle worker locks it again when grace runs out), unlimited if it never had a term.
    period_end = as_utc(sub.current_period_end)
    if not period_end:
        sub.status = "legacy"
    elif period_end > utc_now():
        sub.status = "active"
    else:
        sub.status = "grace"
        sub.grace_ends_at = (utc_now() + timedelta(days=7)).replace(tzinfo=None)
    event = BillingSubscriptionEvent(
        account_id=account_id,
        event_type="unlocked_by_operator",
        from_state=old_status,
        to_state=sub.status,
        actor_user_id=None,
        detail=json.dumps({"reason": "manual_unlock", "operator": ctx.admin.email}),
    )
    db.add(event)
    await db.commit()

    invalidate_entitlements_cache(account_id)
    logger.info(f"Operator {ctx.admin.email} unlocked account #{account_id}")
    return {"success": True, "message": f"Account #{account_id} is now unlocked ({sub.status})."}


# ─────────────────────────────────────────────────────────────────────────────
# OFFLINE PAYMENTS & INVOICING
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/offline-payment")
async def record_offline_payment(
    req: RecordOfflinePaymentRequest,
    ctx: PlatformAdminContext = Depends(current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Operator action: record an offline payment (NEFT/RTGS/Cheque/Cash/UPI).
    Creates an order, fulfils it with offline gateway, generates a sequential
    GST invoice, and activates the customer's subscription.
    """
    clean_ref = req.reference.strip().upper()

    # Prevent duplicate offline payment recording for the same UTR / reference
    existing_pmt = (await db.execute(
        select(BillingPayment).where(
            BillingPayment.gateway == "offline",
            BillingPayment.gateway_payment_id == f"OFFLINE_{clean_ref}",
        )
    )).scalars().first()

    if existing_pmt:
        existing_order = (await db.execute(
            select(BillingOrder).where(BillingOrder.id == existing_pmt.order_id)
        )).scalars().first()
        order_info = existing_order.order_ref if existing_order else str(existing_pmt.order_id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An offline payment with reference '{clean_ref}' has already been recorded (Order #{order_info}).",
        )

    await _account_or_404(db, req.account_id)
    try:
        order, _ = await create_order(
            db,
            account_id=req.account_id,
            plan_id=req.plan_code,
            duration_key=f"{req.duration_years}_year",
            extra_users=req.extra_users,
            extra_companies=req.extra_companies,
            gateway_code="offline",
            allow_offline=True,
            buyer_state_code=req.buyer_state_code,
            # One order per payment reference, however often the request is sent
            client_request_key=f"offline:{clean_ref}"[:100],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    pmt = GatewayPaymentResult(
        gateway_payment_id=f"OFFLINE_{req.reference.strip().upper()}",
        status="captured",
        amount_paise=order.total_paise,
        currency="INR",
        method=req.method.lower(),
        raw={"recorded_by": ctx.admin.email, "reference": req.reference},
    )

    try:
        fulfilled_order = await fulfil_order(db, order.id, gateway_payment=pmt)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    # Fetch generated invoice
    inv = (await db.execute(
        select(BillingInvoice).where(BillingInvoice.order_id == fulfilled_order.id)
    )).scalars().first()

    logger.info(
        f"Operator {ctx.admin.email} recorded offline payment ₹{round(order.total_paise / 100, 2)} "
        f"for account #{req.account_id} (Ref: {req.reference})"
    )

    return {
        "success": True,
        "order_ref": fulfilled_order.order_ref,
        "invoice_number": inv.invoice_number if inv else None,
        "total_rupees": round(order.total_paise / 100, 2),
        "status": fulfilled_order.status,
    }


# ─────────────────────────────────────────────────────────────────────────────
# LEADS & WEBHOOK LOGS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/leads")
async def list_sales_leads(db: AsyncSession = Depends(get_db)):
    """List incoming customer purchase and WhatsApp inquiries."""
    leads = (await db.execute(
        select(BillingLead).order_by(BillingLead.id.desc()).limit(100)
    )).scalars().all()

    return {
        "success": True,
        "leads": [
            {
                "id": l.id,
                "name": l.customer_name,
                "phone": l.phone,
                "email": l.email,
                "company": l.company_name,
                "plan_code": l.plan_code,
                "duration_key": l.duration_key,
                "message": l.message,
                "status": l.status,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            }
            for l in leads
        ],
    }


@router.get("/webhooks")
async def list_webhook_events(db: AsyncSession = Depends(get_db)):
    """Inspect recent webhook events from Razorpay and Cashfree."""
    events = (await db.execute(
        select(BillingWebhookEvent).order_by(BillingWebhookEvent.id.desc()).limit(100)
    )).scalars().all()

    return {
        "success": True,
        "events": [
            {
                "id": e.id,
                "gateway": e.gateway,
                "event_id": e.event_id,
                "event_type": e.event_type,
                "signature_verified": e.signature_verified,
                "processed": e.processed,
                "processing_error": e.processing_error,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ],
    }
