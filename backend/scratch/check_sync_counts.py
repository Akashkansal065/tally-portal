import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def main():
    async with async_session() as session:
        for table in ["account_groups", "ledgers", "vouchers", "voucher_entries", "stock_groups", "uoms", "godowns", "stock_categories", "stock_items"]:
            try:
                res = await session.execute(text(f"SELECT COUNT(*) FROM tally_sync.{table}"))
                count = res.scalar()
                print(f"Table tally_sync.{table}: {count} rows")
            except Exception as e:
                print(f"Table tally_sync.{table} failed: {str(e)}")

asyncio.run(main())
