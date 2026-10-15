import re
import ssl
import os
from sqlalchemy import bindparam, event, text
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

# Enforce Indian Standard Time (IST / UTC+05:30) on all MySQL sessions
connect_args["init_command"] = "SET time_zone = '+05:30'"
connect_args["connect_timeout"] = 15

engine = create_async_engine(
    settings.DATABASE_URL, 
    connect_args=connect_args, 
    pool_size=10,
    max_overflow=20,
    pool_recycle=300, 
    pool_pre_ping=True, 
    echo=False
)
# About a hundred hand-written report and ledger queries name the Tally database as "tally_sync". On a server
# whose TALLY_DATABASE_NAME is something else they would fail, so the name is swapped for the configured one
# as each statement goes out. With the usual name nothing is registered and no statement is touched.
_WRITTEN_TALLY_DATABASE = re.compile(r"(?<![\w`.])tally_sync\.")


def use_configured_tally_database(statement: str, name: str = settings.TALLY_DATABASE_NAME) -> str:
    """The statement with the written-in Tally database name replaced by the configured one."""
    return _WRITTEN_TALLY_DATABASE.sub(f"{name}.", statement)


if settings.TALLY_DATABASE_NAME != "tally_sync":
    @event.listens_for(engine.sync_engine, "before_cursor_execute", retval=True)
    def _swap_tally_database_name(conn, cursor, statement, parameters, context, executemany):
        return use_configured_tally_database(statement), parameters


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

def _model_schemas() -> list:
    return sorted({table.schema or settings.PORTAL_DATABASE_NAME for table in Base.metadata.tables.values()})


async def _existing_columns(conn) -> dict:
    """{(schema, table): {column: (max length, data type)}} for every table the models live in, lower-cased, in
    one query."""
    rows = await conn.execute(
        text("SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, CHARACTER_MAXIMUM_LENGTH, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS "
             "WHERE TABLE_SCHEMA IN :schemas").bindparams(bindparam("schemas", expanding=True)),
        {"schemas": _model_schemas()},
    )
    found: dict = {}
    for schema, table, column, length, data_type in rows.fetchall():
        found.setdefault((schema.lower(), table.lower()), {})[column.lower()] = (length, (data_type or "").lower())
    return found


async def create_missing_tables(conn) -> None:
    """Create the model tables the database does not have yet. One query says which exist; create_all on its
    own asks for every one of the 189 tables in turn, a round trip each."""
    if "sqlite" in settings.DATABASE_URL:
        await conn.run_sync(Base.metadata.create_all)
        return
    rows = await conn.execute(
        text("SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA IN :schemas")
        .bindparams(bindparam("schemas", expanding=True)),
        {"schemas": _model_schemas()},
    )
    existing = {(schema.lower(), table.lower()) for schema, table in rows.fetchall()}
    missing = [table for table in Base.metadata.sorted_tables
               if ((table.schema or settings.PORTAL_DATABASE_NAME).lower(), table.name.lower()) not in existing]
    if missing:
        await conn.run_sync(Base.metadata.create_all, tables=missing)


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
    import app.models.tally_core
    import app.models.portal_core
    import app.models.billing      # billing tables (plans, orders, subscriptions, invoices …)
    import app.models.platform     # platform operator console tables (admins, roles, sessions …)
    import app.routers.orders
    import app.routers.attendance
    
    async with engine.begin() as conn:
        # The whole schema in one query: asking table by table cost two round trips per table (189 tables,
        # about 15 s against a remote database)
        existing_schema = await _existing_columns(conn)
        for table_key, table in Base.metadata.tables.items():
            schema_name = table.schema or settings.PORTAL_DATABASE_NAME
            table_name = table.name

            try:
                existing_cols_map = existing_schema.get((schema_name.lower(), table_name.lower()))
                if existing_cols_map is None:
                    continue

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
                        db_len, db_type = existing_cols_map[col_name_lower]
                        target_len = getattr(column.type, 'length', None)
                        if column.type.__visit_name__.lower() in ("text", "unicode_text") and db_type in ("char", "varchar", "tinytext"):
                            # The model holds free text (an address, say) that the database still caps: widen to TEXT
                            print(f"Auto Schema Synchronizer: Widening column '{col_name}' ({db_type} -> {col_type_str}) in `{schema_name}`.`{table_name}`...")
                            alter_sql = text(f"ALTER TABLE `{schema_name}`.`{table_name}` MODIFY COLUMN `{col_name}` {col_type_str} NULL")
                            await conn.execute(alter_sql)
                        # Column exists -> Check if Python model requires larger length (e.g. VARCHAR(10) -> VARCHAR(100))
                        elif db_len is not None and target_len is not None and int(db_len) < int(target_len):
                            print(f"Auto Schema Synchronizer: Expanding column '{col_name}' ({db_len} -> {target_len}) in `{schema_name}`.`{table_name}`...")
                            alter_sql = text(f"ALTER TABLE `{schema_name}`.`{table_name}` MODIFY COLUMN `{col_name}` {col_type_str}")
                            await conn.execute(alter_sql)
            except Exception as e:
                print(f"Warning during auto schema sync for `{schema_name}`.`{table_name}`: {e}")

        await seed_gst_registration_types(conn)

async def ensure_indexes(specs) -> None:
    """Create the listed indexes declared on the models' tables if the database doesn't have them yet.
    `specs` is a list of (table, index names). Base.metadata.create_all only creates indexes for brand-new
    tables, and the column sync above doesn't touch indexes, so tables that gain an index later need this.
    Only the named indexes are considered, so an index=True added to an old column never starts an
    unplanned build on a large table. Which indexes exist is read in one query for every table."""
    if "sqlite" in settings.DATABASE_URL:
        return
    for table, names in specs:
        unknown = set(names) - {index.name for index in table.indexes}
        if unknown:
            raise ValueError(f"{table.name} declares no index named {sorted(unknown)}")
    schemas = sorted({table.schema or settings.PORTAL_DATABASE_NAME for table, _ in specs})
    async with engine.begin() as conn:
        rows = (await conn.execute(
            text("SELECT DISTINCT TABLE_SCHEMA, TABLE_NAME, INDEX_NAME FROM INFORMATION_SCHEMA.STATISTICS "
                 "WHERE TABLE_SCHEMA IN :schemas").bindparams(bindparam("schemas", expanding=True)),
            {"schemas": schemas},
        )).fetchall()
        existing = {(schema.lower(), table.lower(), index.lower()) for schema, table, index in rows}
        for table, names in specs:
            schema_name = table.schema or settings.PORTAL_DATABASE_NAME
            for index in table.indexes:
                if index.name in names and (schema_name.lower(), table.name.lower(), index.name.lower()) not in existing:
                    columns = ", ".join(f"`{col.name}`" for col in index.columns)
                    print(f"Auto Schema Synchronizer: Creating index {index.name} on `{schema_name}`.`{table.name}` ({columns})...")
                    await conn.execute(text(f"CREATE INDEX `{index.name}` ON `{schema_name}`.`{table.name}` ({columns})"))


async def ensure_table_indexes(table, names) -> None:
    """ensure_indexes for one table."""
    await ensure_indexes([(table, names)])


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
