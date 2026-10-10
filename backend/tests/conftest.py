"""
Test harness: the real models and routers on throwaway SQLite databases.

Run from backend/:
    pip install -r requirements.txt
    pytest tests

The portal and Tally schemas are attached as two SQLite databases so cross-schema models work.
DATABASE_URL is forced to an unreachable dummy so a test can never touch the database in .env.
"""
import os
import sys

# Must run before any app import: settings are read at import time, and env vars beat .env
os.environ.update(
    DATABASE_URL="mysql+aiomysql://test:test@127.0.0.1:1/mytally_db",
    TALLY_DATABASE_NAME="tally_sync",
    DB_SSL="false",
    JWT_SECRET="test-secret-key-for-the-pytest-suite-0123456789",
    RATE_LIMIT_ENABLED="false",
    RAZORPAY_WEBHOOK_SECRET="",
    TALLY_URL="",
    LOG_LEVEL="WARNING",
)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio  # noqa: E402
import hashlib  # noqa: E402
from contextlib import contextmanager  # noqa: E402
from datetime import date, timedelta  # noqa: E402

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import BigInteger, event  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.ext.compiler import compiles  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402


@compiles(BigInteger, "sqlite")
def _bigint_as_integer(type_, compiler, **kw):
    # SQLite only auto-increments INTEGER PRIMARY KEY columns
    return "INTEGER"


from app.core.database import Base, get_db  # noqa: E402
from app.core.cache import clear_all_cache  # noqa: E402
from app.core.permissions import clear_all_auth_and_permission_caches  # noqa: E402
from app.core.security import create_access_token, get_password_hash  # noqa: E402
import app.models.portal_core as P  # noqa: E402
import app.models.tally_core  # noqa: E402,F401
import app.routers.attendance  # noqa: E402,F401  (registers attendance models)
import app.routers.sync  # noqa: E402,F401

PASSWORD = "pw-123456"
# bcrypt is deliberately slow; hash the shared test password once
PASSWORD_HASH = get_password_hash(PASSWORD)


def run(coro):
    return asyncio.run(coro)


class Harness:
    def __init__(self, tmp_path):
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/main.db", poolclass=NullPool)

        @event.listens_for(self.engine.sync_engine, "connect")
        def _attach(conn, _):
            conn.execute(f"ATTACH DATABASE '{tmp_path}/portal.db' AS mytally_db")
            conn.execute(f"ATTACH DATABASE '{tmp_path}/tally.db' AS tally_sync")

        self.Session = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

        async def create():
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        run(create())

    async def _get_db(self):
        async with self.Session() as session:
            yield session

    def app(self, *routers) -> TestClient:
        """Routers to mount; pass (router, "/prefix") for one main.py mounts under a prefix."""
        app = FastAPI()
        for router in routers:
            router, prefix = router if isinstance(router, tuple) else (router, "")
            app.include_router(router, prefix=prefix)
        app.dependency_overrides[get_db] = self._get_db
        return TestClient(app)

    # ── data helpers ──
    def query(self, stmt):
        async def go():
            async with self.Session() as db:
                return (await db.execute(stmt)).all()
        return run(go())

    def scalar(self, stmt):
        rows = self.query(stmt)
        return rows[0][0] if rows else None

    def add(self, *objects):
        async def go():
            async with self.Session() as db:
                db.add_all(objects)
                await db.commit()
        run(go())
        return objects[0] if len(objects) == 1 else objects

    def execute(self, stmt):
        async def go():
            async with self.Session() as db:
                await db.execute(stmt)
                await db.commit()
        run(go())

    @contextmanager
    def count_queries(self):
        """Collects every SQL statement sent to the database inside the block."""
        statements = []

        def before_execute(conn, cursor, statement, *args):
            statements.append(statement)

        event.listen(self.engine.sync_engine, "before_cursor_execute", before_execute)
        try:
            yield statements
        finally:
            event.remove(self.engine.sync_engine, "before_cursor_execute", before_execute)

    def role(self, name, max_active_devices=None):
        return self.add(P.Role(name=name, max_active_devices=max_active_devices))

    def company(self, name="Alpha"):
        return self.add(P.Company(name=name, books_begin_date=date(2026, 4, 1)))

    def user(self, company, role, name):
        user = self.add(P.User(company_id=company.company_id, username=name, email=f"{name}@example.com",
                               password_hash=PASSWORD_HASH, role_id=role.role_id, is_active=True))
        self.add(P.UserCompanyAccess(user_id=user.user_id, company_id=company.company_id))
        return user

    def legacy_session(self, user, days_ago=3):
        """A session as created before device tracking: no device fields, never used since."""
        from app.core.datetime_utils import get_ist_now
        token = create_access_token(user.user_id)
        self.add(P.UserSession(user_id=user.user_id, token_hash=hashlib.sha256(token.encode()).hexdigest(),
                               created_at=get_ist_now() - timedelta(days=days_ago),
                               expires_at=get_ist_now() + timedelta(days=20)))
        return token


@pytest.fixture
def harness(tmp_path):
    clear_all_auth_and_permission_caches()
    clear_all_cache()
    yield Harness(tmp_path)
    clear_all_auth_and_permission_caches()
    clear_all_cache()


# ── device header presets ──
CHROME_WINDOWS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "X-Device-Id": "web-0f6c2a1e-1111-4a5b-9c3d-000000000001",
    "X-Client-Type": "web",
}
ANDROID_APP = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 14; SM-A515F Build/UP1A; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/129.0.6668.81 Mobile Safari/537.36",
    "X-Device-Id": "android-7f3e9b2c4d5a6e10",
    "X-Client-Type": "android",
    "X-Device-Name": "Samsung SM-A515F",
    "X-Device-Type": "mobile",
    "X-App-Version": "1.0",
}
SYNC_AGENT = {
    "User-Agent": "SnehDistSyncAgent/1.1.0 (Windows)",
    "X-Device-Id": "agent-4b1d8c0f2e7a9d3366c1",
    "X-Client-Type": "sync-agent",
    "X-Device-Name": "SNEH-PC",
}


def login(client, email, headers=None):
    response = client.post("/auth/login", json={"email": email, "password": PASSWORD}, headers=headers or {})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def bearer(token, extra=None):
    return {"Authorization": f"Bearer {token}", **(extra or {})}
