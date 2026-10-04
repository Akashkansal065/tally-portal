"""Cached responses never skip the permission check."""
from app.models.tally_core import MstGroup, MstLedger
from app.routers import auth, ledgers
from tests.conftest import bearer, login


def test_ledger_detail_cache_hit_still_checks_permission(harness):
    company = harness.company()
    admin = harness.user(company, harness.role("Admin"), "owner")
    field = harness.user(company, harness.role("Field"), "field.user")  # a role with no grants
    debtors = harness.add(MstGroup(company_id=company.company_id, name="Sundry Debtors", nature="Asset"))
    ledger = harness.add(MstLedger(company_id=company.company_id, name="Amar Enterprises", group_id=debtors.group_id))
    client = harness.app(auth.router, ledgers.router)

    # The admin's read fills the cache
    admin_reply = client.get(f"/ledgers/{ledger.ledger_id}", headers=bearer(login(client, admin.email)))
    assert admin_reply.status_code == 200
    assert admin_reply.json()["name"] == "Amar Enterprises"

    field_reply = client.get(f"/ledgers/{ledger.ledger_id}", headers=bearer(login(client, field.email)))
    assert field_reply.status_code == 403
    assert "ledger_customer" in field_reply.json()["detail"]
