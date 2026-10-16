"""
test_billing_autopay_and_credits.py – Automated tests for Phase 8 & Phase 9:
- Monthly plan quotes & UPI autopay flag
- Autopay cancellation endpoint (POST /billing/subscription/autopay/cancel)
- Recurring webhook processing for Razorpay (subscription.charged) and Cashfree (SUBSCRIPTION_CHARGED)
- Autopay payment failure / dunning (subscription.halted -> grace period)
- Proration credit calculation on mid-term plan upgrades
- Credit pack ledger management (grant, consume, atomic balance checks)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update

import app.models.portal_core as P
from app.core.config import settings
from app.models.billing import (
    AccountSubscription,
    BillingInvoice,
    BillingOrder,
    BillingPayment,
    BillingPlan,
    BillingPlanPrice,
    BillingRefund,
    BillingSubscriptionEvent,
    BillingWebhookEvent,
)
from app.services.billing.gateways.razorpay import RazorpayBillingGateway
from app.routers import auth, billing
from app.services.billing.credits import (
    consume_credits,
    get_all_credit_balances,
    get_credit_balance,
    grant_credits,
)
from app.services.billing.entitlements import get_entitlements, invalidate_entitlements_cache
from app.services.billing.orders import fulfil_order
from app.services.billing.quote import calculate_quote
from tests.conftest import bearer, login, run


def make_account(harness, name="AutopayAccount", role_name="Admin"):
    account = harness.add(P.Account(name=name, status="active"))
    company = harness.company(name)
    role = harness.role(role_name)
    user = harness.user(company, role, f"user_{name.lower()}@test.com")
    harness.execute(update(P.Company).where(P.Company.company_id == company.company_id).values(account_id=account.account_id))
    harness.execute(update(P.User).where(P.User.user_id == user.user_id).values(account_id=account.account_id))
    harness.execute(update(P.Role).where(P.Role.role_id == role.role_id).values(account_id=account.account_id))
    return account, company, user


def fetch_scalar(harness, stmt):
    async def _f():
        async with harness.Session() as db:
            return (await db.execute(stmt)).scalars().first()
    return run(_f())


def rzp_signature(body: bytes, secret: str = "rzp_wh_test_secret") -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def cf_signature(body: bytes, timestamp: str, secret: str = "cf_secret_test_key") -> str:
    data_to_sign = timestamp.encode("utf-8") + body
    return base64.b64encode(hmac.new(secret.encode("utf-8"), data_to_sign, hashlib.sha256).digest()).decode("utf-8")


def test_monthly_plan_quotes(harness):
    """Monthly plans calculate 1-month term and have autopay allowed."""
    client = harness.app(billing.router)

    # Silver monthly: ₹299 taxable
    res_silver = client.post("/billing/quote", json={"plan_id": "silver", "duration_key": "monthly"}).json()
    assert res_silver["success"] is True
    assert res_silver["taxable"] == 299.0
    assert res_silver["months"] == 1
    assert res_silver["interval"] == "month"

    # Gold monthly: ₹499 taxable
    res_gold = client.post("/billing/quote", json={"plan_id": "gold", "duration_key": "monthly"}).json()
    assert res_gold["success"] is True
    assert res_gold["taxable"] == 499.0

    # Diamond monthly: ₹999 taxable
    res_diamond = client.post("/billing/quote", json={"plan_id": "diamond", "duration_key": "monthly"}).json()
    assert res_diamond["success"] is True
    assert res_diamond["taxable"] == 999.0


def test_autopay_cancellation_endpoint(harness):
    """Calling cancel endpoint stops recurring billing at current period end."""
    account, _, owner = make_account(harness, "AutopayCancelTest")
    client = harness.app(auth.router, billing.router)
    token = bearer(login(client, owner.email))

    now = datetime.now(timezone.utc)
    future_end = now + timedelta(days=25)

    gold_plan = fetch_scalar(harness, select(BillingPlan).where(BillingPlan.code == "gold"))
    harness.add(
        AccountSubscription(
            account_id=account.account_id,
            plan_id=gold_plan.id,
            status="active",
            current_period_start=now,
            current_period_end=future_end,
            autopay=True,
            gateway="razorpay",
            gateway_subscription_id="sub_rzp_mock_12345",
            cancel_at_period_end=False,
        )
    )

    # Call cancellation endpoint
    res = client.post("/billing/subscription/autopay/cancel", headers=token)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["success"] is True
    assert data["cancel_at_period_end"] is True

    # Verify subscription in database
    refreshed_sub = fetch_scalar(
        harness, select(AccountSubscription).where(AccountSubscription.account_id == account.account_id)
    )
    assert refreshed_sub.cancel_at_period_end is True
    assert refreshed_sub.autopay is False

    # Check audit event was emitted
    event = fetch_scalar(
        harness,
        select(BillingSubscriptionEvent).where(
            BillingSubscriptionEvent.account_id == account.account_id,
            BillingSubscriptionEvent.event_type == "autopay_cancelled_by_user",
        ),
    )
    assert event is not None
    assert event.actor_user_id == owner.user_id


def test_razorpay_recurring_charge_webhook(harness, monkeypatch):
    """Razorpay subscription.charged creates autopay order, extends period, and issues invoice."""
    account, _, _ = make_account(harness, "RazorpayRecurring")
    client = harness.app(billing.router)

    monkeypatch.setattr(settings, "BILLING_RAZORPAY_WEBHOOK_SECRET", "rzp_wh_test_secret")
    monkeypatch.setattr(settings, "BILLING_RAZORPAY_KEY_ID", "rzp_test_key")
    monkeypatch.setattr(settings, "BILLING_RAZORPAY_KEY_SECRET", "rzp_test_secret")

    now = datetime.now(timezone.utc)
    period_end = now + timedelta(days=2)

    gold_plan = fetch_scalar(harness, select(BillingPlan).where(BillingPlan.code == "gold"))
    price = fetch_scalar(
        harness,
        select(BillingPlanPrice).where(BillingPlanPrice.plan_id == gold_plan.id, BillingPlanPrice.interval == "month"),
    )

    harness.add(
        AccountSubscription(
            account_id=account.account_id,
            plan_id=gold_plan.id,
            price_id=price.id if price else None,
            status="active",
            current_period_start=now - timedelta(days=28),
            current_period_end=period_end,
            autopay=True,
            gateway="razorpay",
            gateway_subscription_id="sub_rzp_recurring_test_99",
        )
    )

    payload = {
        "event": "subscription.charged",
        "event_id": "evt_rzp_charged_1001",
        "payload": {
            "subscription": {
                "entity": {
                    "id": "sub_rzp_recurring_test_99",
                    "status": "active",
                }
            },
            "payment": {
                "entity": {
                    "id": "pay_rzp_rec_debited_1001",
                    "order_id": "order_rzp_rec_1001",
                    "amount": 58882,  # ₹588.82 (₹499 + 18% GST)
                    "status": "captured",
                    "currency": "INR",
                    "method": "upi",
                }
            }
        }
    }
    body = json.dumps(payload).encode("utf-8")
    sig = rzp_signature(body, "rzp_wh_test_secret")

    res = client.post(
        "/billing/webhooks/razorpay",
        data=body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig},
    )
    assert res.status_code == 200, res.text

    # Verify subscription was extended by 30 days
    refreshed_sub = fetch_scalar(
        harness, select(AccountSubscription).where(AccountSubscription.account_id == account.account_id)
    )
    assert refreshed_sub.current_period_end.replace(tzinfo=None) > period_end.replace(tzinfo=None) + timedelta(days=28)

    # Verify autopay order was recorded and paid
    order = fetch_scalar(
        harness,
        select(BillingOrder).where(
            BillingOrder.account_id == account.account_id,
            BillingOrder.purpose == "autopay_charge",
        ),
    )
    assert order is not None
    assert order.status == "paid"

    # Verify invoice was issued
    invoice = fetch_scalar(harness, select(BillingInvoice).where(BillingInvoice.order_id == order.id))
    assert invoice is not None
    assert invoice.invoice_number.startswith("MT/")

    # The same payment announced again by another event (here without an order id) is acknowledged, not
    # failed: a failing webhook is retried for a day and then switched off by the gateway
    again = dict(payload, event="payment.captured", event_id="evt_rzp_captured_1001")
    again["payload"] = {"payment": {"entity": dict(payload["payload"]["payment"]["entity"], order_id=None)},
                        "subscription": payload["payload"]["subscription"]}
    body = json.dumps(again).encode("utf-8")
    res = client.post("/billing/webhooks/razorpay", data=body, headers={
        "Content-Type": "application/json", "X-Razorpay-Signature": rzp_signature(body, "rzp_wh_test_secret")})
    assert res.status_code == 200, res.text
    orders = harness.query(select(BillingOrder.id).where(BillingOrder.account_id == account.account_id))
    assert len(orders) == 1
    still = fetch_scalar(harness, select(AccountSubscription).where(AccountSubscription.account_id == account.account_id))
    assert still.current_period_end == refreshed_sub.current_period_end


def test_cashfree_recurring_charge_webhook(harness, monkeypatch):
    """Cashfree SUBSCRIPTION_CHARGED creates order, extends period, and issues invoice."""
    account, _, _ = make_account(harness, "CashfreeRecurring")
    client = harness.app(billing.router)

    monkeypatch.setattr(settings, "BILLING_CASHFREE_SECRET", "cf_secret_test_key")
    monkeypatch.setattr(settings, "BILLING_CASHFREE_APP_ID", "cf_test_app_id")

    now = datetime.now(timezone.utc)
    period_end = now + timedelta(days=1)

    silver_plan = fetch_scalar(harness, select(BillingPlan).where(BillingPlan.code == "silver"))

    harness.add(
        AccountSubscription(
            account_id=account.account_id,
            plan_id=silver_plan.id,
            status="active",
            current_period_start=now - timedelta(days=29),
            current_period_end=period_end,
            autopay=True,
            gateway="cashfree",
            gateway_subscription_id="sub_cf_recurring_test_88",
        )
    )

    payload = {
        "type": "SUBSCRIPTION_CHARGED",
        "event_id": "evt_cf_charged_2001",
        "data": {
            "subscription": {
                "subscription_id": "sub_cf_recurring_test_88",
                "sub_reference_id": "sub_cf_recurring_test_88",
                "status": "ACTIVE",
            },
            "payment": {
                "cf_payment_id": "cf_pay_rec_2001",
                "payment_amount": 352.82,  # ₹299 + 18% GST
                "payment_status": "SUCCESS",
            }
        }
    }
    body = json.dumps(payload).encode("utf-8")
    ts = "1773000000"
    sig = cf_signature(body, ts, "cf_secret_test_key")

    res = client.post(
        "/billing/webhooks/cashfree",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-webhook-timestamp": ts,
            "x-webhook-signature": sig,
        },
    )
    assert res.status_code == 200, res.text

    # Verify subscription was extended
    refreshed_sub = fetch_scalar(
        harness, select(AccountSubscription).where(AccountSubscription.account_id == account.account_id)
    )
    assert refreshed_sub.current_period_end.replace(tzinfo=None) > period_end.replace(tzinfo=None) + timedelta(days=28)


def test_autopay_payment_failure_moves_to_grace(harness, monkeypatch):
    """Recurring payment failure moves account subscription to grace period."""
    account, _, _ = make_account(harness, "AutopayFailureTest")
    client = harness.app(billing.router)

    monkeypatch.setattr(settings, "BILLING_RAZORPAY_WEBHOOK_SECRET", "rzp_wh_test_secret")
    monkeypatch.setattr(settings, "BILLING_RAZORPAY_KEY_ID", "rzp_test_key")
    monkeypatch.setattr(settings, "BILLING_RAZORPAY_KEY_SECRET", "rzp_test_secret")

    now = datetime.now(timezone.utc)
    gold_plan = fetch_scalar(harness, select(BillingPlan).where(BillingPlan.code == "gold"))

    harness.add(
        AccountSubscription(
            account_id=account.account_id,
            plan_id=gold_plan.id,
            status="active",
            current_period_start=now - timedelta(days=30),
            current_period_end=now,
            autopay=True,
            gateway="razorpay",
            gateway_subscription_id="sub_rzp_failing_999",
        )
    )

    payload = {
        "event": "subscription.halted",
        "event_id": "evt_rzp_halted_5001",
        "payload": {
            "subscription": {
                "entity": {
                    "id": "sub_rzp_failing_999",
                    "status": "halted",
                }
            }
        }
    }
    body = json.dumps(payload).encode("utf-8")
    sig = rzp_signature(body, "rzp_wh_test_secret")

    res = client.post(
        "/billing/webhooks/razorpay",
        data=body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig},
    )
    assert res.status_code == 200, res.text

    refreshed_sub = fetch_scalar(
        harness, select(AccountSubscription).where(AccountSubscription.account_id == account.account_id)
    )
    assert refreshed_sub.status == "grace"
    assert refreshed_sub.grace_ends_at is not None


def test_proration_credit_on_upgrade(harness):
    """Mid-term plan upgrade receives proration credit for unused days of previous plan."""
    account, _, _ = make_account(harness, "ProrationTest")

    silver_plan = fetch_scalar(harness, select(BillingPlan).where(BillingPlan.code == "silver"))
    silver_price = fetch_scalar(
        harness,
        select(BillingPlanPrice).where(BillingPlanPrice.plan_id == silver_plan.id, BillingPlanPrice.interval == "year"),
    )

    now = datetime.now(timezone.utc)
    # 200 days left of a 365-day term
    start = now - timedelta(days=165)
    end = now + timedelta(days=200)

    harness.add(
        AccountSubscription(
            account_id=account.account_id,
            plan_id=silver_plan.id,
            price_id=silver_price.id,
            status="active",
            current_period_start=start,
            current_period_end=end,
        )
    )
    # The credit is the unused share of what was actually paid for the running term
    harness.add(
        BillingOrder(
            order_ref="MT_PAID_SILVER_TERM",
            account_id=account.account_id,
            purpose="new",
            status="paid",
            taxable_paise=249900,
            total_paise=294882,
            quote=json.dumps({"period_start": start.isoformat(), "period_end": end.isoformat()}),
        )
    )

    async def _get_quote():
        async with harness.Session() as db:
            return await calculate_quote(
                db,
                plan_id="gold",
                duration_key="1_year",
                account_id=account.account_id,
            )

    quote = run(_get_quote())

    # Silver yearly is 249900 paise. 200 / 365 = ~54.79% unused -> ~136932 paise credit
    assert quote.proration_credit_paise > 130000
    assert quote.proration_credit_paise < 140000
    # Gold base is 449900 paise. Taxable is reduced by the proration credit.
    assert quote.taxable_paise == quote.subtotal_paise - quote.proration_credit_paise
    assert quote.total_paise < round(449900 * 1.18)


def test_credits_ledger_operations(harness):
    """Credit ledger correctly tracks grants, consumes, and rejects overdrafts."""
    account, _, _ = make_account(harness, "CreditsLedgerTest")

    async def _test():
        async with harness.Session() as db:
            # Initially zero
            initial_balance = await get_credit_balance(db, account.account_id, "einvoice")
            assert initial_balance == 0

            # Grant 500 einvoice credits
            await grant_credits(
                db,
                account_id=account.account_id,
                credit_type="einvoice",
                qty=500,
                reason="Purchased pack 500",
                reference="ORD_CREDIT_PACK_1",
            )
            await db.commit()

            balance_after_grant = await get_credit_balance(db, account.account_id, "einvoice")
            assert balance_after_grant == 500

            # Consume 20 credits
            ok, remaining = await consume_credits(
                db,
                account_id=account.account_id,
                credit_type="einvoice",
                qty=20,
                reason="Generated IRN for INV-001",
                reference="IRN_001",
            )
            await db.commit()
            assert ok is True
            assert remaining == 480

            # Attempt to consume 600 credits (exceeds balance)
            overdraft_ok, overdraft_remaining = await consume_credits(
                db,
                account_id=account.account_id,
                credit_type="einvoice",
                qty=600,
                reason="Bulk IRN generation",
                reference="BULK_BATCH_1",
            )
            assert overdraft_ok is False
            assert overdraft_remaining == 480

            # Check all credit balances
            all_bals = await get_all_credit_balances(db, account.account_id)
            assert all_bals["einvoice"] == 480
            assert all_bals["whatsapp"] == 0

    run(_test())


def test_razorpay_subscription_authenticated_webhook(harness, monkeypatch):
    """subscription.authenticated activates autopay mandate and logs audit event."""
    account, _, _ = make_account(harness, "SubAuthTest")
    client = harness.app(billing.router)

    monkeypatch.setattr(settings, "BILLING_RAZORPAY_WEBHOOK_SECRET", "rzp_wh_test_secret")

    now = datetime.now(timezone.utc)
    gold_plan = fetch_scalar(harness, select(BillingPlan).where(BillingPlan.code == "gold"))

    sub = harness.add(
        AccountSubscription(
            account_id=account.account_id,
            plan_id=gold_plan.id,
            status="active",
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            autopay=False,
            gateway="razorpay",
            gateway_subscription_id="sub_mandate_auth_999",
        )
    )

    payload = {
        "event": "subscription.authenticated",
        "event_id": "evt_auth_mandate_001",
        "payload": {
            "subscription": {
                "entity": {
                    "id": "sub_mandate_auth_999",
                    "status": "active",
                }
            },
            "payment": {
                "entity": {
                    "id": "pay_token_auth_001",
                    "subscription_id": "sub_mandate_auth_999",
                    "amount": 0,
                    "status": "authorized",
                }
            }
        }
    }
    body = json.dumps(payload).encode("utf-8")
    sig = rzp_signature(body, "rzp_wh_test_secret")

    res = client.post(
        "/billing/webhooks/razorpay",
        data=body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig},
    )
    assert res.status_code == 200, res.text

    refreshed_sub = fetch_scalar(
        harness, select(AccountSubscription).where(AccountSubscription.account_id == account.account_id)
    )
    assert refreshed_sub.autopay is True

    event = fetch_scalar(
        harness,
        select(BillingSubscriptionEvent).where(
            BillingSubscriptionEvent.account_id == account.account_id,
            BillingSubscriptionEvent.event_type == "autopay_authenticated",
        ),
    )
    assert event is not None


def test_razorpay_refund_processed_webhook(harness, monkeypatch):
    """refund.processed tracks partial and full refunds on the payment entity."""
    account, _, _ = make_account(harness, "RefundTest")
    client = harness.app(billing.router)

    monkeypatch.setattr(settings, "BILLING_RAZORPAY_WEBHOOK_SECRET", "rzp_wh_test_secret")

    gold_plan = fetch_scalar(harness, select(BillingPlan).where(BillingPlan.code == "gold"))
    order = harness.add(
        BillingOrder(
            account_id=account.account_id,
            plan_id=gold_plan.id,
            order_ref="MT_ORD_REFUND_01",
            purpose="new",
            status="paid",
            total_paise=100000,
            gateway="razorpay",
            gateway_order_id="order_rzp_ref_01",
        )
    )
    payment = harness.add(
        BillingPayment(
            order_id=order.id,
            gateway="razorpay",
            gateway_payment_id="pay_rzp_to_refund_01",
            amount_paise=100000,
            status="captured",
        )
    )

    # 1. Partial refund of ₹400 (40000 paise)
    payload_partial = {
        "event": "refund.processed",
        "event_id": "evt_ref_part_01",
        "payload": {
            "refund": {
                "entity": {
                    "id": "rfnd_001",
                    "payment_id": "pay_rzp_to_refund_01",
                    "amount": 40000,
                    "status": "processed",
                }
            }
        }
    }
    body_p = json.dumps(payload_partial).encode("utf-8")
    res_p = client.post(
        "/billing/webhooks/razorpay",
        data=body_p,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": rzp_signature(body_p, "rzp_wh_test_secret")},
    )
    assert res_p.status_code == 200, res_p.text

    ref1 = fetch_scalar(
        harness, select(BillingRefund).where(BillingRefund.gateway_refund_id == "rfnd_001")
    )
    assert ref1 is not None
    assert ref1.amount_paise == 40000
    assert ref1.status == "processed"

    # 2. Full refund of remaining ₹600 (60000 paise)
    payload_full = {
        "event": "refund.processed",
        "event_id": "evt_ref_full_02",
        "payload": {
            "refund": {
                "entity": {
                    "id": "rfnd_002",
                    "payment_id": "pay_rzp_to_refund_01",
                    "amount": 60000,
                    "status": "processed",
                }
            }
        }
    }
    body_f = json.dumps(payload_full).encode("utf-8")
    res_f = client.post(
        "/billing/webhooks/razorpay",
        data=body_f,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": rzp_signature(body_f, "rzp_wh_test_secret")},
    )
    assert res_f.status_code == 200, res_f.text

    ref2 = fetch_scalar(
        harness, select(BillingRefund).where(BillingRefund.gateway_refund_id == "rfnd_002")
    )
    assert ref2 is not None
    assert ref2.amount_paise == 60000
    assert ref2.status == "processed"

    # Verify event was logged
    event = fetch_scalar(
        harness,
        select(BillingSubscriptionEvent).where(
            BillingSubscriptionEvent.account_id == account.account_id,
            BillingSubscriptionEvent.event_type == "payment_refunded",
        ),
    )
    assert event is not None


def test_razorpay_payment_failed_webhook(harness, monkeypatch):
    """payment.failed records failure event with error codes for dunning analysis."""
    account, _, _ = make_account(harness, "PaymentFailTest")
    client = harness.app(billing.router)

    monkeypatch.setattr(settings, "BILLING_RAZORPAY_WEBHOOK_SECRET", "rzp_wh_test_secret")

    now = datetime.now(timezone.utc)
    silver_plan = fetch_scalar(harness, select(BillingPlan).where(BillingPlan.code == "silver"))
    harness.add(
        AccountSubscription(
            account_id=account.account_id,
            plan_id=silver_plan.id,
            status="active",
            current_period_start=now - timedelta(days=20),
            current_period_end=now + timedelta(days=10),
            autopay=True,
            gateway="razorpay",
            gateway_subscription_id="sub_fail_test_77",
        )
    )

    payload = {
        "event": "payment.failed",
        "event_id": "evt_fail_999",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_fail_777",
                    "subscription_id": "sub_fail_test_77",
                    "amount": 35282,
                    "status": "failed",
                    "error_code": "BAD_REQUEST_ERROR",
                    "error_description": "Payment was declined by issuing bank.",
                }
            }
        }
    }
    body = json.dumps(payload).encode("utf-8")
    res = client.post(
        "/billing/webhooks/razorpay",
        data=body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": rzp_signature(body, "rzp_wh_test_secret")},
    )
    assert res.status_code == 200, res.text

    event = fetch_scalar(
        harness,
        select(BillingSubscriptionEvent).where(
            BillingSubscriptionEvent.account_id == account.account_id,
            BillingSubscriptionEvent.event_type == "payment_failed",
        ),
    )
    assert event is not None
    details = json.loads(event.detail)
    assert details["error_code"] == "BAD_REQUEST_ERROR"
    assert "declined by issuing bank" in details["error_description"]


def test_create_order_with_autopay_mandate(harness, monkeypatch):
    """Creating order with autopay=True links subscription_id in checkout_config."""
    account, _, owner = make_account(harness, "AutopayOrderTest")
    client = harness.app(auth.router, billing.router)
    token = bearer(login(client, owner.email))

    monkeypatch.setattr(settings, "BILLING_CHECKOUT_ENABLED", True)
    monkeypatch.setattr(settings, "BILLING_AUTOPAY_ENABLED", True)
    monkeypatch.setattr(settings, "BILLING_RAZORPAY_KEY_ID", "rzp_test_key_01")
    monkeypatch.setattr(settings, "BILLING_RAZORPAY_KEY_SECRET", "rzp_test_sec_01")

    async def mock_ensure_plan(self, price, plan_name):
        return "plan_mock_monthly_01"

    async def mock_create_subscription(self, plan_id, total_count=120, **kwargs):
        return {"id": "sub_rzp_mock_created_88", "status": "created"}

    monkeypatch.setattr(RazorpayBillingGateway, "ensure_plan", mock_ensure_plan)
    monkeypatch.setattr(RazorpayBillingGateway, "create_subscription", mock_create_subscription)

    res = client.post(
        "/billing/orders",
        headers=token,
        json={
            "plan_id": "silver",
            "duration_key": "monthly",
            "gateway": "razorpay",
            "client_request_key": "AUTOPAY_ORD_001",
            "autopay": True,
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["success"] is True
    assert data["order_ref"].startswith("MT_")
    assert data["checkout_config"]["subscription_id"] == "sub_rzp_mock_created_88"
    assert data["checkout_config"]["key"] == "rzp_test_key_01"

    # Verify order in DB
    order = fetch_scalar(
        harness, select(BillingOrder).where(BillingOrder.order_ref == data["order_ref"])
    )
    quote_data = json.loads(order.quote)
    assert quote_data["autopay"] is True
    assert order.gateway_order_id == "sub_rzp_mock_created_88"

