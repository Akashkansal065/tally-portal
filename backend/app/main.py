import asyncio
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import text
from app.core.database import engine, Base, AsyncSessionLocal
from app.core.seed import seed_global_data
from app.routers import auth, companies, ledgers, vouchers, voucher_types, currency_tds, payment, inventory, advanced, gst, payment_gateway, sync, admin, visits, expenses, orders, reports, report_insights, attendance, health, masters, payments, customers, notifications, planner, bank_recon, integrations, reminders, branding, edocs, approvals, greetings, books, backup_schedule, payroll_masters

from app.core.logging_config import setup_logging, get_logger, RequestLoggingMiddleware

setup_logging()
logger = get_logger("app.main")

async def db_keep_alive_task(interval_seconds: int = 60):
    """Periodically ping the database so idle pooled connections stay usable."""
    logger.info(f"Starting DB Keep-Alive background worker (interval: {interval_seconds}s)...")
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            async with AsyncSessionLocal() as session:
                await session.execute(text("SELECT 1"))
        except asyncio.CancelledError:
            logger.info("DB Keep-Alive background worker stopped.")
            break
        except Exception as e:
            logger.warning(f"DB Keep-Alive ping encountered an error: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database schemas, seed defaults, and start background workers."""
    # Database setup is intentionally completed before yielding the app so every
    # request sees the same schema and default permission data.
    from app.core.database import create_databases_if_not_exist, auto_sync_all_model_schemas
    await create_databases_if_not_exist()
    
    # 2. Create tables if they do not exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    # 3. Dynamically sync all model schemas & missing columns automatically
    await auto_sync_all_model_schemas()

    # Indexes added to existing tables after they were created (create_all skips existing tables)
    from app.core.database import ensure_table_indexes
    from app.models import portal_core as portal
    from app.routers import attendance as attendance_models
    for table, index_names in (
        (portal.UserSession.__table__, ["ix_user_sessions_token", "ix_user_sessions_active", "ix_user_sessions_device"]),
        (portal.SyncTrafficLog.__table__, ["ix_sync_traffic_company_status", "ix_sync_traffic_company_created"]),
        (portal.SyncQueue.__table__, ["ix_sync_queue_company_processed"]),
        (portal.DeletedRecordAudit.__table__, ["ix_deleted_audit_company_status"]),
        (portal.Notification.__table__, ["ix_notifications_user_unread"]),
        (portal.CustomerLocationLog.__table__, ["ix_customer_location_logs_latest"]),
        (attendance_models.Attendance.__table__, ["ix_portal_attendance_user_checkin"]),
        (attendance_models.AttendanceLocationLog.__table__, ["ix_attendance_locations_latest"]),
    ):
        await ensure_table_indexes(table, index_names)
        
    # Seed global default roles, modules, and permissions.
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

    # Start background workers only after initialization has succeeded.
    keep_alive_task = asyncio.create_task(db_keep_alive_task(60))

    # 5. Start background Attendance Auto Punch-Out worker task (checks every 60 seconds)
    from app.services.attendance_worker import attendance_auto_checkout_worker
    attendance_worker_task = asyncio.create_task(attendance_auto_checkout_worker(60))

    # 6. Daily purge of old login sessions and old successful sync logs
    from app.services.daily_cleanup import daily_cleanup_worker
    daily_cleanup_task = asyncio.create_task(daily_cleanup_worker())

    # 7. Automatic payment reminders that are due (every 5 minutes, 9 am-8 pm IST)
    from app.services.reminders import reminder_worker
    reminder_task = asyncio.create_task(reminder_worker())

    # 8. Scheduled Tally backups (every 10 minutes it checks whether today's is due)
    from app.services.backup_schedule import backup_worker
    backup_task = asyncio.create_task(backup_worker())
                
    try:
        yield
    finally:
        keep_alive_task.cancel()
        attendance_worker_task.cancel()
        daily_cleanup_task.cancel()
        reminder_task.cancel()
        backup_task.cancel()
        await asyncio.gather(keep_alive_task, attendance_worker_task, daily_cleanup_task, reminder_task, backup_task, return_exceptions=True)

from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from app.core.rate_limiter import limiter, rate_limit_exceeded_handler

app = FastAPI(title="Open Tally-Clone API", version="1.0.0", lifespan=lifespan)

# A write is carried out once, however often it is sent (double click, client retry). Added first so it
# sits closest to the routes and replays a response before compression and CORS headers are applied.
from app.core.idempotency import IdempotencyMiddleware
app.add_middleware(IdempotencyMiddleware)

# Structured Request Logging & Correlation
app.add_middleware(RequestLoggingMiddleware)

# Rate Limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Response compression (skips backup downloads and server-sent events)
from app.core.compression import ApiGZipMiddleware
app.add_middleware(ApiGZipMiddleware)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://tally-portal-one.vercel.app",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|tally-portal-one(-[a-z0-9-]+)?\.vercel\.app)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Lets the browser app read why a session ended (signed out by admin, blocked, ...)
    expose_headers=["X-Auth-Reason"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(companies.router)
app.include_router(ledgers.router)
app.include_router(vouchers.router)
app.include_router(voucher_types.router, prefix="/voucher-type", tags=["Voucher Types"])
app.include_router(voucher_types.router, prefix="/voucher-types", tags=["Voucher Types"])
app.include_router(currency_tds.router)
app.include_router(payroll_masters.router)
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
app.include_router(report_insights.router)
app.include_router(integrations.router)
app.include_router(reminders.router)
app.include_router(branding.router)
app.include_router(edocs.router)
app.include_router(approvals.router)
app.include_router(greetings.router)
app.include_router(books.router)
app.include_router(backup_schedule.router)
app.include_router(attendance.router)
app.include_router(masters.router)
app.include_router(customers.router)
app.include_router(notifications.router)
app.include_router(planner.router)
app.include_router(bank_recon.router)

# Mount isolated Backup & Restore module
try:
    from backup_module.router import backup_router
    from app.routers.admin import require_admin
    # A backup holds a company's full Tally data and a restore writes into Tally, so every route is admin-only
    app.include_router(backup_router, prefix="/backup", tags=["Backup & Restore"], dependencies=[Depends(require_admin)])
except Exception as e:
    import logging
    logging.getLogger("uvicorn.error").warning(f"Could not load backup_module: {e}")

@app.get("/")
def read_root():
    """Return a lightweight liveness response for the API root."""
    return {"message": "Welcome to Open Tally-Clone API"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host='127.0.0.1', port=8000, reload=True, workers=1)