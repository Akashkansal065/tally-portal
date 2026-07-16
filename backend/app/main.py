from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import text
from app.core.database import engine, Base, AsyncSessionLocal
from app.core.seed import seed_global_data
from app.routers import auth, ledgers, vouchers, currency_tds, payment, inventory, advanced, gst, payment_gateway, sync, admin, visits, expenses, orders, reports

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Ensure databases exist
    from app.core.database import create_databases_if_not_exist
    await create_databases_if_not_exist()
    
    # 2. Create tables if they do not exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    # 2. Seed global default roles, modules, permissions
    async with AsyncSessionLocal() as session:
        roles_count = (await session.execute(text("SELECT COUNT(*) FROM roles"))).scalar()
        if roles_count == 0:
            print("Database empty. Auto-seeding default global metadata...")
            def sync_seed(connection):
                from sqlalchemy.orm import Session
                sync_db = Session(bind=connection)
                try:
                    seed_global_data(sync_db)
                finally:
                    sync_db.close()
            
            async with engine.begin() as conn:
                await conn.run_sync(sync_seed)
                
    yield

app = FastAPI(title="Open Tally-Clone API", version="1.0.0", lifespan=lifespan)

# Configure CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(ledgers.router)
app.include_router(vouchers.router)
app.include_router(currency_tds.router)
app.include_router(payment.router)
app.include_router(inventory.router)
app.include_router(advanced.router)
app.include_router(gst.router)
app.include_router(payment_gateway.router)
app.include_router(sync.router)
app.include_router(admin.router)
app.include_router(visits.router)
app.include_router(expenses.router)
app.include_router(orders.router)
app.include_router(reports.router)

@app.get("/")
def read_root():
    return {"message": "Welcome to Open Tally-Clone API"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host='127.0.0.1', port=8000, reload=True, workers=1)