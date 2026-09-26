import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .router import backup_router

app = FastAPI(
    title="Tally Backup & Restore API",
    version="1.0.0",
    description="Dedicated, standalone microservice for Tally Prime XML backups, archives, and restoration."
)

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://tally-portal-one.vercel.app",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include backup router under /backup prefix and at root level
app.include_router(backup_router, prefix="/backup", tags=["Backup & Restore"])
app.include_router(backup_router, tags=["Backup & Restore (Direct)"])

@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "online",
        "service": "Tally Backup & Restore Module",
        "tally_url": settings.TALLY_URL,
        "backup_dir": str(settings.BACKUP_DIR),
        "db_path": str(settings.SQLITE_DB_PATH)
    }

if __name__ == "__main__":
    uvicorn.run(
        "backup_module.main:app",
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        reload=True
    )
