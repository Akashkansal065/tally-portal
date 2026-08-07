import ssl
import os
from sqlalchemy import text
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

async def auto_sync_all_model_schemas():
    """
    Dynamically inspects ALL SQLAlchemy models in Base.metadata.tables on startup.
    Automatically detects any columns defined in Python code that are missing in the target database,
    and executes ALTER TABLE ADD COLUMN statements to keep any database schema 100% in sync automatically.
    """
    from sqlalchemy import text
    
    db_url = settings.DATABASE_URL
    if "sqlite" in db_url:
        return

    # Import all models to ensure they register their tables and columns in Base.metadata
    import app.models.company
    import app.models.user
    import app.models.ledger
    import app.models.voucher
    import app.models.sync
    import app.models.inventory
    import app.models.gst
    import app.models.advanced
    import app.models.currency_tds
    import app.models.payment
    import app.models.payment_gateway
    
    async with engine.begin() as conn:
        for table_key, table in Base.metadata.tables.items():
            schema_name = table.schema or settings.PORTAL_DATABASE_NAME
            table_name = table.name
            
            # Check if table exists in MySQL
            check_table_sql = text(f"""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_SCHEMA = '{schema_name}' AND TABLE_NAME = '{table_name}'
            """)
            try:
                table_exists_res = await conn.execute(check_table_sql)
                if table_exists_res.scalar() == 0:
                    continue
                    
                # Fetch existing columns and their max length from MySQL
                cols_query = text(f"""
                    SELECT COLUMN_NAME, CHARACTER_MAXIMUM_LENGTH FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_SCHEMA = '{schema_name}' AND TABLE_NAME = '{table_name}'
                """)
                existing_cols_res = await conn.execute(cols_query)
                existing_cols_map = {row[0].lower(): row[1] for row in existing_cols_res.fetchall()}
                
                # Compare with columns defined on SQLAlchemy Table model in Python code
                for column in table.columns:
                    col_name = column.name
                    col_name_lower = col_name.lower()
                    col_type_str = column.type.compile(engine.dialect)

                    if col_name_lower not in existing_cols_map:
                        # Column missing in DB -> Add it dynamically!
                        nullable_str = "NULL"
                        default_clause = ""
                        if column.default is not None and hasattr(column.default, 'arg') and isinstance(column.default.arg, (str, int, float, bool)):
                            val = column.default.arg
                            if isinstance(val, bool):
                                val = 1 if val else 0
                            default_clause = f" DEFAULT '{val}'" if isinstance(val, str) else f" DEFAULT {val}"

                        print(f"Auto Schema Synchronizer: Adding missing column '{col_name}' ({col_type_str}) to `{schema_name}`.`{table_name}`...")
                        alter_sql = text(f"ALTER TABLE `{schema_name}`.`{table_name}` ADD COLUMN `{col_name}` {col_type_str} {nullable_str}{default_clause}")
                        await conn.execute(alter_sql)
                    else:
                        # Column exists -> Check if Python model requires larger length (e.g. VARCHAR(10) -> VARCHAR(100))
                        db_len = existing_cols_map[col_name_lower]
                        target_len = getattr(column.type, 'length', None)
                        if db_len is not None and target_len is not None and int(db_len) < int(target_len):
                            print(f"Auto Schema Synchronizer: Expanding column '{col_name}' ({db_len} -> {target_len}) in `{schema_name}`.`{table_name}`...")
                            alter_sql = text(f"ALTER TABLE `{schema_name}`.`{table_name}` MODIFY COLUMN `{col_name}` {col_type_str}")
                            await conn.execute(alter_sql)
            except Exception as e:
                print(f"Warning during auto schema sync for `{schema_name}`.`{table_name}`: {e}")

        await seed_gst_registration_types(conn)

async def seed_gst_registration_types(conn):
    try:
        check_sql = text(f"SELECT COUNT(*) FROM `{settings.PORTAL_DATABASE_NAME}`.`gst_registration_types`")
        res = await conn.execute(check_sql)
        count = res.scalar()
        if count == 0:
            print("Auto Schema Synchronizer: Seeding GST registration types master data...")
            default_types = [
                ("Regular", "REGULAR", 1, 1),
                ("Composition", "COMPOSITION", 1, 2),
                ("Unregistered/Consumer", "UNREGISTERED", 0, 3),
                ("Government entity / TDS", "GOVT_TDS", 1, 4),
                ("Regular - SEZ", "SEZ", 1, 5),
                ("Regular-Deemed Exporter", "DEEMED_EXPORTER", 1, 6),
                ("Regular-Exports (EOU)", "EOU", 1, 7),
                ("e-Commerce Operator", "ECOMMERCE", 1, 8),
                ("Input Service Distributor", "ISD", 1, 9),
                ("Embassy/UN Body", "EMBASSY", 1, 10),
                ("Non-Resident Taxpayer", "NON_RESIDENT", 1, 11),
                ("Unknown", "UNKNOWN", 0, 12),
            ]
            for name, code, req_gst, order in default_types:
                insert_sql = text(f"""
                    INSERT INTO `{settings.PORTAL_DATABASE_NAME}`.`gst_registration_types`
                    (name, code, requires_gstin, display_order, is_active)
                    VALUES (:name, :code, :req_gst, :order, 1)
                """)
                await conn.execute(insert_sql, {"name": name, "code": code, "req_gst": req_gst, "order": order})
    except Exception as e:
        print(f"Warning seeding GST registration types: {e}")

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
