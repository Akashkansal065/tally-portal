"""
⚠️ DEV ONLY: wipes ALL companies, users, sessions and permission overrides in the portal database,
then recreates one company (ID 1) with default groups/voucher types and one admin user.

Synced Tally data in the tally schema is NOT removed (use reset_sync.py / wipe_all.py for that).
For a normal fresh install you don't need this: start the API and register the first company
from the login page (bootstrap mode).

From backend/:
    python scratch/reset_companies.py --admin-email admin@example.com
The admin password is prompted for (or read from RESET_ADMIN_PASSWORD for scripted use).
Refuses to touch a non-local database unless --allow-remote is given, and always asks you to
type the database name to confirm (skip with --yes only in throwaway environments).
"""
import argparse
import asyncio
import getpass
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.config import settings  # noqa: E402

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "db", "mysql", "host.docker.internal"}


def confirm_target(args) -> None:
    """All safety checks happen here, before any database connection is opened."""
    url = make_url(settings.DATABASE_URL)
    host, db_name = url.host or "", url.database or ""
    print(f"Target database: {url.render_as_string(hide_password=True)}")
    if host not in LOCAL_HOSTS and not args.allow_remote:
        sys.exit(f"Refusing to wipe users on non-local host '{host}'. Pass --allow-remote if you really mean it.")
    if not args.yes:
        typed = input(f"This deletes ALL companies, users and sessions in '{db_name}' on '{host}'. Type the database name to continue: ")
        if typed.strip() != db_name:
            sys.exit("Confirmation did not match. Nothing was changed.")


def admin_password() -> str:
    password = os.environ.get("RESET_ADMIN_PASSWORD") or getpass.getpass("New admin password: ")
    if len(password) < 8:
        sys.exit("Admin password must be at least 8 characters. Nothing was changed.")
    return password


async def reset_companies_and_users(admin_email: str, password: str, company_name: str) -> None:
    from app.core.database import engine, Base, create_databases_if_not_exist
    from app.core.security import get_password_hash
    from app.core.seed import seed_company_defaults
    # Register every model in Base.metadata before create_all
    import app.models.portal_core  # noqa: F401
    import app.models.tally_core  # noqa: F401
    import app.routers.attendance  # noqa: F401  (Attendance models live in the router)
    import app.routers.orders  # noqa: F401
    import app.routers.expenses  # noqa: F401

    print("Ensuring databases exist...")
    await create_databases_if_not_exist()

    try:
        async with engine.begin() as conn:
            print("Creating tables if they do not exist...")
            await conn.run_sync(Base.metadata.create_all)

            # Check prerequisites before anything destructive: MySQL TRUNCATE commits implicitly
            role_row = (await conn.execute(text(
                f"SELECT role_id FROM `{settings.PORTAL_DATABASE_NAME}`.roles WHERE name = 'Admin'"
            ))).fetchone()
            if not role_row:
                sys.exit("Admin role not found. Start the API once so it seeds roles, then re-run. Nothing was changed.")

            await conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
            print("Clearing company, user, session and override data...")
            for table in ("companies", "user_company_access", "users", "user_sessions", "user_permission_overrides"):
                await conn.execute(text(f"TRUNCATE TABLE `{settings.PORTAL_DATABASE_NAME}`.`{table}`"))

            print(f"Inserting company '{company_name}' (ID: 1)...")
            await conn.execute(text(f"""
                INSERT INTO `{settings.PORTAL_DATABASE_NAME}`.companies
                    (company_id, name, country, base_currency, books_begin_date, is_active, created_at, updated_at)
                VALUES (1, :name, 'India', 'INR', '2026-04-01', 1, NOW(), NOW())
            """), {"name": company_name})

            print(f"Creating admin user '{admin_email}' for company 1...")
            await conn.execute(text(f"""
                INSERT INTO `{settings.PORTAL_DATABASE_NAME}`.users
                    (user_id, company_id, username, email, password_hash, role_id, is_active, ledger_scope, stock_scope, created_at)
                VALUES (1, 1, :username, :email, :pwd, :role_id, 1, 'full', 'full', NOW())
            """), {"username": admin_email.split("@")[0], "email": admin_email,
                   "pwd": get_password_hash(password), "role_id": role_row[0]})
            await conn.execute(text(
                f"INSERT INTO `{settings.PORTAL_DATABASE_NAME}`.user_company_access (user_id, company_id) VALUES (1, 1)"
            ))
            await conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))

            print("Seeding default account groups and voucher types for company 1...")
            # Same connection (and TLS settings) as the rest of the reset
            await conn.run_sync(lambda sync_conn: seed_company_defaults(Session(bind=sync_conn), 1, commit=False))
    finally:
        await engine.dispose()

    print("Reset completed. Log in with the admin email and the password you entered.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--admin-email", required=True, help="Email for the recreated admin user")
    parser.add_argument("--company-name", default="Sneh Distributors", help="Name of the recreated company")
    parser.add_argument("--allow-remote", action="store_true", help="Allow a non-local database host")
    parser.add_argument("--yes", action="store_true", help="Skip the typed confirmation (throwaway environments only)")
    args = parser.parse_args()

    confirm_target(args)
    asyncio.run(reset_companies_and_users(args.admin_email, admin_password(), args.company_name))
