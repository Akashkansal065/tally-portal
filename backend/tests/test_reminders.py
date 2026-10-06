"""Phase 2: automatic payment reminders by email (Gmail) and WhatsApp (Meta Cloud API), behind their switches."""
import hashlib
import hmac
import json
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

import app.models.portal_core as P
import app.models.tally_core as T
from app.core.config import settings
from app.routers import auth, integrations, reminders as reminders_router
from app.services import messaging, receivables
from app.services import reminders as svc
from app.services.messaging import SendResult
from tests.conftest import bearer, login, run

TODAY = date(2026, 10, 15)
NOW = datetime(2026, 10, 15, 11, 0)


@pytest.fixture
def world(harness, monkeypatch):
    monkeypatch.setattr(receivables, "get_ist_date", lambda: TODAY)
    monkeypatch.setattr(reminders_router, "get_ist_now", lambda: NOW)
    for key, value in {"SMTP_USER": "shop@gmail.com", "SMTP_PASS": "app-password", "WHATSAPP_ACCESS_TOKEN": "token",
                       "WHATSAPP_PHONE_NUMBER_ID": "123", "WHATSAPP_TEMPLATE": "payment_reminder",
                       "WHATSAPP_APP_SECRET": "secret", "WHATSAPP_VERIFY_TOKEN": "verify-me", "REMINDERS_DRY_RUN": False}.items():
        monkeypatch.setattr(settings, key, value)
    sent = {"email": [], "whatsapp": []}

    async def fake_email(to, subject, text, html=None, from_name=None):
        sent["email"].append(dict(to=to, subject=subject, text=text, from_name=from_name))
        return SendResult(True, provider_message_id=f"mail-{len(sent['email'])}")

    async def fake_whatsapp(to, parameters):
        sent["whatsapp"].append(dict(to=to, parameters=parameters))
        return SendResult(True, provider_message_id=f"wamid.{len(sent['whatsapp'])}")
    monkeypatch.setattr(messaging, "send_email", fake_email)
    monkeypatch.setattr(messaging, "send_whatsapp_template", fake_whatsapp)

    h = harness
    alpha = h.add(P.Company(name="Sneh Demo", books_begin_date=date(2026, 4, 1), features={"upi_id": "shop@upi"}))
    beta = h.company("Beta")
    admin_role = h.role("Admin")
    admin = h.user(alpha, admin_role, "owner")
    partner = h.user(alpha, admin_role, "partner")
    cid = alpha.company_id
    primary = h.add(T.MstGroup(company_id=cid, name="Primary", nature="Asset"))
    debtors = h.add(T.MstGroup(company_id=cid, name="Sundry Debtors", nature="Asset", parent_group_id=primary.group_id))
    sales_l = h.add(T.MstLedger(company_id=cid, name="Sales", group_id=primary.group_id))
    types = {n: h.add(T.MstVoucherType(company_id=cid, name=n, parent_type=n)) for n in ("Sales", "Receipt")}
    counter = [0]

    def voucher(kind, days_ago, amount, entries):
        counter[0] += 1
        v = h.add(T.TrnVoucher(company_id=cid, voucher_type_id=types[kind].voucher_type_id, voucher_number=f"{kind[0]}-{counter[0]}",
                               voucher_date=TODAY - timedelta(days=days_ago), total_amount=Decimal(str(amount)),
                               is_cancelled=False, is_optional=False, created_by=admin.user_id))
        h.add(*[T.TrnAccounting(voucher_id=v.voucher_id, ledger_id=lid, debit_amount=Decimal(str(dr)), credit_amount=Decimal(str(cr)))
                for lid, dr, cr in entries])

    def customer(name, days_ago, amount, **extra):
        c = h.add(T.MstLedger(company_id=cid, name=name, group_id=debtors.group_id, **extra))
        voucher("Sales", days_ago, amount, [(c.ledger_id, amount, 0), (sales_l.ledger_id, 0, amount)])
        return c

    late = customer("Late Traders", 60, 50000, mobile="98370 11111")       # overdue (30 credit days)
    fresh = customer("Fresh Mart", 5, 20000, mobile="9837022222")          # not due yet
    paid = customer("Paid Up Store", 70, 10000, email="paid@example.com")
    voucher("Receipt", 2, 10000, [(paid.ledger_id, 0, 10000)])
    other = h.add(T.MstLedger(company_id=beta.company_id, name="Not ours", group_id=debtors.group_id))

    client = h.app(auth.router, integrations.router, reminders_router.router)
    headers = bearer(login(client, "owner@example.com"))
    return dict(h=h, client=client, headers=headers, alpha=alpha, admin=admin, partner=partner, late=late, fresh=fresh, paid=paid,
                other=other, sent=sent)


def switch(world, key, on=True):
    assert world["client"].put(f"/integrations/{key}", json={"enabled": on}, headers=world["headers"]).status_code == 200


def logs(world, **where):
    stmt = select(P.ReminderLog).order_by(P.ReminderLog.id)
    for k, v in where.items():
        stmt = stmt.where(getattr(P.ReminderLog, k) == v)
    return [row[0] for row in world["h"].query(stmt)]


def test_helpers():
    assert svc.inr(1234567.5) == "12,34,567.50" and svc.inr(50000) == "50,000" and svc.inr(999) == "999"
    assert messaging.whatsapp_number("98370 11111") == "919837011111"
    assert messaging.whatsapp_number("+91-98370-11111") == "919837011111"
    assert messaging.whatsapp_number("09837011111") == "919837011111"
    assert messaging.whatsapp_number("0121 2660000") is None
    monday = datetime(2026, 10, 12, 12, 0)
    assert svc.next_run("daily", "10:00", monday, first=True) == datetime(2026, 10, 13, 10, 0)
    assert svc.next_run("daily", "14:00", monday, first=True) == datetime(2026, 10, 12, 14, 0)
    assert svc.next_run("weekly", "10:00", monday, weekday=4) == datetime(2026, 10, 16, 10, 0)
    assert svc.next_run("monthly", "10:00", monday, month_day=5) == datetime(2026, 11, 5, 10, 0)
    assert svc.next_run("once", "10:00", monday) is None
    with pytest.raises(ValueError):
        svc.parse_time("22:00")


def test_channels_need_their_switch_and_keys(world, monkeypatch):
    client, headers = world["client"], world["headers"]
    body = client.get("/reminders/channels", headers=headers).json()
    assert [c["ready"] for c in body["channels"]] == [False, False]
    assert "switched off" in body["channels"][0]["reason"]

    switch(world, "email")
    monkeypatch.setattr(settings, "SMTP_PASS", None)
    email = client.get("/reminders/channels", headers=headers).json()["channels"][0]
    assert not email["ready"] and "keys" in email["reason"]
    monkeypatch.setattr(settings, "SMTP_PASS", "app-password")
    assert client.get("/reminders/channels", headers=headers).json()["channels"][0]["ready"]


def test_send_now_skips_with_reasons_then_sends_once_a_day(world):
    client, headers, late = world["client"], world["headers"], world["late"]
    r = client.post("/reminders/send-now", json={"ledger_id": late.ledger_id, "channels": ["email", "whatsapp"]}, headers=headers)
    assert r.status_code == 200
    assert [x["status"] for x in r.json()] == ["skipped", "skipped"]   # both switched off

    switch(world, "email")
    switch(world, "whatsapp_api")
    r = client.post("/reminders/send-now", json={"ledger_id": late.ledger_id, "channels": ["email", "whatsapp"]}, headers=headers)
    email, whatsapp = r.json()
    assert email["status"] == "skipped" and "No email" in email["detail"]
    assert whatsapp["status"] == "sent" and whatsapp["recipient"] == "919837011111"
    assert world["sent"]["whatsapp"][0]["parameters"] == ["Late Traders", "Sneh Demo", "50,000", "50,000", "shop@upi"]

    # Add an email in MyTally; WhatsApp was already sent today
    contact = client.put(f"/reminders/contact/{late.ledger_id}", json={"email": "late@example.com"}, headers=headers).json()
    assert contact["email"] == "late@example.com" and contact["email_source"] == "mytally"
    r = client.post("/reminders/send-now", json={"ledger_id": late.ledger_id, "channels": ["email", "whatsapp"]}, headers=headers)
    email, whatsapp = r.json()
    assert email["status"] == "sent" and whatsapp["status"] == "skipped" and "Already" in whatsapp["detail"]
    mail = world["sent"]["email"][0]
    assert mail["to"] == "late@example.com" and "₹50,000 outstanding" in mail["subject"] and "shop@upi" in mail["text"]
    assert mail["from_name"] == "Sneh Demo"

    # Someone who has paid gets nothing
    r = client.post("/reminders/send-now", json={"ledger_id": world["paid"].ledger_id, "channels": ["email"]}, headers=headers)
    assert r.json()[0]["status"] == "skipped" and "Nothing is owed" in r.json()[0]["detail"]


def test_dry_run_and_failures(world, monkeypatch):
    client, headers, late = world["client"], world["headers"], world["late"]
    switch(world, "whatsapp_api")
    monkeypatch.setattr(settings, "REMINDERS_DRY_RUN", True)
    r = client.post("/reminders/send-now", json={"ledger_id": late.ledger_id, "channels": ["whatsapp"]}, headers=headers)
    assert r.json()[0]["status"] == "dry_run" and world["sent"]["whatsapp"] == []

    monkeypatch.setattr(settings, "REMINDERS_DRY_RUN", False)

    async def refused(to, parameters):
        return SendResult(False, error="WhatsApp refused (400): template not approved")
    monkeypatch.setattr(messaging, "send_whatsapp_template", refused)
    fresh = world["fresh"]
    r = client.post("/reminders/send-now", json={"ledger_id": fresh.ledger_id, "channels": ["whatsapp"]}, headers=headers)
    assert r.json()[0]["status"] == "failed" and "not approved" in r.json()[0]["detail"]
    # The other admins hear about it; the person who pressed Send sees it on screen
    rows = world["h"].query(select(P.Notification.user_id, P.Notification.title))
    assert [(uid, "Fresh Mart failed" in title) for uid, title in rows] == [(world["partner"].user_id, True)]


def test_contacts_are_checked_and_company_scoped(world):
    client, headers = world["client"], world["headers"]
    assert client.put(f"/reminders/contact/{world['late'].ledger_id}", json={"email": "not-an-email"}, headers=headers).status_code == 422
    assert client.put(f"/reminders/contact/{world['late'].ledger_id}", json={"whatsapp": "12345"}, headers=headers).status_code == 422
    assert client.put(f"/reminders/contact/{world['other'].ledger_id}", json={"email": "a@b.co"}, headers=headers).status_code == 404
    assert client.get(f"/reminders/preview/{world['other'].ledger_id}", headers=headers).status_code == 404


def test_schedules_run_stop_when_paid_and_wait_until_overdue(world):
    client, headers, h = world["client"], world["headers"], world["h"]
    switch(world, "whatsapp_api")
    r = client.post("/reminders/schedules", json={"bucket": "overdue", "channels": ["whatsapp"], "frequency": "daily",
                                                  "send_time": "10:00"}, headers=headers)
    assert r.status_code == 200, r.text
    assert [s["customer"] for s in r.json()] == ["Late Traders"]   # Fresh Mart isn't overdue; Paid Up owes nothing
    first = r.json()[0]
    assert first["next_run_at"] == "2026-10-16T10:00:00"            # 11:00 now, so tomorrow at 10

    # Not-yet-due customer with "only while overdue": no message, schedule moves on
    client.post("/reminders/schedules", json={"ledger_ids": [world["fresh"].ledger_id], "channels": ["whatsapp"],
                                              "frequency": "daily", "send_time": "12:00"}, headers=headers)

    async def go(now):
        async for db in h._get_db():
            return await svc.run_due(db, now=now)

    assert run(go(datetime(2026, 10, 16, 7, 0))) == 0               # before 9 am: nothing
    assert run(go(datetime(2026, 10, 16, 13, 0))) == 2
    assert len(world["sent"]["whatsapp"]) == 1 and world["sent"]["whatsapp"][0]["parameters"][0] == "Late Traders"
    schedules = {s["customer"]: s for s in client.get("/reminders/schedules", headers=headers).json()}
    assert schedules["Late Traders"]["next_run_at"] == "2026-10-17T10:00:00"
    assert schedules["Fresh Mart"]["next_run_at"] == "2026-10-17T12:00:00"

    # Late Traders pays in full: the next run stops the schedule
    late, cid = world["late"], world["alpha"].company_id
    rc = h.add(T.TrnVoucher(company_id=cid, voucher_type_id=h.query(select(T.MstVoucherType.voucher_type_id).where(
        T.MstVoucherType.name == "Receipt"))[0][0], voucher_number="R-99", voucher_date=TODAY, total_amount=Decimal("50000"),
        is_cancelled=False, is_optional=False, created_by=world["admin"].user_id))
    h.add(T.TrnAccounting(voucher_id=rc.voucher_id, ledger_id=late.ledger_id, debit_amount=0, credit_amount=Decimal("50000")))
    run(go(datetime(2026, 10, 17, 10, 5)))
    stopped = client.get(f"/reminders/schedules?ledger_id={late.ledger_id}&include_stopped=true", headers=headers).json()[0]
    assert stopped["active"] is False and stopped["stop_reason"] == "paid"
    assert len(world["sent"]["whatsapp"]) == 1


def test_whatsapp_receipts_need_a_signature_and_never_go_backwards(world):
    client, headers, late = world["client"], world["headers"], world["late"]
    switch(world, "whatsapp_api")
    client.post("/reminders/send-now", json={"ledger_id": late.ledger_id, "channels": ["whatsapp"]}, headers=headers)

    assert client.get("/reminders/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "verify-me",
                                                             "hub.challenge": "42"}).text == "42"
    assert client.get("/reminders/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "wrong",
                                                             "hub.challenge": "42"}).status_code == 403

    def post(status):
        body = json.dumps({"entry": [{"changes": [{"value": {"statuses": [{"id": "wamid.1", "status": status}]}}]}]}).encode()
        sig = "sha256=" + hmac.new(b"secret", body, hashlib.sha256).hexdigest()
        return client.post("/reminders/whatsapp/webhook", content=body, headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"})

    assert client.post("/reminders/whatsapp/webhook", content=b"{}", headers={"X-Hub-Signature-256": "sha256=bad"}).status_code == 403
    assert post("read").json()["updated"] == 1
    assert post("delivered").json()["updated"] == 0                  # arrived late; stays "read"
    assert logs(world, channel="whatsapp")[0].status == "read"
