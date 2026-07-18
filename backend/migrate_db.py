import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=True)

async def main():
    async with engine.begin() as conn:
        print("Migrating users table...")
        # Add columns if they do not exist
        columns_to_add = [
            ("show_ledger", "BOOLEAN NOT NULL DEFAULT TRUE"),
            ("show_stocks", "BOOLEAN NOT NULL DEFAULT TRUE"),
            ("show_reports", "BOOLEAN NOT NULL DEFAULT FALSE"),
            ("show_orders", "BOOLEAN NOT NULL DEFAULT FALSE"),
            ("show_check_in", "BOOLEAN NOT NULL DEFAULT TRUE"),
            ("show_sales_ledgers", "BOOLEAN NOT NULL DEFAULT TRUE"),
            ("show_purchase_ledgers", "BOOLEAN NOT NULL DEFAULT FALSE"),
            ("show_receipts", "BOOLEAN NOT NULL DEFAULT TRUE"),
            ("show_payments", "BOOLEAN NOT NULL DEFAULT TRUE"),
            ("show_expenses", "BOOLEAN NOT NULL DEFAULT FALSE"),
            ("ledger_scope", "VARCHAR(64) NOT NULL DEFAULT 'dr_only'"),
            ("stock_scope", "VARCHAR(64) NOT NULL DEFAULT 'full'"),
            ("allowed_stock_groups", "VARCHAR(1024) NULL"),
            ("allowed_ledger_groups", "VARCHAR(1024) NULL"),
            ("allowed_report_categories", "VARCHAR(1024) NULL"),
        ]
        
        for col_name, col_type in columns_to_add:
            try:
                await conn.execute(text(f"ALTER TABLE tally_portal.users ADD COLUMN {col_name} {col_type};"))
                print(f"Added column {col_name}")
            except Exception as e:
                # Column might already exist, ignore error
                print(f"Skipping {col_name}: {e}")

asyncio.run(main())
