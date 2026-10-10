"""Every read endpoint of the real app, called by another customer.

Two businesses share the server. The first one's rows, in every table that belongs to a company or an account
(and the tables hanging off those), carry a marker in every text column. The second business's admin then calls
every GET route the app has, with the first business's ids in the path and its company named in the header. The
marker must never come back. This is the net under the per-router scoping: a new endpoint that forgets to scope
its query fails here without anyone writing a test for it.
"""
import datetime as dt
import re
from decimal import Decimal

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

import app.main  # noqa: F401  (registers every model before the test database is built)
import app.models.portal_core as P
from app.core.database import Base, get_db
from tests.conftest import bearer, login, run

MARK = "ZZALPHA"
# Tables that are the same for everyone, or that this audit sets up by hand
BY_HAND = {"accounts", "companies", "users", "roles", "user_company_access", "permissions", "modules", "user_sessions"}


def _value(column, marker, n):
    kind = column.type
    if isinstance(kind, sa.Enum):
        return kind.enums[0]
    if isinstance(kind, (sa.String, sa.Text)):
        text = f"{marker}-{column.table.name}-{column.name}"
        length = getattr(kind, "length", None)
        if length and length < len(marker):
            return None if column.nullable else "Z" * length
        return text[:length] if length else text
    if isinstance(kind, sa.Boolean):
        return False if column.name in ("is_deleted", "is_cancelled", "is_optional", "is_void") else True
    if isinstance(kind, (sa.Integer, sa.BigInteger, sa.SmallInteger)):
        return n
    if isinstance(kind, (sa.Numeric, sa.Float)):
        return Decimal("1")
    if isinstance(kind, sa.DateTime):
        return dt.datetime(2026, 10, 1, 10, 0)
    if isinstance(kind, sa.Date):
        return dt.date(2026, 10, 1)
    if isinstance(kind, sa.Time):
        return dt.time(10, 0)
    if isinstance(kind, sa.JSON):
        return {"note": marker}
    return None


def owned_tables():
    """Tables with a company or an account of their own, then the ones that hang off them, to any depth."""
    tables = [t for t in Base.metadata.sorted_tables if t.name not in BY_HAND]
    owned = {t for t in tables if "company_id" in t.c or "account_id" in t.c}
    grew = True
    while grew:
        grew = False
        for table in tables:
            if table not in owned and any(fk.column.table in owned for fk in table.foreign_keys):
                owned.add(table)
                grew = True
    return [t for t in tables if t in owned]


def seed_rows(harness, marker, n, company_id, account_id, user_id):
    """One row per owned table. Row n of every table belongs to business n, so ids line up across tables."""
    failed = []

    async def go():
        async with harness.Session() as db:
            for table in owned_tables():
                values = {}
                for column in table.columns:
                    if column.name == "company_id":
                        values[column.name] = company_id
                    elif column.name == "account_id":
                        values[column.name] = account_id
                    elif column.name in ("user_id", "created_by", "created_by_user_id", "salesperson_id", "employee_id"):
                        values[column.name] = user_id
                    elif column.primary_key and column.autoincrement is not False and isinstance(column.type, (sa.Integer, sa.BigInteger)):
                        values[column.name] = n
                    else:
                        value = _value(column, marker, n)
                        if value is not None:
                            values[column.name] = value
                try:
                    async with db.begin_nested():
                        await db.execute(table.insert().values(**values))
                except Exception as e:   # a table this generic row does not fit is reported, not hidden
                    failed.append((table.name, str(e).split("\n")[0][:120]))
            await db.commit()
    run(go())
    return failed


@pytest.fixture
def two_businesses(harness):
    made = {}
    for n, marker in ((1, MARK), (2, "ZZBETA")):
        account = harness.add(P.Account(name=f"{marker} Group", status="active"))
        role = harness.add(P.Role(name="Admin", account_id=account.account_id))
        company = harness.add(P.Company(name=f"{marker} Traders", account_id=account.account_id, tally_guid=f"guid-{n}",
                                        books_begin_date=dt.date(2025, 4, 1), is_active=True))
        user = harness.user(company, role, f"{marker.lower()}owner")
        harness.execute(P.User.__table__.update().where(P.User.user_id == user.user_id).values(account_id=account.account_id))
        made[n] = dict(account=account, company=company, user=user,
                       unseeded=seed_rows(harness, marker, n, company.company_id, account.account_id, user.user_id))
    return made


def test_no_read_endpoint_shows_another_businesss_rows(harness, two_businesses):
    from app.main import app as real_app
    real_app.dependency_overrides[get_db] = harness._get_db
    try:
        client = TestClient(real_app, raise_server_exceptions=False)   # no lifespan: nothing touches a real database
        theirs = two_businesses[1]
        headers = bearer(login(client, two_businesses[2]["user"].email))
        reaching = {**headers, "X-Company-ID": str(theirs["company"].company_id)}

        # The marker really is in the first business's own answers, or finding nothing would prove nothing
        own = bearer(login(client, theirs["user"].email))
        assert MARK in client.get("/auth/me/companies", headers=own).text

        leaks, statuses, called = [], {}, 0
        for route_path, operations in real_app.openapi()["paths"].items():
            if "get" not in operations:
                continue
            if route_path.startswith(("/backup", "/health")) or "export" in route_path or "download" in route_path:
                continue   # files and server checks, not rows
            path = re.sub(r"\{[^}]+\}", "1", route_path)     # every id in the path is the first business's
            for attempt in (headers, reaching):
                try:
                    response = client.get(path, headers=attempt)
                except Exception:   # an endpoint that cannot run on the test database
                    statuses["crashed"] = statuses.get("crashed", 0) + 1
                    continue
                called += 1
                statuses[response.status_code] = statuses.get(response.status_code, 0) + 1
                if MARK in response.text:
                    where = response.text.index(MARK)
                    leaks.append(f"{route_path}: …{response.text[max(0, where - 60):where + 60]}…")
        print(f"\nread endpoints called {called} times: {dict(sorted(statuses.items(), key=str))}; "
              f"tables seeded {len(owned_tables()) - len(theirs['unseeded'])} of {len(owned_tables())}")
        assert called > 300 and statuses.get(200, 0) > 100, statuses
        assert not leaks, "another business's rows were returned by:\n" + "\n".join(sorted(set(leaks)))
    finally:
        real_app.dependency_overrides.pop(get_db, None)


def snapshot(harness):
    """The first business's row in every owned table, as text."""
    async def go():
        rows = {}
        async with harness.Session() as db:
            for table in owned_tables():
                key = list(table.primary_key.columns)[0] if table.primary_key.columns else None
                if key is None or not isinstance(key.type, (sa.Integer, sa.BigInteger)):
                    continue
                rows[table.name] = repr((await db.execute(table.select().where(key == 1))).all())
        return rows
    return run(go())


def test_no_write_endpoint_changes_another_businesss_rows(harness, two_businesses):
    """Every POST, PUT, PATCH and DELETE route, called by the second business with the first one's ids in the
    path, its company in the header and an empty body. Whatever each answers, the first business's rows must be
    exactly as they were."""
    from app.main import app as real_app
    real_app.dependency_overrides[get_db] = harness._get_db
    try:
        client = TestClient(real_app, raise_server_exceptions=False)
        theirs = two_businesses[1]
        headers = bearer(login(client, two_businesses[2]["user"].email))
        reaching = {**headers, "X-Company-ID": str(theirs["company"].company_id)}
        before = snapshot(harness)

        statuses, called, signed_out_by = {}, 0, []
        for route_path, operations in real_app.openapi()["paths"].items():
            if route_path.startswith(("/backup", "/health", "/auth/log", "/auth/me/sessions", "/agent/sign", "/auth/invites")):
                continue   # files, server checks, and the caller's own sign-in
            path = re.sub(r"\{[^}]+\}", "1", route_path)
            for method in ("post", "put", "patch", "delete"):
                if method not in operations:
                    continue
                for attempt in (headers, reaching):
                    try:
                        response = client.request(method.upper(), path, headers=attempt, **({} if method == "delete" else {"json": {}}))
                    except Exception:
                        statuses["crashed"] = statuses.get("crashed", 0) + 1
                        continue
                    called += 1
                    statuses[response.status_code] = statuses.get(response.status_code, 0) + 1
                    if response.status_code == 401:
                        # Something signed the caller out (their own sessions, password or role): sign in again
                        signed_out_by.append(f"{method.upper()} {route_path}")
                        headers = bearer(login(client, two_businesses[2]["user"].email))
                        reaching = {**headers, "X-Company-ID": str(theirs["company"].company_id)}
                        break
        after = snapshot(harness)
        print(f"\nwrite endpoints called {called} times: {dict(sorted(statuses.items(), key=str))}; signed out by {signed_out_by}")
        changed = sorted(name for name in before if before[name] != after.get(name))
        assert called > 200, statuses
        assert not changed, "another business's rows were changed or deleted in: " + ", ".join(changed)
    finally:
        real_app.dependency_overrides.pop(get_db, None)
