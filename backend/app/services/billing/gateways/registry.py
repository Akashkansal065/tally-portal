"""
registry.py – Billing payment gateway registry and factory.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from app.services.billing.gateways.base import BillingGateway
from app.services.billing.gateways.cashfree import CashfreeBillingGateway
from app.services.billing.gateways.offline import OfflineBillingGateway
from app.services.billing.gateways.razorpay import RazorpayBillingGateway

_GATEWAYS: Dict[str, BillingGateway] = {
    "razorpay": RazorpayBillingGateway(),
    "cashfree": CashfreeBillingGateway(),
    "offline": OfflineBillingGateway(),
}


def get_gateway(code: str) -> BillingGateway:
    """Retrieve gateway adapter by code. Raises ValueError if unknown."""
    gw = _GATEWAYS.get(code.lower())
    if not gw:
        valid = list(_GATEWAYS.keys())
        raise ValueError(f"Unknown billing gateway '{code}'. Valid gateways: {valid}")
    return gw


def get_enabled_gateways() -> List[Dict[str, str]]:
    """Return configured gateways available for online checkout."""
    enabled = []
    for code in ("razorpay", "cashfree"):
        gw = _GATEWAYS[code]
        if gw.is_configured:
            enabled.append({
                "code": gw.code,
                "name": gw.name,
            })
    return enabled
