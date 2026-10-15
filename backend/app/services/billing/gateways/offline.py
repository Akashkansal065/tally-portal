"""
offline.py – Offline / Manual operator payment adapter (NEFT / RTGS / Cheque / UTR).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.models.billing import BillingOrder, BillingPayment
from app.services.billing.gateways.base import (
    GatewayOrderResult, GatewayPaymentResult, GatewayRefundResult, NormalisedEvent,
)

logger = logging.getLogger("app.services.billing.gateways.offline")


class OfflineBillingGateway:
    code = "offline"
    name = "Offline Payment"

    @property
    def is_configured(self) -> bool:
        return True

    def checkout_config(self, order: BillingOrder) -> Dict[str, Any]:
        return {
            "gateway": self.code,
            "order_id": order.order_ref,
            "amount": round(order.total_paise / 100, 2),
            "currency": "INR",
        }

    async def create_order(self, order: BillingOrder) -> GatewayOrderResult:
        return GatewayOrderResult(
            gateway_order_id=f"OFFLINE_{order.order_ref}",
            client_payload={"order_id": order.order_ref},
            raw={"type": "offline_manual"},
        )

    async def confirm_payment(
        self, order: BillingOrder, client_payload: Dict[str, Any]
    ) -> GatewayPaymentResult:
        raise ValueError("Offline payments cannot be confirmed via customer endpoint. They must be verified and recorded by a platform operator.")

    def verify_webhook(self, headers: Dict[str, str], raw_body: bytes) -> bool:
        return False

    def parse_webhook(self, payload: Dict[str, Any]) -> NormalisedEvent:
        raise NotImplementedError("Offline gateway does not support incoming webhooks.")

    async def fetch_order_payments(self, gateway_order_id: str) -> List[GatewayPaymentResult]:
        return []

    async def refund(
        self, payment: BillingPayment, amount_paise: int, reference: str
    ) -> GatewayRefundResult:
        return GatewayRefundResult(
            gateway_refund_id=f"REFUND_{reference}",
            status="processed",
            amount_paise=amount_paise,
            raw={"reason": "manual_offline_refund"},
        )
