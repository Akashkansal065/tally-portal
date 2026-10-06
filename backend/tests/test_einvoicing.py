"""Phase 4: live e-invoice (IRN) and e-way bill through the GSP, with a fake provider in place of MasterGST."""
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

import app.models.portal_core as P
import app.models.tally_core as T
from app.core.config import settings
from app.routers import auth, edocs, gst, integrations
from app.services import einvoicing, gsp
from app.services import gst_documents as docs
from tests.conftest import bearer, login, run

NOW = datetime(2026, 10, 6, 11, 0)


class FakeGsp:
    def __init__(self):
        self.calls = []

    async def generate_irn(self, company, payload):
        self.calls.append(("generate_irn", payload))
        return {"Irn": "a" * 64, "AckNo": 112610000000001, "AckDt": "2026-10-06 11:00:00", "SignedQRCode": "eyJhbGciOi.signed.qr"}

    async def cancel_irn(self, company, irn, reason, remark):
        self.calls.append(("cancel_irn", irn, reason))
        return {"Irn": irn, "CancelDate": "2026-10-06 12:00:00"}

    async def ewaybill_by_irn(self, company, body):
        self.calls.append(("ewaybill_by_irn", body))
        return {"EwbNo": 181010000001, "EwbDt": "2026-10-06 11:05:00", "EwbValidTill": "2026-10-07 23:59:00"}

    async def generate_ewaybill(self, company, payload):
        self.calls.append(("generate_ewaybill", payload))
        return {"ewayBillNo": 181010000002, "ewayBillDate": "06/10/2026 11:05:00 AM", "validUpto": "07/10/2026 11:59:00 PM"}

    async def update_vehicle(self, company, body):
        self.calls.append(("update_vehicle", body))
        return {"vehUpdDate": "06/10/2026 01:00:00 PM", "validUpto": "08/10/2026 11:59:00 PM"}

    async def cancel_ewaybill(self, company, ewb_no, reason, remark):
        self.calls.append(("cancel_ewaybill", ewb_no, reason))
        return {"ewayBillNo": ewb_no, "cancelDate": "06/10/2026 01:30:00 PM"}


@pytest.fixture
def world(harness, monkeypatch):
    fake = FakeGsp()
    monkeypatch.setattr(einvoicing, "provider", lambda: fake)
    clock = {"now": NOW}
    monkeypatch.setattr(einvoicing, "get_ist_now", lambda: clock["now"])
    monkeypatch.setattr(edocs, "get_ist_now", lambda: clock["now"])
    for key, value in {"GSP_EMAIL": "shop@example.com", "GSP_CLIENT_ID": "cid", "GSP_CLIENT_SECRET": "secret"}.items():
        monkeypatch.setattr(settings, key, value)

    h = harness
    alpha = h.add(P.Company(name="Demo Traders", books_begin_date=date(2026, 4, 1), gstin="09AAAAA1111A1Z5",
                            address_line1="12 Main Road", address_line2="Meerut", state="Uttar Pradesh", pincode="250004",
                            mobile="9800000000", email="accounts@demo.example", einvoice_env="mock"))
    admin = h.user(alpha, h.role("Admin"), "owner")
    cid = alpha.company_id
    debtors = h.add(T.MstGroup(company_id=cid, name="Sundry Debtors", nature="Asset"))
    ledgers = {n: h.add(T.MstLedger(company_id=cid, name=n, group_id=debtors.group_id)) for n in ("Sales", "Output CGST", "Output SGST", "Output IGST")}
    up = h.add(T.MstLedger(company_id=cid, name="Gupta Electricals", group_id=debtors.group_id, gstin="09AAAPG1234F1Z5",
                           address="5 Station Road, Meerut", state="Uttar Pradesh", pincode="250001", mobile="9837011111"))
    delhi = h.add(T.MstLedger(company_id=cid, name="Delhi Mart", group_id=debtors.group_id, gstin="07AAACD1234E1Z2",
                              address="9 Ring Road, New Delhi", state="Delhi", pincode="110001"))
    retail = h.add(T.MstLedger(company_id=cid, name="Walk-in Shop", group_id=debtors.group_id, address="Market, Meerut",
                               state="Uttar Pradesh", pincode="250002"))
    unit = h.add(T.MstUom(company_id=cid, name="Pieces", symbol="PCS"))
    kettle = h.add(T.MstStockItem(company_id=cid, name="Electric Kettle 1.5L", unit_id=unit.unit_id, hsn_code="8516", gst_rate_percent=Decimal("18")))
    no_hsn = h.add(T.MstStockItem(company_id=cid, name="Loose Item", unit_id=unit.unit_id, gst_rate_percent=Decimal("18")))
    vt = h.add(T.MstVoucherType(company_id=cid, name="Sales", parent_type="Sales"))
    n = [0]

    def sale(party, item=kettle, inter=False):
        n[0] += 1
        v = h.add(T.TrnVoucher(company_id=cid, voucher_type_id=vt.voucher_type_id, voucher_number=f"S-{100 + n[0]}",
                               voucher_date=date(2026, 10, 6), total_amount=Decimal("11800"), is_cancelled=False,
                               is_optional=False, created_by=admin.user_id, party_ledger_id=party.ledger_id))
        taxes = [(ledgers["Output IGST"], 1800)] if inter else [(ledgers["Output CGST"], 900), (ledgers["Output SGST"], 900)]
        h.add(T.TrnAccounting(voucher_id=v.voucher_id, ledger_id=party.ledger_id, debit_amount=Decimal("11800"), credit_amount=0),
              T.TrnAccounting(voucher_id=v.voucher_id, ledger_id=ledgers["Sales"].ledger_id, debit_amount=0, credit_amount=Decimal("10000")),
              *[T.TrnAccounting(voucher_id=v.voucher_id, ledger_id=l.ledger_id, debit_amount=0, credit_amount=Decimal(str(a))) for l, a in taxes],
              T.TrnInventory(voucher_id=v.voucher_id, stock_item_id=item.stock_item_id, quantity=Decimal(10), rate=Decimal(1000),
                             amount=Decimal(10000), is_inward=False))
        return v

    client = h.app(auth.router, integrations.router, gst.router, edocs.router)
    headers = bearer(login(client, "owner@example.com"))
    for key in ("einvoice", "eway_bill"):
        assert client.put(f"/integrations/{key}", json={"enabled": True}, headers=headers).status_code == 200
    return dict(h=h, client=client, headers=headers, company=alpha, fake=fake, clock=clock, sale=sale,
                up=up, delhi=delhi, retail=retail, no_hsn=no_hsn)


def go_live(world):
    r = world["client"].put("/gst/einvoice/settings", json={
        "mode": "live", "einvoice_username": "API_demo", "einvoice_password": "pw1", "eway_username": "EWB_demo",
        "eway_password": "pw2"}, headers=world["headers"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "live" and body["has_einvoice_password"] and body["has_eway_password"]
    assert "pw1" not in r.text and "pw2" not in r.text


async def _doc(world, voucher_id):
    async for db in world["h"]._get_db():
        return await docs.load_document(db, world["company"].company_id, voucher_id)


def test_einvoice_payload_intra_and_inter_state(world):
    v = world["sale"](world["up"])
    doc = run(_doc(world, v.voucher_id))
    assert docs.einvoice_problems(doc) == []
    body = docs.einvoice_payload(doc)
    assert body["DocDtls"] == {"Typ": "INV", "No": v.voucher_number, "Dt": "06/10/2026"}
    assert body["SellerDtls"]["Gstin"] == "09AAAAA1111A1Z5" and body["SellerDtls"]["Pin"] == 250004 and body["SellerDtls"]["Stcd"] == "09"
    assert body["BuyerDtls"]["Gstin"] == "09AAAPG1234F1Z5" and body["BuyerDtls"]["Pos"] == "09"
    item = body["ItemList"][0]
    assert (item["HsnCd"], item["Unit"], item["AssAmt"], item["CgstAmt"], item["SgstAmt"], item["IgstAmt"], item["TotItemVal"]) == \
        ("8516", "PCS", 10000.0, 900.0, 900.0, 0.0, 11800.0)
    assert body["ValDtls"]["TotInvVal"] == 11800.0 and body["ValDtls"]["RndOffAmt"] == 0.0

    inter = run(_doc(world, world["sale"](world["delhi"], inter=True).voucher_id))
    assert inter.inter_state and docs.einvoice_payload(inter)["ItemList"][0]["IgstAmt"] == 1800.0
    ewb = docs.ewaybill_payload(inter, docs.Transport(vehicle_no="up15ab1234"))
    assert ewb["toStateCode"] == 7 and ewb["igstValue"] == 1800.0 and ewb["vehicleNo"] == "UP15AB1234" and ewb["transDistance"] == "0"


def test_problems_are_plain_and_specific(world, monkeypatch):
    doc = run(_doc(world, world["sale"](world["retail"], item=world["no_hsn"]).voucher_id))
    problems = docs.einvoice_problems(doc)
    assert any("Loose Item has no valid HSN" in p for p in problems)
    assert any("Walk-in Shop has no GSTIN" in p for p in problems)
    # An unregistered buyer is fine for an e-way bill ("URP"), but the HSN still matters
    ewb = docs.ewaybill_problems(doc, docs.Transport(vehicle_no="UP15AB1234"))
    assert not any("no GSTIN" in p for p in ewb) and any("HSN" in p for p in ewb)
    assert docs.Transport(vehicle_no="ABC").check()


def test_live_needs_gsp_keys_and_only_admins_change_settings(world, monkeypatch):
    monkeypatch.setattr(settings, "GSP_CLIENT_SECRET", None)
    r = world["client"].put("/gst/einvoice/settings", json={"mode": "live"}, headers=world["headers"])
    assert r.status_code == 422 and "GSP_CLIENT_SECRET" in r.json()["detail"]
    statuses = {s["key"]: s["status"] for s in world["client"].get("/integrations", headers=world["headers"]).json()}
    assert statuses["einvoice"] == "demo" and statuses["eway_bill"] == "demo"


def test_live_irn_then_ewaybill_then_cancel_rules(world):
    client, headers, fake = world["client"], world["headers"], world["fake"]
    go_live(world)
    statuses = {s["key"]: s["status"] for s in client.get("/integrations", headers=headers).json()}
    assert statuses["einvoice"] == "connected" and statuses["eway_bill"] == "connected"

    v = world["sale"](world["up"])
    r = client.post(f"/gst/einvoice/{v.voucher_id}/generate", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["demo"] is False and r.json()["irn"] == "a" * 64 and r.json()["ack_no"] == "112610000000001"
    voucher = world["h"].query(select(T.TrnVoucher).where(T.TrnVoucher.voucher_id == v.voucher_id))[0][0]
    assert voucher.irn == "a" * 64 and voucher.irn_source == "MyTally" and voucher.irn_qr_code.startswith("eyJ")
    # Asking again doesn't register a second IRN
    client.post(f"/gst/einvoice/{v.voucher_id}/generate", headers=headers)
    assert [c[0] for c in fake.calls].count("generate_irn") == 1

    r = client.post(f"/gst/ewaybill/{v.voucher_id}/generate", json={"vehicle_no": "UP15AB1234", "distance_km": 12}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["eway_bill_no"] == "181010000001" and fake.calls[-1][0] == "ewaybill_by_irn"
    assert fake.calls[-1][1]["VehNo"] == "UP15AB1234" and fake.calls[-1][1]["Distance"] == 12

    status = client.get(f"/gst/edocs/{v.voucher_id}", headers=headers).json()
    assert status["mode"] == "live" and status["can_cancel_ewb"] and not status["can_cancel_irn"]  # e-way bill first
    assert client.post(f"/gst/einvoice/{v.voucher_id}/cancel", json={"reason": "2"}, headers=headers).status_code == 422

    r = client.post(f"/gst/ewaybill/{v.voucher_id}/vehicle", json={"vehicle_no": "UP15CD9876", "reason": "1", "from_place": "Meerut"}, headers=headers)
    assert r.status_code == 200 and fake.calls[-1][1]["vehicleNo"] == "UP15CD9876"
    assert client.post(f"/gst/ewaybill/{v.voucher_id}/cancel", json={"reason": "2"}, headers=headers).json()["ewb_status"] == "cancelled"
    assert client.post(f"/gst/einvoice/{v.voucher_id}/cancel", json={"reason": "2"}, headers=headers).json()["irn_status"] == "cancelled"

    # After 24 hours nothing can be cancelled
    other = world["sale"](world["up"])
    client.post(f"/gst/einvoice/{other.voucher_id}/generate", headers=headers)
    world["clock"]["now"] = NOW + timedelta(hours=25)
    r = client.post(f"/gst/einvoice/{other.voucher_id}/cancel", json={"reason": "2"}, headers=headers)
    assert r.status_code == 422 and "credit note" in str(r.json()["detail"])


def test_direct_ewaybill_for_an_unregistered_buyer_and_portal_errors(world, monkeypatch):
    client, headers, fake = world["client"], world["headers"], world["fake"]
    go_live(world)
    v = world["sale"](world["retail"])
    r = client.post(f"/gst/ewaybill/{v.voucher_id}/generate", json={"vehicle_no": "UP15AB1234"}, headers=headers)
    assert r.status_code == 200, r.text
    assert fake.calls[-1][0] == "generate_ewaybill" and fake.calls[-1][1]["toGstin"] == "URP"
    rows = world["h"].query(select(T.TrnEwayBill.bill_number, T.TrnEwayBill.vehicle_number).where(T.TrnEwayBill.voucher_id == v.voucher_id))
    assert [tuple(r) for r in rows] == [("181010000002", "UP15AB1234")]

    async def refused(company, payload):
        raise gsp.GspError("2150: Duplicate IRN")
    monkeypatch.setattr(fake, "generate_irn", refused)
    up_sale = world["sale"](world["up"])
    r = client.post(f"/gst/einvoice/{up_sale.voucher_id}/generate", headers=headers)
    assert r.status_code == 502 and "Duplicate IRN" in r.json()["detail"]
    # Problems are listed before anything is sent
    r = client.post(f"/gst/einvoice/{v.voucher_id}/generate", headers=headers)
    assert r.status_code == 422 and any("no GSTIN" in p for p in r.json()["detail"]["problems"])


def test_demo_mode_ewaybill_is_labelled(world):
    v = world["sale"](world["up"])
    r = world["client"].post(f"/gst/ewaybill/{v.voucher_id}/generate", json={"vehicle_no": "UP15AB1234"}, headers=world["headers"])
    assert r.status_code == 200 and r.json()["demo"] is True and len(r.json()["eway_bill_no"]) == 12
    assert world["fake"].calls == []


def test_mastergst_error_messages_and_token_retry(monkeypatch):
    assert gsp._error_text({"status_cd": "0", "status_desc": '[{"ErrorCode":"2150","ErrorMessage":"Duplicate IRN"}]'}) == "Duplicate IRN"
    assert gsp._error_text({"error": {"message": "Invalid Token"}}) == "Invalid Token"

    adapter = gsp.MasterGst()
    company = P.Company(name="X", gstin="09AAAAA1111A1Z5", einvoice_username="u", einvoice_password="p")
    seen = []

    async def fake_call(method, path, headers, params=None, body=None):
        seen.append(path)
        if path.endswith("/authenticate"):
            return {"AuthToken": f"tok{len(seen)}"}
        if len([p for p in seen if "GENERATE" in p]) == 1:
            raise gsp.GspError("Invalid Token")
        return {"Irn": "x" * 64, "auth": headers["auth-token"]}
    monkeypatch.setattr(adapter, "_call", fake_call)
    result = run(adapter.generate_irn(company, {}))
    assert result["Irn"] == "x" * 64 and seen.count("/einvoice/authenticate") == 2  # signed in again once
