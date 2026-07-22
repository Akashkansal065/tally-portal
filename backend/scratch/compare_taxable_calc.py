import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from datetime import date

# Import all models to register them
from app.models.company import Company
from app.models.user import User
from app.models.voucher import TrnVoucher

from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def main():
    async with async_session() as session:
        start_date = date(2026, 3, 1)
        end_date = date(2026, 3, 31)
        
        stmt = select(TrnVoucher).where(
            TrnVoucher.company_id == 1,
            TrnVoucher.voucher_date >= start_date,
            TrnVoucher.voucher_date <= end_date
        ).order_by(TrnVoucher.voucher_number.asc())
        
        res = await session.execute(stmt)
        vouchers = res.scalars().all()
        
        print(f"Total Vouchers: {len(vouchers)}")
        for v in vouchers:
            print(f"  Voucher ID: {v.voucher_id}, Number: {v.voucher_number}, Date: {v.voucher_date}, Amount: {v.total_amount}, GUID: {v.tally_guid}")

if __name__ == "__main__":
    asyncio.run(main())
