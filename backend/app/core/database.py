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
    from sqlalchemy.exc import OperationalError, InternalError
    
    db_url = settings.DATABASE_URL
    if "sqlite" in db_url:
        return
        
    base_url, portal_db = db_url.rsplit('/', 1)
    if '?' in portal_db:
        portal_db = portal_db.split('?')[0]
    tally_db = settings.TALLY_DATABASE_NAME
    
    # 1. Check if the main portal database exists by trying to connect directly
    portal_exists = False
    try:
        test_engine = create_async_engine(
            db_url,
            connect_args=connect_args,
            pool_recycle=300,
            pool_pre_ping=True,
            echo=False
        )
        async with test_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            portal_exists = True
        await test_engine.dispose()
    except (OperationalError, InternalError) as e:
        err_msg = str(e).lower()
        is_missing_db = any(x in err_msg for x in ["unknown database", "does not exist", "database no exist", "1049", "3d000"])
        if not is_missing_db:
            # If it's a connection refused, password error, etc., propagate the error
            raise e

    # 2. Check if the tally_sync database exists by trying to connect directly
    sync_exists = False
    try:
        sync_db_url = f"{base_url}/{tally_db}"
        test_sync_engine = create_async_engine(
            sync_db_url,
            connect_args=connect_args,
            pool_recycle=300,
            pool_pre_ping=True,
            echo=False
        )
        async with test_sync_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            sync_exists = True
        await test_sync_engine.dispose()
    except (OperationalError, InternalError) as e:
        err_msg = str(e).lower()
        is_missing_db = any(x in err_msg for x in ["unknown database", "does not exist", "database no exist", "1049", "3d000"])
        if not is_missing_db:
            raise e

    # 3. If either database does not exist, try to connect to the server and create them
    if not portal_exists or not sync_exists:
        creation_base_url = base_url
        # In PostgreSQL, we cannot connect to the server without a database name.
        # "postgres" is a default database that is always present.
        if "postgresql" in db_url:
            creation_base_url = f"{base_url}/postgres"
            
        print(f"Database setup required: portal_db_exists={portal_exists}, sync_db_exists={sync_exists}")
        temp_engine = create_async_engine(
            creation_base_url, 
            connect_args=connect_args, 
            pool_recycle=300, 
            pool_pre_ping=True, 
            echo=False
        ).execution_options(isolation_level="AUTOCOMMIT")
        
        try:
            async with temp_engine.connect() as conn:
                if not portal_exists:
                    # Use CREATE DATABASE IF NOT EXISTS for databases that support it (like MySQL)
                    # For databases that don't, run a standard CREATE DATABASE (the check above protects us)
                    if "mysql" in db_url:
                        await conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {portal_db}"))
                    else:
                        await conn.execute(text(f"CREATE DATABASE {portal_db}"))
                    print(f"Successfully created database: {portal_db}")
                if not sync_exists:
                    if "mysql" in db_url:
                        await conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {tally_db}"))
                    else:
                        await conn.execute(text(f"CREATE DATABASE {tally_db}"))
                    print(f"Successfully created database: {tally_db}")
        except Exception as create_err:
            print(f"Warning: Could not automatically create missing databases: {create_err}")
            print("The application will attempt to proceed, but may fail if the databases do not exist.")
            # If the databases actually don't exist and creation failed, let the app start attempt
            # to connect anyway, which will raise the final connection error to the user if it still fails.
        finally:
            await temp_engine.dispose()

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
