"""Moving a one-customer server into one account: every existing row gets its owner, nobody new is created,
nothing is deleted, and a second run changes nothing."""
from datetime import date

import pytest
from sqlalchemy import func, select

import app.models.portal_core as P
import app.models.tally_core as T
from app.routers.attendance import Attendance
from app.routers.expenses import Expense
from app.routers.orders import TempOrder
from app.services.tenant_migration import MigrationRefused, migrate_to_single_account, remaining_problems
from tests.conftest import run


def migrate(harness, commit=True, **kwargs):
    async def go():
        async with harness.Session() as db:
            changed = await migrate_to_single_account(db, **kwargs)
            problems = await remaining_problems(db)
            await (db.commit() if commit else db.rollback())
            return changed, problems
    return run(go())


def seed(harness):
    alpha, beta = harness.company("Alpha"), harness.company("Beta")
    admin_role, sales_role = harness.role("Admin"), harness.role("Salesman")
    owner = harness.user(alpha, admin_role, "owner")
    partner = harness.user(alpha, admin_role, "partner")
    rep = harness.user(alpha, sales_role, "rep")
    group = harness.add(T.MstGroup(company_id=beta.company_id, name="Debtors", nature="Assets"))
    beta_ledger = harness.add(T.MstLedger(company_id=beta.company_id, name="Shop", group_id=group.group_id))
    harness.add(
        TempOrder(user_id=rep.user_id, ledger_id=beta_ledger.ledger_id),   # made for Beta's customer
        TempOrder(user_id=rep.user_id),                                    # no ledger: goes by its owner
        Expense(user_id=rep.user_id, amount=120, category="Fuel", payment_mode="Cash", expense_date=date(2026, 10, 1)),
        Attendance(user_id=rep.user_id),
    )
    return alpha, beta, owner, partner, rep


def test_everything_existing_moves_into_one_account(harness):
    alpha, beta, owner, partner, rep = seed(harness)

    changed, problems = migrate(harness)

    assert problems == []
    account_id = changed["account_id"]
    assert harness.query(select(P.Account.name, P.Account.created_by_user_id)) == [("Alpha", owner.user_id)]
    for model in (P.Company, P.User, P.Role):
        assert {row[0] for row in harness.query(select(model.account_id))} == {account_id}
    assert harness.scalar(select(Attendance.account_id)) == account_id
    assert [row[0] for row in harness.query(select(TempOrder.company_id).order_by(TempOrder.id))] == [
        beta.company_id, alpha.company_id]
    assert harness.scalar(select(Expense.company_id)) == alpha.company_id
    # No user created; both admins, and only they, may run the sync agent
    assert harness.scalar(select(func.count()).select_from(P.User)) == 3
    granted = harness.query(
        select(P.UserPermissionOverride.user_id).join(P.Module, P.Module.module_id == P.UserPermissionOverride.module_id)
        .where(P.Module.code == "sync_agent").order_by(P.UserPermissionOverride.user_id))
    assert [row[0] for row in granted] == [owner.user_id, partner.user_id]
    assert changed["sync_agent_granted_to"] == [owner.email, partner.email]


def test_second_run_changes_nothing(harness):
    seed(harness)
    migrate(harness)

    changed, problems = migrate(harness)

    assert problems == []
    assert changed["account"].startswith("existing")
    assert {key: value for key, value in changed.items() if isinstance(value, int) and key != "account_id"} == {
        "companies": 0, "users": 0, "roles": 0, "attendance": 0, "attendance_locations": 0,
        "temp_orders": 0, "sales_visits": 0, "shop_payments": 0, "expenses": 0, "settings": 0}
    assert changed["sync_agent_granted_to"] == []
    assert harness.scalar(select(func.count()).select_from(P.Account)) == 1
    assert harness.scalar(select(func.count()).select_from(P.UserPermissionOverride)) == 2


def test_rolled_back_run_leaves_the_data_as_it_was(harness):
    seed(harness)

    changed, _ = migrate(harness, commit=False, account_name="Sneh")

    assert changed["companies"] == 2
    assert harness.scalar(select(func.count()).select_from(P.Account)) == 0
    assert {row[0] for row in harness.query(select(P.User.account_id))} == {None}


def test_refuses_a_server_that_already_has_several_accounts(harness):
    seed(harness)
    harness.add(P.Account(name="One"), P.Account(name="Two"))

    with pytest.raises(MigrationRefused, match="2 accounts"):
        migrate(harness)
    assert {row[0] for row in harness.query(select(P.Company.account_id))} == {None}


def test_refuses_when_no_admin_would_be_left_to_run_the_account(harness):
    company = harness.company("Alpha")
    harness.user(company, harness.role("Salesman"), "rep")

    with pytest.raises(MigrationRefused, match="admin"):
        migrate(harness)


def test_the_businesss_settings_become_the_accounts(harness):
    from app.services.app_settings import get_settings
    seed(harness)
    harness.add(P.AppSetting(key="default_credit_days", value="45"))

    changed, _ = migrate(harness)
    assert changed["settings"] == 1
    assert migrate(harness)[0]["settings"] == 0          # not copied twice

    async def read():
        async with harness.Session() as db:
            return await get_settings(db, changed["account_id"])
    assert run(read())["default_credit_days"] == 45


def test_keys_that_become_unique_cover_companies_roles_and_tally_records():
    from app.services.tenant_migration import unique_key_targets
    targets = {table: (columns, name) for _, table, columns, name in unique_key_targets()}

    assert targets["companies"] == (("account_id", "tally_guid"), "uq_companies_account_guid")
    assert targets["roles"] == (("account_id", "name"), "uq_roles_account_name")
    assert targets["ledgers"][0] == ("company_id", "tally_guid") and targets["vouchers"][0] == ("company_id", "tally_guid")
    assert all(len(name) <= 64 for _, name in targets.values())          # MySQL's limit on an index name
    assert all(columns[0] in ("company_id", "account_id") for columns, _ in targets.values())
    # A GUID that is not one row's own identity must never be made unique
    assert "bills" not in targets and "deleted_records_audit" not in targets
