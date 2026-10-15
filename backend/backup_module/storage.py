import os
import shutil
import zipfile
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional
import json
import stat

from .config import settings

MAX_ARCHIVE_MEMBERS = 10_000
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 20 * 1024 ** 3


class UnsafeArchiveError(ValueError):
    """A zip member would escape the target folder, is a link, or the archive is implausibly large."""


def safe_extract_zip(zip_path: Path, target_dir: Path,
                     max_members: int = MAX_ARCHIVE_MEMBERS,
                     max_total_bytes: int = MAX_ARCHIVE_UNCOMPRESSED_BYTES) -> Path:
    """Extracts member by member. Rejects absolute paths, '..' traversal, drive letters, symlinks, and archives over
    the member or uncompressed-size caps, before anything is written."""
    target_dir.mkdir(parents=True, exist_ok=True)
    root = target_dir.resolve()
    with zipfile.ZipFile(zip_path, "r") as zipf:
        members = zipf.infolist()
        if len(members) > max_members:
            raise UnsafeArchiveError(f"Archive has {len(members)} members (limit {max_members}).")
        if sum(m.file_size for m in members) > max_total_bytes:
            raise UnsafeArchiveError("Archive uncompressed size exceeds the limit.")
        plan = []
        for m in members:
            name = m.filename.replace("\\", "/")
            parts = [p for p in name.split("/") if p not in ("", ".")]
            if name.startswith("/") or ".." in parts or (parts and ":" in parts[0]):
                raise UnsafeArchiveError(f"Unsafe path in archive: {m.filename!r}")
            if stat.S_ISLNK(m.external_attr >> 16):
                raise UnsafeArchiveError(f"Symlink in archive: {m.filename!r}")
            dest = (root.joinpath(*parts)).resolve() if parts else root
            if dest != root and root not in dest.parents:
                raise UnsafeArchiveError(f"Unsafe path in archive: {m.filename!r}")
            plan.append((m, dest))
        written = 0
        for m, dest in plan:
            if m.is_dir() or dest == root:
                dest.mkdir(parents=True, exist_ok=True)
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            with zipf.open(m) as src, open(dest, "wb") as out:
                while True:
                    chunk = src.read(65536)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > max_total_bytes:
                        raise UnsafeArchiveError("Archive uncompressed size exceeds the limit.")
                    out.write(chunk)
    return target_dir


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
        return safe_extract_zip(zip_path, target_dir)

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
