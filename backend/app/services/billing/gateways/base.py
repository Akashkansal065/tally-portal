"""
base.py – Abstract protocol and types for billing payment gateways.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol

from app.models.billing import BillingOrder, BillingPayment


@dataclass
class GatewayOrderResult:
    gateway_order_id: str
    client_payload: Dict[str, Any]
    raw: Dict[str, Any]


@dataclass
class GatewayPaymentResult:
    gateway_payment_id: str
    status: str                         # "captured" | "failed" | "pending"
    amount_paise: int
    currency: str
    method: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None


@dataclass
class GatewayRefundResult:
    gateway_refund_id: str
    status: str
    amount_paise: int
    raw: Optional[Dict[str, Any]] = None


@dataclass
class NormalisedEvent:
    event_id: str
    event_type: str                     # "payment.captured", "payment.failed", "refund.processed", "subscription.charged", etc.
    gateway_order_id: Optional[str]
    gateway_payment_id: Optional[str]
    amount_paise: Optional[int]
    status: str
    raw: Dict[str, Any]
    gateway_subscription_id: Optional[str] = None


class BillingGateway(Protocol):
    code: str
    name: str

    @property
    def is_configured(self) -> bool:
        """Whether this gateway has the required credentials in settings."""
        ...

    def checkout_config(self, order: BillingOrder) -> Dict[str, Any]:
        """Data passed to the frontend checkout SDK (key, env, etc)."""
        ...

    async def create_order(self, order: BillingOrder) -> GatewayOrderResult:
        """Create an order in the gateway's system before the customer pays."""
        ...

    async def confirm_payment(
        self, order: BillingOrder, client_payload: Dict[str, Any]
    ) -> GatewayPaymentResult:
        """Verify client-submitted payment details server-side and ensure captured status."""
        ...

    def verify_webhook(self, headers: Dict[str, str], raw_body: bytes) -> bool:
        """Verify the cryptographic signature of an incoming webhook."""
        ...

    def parse_webhook(self, payload: Dict[str, Any]) -> NormalisedEvent:
        """Parse raw webhook JSON into a NormalisedEvent."""
        ...

    async def fetch_order_payments(self, gateway_order_id: str) -> List[GatewayPaymentResult]:
        """Fetch all payments recorded under a gateway order."""
        ...

    async def refund(
        self, payment: BillingPayment, amount_paise: int, reference: str
    ) -> GatewayRefundResult:
        """Initiate a refund against a captured payment."""
        ...
