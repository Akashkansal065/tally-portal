import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import text
from app.core.database import engine, Base, AsyncSessionLocal
from app.core.seed import seed_global_data
from app.routers import auth, companies, ledgers, vouchers, voucher_types, currency_tds, payment, inventory, advanced, gst, payment_gateway, sync, admin, visits, expenses, orders, reports, attendance, health, masters, payments

async def db_keep_alive_task(interval_seconds: int = 120):
    """Background task running every 2 minutes to keep the DB connection pool active."""
    print(f"Starting DB Keep-Alive background worker (interval: {interval_seconds}s)...")
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            async with AsyncSessionLocal() as session:
                await session.execute(text("SELECT 1"))
        except asyncio.CancelledError:
            print("DB Keep-Alive background worker stopped.")
            break
        except Exception as e:
            print(f"Warning: DB Keep-Alive ping encountered an error: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Ensure databases exist
    from app.core.database import create_databases_if_not_exist, auto_sync_all_model_schemas
    await create_databases_if_not_exist()
    
    # 2. Create tables if they do not exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    # 3. Dynamically sync all model schemas & missing columns automatically
    await auto_sync_all_model_schemas()
        
    # 3. Seed global default roles, modules, permissions
    async with AsyncSessionLocal() as session:
        roles_count = (await session.execute(text("SELECT COUNT(*) FROM roles"))).scalar()
        if roles_count == 0:
            print("Database empty. Auto-seeding default global metadata...")
            def sync_seed(connection):
                with connection.begin():
                    # We pass the underlying synchronous DBAPI connection wrapper
                    from sqlalchemy.orm import Session
                    sync_db = Session(bind=connection)
                    seed_global_data(sync_db)
            async with engine.connect() as conn:
                # We need to run the sync function in a thread pool since it blocks
                # and SQLAlchemy requires a special wrapper for sync execution
                await conn.run_sync(sync_seed)

    # 4. Start background DB keep-alive worker task (pings every 2 minutes)
    keep_alive_task = asyncio.create_task(db_keep_alive_task(120))
                
    try:
        yield
    finally:
        keep_alive_task.cancel()
        await asyncio.gather(keep_alive_task, return_exceptions=True)

app = FastAPI(title="Open Tally-Clone API", version="1.0.0", lifespan=lifespan)

# Configure CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(companies.router)
app.include_router(ledgers.router)
app.include_router(vouchers.router)
app.include_router(voucher_types.router, prefix="/voucher-type", tags=["Voucher Types"])
app.include_router(voucher_types.router, prefix="/voucher-types", tags=["Voucher Types"])
app.include_router(currency_tds.router)
app.include_router(payment.router)
app.include_router(inventory.router)
app.include_router(advanced.router)
app.include_router(gst.router)
app.include_router(payment_gateway.router)
app.include_router(sync.router)
app.include_router(admin.router)
app.include_router(payments.router)
app.include_router(visits.router)
app.include_router(expenses.router)
app.include_router(orders.router)
app.include_router(reports.router)
app.include_router(attendance.router)
app.include_router(masters.router)

@app.get("/")
def read_root():
    return {"message": "Welcome to Open Tally-Clone API"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host='127.0.0.1', port=8000, reload=True, workers=1)