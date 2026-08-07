import asyncio
import os
import sys
from sqlalchemy import text

# Add parent directory of scratch to sys.path to enable app module imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import engine, Base
# Import all models to ensure complete metadata registration
import app.models.advanced
import app.models.company
import app.models.currency_tds
import app.models.gst
import app.models.inventory
import app.models.ledger
import app.models.payment
import app.models.payment_gateway
import app.models.sync
import app.models.user
import app.models.voucher

# Core system tables to preserve (preserves user accounts, credentials, roles, & permissions)
USER_PRESERVED_TABLES = {
    "users", "roles", "permissions", "modules", "role_permissions",
    "user_permission_overrides", "refresh_tokens", "alembic_version"
}

async def clear_companies():
    """
    Deletes ALL companies and company-related data from MySQL.
    Preserves user login accounts, roles, permissions, and system modules.
    """
    print("Ensuring databases exist...")
    from app.core.database import create_databases_if_not_exist
    await create_databases_if_not_exist()
    
    print("Connecting to database...")
    async with engine.begin() as conn:
        print("Disabling foreign key checks...")
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
        
        all_tables = Base.metadata.tables
        cleared_count = 0
        
        for table_key, table_obj in all_tables.items():
            table_name = table_obj.name
            schema_name = table_obj.schema
            
            # Skip preserved user/system tables
            if table_name in USER_PRESERVED_TABLES:
                continue
                
            fq_table = f"`{schema_name}`.`{table_name}`" if schema_name else f"`{table_name}`"
            print(f"Truncating table: {fq_table}...")
            try:
                await conn.execute(text(f"TRUNCATE TABLE {fq_table};"))
                print(f" -> Table {fq_table} cleared successfully.")
                cleared_count += 1
            except Exception as e:
                print(f" -> Error truncating {fq_table}: {e}")
                
        print("Enabling foreign key checks...")
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
        
    print(f"Company clear operations completed successfully! ({cleared_count} tables truncated)")
    print("User accounts, credentials, roles, and permissions remain intact.")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(clear_companies())
