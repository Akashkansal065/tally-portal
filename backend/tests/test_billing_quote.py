"""
Unit tests for billing quotes: plan prices, terms, add-ons, coupon validation and caps,
intra-state CGST/SGST vs inter-state IGST, and input constraints.
"""
import json
import pytest
from sqlalchemy import select

from app.models.billing import BillingCoupon, BillingCouponRedemption
from app.routers import billing
from tests.conftest import bearer, login


def world(harness):
    client = harness.app(billing.router)
    return client


def test_quote_base_plans_and_terms(harness):
    client = world(harness)

    # Silver 1-year: ₹2499 taxable + 18% IGST = ₹2948.82
    res = client.post("/billing/quote", json={"plan_id": "silver", "duration_key": "1_year"}).json()
    assert res["success"] is True
    assert res["plan_code"] == "silver"
    assert res["taxable"] == 2499.0
    assert res["taxable_paise"] == 249900
    assert res["igst"] == 449.82
    assert res["total"] == 2948.82

    # Gold 2-year: ₹7499 taxable + 18% IGST = ₹8848.82
    res = client.post("/billing/quote", json={"plan_id": "gold", "duration_key": "2_year"}).json()
    assert res["success"] is True
    assert res["taxable"] == 7499.0
    assert res["total"] == 7499.0 + round(7499.0 * 0.18, 2)

    # Diamond 3-year: ₹14999 taxable
    res = client.post("/billing/quote", json={"plan_id": "diamond", "duration_key": "3_year"}).json()
    assert res["success"] is True
    assert res["taxable"] == 14999.0


def test_quote_addons_multi_year(harness):
    client = world(harness)

    # Gold 2-year (7499) + 2 extra users (999 * 2 * 2 = 3996) + 1 extra company (1499 * 1 * 2 = 2998)
    # Subtotal: 7499 + 3996 + 2998 = 14493.0
    res = client.post(
        "/billing/quote",
        json={"plan_id": "gold", "duration_key": "2_year", "extra_users": 2, "extra_companies": 1},
    ).json()
    assert res["success"] is True
    assert res["base_plan"] == 7499.0
    assert res["extra_users"] == 3996.0
    assert res["extra_companies"] == 2998.0
    assert res["taxable"] == 14493.0
    assert res["total"] == round(14493.0 * 1.18, 2)


def test_quote_tax_split_intra_vs_inter_state(harness):
    client = world(harness)

    # Intra-state (seller=07 Delhi, buyer=07 Delhi): CGST (9%) + SGST (9%), IGST = 0
    res_intra = client.post(
        "/billing/quote",
        json={"plan_id": "silver", "duration_key": "1_year", "buyer_state_code": "07"},
    ).json()
    assert res_intra["igst_applied"] is False
    assert res_intra["igst_paise"] == 0
    assert res_intra["cgst_paise"] > 0
    assert res_intra["sgst_paise"] > 0
    assert res_intra["cgst_paise"] + res_intra["sgst_paise"] == 44982  # ₹449.82
    assert res_intra["total"] == 2948.82

    # Inter-state (seller=07 Delhi, buyer=27 Maharashtra): IGST (18%), CGST = 0, SGST = 0
    res_inter = client.post(
        "/billing/quote",
        json={"plan_id": "silver", "duration_key": "1_year", "buyer_state_code": "27"},
    ).json()
    assert res_inter["igst_applied"] is True
    assert res_inter["igst_paise"] == 44982
    assert res_inter["cgst_paise"] == 0
    assert res_inter["sgst_paise"] == 0


def test_quote_coupon_percentage_with_cap(harness):
    client = world(harness)

    # Seed a 20% coupon capped at ₹1000 (100000 paise)
    coupon = harness.add(
        BillingCoupon(
            code="SAVE20",
            kind="percent",
            value=20,
            max_discount_paise=100000,
            is_active=True,
        )
    )

    # Gold 1-year is ₹4499. 20% of 449900 paise = 89980 paise (₹899.80, under ₹1000 cap)
    res1 = client.post(
        "/billing/quote",
        json={"plan_id": "gold", "duration_key": "1_year", "coupon_code": "SAVE20"},
    ).json()
    assert res1["discount_paise"] == 89980
    assert res1["discount"] == 899.8
    assert res1["taxable"] == 4499.0 - 899.8

    # Diamond 1-year is ₹6999. 20% of 699900 paise = 139980 paise -> capped at 100000 paise (₹1000)
    res2 = client.post(
        "/billing/quote",
        json={"plan_id": "diamond", "duration_key": "1_year", "coupon_code": "SAVE20"},
    ).json()
    assert res2["discount_paise"] == 100000
    assert res2["discount"] == 1000.0
    assert res2["taxable"] == 5999.0


def test_quote_coupon_plan_restriction(harness):
    client = world(harness)

    # Coupon restricted to diamond only
    harness.add(
        BillingCoupon(
            code="DIAMONDONLY",
            kind="flat",
            value=100000,  # ₹1000
            plan_codes=json.dumps(["diamond"]),
            is_active=True,
        )
    )

    # Using on Silver must fail with 400
    res_bad = client.post(
        "/billing/quote",
        json={"plan_id": "silver", "duration_key": "1_year", "coupon_code": "DIAMONDONLY"},
    )
    assert res_bad.status_code == 400
    assert "not valid for the Silver plan" in res_bad.json()["detail"]

    # Using on Diamond must succeed
    res_ok = client.post(
        "/billing/quote",
        json={"plan_id": "diamond", "duration_key": "1_year", "coupon_code": "DIAMONDONLY"},
    )
    assert res_ok.status_code == 200
    assert res_ok.json()["discount"] == 1000.0


def test_quote_validation_negative_and_oversize(harness):
    client = world(harness)

    # Negative quantities
    assert client.post("/billing/quote", json={"plan_id": "silver", "extra_users": -1}).status_code == 422
    assert client.post("/billing/quote", json={"plan_id": "silver", "extra_companies": -5}).status_code == 422

    # Quantities exceeding max 500
    assert client.post("/billing/quote", json={"plan_id": "silver", "extra_users": 501}).status_code == 422

    # Nonexistent plan
    assert client.post("/billing/quote", json={"plan_id": "nonexistent"}).status_code == 400


def test_sales_inquiry_is_saved_without_signing_in(harness):
    """The public inquiry form works signed out (it is rate limited per caller)."""
    from app.models.billing import BillingLead
    client = harness.app(billing.router)
    res = client.post("/billing/inquiry", json={"plan_id": "gold", "customer_name": "Asha", "customer_phone": "9876543210"})
    assert res.status_code == 200, res.text
    assert harness.scalar(select(BillingLead.customer_name).where(BillingLead.id == res.json()["lead_id"])) == "Asha"


def test_sales_number_comes_only_from_the_setting(harness, monkeypatch):
    """No sales number is shown until BILLING_SALES_PHONE is set; then the catalog and the inquiry use it."""
    from app.core.config import settings
    client = harness.app(billing.router)
    inquiry = {"plan_id": "gold", "customer_name": "Asha", "customer_phone": "9876543210"}

    monkeypatch.setattr(settings, "BILLING_SALES_PHONE", None)
    plans = client.get("/billing/plans").json()
    assert plans["sales_phone"] is None and plans["sales_whatsapp"] is None
    assert client.post("/billing/inquiry", json=inquiry).json()["whatsapp_url"] is None

    monkeypatch.setattr(settings, "BILLING_SALES_PHONE", "+91 98765-43210")
    plans = client.get("/billing/plans").json()
    assert (plans["sales_phone"], plans["sales_whatsapp"]) == ("+91 98765 43210", "919876543210")
    assert client.post("/billing/inquiry", json=inquiry).json()["whatsapp_url"].startswith("https://wa.me/919876543210?text=")
