from sqlalchemy import Column, Integer, BigInteger, String, Enum, Numeric, ForeignKey, DateTime, JSON, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.core.config import settings

class PaymentGatewayConfig(Base):
    __tablename__ = "payment_gateway_configs"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    gateway_config_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    gateway = Column(Enum('Razorpay', 'Stripe', name='gateway_provider_enum'), nullable=False)
    public_key = Column(String(255), nullable=False)
    secret_key_ref = Column(String(100), nullable=False)
    webhook_secret_ref = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True)
    is_test_mode = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

class PaymentLink(Base):
    __tablename__ = "payment_links"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    payment_link_id = Column(BigInteger, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    bill_id = Column(BigInteger, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.bills.bill_id", ondelete="CASCADE"), nullable=False)
    gateway_config_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.payment_gateway_configs.gateway_config_id"), nullable=False)
    gateway_link_id = Column(String(100), nullable=True)
    link_url = Column(String(500), nullable=True)
    amount = Column(Numeric(18, 2), nullable=False)
    currency = Column(String(3), default="INR")
    status = Column(Enum('Created', 'Sent', 'Paid', 'Expired', 'Cancelled', name='payment_link_status_enum'), default='Created')
    expires_at = Column(DateTime, nullable=True)
    created_by = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

class GatewayTransaction(Base):
    __tablename__ = "gateway_transactions"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    transaction_id = Column(BigInteger, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    payment_link_id = Column(BigInteger, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.payment_links.payment_link_id", ondelete="SET NULL"), nullable=True)
    bill_id = Column(BigInteger, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.bills.bill_id"), nullable=False)
    gateway_config_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.payment_gateway_configs.gateway_config_id"), nullable=False)
    gateway_payment_id = Column(String(100), nullable=False)
    gateway_order_id = Column(String(100), nullable=True)
    amount = Column(Numeric(18, 2), nullable=False)
    currency = Column(String(3), default="INR")
    status = Column(Enum('Created', 'Authorized', 'Captured', 'Failed', 'Refunded', 'Partially Refunded', name='gateway_txn_status_enum'), nullable=False)
    failure_reason = Column(String(255), nullable=True)
    method = Column(String(30), nullable=True)
    voucher_id = Column(BigInteger, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.vouchers.voucher_id", ondelete="SET NULL"), nullable=True)
    raw_payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    webhook_event_id = Column(BigInteger, primary_key=True, index=True)
    gateway_config_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.payment_gateway_configs.gateway_config_id", ondelete="CASCADE"), nullable=False)
    gateway_event_id = Column(String(150), nullable=False)
    event_type = Column(String(60), nullable=False)
    payload = Column(JSON, nullable=False)
    signature_verified = Column(Boolean, default=False)
    processed = Column(Boolean, default=False)
    processing_error = Column(String(500), nullable=True)
    received_at = Column(DateTime, server_default=func.now())
    processed_at = Column(DateTime, nullable=True)
