"""
test_billing_orders.py – Automated tests for Phase 3:
- Order creation and quote persistence
- Idempotency via client_request_key
- Access control (only account admin can order/confirm)
- confirm_order & fulfil_order idempotency
- Sequential GST invoice numbering and tax calculation
- Razorpay and Cashfree webhook signature verification, de-duplication, and order fulfillment
- Account isolation on orders and invoices
- Buyer billing profile GET and PUT
- Stale order expiration
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update

import app.models.portal_core as P
from app.core.config import settings
from app.models.billing import (
    AccountBillingProfile,
    AccountSubscription,
    BillingInvoice,
    BillingOrder,
    BillingPayment,
    BillingPlan,
    BillingSubscriptionEvent,
    BillingWebhookEvent,
)
from app.routers import auth, billing
from app.services.billing.gateways.base import GatewayOrderResult, GatewayPaymentResult
from app.services.billing.gateways.razorpay import RazorpayBillingGateway
from app.services.billing.orders import (
    confirm_order,
    create_order,
    expire_stale_orders,
    fulfil_order,
)
from tests.conftest import bearer, login, run


@pytest.fixture(autouse=True)
def mock_razorpay_gateway(monkeypatch):
    async def mock_create_order(self, order):
        return GatewayOrderResult(
            gateway_order_id=f"rzp_order_{order.order_ref}",
            client_payload={"order_id": f"rzp_order_{order.order_ref}"},
            raw={},
        )

    async def mock_confirm_payment(self, order, client_payload):
        return GatewayPaymentResult(
            gateway_payment_id="pay_mock_12345",
            status="captured",
            amount_paise=order.total_paise,
            currency="INR",
            method="upi",
            raw={},
        )

    monkeypatch.setattr(RazorpayBillingGateway, "create_order", mock_create_order)
    monkeypatch.setattr(RazorpayBillingGateway, "confirm_payment", mock_confirm_payment)


@pytest.fixture(autouse=True)
def razorpay_test_keys(monkeypatch):
    """Checkout opens only with a gateway's keys set. Set here so these tests do not depend on another file
    having left keys behind."""
    monkeypatch.setattr(settings, "BILLING_RAZORPAY_KEY_ID", "rzp_test_key")
    monkeypatch.setattr(settings, "BILLING_RAZORPAY_KEY_SECRET", "rzp_test_secret")


def make_account(harness, name="Alpha", role_name="Admin"):
    account = harness.add(P.Account(name=name, status="active"))
    company = harness.company(name)
    role = harness.role(role_name)
    user = harness.user(company, role, f"user_{name.lower()}@test.com")
    harness.execute(update(P.Company).where(P.Company.company_id == company.company_id).values(account_id=account.account_id))
    harness.execute(update(P.User).where(P.User.user_id == user.user_id).values(account_id=account.account_id))
    harness.execute(update(P.Role).where(P.Role.role_id == role.role_id).values(account_id=account.account_id))
    return account, company, user


def test_order_creation_persists_quote_and_calculates_gst(harness):
    account, _, owner = make_account(harness, "Alpha")
    client = harness.app(auth.router, billing.router)
    token = bearer(login(client, owner.email))

    # Enable checkout for this test
    original_checkout = settings.BILLING_CHECKOUT_ENABLED
    try:
        settings.BILLING_CHECKOUT_ENABLED = True
        res = client.post(
            "/billing/orders",
            headers=token,
            json={
                "plan_id": "gold",
                "duration_key": "1_year",
                "extra_users": 1,
                "extra_companies": 1,
                "gateway": "razorpay",
                "client_request_key": "IDEMP_KEY_001",
                "buyer_state_code": "07",  # Delhi (Intra-state, CGST + SGST)
            },
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["success"] is True
        assert data["order_ref"].startswith("MT_")
        assert data["status"] == "pending"
        assert data["gateway"] == "razorpay"

        # Gold 1-year (4499) + 1 user (999) + 1 company (1499) = 6997 taxable
        # 18% GST = 1259.46 -> Total = 8256.46 -> 825646 paise
        assert data["total_paise"] == 825646
        assert data["total_rupees"] == 8256.46
    finally:
        settings.BILLING_CHECKOUT_ENABLED = original_checkout


def test_client_request_key_idempotency(harness):
    account, _, owner = make_account(harness, "Alpha")
    client = harness.app(auth.router, billing.router)
    token = bearer(login(client, owner.email))

    original_checkout = settings.BILLING_CHECKOUT_ENABLED
    try:
        settings.BILLING_CHECKOUT_ENABLED = True
        payload = {
            "plan_id": "silver",
            "duration_key": "1_year",
            "gateway": "razorpay",
            "client_request_key": "REUSED_REQ_KEY_999",
        }
        res1 = client.post("/billing/orders", headers=token, json=payload)
        assert res1.status_code == 200
        ref1 = res1.json()["order_ref"]

        # Second request with exact same client_request_key returns identical order
        res2 = client.post("/billing/orders", headers=token, json=payload)
        assert res2.status_code == 200
        ref2 = res2.json()["order_ref"]

        assert ref1 == ref2

        # Check in DB only 1 order exists
        async def count_orders():
            async with harness.Session() as db:
                orders = (await db.execute(
                    select(BillingOrder).where(BillingOrder.account_id == account.account_id)
                )).scalars().all()
                assert len(orders) == 1

        run(count_orders())
    finally:
        settings.BILLING_CHECKOUT_ENABLED = original_checkout


def test_non_admin_cannot_create_or_confirm_order(harness):
    # Create account with Viewer role
    account = harness.add(P.Account(name="Beta", status="active"))
    company = harness.company("Beta")
    role = harness.role("Viewer")
    user = harness.user(company, role, "viewer@test.com")
    harness.execute(update(P.Company).where(P.Company.company_id == company.company_id).values(account_id=account.account_id))
    harness.execute(update(P.User).where(P.User.user_id == user.user_id).values(account_id=account.account_id))
    harness.execute(update(P.Role).where(P.Role.role_id == role.role_id).values(account_id=account.account_id))

    client = harness.app(auth.router, billing.router)
    token = bearer(login(client, user.email))

    original_checkout = settings.BILLING_CHECKOUT_ENABLED
    try:
        settings.BILLING_CHECKOUT_ENABLED = True
        res = client.post(
            "/billing/orders",
            headers=token,
            json={"plan_id": "silver", "duration_key": "1_year", "gateway": "razorpay"},
        )
        assert res.status_code == 403
        assert "Only account administrators" in res.json()["detail"]
    finally:
        settings.BILLING_CHECKOUT_ENABLED = original_checkout


def test_fulfil_order_activation_and_idempotency(harness):
    account, _, _ = make_account(harness, "Gamma")

    async def run_test():
        async with harness.Session() as db:
            order, _ = await create_order(
                db,
                account_id=account.account_id,
                plan_id="gold",
                duration_key="1_year",
                gateway_code="offline",
                allow_offline=True,
            )
            order_id = order.id
            order_ref = order.order_ref

            # First fulfillment
            pmt = GatewayPaymentResult(
                gateway_payment_id="TEST_UTR_1001",
                status="captured",
                amount_paise=order.total_paise,
                currency="INR",
                method="neft",
            )
            fulfilled_1 = await fulfil_order(db, order_id, gateway_payment=pmt)
            assert fulfilled_1.status == "paid"
            assert fulfilled_1.fulfilled_at is not None

            # Verify subscription is now active
            sub = (await db.execute(
                select(AccountSubscription).where(AccountSubscription.account_id == account.account_id)
            )).scalars().first()
            assert sub is not None
            assert sub.status == "active"
            assert sub.current_period_end is not None

            # Verify invoice issued
            invoices = (await db.execute(
                select(BillingInvoice).where(BillingInvoice.order_id == order_id)
            )).scalars().all()
            assert len(invoices) == 1
            inv = invoices[0]
            assert inv.invoice_number.startswith("MT/")
            assert inv.total_paise == order.total_paise

            # Verify event recorded
            events = (await db.execute(
                select(BillingSubscriptionEvent).where(BillingSubscriptionEvent.order_id == order_id)
            )).scalars().all()
            assert len(events) == 1
            assert events[0].event_type == "plan_purchased"

            # SECOND fulfillment of the exact same order (idempotency check)
            fulfilled_2 = await fulfil_order(db, order_id, gateway_payment=pmt)
            assert fulfilled_2.status == "paid"

            # Still only 1 payment, 1 invoice, 1 subscription event
            payments_count = (await db.execute(
                select(BillingPayment).where(BillingPayment.order_id == order_id)
            )).scalars().all()
            assert len(payments_count) == 1

            invoices_count = (await db.execute(
                select(BillingInvoice).where(BillingInvoice.order_id == order_id)
            )).scalars().all()
            assert len(invoices_count) == 1

    run(run_test())


def test_confirm_order_endpoint_flow(harness):
    account, _, owner = make_account(harness, "Delta")
    client = harness.app(auth.router, billing.router)
    token = bearer(login(client, owner.email))

    original_checkout = settings.BILLING_CHECKOUT_ENABLED
    try:
        settings.BILLING_CHECKOUT_ENABLED = True

        # 1. Create order
        create_res = client.post(
            "/billing/orders",
            headers=token,
            json={"plan_id": "silver", "duration_key": "1_year", "gateway": "razorpay"},
        )
        assert create_res.status_code == 200
        order_ref = create_res.json()["order_ref"]

        # 2. Confirm order with valid mock razorpay payload
        confirm_res = client.post(
            f"/billing/orders/{order_ref}/confirm",
            headers=token,
            json={
                "payload": {
                    "razorpay_payment_id": "pay_mock_12345",
                    "razorpay_order_id": f"rzp_order_{order_ref}",
                    "razorpay_signature": "sig_mock_123",
                }
            },
        )
        assert confirm_res.status_code == 200, confirm_res.text
        assert confirm_res.json()["status"] == "paid"

        # 3. Poll order endpoint
        get_res = client.get(f"/billing/orders/{order_ref}", headers=token)
        assert get_res.status_code == 200
        assert get_res.json()["status"] == "paid"
        assert get_res.json()["fulfilled_at"] is not None

        # 4. Check entitlements reflect silver active
        sub_res = client.get("/billing/current-subscription", headers=token)
        assert sub_res.status_code == 200
        assert sub_res.json()["status"] == "active"
        assert sub_res.json()["tier"] == "silver"
    finally:
        settings.BILLING_CHECKOUT_ENABLED = original_checkout


def test_razorpay_webhook_verification_and_deduplication(harness):
    account, _, owner = make_account(harness, "Epsilon")

    async def setup_order():
        async with harness.Session() as db:
            order, _ = await create_order(
                db,
                account_id=account.account_id,
                plan_id="diamond",
                duration_key="1_year",
                gateway_code="offline",
                allow_offline=True,
            )
            order.gateway = "razorpay"
            order.gateway_order_id = "order_RZP_EPSILON_123"
            await db.commit()
            return order.order_ref, order.total_paise

    order_ref, total_paise = run(setup_order())
    client = harness.app(auth.router, billing.router)

    # Configure webhook secret
    webhook_secret = "test_rzp_webhook_secret_key"
    orig_key = settings.BILLING_RAZORPAY_KEY_ID
    orig_sec = settings.BILLING_RAZORPAY_KEY_SECRET
    orig_wh = settings.BILLING_RAZORPAY_WEBHOOK_SECRET

    try:
        settings.BILLING_RAZORPAY_KEY_ID = "rzp_test_key"
        settings.BILLING_RAZORPAY_KEY_SECRET = "rzp_test_sec"
        settings.BILLING_RAZORPAY_WEBHOOK_SECRET = webhook_secret

        payload = {
            "entity": "event",
            "account_id": "acc_123",
            "event": "payment.captured",
            "contains": ["payment"],
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_RZP_TEST_9999",
                        "order_id": "order_RZP_EPSILON_123",
                        "amount": total_paise,
                        "currency": "INR",
                        "status": "captured",
                        "method": "upi",
                    }
                }
            },
        }
        body_bytes = json.dumps(payload).encode("utf-8")
        valid_signature = hmac.new(webhook_secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()

        # 1. Invalid signature returns 400
        res_bad = client.post(
            "/billing/webhooks/razorpay",
            content=body_bytes,
            headers={"Content-Type": "application/json", "X-Razorpay-Signature": "invalid_sig"},
        )
        assert res_bad.status_code == 400

        # 2. Valid signature returns 200 and fulfills order
        res_good = client.post(
            "/billing/webhooks/razorpay",
            content=body_bytes,
            headers={"Content-Type": "application/json", "X-Razorpay-Signature": valid_signature},
        )
        assert res_good.status_code == 200, res_good.text
        assert res_good.json()["success"] is True

        # Check order fulfilled
        async def check_order():
            async with harness.Session() as db:
                ord_row = (await db.execute(
                    select(BillingOrder).where(BillingOrder.order_ref == order_ref)
                )).scalars().first()
                assert ord_row.status == "paid"
                assert ord_row.fulfilled_at is not None

        run(check_order())

        # 3. Duplicate webhook returns duplicate status (200)
        res_dup = client.post(
            "/billing/webhooks/razorpay",
            content=body_bytes,
            headers={"Content-Type": "application/json", "X-Razorpay-Signature": valid_signature},
        )
        assert res_dup.status_code == 200
        assert res_dup.json()["status"] == "duplicate"

    finally:
        settings.BILLING_RAZORPAY_KEY_ID = orig_key
        settings.BILLING_RAZORPAY_KEY_SECRET = orig_sec
        settings.BILLING_RAZORPAY_WEBHOOK_SECRET = orig_wh


def test_cashfree_webhook_verification(harness):
    account, _, _ = make_account(harness, "Zeta")

    async def setup_order():
        async with harness.Session() as db:
            order, _ = await create_order(
                db,
                account_id=account.account_id,
                plan_id="silver",
                duration_key="1_year",
                gateway_code="offline",
                allow_offline=True,
            )
            order.gateway = "cashfree"
            order.gateway_order_id = "CF_ORDER_ZETA_123"
            await db.commit()
            return order.order_ref, order.total_paise

    order_ref, total_paise = run(setup_order())
    client = harness.app(auth.router, billing.router)

    orig_app = settings.BILLING_CASHFREE_APP_ID
    orig_sec = settings.BILLING_CASHFREE_SECRET

    try:
        settings.BILLING_CASHFREE_APP_ID = "cf_test_app"
        settings.BILLING_CASHFREE_SECRET = "cf_test_secret"

        payload = {
            "type": "PAYMENT_SUCCESS_WEBHOOK",
            "event_time": "2026-10-12T10:00:00Z",
            "data": {
                "order": {
                    "order_id": order_ref,
                    "order_amount": round(total_paise / 100, 2),
                    "order_currency": "INR",
                },
                "payment": {
                    "cf_payment_id": "11223344",
                    "payment_status": "SUCCESS",
                    "payment_amount": round(total_paise / 100, 2),
                    "payment_currency": "INR",
                },
            },
        }
        body_bytes = json.dumps(payload).encode("utf-8")
        timestamp = "1728734400"

        # Compute Cashfree signature: base64(hmac_sha256(timestamp + raw_body, secret))
        data_to_sign = timestamp.encode("utf-8") + body_bytes
        sig = base64.b64encode(
            hmac.new(b"cf_test_secret", data_to_sign, hashlib.sha256).digest()
        ).decode("utf-8")

        # 1. Invalid signature returns 400
        res_bad = client.post(
            "/billing/webhooks/cashfree",
            content=body_bytes,
            headers={
                "Content-Type": "application/json",
                "x-webhook-timestamp": timestamp,
                "x-webhook-signature": "wrong_sig",
            },
        )
        assert res_bad.status_code == 400

        # 2. Valid signature returns 200
        res_good = client.post(
            "/billing/webhooks/cashfree",
            content=body_bytes,
            headers={
                "Content-Type": "application/json",
                "x-webhook-timestamp": timestamp,
                "x-webhook-signature": sig,
            },
        )
        assert res_good.status_code == 200, res_good.text
        assert res_good.json()["success"] is True

        # 3. Duplicate returns duplicate
        res_dup = client.post(
            "/billing/webhooks/cashfree",
            content=body_bytes,
            headers={
                "Content-Type": "application/json",
                "x-webhook-timestamp": timestamp,
                "x-webhook-signature": sig,
            },
        )
        assert res_dup.status_code == 200
        assert res_dup.json()["status"] == "duplicate"
    finally:
        settings.BILLING_CASHFREE_APP_ID = orig_app
        settings.BILLING_CASHFREE_SECRET = orig_sec


def test_invoices_retrieval_and_tenant_isolation(harness):
    account_a, _, owner_a = make_account(harness, "AccountA")
    account_b, _, owner_b = make_account(harness, "AccountB")

    # Fulfill order for Account A
    async def create_and_pay():
        async with harness.Session() as db:
            order, _ = await create_order(
                db,
                account_id=account_a.account_id,
                plan_id="gold",
                duration_key="1_year",
                gateway_code="offline",
                allow_offline=True,
            )
            pmt = GatewayPaymentResult(
                gateway_payment_id="PAY_A_1",
                status="captured",
                amount_paise=order.total_paise,
                currency="INR",
            )
            await fulfil_order(db, order.id, gateway_payment=pmt)
            inv = (await db.execute(
                select(BillingInvoice).where(BillingInvoice.order_id == order.id)
            )).scalars().first()
            return inv.id

    invoice_a_id = run(create_and_pay())

    client = harness.app(auth.router, billing.router)
    token_a = bearer(login(client, owner_a.email))
    token_b = bearer(login(client, owner_b.email))

    # Account A can see its invoice
    res_a = client.get("/billing/invoices", headers=token_a)
    assert res_a.status_code == 200
    invoices = res_a.json()["invoices"]
    assert len(invoices) == 1
    assert invoices[0]["id"] == invoice_a_id

    # Account A can view invoice details
    res_a_detail = client.get(f"/billing/invoices/{invoice_a_id}", headers=token_a)
    assert res_a_detail.status_code == 200
    assert res_a_detail.json()["invoice_number"].startswith("MT/")

    # Account B sees empty list
    res_b = client.get("/billing/invoices", headers=token_b)
    assert res_b.status_code == 200
    assert len(res_b.json()["invoices"]) == 0

    # Account B CANNOT view Account A's invoice, and is not told it exists
    res_b_detail = client.get(f"/billing/invoices/{invoice_a_id}", headers=token_b)
    assert res_b_detail.status_code == 404

    # Naming one's own role "superadmin" does not open other accounts' billing
    from app.core.permissions import clear_all_auth_and_permission_caches
    harness.execute(update(P.Role).where(P.Role.role_id == owner_b.role_id).values(name="superadmin"))
    clear_all_auth_and_permission_caches()
    token_b = bearer(login(client, owner_b.email))
    assert client.get(f"/billing/invoices/{invoice_a_id}", headers=token_b).status_code == 404


def test_billing_profile_get_and_update(harness):
    account, company, owner = make_account(harness, "Eta")
    client = harness.app(auth.router, billing.router)
    token = bearer(login(client, owner.email))

    # 1. GET profile prefilled from company
    res_get = client.get("/billing/profile", headers=token)
    assert res_get.status_code == 200
    prof = res_get.json()["profile"]
    assert prof["legal_name"] == company.name

    # 2. Invalid GSTIN fails with 400
    res_bad = client.put(
        "/billing/profile",
        headers=token,
        json={"gstin": "123"},
    )
    assert res_bad.status_code == 400
    assert "15" in res_bad.json()["detail"]

    # 3. Valid update succeeds
    res_good = client.put(
        "/billing/profile",
        headers=token,
        json={
            "legal_name": "Eta Enterprises Pvt Ltd",
            "gstin": "07AAAAA1234A1Z5",
            "state_code": "07",
            "email": "finance@eta.com",
            "phone": "+91 9876543210",
        },
    )
    assert res_good.status_code == 200

    # 4. GET profile returns updated values
    res_get2 = client.get("/billing/profile", headers=token)
    assert res_get2.status_code == 200
    updated_prof = res_get2.json()["profile"]
    assert updated_prof["legal_name"] == "Eta Enterprises Pvt Ltd"
    assert updated_prof["gstin"] == "07AAAAA1234A1Z5"


def test_stale_orders_expiration(harness):
    account, _, _ = make_account(harness, "Theta")

    async def run_test():
        async with harness.Session() as db:
            order, _ = await create_order(
                db,
                account_id=account.account_id,
                plan_id="silver",
                duration_key="1_year",
                gateway_code="offline",
                allow_offline=True,
            )
            # Backdate expires_at to 1 hour ago
            order.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
            await db.commit()

            expired_count = await expire_stale_orders(db)
            assert expired_count == 1

            # Check order status in DB
            reloaded = (await db.execute(
                select(BillingOrder).where(BillingOrder.id == order.id)
            )).scalars().first()
            assert reloaded.status == "expired"

    run(run_test())
