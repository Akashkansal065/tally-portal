"""Phase 3: invoice branding (company profile + company_branding), buyer details on vouchers, and emailing a PDF."""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

import app.models.portal_core as P
import app.models.tally_core as T
from app.core.config import settings
from app.routers import auth, branding, integrations, reminders as reminders_router, vouchers
from app.services import messaging
from app.services.messaging import SendResult
from tests.conftest import bearer, login

PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


@pytest.fixture
def world(harness, monkeypatch):
    monkeypatch.setattr(settings, "SMTP_USER", "shop@gmail.com")
    monkeypatch.setattr(settings, "SMTP_PASS", "app-password")
    monkeypatch.setattr(settings, "REMINDERS_DRY_RUN", False)
    sent = []

    async def fake_email(to, subject, text, html=None, from_name=None, attachments=()):
        sent.append(dict(to=to, subject=subject, attachments=list(attachments), from_name=from_name))
        return SendResult(True, provider_message_id="mail-1")
    monkeypatch.setattr(messaging, "send_email", fake_email)

    h = harness
    alpha = h.add(P.Company(name="Demo Traders", books_begin_date=date(2026, 4, 1), address_line1="12 Main Road",
                            state="Uttar Pradesh", pincode="250001", mobile="9837000000", email="shop@example.com",
                            features={"upi_id": "demo@upi"}))
    beta = h.company("Beta")
    admin_role, staff_role = h.role("Admin"), h.role("Sales")
    owner = h.user(alpha, admin_role, "owner")
    h.user(alpha, staff_role, "staff")
    for code in ("payments", "vouchers"):
        module = h.add(P.Module(code=code, name=code.title()))
        h.add(P.Permission(role_id=staff_role.role_id, module_id=module.module_id, can_read=True, can_create=True))
    debtors = h.add(T.MstGroup(company_id=alpha.company_id, name="Sundry Debtors", nature="Asset"))
    party = h.add(T.MstLedger(company_id=alpha.company_id, name="Gupta Electricals", group_id=debtors.group_id,
                              address="5 Station Road, Meerut", state="Uttar Pradesh", pincode="250002",
                              gstin="09AAAPG1234F1Z5", mobile="9837011111", email="gupta@example.com"))
    sales = h.add(T.MstLedger(company_id=alpha.company_id, name="Sales", group_id=debtors.group_id))
    other = h.add(T.MstLedger(company_id=beta.company_id, name="Not ours", group_id=debtors.group_id))
    vt = h.add(T.MstVoucherType(company_id=alpha.company_id, name="Sales", parent_type="Sales"))
    v = h.add(T.TrnVoucher(company_id=alpha.company_id, voucher_type_id=vt.voucher_type_id, voucher_number="S-101",
                           voucher_date=date(2026, 10, 1), total_amount=Decimal("11800"), is_cancelled=False, is_optional=False,
                           created_by=owner.user_id))
    h.add(T.TrnAccounting(voucher_id=v.voucher_id, ledger_id=party.ledger_id, debit_amount=Decimal("11800"), credit_amount=0),
          T.TrnAccounting(voucher_id=v.voucher_id, ledger_id=sales.ledger_id, debit_amount=0, credit_amount=Decimal("10000")))
    client = h.app(auth.router, integrations.router, branding.router, reminders_router.router, vouchers.router)
    return dict(h=h, client=client, admin=bearer(login(client, "owner@example.com")), staff=bearer(login(client, "staff@example.com")),
                party=party, other=other, voucher=v, sent=sent)


def test_branding_defaults_come_from_the_company_profile(world):
    body = world["client"].get("/branding", headers=world["staff"]).json()
    assert body["company"]["name"] == "Demo Traders"
    assert body["company"]["address_lines"] == ["12 Main Road"]
    assert body["company"]["upi_id"] == "demo@upi" and body["company"]["gstin"] is None
    assert body["logo"] is None and body["show_upi_qr"] is True
    assert body["declaration"].startswith("We declare")
    assert body["bank"] == {"account_name": None, "bank_name": None, "account_no": None, "ifsc": None, "branch": None}


def test_only_admins_change_branding_and_images_are_checked(world):
    client, admin = world["client"], world["admin"]
    assert client.put("/branding", json={"bank_name": "X"}, headers=world["staff"]).status_code == 403
    assert client.put("/branding", json={"logo": "data:image/gif;base64,R0lGOD"}, headers=admin).status_code == 422
    assert client.put("/branding", json={"logo": "data:image/png;base64," + "A" * 500_000}, headers=admin).status_code == 422

    body = client.put("/branding", json={"logo": PNG, "bank_name": " Punjab National Bank ", "bank_ifsc": "punb0400700",
                                         "bank_account_no": "1234567890", "show_upi_qr": False}, headers=admin).json()
    assert body["logo"] == PNG and body["bank"]["bank_name"] == "Punjab National Bank" and body["bank"]["ifsc"] == "PUNB0400700"
    assert body["show_upi_qr"] is False
    # Leaving a field out keeps it; "" removes an image
    body = client.put("/branding", json={"logo": ""}, headers=admin).json()
    assert body["logo"] is None and body["bank"]["account_no"] == "1234567890"
    audit = world["h"].query(select(P.AuditLog.entity_type).where(P.AuditLog.entity_type == "Branding"))
    assert len(audit) == 2


def test_voucher_detail_has_the_buyer_details(world):
    body = world["client"].get(f"/vouchers/{world['voucher'].voucher_id}", headers=world["admin"]).json()
    assert body["party_details"] == {"name": "Gupta Electricals", "address": "5 Station Road, Meerut", "state": "Uttar Pradesh",
                                     "pincode": "250002", "gstin": "09AAAPG1234F1Z5", "mobile": "9837011111",
                                     "email": "gupta@example.com"}


def email(world, ledger_id=None, content=PDF, to="gupta@example.com"):
    return world["client"].post(
        "/reminders/email-document",
        data={"ledger_id": ledger_id or world["party"].ledger_id, "to": to, "subject": "Invoice S-101 from Demo Traders",
              "message": "Please find the invoice attached.", "reference": "Invoice S-101"},
        files={"file": ("Invoice_S-101.pdf", content, "application/pdf")},
        headers=world["admin"],
    )


def test_emailing_a_pdf_needs_the_switch_and_attaches_the_file(world):
    r = email(world)
    assert r.status_code == 200 and r.json()["status"] == "skipped" and "switched off" in r.json()["detail"]
    assert world["client"].put("/integrations/email", json={"enabled": True}, headers=world["admin"]).status_code == 200

    assert email(world, content=b"not a pdf").status_code == 422
    assert email(world, ledger_id=world["other"].ledger_id).status_code == 404
    assert email(world, to="nobody").json()["status"] == "skipped"

    r = email(world)
    assert r.json()["status"] == "sent" and r.json()["detail"] == "Invoice S-101"
    sent = world["sent"][-1]
    assert sent["to"] == "gupta@example.com" and sent["from_name"] == "Demo Traders"
    assert sent["attachments"] == [("Invoice_S-101.pdf", PDF, "application/pdf")]
