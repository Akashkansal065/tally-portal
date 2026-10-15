"""
test_billing_commercial_and_gst.py – Automated tests for Steps 4, 5, and 6:
- Dynamic seller snapshot & GST invoice prefix from app settings
- Profile-based place of supply & buyer snapshot propagation
- Coupon lifecycle: valid_from, valid_until, and first_purchase_only checks
- Standalone add-ons quote & fulfillment (incrementing extra seats)
- Scheduled downgrades preserving active plan and setting pending_plan_id
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update

import app.models.portal_core as P
from app.core.config import settings
from app.models.billing import (
    AccountBillingProfile,
    AccountSubscription,
    BillingCoupon,
    BillingInvoice,
    BillingOrder,
    BillingPlan,
    BillingPlanPrice,
)
from app.services.billing.gateways.base import GatewayOrderResult, GatewayPaymentResult
from app.services.billing.invoices import issue_invoice_for_order
from app.services.billing.orders import create_order, fulfil_order
from app.services.billing.quote import calculate_quote
from tests.conftest import run


@pytest.fixture(autouse=True)
def mock_razorpay_gateway(monkeypatch):
    async def mock_create_order(self, order):
        return GatewayOrderResult(
            gateway_order_id=f"rzp_order_{order.order_ref}",
            client_payload={"order_id": f"rzp_order_{order.order_ref}"},
            raw={},
        )

    async def mock_confirm_payment(self, order, client_payload):
        return GatewayPaymentResult(
            gateway_payment_id="pay_mock_commercial_123",
            status="captured",
            amount_paise=order.total_paise,
            currency="INR",
            method="card",
            raw={},
        )

    from app.services.billing.gateways.razorpay import RazorpayBillingGateway
    monkeypatch.setattr(RazorpayBillingGateway, "create_order", mock_create_order)
    monkeypatch.setattr(RazorpayBillingGateway, "confirm_payment", mock_confirm_payment)


def make_account(harness, name="CommercialAccount"):
    account = harness.add(P.Account(name=name, status="active"))
    company = harness.company(name)
    role = harness.role("Admin")
    user = harness.user(company, role, f"user_{name.lower()}@test.com")
    harness.execute(update(P.Company).where(P.Company.company_id == company.company_id).values(account_id=account.account_id))
    harness.execute(update(P.User).where(P.User.user_id == user.user_id).values(account_id=account.account_id))
    harness.execute(update(P.Role).where(P.Role.role_id == role.role_id).values(account_id=account.account_id))
    return account, user


def test_seller_gst_and_invoice_prefix(harness):
    """Verify that seller GST snapshot and invoice sequential numbering use settings."""
    account, _ = make_account(harness, "SellerGstAcct")

    async def _test():
        async with harness.Session() as db:
            order, _ = await create_order(
                db,
                account_id=account.account_id,
                plan_id="silver",
                duration_key="1_year",
            )
            invoice = await issue_invoice_for_order(db, order, kind="invoice")

            # Check seller snapshot
            seller = json.loads(invoice.seller_snapshot)
            assert seller["legal_name"] == settings.BILLING_SELLER_NAME
            assert seller["gstin"] == settings.BILLING_SELLER_GSTIN
            assert seller["state_code"] == "07"

            # Check prefix
            assert invoice.invoice_number.startswith(settings.BILLING_INVOICE_PREFIX)

    run(_test())


def test_buyer_profile_propagates_state_and_snapshot(harness):
    """Verify that AccountBillingProfile automatically determines place of supply."""
    account, _ = make_account(harness, "BuyerProfileAcct")

    async def _test():
        async with harness.Session() as db:
            # Create a billing profile with Maharashtra state code (27)
            profile = AccountBillingProfile(
                account_id=account.account_id,
                legal_name="Maharashtra Traders LLP",
                gstin="27ABCDE1234F1Z5",
                state_code="27",
                address=json.dumps({"city": "Mumbai", "pincode": "400001"}),
                email="accounts@maharashtratraders.in",
            )
            db.add(profile)
            await db.flush()

            # Quote without explicit state should automatically resolve to 27 (IGST applied because seller is 07 Delhi)
            q = await calculate_quote(
                db,
                plan_id="silver",
                duration_key="1_year",
                account_id=account.account_id,
            )
            assert q.buyer_state_code == "27"
            assert q.igst_applied is True
            assert q.igst_paise > 0
            assert q.cgst_paise == 0

            # Create order and issue invoice
            order, _ = await create_order(
                db,
                account_id=account.account_id,
                plan_id="silver",
                duration_key="1_year",
            )
            buyer_snap = json.loads(order.buyer_snapshot)
            assert buyer_snap["legal_name"] == "Maharashtra Traders LLP"
            assert buyer_snap["gstin"] == "27ABCDE1234F1Z5"

            inv = await issue_invoice_for_order(db, order, kind="invoice")
            assert inv.place_of_supply == "27"

    run(_test())


def test_coupon_valid_from_and_until_enforced(harness):
    """Verify that coupons before valid_from or after valid_until are rejected."""
    account, _ = make_account(harness, "CouponDatesAcct")

    async def _test():
        async with harness.Session() as db:
            now = datetime.now(timezone.utc).replace(tzinfo=None)

            # Future coupon
            future_coupon = BillingCoupon(
                code="FUTURE50",
                kind="percent",
                value=50,
                valid_from=now + timedelta(days=5),
                is_active=True,
            )
            # Expired coupon
            expired_coupon = BillingCoupon(
                code="EXPIRED50",
                kind="percent",
                value=50,
                valid_until=now - timedelta(days=2),
                is_active=True,
            )
            db.add(future_coupon)
            db.add(expired_coupon)
            await db.flush()

            with pytest.raises(ValueError, match="not active yet"):
                await calculate_quote(
                    db,
                    plan_id="silver",
                    duration_key="1_year",
                    coupon_code="FUTURE50",
                )

            with pytest.raises(ValueError, match="has expired"):
                await calculate_quote(
                    db,
                    plan_id="silver",
                    duration_key="1_year",
                    coupon_code="EXPIRED50",
                )

    run(_test())


def test_coupon_first_purchase_only_enforced(harness):
    """Verify that first_purchase_only coupons are rejected on subsequent purchases."""
    account, _ = make_account(harness, "FirstPurchaseAcct")

    async def _test():
        async with harness.Session() as db:
            coupon = BillingCoupon(
                code="FIRSTORDER",
                kind="flat",
                value=50000,
                first_purchase_only=True,
                is_active=True,
            )
            db.add(coupon)
            await db.flush()

            # First purchase: quote is accepted
            q1 = await calculate_quote(
                db,
                plan_id="silver",
                duration_key="1_year",
                coupon_code="FIRSTORDER",
                account_id=account.account_id,
            )
            assert q1.discount_paise == 50000

            # Fulfill an order for this account
            order, _ = await create_order(
                db,
                account_id=account.account_id,
                plan_id="silver",
                duration_key="1_year",
                coupon_code="FIRSTORDER",
            )
            pmt = GatewayPaymentResult(
                gateway_payment_id="pay_first_order_123",
                status="captured",
                amount_paise=order.total_paise,
                currency="INR",
                method="upi",
            )
            await fulfil_order(db, order.id, gateway_payment=pmt)

            # Second purchase: coupon should be rejected
            with pytest.raises(ValueError, match="first-time purchase"):
                await calculate_quote(
                    db,
                    plan_id="gold",
                    duration_key="1_year",
                    coupon_code="FIRSTORDER",
                    account_id=account.account_id,
                )

    run(_test())


def test_standalone_addons_quote_and_fulfillment(harness):
    """Verify that standalone add-ons can be purchased and increment seat counts."""
    account, _ = make_account(harness, "AddonAcct")

    async def _test():
        async with harness.Session() as db:
            # 1. Start with silver plan (1 user, 1 company)
            order1, _ = await create_order(
                db,
                account_id=account.account_id,
                plan_id="silver",
                duration_key="1_year",
            )
            pmt1 = GatewayPaymentResult(
                gateway_payment_id="pay_silver_123",
                status="captured",
                amount_paise=order1.total_paise,
                currency="INR",
                method="upi",
            )
            await fulfil_order(db, order1.id, gateway_payment=pmt1)

            sub = (await db.execute(
                select(AccountSubscription).where(AccountSubscription.account_id == account.account_id)
            )).scalars().first()
            assert sub.extra_users == 0
            assert sub.extra_companies == 0
            orig_period_end = sub.current_period_end

            # 2. Quote standalone add-on for 2 users, 1 company
            q = await calculate_quote(
                db,
                plan_id="addon",
                extra_users=2,
                extra_companies=1,
                account_id=account.account_id,
            )
            assert q.base_plan_paise == 0
            assert q.extra_users_paise > 0
            assert q.extra_companies_paise > 0
            assert q.plan_code == "addon"

            # 3. Order & fulfill standalone add-on
            order_addon, _ = await create_order(
                db,
                account_id=account.account_id,
                plan_id="addon",
                extra_users=2,
                extra_companies=1,
            )
            pmt_addon = GatewayPaymentResult(
                gateway_payment_id="pay_addon_123",
                status="captured",
                amount_paise=order_addon.total_paise,
                currency="INR",
                method="card",
            )
            await fulfil_order(db, order_addon.id, gateway_payment=pmt_addon)

            await db.refresh(sub)
            assert sub.extra_users == 2
            assert sub.extra_companies == 1
            # Term was NOT reset by add-on purchase
            assert sub.current_period_end == orig_period_end

    run(_test())


def test_scheduled_downgrade_preserves_active_plan(harness):
    """Verify that a downgrade order sets pending_plan_id without immediately demoting."""
    account, _ = make_account(harness, "DowngradeAcct")

    async def _test():
        async with harness.Session() as db:
            # 1. Activate gold plan
            order_gold, _ = await create_order(
                db,
                account_id=account.account_id,
                plan_id="gold",
                duration_key="1_year",
            )
            pmt_gold = GatewayPaymentResult(
                gateway_payment_id="pay_gold_123",
                status="captured",
                amount_paise=order_gold.total_paise,
                currency="INR",
                method="upi",
            )
            await fulfil_order(db, order_gold.id, gateway_payment=pmt_gold)

            sub = (await db.execute(
                select(AccountSubscription).where(AccountSubscription.account_id == account.account_id)
            )).scalars().first()
            gold_plan_id = sub.plan_id

            # 2. Schedule downgrade to silver
            silver_plan = (await db.execute(
                select(BillingPlan).where(BillingPlan.code == "silver")
            )).scalars().first()

            order_down, _ = await create_order(
                db,
                account_id=account.account_id,
                plan_id="silver",
                duration_key="1_year",
            )
            pmt_down = GatewayPaymentResult(
                gateway_payment_id="pay_down_123",
                status="captured",
                amount_paise=order_down.total_paise,
                currency="INR",
                method="card",
            )
            await fulfil_order(db, order_down.id, gateway_payment=pmt_down)

            await db.refresh(sub)
            # Active plan is still Gold!
            assert sub.plan_id == gold_plan_id
            # Pending plan is Silver!
            assert sub.pending_plan_id == silver_plan.id

    run(_test())
