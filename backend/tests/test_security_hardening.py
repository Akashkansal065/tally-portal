"""Fixes from the API security assessment (docs/Security Assessment - API Attack Surface.md): another company's
POS payments, uploads that could exhaust memory, and the server-wide sync run."""
import io
import json
import zipfile
from datetime import date

import pytest

import app.models.portal_core as P
import app.models.tally_core as T
from app.core.config import settings
from app.routers import advanced, auth, bank_recon, gst, sync
from tests.conftest import bearer, login


@pytest.fixture
def world(harness):
    """Companies Alpha and Beta, each with a voucher that has POS payment splits, and a clerk in Alpha who may
    read vouchers and reports."""
    alpha, beta = harness.company("Alpha"), harness.company("Beta")
    role = harness.role("Sales")
    for code in ("vouchers", "reports"):
        module = harness.add(P.Module(code=code, name=code.title()))
        harness.add(P.Permission(role_id=role.role_id, module_id=module.module_id,
                                 can_read=True, can_create=True, can_update=True))
    clerk = harness.user(alpha, role, "clerk")
    pos = {}
    for company in (alpha, beta):
        voucher = harness.add(T.TrnVoucher(company_id=company.company_id, voucher_type_id=1, voucher_number="1",
                                           voucher_date=date(2026, 10, 1), created_by=clerk.user_id))
        harness.add(T.PosPayment(voucher_id=voucher.voucher_id, cash_amount=100, card_amount=0, upi_amount=0))
        pos[company.name] = voucher.voucher_id
    bank = harness.add(T.MstLedger(company_id=alpha.company_id, name="HDFC Bank", group_id=1))
    client = harness.app(auth.router, advanced.router, bank_recon.router, gst.router, sync.router)
    return dict(client=client, headers=bearer(login(client, clerk.email)), pos=pos, bank=bank, alpha=alpha)


# ── M1: POS payment splits belong to the voucher's company ─────────────────────

def test_pos_payments_of_another_company_are_not_found(world):
    c, headers = world["client"], world["headers"]

    own = c.get(f"/pos/payments/{world['pos']['Alpha']}", headers=headers)
    other = c.get(f"/pos/payments/{world['pos']['Beta']}", headers=headers)

    assert own.status_code == 200 and float(own.json()["cash_amount"]) == 100
    assert other.status_code == 404     # the same answer as a voucher that does not exist


# ── M3: uploads are bounded, and parser errors stay in the log ────────────────

def upload_statement(world, name, content):
    return world["client"].post("/bank-recon/upload", headers=world["headers"],
                                data={"bank_ledger_id": str(world["bank"].ledger_id)},
                                files={"file": (name, content, "application/octet-stream")})


def test_bank_statement_larger_than_the_limit_is_refused(world):
    response = upload_statement(world, "statement.csv", b"a" * (bank_recon.MAX_STATEMENT_BYTES + 1))

    assert response.status_code == 413


def test_excel_that_unpacks_to_gigabytes_is_refused_before_it_is_opened(world):
    """A zip bomb: small on the wire, enormous once unpacked."""
    packed = io.BytesIO()
    with zipfile.ZipFile(packed, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("xl/worksheets/sheet1.xml", b"\0" * (bank_recon.MAX_STATEMENT_UNPACKED_BYTES + 1))
    assert len(packed.getvalue()) < bank_recon.MAX_STATEMENT_BYTES

    response = upload_statement(world, "statement.xlsx", packed.getvalue())

    assert response.status_code == 413


def test_unreadable_excel_gets_a_plain_answer(world):
    response = upload_statement(world, "statement.xlsx", b"PK\x03\x04 this is not really a workbook")

    assert response.status_code == 400
    assert response.json()["detail"].startswith("Unable to read this Excel workbook.")


def upload_gstr2b(world, content):
    return world["client"].post("/gst/gstr2b/upload", headers=world["headers"],
                                files={"file": ("gstr2b.json", content, "application/json")})


def test_gstr2b_file_larger_than_the_limit_is_refused(world):
    assert upload_gstr2b(world, b" " * (20 * 1024 * 1024 + 1)).status_code == 413


def test_gstr2b_that_is_not_a_gst_download_gets_a_plain_answer(world):
    plain = "That file is not a valid GSTR-2B JSON download from the GST portal."
    broken = upload_gstr2b(world, b"{not json")
    a_list = upload_gstr2b(world, json.dumps([1, 2, 3]).encode())     # valid JSON, but crashed the parser before

    assert (broken.status_code, broken.json()["detail"]) == (400, plain)
    assert (a_list.status_code, a_list.json()["detail"]) == (400, plain)


# ── M4: one sync run against the server's own Tally is for the people who run the server ──

def test_sync_run_once_is_refused_to_an_account_admin(harness, monkeypatch):
    monkeypatch.setattr(settings, "TALLY_URL", "http://tally.test:9000")
    company = harness.company("Alpha")
    admin = harness.user(company, harness.role("Admin"), "owner")
    client = harness.app(auth.router, sync.router)

    response = client.post("/sync/run-once", headers=bearer(login(client, admin.email)))

    assert response.status_code == 403


def test_sync_run_sends_only_the_direct_companys_changes_to_the_servers_tally(harness, monkeypatch):
    """The background sync run goes through every company the person can open. Only the company the server's Tally
    belongs to may be sent there; another company's changes wait in the queue for its own sync agent."""
    import app.core.database as database
    from tests.conftest import run
    monkeypatch.setattr(settings, "TALLY_URL", "http://tally.test:9000")
    monkeypatch.setattr(settings, "TALLY_URL_COMPANY_ID", None)
    monkeypatch.setattr(database, "AsyncSessionLocal", harness.Session)
    monkeypatch.setattr(sync, "_post_to_tally_sync", lambda url, xml, timeout=5: "")   # nothing leaves the test
    pushed = []

    async def push_currency(record_id, sync_id, action, db):
        pushed.append(record_id)
    monkeypatch.setattr(sync, "try_push_currency_realtime", push_currency)

    first, later = harness.add(P.Account(name="First"), P.Account(name="Signed up later"))
    own, other = harness.company("Own"), harness.company("Other")
    for account, company in ((first, own), (later, other)):
        harness.execute(P.Company.__table__.update().where(P.Company.company_id == company.company_id)
                        .values(account_id=account.account_id))
    operator = harness.user(own, harness.role("Admin"), "operator")
    harness.add(P.UserCompanyAccess(user_id=operator.user_id, company_id=other.company_id))
    for company, record_id in ((own, 1), (other, 2)):
        harness.add(P.SyncQueue(company_id=company.company_id, record_type="Currency", record_id=record_id,
                                action="Create", is_processed=False))

    run(sync.run_once_sync_background(operator.user_id))

    assert pushed == [1]
