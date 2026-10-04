"""ensure_table_indexes creates only the listed indexes that MySQL doesn't have yet."""
from contextlib import asynccontextmanager

import pytest

import app.core.database as database
import app.models.portal_core as P
from tests.conftest import run


class FakeConnection:
    def __init__(self, existing):
        self.existing = existing
        self.created = []

    async def execute(self, statement, params=None):
        sql = str(statement)
        if sql.startswith("SELECT DISTINCT INDEX_NAME"):
            return FakeResult([(name,) for name in self.existing])
        self.created.append(sql)


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


@pytest.fixture
def mysql(monkeypatch):
    conn = FakeConnection(existing={"PRIMARY", "ix_sync_traffic_company_status"})

    class FakeEngine:
        @asynccontextmanager
        async def begin(self):
            yield conn

    monkeypatch.setattr(database, "engine", FakeEngine())
    monkeypatch.setattr(database.settings, "DATABASE_URL", "mysql+aiomysql://u:p@db.example:3306/mytally_db")
    return conn


def test_creates_only_missing_listed_indexes(mysql):
    table = P.SyncTrafficLog.__table__
    run(database.ensure_table_indexes(table, ["ix_sync_traffic_company_status", "ix_sync_traffic_company_created"]))

    assert mysql.created == [
        f"CREATE INDEX `ix_sync_traffic_company_created` ON `{table.schema}`.`sync_traffic_logs` (`company_id`, `created_at`)"
    ]


def test_single_column_indexes_are_never_built_implicitly(mysql):
    # sync_traffic_logs has several index=True columns the fake database "lacks"; none may be created
    run(database.ensure_table_indexes(P.SyncTrafficLog.__table__, []))
    assert mysql.created == []


def test_unknown_index_name_is_rejected(mysql):
    with pytest.raises(ValueError, match="ix_does_not_exist"):
        run(database.ensure_table_indexes(P.SyncQueue.__table__, ["ix_does_not_exist"]))
