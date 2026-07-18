import asyncio
from sqlalchemy import text
from app.core.database import engine, get_db
from app.core.security import get_password_hash
from app.core.seed import seed_company_defaults
from sqlalchemy.orm import Session

async def reset_companies_and_users():
    print("Ensuring databases exist...")
    from app.core.database import create_databases_if_not_exist, Base
    await create_databases_if_not_exist()
    
    # Import all SQLAlchemy models to register them in metadata before create_all
    import app.models.company
    import app.models.user
    import app.models.ledger
    import app.models.voucher
    import app.models.payment
    import app.models.inventory
    import app.models.advanced
    import app.models.gst
    import app.models.currency_tds
    import app.models.payment_gateway
    import app.models.sync
    import app.routers.expenses  # loads Expense model
    
    print("Connecting to database...")
    async with engine.begin() as conn:
        print("Creating tables if they do not exist...")
        await conn.run_sync(Base.metadata.create_all)
        
        print("Disabling foreign key checks...")
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
        
        # 1. Truncate companies, user_company_access, users, and user sessions
        print("Clearing company, user, and session data...")
        await conn.execute(text("TRUNCATE TABLE companies;"))
        await conn.execute(text("TRUNCATE TABLE user_company_access;"))
        await conn.execute(text("TRUNCATE TABLE users;"))
        await conn.execute(text("TRUNCATE TABLE user_sessions;"))
        await conn.execute(text("TRUNCATE TABLE user_permission_overrides;"))
        
        # 2. Insert clean Sneh Distributors company
        print("Inserting clean company 'Sneh Distributors' (ID: 1)...")
        await conn.execute(text("""
            INSERT INTO companies (company_id, name, country, base_currency, books_begin_date, is_active, created_at, updated_at)
            VALUES (1, 'Sneh Distributors', 'India', 'INR', '2026-04-01', 1, NOW(), NOW());
        """))
        
        # 3. Get Admin Role ID
        res = await conn.execute(text("SELECT role_id FROM roles WHERE name = 'Admin';"))
        role_row = res.fetchone()
        admin_role_id = role_row[0] if role_row else 1
        
        # 4. Insert default admin user with full access/scopes
        print("Recreating admin user 'admin_test@test.com' linked to company 1...")
        pwd_hash = get_password_hash("securepassword123")
        await conn.execute(text(f"""
            INSERT INTO users (
                user_id, company_id, username, email, password_hash, role_id, is_active, 
                show_ledger, show_stocks, show_reports, show_orders, show_check_in, 
                show_sales_ledgers, show_purchase_ledgers, show_receipts, show_payments, 
                show_expenses, show_attendance, ledger_scope, stock_scope, created_at
            )
            VALUES (
                1, 1, 'admin_test', 'admin_test@test.com', '{pwd_hash}', {admin_role_id}, 1,
                1, 1, 1, 1, 1,
                1, 1, 1, 1,
                1, 1, 'full', 'full', NOW()
            );
        """))
        
        # 5. Link user to company access
        await conn.execute(text("""
            INSERT INTO user_company_access (user_id, company_id)
            VALUES (1, 1);
        """))
        
        print("Enabling foreign key checks...")
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
        
    # 6. Re-seed default company account groups and voucher types in a separate transaction
    print("Seeding defaults for Sneh Distributors (company_id = 1)...")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from dotenv import load_dotenv
    import os
    
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
    db_url = os.getenv("DATABASE_URL")
    if db_url and "mysql+aiomysql://" in db_url:
        db_url = db_url.replace("mysql+aiomysql://", "mysql+pymysql://")
        
    if db_url:
        sync_engine = create_engine(db_url)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)
        db = SessionLocal()
        try:
            seed_company_defaults(db, 1)
        finally:
            db.close()
            
    print("Reset operations completed successfully!")

if __name__ == "__main__":
    asyncio.run(reset_companies_and_users())
