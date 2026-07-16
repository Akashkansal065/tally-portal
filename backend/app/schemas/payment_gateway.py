from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime

class PaymentGatewayConfigCreate(BaseModel):
    gateway: str  # 'Razorpay' or 'Stripe'
    public_key: str
    secret_key_ref: str
    webhook_secret_ref: str
    is_test_mode: bool = True

class PaymentGatewayConfigResponse(PaymentGatewayConfigCreate):
    gateway_config_id: int
    company_id: int
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
