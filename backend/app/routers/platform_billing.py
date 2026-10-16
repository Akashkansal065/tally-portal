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
from app.core.platform_audit import write_platform_audit_log
from app.core.platform_dependencies import PlatformAdminContext, current_admin, require_platform_permission
from app.models.billing import (
    AccountSubscription,
    BillingAddon,
    BillingCoupon,
    BillingInvoice,
    BillingLead,
    BillingOrder,
    BillingPayment,
    BillingPlan,
    BillingPlanGroup,
    BillingPlanPrice,
    BillingSubscriptionEvent,
    BillingWebhookEvent,
)
from app.models.portal_core import Account, User
from app.services.billing.catalog_admin import (
    add_price,
    create_package,
    create_plan_group,
    deactivate_price,
    duplicate_package,
    generate_package_label,
    get_catalog_admin_tree,
    get_trial_setting,
    set_package_active,
    set_plan_group_active,
    set_trial_setting,
    update_addon,
    update_package,
    update_plan_group,
    update_price,
)
from app.services.billing.entitlements import (
    get_entitlements,
    invalidate_entitlements_cache,
)
from app.services.billing.gateways.base import GatewayPaymentResult
from app.services.billing.coupons import (
    create_coupon,
    get_coupon_detail,
    list_coupons,
    set_coupon_active,
    update_coupon,
)
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


class CreatePlanGroupRequest(BaseModel):
    code: str
    name: str
    tagline: Optional[str] = None
    badge: Optional[str] = None
    display: Optional[Dict[str, Any]] = None
    features: Optional[List[str]] = None
    trial_days: int = 0
    allow_extra_users: bool = True
    allow_extra_companies: bool = True
    is_public: bool = True
    is_active: bool = True
    account_id: Optional[int] = None
    sort_order: int = 0


class UpdatePlanGroupRequest(BaseModel):
    name: Optional[str] = None
    tagline: Optional[str] = None
    badge: Optional[str] = None
    display: Optional[Dict[str, Any]] = None
    features: Optional[List[str]] = None
    trial_days: Optional[int] = None
    allow_extra_users: Optional[bool] = None
    allow_extra_companies: Optional[bool] = None
    is_public: Optional[bool] = None
    sort_order: Optional[int] = None


class CreatePackageRequest(BaseModel):
    max_companies: int = Field(..., ge=1)
    max_users: int = Field(..., ge=1)
    max_devices: int = Field(..., ge=1)
    label: Optional[str] = None
    code: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True


class UpdatePackageRequest(BaseModel):
    label: Optional[str] = None
    max_companies: Optional[int] = None
    max_users: Optional[int] = None
    max_devices: Optional[int] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class AddPriceRequest(BaseModel):
    interval: str
    interval_count: int = 1
    amount_paise: int
    compare_at_paise: Optional[int] = None
    autopay_allowed: bool = False
    replace: bool = False


class UpdatePriceRequest(BaseModel):
    compare_at_paise: Optional[int] = None
    autopay_allowed: Optional[bool] = None
    amount_paise: Optional[int] = None


class UpdateAddonRequest(BaseModel):
    yearly_paise: Optional[int] = None
    monthly_paise: Optional[int] = None
    is_active: Optional[bool] = None
    description: Optional[str] = None


class TrialSettingRequest(BaseModel):
    package_id: int
    trial_days: int = Field(..., ge=1, le=90)


class CreateCouponRequest(BaseModel):
    code: str
    description: Optional[str] = None
    kind: str = "percent"
    value: int
    max_discount_paise: Optional[int] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    max_redemptions: Optional[int] = None
    per_account_limit: int = 1
    plan_codes: Optional[List[str]] = None
    first_purchase_only: bool = False
    account_id: Optional[int] = None
    is_active: bool = True


class UpdateCouponRequest(BaseModel):
    description: Optional[str] = None
    kind: Optional[str] = None
    value: Optional[int] = None
    max_discount_paise: Optional[int] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    max_redemptions: Optional[int] = None
    per_account_limit: Optional[int] = None
    plan_codes: Optional[List[str]] = None
    first_purchase_only: Optional[bool] = None
    account_id: Optional[int] = None
    is_active: Optional[bool] = None


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
    group = BillingPlanGroup(
        code=f"{code}_grp",
        name=req.name,
        tagline=req.tagline or f"Custom plan for account #{account_id}",
        badge="Custom",
        display=json.dumps({"color": "from-teal-600 to-emerald-700", "accent": "teal"}),
        feature_keys=json.dumps(req.feature_keys),
        trial_days=0,
        allow_extra_users=True,
        allow_extra_companies=True,
        is_public=False,
        is_active=True,
        account_id=account_id,
        sort_order=999,
    )
    db.add(group)
    await db.flush()

    label = generate_package_label(req.max_companies, req.max_users)
    plan = BillingPlan(
        group_id=group.id,
        code=code,
        name=f"{req.name} - {label}",
        label=label,
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
    await db.flush()

    await write_platform_audit_log(
        db=db,
        action_type="billing.custom_plan.create",
        admin_email=ctx.admin.email,
        admin_id=ctx.admin.admin_id,
        session_id=ctx.session.session_id,
        target_type="plan",
        target_id=plan.id,
        target_account_id=account_id,
        new_values={
            "plan_id": plan.id,
            "group_id": group.id,
            "code": plan.code,
            "name": plan.name,
            "yearly_price_paise": req.yearly_price_paise,
        },
    )
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


# ─────────────────────────────────────────────────────────────────────────────
# CATALOG MANAGEMENT (PLAN GROUPS, PACKAGES, PRICES, ADDONS, TRIAL)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/catalog")
async def get_catalog(
    db: AsyncSession = Depends(get_db),
):
    """The whole catalog admin tree: plans -> packages -> prices, add-on rates, trial settings, subscriber count, orders count."""
    return await get_catalog_admin_tree(db)


_GROUP_FIELDS = ("code", "name", "tagline", "badge", "display", "feature_keys", "trial_days", "allow_extra_users",
                 "allow_extra_companies", "is_public", "is_active", "account_id", "sort_order")
_PACKAGE_FIELDS = ("code", "label", "max_companies", "max_users", "max_devices", "is_active", "sort_order")
_PRICE_FIELDS = ("plan_id", "interval", "interval_count", "amount_paise", "compare_at_paise", "autopay_allowed", "is_active")
_ADDON_FIELDS = ("code", "kind", "yearly_paise", "monthly_paise", "is_active", "description")
_COUPON_FIELDS = ("code", "description", "kind", "value", "max_discount_paise", "valid_from", "valid_until",
                  "max_redemptions", "per_account_limit", "plan_codes", "first_purchase_only", "account_id", "is_active")


def _snapshot(row: Any, fields: tuple) -> Dict[str, Any]:
    """The audited fields of a row, as they are now."""
    return {f: getattr(row, f, None) for f in fields}


def _changed(old: Dict[str, Any], new: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Only the fields that differ, before and after."""
    keys = [k for k in new if old.get(k) != new.get(k)]
    return {k: old.get(k) for k in keys}, {k: new.get(k) for k in keys}


async def _load(db: AsyncSession, model, id: int, what: str):
    row = (await db.execute(select(model).where(model.id == id))).scalars().first()
    if not row:
        raise HTTPException(status_code=404, detail=f"{what} {id} not found.")
    return row


async def _audit(db: AsyncSession, ctx: PlatformAdminContext, action: str, target_type: str, target_id: Optional[int],
                 old: Optional[Dict[str, Any]], new: Optional[Dict[str, Any]], account_id: Optional[int] = None) -> None:
    await write_platform_audit_log(
        db=db,
        action_type=action,
        admin_email=ctx.admin.email,
        admin_id=ctx.admin.admin_id,
        session_id=ctx.session.session_id,
        target_type=target_type,
        target_id=target_id,
        target_account_id=account_id,
        old_values=old,
        new_values=new,
    )


def _bad_request(db_error: ValueError) -> HTTPException:
    message = str(db_error)
    return HTTPException(status_code=409 if "already exists" in message.lower() else 400, detail=message)


async def _apply_edit(db: AsyncSession, ctx: PlatformAdminContext, *, model, id: int, what: str, fields: tuple,
                      action: str, target_type: str, change) -> Any:
    """Load the row, run `change`, audit what actually changed (nothing changed writes no audit row),
    commit. A ValueError from `change` becomes a 400 (409 for a duplicate) and nothing is saved."""
    row = await _load(db, model, id, what)
    before = _snapshot(row, fields)
    try:
        row = await change()
    except ValueError as e:
        await db.rollback()
        raise _bad_request(e)
    old, new = _changed(before, _snapshot(row, fields))
    if new:
        await _audit(db, ctx, action, target_type, id, old, new, getattr(row, "account_id", None))
    await db.commit()
    return row


@router.post("/plans")
async def create_plan(
    req: CreatePlanGroupRequest,
    ctx: PlatformAdminContext = Depends(current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a new plan group."""
    try:
        group = await create_plan_group(db, req.model_dump())
    except ValueError as e:
        await db.rollback()
        raise _bad_request(e)
    await _audit(db, ctx, "billing.plan_group.create", "plan_group", group.id, None,
                 _snapshot(group, _GROUP_FIELDS), group.account_id)
    await db.commit()
    return {"success": True, "id": group.id, "code": group.code, "name": group.name}


@router.patch("/plans/{id}")
async def update_plan(
    id: int,
    req: UpdatePlanGroupRequest,
    ctx: PlatformAdminContext = Depends(current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Edit plan group details and features."""
    group = await _apply_edit(db, ctx, model=BillingPlanGroup, id=id, what="Plan", fields=_GROUP_FIELDS,
                              action="billing.plan_group.update", target_type="plan_group",
                              change=lambda: update_plan_group(db, id, req.model_dump(exclude_unset=True)))
    # Features live on the plan, so every account on it may now be entitled to something else
    invalidate_entitlements_cache()
    return {"success": True, "id": group.id, "code": group.code, "name": group.name}


async def _set_plan_active(id: int, is_active: bool, ctx: PlatformAdminContext, db: AsyncSession) -> dict:
    await _apply_edit(db, ctx, model=BillingPlanGroup, id=id, what="Plan", fields=("is_active",),
                      action=f"billing.plan_group.{'activate' if is_active else 'deactivate'}",
                      target_type="plan_group", change=lambda: set_plan_group_active(db, id, is_active))
    return {"success": True, "id": id, "is_active": is_active}


@router.post("/plans/{id}/activate")
async def activate_plan(id: int, ctx: PlatformAdminContext = Depends(current_admin), db: AsyncSession = Depends(get_db)):
    """Activate a plan group (idempotent)."""
    return await _set_plan_active(id, True, ctx, db)


@router.post("/plans/{id}/deactivate")
async def deactivate_plan(id: int, ctx: PlatformAdminContext = Depends(current_admin), db: AsyncSession = Depends(get_db)):
    """Deactivate a plan group (idempotent). Its packages can no longer be bought; current subscribers keep theirs."""
    return await _set_plan_active(id, False, ctx, db)


@router.post("/plans/{id}/packages")
async def create_plan_package(
    id: int,
    req: CreatePackageRequest,
    ctx: PlatformAdminContext = Depends(current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Add a package to a plan group."""
    try:
        pkg = await create_package(db, id, req.model_dump())
    except ValueError as e:
        await db.rollback()
        raise _bad_request(e)
    await _audit(db, ctx, "billing.package.create", "package", pkg.id, None,
                 {"group_id": id, **_snapshot(pkg, _PACKAGE_FIELDS)}, pkg.account_id)
    await db.commit()
    return {"success": True, "id": pkg.id, "code": pkg.code, "label": pkg.label}


@router.patch("/packages/{id}")
async def update_plan_package(
    id: int,
    req: UpdatePackageRequest,
    ctx: PlatformAdminContext = Depends(current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Edit package label and limits (frozen once in use)."""
    pkg = await _apply_edit(db, ctx, model=BillingPlan, id=id, what="Package", fields=_PACKAGE_FIELDS,
                            action="billing.package.update", target_type="package",
                            change=lambda: update_package(db, id, req.model_dump(exclude_unset=True)))
    return {"success": True, "id": pkg.id, "code": pkg.code, "label": pkg.label}


@router.post("/packages/{id}/duplicate")
async def duplicate_plan_package(
    id: int,
    ctx: PlatformAdminContext = Depends(current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Duplicate a package (inactive) with its prices."""
    try:
        new_pkg = await duplicate_package(db, id)
    except ValueError as e:
        await db.rollback()
        raise _bad_request(e)
    await _audit(db, ctx, "billing.package.duplicate", "package", new_pkg.id, {"source_package_id": id},
                 _snapshot(new_pkg, _PACKAGE_FIELDS), new_pkg.account_id)
    await db.commit()
    return {"success": True, "id": new_pkg.id, "code": new_pkg.code, "label": new_pkg.label}


async def _set_package_active(id: int, is_active: bool, ctx: PlatformAdminContext, db: AsyncSession) -> dict:
    await _apply_edit(db, ctx, model=BillingPlan, id=id, what="Package", fields=("is_active",),
                      action=f"billing.package.{'activate' if is_active else 'deactivate'}",
                      target_type="package", change=lambda: set_package_active(db, id, is_active))
    return {"success": True, "id": id, "is_active": is_active}


@router.post("/packages/{id}/activate")
async def activate_plan_package(id: int, ctx: PlatformAdminContext = Depends(current_admin), db: AsyncSession = Depends(get_db)):
    """Activate a package (idempotent)."""
    return await _set_package_active(id, True, ctx, db)


@router.post("/packages/{id}/deactivate")
async def deactivate_plan_package(id: int, ctx: PlatformAdminContext = Depends(current_admin), db: AsyncSession = Depends(get_db)):
    """Deactivate a package (idempotent)."""
    return await _set_package_active(id, False, ctx, db)


@router.post("/packages/{id}/prices")
async def add_package_price(
    id: int,
    req: AddPriceRequest,
    ctx: PlatformAdminContext = Depends(current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Add a price to a package. 409 if the term already has an active price, unless replace=True,
    which retires that price (current subscribers keep it until renewal) and adds this one."""
    try:
        retiring = (await db.execute(select(BillingPlanPrice).where(
            BillingPlanPrice.plan_id == id,
            BillingPlanPrice.interval == req.interval,
            BillingPlanPrice.interval_count == req.interval_count,
            BillingPlanPrice.is_active == True,  # noqa: E712
        ))).scalars().first() if req.replace else None
        old = _snapshot(retiring, _PRICE_FIELDS) | {"id": retiring.id} if retiring else None
        price = await add_price(db, id, req.model_dump())
    except ValueError as e:
        await db.rollback()
        raise _bad_request(e)
    await _audit(db, ctx, "billing.price.replace" if old else "billing.price.create", "price", price.id, old,
                 {"id": price.id, **_snapshot(price, _PRICE_FIELDS)})
    await db.commit()
    return {
        "success": True,
        "id": price.id,
        "package_id": price.plan_id,
        "interval": price.interval,
        "interval_count": price.interval_count,
        "amount_paise": price.amount_paise,
    }


@router.patch("/prices/{id}")
async def update_package_price(
    id: int,
    req: UpdatePriceRequest,
    ctx: PlatformAdminContext = Depends(current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update a price point. Amount is frozen once ordered."""
    price = await _apply_edit(db, ctx, model=BillingPlanPrice, id=id, what="Price", fields=_PRICE_FIELDS,
                              action="billing.price.update", target_type="price",
                              change=lambda: update_price(db, id, req.model_dump(exclude_unset=True)))
    return {
        "success": True,
        "id": price.id,
        "amount_paise": price.amount_paise,
        "compare_at_paise": price.compare_at_paise,
        "autopay_allowed": price.autopay_allowed,
    }


@router.post("/prices/{id}/deactivate")
async def deactivate_package_price(
    id: int,
    ctx: PlatformAdminContext = Depends(current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Retire a price point (idempotent)."""
    await _apply_edit(db, ctx, model=BillingPlanPrice, id=id, what="Price", fields=("is_active",),
                      action="billing.price.deactivate", target_type="price",
                      change=lambda: deactivate_price(db, id))
    return {"success": True, "id": id, "is_active": False}


def _addon_out(a: BillingAddon) -> dict:
    return {
        "id": a.id,
        "code": a.code,
        "name": a.name,
        "kind": a.kind,
        "yearly_paise": a.yearly_paise,
        "monthly_paise": a.monthly_paise,
        "yearly_rupees": (a.yearly_paise / 100) if a.yearly_paise else None,
        "monthly_rupees": (a.monthly_paise / 100) if a.monthly_paise else None,
        "is_active": a.is_active,
        "description": a.description,
    }


@router.get("/addons")
async def list_addons_endpoint(
    db: AsyncSession = Depends(get_db),
):
    """List all add-ons and their current pricing."""
    addons = (await db.execute(select(BillingAddon).order_by(BillingAddon.sort_order, BillingAddon.id))).scalars().all()
    return [_addon_out(a) for a in addons]


@router.patch("/addons/{id}")
async def update_addon_endpoint(
    id: int,
    req: UpdateAddonRequest,
    ctx: PlatformAdminContext = Depends(current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update add-on prices or active status."""
    addon = await _apply_edit(db, ctx, model=BillingAddon, id=id, what="Add-on", fields=_ADDON_FIELDS,
                              action="billing.addon.update", target_type="addon",
                              change=lambda: update_addon(db, id, req.model_dump(exclude_unset=True)))
    return {"success": True, **_addon_out(addon)}


@router.get("/settings/trial")
async def get_trial_setting_endpoint(
    db: AsyncSession = Depends(get_db),
):
    """Get default trial package and trial days."""
    return await get_trial_setting(db)


@router.put("/settings/trial")
async def set_trial_setting_endpoint(
    req: TrialSettingRequest,
    ctx: PlatformAdminContext = Depends(current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Configure default trial package and trial days."""
    old = await get_trial_setting(db)
    try:
        res = await set_trial_setting(db, req.package_id, req.trial_days, user_id=ctx.admin.admin_id)
    except ValueError as e:
        await db.rollback()
        raise _bad_request(e)
    old_changed, new_changed = _changed(old, res)
    if new_changed:
        await _audit(db, ctx, "billing.settings.trial", "setting", None, old_changed, new_changed)
    await db.commit()
    return {"success": True, **res}


# ─────────────────────────────────────────────────────────────────────────────
# COUPONS MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/coupons")
async def get_coupons_endpoint(
    status: Optional[str] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List coupons with calculated status and usage counts."""
    return await list_coupons(db, status_filter=status, search=search)


@router.get("/coupons/{id}")
async def get_coupon_endpoint(
    id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get coupon details and redemption log."""
    try:
        return await get_coupon_detail(db, id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/coupons")
async def create_coupon_endpoint(
    req: CreateCouponRequest,
    ctx: PlatformAdminContext = Depends(current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a new coupon. 409 if code already exists."""
    try:
        coupon = await create_coupon(db, req.model_dump(), created_by_admin_id=ctx.admin.admin_id)
    except ValueError as e:
        await db.rollback()
        raise _bad_request(e)
    await _audit(db, ctx, "billing.coupon.create", "coupon", coupon.id, None,
                 _snapshot(coupon, _COUPON_FIELDS), coupon.account_id)
    await db.commit()
    return {"success": True, "id": coupon.id, "code": coupon.code}


@router.patch("/coupons/{id}")
async def update_coupon_endpoint(
    id: int,
    req: UpdateCouponRequest,
    ctx: PlatformAdminContext = Depends(current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Edit coupon details. Money terms frozen once redeemed."""
    coupon = await _apply_edit(db, ctx, model=BillingCoupon, id=id, what="Coupon", fields=_COUPON_FIELDS,
                               action="billing.coupon.update", target_type="coupon",
                               change=lambda: update_coupon(db, id, req.model_dump(exclude_unset=True)))
    return {"success": True, "id": coupon.id, "code": coupon.code}


async def _set_coupon_active(id: int, is_active: bool, ctx: PlatformAdminContext, db: AsyncSession) -> dict:
    await _apply_edit(db, ctx, model=BillingCoupon, id=id, what="Coupon", fields=("is_active",),
                      action=f"billing.coupon.{'activate' if is_active else 'deactivate'}",
                      target_type="coupon", change=lambda: set_coupon_active(db, id, is_active))
    return {"success": True, "id": id, "is_active": is_active}


@router.post("/coupons/{id}/activate")
async def activate_coupon_endpoint(id: int, ctx: PlatformAdminContext = Depends(current_admin), db: AsyncSession = Depends(get_db)):
    """Activate coupon (idempotent)."""
    return await _set_coupon_active(id, True, ctx, db)


@router.post("/coupons/{id}/deactivate")
async def deactivate_coupon_endpoint(id: int, ctx: PlatformAdminContext = Depends(current_admin), db: AsyncSession = Depends(get_db)):
    """Deactivate coupon (idempotent)."""
    return await _set_coupon_active(id, False, ctx, db)
