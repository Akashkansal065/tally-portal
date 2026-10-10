"""The ownership inventory reports what stands between today's rows and enforced accounts, and changes nothing."""
import app.models.portal_core as P
import app.models.tally_core as T
from app.routers.orders import TempOrder
from app.services.tenant_inventory import blocking_findings, collect_inventory
from tests.conftest import run


def inventory(harness):
    async def go():
        async with harness.Session() as db:
            return await collect_inventory(db)
    return run(go())


def ledger(harness, company, name, guid):
    group = harness.add(T.MstGroup(company_id=company.company_id, name=f"{name} group", nature="Assets"))
    return harness.add(T.MstLedger(company_id=company.company_id, name=name, group_id=group.group_id, tally_guid=guid))


def test_reports_owners_duplicates_and_misplaced_sales_rows(harness):
    account = harness.add(P.Account(name="One"))
    alpha, beta = harness.company("Alpha"), harness.company("Beta")
    harness.execute(P.Company.__table__.update().where(P.Company.company_id == alpha.company_id)
                    .values(account_id=account.account_id, tally_guid="guid-alpha"))
    user = harness.user(alpha, harness.role("Admin"), "owner")   # no account yet; home company Alpha
    harness.add(P.UserCompanyAccess(user_id=user.user_id, company_id=beta.company_id))
    ledger(harness, alpha, "Cash", "g-1")
    ledger(harness, alpha, "Cash copy", "g-1")                    # same GUID twice in one company
    ledger(harness, alpha, "Bank", "g-2")
    beta_ledger = ledger(harness, beta, "Cash", "g-1")            # same GUID in another company is fine
    harness.add(TempOrder(user_id=user.user_id, ledger_id=beta_ledger.ledger_id))  # owner is "in" Alpha

    report = inventory(harness)

    assert [(c["name"], c["account_id"], c["ledgers"]) for c in report["companies"]] == [
        ("Alpha", account.account_id, 3), ("Beta", None, 1)]
    assert report["companies_without_guid"] == [beta.company_id]
    assert report["users"][0]["granted_company_ids"] == [alpha.company_id, beta.company_id]
    # The user has no account: the grant to Alpha (which has one) crosses, the grant to Beta (none) does not
    assert report["cross_account_grants"] == [{"user_id": user.user_id, "company_id": alpha.company_id}]
    assert report["duplicate_tally_guids"] == {
        "ledgers": [{"company_id": alpha.company_id, "tally_guid": "g-1", "rows": 2}]}
    assert report["sales_rows_under_another_company"]["temp_orders"] == 1
    assert report["rows_without_owner"]["users.account_id"] == {"missing": 1, "total": 1}
    assert report["rows_without_owner"]["temp_orders.company_id"] == {"missing": 1, "total": 1}

    findings = "\n".join(blocking_findings(report))
    for expected in ("no Tally GUID", "cross accounts", "ledgers: 1 Tally GUID", "users.account_id: 1 of 1", "temp_orders: 1 row"):
        assert expected in findings


def test_clean_data_has_no_findings_and_nothing_is_written(harness):
    account = harness.add(P.Account(name="One"))
    company = harness.company("Alpha")
    harness.execute(P.Company.__table__.update().values(account_id=account.account_id, tally_guid="guid-alpha"))
    role = harness.role("Admin")
    harness.execute(P.Role.__table__.update().values(account_id=account.account_id))
    user = harness.user(company, role, "owner")
    harness.execute(P.User.__table__.update().values(account_id=account.account_id))

    with harness.count_queries() as statements:
        report = inventory(harness)

    assert blocking_findings(report) == []
    assert all(statement.lstrip().upper().startswith("SELECT") for statement in statements)
