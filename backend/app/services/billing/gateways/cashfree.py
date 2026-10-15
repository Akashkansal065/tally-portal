"""
cashfree.py – Cashfree Payment Gateway adapter using httpx.
"""

from __future__ import annotations

import base64
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

logger = logging.getLogger("app.services.billing.gateways.cashfree")


class CashfreeBillingGateway:
    code = "cashfree"
    name = "Cashfree"

    @property
    def is_configured(self) -> bool:
        return bool(
            settings.BILLING_CASHFREE_APP_ID and settings.BILLING_CASHFREE_SECRET
        )

    def _base_url(self) -> str:
        env = (settings.BILLING_CASHFREE_ENV or "sandbox").lower()
        if env == "production":
            return "https://api.cashfree.com/pg"
        return "https://sandbox.cashfree.com/pg"

    def _headers(self) -> Dict[str, str]:
        if not self.is_configured:
            raise RuntimeError("Cashfree gateway is not configured with app_id and secret.")
        return {
            "x-client-id": settings.BILLING_CASHFREE_APP_ID or "",
            "x-client-secret": settings.BILLING_CASHFREE_SECRET or "",
            "x-api-version": "2023-08-01",
            "Content-Type": "application/json",
        }

    def checkout_config(self, order: BillingOrder) -> Dict[str, Any]:
        return {
            "gateway": self.code,
            "order_id": order.order_ref,
            "env": settings.BILLING_CASHFREE_ENV or "sandbox",
            "amount": round(order.total_paise / 100, 2),
            "currency": "INR",
        }

    async def create_order(self, order: BillingOrder) -> GatewayOrderResult:
        # Cashfree amounts are in Rupees (float/decimal)
        amount_rupees = round(order.total_paise / 100, 2)

        buyer_data = {}
        if order.buyer_snapshot:
            try:
                buyer_data = json.loads(order.buyer_snapshot)
            except Exception:
                buyer_data = {}

        cust_email = buyer_data.get("email") or f"billing+acc{order.account_id}@mytally.in"
        clean_phone = "".join(filter(str.isdigit, str(buyer_data.get("phone") or "")))[-10:]
        if len(clean_phone) < 10:
            raise ValueError("Cashfree needs a 10-digit mobile number. Add one to your billing details and try again.")

        payload: Dict[str, Any] = {
            "order_id": order.order_ref,
            "order_amount": amount_rupees,
            "order_currency": "INR",
            "customer_details": {
                "customer_id": f"acc_{order.account_id}",
                "customer_email": cust_email,
                "customer_phone": clean_phone,
            },
            "order_note": f"Subscription {order.order_ref}",
        }

        notify_url = getattr(settings, "BILLING_CASHFREE_NOTIFY_URL", None) or (
            f"{settings.APP_PUBLIC_URL.rstrip('/')}/billing/webhooks/cashfree"
            if settings.APP_PUBLIC_URL
            else None
        )
        if notify_url:
            payload["order_meta"] = {"notify_url": notify_url}

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self._base_url()}/orders",
                json=payload,
                headers=self._headers(),
            )
            if resp.status_code >= 400:
                logger.error(f"Cashfree order creation failed: {resp.status_code} {resp.text}")
                raise RuntimeError(f"Cashfree returned {resp.status_code}: {resp.text}")

            data = resp.json()
            session_id = data.get("payment_session_id")
            cf_order_id = str(data.get("cf_order_id", data.get("order_id")))

            return GatewayOrderResult(
                gateway_order_id=cf_order_id,
                client_payload={"payment_session_id": session_id, "order_id": order.order_ref},
                raw=data,
            )

    async def confirm_payment(
        self, order: BillingOrder, client_payload: Dict[str, Any]
    ) -> GatewayPaymentResult:
        """
        Verify payment by polling Cashfree order payments server-side.
        """
        payments = await self.fetch_order_payments(order.order_ref)
        if not payments:
            # Check by cf_order_id if different
            if order.gateway_order_id and order.gateway_order_id != order.order_ref:
                payments = await self.fetch_order_payments(order.gateway_order_id)

        captured = [p for p in payments if p.status in ("SUCCESS", "captured")]
        if not captured:
            raise ValueError(f"No captured payment found on Cashfree for order {order.order_ref}.")

        best = captured[0]
        if best.amount_paise != int(order.total_paise):
            raise ValueError(
                f"Amount mismatch on Cashfree: expected {order.total_paise} paise, got {best.amount_paise} paise."
            )

        return best

    def verify_webhook(self, headers: Dict[str, str], raw_body: bytes) -> bool:
        secret = settings.BILLING_CASHFREE_SECRET
        if not secret:
            return False

        ts = headers.get("x-webhook-timestamp")
        sig = headers.get("x-webhook-signature")
        if not ts or not sig:
            return False

        # Compute HMAC signature: base64(hmac_sha256(timestamp + raw_body, secret))
        data_to_sign = ts.encode("utf-8") + raw_body
        expected = base64.b64encode(
            hmac.new(secret.encode("utf-8"), data_to_sign, hashlib.sha256).digest()
        ).decode("utf-8")

        return hmac.compare_digest(expected, sig)

    def parse_webhook(self, payload: Dict[str, Any]) -> NormalisedEvent:
        data = payload.get("data", {})
        order_data = data.get("order", {})
        payment_data = data.get("payment", {})
        subscription_data = data.get("subscription", {})

        event_type = payload.get("type", "unknown")
        gateway_order_id = str(order_data.get("order_id") or "")
        gateway_payment_id = str(payment_data.get("cf_payment_id") or payment_data.get("payment_id") or "")
        gateway_subscription_id = str(subscription_data.get("sub_reference_id") or subscription_data.get("subscription_id") or "") or None

        amount_rupees = payment_data.get("payment_amount") or order_data.get("order_amount") or 0
        amount_paise = int(round(float(amount_rupees) * 100))

        cf_status = payment_data.get("payment_status", "UNKNOWN")
        status = "captured" if cf_status == "SUCCESS" else "pending"

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
                f"{self._base_url()}/orders/{gateway_order_id}/payments",
                headers=self._headers(),
            )
            if resp.status_code >= 400:
                return []

            items = resp.json()
            if not isinstance(items, list):
                return []

            results = []
            for item in items:
                amt_rupees = float(item.get("payment_amount", 0))
                amt_paise = int(round(amt_rupees * 100))
                cf_status = item.get("payment_status", "UNKNOWN")
                results.append(
                    GatewayPaymentResult(
                        gateway_payment_id=str(item.get("cf_payment_id", "")),
                        status="captured" if cf_status == "SUCCESS" else cf_status.lower(),
                        amount_paise=amt_paise,
                        currency=item.get("payment_currency", "INR"),
                        method=item.get("payment_group"),
                        raw=item,
                    )
                )
            return results

    async def refund(
        self, payment: BillingPayment, amount_paise: int, reference: str, order: Optional[BillingOrder] = None
    ) -> GatewayRefundResult:
        amount_rupees = round(amount_paise / 100, 2)
        payload = {
            "refund_amount": amount_rupees,
            "refund_id": reference,
            "refund_note": f"Refund for {payment.gateway_payment_id}",
        }

        # Cashfree refund endpoint requires /orders/{order_id}/refunds
        order_ref = None
        if order:
            order_ref = order.order_ref
        elif payment.raw:
            try:
                raw_data = json.loads(payment.raw) if isinstance(payment.raw, str) else payment.raw
                order_ref = raw_data.get("order_id") or raw_data.get("order", {}).get("order_id")
            except Exception:
                pass

        target_order_id = order_ref or payment.gateway_payment_id

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self._base_url()}/orders/{target_order_id}/refunds",
                json=payload,
                headers=self._headers(),
            )
            if resp.status_code >= 400:
                raise RuntimeError(f"Cashfree refund failed: {resp.text}")

            data = resp.json()
            return GatewayRefundResult(
                gateway_refund_id=str(data.get("cf_refund_id", reference)),
                status=data.get("refund_status", "SUCCESS"),
                amount_paise=amount_paise,
                raw=data,
            )
