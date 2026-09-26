import logging
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, status
from fastapi.responses import FileResponse

from .config import settings
from .models import (
    CreateBackupRequest,
    RestoreBackupRequest,
    TallyStatusResponse,
    BackupRecordResponse,
    RestoreRecordResponse,
    GenericMessageResponse
)
from .tally_client import tally_client
from .backup_service import backup_service
from .restore_service import restore_service

logger = logging.getLogger("backup_module.router")

# Router can be mounted with prefix="/backup" in existing app, or standalone
backup_router = APIRouter()

@backup_router.get("/tally/status", response_model=TallyStatusResponse)
def get_tally_status():
    """Checks Tally Prime XML server connectivity and lists open companies."""
    is_connected, msg, companies = tally_client.check_health()
    return TallyStatusResponse(
        connected=is_connected,
        tally_url=settings.TALLY_URL,
        message=msg,
        companies=companies
    )

@backup_router.get("/tally/companies")
def get_tally_companies():
    """Lists all open companies in Tally Prime."""
    is_connected, msg, companies = tally_client.check_health()
    if not is_connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cannot connect to Tally Prime at {settings.TALLY_URL}: {msg}"
        )
    return {"companies": companies}

@backup_router.post("/create", response_model=GenericMessageResponse)
def create_backup(payload: CreateBackupRequest):
    """Initiates an asynchronous XML export backup of the specified company."""
    if not payload.company_name or not payload.company_name.strip():
        raise HTTPException(status_code=400, detail="Company name is required")

    try:
        backup_id = backup_service.start_backup(
            company_name=payload.company_name.strip(),
            notes=payload.notes
        )
        return GenericMessageResponse(
            success=True,
            message="Backup task initiated successfully",
            data={"backup_id": backup_id}
        )
    except Exception as e:
        logger.error(f"Error initiating backup: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@backup_router.get("/list", response_model=List[BackupRecordResponse])
def list_backups():
    """Retrieves all historical backup records."""
    return backup_service.list_all_backups()

@backup_router.get("/{backup_id}/status", response_model=BackupRecordResponse)
def get_backup_status(backup_id: str):
    """Retrieves the real-time progress and details of a specific backup."""
    record = backup_service.get_backup_record(backup_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Backup with ID {backup_id} not found")
    return record

@backup_router.get("/{backup_id}/download")
def download_backup_file(backup_id: str):
    """Downloads the compressed backup ZIP file."""
    record = backup_service.get_backup_record(backup_id)
    if not record:
        raise HTTPException(status_code=404, detail="Backup record not found")
    
    file_path = Path(record["file_path"])
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Backup file not found on disk")

    return FileResponse(
        path=str(file_path),
        filename=record["file_name"],
        media_type="application/zip"
    )

@backup_router.delete("/{backup_id}", response_model=GenericMessageResponse)
def delete_backup(backup_id: str):
    """Deletes a backup archive and its corresponding database records."""
    success = backup_service.delete_backup(backup_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Backup with ID {backup_id} not found")
    return GenericMessageResponse(success=True, message=f"Backup {backup_id} deleted successfully")

@backup_router.post("/restore", response_model=GenericMessageResponse)
def restore_backup(payload: RestoreBackupRequest):
    """Initiates an asynchronous restore of an existing backup into Tally Prime."""
    try:
        restore_id = restore_service.start_restore(
            backup_id=payload.backup_id,
            target_company_name=payload.company_name
        )
        return GenericMessageResponse(
            success=True,
            message="Restore task initiated successfully",
            data={"restore_id": restore_id}
        )
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Error initiating restore: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@backup_router.get("/restore/{restore_id}/status", response_model=RestoreRecordResponse)
def get_restore_status(restore_id: str):
    """Retrieves progress and results of a restore operation."""
    record = restore_service.get_restore_record(restore_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Restore operation {restore_id} not found")
    return record

@backup_router.get("/restore/logs", response_model=List[RestoreRecordResponse])
def list_restore_logs(backup_id: Optional[str] = None):
    """Retrieves history of restore operations."""
    return restore_service.list_restore_logs(backup_id)
