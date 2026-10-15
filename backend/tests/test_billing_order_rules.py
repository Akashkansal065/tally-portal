"""What an order may do is decided by the server, and nothing is activated that was not paid for:
add-ons never buy a plan term, renewals keep paid seats, downgrades are checked and take effect later,
a webhook that fails leaves nothing half done, and nothing is sold without real seller details."""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import timedelta

import pytest
from sqlalchemy import select, update

import app.models.portal_core as P
from app.core.config import settings
from app.models.billing import (
    AccountBillingProfile, AccountSubscription, BillingInvoice, BillingOrder, BillingPlan, BillingPlanPrice,
    BillingSubscriptionEvent, BillingWebhookEvent,
)
from app.routers import auth, billing
from app.services.billing.gateways.base import GatewayOrderResult, GatewayPaymentResult
from app.services.billing.gateways.razorpay import RazorpayBillingGateway
from app.services.billing.notices import send_expiry_reminders
from app.services.billing.orders import create_order, fulfil_order
from app.services.billing.quote import calculate_quote
from app.services.billing.subscriptions import process_subscription_lifecycle, start_trial
from app.services.billing.terms import add_term, as_utc, utc_now
from tests.conftest import bearer, login, run


@pytest.fixture(autouse=True)
def gateway(monkeypatch):
    async def create(self, order):
        return GatewayOrderResult(f"rzp_order_{order.order_ref}", {"order_id": f"rzp_order_{order.order_ref}"}, {})

    async def confirm(self, order, client_payload):
        return GatewayPaymentResult(f"pay_{order.order_ref}", "captured", int(order.total_paise), "INR")

    monkeypatch.setattr(RazorpayBillingGateway, "create_order", create)
    monkeypatch.setattr(RazorpayBillingGateway, "confirm_payment", confirm)
    monkeypatch.setattr(settings, "BILLING_RAZORPAY_KEY_ID", "rzp_test_key")
    monkeypatch.setattr(settings, "BILLING_RAZORPAY_KEY_SECRET", "rzp_test_secret")
    monkeypatch.setattr(settings, "BILLING_RAZORPAY_WEBHOOK_SECRET", "wh_secret")
    monkeypatch.setattr(settings, "BILLING_CHECKOUT_ENABLED", True)


def make_account(harness, name="Alpha"):
    account = harness.add(P.Account(name=name, status="active"))
    company = harness.company(name)
    owner = harness.user(company, harness.role("Admin"), f"owner_{name.lower()}")
    harness.execute(update(P.Company).where(P.Company.company_id == company.company_id).values(account_id=account.account_id))
    harness.execute(update(P.User).where(P.User.user_id == owner.user_id).values(account_id=account.account_id))
    return account, company, owner


def in_db(harness, work):
    async def go():
        async with harness.Session() as db:
            return await work(db)
    return run(go())


async def buy(db, account_id, plan="silver", payment="pay_1", **kwargs):
    order, _ = await create_order(db, account_id=account_id, plan_id=plan, **kwargs)
    await fulfil_order(db, order.id, gateway_payment=GatewayPaymentResult(payment, "captured", order.total_paise, "INR"))
    return order


async def sub_of(db, account_id):
    sub = (await db.execute(select(AccountSubscription).where(AccountSubscription.account_id == account_id))).scalars().first()
    await db.refresh(sub)
    return sub


def test_addon_order_cannot_start_or_extend_a_plan_term(harness):
    account, _, owner = make_account(harness)
    in_db(harness, lambda db: _trial(db, account.account_id))
    client = harness.app(auth.router, billing.router)
    headers = bearer(login(client, owner.email))

    # On a trial there is no paid term to add seats to, whatever term the request names
    refused = client.post("/billing/orders", headers=headers,
                          json={"plan_id": "addon", "duration_key": "10_year", "extra_users": 1, "gateway": "razorpay"})
    assert refused.status_code == 400 and "paid plan is active" in refused.json()["detail"]
    assert in_db(harness, lambda db: sub_of(db, account.account_id)).status == "trialing"

    async def on_a_paid_term(db):
        await buy(db, account.account_id, "silver", "pay_plan", duration_key="1_year")
        before = await sub_of(db, account.account_id)
        end, plan_id = before.current_period_end, before.plan_id
        addon, _ = await create_order(db, account_id=account.account_id, plan_id="addon", duration_key="10_year", extra_users=1)
        await fulfil_order(db, addon.id, gateway_payment=GatewayPaymentResult("pay_addon", "captured", addon.total_paise, "INR"))
        after = await sub_of(db, account.account_id)
        return addon, end, plan_id, after

    addon, end, plan_id, after = in_db(harness, on_a_paid_term)
    assert addon.purpose == "addon"
    # One seat for the year that is left costs one year's price (within a paisa of rounding), not ten
    assert 99800 <= addon.taxable_paise <= 99900
    assert (after.extra_users, after.current_period_end, after.plan_id, after.status) == (1, end, plan_id, "active")


async def _trial(db, account_id):
    await start_trial(db, account_id)
    await db.commit()


def test_the_request_cannot_say_what_an_order_is(harness):
    account, _, owner = make_account(harness)
    client = harness.app(auth.router, billing.router)
    headers = bearer(login(client, owner.email))

    made = client.post("/billing/orders", headers=headers,
                       json={"plan_id": "silver", "duration_key": "1_year", "gateway": "razorpay", "purpose": "addon"})
    assert made.status_code == 200, made.text
    order = harness.query(select(BillingOrder.purpose).where(BillingOrder.order_ref == made.json()["order_ref"]))
    assert order[0][0] == "new"


def test_renewal_is_added_to_the_term_and_keeps_paid_seats(harness):
    account, _, _ = make_account(harness)

    async def work(db):
        await buy(db, account.account_id, "silver", "pay_first", duration_key="1_year", extra_users=2)
        first_end = as_utc((await sub_of(db, account.account_id)).current_period_end)
        quote = await calculate_quote(db, plan_id="silver", duration_key="1_year", account_id=account.account_id)
        renewal = await buy(db, account.account_id, "silver", "pay_renewal", duration_key="1_year")
        return first_end, quote, renewal, await sub_of(db, account.account_id)

    first_end, quote, renewal, sub = in_db(harness, work)
    assert (quote.purpose, quote.extra_users) == ("renewal", 2) and quote.extra_users_paise == 2 * 99900
    assert renewal.purpose == "renewal" and sub.extra_users == 2
    assert as_utc(sub.current_period_end) == add_term(first_end, "year", 1)


def test_upgrade_is_credited_what_was_paid_and_starts_now(harness):
    account, _, _ = make_account(harness)

    async def work(db):
        silver = await buy(db, account.account_id, "silver", "pay_silver", duration_key="1_year")
        quote = await calculate_quote(db, plan_id="gold", duration_key="1_year", account_id=account.account_id)
        await buy(db, account.account_id, "gold", "pay_gold", duration_key="1_year")
        gold = (await db.execute(select(BillingPlan.id).where(BillingPlan.code == "gold"))).scalar()
        return silver, quote, gold, await sub_of(db, account.account_id)

    silver, quote, gold_id, sub = in_db(harness, work)
    assert quote.purpose == "upgrade"
    # Bought a moment ago, so all but a sliver of what was paid comes off
    assert silver.taxable_paise - 100 <= quote.proration_credit_paise <= silver.taxable_paise
    assert sub.plan_id == gold_id
    assert abs((as_utc(sub.current_period_end) - add_term(utc_now(), "year", 1)).total_seconds()) < 60


def test_a_second_upgrade_is_not_credited_the_first_term_again(harness):
    """Silver, then Gold, then Diamond: the Diamond price has Gold's unused value taken off, not Silver's too,
    since Silver's was already credited to Gold."""
    account, _, _ = make_account(harness)

    async def work(db):
        await buy(db, account.account_id, "silver", "pay_silver", duration_key="1_year")
        gold = await buy(db, account.account_id, "gold", "pay_gold", duration_key="1_year")
        quote = await calculate_quote(db, plan_id="diamond", duration_key="1_year", account_id=account.account_id)
        return gold, quote

    gold, quote = in_db(harness, work)
    assert quote.purpose == "upgrade"
    assert gold.taxable_paise - 100 <= quote.proration_credit_paise <= gold.taxable_paise


def test_a_one_use_coupon_is_held_by_the_first_unpaid_order(harness):
    """A coupon's last use is taken when an order is made, not when it is paid, so two open orders cannot both
    get it; an order that expires unpaid gives it back."""
    from datetime import timedelta
    from app.models.billing import BillingCoupon
    from app.services.billing.orders import expire_stale_orders
    first, _, _ = make_account(harness, "First")
    second, _, _ = make_account(harness, "Second")
    harness.add(BillingCoupon(code="ONCE", kind="percent", value=10, max_redemptions=1, is_active=True))

    async def work(db):
        held, _ = await create_order(db, account_id=first.account_id, plan_id="silver", duration_key="1_year",
                                     coupon_code="ONCE")
        held_id = held.id
        with pytest.raises(ValueError, match="maximum redemptions"):
            await create_order(db, account_id=second.account_id, plan_id="silver", duration_key="1_year",
                               coupon_code="ONCE")
        await db.rollback()
        held = (await db.execute(select(BillingOrder).where(BillingOrder.id == held_id))).scalars().first()
        held.expires_at = utc_now() - timedelta(minutes=1)
        await db.commit()
        assert await expire_stale_orders(db) == 1
        retry, _ = await create_order(db, account_id=second.account_id, plan_id="silver", duration_key="1_year",
                                      coupon_code="ONCE")
        return retry

    assert in_db(harness, work).discount_paise > 0


def test_downgrade_is_refused_over_the_limits_and_otherwise_starts_when_the_term_ends(harness):
    account, company, _ = make_account(harness)
    role = harness.role("Sales")

    async def gold(db):
        await buy(db, account.account_id, "gold", "pay_gold", duration_key="1_year")
        return as_utc((await sub_of(db, account.account_id)).current_period_end)

    gold_end = in_db(harness, gold)
    second = harness.user(company, role, "second")
    harness.execute(update(P.User).where(P.User.user_id == second.user_id).values(account_id=account.account_id))

    async def too_small(db):
        with pytest.raises(ValueError, match="too small for this account"):
            await create_order(db, account_id=account.account_id, plan_id="silver", duration_key="1_year")

    in_db(harness, too_small)
    harness.execute(update(P.User).where(P.User.user_id == second.user_id).values(is_active=False))

    async def downgrade(db):
        order = await buy(db, account.account_id, "silver", "pay_silver", duration_key="1_year")
        return order, await sub_of(db, account.account_id)

    order, sub = in_db(harness, downgrade)
    plans = dict(harness.query(select(BillingPlan.code, BillingPlan.id)))
    assert order.purpose == "downgrade"
    # Still Gold for the term already paid; the Silver year that was just paid for follows it
    assert (sub.plan_id, sub.pending_plan_id) == (plans["gold"], plans["silver"])
    assert as_utc(sub.pending_effective_at) == gold_end
    assert as_utc(sub.current_period_end) == add_term(gold_end, "year", 1)

    harness.execute(update(AccountSubscription).values(pending_effective_at=utc_now() - timedelta(minutes=1)))
    counts = in_db(harness, process_subscription_lifecycle)
    sub = in_db(harness, lambda db: sub_of(db, account.account_id))
    assert counts["downgrades_applied"] == 1
    assert (sub.plan_id, sub.pending_plan_id, sub.status) == (plans["silver"], None, "active")


def test_a_plan_made_for_one_account_cannot_be_bought_by_another(harness):
    mine, _, _ = make_account(harness, "Mine")
    other, _, _ = make_account(harness, "Other")
    plan = harness.add(BillingPlan(code="custom_mine", name="Mine Only", feature_keys="[]", is_public=False,
                                   is_active=True, account_id=mine.account_id, sort_order=999, trial_days=0))
    harness.add(BillingPlanPrice(plan_id=plan.id, interval="year", interval_count=1, amount_paise=10000, is_active=True))

    async def work(db):
        assert (await calculate_quote(db, plan_id="custom_mine", account_id=mine.account_id)).base_plan_paise == 10000
        for buyer in (other.account_id, None):
            with pytest.raises(ValueError, match="not found"):
                await calculate_quote(db, plan_id="custom_mine", account_id=buyer)
        with pytest.raises(ValueError, match="not found"):
            await calculate_quote(db, plan_id="legacy", account_id=mine.account_id)

    in_db(harness, work)


def test_tax_follows_the_saved_billing_profile_not_the_request(harness):
    account, _, _ = make_account(harness)
    harness.add(AccountBillingProfile(account_id=account.account_id, legal_name="Mumbai Traders",
                                      gstin="27ABCDE1234F1Z5", state_code="27"))

    async def work(db):
        # Claiming the seller's own state would halve nothing, but it must not change the kind of tax either
        order = await buy(db, account.account_id, "silver", duration_key="1_year", buyer_state_code="07")
        invoice = (await db.execute(select(BillingInvoice).where(BillingInvoice.order_id == order.id))).scalars().first()
        return order, invoice

    order, invoice = in_db(harness, work)
    assert order.igst_paise > 0 and order.cgst_paise == 0
    assert invoice.place_of_supply == "27" and json.loads(invoice.buyer_snapshot)["state_code"] == "27"


@pytest.mark.parametrize("gstin", [None, "", "07AAAAA0000A1Z5", "NOTAGSTIN"])
def test_nothing_is_sold_without_real_seller_details(harness, monkeypatch, gstin):
    account, _, owner = make_account(harness)
    monkeypatch.setattr(settings, "BILLING_SELLER_GSTIN", gstin)
    client = harness.app(auth.router, billing.router)

    assert client.get("/billing/plans").json()["checkout_enabled"] is False
    refused = client.post("/billing/orders", headers=bearer(login(client, owner.email)),
                          json={"plan_id": "silver", "duration_key": "1_year", "gateway": "razorpay"})
    assert refused.status_code == 400

    async def operator_path(db):
        with pytest.raises(ValueError, match="Billing is not set up"):
            await create_order(db, account_id=account.account_id, plan_id="silver", gateway_code="offline", allow_offline=True)

    in_db(harness, operator_path)
    assert harness.query(select(BillingOrder.id)) == []


def test_autopay_cannot_be_claimed_while_there_are_no_mandates(harness):
    account, _, _ = make_account(harness)

    async def work(db):
        with pytest.raises(ValueError, match="Autopay is not available"):
            await create_order(db, account_id=account.account_id, plan_id="gold", duration_key="monthly", autopay=True)

    in_db(harness, work)


def _signed(client, payload, event_id):
    body = json.dumps(payload).encode()
    signature = hmac.new(b"wh_secret", body, hashlib.sha256).hexdigest()
    return client.post("/billing/webhooks/razorpay", content=body,
                       headers={"Content-Type": "application/json", "X-Razorpay-Signature": signature,
                                "X-Razorpay-Event-Id": event_id})


def test_a_failed_webhook_leaves_nothing_half_done_and_is_tried_again(harness):
    account, _, _ = make_account(harness)

    async def order_only(db):
        order, _ = await create_order(db, account_id=account.account_id, plan_id="silver", duration_key="1_year")
        return order

    order = in_db(harness, order_only)
    client = harness.app(billing.router)

    def captured(amount):
        return {"event": "payment.captured", "payload": {"payment": {"entity": {
            "id": "pay_webhook_1", "order_id": order.gateway_order_id, "amount": amount, "status": "captured"}}}}

    short = _signed(client, captured(order.total_paise - 1), "evt_1")
    assert short.status_code == 500
    saved = harness.query(select(BillingWebhookEvent.processed, BillingWebhookEvent.processing_error))
    assert saved[0][0] is False and "less than order total" in saved[0][1]
    assert harness.query(select(AccountSubscription.id)) == []
    assert harness.scalar(select(BillingOrder.status).where(BillingOrder.id == order.id)) == "pending"

    # The same delivery again is tried again, not waved through as a duplicate
    assert _signed(client, captured(order.total_paise - 1), "evt_1").status_code == 500

    paid = _signed(client, captured(order.total_paise), "evt_2")
    assert paid.status_code == 200, paid.text
    assert harness.scalar(select(AccountSubscription.status)) == "active"
    # Delivered once more, it changes nothing
    assert _signed(client, captured(order.total_paise), "evt_2").json()["status"] == "duplicate"
    assert len(harness.query(select(BillingInvoice.id))) == 1


def test_expiry_reminder_is_sent_once_per_step(harness):
    account, _, _ = make_account(harness)
    plan_id = harness.scalar(select(BillingPlan.id).where(BillingPlan.code == "gold"))
    harness.add(AccountSubscription(account_id=account.account_id, plan_id=plan_id, status="active",
                                    current_period_end=(utc_now() + timedelta(days=2, hours=12)).replace(tzinfo=None)))

    first = in_db(harness, lambda db: send_expiry_reminders(db, utc_now()))
    again = in_db(harness, lambda db: send_expiry_reminders(db, utc_now()))
    next_day = in_db(harness, lambda db: send_expiry_reminders(db, utc_now() + timedelta(days=2)))

    assert (first, again, next_day) == (1, 0, 1)
    sent = harness.query(select(BillingSubscriptionEvent.detail).where(BillingSubscriptionEvent.event_type == "expiry_reminder_sent"))
    assert sorted(json.loads(d)["days_before"] for (d,) in sent) == [1, 3]
    assert harness.query(select(P.Notification.title))[0][0] == "Your MyTally plan ends in 3 days"
