from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from decimal import Decimal
from datetime import datetime

class PaymentGatewayConfigCreate(BaseModel):
    gateway: Literal["Razorpay", "Stripe"]
    public_key: str
    secret_key_ref: str
    # Webhooks are rejected unless they are signed with this secret
    webhook_secret_ref: str = Field(min_length=8)
    # Bank/cash ledger debited when a captured payment is posted as a Receipt
    settlement_ledger_id: int
    is_test_mode: bool = True

class PaymentGatewayConfigResponse(BaseModel):
    """Never echoes secret_key_ref / webhook_secret_ref back to clients."""
    gateway_config_id: int
    company_id: int
    gateway: str
    public_key: str
    settlement_ledger_id: Optional[int] = None
    is_test_mode: bool
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class PaymentLinkCreate(BaseModel):
    bill_id: int
    amount: Decimal
    currency: str = "INR"

class PaymentLinkResponse(BaseModel):
    payment_link_id: int
    company_id: int
    bill_id: int
    gateway_config_id: int
    gateway_link_id: Optional[str] = None
    link_url: Optional[str] = None
    amount: Decimal
    currency: str
    status: str
    expires_at: Optional[datetime] = None
    created_by: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class WebhookPayload(BaseModel):
    event: str
    payload: Dict[str, Any]
