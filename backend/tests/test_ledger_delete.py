"""Deleting a ledger removes it and leaves an audit row for the Tally delete sync."""
from sqlalchemy import select

from app.models.portal_core import DeletedRecordAudit, SyncQueue
from app.models.tally_core import MstGroup, MstLedger
from app.routers import auth, ledgers
from tests.conftest import bearer, login


def test_admin_deletes_ledger_and_audit_row_is_written(harness):
    company = harness.company()
    admin = harness.user(company, harness.role("Admin"), "owner")
    debtors = harness.add(MstGroup(company_id=company.company_id, name="Sundry Debtors", nature="Asset"))
    ledger = harness.add(MstLedger(company_id=company.company_id, name="Amar Enterprises", group_id=debtors.group_id))
    client = harness.app(auth.router, ledgers.router)

    reply = client.delete(f"/ledgers/{ledger.ledger_id}", headers=bearer(login(client, admin.email)))

    assert reply.status_code == 200, reply.text
    assert harness.scalar(select(MstLedger.ledger_id).where(MstLedger.ledger_id == ledger.ledger_id)) is None
    audits = [row[0] for row in harness.query(select(DeletedRecordAudit))]
    assert len(audits) == 1
    audit = audits[0]
    assert (audit.entity_type, audit.record_id, audit.entity_identifier) == ("Ledger", ledger.ledger_id, "Amar Enterprises")
    assert audit.company_id == company.company_id
    assert audit.deleted_by_user_id == admin.user_id
    assert audit.snapshot_data["name"] == "Amar Enterprises"
    assert harness.scalar(select(SyncQueue.action).where(SyncQueue.record_type == "Ledger")) == "Delete"
