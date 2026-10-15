"""
razorpay.py – Razorpay billing gateway adapter using httpx.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings
from app.models.billing import BillingOrder, BillingPayment
from app.services.billing.gateways.base import (
    GatewayOrderResult, GatewayPaymentResult, GatewayRefundResult, NormalisedEvent,
)

logger = logging.getLogger("app.services.billing.gateways.razorpay")
BASE_URL = "https://api.razorpay.com/v1"


class RazorpayBillingGateway:
    code = "razorpay"
    name = "Razorpay"

    @property
    def is_configured(self) -> bool:
        return bool(
            settings.BILLING_RAZORPAY_KEY_ID and settings.BILLING_RAZORPAY_KEY_SECRET
        )

    def _auth(self) -> tuple[str, str]:
        if not self.is_configured:
            raise RuntimeError("Razorpay billing gateway is not configured with key and secret.")
        return (settings.BILLING_RAZORPAY_KEY_ID or "", settings.BILLING_RAZORPAY_KEY_SECRET or "")

    def checkout_config(self, order: BillingOrder) -> Dict[str, Any]:
        return {
            "gateway": self.code,
            "key": settings.BILLING_RAZORPAY_KEY_ID,
            "order_id": order.gateway_order_id,
            "amount": order.total_paise,
            "currency": "INR",
            "name": "MyTally",
            "description": f"Subscription {order.order_ref}",
            "receipt": order.order_ref,
        }

    async def create_order(self, order: BillingOrder) -> GatewayOrderResult:
        payload = {
            "amount": int(order.total_paise),
            "currency": "INR",
            "receipt": order.order_ref,
            "notes": {
                "account_id": str(order.account_id),
                "order_ref": order.order_ref,
                "purpose": order.purpose,
            },
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{BASE_URL}/orders",
                json=payload,
                auth=self._auth(),
            )
            if resp.status_code >= 400:
                logger.error(f"Razorpay order creation failed: {resp.status_code} {resp.text}")
                raise RuntimeError(f"Razorpay returned {resp.status_code}: {resp.text}")

            data = resp.json()
            return GatewayOrderResult(
                gateway_order_id=data["id"],
                client_payload={"order_id": data["id"]},
                raw=data,
            )

    async def confirm_payment(
        self, order: BillingOrder, client_payload: Dict[str, Any]
    ) -> GatewayPaymentResult:
        """
        Verify the client-provided signature, then fetch payment from Razorpay
        to ensure status is captured and amount equals order total.
        """
        payment_id = client_payload.get("razorpay_payment_id")
        order_id = client_payload.get("razorpay_order_id")
        signature = client_payload.get("razorpay_signature")

        if not payment_id or not order_id or not signature:
            raise ValueError("Missing razorpay_payment_id, razorpay_order_id, or razorpay_signature.")

        if order.gateway_order_id and order_id != order.gateway_order_id:
            raise ValueError(
                f"Razorpay order ID mismatch: expected {order.gateway_order_id}, got {order_id}"
            )

        # 1. Cryptographic signature check
        key_secret = settings.BILLING_RAZORPAY_KEY_SECRET or ""
        msg = f"{order_id}|{payment_id}".encode("utf-8")
        expected_sig = hmac.new(key_secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()

        if not hmac.compare_digest(expected_sig, signature):
            logger.warning(f"Razorpay signature mismatch for order {order.order_ref}")
            raise ValueError("Invalid Razorpay payment signature.")

        # 2. Fetch payment from Razorpay server-side
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{BASE_URL}/payments/{payment_id}",
                auth=self._auth(),
            )
            if resp.status_code >= 400:
                raise RuntimeError(f"Could not fetch payment {payment_id} from Razorpay: {resp.text}")

            p_data = resp.json()

        # 3. Server-side payment object validation against our order
        p_order_id = p_data.get("order_id")
        if p_order_id and order.gateway_order_id and p_order_id != order.gateway_order_id:
            raise ValueError(
                f"Razorpay payment {payment_id} belongs to order {p_order_id}, not {order.gateway_order_id}."
            )

        status = p_data.get("status")
        amount = int(p_data.get("amount", 0))
        currency = p_data.get("currency")

        if status != "captured":
            raise ValueError(f"Payment {payment_id} is in status '{status}'; must be 'captured' to fulfil order.")

        if amount != int(order.total_paise):
            raise ValueError(
                f"Payment amount mismatch: expected {order.total_paise} paise, got {amount} paise."
            )

        if currency != "INR":
            raise ValueError(f"Invalid currency: {currency}")

        return GatewayPaymentResult(
            gateway_payment_id=payment_id,
            status="captured",
            amount_paise=amount,
            currency=currency,
            method=p_data.get("method"),
            raw=p_data,
        )

    def verify_webhook(self, headers: Dict[str, str], raw_body: bytes) -> bool:
        secret = settings.BILLING_RAZORPAY_WEBHOOK_SECRET
        if not secret:
            logger.warning("BILLING_RAZORPAY_WEBHOOK_SECRET is not configured.")
            return False

        sig = headers.get("x-razorpay-signature") or headers.get("X-Razorpay-Signature")
        if not sig:
            return False

        expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, sig)

    def parse_webhook(self, payload: Dict[str, Any]) -> NormalisedEvent:
        event_type = payload.get("event", "unknown")
        entity_payment = payload.get("payload", {}).get("payment", {}).get("entity", {})
        entity_order = payload.get("payload", {}).get("order", {}).get("entity", {})
        entity_sub = payload.get("payload", {}).get("subscription", {}).get("entity", {})

        gateway_payment_id = entity_payment.get("id")
        gateway_order_id = entity_payment.get("order_id") or entity_order.get("id")
        gateway_subscription_id = entity_sub.get("id") or entity_payment.get("subscription_id")
        amount_paise = entity_payment.get("amount") or entity_order.get("amount")
        status = entity_payment.get("status") or ("captured" if "captured" in event_type else "pending")

        event_id = payload.get("event_id") or f"{event_type}_{gateway_payment_id or gateway_subscription_id or gateway_order_id}"

        return NormalisedEvent(
            event_id=event_id,
            event_type=event_type,
            gateway_order_id=gateway_order_id,
            gateway_payment_id=gateway_payment_id,
            amount_paise=amount_paise,
            status=status,
            raw=payload,
            gateway_subscription_id=gateway_subscription_id,
        )

    async def fetch_order_payments(self, gateway_order_id: str) -> List[GatewayPaymentResult]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{BASE_URL}/orders/{gateway_order_id}/payments",
                auth=self._auth(),
            )
            if resp.status_code >= 400:
                return []

            data = resp.json()
            items = data.get("items", [])
            results = []
            for item in items:
                results.append(
                    GatewayPaymentResult(
                        gateway_payment_id=item["id"],
                        status=item.get("status", "unknown"),
                        amount_paise=int(item.get("amount", 0)),
                        currency=item.get("currency", "INR"),
                        method=item.get("method"),
                        raw=item,
                    )
                )
            return results

    async def refund(
        self, payment: BillingPayment, amount_paise: int, reference: str
    ) -> GatewayRefundResult:
        payload = {
            "amount": amount_paise,
            "speed": "normal",
            "notes": {"reference": reference},
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{BASE_URL}/payments/{payment.gateway_payment_id}/refund",
                json=payload,
                auth=self._auth(),
            )
            if resp.status_code >= 400:
                raise RuntimeError(f"Razorpay refund failed: {resp.text}")

            data = resp.json()
            return GatewayRefundResult(
                gateway_refund_id=data["id"],
                status=data.get("status", "processed"),
                amount_paise=int(data.get("amount", amount_paise)),
                raw=data,
            )
