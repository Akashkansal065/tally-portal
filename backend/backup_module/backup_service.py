import os
import json
import uuid
import datetime
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import threading

from .config import settings
from .database import get_db
from .storage import storage
from .tally_client import tally_client

logger = logging.getLogger("backup_module.backup_service")

ENTITY_EXPORT_ORDER = [
    ("groups", "Masters / Groups"),
    ("ledgers", "Masters / Ledgers"),
    ("cost_categories", "Masters / Cost Categories"),
    ("cost_centres", "Masters / Cost Centres"),
    ("units", "Masters / Units"),
    ("stock_groups", "Masters / Stock Groups"),
    ("stock_categories", "Masters / Stock Categories"),
    ("godowns", "Masters / Godowns"),
    ("stock_items", "Masters / Stock Items"),
    ("voucher_types", "Masters / Voucher Types"),
    ("vouchers", "Transactions / Vouchers")
]

class BackupService:
    """Orchestrates full XML backups of Tally companies into compressed ZIP archives."""

    def __init__(self):
        self._running_tasks: Dict[str, threading.Thread] = {}

    def get_backup_record(self, backup_id: str) -> Optional[Dict[str, Any]]:
        with get_db() as conn:
            cur = conn.execute("SELECT * FROM backups WHERE id = ?", (backup_id,))
            row = cur.fetchone()
            if not row:
                return None
            res = dict(row)
            try:
                res["record_counts"] = json.loads(res.get("record_counts") or "{}")
            except Exception:
                res["record_counts"] = {}
            return res

    def list_all_backups(self) -> List[Dict[str, Any]]:
        with get_db() as conn:
            cur = conn.execute("SELECT * FROM backups ORDER BY created_at DESC")
            rows = cur.fetchall()
            result = []
            for r in rows:
                item = dict(r)
                try:
                    item["record_counts"] = json.loads(item.get("record_counts") or "{}")
                except Exception:
                    item["record_counts"] = {}
                result.append(item)
            return result

    def delete_backup(self, backup_id: str) -> bool:
        record = self.get_backup_record(backup_id)
        if not record:
            return False
        
        # Remove file from disk
        file_name = record.get("file_name")
        if file_name:
            storage.delete_backup_file(file_name)

        # Delete database records
        with get_db() as conn:
            conn.execute("DELETE FROM restore_logs WHERE backup_id = ?", (backup_id,))
            conn.execute("DELETE FROM backups WHERE id = ?", (backup_id,))
        return True

    def _update_backup_progress(
        self,
        backup_id: str,
        progress_percent: int,
        progress_message: str,
        status: Optional[str] = None
    ):
        with get_db() as conn:
            if status:
                conn.execute(
                    "UPDATE backups SET progress_percent = ?, progress_message = ?, status = ? WHERE id = ?",
                    (progress_percent, progress_message, status, backup_id)
                )
            else:
                conn.execute(
                    "UPDATE backups SET progress_percent = ?, progress_message = ? WHERE id = ?",
                    (progress_percent, progress_message, backup_id)
                )

    def _execute_backup_thread(self, backup_id: str, company_name: str, notes: Optional[str] = None):
        """Worker thread executing the full XML export and packaging."""
        staging_dir = settings.BACKUP_DIR / f".staging_{backup_id}"
        zip_file_name = f"{backup_id}.zip"
        zip_path = settings.BACKUP_DIR / zip_file_name

        try:
            self._update_backup_progress(backup_id, 5, "Connecting to Tally Prime...", "running")
            staging_dir.mkdir(parents=True, exist_ok=True)

            # 1. Fetch Company profile first
            is_connected, health_msg, companies = tally_client.check_health()
            if not is_connected:
                raise RuntimeError(f"Tally Prime is not reachable: {health_msg}")

            # Verify target company exists or matches
            found_company = next((c for c in companies if c["name"].lower() == company_name.lower()), None)
            company_profile = found_company or {"name": company_name}

            # Save company metadata
            with open(staging_dir / "company.json", "w", encoding="utf-8") as f:
                json.dump(company_profile, f, indent=2, ensure_ascii=False)

            record_counts = {}
            total_masters = 0
            total_vouchers = 0

            # 2. Export each entity
            total_steps = len(ENTITY_EXPORT_ORDER)
            for idx, (entity_key, entity_label) in enumerate(ENTITY_EXPORT_ORDER):
                current_percent = 10 + int((idx / total_steps) * 80)
                self._update_backup_progress(
                    backup_id,
                    current_percent,
                    f"Exporting {entity_label}..."
                )

                success, xml_data, count = tally_client.export_entity(entity_key, company_name)
                if not success:
                    logger.warning(f"Failed exporting {entity_key}: {xml_data}")
                    # Write whatever we received or empty XML
                    xml_data = f"<!-- Export failed: {xml_data} -->"
                    count = 0

                # Write XML file
                file_target = staging_dir / f"{entity_key}.xml"
                with open(file_target, "w", encoding="utf-8") as f:
                    f.write(xml_data)

                record_counts[entity_key] = count
                if entity_key == "vouchers":
                    total_vouchers += count
                else:
                    total_masters += count

            # 3. Create manifest.json
            self._update_backup_progress(backup_id, 92, "Creating backup manifest...")
            manifest = {
                "backup_id": backup_id,
                "company_name": company_name,
                "company_profile": company_profile,
                "version": "1.0.0",
                "created_at": datetime.datetime.now().isoformat(),
                "notes": notes or "",
                "total_masters": total_masters,
                "total_vouchers": total_vouchers,
                "entities": record_counts
            }
            with open(staging_dir / "manifest.json", "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2, ensure_ascii=False)

            # 4. Zip the entire bundle
            self._update_backup_progress(backup_id, 96, "Compressing archive (.zip)...")
            file_size_bytes, sha256_checksum = storage.create_zip(staging_dir, zip_path)

            # 5. Clean staging directory
            storage.clean_staging_dir(staging_dir)

            # 6. Finalize in database
            completed_time = datetime.datetime.now().isoformat()
            with get_db() as conn:
                conn.execute("""
                    UPDATE backups 
                    SET file_size_bytes = ?,
                        record_counts = ?,
                        total_masters = ?,
                        total_vouchers = ?,
                        status = 'completed',
                        progress_percent = 100,
                        progress_message = 'Backup completed successfully',
                        checksum_sha256 = ?,
                        completed_at = ?
                    WHERE id = ?
                """, (
                    file_size_bytes,
                    json.dumps(record_counts),
                    total_masters,
                    total_vouchers,
                    sha256_checksum,
                    completed_time,
                    backup_id
                ))

            logger.info(f"✅ Backup {backup_id} completed successfully for '{company_name}' ({file_size_bytes} bytes)")

        except Exception as e:
            logger.error(f"❌ Backup {backup_id} failed: {e}", exc_info=True)
            storage.clean_staging_dir(staging_dir)
            with get_db() as conn:
                conn.execute("""
                    UPDATE backups 
                    SET status = 'failed',
                        progress_message = 'Backup failed',
                        error_message = ?
                    WHERE id = ?
                """, (str(e), backup_id))
        finally:
            self._running_tasks.pop(backup_id, None)

    def start_backup(self, company_name: str, notes: Optional[str] = None) -> str:
        """
        Initiates a new company backup asynchronously.
        Returns the generated backup_id immediately.
        """
        now = datetime.datetime.now()
        timestamp_str = now.strftime("%Y%m%d-%H%M%S")
        short_hash = uuid.uuid4().hex[:6]
        backup_id = f"BKP-{timestamp_str}-{short_hash}"
        file_name = f"{backup_id}.zip"
        file_path = str(settings.BACKUP_DIR / file_name)
        created_at = now.isoformat()

        # Insert initial record into SQLite
        with get_db() as conn:
            conn.execute("""
                INSERT INTO backups (
                    id, company_name, file_name, file_path, status,
                    progress_percent, progress_message, created_at
                ) VALUES (?, ?, ?, ?, 'pending', 0, 'Initializing backup...', ?)
            """, (backup_id, company_name, file_name, file_path, created_at))

        # Launch background worker
        worker = threading.Thread(
            target=self._execute_backup_thread,
            args=(backup_id, company_name, notes),
            daemon=True
        )
        self._running_tasks[backup_id] = worker
        worker.start()

        return backup_id

backup_service = BackupService()
