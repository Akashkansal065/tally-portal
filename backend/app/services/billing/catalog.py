"""
catalog.py – Billing catalog: load plans, prices and add-ons from the
database and seed Silver / Gold / Diamond / legacy on first boot.

All amounts that go into the DB are INTEGER PAISE.
"""

import json
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import BillingPlan, BillingPlanPrice, BillingAddon
from app.services.billing.features import FEATURE_REGISTRY

logger = logging.getLogger("app.services.billing.catalog")

# ─────────────────────────────────────────────────────────────────────────────
# Seed data (mirrors PLANS_DATA / ADDONS_DATA in the old billing router)
# All prices in PAISE (multiply rupees by 100)
# ─────────────────────────────────────────────────────────────────────────────

_SEED_PLANS = [
    {
        "code": "legacy",
        "name": "Legacy",
        "tagline": "Existing accounts grandfathered on unlimited access",
        "badge": None,
        "max_users": None,
        "max_companies": None,
        "max_devices": None,
        "feature_keys": json.dumps([f.key for f in FEATURE_REGISTRY]),
        "display": json.dumps({"color": "from-gray-600 to-gray-800", "accent": "gray", "is_popular": False}),
        "trial_days": 0,
        "is_public": False,
        "is_active": True,
        "sort_order": 0,
        "prices": [],   # legacy has no price; it has no expiry
    },
    {
        "code": "silver",
        "name": "Silver",
        "tagline": "Ideal for single-firm businesses & retailers beginning their cloud journey",
        "badge": "Starter",
        "max_users": 1,
        "max_companies": 1,
        "max_devices": 3,
        "feature_keys": json.dumps([
            "real_time_sync", "mobile_web_access", "sales_purchase_reports",
            "outstanding_aging", "pdf_whatsapp_share", "daybook_cash_bank",
            "ratio_analysis", "multiple_devices"
        ]),
        "display": json.dumps({"color": "from-slate-600 to-slate-800", "accent": "slate", "is_popular": False}),
        "trial_days": 0,
        "is_public": True,
        "is_active": True,
        "sort_order": 10,
        "prices": [
            # (interval, interval_count, amount_rupees, compare_at_rupees)
            ("month", 1, 299, None),
            ("year", 1, 2499, None),
            ("year", 2, 4199, 4998),
            ("year", 3, 5499, 7497),
        ],
    },
    {
        "code": "gold",
        "name": "Gold",
        "tagline": "For growing distributors & wholesalers with teams and multiple firms",
        "badge": "Most Popular",
        "max_users": 3,
        "max_companies": 5,
        "max_devices": 5,
        "feature_keys": json.dumps([
            "real_time_sync", "mobile_web_access", "sales_purchase_reports",
            "outstanding_aging", "pdf_whatsapp_share", "daybook_cash_bank",
            "ratio_analysis", "multiple_devices", "multi_company_switch",
            "custom_roles_rbac", "salesman_checkin_orders", "stock_dead_fast",
            "auto_payment_reminders", "payment_links_collect", "customer_portal",
            "financial_statements_drilldown", "priority_sync_support"
        ]),
        "display": json.dumps({"color": "from-amber-500 to-yellow-600", "accent": "amber", "is_popular": True}),
        "trial_days": 0,
        "is_public": True,
        "is_active": True,
        "sort_order": 20,
        "prices": [
            ("month", 1, 499, None),
            ("year", 1, 4499, None),
            ("year", 2, 7499, 8998),
            ("year", 3, 9999, 13497),
        ],
    },
    {
        "code": "diamond",
        "name": "Diamond",
        "tagline": "Complete enterprise compliance, unlimited entities & VIP concierge support",
        "badge": "Enterprise",
        "max_users": 10,
        "max_companies": None,   # unlimited
        "max_devices": 10,
        "feature_keys": json.dumps([
            "real_time_sync", "mobile_web_access", "sales_purchase_reports",
            "outstanding_aging", "pdf_whatsapp_share", "daybook_cash_bank",
            "ratio_analysis", "multiple_devices", "multi_company_switch",
            "custom_roles_rbac", "salesman_checkin_orders", "stock_dead_fast",
            "auto_payment_reminders", "payment_links_collect", "customer_portal",
            "financial_statements_drilldown", "priority_sync_support",
            "unlimited_companies", "einvoice_eway_bill", "bank_reconciliation",
            "multi_godown_branch", "audit_trail_deleted_logs", "approval_rules_matrix",
            "dedicated_account_manager", "custom_onboarding_vip"
        ]),
        "display": json.dumps({"color": "from-indigo-600 to-blue-700", "accent": "indigo", "is_popular": False}),
        "trial_days": 0,
        "is_public": True,
        "is_active": True,
        "sort_order": 30,
        "prices": [
            ("month", 1, 999, None),
            ("year", 1, 6999, None),
            ("year", 2, 11999, 13998),
            ("year", 3, 14999, 20997),
        ],
    },
]

_SEED_ADDONS = [
    {
        "code": "extra_user",
        "name": "Additional User License",
        "description": "Add one more team member or salesperson with custom permissions",
        "kind": "seat_user",
        "yearly_rupees": 999,
        "monthly_rupees": 99,
    },
    {
        "code": "extra_company",
        "name": "Additional Tally Company",
        "description": "Connect an additional Tally company to your organization",
        "kind": "seat_company",
        "yearly_rupees": 1499,
        "monthly_rupees": 149,
    },
    {
        "code": "einvoice_pack",
        "name": "E-Invoicing Credits Pack",
        "description": "500 Government GSP E-Invoice IRN & E-Way Bill generation credits",
        "kind": "credit_pack",
        "yearly_rupees": 499,
        "monthly_rupees": None,
        "credit_type": "einvoice",
        "credit_qty": 500,
    },
    {
        "code": "whatsapp_pack",
        "name": "WhatsApp Notification Pack",
        "description": "1,000 Automated WhatsApp payment reminder & statement alerts",
        "kind": "credit_pack",
        "yearly_rupees": 499,
        "monthly_rupees": None,
        "credit_type": "whatsapp",
        "credit_qty": 1000,
    },
]


async def seed_catalog(db: AsyncSession) -> None:
    """
    Idempotent seed: insert Silver/Gold/Diamond/legacy and their prices if they
    do not already exist.  Existing rows are left untouched so live prices
    survive deploys.
    """
    for plan_data in _SEED_PLANS:
        prices = plan_data.get("prices", [])
        existing = (await db.execute(
            select(BillingPlan).where(BillingPlan.code == plan_data["code"])
        )).scalars().first()

        if not existing:
            plan_kwargs = {k: v for k, v in plan_data.items() if k != "prices"}
            plan = BillingPlan(**plan_kwargs)
            db.add(plan)
            await db.flush()   # get plan.id
            plan_id = plan.id
            logger.info(f"Seeded billing plan '{plan_data['code']}' (id={plan_id})")
        else:
            plan_id = existing.id

        # Seed prices
        for (interval, interval_count, amount_rupees, compare_rupees) in prices:
            price_exists = (await db.execute(
                select(BillingPlanPrice).where(
                    BillingPlanPrice.plan_id == plan_id,
                    BillingPlanPrice.interval == interval,
                    BillingPlanPrice.interval_count == interval_count,
                )
            )).scalars().first()

            if not price_exists:
                price = BillingPlanPrice(
                    plan_id=plan_id,
                    interval=interval,
                    interval_count=interval_count,
                    amount_paise=amount_rupees * 100,
                    compare_at_paise=(compare_rupees * 100 if compare_rupees else None),
                    autopay_allowed=(interval == "month"),
                    is_active=True,
                )
                db.add(price)
                logger.info(f"  Seeded price {interval}/{interval_count} = ₹{amount_rupees}")


    for addon_data in _SEED_ADDONS:
        existing = (await db.execute(
            select(BillingAddon).where(BillingAddon.code == addon_data["code"])
        )).scalars().first()

        if not existing:
            addon = BillingAddon(
                code=addon_data["code"],
                name=addon_data["name"],
                description=addon_data.get("description"),
                kind=addon_data["kind"],
                yearly_paise=(addon_data["yearly_rupees"] * 100 if addon_data.get("yearly_rupees") else None),
                monthly_paise=(addon_data["monthly_rupees"] * 100 if addon_data.get("monthly_rupees") else None),
                credit_type=addon_data.get("credit_type"),
                credit_qty=addon_data.get("credit_qty"),
                is_active=True,
                sort_order=_SEED_ADDONS.index(addon_data) * 10,
            )
            db.add(addon)
            logger.info(f"Seeded billing add-on '{addon_data['code']}'")

    await db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Catalog loaders (used by the API endpoints)
# ─────────────────────────────────────────────────────────────────────────────

async def get_public_plans(db: AsyncSession, account_id: Optional[int] = None) -> list[BillingPlan]:
    """
    Return active public plans, plus any custom plans for *account_id*.
    Plans are sorted by sort_order.
    """
    stmt = select(BillingPlan).where(
        BillingPlan.is_active == True,  # noqa: E712
    ).order_by(BillingPlan.sort_order)

    result = await db.execute(stmt)
    plans = result.scalars().all()

    # Filter: either public (no account restriction) or belongs to this account
    visible = [
        p for p in plans
        if p.is_public and p.account_id is None
        or (account_id and p.account_id == account_id)
    ]
    return visible


async def get_prices_for_plan(db: AsyncSession, plan_id: int) -> list[BillingPlanPrice]:
    """Return all active prices for a plan, ordered by interval then interval_count."""
    result = await db.execute(
        select(BillingPlanPrice).where(
            BillingPlanPrice.plan_id == plan_id,
            BillingPlanPrice.is_active == True,  # noqa: E712
        ).order_by(BillingPlanPrice.interval, BillingPlanPrice.interval_count)
    )
    return result.scalars().all()


async def get_active_addons(db: AsyncSession) -> list[BillingAddon]:
    result = await db.execute(
        select(BillingAddon).where(BillingAddon.is_active == True).order_by(BillingAddon.sort_order)  # noqa: E712
    )
    return result.scalars().all()
