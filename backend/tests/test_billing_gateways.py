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
