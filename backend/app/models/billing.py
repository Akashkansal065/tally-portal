"""
billing.py – SQLAlchemy models for the MyTally billing subsystem.

All money amounts are stored as INTEGER PAISE (1 INR = 100 paise).
NULL on a limit column means unlimited.
Register this module in:
  • main.py         – import so Base.metadata sees the tables
  • database.py     – auto_sync_all_model_schemas
"""

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Index, Integer,
    String, Text, BigInteger, UniqueConstraint,
)
from sqlalchemy.sql import func

from app.core.database import Base
from app.core.config import settings

_DB = settings.PORTAL_DATABASE_NAME  # all billing tables live in the portal schema


# ─────────────────────────────────────────────────────────────────────────────
# CATALOG
# ─────────────────────────────────────────────────────────────────────────────
# CATALOG: PLAN GROUPS, PACKAGES (PLANS) & PRICES
# ─────────────────────────────────────────────────────────────────────────────

class BillingPlanGroup(Base):
    """The customer-facing plan tier (Silver, Gold, Diamond), containing one or more packages."""
    __tablename__ = "billing_plan_groups"
    __table_args__ = (
        UniqueConstraint("code", name="uq_billing_plan_groups_code"),
        {"schema": _DB},
    )

    id                      = Column(Integer, primary_key=True, autoincrement=True)
    code                    = Column(String(60), nullable=False)
    name                    = Column(String(120), nullable=False)
    tagline                 = Column(String(255), nullable=True)
    badge                   = Column(String(80), nullable=True)
    display                 = Column(Text, nullable=True)   # JSON: color, accent, is_popular
    feature_keys            = Column(Text, nullable=True)   # JSON array of feature key strings
    trial_days              = Column(Integer, nullable=False, default=0)
    allow_extra_users       = Column(Boolean, nullable=False, default=True)
    allow_extra_companies   = Column(Boolean, nullable=False, default=True)
    is_public               = Column(Boolean, nullable=False, default=True)
    is_active               = Column(Boolean, nullable=False, default=True)
    account_id              = Column(
        Integer,
        ForeignKey(f"{_DB}.accounts.account_id", ondelete="CASCADE"),
        nullable=True,
    )
    sort_order              = Column(Integer, nullable=False, default=0)
    created_at              = Column(DateTime, server_default=func.now())
    updated_at              = Column(DateTime, server_default=func.now(), onupdate=func.now())


class BillingPlan(Base):
    """A package (combination of companies, users, devices) within a plan tier."""
    __tablename__ = "billing_plans"
    __table_args__ = (
        UniqueConstraint("code", name="uq_billing_plans_code"),
        {"schema": _DB},
    )

    id          = Column(Integer, primary_key=True, autoincrement=True)
    group_id    = Column(
        Integer,
        ForeignKey(f"{_DB}.billing_plan_groups.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    code        = Column(String(60), nullable=False)
    name        = Column(String(120), nullable=False)
    label       = Column(String(120), nullable=True)   # e.g. "1 company + 3 users"
    tagline     = Column(String(255), nullable=True)
    badge       = Column(String(80), nullable=True)

    max_users       = Column(Integer, nullable=True)   # NULL = unlimited
    max_companies   = Column(Integer, nullable=True)
    max_devices     = Column(Integer, nullable=True)

    # JSON array of feature key strings (read from group when group_id is set)
    feature_keys    = Column(Text, nullable=True)
    # JSON: gradient colour, accent, is_popular etc.
    display         = Column(Text, nullable=True)

    trial_days      = Column(Integer, nullable=False, default=0)
    is_public       = Column(Boolean, nullable=False, default=True)
    is_active       = Column(Boolean, nullable=False, default=True)
    sort_order      = Column(Integer, nullable=False, default=0)

    # NULL = global plan; non-null = custom plan visible only to that account
    account_id      = Column(
        Integer,
        ForeignKey(f"{_DB}.accounts.account_id", ondelete="CASCADE"),
        nullable=True,
    )

    created_at  = Column(DateTime, server_default=func.now())
    updated_at  = Column(DateTime, server_default=func.now(), onupdate=func.now())


class BillingPlanPrice(Base):
    """A price point for a plan (interval + interval_count pair)."""
    __tablename__ = "billing_plan_prices"
    __table_args__ = (
        Index("ix_plan_prices_plan_interval_active", "plan_id", "interval", "interval_count", "is_active"),
        {"schema": _DB},
    )

    id              = Column(Integer, primary_key=True, autoincrement=True)
    plan_id         = Column(
        Integer,
        ForeignKey(f"{_DB}.billing_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    interval        = Column(String(10), nullable=False)   # "month" | "year"
    interval_count  = Column(Integer, nullable=False, default=1)

    amount_paise        = Column(BigInteger, nullable=False)
    compare_at_paise    = Column(BigInteger, nullable=True)

    autopay_allowed     = Column(Boolean, nullable=False, default=False)
    # {"razorpay": "plan_...", "cashfree": "plan_..."}
    gateway_plan_refs   = Column(Text, nullable=True)

    is_active           = Column(Boolean, nullable=False, default=True)
    created_at          = Column(DateTime, server_default=func.now())


class BillingAddon(Base):
    """Add-on SKUs: extra user/company seats or credit packs."""
    __tablename__ = "billing_addons"
    __table_args__ = (
        UniqueConstraint("code", name="uq_billing_addons_code"),
        {"schema": _DB},
    )

    id              = Column(Integer, primary_key=True, autoincrement=True)
    code            = Column(String(60), nullable=False)
    name            = Column(String(150), nullable=False)
    description     = Column(String(500), nullable=True)

    kind            = Column(String(30), nullable=False)   # "seat_user" | "seat_company" | "credit_pack"

    yearly_paise    = Column(BigInteger, nullable=True)
    monthly_paise   = Column(BigInteger, nullable=True)

    credit_type     = Column(String(60), nullable=True)   # "einvoice" | "whatsapp"
    credit_qty      = Column(Integer, nullable=True)

    is_active       = Column(Boolean, nullable=False, default=True)
    sort_order      = Column(Integer, nullable=False, default=0)
    created_at      = Column(DateTime, server_default=func.now())


class BillingCoupon(Base):
    """Promotional discount codes."""
    __tablename__ = "billing_coupons"
    __table_args__ = (
        UniqueConstraint("code", name="uq_billing_coupons_code"),
        {"schema": _DB},
    )

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    code                = Column(String(60), nullable=False)
    description         = Column(String(255), nullable=True)

    kind                = Column(String(10), nullable=False)   # "percent" | "flat"
    value               = Column(Integer, nullable=False)
    max_discount_paise  = Column(BigInteger, nullable=True)

    valid_from          = Column(DateTime, nullable=True)
    valid_until         = Column(DateTime, nullable=True)

    max_redemptions     = Column(Integer, nullable=True)
    per_account_limit   = Column(Integer, nullable=False, default=1)

    plan_codes          = Column(Text, nullable=True)   # JSON array; NULL = all plans
    first_purchase_only = Column(Boolean, nullable=False, default=False)
    partner_id          = Column(Integer, nullable=True)
    # NULL = available to all accounts; non-null = private coupon restricted to one account
    account_id          = Column(
        Integer,
        ForeignKey(f"{_DB}.accounts.account_id", ondelete="CASCADE"),
        nullable=True,
    )
    created_by_admin_id = Column(Integer, nullable=True)

    is_active           = Column(Boolean, nullable=False, default=True)
    created_at          = Column(DateTime, server_default=func.now())
    updated_at          = Column(DateTime, server_default=func.now(), onupdate=func.now())


class BillingCouponRedemption(Base):
    """Records each time a coupon is used on an order."""
    __tablename__ = "billing_coupon_redemptions"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_coupon_redemption_order"),
        {"schema": _DB},
    )

    id          = Column(Integer, primary_key=True, autoincrement=True)
    coupon_id   = Column(Integer, ForeignKey(f"{_DB}.billing_coupons.id", ondelete="RESTRICT"), nullable=False, index=True)
    account_id  = Column(Integer, ForeignKey(f"{_DB}.accounts.account_id", ondelete="CASCADE"), nullable=False, index=True)
    order_id    = Column(Integer, nullable=False)
    created_at  = Column(DateTime, server_default=func.now())


# ─────────────────────────────────────────────────────────────────────────────
# PER-ACCOUNT
# ─────────────────────────────────────────────────────────────────────────────

class AccountSubscription(Base):
    """The current subscription row for an account.  One row per account (unique)."""
    __tablename__ = "account_subscriptions"
    __table_args__ = (
        UniqueConstraint("account_id", name="uq_account_subscriptions_account"),
        {"schema": _DB},
    )

    id          = Column(Integer, primary_key=True, autoincrement=True)
    account_id  = Column(
        Integer,
        ForeignKey(f"{_DB}.accounts.account_id", ondelete="CASCADE"),
        nullable=False,
    )
    plan_id     = Column(Integer, ForeignKey(f"{_DB}.billing_plans.id", ondelete="RESTRICT"), nullable=True)
    price_id    = Column(Integer, ForeignKey(f"{_DB}.billing_plan_prices.id", ondelete="RESTRICT"), nullable=True)

    # legacy | trialing | active | grace | locked | cancelled
    status                  = Column(String(20), nullable=False, default="legacy")

    trial_ends_at           = Column(DateTime, nullable=True)
    current_period_start    = Column(DateTime, nullable=True)
    current_period_end      = Column(DateTime, nullable=True)
    grace_ends_at           = Column(DateTime, nullable=True)

    extra_users             = Column(Integer, nullable=False, default=0)
    extra_companies         = Column(Integer, nullable=False, default=0)

    # Operator-level per-account overrides; JSON
    overrides               = Column(Text, nullable=True)

    autopay                 = Column(Boolean, nullable=False, default=False)
    gateway                 = Column(String(20), nullable=True)
    gateway_subscription_id = Column(String(120), nullable=True)
    gateway_customer_id     = Column(String(120), nullable=True)

    cancel_at_period_end    = Column(Boolean, nullable=False, default=False)

    pending_plan_id         = Column(Integer, ForeignKey(f"{_DB}.billing_plans.id"), nullable=True)
    pending_price_id        = Column(Integer, ForeignKey(f"{_DB}.billing_plan_prices.id"), nullable=True)
    # When the pending plan takes over: the end of the term that was running when the downgrade was bought
    pending_effective_at    = Column(DateTime, nullable=True)

    created_at  = Column(DateTime, server_default=func.now())
    updated_at  = Column(DateTime, server_default=func.now(), onupdate=func.now())


class BillingSubscriptionEvent(Base):
    """Append-only audit log of every subscription state change."""
    __tablename__ = "billing_subscription_events"
    __table_args__ = {"schema": _DB}

    id              = Column(Integer, primary_key=True, autoincrement=True)
    account_id      = Column(Integer, ForeignKey(f"{_DB}.accounts.account_id", ondelete="CASCADE"), nullable=False, index=True)
    event_type      = Column(String(60), nullable=False)
    from_state      = Column(String(20), nullable=True)
    to_state        = Column(String(20), nullable=True)
    order_id        = Column(Integer, nullable=True)
    actor_user_id   = Column(Integer, nullable=True)
    detail          = Column(Text, nullable=True)   # JSON
    created_at      = Column(DateTime, server_default=func.now())


class AccountBillingProfile(Base):
    """GST/invoice details for an account (buyer profile)."""
    __tablename__ = "account_billing_profiles"
    __table_args__ = (
        UniqueConstraint("account_id", name="uq_billing_profiles_account"),
        {"schema": _DB},
    )

    id              = Column(Integer, primary_key=True, autoincrement=True)
    account_id      = Column(Integer, ForeignKey(f"{_DB}.accounts.account_id", ondelete="CASCADE"), nullable=False)
    legal_name      = Column(String(200), nullable=True)
    gstin           = Column(String(15), nullable=True)
    address         = Column(Text, nullable=True)    # JSON: {line1, line2, city, pin}
    state_code      = Column(String(2), nullable=True)
    email           = Column(String(120), nullable=True)
    phone           = Column(String(20), nullable=True)
    created_at      = Column(DateTime, server_default=func.now())
    updated_at      = Column(DateTime, server_default=func.now(), onupdate=func.now())


class BillingCreditLedger(Base):
    """Pack credits ledger (e-invoice, WhatsApp). Balance = SUM(delta)."""
    __tablename__ = "billing_credit_ledger"
    __table_args__ = (
        UniqueConstraint("account_id", "credit_type", "reference", name="uq_credit_ledger_ref"),
        {"schema": _DB},
    )

    id              = Column(Integer, primary_key=True, autoincrement=True)
    account_id      = Column(Integer, ForeignKey(f"{_DB}.accounts.account_id", ondelete="CASCADE"), nullable=False, index=True)
    credit_type     = Column(String(60), nullable=False)
    delta           = Column(Integer, nullable=False)
    reason          = Column(String(255), nullable=True)
    reference       = Column(String(120), nullable=False)
    created_at      = Column(DateTime, server_default=func.now())


# ─────────────────────────────────────────────────────────────────────────────
# MONEY MOVEMENT
# ─────────────────────────────────────────────────────────────────────────────

class BillingOrder(Base):
    """An intent to pay; created before the gateway is hit, fulfilled after payment confirmed."""
    __tablename__ = "billing_orders"
    __table_args__ = (
        UniqueConstraint("order_ref", name="uq_billing_orders_ref"),
        UniqueConstraint("gateway", "gateway_order_id", name="uq_billing_orders_gw_order"),
        UniqueConstraint("account_id", "client_request_key", name="uq_billing_orders_idempotency"),
        {"schema": _DB},
    )

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    order_ref           = Column(String(40), nullable=False)

    account_id          = Column(Integer, ForeignKey(f"{_DB}.accounts.account_id", ondelete="RESTRICT"), nullable=False, index=True)

    # new | renewal | upgrade | downgrade | addon | credit_pack | autopay_charge. Decided by the server (quote.py)
    purpose             = Column(String(30), nullable=False, default="new")

    quote               = Column(Text, nullable=True)   # frozen itemised quote JSON

    subtotal_paise      = Column(BigInteger, nullable=False, default=0)
    discount_paise      = Column(BigInteger, nullable=False, default=0)
    taxable_paise       = Column(BigInteger, nullable=False, default=0)
    cgst_paise          = Column(BigInteger, nullable=False, default=0)
    sgst_paise          = Column(BigInteger, nullable=False, default=0)
    igst_paise          = Column(BigInteger, nullable=False, default=0)
    total_paise         = Column(BigInteger, nullable=False, default=0)

    # pending | paid | failed | expired | refunded
    status              = Column(String(20), nullable=False, default="pending")

    gateway             = Column(String(20), nullable=True)
    gateway_order_id    = Column(String(120), nullable=True)
    client_request_key  = Column(String(100), nullable=True)

    buyer_snapshot      = Column(Text, nullable=True)   # JSON

    plan_id             = Column(Integer, nullable=True)
    price_id            = Column(Integer, nullable=True)

    paid_at             = Column(DateTime, nullable=True)
    fulfilled_at        = Column(DateTime, nullable=True)
    expires_at          = Column(DateTime, nullable=True)
    created_at          = Column(DateTime, server_default=func.now())
    updated_at          = Column(DateTime, server_default=func.now(), onupdate=func.now())


class BillingPayment(Base):
    """A payment captured against an order."""
    __tablename__ = "billing_payments"
    __table_args__ = (
        UniqueConstraint("gateway", "gateway_payment_id", name="uq_billing_payments_gw_payment"),
        {"schema": _DB},
    )

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    order_id            = Column(Integer, ForeignKey(f"{_DB}.billing_orders.id", ondelete="RESTRICT"), nullable=False, index=True)
    gateway             = Column(String(20), nullable=False)
    gateway_payment_id  = Column(String(120), nullable=False)
    amount_paise        = Column(BigInteger, nullable=False)
    status              = Column(String(20), nullable=False, default="captured")
    method              = Column(String(50), nullable=True)
    raw                 = Column(Text, nullable=True)   # full gateway response JSON
    created_at          = Column(DateTime, server_default=func.now())


class BillingRefund(Base):
    """A (partial or full) refund against a payment."""
    __tablename__ = "billing_refunds"
    __table_args__ = (
        UniqueConstraint("gateway_refund_id", name="uq_billing_refunds_gw_refund"),
        {"schema": _DB},
    )

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    payment_id          = Column(Integer, ForeignKey(f"{_DB}.billing_payments.id", ondelete="RESTRICT"), nullable=False, index=True)
    gateway_refund_id   = Column(String(120), nullable=False)
    amount_paise        = Column(BigInteger, nullable=False)
    status              = Column(String(20), nullable=False, default="pending")
    reason              = Column(String(255), nullable=True)
    actor_user_id       = Column(Integer, nullable=True)
    created_at          = Column(DateTime, server_default=func.now())


class BillingWebhookEvent(Base):
    """De-dup log for incoming gateway webhook events."""
    __tablename__ = "billing_webhook_events"
    __table_args__ = (
        UniqueConstraint("gateway", "event_id", name="uq_billing_webhooks_gw_event"),
        {"schema": _DB},
    )

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    gateway             = Column(String(20), nullable=False)
    event_id            = Column(String(120), nullable=False)
    event_type          = Column(String(80), nullable=False)
    payload             = Column(Text, nullable=True)
    signature_verified  = Column(Boolean, nullable=False, default=False)
    processed           = Column(Boolean, nullable=False, default=False)
    processing_error    = Column(Text, nullable=True)
    created_at          = Column(DateTime, server_default=func.now())


class BillingInvoice(Base):
    """A tax invoice or credit note for a billing order."""
    __tablename__ = "billing_invoices"
    __table_args__ = (
        UniqueConstraint("invoice_number", name="uq_billing_invoices_number"),
        UniqueConstraint("order_id", "kind", name="uq_billing_invoices_order_kind"),
        {"schema": _DB},
    )

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    invoice_number      = Column(String(40), nullable=False)
    kind                = Column(String(20), nullable=False, default="invoice")
    order_id            = Column(Integer, ForeignKey(f"{_DB}.billing_orders.id", ondelete="RESTRICT"), nullable=False, index=True)

    buyer_snapshot      = Column(Text, nullable=True)
    seller_snapshot     = Column(Text, nullable=True)

    place_of_supply     = Column(String(2), nullable=True)
    sac                 = Column(String(10), nullable=True)

    lines               = Column(Text, nullable=True)   # JSON array

    taxable_paise       = Column(BigInteger, nullable=False, default=0)
    cgst_paise          = Column(BigInteger, nullable=False, default=0)
    sgst_paise          = Column(BigInteger, nullable=False, default=0)
    igst_paise          = Column(BigInteger, nullable=False, default=0)
    total_paise         = Column(BigInteger, nullable=False, default=0)

    pdf_path            = Column(String(500), nullable=True)
    created_at          = Column(DateTime, server_default=func.now())


class BillingInvoiceCounter(Base):
    """Row-locked counter for sequential invoice numbering per financial year."""
    __tablename__ = "billing_invoice_counters"
    __table_args__ = (
        UniqueConstraint("fy", "kind", name="uq_billing_invoice_counters"),
        {"schema": _DB},
    )

    id          = Column(Integer, primary_key=True, autoincrement=True)
    fy          = Column(String(7), nullable=False)    # "2024-25"
    kind        = Column(String(20), nullable=False)   # "invoice" | "credit_note"
    last_number = Column(Integer, nullable=False, default=0)


class BillingLead(Base):
    """Sales/contact inquiries submitted via the pricing page."""
    __tablename__ = "billing_leads"
    __table_args__ = {"schema": _DB}

    id              = Column(Integer, primary_key=True, autoincrement=True)
    customer_name   = Column(String(150), nullable=True)
    phone           = Column(String(30), nullable=True)
    email           = Column(String(120), nullable=True)
    company_name    = Column(String(200), nullable=True)
    plan_code       = Column(String(60), nullable=True)
    duration_key    = Column(String(20), nullable=True)
    message         = Column(Text, nullable=True)
    status          = Column(String(20), nullable=False, default="new")
    created_at      = Column(DateTime, server_default=func.now())
    updated_at      = Column(DateTime, server_default=func.now(), onupdate=func.now())
