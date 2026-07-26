"""
Health Check Router — Database connectivity status & system diagnostics.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import datetime

from app.core.database import get_db, engine

router = APIRouter(tags=["Health & System"])

@router.get("/health")
async def health_check():
    """Simple API health check endpoint."""
    return {
        "status": "healthy",
        "service": "Open Tally-Clone API",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

@router.get("/health/db")
async def db_health_check(db: AsyncSession = Depends(get_db)):
    """Database connectivity health check endpoint."""
    try:
        start_time = datetime.utcnow()
        result = await db.execute(text("SELECT 1"))
        val = result.scalar()
        latency_ms = round((datetime.utcnow() - start_time).total_seconds() * 1000, 2)
        
        if val == 1:
            return {
                "status": "healthy",
                "database": "connected",
                "latency_ms": latency_ms,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unexpected result from database ping"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connection error: {str(e)}"
        )
