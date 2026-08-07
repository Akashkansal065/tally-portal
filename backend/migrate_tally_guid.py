import asyncio
from app.core.database import engine
from sqlalchemy import text

async def add_column():
    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE companies ADD COLUMN tally_guid VARCHAR(100);"))
            await conn.execute(text("CREATE INDEX ix_tally_guid ON companies(tally_guid);"))
            print("Column tally_guid and index added successfully.")
        except Exception as e:
            print(f"Error (might already exist): {e}")

asyncio.run(add_column())
