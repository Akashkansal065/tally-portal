"""Phase 1 of the Livekeeping parity plan: features that need another provider's keys or a paid subscription sit
behind per-company switches (off by default), and nothing made up is presented as real."""
from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

import app.models.portal_core as P
import app.models.tally_core as T
from app.routers import advanced, auth, gst, integrations, payment_gateway, payments, vouchers
from app.services.integrations import INTEGRATIONS, is_enabled
from tests.conftest import bearer, login, run


@pytest.fixture
def world(harness):
    alpha = harness.company("Alpha")
    beta = harness.company("Beta")
    admin_role = harness.role("Admin")
    staff_role = harness.role("Sales")
    owner = harness.user(alpha, admin_role, "owner")
    staff = harness.user(alpha, staff_role, "staff")
    for code in ("reports", "vouchers", "payments", "settings"):
        module = harness.add(P.Module(code=code, name=code.title()))
        harness.add(P.Permission(role_id=staff_role.role_id, module_id=module.module_id,
                                 can_read=True, can_create=True, can_update=True))
    sales = {cid: harness.add(T.MstVoucherType(company_id=cid, name="Sales", parent_type="Sales"))
             for cid in (alpha.company_id, beta.company_id)}

    def sale(company, amount):
        return harness.add(T.TrnVoucher(company_id=company.company_id, voucher_type_id=sales[company.company_id].voucher_type_id,
                                        voucher_number=f"S-{amount}", voucher_date=date(2026, 10, 1),
                                        total_amount=Decimal(str(amount)), is_cancelled=False, is_optional=False,
                                        created_by=owner.user_id))

    client = harness.app(auth.router, integrations.router, gst.router, payments.router, payment_gateway.router, advanced.router,
                         vouchers.router)
    return dict(h=harness, alpha=alpha, beta=beta, owner=owner, staff=staff, client=client, sale=sale,
                admin=bearer(login(client, "owner@example.com")), staff_h=bearer(login(client, "staff@example.com")))


def switch(world, key, on=True):
    r = world["client"].put(f"/integrations/{key}", json={"enabled": on}, headers=world["admin"])
    assert r.status_code == 200, r.text
    return r.json()


def test_switches_are_off_by_default_and_listed_for_everyone(world):
    r = world["client"].get("/integrations", headers=world["staff_h"])
    assert r.status_code == 200
    rows = {row["key"]: row for row in r.json()}
    assert set(rows) == set(INTEGRATIONS)
    assert all(not row["enabled"] and row["status"] == "off" for row in rows.values())


def test_only_admins_switch_and_it_is_per_company_and_audited(world):
    client, h = world["client"], world["h"]
    assert client.put("/integrations/einvoice", json={"enabled": True}, headers=world["staff_h"]).status_code == 403
    assert client.put("/integrations/nope", json={"enabled": True}, headers=world["admin"]).status_code == 404

    assert switch(world, "einvoice")["status"] == "demo"            # safe labelled demo
    assert switch(world, "payment_gateway")["status"] == "unavailable"  # no safe demo, not built
    assert run(_enabled(h, world["alpha"].company_id, "einvoice"))
    assert not run(_enabled(h, world["beta"].company_id, "einvoice"))
    actions = [row[0] for row in h.query(select(P.AuditLog.action).where(P.AuditLog.entity_type == "Integration"))]
    assert "INTEGRATION_ON" in actions

    assert switch(world, "einvoice", on=False)["status"] == "off"


async def _enabled(h, company_id, key):
    async for db in h._get_db():
        return await is_enabled(db, company_id, key)


def test_einvoice_is_refused_when_off_and_demo_only_when_on(world):
    client, admin = world["client"], world["admin"]
    small, big = world["sale"](world["alpha"], 10_000), world["sale"](world["alpha"], 75_000)

    r = client.post(f"/gst/einvoice/{small.voucher_id}/generate", headers=admin)
    assert r.status_code == 403 and "switched off" in r.json()["detail"]
    assert client.get("/gst/einvoices", headers=admin).status_code == 403
    assert client.get("/gst/einvoice/settings", headers=admin).status_code == 403

    switch(world, "einvoice")
    # Live needs the GST provider's account keys on the server
    r = client.put("/gst/einvoice/settings", json={"einvoice_env": "production"}, headers=admin)
    assert r.status_code == 422
    assert client.put("/gst/einvoice/settings", json={"einvoice_env": "mock"}, headers=admin).status_code == 200

    r = client.post(f"/gst/einvoice/{big.voucher_id}/generate", headers=admin)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["demo"] is True and len(body["irn"]) == 64
    assert body["eway_bill_no"] is None   # e-way bill switch is still off

    switch(world, "eway_bill")
    other = world["sale"](world["alpha"], 80_000)
    assert client.post(f"/gst/einvoice/{other.voucher_id}/generate", headers=admin).json()["eway_bill_no"]

    listed = {row["voucher_id"]: row for row in client.get("/gst/einvoices", headers=admin).json()}
    assert listed[big.voucher_id]["demo"] is True and listed[small.voucher_id]["irn"] is None


def test_einvoice_metadata_is_company_scoped_and_manual_records_are_not_demo(world):
    client, admin = world["client"], world["admin"]
    own, theirs = world["sale"](world["alpha"], 5_000), world["sale"](world["beta"], 5_000)
    world["h"].add(P.EinvoiceMetadata(voucher_id=theirs.voucher_id, irn="b" * 64, environment="mock"))

    assert client.get(f"/einvoice/metadata/{theirs.voucher_id}", headers=admin).status_code == 404

    r = client.post("/einvoice/metadata", json={"voucher_id": own.voucher_id, "irn": "a" * 64, "ack_no": "1"}, headers=admin)
    assert r.status_code == 200, r.text
    meta = client.get(f"/einvoice/metadata/{own.voucher_id}", headers=admin).json()
    assert meta["environment"] == "manual" and meta["demo"] is False


def test_gstr2b_portal_fetch_never_touches_saved_rows(world):
    client, admin, h = world["client"], world["admin"], world["h"]
    period = h.add(P.GstReturnPeriod(company_id=world["alpha"].company_id, return_type="GSTR3B", period_month=9, period_year=2026))
    h.add(P.Gstr2bEntry(company_id=world["alpha"].company_id, return_period_id=period.return_period_id,
                        supplier_gstin="09AAAAA0000A1Z5", supplier_name="Real supplier", invoice_number="R-1",
                        invoice_date=date(2026, 9, 3), taxable_value=Decimal("100"), cgst_amount=0, sgst_amount=0,
                        igst_amount=Decimal("18"), cess_amount=0, itc_availability="Available", match_status="Unmatched"))

    assert client.post("/gst/gstr2b/request-otp", json={"period_id": period.return_period_id}, headers=admin).status_code == 403
    switch(world, "gst_portal")
    r = client.post("/gst/gstr2b/verify-otp", json={"period_id": period.return_period_id, "otp": "123456", "txn_id": "T"}, headers=admin)
    assert r.status_code == 501 and "Upload" in r.json()["detail"]
    names = [row[0] for row in h.query(select(P.Gstr2bEntry.supplier_name))]
    assert names == ["Real supplier"]


def test_gst_return_submission_is_switched_and_demo_only(world):
    client, admin, h = world["client"], world["admin"], world["h"]
    period = h.add(P.GstReturnPeriod(company_id=world["alpha"].company_id, return_type="GSTR1", period_month=9,
                                     period_year=2026, locked_at=datetime(2026, 10, 2)))
    url = f"/gst/periods/{period.return_period_id}/submit"
    assert client.post(url, json={"environment": "mock"}, headers=admin).status_code == 403
    switch(world, "gst_filing")
    assert client.post(url, json={"environment": "sandbox"}, headers=admin).status_code == 501
    r = client.post(url, json={"environment": "mock"}, headers=admin)
    assert r.status_code == 200, r.text
    assert r.json()["demo"] is True


def test_payment_links_are_upi_only_and_gateway_links_are_switched(world):
    client, admin = world["client"], world["admin"]
    v = world["sale"](world["alpha"], 1_234)
    r = client.post("/payments/generate-link", json={"voucher_id": v.voucher_id, "upi_vpa": "shop@upi"}, headers=admin)
    assert r.status_code == 200, r.text
    link = r.json()
    assert link["payment_url"].startswith("upi://pay?") and "mytally.in" not in link["payment_url"]

    assert client.post("/gateways/payment-links", json={"bill_id": 1, "amount": 10}, headers=admin).status_code == 403
    switch(world, "payment_gateway")
    assert client.post("/gateways/payment-links", json={"bill_id": 1, "amount": 10}, headers=admin).status_code == 501


def test_voucher_detail_includes_the_party_gstin(world):
    """The voucher screen decides B2B (e-invoice) from this; it used to read a field the API never sent."""
    h, alpha = world["h"], world["alpha"]
    debtors = h.add(T.MstGroup(company_id=alpha.company_id, name="Sundry Debtors", nature="Asset"))
    party = h.add(T.MstLedger(company_id=alpha.company_id, name="Gupta Electricals", group_id=debtors.group_id, gstin="09AAAPG1234F1Z5"))
    sales = h.add(T.MstLedger(company_id=alpha.company_id, name="Sales", group_id=debtors.group_id))
    v = world["sale"](alpha, 11_800)
    h.add(T.TrnAccounting(voucher_id=v.voucher_id, ledger_id=party.ledger_id, debit_amount=Decimal("11800"), credit_amount=0),
          T.TrnAccounting(voucher_id=v.voucher_id, ledger_id=sales.ledger_id, debit_amount=0, credit_amount=Decimal("10000")))
    r = world["client"].get(f"/vouchers/{v.voucher_id}", headers=world["admin"])
    assert r.status_code == 200, r.text
    assert r.json()["party_gstin"] == "09AAAPG1234F1Z5"
