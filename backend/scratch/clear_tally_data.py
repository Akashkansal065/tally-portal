import asyncio
import os
import sys
from sqlalchemy import text

# Add parent directory of scratch to sys.path to enable app module imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import engine, Base
# Import all models to ensure complete metadata registration
import app.models.tally_core
import app.models.portal_core

# Core system tables to preserve (user accounts, roles, permissions, registered companies)
PRESERVED_TABLES = {
    "users", "roles", "permissions", "modules", "role_permissions",
    "user_permission_overrides", "user_company_access", "companies",
    "financial_years", "alembic_version"
}

async def clear_data(target_db: str = "tally_sync"):
    print("Ensuring databases exist...")
    from app.core.database import create_databases_if_not_exist
    await create_databases_if_not_exist()
    
    print(f"Target database selection: '{target_db}'")
    print("Connecting to database...")
    
    async with engine.begin() as conn:
        print("Disabling foreign key checks...")
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
        
        # Discover all tables dynamically from SQLAlchemy metadata
        all_tables = Base.metadata.tables
        
        cleared_count = 0
        for table_key, table_obj in all_tables.items():
            table_name = table_obj.name
            schema_name = table_obj.schema
            
            # Skip preserved core system tables
            if table_name in PRESERVED_TABLES:
                continue
                
            # Filter by target_db selection
            if target_db == "tally_sync" and schema_name != "tally_sync":
                continue
            elif target_db == "tally_portal" and schema_name != "tally_portal":
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
        
    print(f"Database clear operations completed successfully! ({cleared_count} tables truncated)")
    await engine.dispose()

if __name__ == "__main__":
    # Options: "all", "tally_sync", or "tally_portal"
    TARGET_DB = "tally_sync"
    
    asyncio.run(clear_data(TARGET_DB))
