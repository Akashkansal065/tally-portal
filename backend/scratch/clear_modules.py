import asyncio
from app.core.database import AsyncSessionLocal
from sqlalchemy import text

async def clear():
    async with AsyncSessionLocal() as s:
        # Disable foreign key checks temporarily to clear cleanly
        await s.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        await s.execute(text("TRUNCATE TABLE permissions"))
        await s.execute(text("TRUNCATE TABLE modules"))
        await s.execute(text("TRUNCATE TABLE roles"))
        await s.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        await s.commit()
    print("Database security tables cleared. Ready for re-seeding.")

if __name__ == "__main__":
    asyncio.run(clear())
