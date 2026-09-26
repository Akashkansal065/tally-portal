from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

class CreateBackupRequest(BaseModel):
    company_name: str = Field(..., description="Name of the open company in Tally to backup")
    notes: Optional[str] = Field(None, description="Optional notes or tag for the backup")

class RestoreBackupRequest(BaseModel):
    backup_id: str = Field(..., description="Unique ID of the backup archive to restore")
    company_name: Optional[str] = Field(None, description="Target company name in Tally (defaults to company in backup)")

class TallyStatusResponse(BaseModel):
    connected: bool
    tally_url: str
    message: str
    companies: List[Dict[str, Any]] = []

class BackupRecordResponse(BaseModel):
    id: str
    company_name: str
    file_name: str
    file_size_bytes: int
    record_counts: Dict[str, int] = {}
    total_masters: int = 0
    total_vouchers: int = 0
    status: str
    progress_percent: int = 0
    progress_message: str = ""
    error_message: str = ""
    checksum_sha256: str = ""
    created_at: str
    completed_at: Optional[str] = None

class RestoreRecordResponse(BaseModel):
    id: str
    backup_id: str
    company_name: str
    target_company_name: str
    status: str
    progress_percent: int = 0
    progress_message: str = ""
    summary: Dict[str, Any] = {}
    error_message: str = ""
    started_at: str
    completed_at: Optional[str] = None

class GenericMessageResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
