from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()

async def create_databases_if_not_exist():
    from sqlalchemy import text
    db_url = settings.DATABASE_URL
    base_url, portal_db = db_url.rsplit('/', 1)
    if '?' in portal_db:
        portal_db = portal_db.split('?')[0]
    tally_db = settings.TALLY_DATABASE_NAME
    
    # Create temp engine connected to MySQL server base to execute database creation
    temp_engine = create_async_engine(base_url, echo=False)
    async with temp_engine.begin() as conn:
        await conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {portal_db}"))
        await conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {tally_db}"))
    await temp_engine.dispose()

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
