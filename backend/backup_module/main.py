import secrets

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, status
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
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



def require_backup_key(x_backup_key: str = Header(default="")):
    """Backups hold a company's full Tally data, so the standalone server only answers callers with the key."""
    if not settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Set BACKUP_API_KEY before using the standalone backup service.",
        )
    if not secrets.compare_digest(x_backup_key.encode(), settings.API_KEY.encode()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or wrong X-Backup-Key header.")


# Include backup router under /backup prefix and at root level
app.include_router(backup_router, prefix="/backup", tags=["Backup & Restore"], dependencies=[Depends(require_backup_key)])
app.include_router(backup_router, tags=["Backup & Restore (Direct)"], dependencies=[Depends(require_backup_key)])

@app.get("/health", tags=["Health"])
def health_check():
    # Public, so it reports no addresses or file paths
    return {
        "status": "online",
        "service": "Tally Backup & Restore Module",
    }

if __name__ == "__main__":
    uvicorn.run(
        "backup_module.main:app",
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        reload=True
    )
