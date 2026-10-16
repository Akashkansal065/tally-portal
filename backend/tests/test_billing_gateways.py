"""
test_billing_gateways.py – Unit tests for Razorpay, Cashfree, and Offline gateway adapters:
- Signature checks (Razorpay HMAC-SHA256, Cashfree timestamp+body base64)
- Webhook parsing into NormalisedEvent
- Gateway registry and configuration checks
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import pytest

from app.core.config import settings
from app.services.billing.gateways.base import NormalisedEvent
from app.services.billing.gateways.cashfree import CashfreeBillingGateway
from app.services.billing.gateways.offline import OfflineBillingGateway
from app.services.billing.gateways.razorpay import RazorpayBillingGateway
from app.services.billing.gateways.registry import get_enabled_gateways, get_gateway
from tests.conftest import run


def test_gateway_registry():
    rzp = get_gateway("razorpay")
    assert isinstance(rzp, RazorpayBillingGateway)
    assert rzp.code == "razorpay"

    cf = get_gateway("cashfree")
    assert isinstance(cf, CashfreeBillingGateway)
    assert cf.code == "cashfree"

    off = get_gateway("offline")
    assert isinstance(off, OfflineBillingGateway)
    assert off.code == "offline"

    with pytest.raises(ValueError, match="Unknown billing gateway"):
        get_gateway("stripe")


def test_enabled_gateways_detection():
    orig_rzp_id = settings.BILLING_RAZORPAY_KEY_ID
    orig_rzp_sec = settings.BILLING_RAZORPAY_KEY_SECRET
    orig_cf_app = settings.BILLING_CASHFREE_APP_ID
    orig_cf_sec = settings.BILLING_CASHFREE_SECRET

    try:
        # None configured
        settings.BILLING_RAZORPAY_KEY_ID = None
        settings.BILLING_RAZORPAY_KEY_SECRET = None
        settings.BILLING_CASHFREE_APP_ID = None
        settings.BILLING_CASHFREE_SECRET = None
        assert get_enabled_gateways() == []

        # Razorpay only
        settings.BILLING_RAZORPAY_KEY_ID = "rzp_id"
        settings.BILLING_RAZORPAY_KEY_SECRET = "rzp_sec"
        assert get_enabled_gateways() == [{"code": "razorpay", "name": "Razorpay"}]

        # Both
        settings.BILLING_CASHFREE_APP_ID = "cf_app"
        settings.BILLING_CASHFREE_SECRET = "cf_sec"
        enabled = get_enabled_gateways()
        codes = [g["code"] for g in enabled]
        assert "razorpay" in codes
        assert "cashfree" in codes
    finally:
        settings.BILLING_RAZORPAY_KEY_ID = orig_rzp_id
        settings.BILLING_RAZORPAY_KEY_SECRET = orig_rzp_sec
        settings.BILLING_CASHFREE_APP_ID = orig_cf_app
        settings.BILLING_CASHFREE_SECRET = orig_cf_sec


def test_razorpay_webhook_verification():
    gw = RazorpayBillingGateway()
    secret = "secret_webhook_12345"
    orig_sec = settings.BILLING_RAZORPAY_WEBHOOK_SECRET

    try:
        settings.BILLING_RAZORPAY_WEBHOOK_SECRET = secret
        body = b'{"event":"payment.captured","account_id":"acc_test"}'

        # Correct signature
        valid_sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        assert gw.verify_webhook({"x-razorpay-signature": valid_sig}, body) is True
        assert gw.verify_webhook({"X-Razorpay-Signature": valid_sig}, body) is True

        # Incorrect signature
        assert gw.verify_webhook({"x-razorpay-signature": "bogus_sig"}, body) is False

        # Missing signature
        assert gw.verify_webhook({}, body) is False
    finally:
        settings.BILLING_RAZORPAY_WEBHOOK_SECRET = orig_sec


def test_razorpay_parse_webhook():
    gw = RazorpayBillingGateway()
    payload = {
        "event": "payment.captured",
        "account_id": "acc_1",
        "event_id": "evt_rzp_999",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_test_123",
                    "order_id": "order_test_456",
                    "amount": 549900,
                    "status": "captured",
                }
            }
        },
    }
    event: NormalisedEvent = gw.parse_webhook(payload)
    assert event.event_id == "evt_rzp_999"
    assert event.event_type == "payment.captured"
    assert event.gateway_order_id == "order_test_456"
    assert event.gateway_payment_id == "pay_test_123"
    assert event.amount_paise == 549900
    assert event.status == "captured"


def test_cashfree_webhook_verification():
    gw = CashfreeBillingGateway()
    secret = "cashfree_secret_54321"
    orig_sec = settings.BILLING_CASHFREE_SECRET

    try:
        settings.BILLING_CASHFREE_SECRET = secret
        body = b'{"type":"PAYMENT_SUCCESS_WEBHOOK","data":{}}'
        timestamp = "1728734000"

        # Correct HMAC signature
        to_sign = timestamp.encode("utf-8") + body
        sig = base64.b64encode(hmac.new(secret.encode("utf-8"), to_sign, hashlib.sha256).digest()).decode("utf-8")

        headers = {
            "x-webhook-timestamp": timestamp,
            "x-webhook-signature": sig,
        }
        assert gw.verify_webhook(headers, body) is True

        # Tampered body
        tampered_body = b'{"type":"PAYMENT_SUCCESS_WEBHOOK","data":{"hacked":true}}'
        assert gw.verify_webhook(headers, tampered_body) is False

        # Missing headers
        assert gw.verify_webhook({}, body) is False
    finally:
        settings.BILLING_CASHFREE_SECRET = orig_sec


def test_cashfree_parse_webhook():
    gw = CashfreeBillingGateway()
    payload = {
        "type": "PAYMENT_SUCCESS_WEBHOOK",
        "event_id": "evt_cf_777",
        "data": {
            "order": {
                "order_id": "MT_ORDER_001",
                "order_amount": 7499.00,
            },
            "payment": {
                "cf_payment_id": "998877",
                "payment_status": "SUCCESS",
                "payment_amount": 7499.00,
            },
        },
    }
    event: NormalisedEvent = gw.parse_webhook(payload)
    assert event.event_id == "evt_cf_777"
    assert event.event_type == "PAYMENT_SUCCESS_WEBHOOK"
    assert event.gateway_order_id == "MT_ORDER_001"
    assert event.gateway_payment_id == "998877"
    assert event.amount_paise == 749900
    assert event.status == "captured"


def test_razorpay_create_plan_and_ensure_plan(monkeypatch):
    """Test Razorpay plan creation and caching in BillingPlanPrice."""
    async def _test():
        gw = RazorpayBillingGateway()
        monkeypatch.setattr(settings, "BILLING_RAZORPAY_KEY_ID", "rzp_test_key")
        monkeypatch.setattr(settings, "BILLING_RAZORPAY_KEY_SECRET", "rzp_test_sec")

        class DummyResponse:
            status_code = 200
            def json(self):
                return {"id": "plan_rzp_mock_123", "item": {"name": "Gold Monthly", "amount": 49900}}

        class DummyClient:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass
            async def post(self, url, json=None, auth=None):
                assert "/plans" in url
                assert json["item"]["amount"] == 49900
                assert json["period"] == "monthly"
                assert json["interval"] == 1
                return DummyResponse()

        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: DummyClient())

        # 1. create_plan
        plan_res = await gw.create_plan(
            period="monthly",
            interval=1,
            item_name="Gold Monthly",
            amount_paise=49900,
            description="Gold Monthly Subscription",
        )
        assert plan_res["id"] == "plan_rzp_mock_123"

        # 2. ensure_plan creates when missing
        class DummyPrice:
            id = 10
            plan_id = 5
            interval = "month"
            interval_count = 1
            amount_paise = 49900
            gateway_plan_refs = None

        price = DummyPrice()
        plan_id = await gw.ensure_plan(price, "Gold")
        assert plan_id == "plan_rzp_mock_123"
        assert json.loads(price.gateway_plan_refs)["razorpay"] == "plan_rzp_mock_123"

        # 3. ensure_plan reuses cached ref without HTTP call
        reused_id = await gw.ensure_plan(price, "Gold")
        assert reused_id == "plan_rzp_mock_123"

    run(_test())


def test_razorpay_subscription_lifecycle_api(monkeypatch):
    """Test Razorpay subscription creation and cancellation."""
    async def _test():
        gw = RazorpayBillingGateway()
        monkeypatch.setattr(settings, "BILLING_RAZORPAY_KEY_ID", "rzp_test_key")
        monkeypatch.setattr(settings, "BILLING_RAZORPAY_KEY_SECRET", "rzp_test_sec")

        called_urls = []

        class DummyClient:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass
            async def post(self, url, json=None, auth=None):
                called_urls.append((url, json))
                if "cancel" in url:
                    return type("R", (), {"status_code": 200, "json": lambda self: {"id": "sub_123", "status": "cancelled"}})()
                return type("R", (), {"status_code": 200, "json": lambda self: {"id": "sub_123", "status": "created"}})()

        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: DummyClient())

        # Create subscription
        sub = await gw.create_subscription("plan_rzp_mock_123", total_count=60, notes={"order_ref": "MT_123"})
        assert sub["id"] == "sub_123"
        assert sub["status"] == "created"
        assert called_urls[0][1]["total_count"] == 60

        # Cancel subscription
        cancelled = await gw.cancel_subscription("sub_123", cancel_at_cycle_end=True)
        assert cancelled["status"] == "cancelled"
        assert called_urls[1][1]["cancel_at_cycle_end"] == 1

    run(_test())


def test_razorpay_confirm_payment_subscription_mandate(monkeypatch):
    """Test Razorpay signature verification for recurring subscription mandates (payment_id|subscription_id)."""
    async def _test():
        gw = RazorpayBillingGateway()
        secret = "rzp_test_sec_999"
        monkeypatch.setattr(settings, "BILLING_RAZORPAY_KEY_ID", "rzp_test_key")
        monkeypatch.setattr(settings, "BILLING_RAZORPAY_KEY_SECRET", secret)

        sub_id = "sub_mandate_001"
        pay_id = "pay_mandate_001"

        # In subscriptions, signature is HMAC-SHA256(payment_id + "|" + subscription_id, secret)
        msg = f"{pay_id}|{sub_id}".encode("utf-8")
        valid_sig = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()

        class DummyOrder:
            order_ref = "MT_ORD_SUB_01"
            gateway_order_id = sub_id
            quote = None

        class DummyClient:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass
            async def get(self, url, auth=None):
                return type(
                    "R",
                    (),
                    {
                        "status_code": 200,
                        "json": lambda self: {
                            "id": pay_id,
                            "subscription_id": sub_id,
                            "status": "captured",
                            "amount": 58882,
                            "currency": "INR",
                            "method": "upi",
                        },
                    },
                )()

        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: DummyClient())

        # Valid confirmation
        result = await gw.confirm_payment(
            DummyOrder(),
            {
                "razorpay_payment_id": pay_id,
                "razorpay_subscription_id": sub_id,
                "razorpay_signature": valid_sig,
            },
        )
        assert result.gateway_payment_id == pay_id
        assert result.status == "captured"
        assert result.amount_paise == 58882

        # Tampered signature fails
        with pytest.raises(ValueError, match="Invalid Razorpay payment signature"):
            await gw.confirm_payment(
                DummyOrder(),
                {
                    "razorpay_payment_id": pay_id,
                    "razorpay_subscription_id": sub_id,
                    "razorpay_signature": "invalid_sig",
                },
            )

    run(_test())


def test_razorpay_parse_extended_webhooks():
    """Test webhook parsing for subscription events, refunds, disputes, and failures."""
    gw = RazorpayBillingGateway()

    # 1. subscription.authenticated
    sub_payload = {
        "event": "subscription.authenticated",
        "event_id": "evt_sub_auth_01",
        "payload": {
            "subscription": {
                "entity": {"id": "sub_authed_001", "status": "active"}
            },
            "payment": {
                "entity": {"id": "pay_authed_001", "subscription_id": "sub_authed_001", "amount": 0, "status": "authorized"}
            }
        }
    }
    event = gw.parse_webhook(sub_payload)
    assert event.event_type == "subscription.authenticated"
    assert event.gateway_subscription_id == "sub_authed_001"
    assert event.gateway_payment_id == "pay_authed_001"

    # 2. refund.processed
    refund_payload = {
        "event": "refund.processed",
        "event_id": "evt_ref_01",
        "payload": {
            "refund": {
                "entity": {
                    "id": "rfnd_test_101",
                    "payment_id": "pay_test_orig_01",
                    "amount": 25000,
                    "status": "processed",
                }
            }
        }
    }
    event_ref = gw.parse_webhook(refund_payload)
    assert event_ref.event_type == "refund.processed"
    assert event_ref.gateway_refund_id == "rfnd_test_101"
    assert event_ref.gateway_payment_id == "pay_test_orig_01"
    assert event_ref.amount_paise == 25000

    # 3. payment.failed
    fail_payload = {
        "event": "payment.failed",
        "event_id": "evt_fail_01",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_failed_001",
                    "order_id": "order_fail_001",
                    "amount": 549900,
                    "status": "failed",
                    "error_code": "BAD_REQUEST_ERROR",
                    "error_description": "Payment was declined by bank due to insufficient funds.",
                }
            }
        }
    }
    event_fail = gw.parse_webhook(fail_payload)
    assert event_fail.event_type == "payment.failed"
    assert event_fail.error_code == "BAD_REQUEST_ERROR"
    assert "insufficient funds" in event_fail.error_description

    # 4. payment.dispute.created
    dispute_payload = {
        "event": "payment.dispute.created",
        "event_id": "evt_disp_01",
        "payload": {
            "dispute": {
                "entity": {
                    "id": "disp_test_505",
                    "payment_id": "pay_disputed_001",
                    "amount": 549900,
                    "status": "open",
                }
            }
        }
    }
    event_disp = gw.parse_webhook(dispute_payload)
    assert event_disp.event_type == "payment.dispute.created"
    assert event_disp.gateway_dispute_id == "disp_test_505"
    assert event_disp.gateway_payment_id == "pay_disputed_001"

