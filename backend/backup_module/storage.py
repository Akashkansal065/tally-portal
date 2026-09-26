import os
import shutil
import zipfile
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional
import json

from .config import settings

class LocalBackupStorage:
    """Manages creation, extraction, hashing, and deletion of backup archive files."""

    def __init__(self, backup_dir: Optional[Path] = None):
        self.backup_dir = backup_dir or settings.BACKUP_DIR
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def get_backup_path(self, file_name: str) -> Path:
        return self.backup_dir / file_name

    def calculate_sha256(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of a file."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def create_zip(self, source_dir: Path, output_zip_path: Path) -> tuple[int, str]:
        """
        Zips all files in source_dir into output_zip_path.
        Returns (file_size_bytes, sha256_checksum).
        """
        output_zip_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output_zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(source_dir):
                for file in files:
                    file_p = Path(root) / file
                    arcname = file_p.relative_to(source_dir)
                    zipf.write(file_p, arcname)
        
        file_size = output_zip_path.stat().st_size
        checksum = self.calculate_sha256(output_zip_path)
        return file_size, checksum

    def extract_zip(self, zip_path: Path, target_dir: Path) -> Path:
        """Extracts a backup zip into target_dir."""
        target_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            zipf.extractall(target_dir)
        return target_dir

    def delete_backup_file(self, file_name: str) -> bool:
        """Deletes a backup zip file from disk."""
        target = self.backup_dir / file_name
        if target.exists() and target.is_file():
            try:
                target.unlink()
                return True
            except Exception:
                return False
        return False

    def clean_staging_dir(self, staging_dir: Path):
        """Cleans up a temporary staging directory."""
        if staging_dir.exists() and staging_dir.is_dir():
            try:
                shutil.rmtree(staging_dir)
            except Exception:
                pass

storage = LocalBackupStorage()
