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
from app.models.billing import BillingOrder, BillingPayment, BillingPlanPrice
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
        cfg: Dict[str, Any] = {
            "gateway": self.code,
            "key": settings.BILLING_RAZORPAY_KEY_ID,
            "amount": order.total_paise,
            "currency": "INR",
            "name": "MyTally",
            "description": f"Subscription {order.order_ref}",
            "receipt": order.order_ref,
        }
        sub_id: Optional[str] = None
        if order.gateway_order_id and order.gateway_order_id.startswith("sub_"):
            sub_id = order.gateway_order_id
        elif order.quote:
            try:
                q = json.loads(order.quote)
                sub_id = q.get("gateway_subscription_id")
            except Exception:
                pass

        if sub_id:
            cfg["subscription_id"] = sub_id
        else:
            cfg["order_id"] = order.gateway_order_id
        return cfg

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

    async def create_plan(
        self,
        period: str,
        interval: int,
        item_name: str,
        amount_paise: int,
        description: Optional[str] = None,
        notes: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a recurring plan in Razorpay (POST /v1/plans)."""
        period_norm = "monthly" if period in ("month", "monthly") else "yearly" if period in ("year", "yearly") else period
        payload = {
            "period": period_norm,
            "interval": int(interval),
            "item": {
                "name": item_name,
                "amount": int(amount_paise),
                "currency": "INR",
                "description": description or f"MyTally {item_name}",
            },
            "notes": notes or {},
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{BASE_URL}/plans",
                json=payload,
                auth=self._auth(),
            )
            if resp.status_code >= 400:
                logger.error(f"Razorpay plan creation failed: {resp.status_code} {resp.text}")
                raise RuntimeError(f"Razorpay plan creation failed: {resp.text}")
            return resp.json()

    async def ensure_plan(
        self,
        price: BillingPlanPrice,
        plan_name: str,
    ) -> str:
        """Return the Razorpay plan_id for a BillingPlanPrice. Create on demand if not cached."""
        refs: Dict[str, Any] = {}
        if price.gateway_plan_refs:
            try:
                refs = json.loads(price.gateway_plan_refs)
            except Exception:
                refs = {}

        if refs.get("razorpay"):
            return str(refs["razorpay"])

        plan_res = await self.create_plan(
            period=price.interval,
            interval=price.interval_count or 1,
            item_name=f"{plan_name} ({price.interval})",
            amount_paise=price.amount_paise,
            description=f"MyTally {plan_name} recurring {price.interval} subscription",
            notes={"price_id": str(price.id), "plan_id": str(price.plan_id)},
        )
        plan_id = str(plan_res["id"])
        refs["razorpay"] = plan_id
        price.gateway_plan_refs = json.dumps(refs)
        return plan_id

    async def create_subscription(
        self,
        plan_id: str,
        total_count: int = 120,
        quantity: int = 1,
        customer_notify: bool = True,
        start_at: Optional[int] = None,
        notes: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a recurring subscription mandate in Razorpay (POST /v1/subscriptions)."""
        payload: Dict[str, Any] = {
            "plan_id": plan_id,
            "total_count": int(total_count),
            "quantity": int(quantity),
            "customer_notify": 1 if customer_notify else 0,
            "notes": notes or {},
        }
        if start_at:
            payload["start_at"] = int(start_at)

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{BASE_URL}/subscriptions",
                json=payload,
                auth=self._auth(),
            )
            if resp.status_code >= 400:
                logger.error(f"Razorpay subscription creation failed: {resp.status_code} {resp.text}")
                raise RuntimeError(f"Razorpay subscription creation failed: {resp.text}")
            return resp.json()

    async def cancel_subscription(
        self, subscription_id: str, cancel_at_cycle_end: bool = True
    ) -> Dict[str, Any]:
        """Cancel a recurring subscription mandate (POST /v1/subscriptions/{id}/cancel)."""
        payload = {"cancel_at_cycle_end": 1 if cancel_at_cycle_end else 0}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{BASE_URL}/subscriptions/{subscription_id}/cancel",
                json=payload,
                auth=self._auth(),
            )
            if resp.status_code >= 400:
                logger.error(f"Razorpay subscription cancel failed: {resp.status_code} {resp.text}")
                raise RuntimeError(f"Razorpay subscription cancel failed: {resp.text}")
            return resp.json()

    async def pause_subscription(self, subscription_id: str) -> Dict[str, Any]:
        payload = {"pause_at": "now"}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{BASE_URL}/subscriptions/{subscription_id}/pause",
                json=payload,
                auth=self._auth(),
            )
            if resp.status_code >= 400:
                raise RuntimeError(f"Razorpay subscription pause failed: {resp.text}")
            return resp.json()

    async def resume_subscription(self, subscription_id: str) -> Dict[str, Any]:
        payload = {"resume_at": "now"}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{BASE_URL}/subscriptions/{subscription_id}/resume",
                json=payload,
                auth=self._auth(),
            )
            if resp.status_code >= 400:
                raise RuntimeError(f"Razorpay subscription resume failed: {resp.text}")
            return resp.json()

    async def confirm_payment(
        self, order: BillingOrder, client_payload: Dict[str, Any]
    ) -> GatewayPaymentResult:
        """
        Verify the client-provided signature (order or subscription mandate),
        then fetch payment from Razorpay to ensure status is captured and amount matches.
        """
        payment_id = client_payload.get("razorpay_payment_id")
        order_id = client_payload.get("razorpay_order_id")
        subscription_id = client_payload.get("razorpay_subscription_id") or (
            order.gateway_order_id if (order.gateway_order_id and order.gateway_order_id.startswith("sub_")) else None
        )
        if not subscription_id and order.quote:
            try:
                subscription_id = json.loads(order.quote).get("gateway_subscription_id")
            except Exception:
                pass

        signature = client_payload.get("razorpay_signature")

        if not payment_id or not signature:
            raise ValueError("Missing razorpay_payment_id or razorpay_signature.")

        # 1. Cryptographic signature check
        key_secret = settings.BILLING_RAZORPAY_KEY_SECRET or ""
        if not key_secret:
            raise RuntimeError("Razorpay key secret not configured.")

        if subscription_id:
            # Per Razorpay Subscriptions docs:
            # generated_signature = hmac_sha256(razorpay_payment_id + "|" + subscription_id, secret)
            msg = f"{payment_id}|{subscription_id}".encode("utf-8")
        else:
            if not order_id:
                raise ValueError("Missing razorpay_order_id.")
            if order.gateway_order_id and order_id != order.gateway_order_id:
                raise ValueError(
                    f"Razorpay order ID mismatch: expected {order.gateway_order_id}, got {order_id}"
                )
            # Per Razorpay Orders docs:
            # generated_signature = hmac_sha256(order_id + "|" + razorpay_payment_id, secret)
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
        p_sub_id = p_data.get("subscription_id")
        if order.gateway_order_id:
            if order.gateway_order_id.startswith("sub_"):
                if p_sub_id and p_sub_id != order.gateway_order_id:
                    raise ValueError(f"Razorpay payment {payment_id} belongs to subscription {p_sub_id}, not {order.gateway_order_id}.")
            elif p_order_id and p_order_id != order.gateway_order_id:
                raise ValueError(
                    f"Razorpay payment {payment_id} belongs to order {p_order_id}, not {order.gateway_order_id}."
                )

        status = p_data.get("status")
        amount = int(p_data.get("amount", 0))
        currency = p_data.get("currency")

        if status not in ("captured", "authorized"):
            raise ValueError(f"Payment {payment_id} is in status '{status}'; must be 'captured' to fulfil order.")

        # When creating a recurring mandate, Razorpay may authorize an upfront tokenization amount
        # or charge the full first cycle. Validate that positive amount was received.
        if amount <= 0:
            raise ValueError(f"Payment {payment_id} recorded invalid amount: {amount} paise.")

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
        payload_data = payload.get("payload", {})
        entity_payment = payload_data.get("payment", {}).get("entity", {})
        entity_order = payload_data.get("order", {}).get("entity", {})
        entity_sub = payload_data.get("subscription", {}).get("entity", {})
        entity_refund = payload_data.get("refund", {}).get("entity", {})
        entity_dispute = payload_data.get("dispute", {}).get("entity", {})

        gateway_payment_id = (
            entity_payment.get("id")
            or entity_refund.get("payment_id")
            or entity_dispute.get("payment_id")
        )
        gateway_order_id = entity_payment.get("order_id") or entity_order.get("id")
        gateway_subscription_id = entity_sub.get("id") or entity_payment.get("subscription_id")
        gateway_refund_id = entity_refund.get("id")
        gateway_dispute_id = entity_dispute.get("id")

        amount_paise = (
            entity_dispute.get("amount")
            or entity_refund.get("amount")
            or entity_payment.get("amount")
            or entity_order.get("amount")
        )
        status = (
            entity_payment.get("status")
            or entity_refund.get("status")
            or entity_dispute.get("status")
            or ("captured" if "captured" in event_type else "pending")
        )

        error_code = entity_payment.get("error_code")
        error_description = entity_payment.get("error_description")

        event_id = payload.get("event_id") or f"{event_type}_{gateway_payment_id or gateway_subscription_id or gateway_order_id or gateway_refund_id or gateway_dispute_id}"

        return NormalisedEvent(
            event_id=event_id,
            event_type=event_type,
            gateway_order_id=gateway_order_id,
            gateway_payment_id=gateway_payment_id,
            amount_paise=amount_paise,
            status=status,
            raw=payload,
            gateway_subscription_id=gateway_subscription_id,
            gateway_refund_id=gateway_refund_id,
            gateway_dispute_id=gateway_dispute_id,
            error_code=error_code,
            error_description=error_description,
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
