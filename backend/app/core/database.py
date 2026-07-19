import ssl
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.core.config import settings

# Setup SSL connect args for Aiven/cloud databases
connect_args = {}
if settings.DB_SSL:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    # Fallback/support for secure CA certificate validation if file is present
    ca_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "ca.pem"))
    if os.path.exists(ca_path):
        try:
            ctx.load_verify_locations(cafile=ca_path)
            ctx.verify_mode = ssl.CERT_REQUIRED
            ctx.check_hostname = True
            print("Database configured to use secure CA verification from ca.pem")
        except Exception as e:
            print("Error loading ca.pem certificate:", e)
            
    connect_args["ssl"] = ctx

engine = create_async_engine(
    settings.DATABASE_URL, 
    connect_args=connect_args, 
    pool_size=10,
    max_overflow=20,
    pool_recycle=300, 
    pool_pre_ping=True, 
    echo=False
)
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
    temp_engine = create_async_engine(
        base_url, 
        connect_args=connect_args, 
        pool_recycle=300, 
        pool_pre_ping=True, 
        echo=False
    )
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
