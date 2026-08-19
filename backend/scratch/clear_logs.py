import asyncio
import os
import sys
from sqlalchemy import text

# Add parent directory of scratch to sys.path to enable app module imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from app.core.database import engine
from app.core.config import settings

# Explicit log & audit tables to truncate
LOG_TABLES = [
    f"`{settings.PORTAL_DATABASE_NAME}`.`sync_traffic_logs`",
    f"`{settings.PORTAL_DATABASE_NAME}`.`deleted_records_audit`",
    f"`{settings.PORTAL_DATABASE_NAME}`.`sync_queue`",
    f"`{settings.PORTAL_DATABASE_NAME}`.`audit_logs`",
]

async def clear_logs():
    print("Connecting to database...")
    async with engine.begin() as conn:
        print("Disabling foreign key checks...")
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
        
        cleared_count = 0
        for fq_table in LOG_TABLES:
            print(f"Truncating table: {fq_table}...")
            try:
                await conn.execute(text(f"TRUNCATE TABLE {fq_table};"))
                print(f" -> Table {fq_table} cleared successfully.")
                cleared_count += 1
            except Exception as e:
                print(f" -> Error truncating {fq_table}: {e}")
                
        print("Enabling foreign key checks...")
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
        
    print(f"Database log clear operations completed successfully! ({cleared_count} tables truncated)")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(clear_logs())
