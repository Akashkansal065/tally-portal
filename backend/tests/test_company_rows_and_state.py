"""Field-sales rows stay with the company they were made for when their owner switches company, and the agent's
per-company report is what "Last synced" is read from."""
from sqlalchemy import select

import app.models.portal_core as P
import app.models.tally_core as T
from app.core.tenancy import rows_of_account, rows_of_company, rows_of_company_by_ledger
from app.routers import agent, auth, sync
from app.routers.attendance import Attendance
from app.routers.orders import TempOrder
from tests.conftest import bearer, login, run


def ids(harness, stmt):
    return sorted(row[0] for row in harness.query(stmt))


def as_user(harness, user_id, company_id):
    """The caller as a request sees them: their row, working in the given company."""
    async def go():
        async with harness.Session() as db:
            user = (await db.execute(select(P.User).where(P.User.user_id == user_id))).scalars().first()
            db.expunge(user)
            user.company_id = company_id
            return user
    return run(go())


def test_orders_stay_with_their_company_when_the_owner_switches(harness):
    alpha, beta = harness.company("Alpha"), harness.company("Beta")
    rep = harness.user(alpha, harness.role("Salesman"), "rep")
    in_alpha, in_beta, old = harness.add(
        TempOrder(user_id=rep.user_id, company_id=alpha.company_id),
        TempOrder(user_id=rep.user_id, company_id=beta.company_id),
        TempOrder(user_id=rep.user_id),          # from before rows carried a company
    )
    orders = lambda viewer: select(TempOrder.id).join(P.User, P.User.user_id == TempOrder.user_id).where(  # noqa: E731
        rows_of_company(TempOrder, viewer))

    assert ids(harness, orders(as_user(harness, rep.user_id, alpha.company_id))) == sorted([in_alpha.id, old.id])
    assert ids(harness, orders(as_user(harness, rep.user_id, beta.company_id))) == [in_beta.id]

    # The rep makes Beta their active company: the Alpha order does not follow them
    harness.execute(P.User.__table__.update().where(P.User.user_id == rep.user_id).values(company_id=beta.company_id))
    assert ids(harness, orders(as_user(harness, rep.user_id, alpha.company_id))) == [in_alpha.id]
    assert ids(harness, orders(as_user(harness, rep.user_id, beta.company_id))) == sorted([in_beta.id, old.id])


def test_shop_payments_are_listed_only_for_their_company(harness):
    alpha, beta = harness.company("Alpha"), harness.company("Beta")
    rep = harness.user(alpha, harness.role("Salesman"), "rep")
    ledgers = {}
    for company in (alpha, beta):
        group = harness.add(T.MstGroup(company_id=company.company_id, name="Debtors", nature="Assets"))
        ledgers[company.company_id] = harness.add(T.MstLedger(company_id=company.company_id, name="Shop", group_id=group.group_id))
    mine = harness.add(P.ShopPayment(user_id=rep.user_id, ledger_id=ledgers[alpha.company_id].ledger_id, amount=10,
                                     payment_mode="Cash", company_id=alpha.company_id))
    old = harness.add(P.ShopPayment(user_id=rep.user_id, ledger_id=ledgers[alpha.company_id].ledger_id, amount=20, payment_mode="Cash"))
    other = harness.add(P.ShopPayment(user_id=rep.user_id, ledger_id=ledgers[beta.company_id].ledger_id, amount=30, payment_mode="Cash"))
    payments = lambda viewer: select(P.ShopPayment.id).where(rows_of_company_by_ledger(P.ShopPayment, viewer))  # noqa: E731

    assert ids(harness, payments(as_user(harness, rep.user_id, alpha.company_id))) == sorted([mine.id, old.id])
    assert ids(harness, payments(as_user(harness, rep.user_id, beta.company_id))) == [other.id]


def test_attendance_is_the_accounts_not_one_companys(harness):
    account = harness.add(P.Account(name="One"))
    alpha, beta = harness.company("Alpha"), harness.company("Beta")
    role = harness.role("Salesman")
    rep, other_rep = harness.user(alpha, role, "rep"), harness.user(beta, role, "other")
    harness.execute(P.User.__table__.update().values(account_id=account.account_id))
    harness.add(Attendance(user_id=rep.user_id, account_id=account.account_id),
                Attendance(user_id=other_rep.user_id, account_id=account.account_id))
    attendance = lambda viewer: select(Attendance.id).join(P.User, P.User.user_id == Attendance.user_id).where(  # noqa: E731
        rows_of_account(Attendance, viewer))

    # Seen from either company of the account: one record per person per day, whichever company they are in
    assert len(ids(harness, attendance(as_user(harness, rep.user_id, alpha.company_id)))) == 2
    assert len(ids(harness, attendance(as_user(harness, rep.user_id, beta.company_id)))) == 2


def test_last_synced_moves_only_on_a_clean_cycle(harness):
    company = harness.company("Alpha")
    harness.execute(P.Company.__table__.update().values(tally_guid="guid-alpha"))
    admin = harness.user(company, harness.role("Admin"), "owner")
    client = harness.app(auth.router, agent.router, sync.router)
    headers = bearer(login(client, admin.email))
    report = lambda **fields: client.post("/sync/state", headers=headers, json=[{"tally_guid": "guid-alpha", **fields}])  # noqa: E731

    assert report(state="error", error="Tally timed out").json() == {"recorded": 1, "skipped": []}
    state = harness.query(select(P.CompanySyncState.state, P.CompanySyncState.last_success_at, P.CompanySyncState.last_error))
    assert state == [("error", None, "Tally timed out")]

    report(state="live", ok=True, voucher_alter_id=42)
    row = harness.query(select(P.CompanySyncState.state, P.CompanySyncState.last_error, P.CompanySyncState.voucher_alter_id))
    assert row == [("live", None, 42)]
    succeeded_at = harness.scalar(select(P.CompanySyncState.last_success_at))
    assert succeeded_at is not None

    # Closed in Tally afterwards: reported, but the last success stays where it was
    report(state="closed")
    assert harness.scalar(select(P.CompanySyncState.last_success_at)) == succeeded_at
    assert client.post("/sync/state", headers=headers, json=[{"tally_guid": "guid-unknown", "state": "live", "ok": True}]).json() == {
        "recorded": 0, "skipped": ["guid-unknown"]}
