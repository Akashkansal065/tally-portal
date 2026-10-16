"""
billing.py – Billing API router (Phase 1: Catalog & Quote, Phase 3: Orders & Gateways).

Public endpoints (no auth required):
  GET  /billing/plans           – plan catalog, prices, add-ons, feature comparison
  POST /billing/quote           – server-side quote calculation
  POST /billing/inquiry         – sales lead / WhatsApp link
  GET  /billing/gateways        – active payment gateways
  POST /billing/webhooks/razorpay – incoming Razorpay webhooks
  POST /billing/webhooks/cashfree – incoming Cashfree webhooks

Auth-required:
  GET  /billing/current-subscription – account plan, usage, limits
  GET  /billing/orders/{order_ref}   – order inspection
  GET  /billing/invoices             – account GST invoices
  GET  /billing/invoices/{id}        – single invoice details
  GET  /billing/profile              – buyer billing profile

Account Admin-required:
  POST /billing/orders               – create order with gateway
  POST /billing/orders/{ref}/confirm – verify payment & activate subscription
  PUT  /billing/profile              – update buyer billing profile
"""

from __future__ import annotations

import json
import urllib.parse
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limiter import limiter
from app.core.logging_config import get_logger
from app.core.permissions import (
    get_current_user,
    get_optional_current_user,
    is_admin_user,
)
from app.models.billing import (
    AccountBillingProfile,
    AccountSubscription,
    BillingAddon,
    BillingInvoice,
    BillingLead,
    BillingOrder,
    BillingPayment,
    BillingPlan,
    BillingPlanGroup,
    BillingPlanPrice,
    BillingRefund,
    BillingSubscriptionEvent,
    BillingWebhookEvent,
)
from app.models.portal_core import Account, Company, User
from app.services.billing.catalog_admin import generate_package_label, migrate_plans_to_groups
from app.services.billing.catalog import (
    get_active_addons,
    get_prices_for_plan,
    get_public_plans,
)
from app.services.billing.credits import get_all_credit_balances
from app.services.billing.entitlements import (
    get_entitlements,
    invalidate_entitlements_cache,
)
from app.services.billing.features import FEATURE_REGISTRY, get_feature
from app.services.billing.gateways.base import GatewayPaymentResult
from app.services.billing.gateways.registry import (
    get_enabled_gateways,
    get_gateway,
)
from app.services.billing.orders import (
    confirm_order,
    create_order,
    fulfil_order,
)
from app.services.billing.invoices import seller_configured, seller_state_code
from app.services.billing.quote import calculate_quote
from app.services.billing.terms import as_utc, utc_now

router = APIRouter(prefix="/billing", tags=["Subscription & Billing"])
logger = get_logger("app.routers.billing")


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS & DEPENDENCIES
# ─────────────────────────────────────────────────────────────────────────────

def _rupees(paise: int) -> float:
    """Convert integer paise to rupees rounded to 2dp."""
    return round(paise / 100, 2)


def sales_contact() -> dict:
    """The sales number from BILLING_SALES_PHONE: for display ("+91 98765 43210") and for wa.me / tel links
    (digits only). Both None when it is not set, so no page shows a number nobody answers."""
    digits = "".join(ch for ch in (settings.BILLING_SALES_PHONE or "") if ch.isdigit())
    if len(digits) < 8:
        return {"sales_phone": None, "sales_whatsapp": None}
    if len(digits) == 12 and digits.startswith("91"):
        display = f"+91 {digits[2:7]} {digits[7:]}"
    else:
        display = f"+{digits}"
    return {"sales_phone": display, "sales_whatsapp": digits}


def checkout_open() -> bool:
    """Paying online is open only when it is switched on, a gateway has its keys, and the seller's legal name
    and GSTIN are set: without those no tax invoice can be issued."""
    return bool(settings.BILLING_CHECKOUT_ENABLED and seller_configured() and get_enabled_gateways())


async def require_account_admin(user: User = Depends(get_current_user)) -> User:
    """Ensure the user is authenticated, has an account_id, and is an account admin."""
    if not user.account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your user is not associated with an account.",
        )
    if not is_admin_user(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only account administrators can purchase or modify plans.",
        )
    return user


def _plan_to_dict(plan: BillingPlan, prices: list[BillingPlanPrice]) -> dict:
    """Serialise a BillingPlan + its prices into the shape the frontend expects."""
    feature_keys = json.loads(plan.feature_keys) if plan.feature_keys else []
    display = json.loads(plan.display) if plan.display else {}

    pricing: dict = {}
    for p in prices:
        if p.interval == "year":
            key = f"{p.interval_count}_year"
            total_rupees = _rupees(p.amount_paise)
            per_month = round(total_rupees / (p.interval_count * 12), 0)
            if p.compare_at_paise:
                savings = _rupees(p.compare_at_paise - p.amount_paise)
                discount_pct = round((savings / _rupees(p.compare_at_paise)) * 100)
            else:
                savings = 0
                discount_pct = 0
            pricing[key] = {
                "price_id": p.id,
                "total": total_rupees,
                "per_month": per_month,
                "discount_pct": discount_pct,
                "savings": savings,
                "autopay_allowed": p.autopay_allowed,
            }
        elif p.interval == "month":
            key = "monthly"
            pricing[key] = {
                "price_id": p.id,
                "total": _rupees(p.amount_paise),
                "autopay_allowed": p.autopay_allowed,
            }

    highlights = display.get("highlights") or [
        get_feature(k).label
        for k in feature_keys
        if get_feature(k) is not None
    ][:5]

    return {
        "id": plan.code,
        "plan_db_id": plan.id,
        "name": plan.name,
        "tagline": plan.tagline,
        "badge": plan.badge,
        "is_popular": display.get("is_popular", False),
        "color": display.get("color", "from-gray-600 to-gray-800"),
        "accent": display.get("accent", "gray"),
        "pricing": pricing,
        "limits": {
            "companies": plan.max_companies,
            "companies_label": "Unlimited Companies" if plan.max_companies is None else f"Up to {plan.max_companies} {'Company' if plan.max_companies == 1 else 'Companies'}",
            "users": plan.max_users,
            "users_label": "Unlimited Users" if plan.max_users is None else f"{plan.max_users} {'User (Admin)' if plan.max_users == 1 else 'Users'} Included",
            "devices_per_user": plan.max_devices,
        },
        "feature_keys": feature_keys,
        "highlights": highlights,
    }


def _addon_to_dict(addon: BillingAddon) -> dict:
    return {
        "id": addon.code,
        "addon_db_id": addon.id,
        "name": addon.name,
        "description": addon.description,
        "kind": addon.kind,
        "unit": f"{'user' if addon.kind == 'seat_user' else 'company'}/year" if addon.kind in ("seat_user", "seat_company") else f"{addon.credit_qty or ''} credits",
        "price_per_year": _rupees(addon.yearly_paise) if addon.yearly_paise else None,
        "price_per_month": _rupees(addon.monthly_paise) if addon.monthly_paise else None,
        "credit_type": addon.credit_type,
        "credit_qty": addon.credit_qty,
    }


def _build_comparison_table() -> list[dict]:
    """Build the feature comparison table from the feature registry."""
    categories: dict[str, list] = {}
    for feat in FEATURE_REGISTRY:
        categories.setdefault(feat.category, []).append(feat)

    result = []
    for cat_name, feats in categories.items():
        rows = []
        for feat in feats:
            rows.append({
                "key": feat.key,
                "name": feat.label,
                "info": feat.info,
            })
        result.append({"category": cat_name, "features": rows})
    return result


# ─────────────────────────────────────────────────────────────────────────────
# PYDANTIC SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class QuoteRequest(BaseModel):
    plan_id: Union[int, str]                    # BillingPlan.id or BillingPlan.code
    price_id: Optional[int] = None              # BillingPlanPrice.id
    duration_key: Optional[str] = None          # "1_year", "2_year", "3_year", "monthly"
    extra_users: int = Field(0, ge=0, le=500)
    extra_companies: int = Field(0, ge=0, le=500)
    coupon_code: Optional[str] = Field(None, max_length=60)
    buyer_state_code: Optional[str] = Field(None, max_length=2)


class SalesInquiryRequest(BaseModel):
    plan_id: str = Field(max_length=60)
    duration_key: str = "1_year"
    customer_name: str = Field(max_length=120)
    customer_phone: str = Field(max_length=30)
    customer_email: Optional[str] = Field(None, max_length=120)
    company_name: Optional[str] = Field(None, max_length=200)
    message: Optional[str] = Field(None, max_length=500)


class CreateOrderRequest(BaseModel):
    plan_id: Union[int, str]
    price_id: Optional[int] = None
    duration_key: Optional[str] = "1_year"
    extra_users: int = Field(0, ge=0, le=500)
    extra_companies: int = Field(0, ge=0, le=500)
    coupon_code: Optional[str] = Field(None, max_length=60)
    gateway: str = Field("razorpay", max_length=30)
    autopay: bool = False
    client_request_key: Optional[str] = Field(None, max_length=64)
    buyer_state_code: Optional[str] = Field(None, max_length=2)
    buyer_snapshot: Optional[Dict[str, Any]] = None


class ConfirmOrderRequest(BaseModel):
    payload: Dict[str, Any]


class BillingProfileUpdateRequest(BaseModel):
    legal_name: Optional[str] = Field(None, max_length=200)
    gstin: Optional[str] = Field(None, max_length=15)
    address: Optional[Dict[str, Any]] = None
    state_code: Optional[str] = Field(None, max_length=2)
    email: Optional[str] = Field(None, max_length=120)
    phone: Optional[str] = Field(None, max_length=20)


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC & CATALOG ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/plans")
async def get_plans_catalog(
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Public endpoint: return all plan groups, packages, prices, dynamic terms,
    add-ons, feature comparison table, and gateway metadata.
    """
    unlinked = (await db.execute(
        select(BillingPlan.id).where(BillingPlan.group_id.is_(None)).limit(1)
    )).scalar()
    if unlinked:
        await migrate_plans_to_groups(db)
        await db.commit()

    account_id = user.account_id if user else None
    addons = await get_active_addons(db)

    stmt = (
        select(BillingPlanGroup)
        .where(
            BillingPlanGroup.is_active == True,
            or_(
                (BillingPlanGroup.is_public == True) & (BillingPlanGroup.account_id.is_(None)),
                BillingPlanGroup.account_id == account_id if account_id else False,
            ),
        )
        .order_by(BillingPlanGroup.sort_order)
    )
    groups = (await db.execute(stmt)).scalars().all()

    plans_out = []
    seen_terms: set[tuple[str, int]] = set()

    for g in groups:
        packages = (await db.execute(
            select(BillingPlan)
            .where(
                BillingPlan.group_id == g.id,
                BillingPlan.is_active == True,
            )
            .order_by(BillingPlan.sort_order, BillingPlan.id)
        )).scalars().all()

        packages_out = []
        for pkg in packages:
            prices = (await db.execute(
                select(BillingPlanPrice)
                .where(
                    BillingPlanPrice.plan_id == pkg.id,
                    BillingPlanPrice.is_active == True,
                )
                .order_by(BillingPlanPrice.interval, BillingPlanPrice.interval_count)
            )).scalars().all()

            if not prices:
                continue

            prices_out = []
            for p in prices:
                seen_terms.add((p.interval, p.interval_count))
                months = p.interval_count * 12 if p.interval == "year" else p.interval_count
                per_month_paise = round(p.amount_paise / (months if months > 0 else 1))
                prices_out.append({
                    "price_id": p.id,
                    "interval": p.interval,
                    "count": p.interval_count,
                    "interval_count": p.interval_count,
                    "amount_paise": p.amount_paise,
                    "amount": round(p.amount_paise / 100, 2),
                    "compare_at_paise": p.compare_at_paise,
                    "compare_at": round(p.compare_at_paise / 100, 2) if p.compare_at_paise else None,
                    "per_month_paise": per_month_paise,
                    "per_month": round(per_month_paise / 100, 2),
                    "autopay_allowed": p.autopay_allowed,
                })

            packages_out.append({
                "id": pkg.id,
                "code": pkg.code,
                "label": pkg.label or generate_package_label(pkg.max_companies, pkg.max_users),
                "max_companies": pkg.max_companies,
                "max_users": pkg.max_users,
                "max_devices": pkg.max_devices,
                "limits": {
                    "companies": pkg.max_companies,
                    "companies_label": "Unlimited Companies" if pkg.max_companies is None else f"Up to {pkg.max_companies} {'Company' if pkg.max_companies == 1 else 'Companies'}",
                    "users": pkg.max_users,
                    "users_label": "Unlimited Users" if pkg.max_users is None else f"{pkg.max_users} {'User (Admin)' if pkg.max_users == 1 else 'Users'} Included",
                    "devices_per_user": pkg.max_devices,
                },
                "prices": prices_out,
            })

        if not packages_out:
            continue

        display = json.loads(g.display) if g.display else {}
        try:
            feature_keys = json.loads(g.feature_keys) if g.feature_keys else []
        except Exception:
            feature_keys = []

        highlights = display.get("highlights") or [
            get_feature(k).label
            for k in feature_keys
            if get_feature(k) is not None
        ][:5]

        first_pkg = packages_out[0]
        legacy_pricing = {}
        for pr in first_pkg["prices"]:
            p_int, p_cnt = pr["interval"], pr["interval_count"]
            # "monthly", "N_month" or "N_year": the duration keys the quote understands
            key = "monthly" if p_int == "month" and p_cnt == 1 else f"{p_cnt}_{p_int}"
            total_rupees = pr["amount"]
            savings = round((pr["compare_at_paise"] - pr["amount_paise"]) / 100, 2) if pr.get("compare_at_paise") else 0
            discount_pct = round((savings / (pr["compare_at_paise"] / 100)) * 100) if pr.get("compare_at_paise") else 0
            legacy_pricing[key] = {
                "price_id": pr["price_id"],
                "total": total_rupees,
                "per_month": pr["per_month"],
                "discount_pct": discount_pct,
                "savings": savings,
                "autopay_allowed": pr["autopay_allowed"],
            }

        plans_out.append({
            "id": g.code,
            "code": g.code,
            "name": g.name,
            "tagline": g.tagline,
            "badge": g.badge,
            "display": display,
            "is_popular": display.get("is_popular", False),
            "color": display.get("color", "from-gray-600 to-gray-800"),
            "accent": display.get("accent", "gray"),
            "border": display.get("border", "border-border"),
            "allow_extra_users": g.allow_extra_users,
            "allow_extra_companies": g.allow_extra_companies,
            "feature_keys": feature_keys,
            "highlights": highlights,
            "features": [
                {"text": get_feature(k).label if get_feature(k) else k, "bold": False}
                for k in feature_keys
            ],
            "packages": packages_out,
            "plan_db_id": first_pkg["id"],
            "limits": first_pkg["limits"],
            "pricing": legacy_pricing,
        })

    def term_sort_key(t: tuple[str, int]) -> int:
        interval, count = t
        return count if interval == "month" else count * 12

    terms_out = []
    for interval, count in sorted(seen_terms, key=term_sort_key):
        if interval == "month":
            label = "Monthly" if count == 1 else f"{count} months"
        else:
            label = "1 year" if count == 1 else f"{count} years"
        terms_out.append({
            "interval": interval,
            "count": count,
            "label": label,
        })

    return {
        "success": True,
        "terms": terms_out,
        "plans": plans_out,
        "addons": [_addon_to_dict(a) for a in addons],
        "comparison": _build_comparison_table(),
        "currency": "INR",
        "currency_symbol": "₹",
        "gst_percentage": 18,
        "checkout_enabled": checkout_open(),
        "autopay_enabled": settings.BILLING_AUTOPAY_ENABLED,
        "gateways": get_enabled_gateways(),
        **sales_contact(),
    }


@router.get("/gateways")
async def get_payment_gateways():
    """Return enabled payment gateways and checkout availability flag."""
    return {
        "success": True,
        "gateways": get_enabled_gateways(),
        "checkout_enabled": checkout_open(),
        "autopay_enabled": settings.BILLING_AUTOPAY_ENABLED,
    }


@router.get("/current-subscription")
async def get_current_subscription(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    The account's plan and usage as the server enforces them.
    Reads from real account_subscriptions and entitlements.
    """
    from app.services.billing.entitlements import get_entitlements
    ent = await get_entitlements(db, user.account_id)

    linked_companies = (await db.execute(
        select(func.count(Company.company_id)).where(
            Company.account_id == user.account_id if user.account_id else Company.company_id == user.company_id,
            Company.is_active == True,  # noqa: E712
        )
    )).scalar() or 0

    active_users = (await db.execute(
        select(func.count(User.user_id)).where(
            User.account_id == user.account_id if user.account_id else User.user_id == user.user_id,
            User.is_active == True,  # noqa: E712
        )
    )).scalar() or 0

    valid_until = None
    if ent.current_period_end:
        valid_until = ent.current_period_end.isoformat()
    elif ent.trial_ends_at:
        valid_until = ent.trial_ends_at.isoformat()

    sub = (await db.execute(
        select(AccountSubscription).where(AccountSubscription.account_id == user.account_id)
    )).scalars().first()

    pkg = None
    if sub and sub.plan_id:
        pkg = (await db.execute(
            select(BillingPlan).where(BillingPlan.id == sub.plan_id)
        )).scalars().first()

    credits = await get_all_credit_balances(db, user.account_id)

    return {
        "success": True,
        "account_id": user.account_id,
        "plan": ent.plan_name,
        "package": pkg.label if pkg else None,
        "tier": ent.plan_code.lower() if ent.plan_code else None,
        "status": ent.status,
        "valid_until": valid_until,
        "usage": {
            "companies_linked": linked_companies,
            "max_companies": ent.max_companies,
            "users_active": active_users,
            "max_users": ent.max_users,
        },
        "features_available": list(ent.features),
        "extra_users": (sub.extra_users or 0) if sub else 0,
        "extra_companies": (sub.extra_companies or 0) if sub else 0,
        "pending_plan_from": sub.pending_effective_at.isoformat() if sub and sub.pending_effective_at else None,
        "autopay": bool(sub.autopay) if sub else False,
        "cancel_at_period_end": bool(sub.cancel_at_period_end) if sub else False,
        "credits": credits,
    }


@router.post("/quote")
@router.post("/calculate-quote")
async def calculate_quote_endpoint(
    req: QuoteRequest,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Server-side itemised quote in integer paise with rupee display fields.
    """
    try:
        quote = await calculate_quote(
            db,
            plan_id=req.plan_id,
            price_id=req.price_id,
            duration_key=req.duration_key,
            extra_users=req.extra_users,
            extra_companies=req.extra_companies,
            coupon_code=req.coupon_code,
            account_id=user.account_id if user else None,
            buyer_state_code=req.buyer_state_code,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    d = quote.as_dict()
    d["extra_users_count"] = quote.extra_users
    d["extra_companies_count"] = quote.extra_companies
    rupee_fields = [
        "base_plan_paise", "extra_users_paise", "extra_companies_paise",
        "subtotal_paise", "discount_paise", "taxable_paise",
        "cgst_paise", "sgst_paise", "igst_paise", "total_paise",
    ]
    for field in rupee_fields:
        d[field.replace("_paise", "")] = round(d[field] / 100, 2)

    d["net_taxable"] = d["taxable"]
    d["gst_amount"] = round((d["cgst_paise"] + d["sgst_paise"] + d["igst_paise"]) / 100, 2)
    d["grand_total"] = d["total"]

    return {"success": True, **d}


@router.post("/inquiry")
@limiter.limit(settings.REGISTER_RATE_LIMIT)
async def create_sales_inquiry(
    request: Request,
    response: Response,
    req: SalesInquiryRequest,
    db: AsyncSession = Depends(get_db),
):
    """Store the lead in billing_leads and return a pre-filled WhatsApp link."""
    duration_label = {"1_year": "1 Year", "2_year": "2 Years", "3_year": "3 Years"}.get(
        req.duration_key, req.duration_key
    )

    lead = BillingLead(
        customer_name=req.customer_name,
        phone=req.customer_phone,
        email=req.customer_email,
        company_name=req.company_name,
        plan_code=req.plan_id,
        duration_key=req.duration_key,
        message=req.message,
        status="new",
    )
    db.add(lead)
    await db.commit()
    # The lead's name and number stay in billing_leads, not in the logs
    logger.info(f"Sales lead #{lead.id}: plan={req.plan_id} term={req.duration_key}")

    wa_message = (
        f"Hello MyTally Team! 🚀\n\n"
        f"I am interested in upgrading to the *{req.plan_id.title()} Plan ({duration_label})* for my business.\n"
        f"• *Name:* {req.customer_name}\n"
        f"• *Phone:* {req.customer_phone}\n"
        + (f"• *Company:* {req.company_name}\n" if req.company_name else "")
        + (f"• *Note:* {req.message}\n" if req.message else "")
        + "\nPlease connect with me regarding activation & onboarding."
    )
    contact = sales_contact()
    whatsapp_url = (f"https://wa.me/{contact['sales_whatsapp']}?text={urllib.parse.quote(wa_message)}"
                    if contact["sales_whatsapp"] else None)

    return {
        "success": True,
        "lead_id": lead.id,
        "message": "Your inquiry has been received. Our sales specialist will reach out shortly.",
        "whatsapp_url": whatsapp_url,
        "sales_phone": contact["sales_phone"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# ORDERS & CHECKOUT (PHASE 3)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/orders")
async def create_order_endpoint(
    req: CreateOrderRequest,
    user: User = Depends(require_account_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new billing order and initialize it with the chosen payment gateway.
    Returns the order reference and the client checkout configuration.
    """
    if req.gateway.lower() == "offline":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Offline payments cannot be self-served. Please contact sales or request manual activation via operator.",
        )

    if not checkout_open():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Online checkout is temporarily disabled. Please contact sales.",
        )

    try:
        order, checkout_config = await create_order(
            db,
            account_id=user.account_id,
            plan_id=req.plan_id,
            price_id=req.price_id,
            duration_key=req.duration_key,
            extra_users=req.extra_users,
            extra_companies=req.extra_companies,
            coupon_code=req.coupon_code,
            gateway_code=req.gateway,
            client_request_key=req.client_request_key,
            buyer_state_code=req.buyer_state_code,
            buyer_snapshot=req.buyer_snapshot,
            autopay=req.autopay,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    return {
        "success": True,
        "order_ref": order.order_ref,
        "total_paise": order.total_paise,
        "total_rupees": round(order.total_paise / 100, 2),
        "status": order.status,
        "gateway": order.gateway,
        "checkout_config": checkout_config,
    }


@router.post("/orders/{order_ref}/confirm")
async def confirm_order_endpoint(
    order_ref: str,
    req: ConfirmOrderRequest,
    user: User = Depends(require_account_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Verify client-submitted payment details server-side and trigger fulfil_order.
    """
    order = (await db.execute(
        select(BillingOrder).where(BillingOrder.order_ref == order_ref)
    )).scalars().first()

    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Order '{order_ref}' not found.")

    if order.account_id != user.account_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    if order.gateway == "offline":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Offline payments cannot be confirmed via customer endpoint. Please contact sales or platform operator.",
        )

    try:
        confirmed = await confirm_order(db, order_ref, req.payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    return {
        "success": True,
        "order_ref": confirmed.order_ref,
        "status": confirmed.status,
        "fulfilled_at": confirmed.fulfilled_at.isoformat() if confirmed.fulfilled_at else None,
    }


@router.get("/orders/{order_ref}")
async def get_order_endpoint(
    order_ref: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Poll or inspect an order's status and payment fulfillment.
    """
    order = (await db.execute(
        select(BillingOrder).where(BillingOrder.order_ref == order_ref)
    )).scalars().first()

    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Order '{order_ref}' not found.")

    # Only the account's own people. Role names are chosen by each account, so none of them may widen this;
    # operators look at other accounts' billing from the operator console.
    if user.account_id is None or order.account_id != user.account_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")

    return {
        "success": True,
        "order_ref": order.order_ref,
        "status": order.status,
        "total_paise": order.total_paise,
        "total_rupees": round(order.total_paise / 100, 2),
        "gateway": order.gateway,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "paid_at": order.paid_at.isoformat() if order.paid_at else None,
        "fulfilled_at": order.fulfilled_at.isoformat() if order.fulfilled_at else None,
    }


@router.post("/subscription/autopay/cancel")
async def cancel_autopay_subscription(
    user: User = Depends(require_account_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Cancel recurring autopay mandate for the account's subscription.
    Leaves subscription active until current_period_end; sets cancel_at_period_end=True.
    """
    sub = (await db.execute(
        select(AccountSubscription).where(AccountSubscription.account_id == user.account_id)
    )).scalars().first()

    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No subscription found for this account.")

    if not sub.autopay and not sub.gateway_subscription_id:
        return {
            "success": True,
            "message": "Autopay is not active for this subscription.",
            "cancel_at_period_end": bool(sub.cancel_at_period_end),
            "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
        }

    # Cancel mandate at the gateway if gateway subscription id is active
    if sub.gateway and sub.gateway_subscription_id:
        try:
            gw = get_gateway(sub.gateway)
            if hasattr(gw, "cancel_subscription"):
                await gw.cancel_subscription(sub.gateway_subscription_id, cancel_at_cycle_end=True)
                logger.info(f"Cancelled mandate {sub.gateway_subscription_id} at gateway {sub.gateway}")
        except Exception as e:
            logger.warning(f"Could not cancel mandate {sub.gateway_subscription_id} at {sub.gateway}: {e}")

    sub.cancel_at_period_end = True
    sub.autopay = False

    # Audit event
    now = datetime.now(timezone.utc)
    event = BillingSubscriptionEvent(
        account_id=user.account_id,
        event_type="autopay_cancelled_by_user",
        from_state=sub.status,
        to_state=sub.status,
        actor_user_id=user.user_id,
        detail=json.dumps({
            "cancelled_at": now.isoformat(),
            "active_until": sub.current_period_end.isoformat() if sub.current_period_end else None,
            "gateway_subscription_id": sub.gateway_subscription_id,
        }),
    )
    db.add(event)
    await db.commit()

    invalidate_entitlements_cache(user.account_id)

    return {
        "success": True,
        "message": "Autopay cancelled successfully. Your plan remains active until the end of the billing period.",
        "cancel_at_period_end": True,
        "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# WEBHOOKS
# ─────────────────────────────────────────────────────────────────────────────

# What each gateway calls the events we act on
_WEBHOOK_EVENTS = {
    "razorpay": {
        "paid": ("payment.captured", "order.paid", "subscription.charged", "subscription.completed"),
        "autopay_authenticated": ("subscription.authenticated", "subscription.activated", "subscription.resumed"),
        "autopay_cancelled": ("subscription.cancelled", "subscription.paused"),
        "autopay_failed": ("subscription.halted", "subscription.payment_failed"),
        "payment_failed": ("payment.failed",),
        "refund": ("refund.processed", "refund.created", "refund.failed"),
        "dispute": (
            "payment.dispute.created",
            "payment.dispute.won",
            "payment.dispute.lost",
            "payment.dispute.closed",
            "payment.dispute.under_review",
            "payment.dispute.action_required",
        ),
    },
    "cashfree": {
        "paid": ("PAYMENT_SUCCESS", "SUBSCRIPTION_CHARGED", "SUBSCRIPTION_PAYMENT_SUCCESS"),
        "autopay_authenticated": ("SUBSCRIPTION_AUTHENTICATED", "SUBSCRIPTION_ACTIVATED"),
        "autopay_cancelled": ("SUBSCRIPTION_CANCELLED", "SUBSCRIPTION_PAUSED"),
        "autopay_failed": ("SUBSCRIPTION_PAYMENT_DECLINED", "SUBSCRIPTION_PAYMENT_FAILED"),
        "payment_failed": ("PAYMENT_FAILED", "PAYMENT_USER_DROPPED"),
        "refund": ("REFUND_PROCESSED", "REFUND_SUCCESS"),
        "dispute": ("DISPUTE_CREATED", "DISPUTE_RESOLVED"),
    },
}


def _webhook_kind(gateway: str, event) -> str:
    for kind, names in _WEBHOOK_EVENTS.get(gateway, {}).items():
        if any(name in event.event_type for name in names):
            return kind
    return "paid" if event.status == "captured" else "other"


async def _subscription_for(db: AsyncSession, gateway: str, gateway_subscription_id: Optional[str]):
    if not gateway_subscription_id:
        return None
    return (await db.execute(
        select(AccountSubscription).where(
            AccountSubscription.gateway == gateway,
            AccountSubscription.gateway_subscription_id == gateway_subscription_id,
        )
    )).scalars().first()


async def _recurring_charge_order(db: AsyncSession, gateway: str, sub: AccountSubscription, event) -> BillingOrder:
    """The order for one debit of an autopay mandate. The amount is what the gateway says it took (tax
    included); the tax is split for the state on the account's billing profile."""
    amount = int(event.amount_paise)
    taxable = int((Decimal(amount) * 100 / 118).quantize(Decimal("1")))
    gst = amount - taxable
    profile = (await db.execute(
        select(AccountBillingProfile).where(AccountBillingProfile.account_id == sub.account_id)
    )).scalars().first()
    buyer_state = profile.state_code if profile else None
    same_state = bool(buyer_state and buyer_state == seller_state_code())
    cgst = gst // 2 if same_state else 0
    price = (await db.execute(
        select(BillingPlanPrice).where(BillingPlanPrice.id == sub.price_id))).scalars().first() if sub.price_id else None
    plan = (await db.execute(select(BillingPlan).where(BillingPlan.id == sub.plan_id))).scalars().first()
    order = BillingOrder(
        order_ref=f"MT_REC_{uuid.uuid4().hex[:10].upper()}",
        account_id=sub.account_id,
        purpose="autopay_charge",
        quote=json.dumps({
            "plan_code": plan.code if plan else None,
            "plan_name": plan.name if plan else None,
            "interval": price.interval if price else "month",
            "interval_count": price.interval_count if price else 1,
            "base_plan_paise": taxable,
            "buyer_state_code": buyer_state,
            "autopay": True,
        }),
        subtotal_paise=taxable,
        taxable_paise=taxable,
        cgst_paise=cgst,
        sgst_paise=(gst - cgst) if same_state else 0,
        igst_paise=0 if same_state else gst,
        total_paise=amount,
        status="pending",
        gateway=gateway,
        gateway_order_id=event.gateway_order_id or f"{gateway}_charge_{event.event_id}",
        buyer_snapshot=json.dumps({f: getattr(profile, f) for f in
                                   ("legal_name", "gstin", "address", "state_code", "email", "phone")} if profile else {}),
        plan_id=sub.plan_id,
        price_id=sub.price_id,
    )
    db.add(order)
    await db.flush()
    return order


async def _act_on_webhook(db: AsyncSession, gateway: str, event, payload: dict) -> Optional[str]:
    """Carry out one verified webhook event. Returns a note when the event was understood but nothing could be
    done with it. Raises when it should be delivered again."""
    kind = _webhook_kind(gateway, event)

    if kind == "paid":
        order = None
        if event.gateway_order_id:
            order = (await db.execute(
                select(BillingOrder).where(
                    BillingOrder.gateway == gateway,
                    or_(BillingOrder.gateway_order_id == event.gateway_order_id,
                        BillingOrder.order_ref == event.gateway_order_id),
                )
            )).scalars().first()
        if not event.gateway_payment_id or not event.amount_paise:
            return "Paid event without a payment id or an amount: nothing recorded."
        # A gateway sends several events for one payment (payment.captured, then subscription.charged or
        # order.paid). Once the payment is recorded the others have nothing left to do, and must be answered
        # 200: failing them would have the gateway retry for a day and then switch the webhook off.
        recorded = (await db.execute(
            select(BillingPayment.order_id).where(
                BillingPayment.gateway == gateway,
                BillingPayment.gateway_payment_id == event.gateway_payment_id,
            )
        )).scalar()
        if recorded is not None and (order is None or order.id == recorded):
            return None
        if not order:
            # A debit of an autopay mandate has no order of ours until now
            sub = await _subscription_for(db, gateway, event.gateway_subscription_id)
            if not sub:
                return f"No order matches gateway order '{event.gateway_order_id}'."
            order = await _recurring_charge_order(db, gateway, sub, event)
        await fulfil_order(db, order.id, gateway_payment=GatewayPaymentResult(
            gateway_payment_id=event.gateway_payment_id,
            status="captured",
            # What the gateway says was paid. fulfil_order refuses it when it is less than the order's total.
            amount_paise=int(event.amount_paise),
            currency="INR",
            raw=payload,
        ))
        return None

    sub = await _subscription_for(db, gateway, event.gateway_subscription_id)

    if kind == "autopay_authenticated" and sub:
        sub.autopay = True
        sub.cancel_at_period_end = False
        db.add(BillingSubscriptionEvent(
            account_id=sub.account_id,
            event_type="autopay_authenticated",
            from_state=sub.status,
            to_state=sub.status,
            detail=json.dumps({
                "event_id": event.event_id,
                "subscription_id": event.gateway_subscription_id,
                "payment_id": event.gateway_payment_id,
            }),
        ))
        await db.commit()
        invalidate_entitlements_cache(sub.account_id)
        return None

    if kind == "autopay_cancelled" and sub:
        sub.cancel_at_period_end = True
        sub.autopay = False
        db.add(BillingSubscriptionEvent(
            account_id=sub.account_id,
            event_type="autopay_cancelled_by_gateway",
            from_state=sub.status,
            to_state=sub.status,
            detail=json.dumps({"event_id": event.event_id}),
        ))
        await db.commit()
        invalidate_entitlements_cache(sub.account_id)
        return None

    if kind == "autopay_failed" and sub and sub.status == "active":
        # The term that was paid for still runs to its end; only then does grace start
        period_end = as_utc(sub.current_period_end)
        if not period_end or period_end <= utc_now():
            sub.status = "grace"
            sub.grace_ends_at = (utc_now() + timedelta(days=7)).replace(tzinfo=None)
        db.add(BillingSubscriptionEvent(
            account_id=sub.account_id,
            event_type="autopay_debit_failed",
            from_state="active",
            to_state=sub.status,
            detail=json.dumps({"event_id": event.event_id}),
        ))
        await db.commit()
        invalidate_entitlements_cache(sub.account_id)
        return None

    if kind == "payment_failed":
        order = None
        if event.gateway_order_id:
            order = (await db.execute(
                select(BillingOrder).where(
                    BillingOrder.gateway == gateway,
                    or_(BillingOrder.gateway_order_id == event.gateway_order_id,
                        BillingOrder.order_ref == event.gateway_order_id),
                )
            )).scalars().first()
        target_account_id = order.account_id if order else (sub.account_id if sub else None)
        if target_account_id:
            logger.warning(f"Payment failed for account {target_account_id}: {event.error_code} - {event.error_description}")
            db.add(BillingSubscriptionEvent(
                account_id=target_account_id,
                event_type="payment_failed",
                order_id=order.id if order else None,
                detail=json.dumps({
                    "event_id": event.event_id,
                    "error_code": event.error_code,
                    "error_description": event.error_description,
                    "gateway_payment_id": event.gateway_payment_id,
                    "gateway_subscription_id": event.gateway_subscription_id,
                }),
            ))
            await db.commit()
        return None

    if kind == "refund" and event.gateway_payment_id:
        pmt = (await db.execute(
            select(BillingPayment).where(
                BillingPayment.gateway == gateway,
                BillingPayment.gateway_payment_id == event.gateway_payment_id,
            )
        )).scalars().first()
        if pmt:
            refund_amt = int(event.amount_paise or 0)
            existing_refund = None
            if event.gateway_refund_id:
                existing_refund = (await db.execute(
                    select(BillingRefund).where(BillingRefund.gateway_refund_id == event.gateway_refund_id)
                )).scalars().first()
            if not existing_refund and event.gateway_refund_id:
                db.add(BillingRefund(
                    payment_id=pmt.id,
                    gateway_refund_id=event.gateway_refund_id,
                    amount_paise=refund_amt,
                    status=event.status or "processed",
                    reason="Processed by gateway webhook",
                ))
            order = (await db.execute(
                select(BillingOrder).where(BillingOrder.id == pmt.order_id)
            )).scalars().first()
            if order:
                db.add(BillingSubscriptionEvent(
                    account_id=order.account_id,
                    event_type="payment_refunded",
                    order_id=order.id,
                    detail=json.dumps({
                        "event_id": event.event_id,
                        "refund_id": event.gateway_refund_id,
                        "amount_paise": refund_amt,
                    }),
                ))
            await db.commit()
        return None

    if kind == "dispute":
        logger.warning(f"Gateway dispute event: {event.event_type} dispute_id={event.gateway_dispute_id} payment_id={event.gateway_payment_id}")
        if event.gateway_payment_id:
            pmt = (await db.execute(
                select(BillingPayment).where(
                    BillingPayment.gateway == gateway,
                    BillingPayment.gateway_payment_id == event.gateway_payment_id,
                )
            )).scalars().first()
            if pmt:
                order = (await db.execute(
                    select(BillingOrder).where(BillingOrder.id == pmt.order_id)
                )).scalars().first()
                if order:
                    db.add(BillingSubscriptionEvent(
                        account_id=order.account_id,
                        event_type=f"dispute_{event.event_type.replace('.', '_')}",
                        order_id=order.id,
                        detail=json.dumps({
                            "event_id": event.event_id,
                            "dispute_id": event.gateway_dispute_id,
                            "payment_id": event.gateway_payment_id,
                        }),
                    ))
                    await db.commit()
        return None

    return None


async def _handle_webhook(gateway: str, secret: Optional[str], request: Request, db: AsyncSession) -> dict:
    """Verify, record and carry out one webhook delivery.

    The event is saved before anything is done with it. If carrying it out fails, everything it did is rolled
    back, the error is noted on the saved event, and the gateway is answered 500 so it delivers again; the
    next delivery finds the event unprocessed and tries again. A processed event is answered 200 and ignored.
    """
    gw = get_gateway(gateway)
    if not gw.is_configured or not secret:
        logger.warning(f"{gw.name} webhook received but its secret is not configured.")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Gateway not configured.")

    body_bytes = await request.body()
    if not gw.verify_webhook(dict(request.headers), body_bytes):
        logger.warning(f"{gw.name} webhook signature verification failed.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook signature.")
    try:
        payload = json.loads(body_bytes.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload.")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload.")

    event = gw.parse_webhook(payload)
    # Razorpay sends the event id in a header, not in the body
    event_id = (request.headers.get("x-razorpay-event-id") if gateway == "razorpay" else None) or event.event_id
    event.event_id = event_id

    saved = (await db.execute(
        select(BillingWebhookEvent).where(
            BillingWebhookEvent.gateway == gateway,
            BillingWebhookEvent.event_id == event_id,
        )
    )).scalars().first()
    if saved and saved.processed:
        return {"success": True, "status": "duplicate"}
    if not saved:
        saved = BillingWebhookEvent(
            gateway=gateway,
            event_id=event_id,
            event_type=event.event_type,
            payload=json.dumps(payload),
            signature_verified=True,
            processed=False,
        )
        db.add(saved)
    await db.commit()
    saved_id = saved.id

    try:
        note = await _act_on_webhook(db, gateway, event, payload)
    except Exception as exc:
        await db.rollback()
        logger.error(f"{gw.name} webhook {event_id} ({event.event_type}) failed: {exc}", exc_info=True)
        await db.execute(update(BillingWebhookEvent).where(BillingWebhookEvent.id == saved_id)
                         .values(processing_error=str(exc)[:500]))
        await db.commit()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="The event could not be processed yet.")

    if note:
        logger.warning(f"{gw.name} webhook {event_id} ({event.event_type}): {note}")
    await db.execute(update(BillingWebhookEvent).where(BillingWebhookEvent.id == saved_id)
                     .values(processed=True, processing_error=note))
    await db.commit()
    return {"success": True, "event_id": event_id}


@router.post("/webhooks/razorpay")
async def razorpay_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Razorpay server-to-server webhook."""
    return await _handle_webhook("razorpay", settings.BILLING_RAZORPAY_WEBHOOK_SECRET, request, db)


@router.post("/webhooks/cashfree")
async def cashfree_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Cashfree server-to-server webhook."""
    return await _handle_webhook("cashfree", settings.BILLING_CASHFREE_SECRET, request, db)


# ─────────────────────────────────────────────────────────────────────────────
# INVOICES & GST (PHASE 4)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/invoices")
async def list_invoices(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List GST tax invoices and credit notes for the current account."""
    if not user.account_id:
        return {"success": True, "invoices": []}

    stmt = (
        select(BillingInvoice, BillingOrder)
        .join(BillingOrder, BillingInvoice.order_id == BillingOrder.id)
        .where(BillingOrder.account_id == user.account_id)
        .order_by(BillingInvoice.id.desc())
    )
    rows = (await db.execute(stmt)).all()
    invoices_out = []
    for inv, order in rows:
        invoices_out.append({
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "kind": inv.kind,
            "order_ref": order.order_ref,
            "date": inv.created_at.isoformat() if inv.created_at else None,
            "place_of_supply": inv.place_of_supply,
            "sac": inv.sac,
            "taxable_paise": inv.taxable_paise,
            "taxable_rupees": round(inv.taxable_paise / 100, 2),
            "cgst_paise": inv.cgst_paise,
            "sgst_paise": inv.sgst_paise,
            "igst_paise": inv.igst_paise,
            "total_paise": inv.total_paise,
            "total_rupees": round(inv.total_paise / 100, 2),
            "lines": json.loads(inv.lines) if inv.lines else [],
            "pdf_path": inv.pdf_path,
        })

    return {"success": True, "invoices": invoices_out}


@router.get("/invoices/{invoice_id}")
async def get_invoice(
    invoice_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve full detail of a specific invoice."""
    stmt = (
        select(BillingInvoice, BillingOrder)
        .join(BillingOrder, BillingInvoice.order_id == BillingOrder.id)
        .where(BillingInvoice.id == invoice_id)
    )
    res = (await db.execute(stmt)).first()
    if not res:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found.")

    inv, order = res
    # Only the account's own people. Role names are chosen by each account, so none of them may widen this;
    # operators look at other accounts' billing from the operator console.
    if user.account_id is None or order.account_id != user.account_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")

    return {
        "success": True,
        "id": inv.id,
        "invoice_number": inv.invoice_number,
        "kind": inv.kind,
        "order_ref": order.order_ref,
        "date": inv.created_at.isoformat() if inv.created_at else None,
        "buyer": json.loads(inv.buyer_snapshot) if inv.buyer_snapshot else {},
        "seller": json.loads(inv.seller_snapshot) if inv.seller_snapshot else {},
        "place_of_supply": inv.place_of_supply,
        "sac": inv.sac,
        "lines": json.loads(inv.lines) if inv.lines else [],
        "taxable_paise": inv.taxable_paise,
        "taxable_rupees": round(inv.taxable_paise / 100, 2),
        "cgst_paise": inv.cgst_paise,
        "sgst_paise": inv.sgst_paise,
        "igst_paise": inv.igst_paise,
        "total_paise": inv.total_paise,
        "total_rupees": round(inv.total_paise / 100, 2),
        "pdf_path": inv.pdf_path,
    }


# ─────────────────────────────────────────────────────────────────────────────
# BUYER BILLING PROFILE
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/profile")
async def get_billing_profile(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the account's GST billing profile (prefilled from primary company if empty)."""
    if not user.account_id:
        return {"success": True, "profile": None}

    profile = (await db.execute(
        select(AccountBillingProfile).where(AccountBillingProfile.account_id == user.account_id)
    )).scalars().first()

    if profile:
        addr = json.loads(profile.address) if profile.address else {}
        return {
            "success": True,
            "profile": {
                "legal_name": profile.legal_name,
                "gstin": profile.gstin,
                "address": addr,
                "state_code": profile.state_code,
                "email": profile.email,
                "phone": profile.phone,
            },
        }

    # Prefill from first active company
    company = (await db.execute(
        select(Company).where(
            Company.account_id == user.account_id,
            Company.is_active == True,
        ).order_by(Company.company_id.asc())
    )).scalars().first()

    prefill = {
        "legal_name": company.name if company else None,
        "gstin": company.gstin if company else None,
        "address": {"state": company.state} if company and company.state else {},
        "state_code": company.gstin[:2] if company and company.gstin and len(company.gstin) >= 2 else None,
        "email": user.email,
        "phone": user.phone,
    }
    return {"success": True, "profile": prefill}


@router.put("/profile")
async def update_billing_profile(
    req: BillingProfileUpdateRequest,
    user: User = Depends(require_account_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update or save the account's GST billing profile."""
    if req.gstin:
        gstin_clean = req.gstin.strip().upper()
        if len(gstin_clean) != 15:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GSTIN must be exactly 15 alphanumeric characters.",
            )
        req.gstin = gstin_clean
        if not req.state_code and gstin_clean[:2].isdigit():
            req.state_code = gstin_clean[:2]

    profile = (await db.execute(
        select(AccountBillingProfile).where(AccountBillingProfile.account_id == user.account_id)
    )).scalars().first()

    if not profile:
        profile = AccountBillingProfile(account_id=user.account_id)
        db.add(profile)

    if req.legal_name is not None:
        profile.legal_name = req.legal_name
    if req.gstin is not None:
        profile.gstin = req.gstin
    if req.address is not None:
        profile.address = json.dumps(req.address)
    if req.state_code is not None:
        profile.state_code = req.state_code
    if req.email is not None:
        profile.email = req.email
    if req.phone is not None:
        profile.phone = req.phone

    await db.commit()
    return {"success": True, "message": "Billing profile updated successfully."}
