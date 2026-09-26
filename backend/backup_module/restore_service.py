import os
import json
import uuid
import datetime
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import xml.etree.ElementTree as ET
import threading

from .config import settings
from .database import get_db
from .storage import storage
from .tally_client import tally_client

logger = logging.getLogger("backup_module.restore_service")

# Strict dependency order for importing into Tally Prime
ENTITY_IMPORT_ORDER = [
    ("groups", "Groups", "All Masters"),
    ("ledgers", "Ledgers", "All Masters"),
    ("cost_categories", "Cost Categories", "All Masters"),
    ("cost_centres", "Cost Centres", "All Masters"),
    ("units", "Units of Measure", "All Masters"),
    ("stock_groups", "Stock Groups", "All Masters"),
    ("stock_categories", "Stock Categories", "All Masters"),
    ("godowns", "Godowns", "All Masters"),
    ("stock_items", "Stock Items", "All Masters"),
    ("voucher_types", "Voucher Types", "All Masters"),
    ("vouchers", "Vouchers", "Vouchers")
]

BATCH_SIZE = 50

class RestoreService:
    """Orchestrates restoring Tally company data from ZIP backup archives."""

    def __init__(self):
        self._running_tasks: Dict[str, threading.Thread] = {}

    def get_restore_record(self, restore_id: str) -> Optional[Dict[str, Any]]:
        with get_db() as conn:
            cur = conn.execute("SELECT * FROM restore_logs WHERE id = ?", (restore_id,))
            row = cur.fetchone()
            if not row:
                return None
            res = dict(row)
            try:
                res["summary"] = json.loads(res.get("summary") or "{}")
            except Exception:
                res["summary"] = {}
            return res

    def list_restore_logs(self, backup_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with get_db() as conn:
            if backup_id:
                cur = conn.execute(
                    "SELECT * FROM restore_logs WHERE backup_id = ? ORDER BY started_at DESC",
                    (backup_id,)
                )
            else:
                cur = conn.execute("SELECT * FROM restore_logs ORDER BY started_at DESC")
            rows = cur.fetchall()
            result = []
            for r in rows:
                item = dict(r)
                try:
                    item["summary"] = json.loads(item.get("summary") or "{}")
                except Exception:
                    item["summary"] = {}
                result.append(item)
            return result

    def _update_restore_progress(
        self,
        restore_id: str,
        progress_percent: int,
        progress_message: str,
        status: Optional[str] = None
    ):
        with get_db() as conn:
            if status:
                conn.execute(
                    "UPDATE restore_logs SET progress_percent = ?, progress_message = ?, status = ? WHERE id = ?",
                    (progress_percent, progress_message, status, restore_id)
                )
            else:
                conn.execute(
                    "UPDATE restore_logs SET progress_percent = ?, progress_message = ? WHERE id = ?",
                    (progress_percent, progress_message, restore_id)
                )

    def _prepare_nodes_with_alter_action(self, xml_content: str) -> List[str]:
        """
        Extracts master/voucher nodes from the exported XML and ensures ACTION="Alter"
        attribute is present on each entity node for update-existing mode.
        """
        extracted_nodes = []
        try:
            root = ET.fromstring(xml_content)
            # Find all TALLYMESSAGE children or direct body elements
            messages = root.findall(".//TALLYMESSAGE")
            if messages:
                for msg in messages:
                    for child in list(msg):
                        child.set("ACTION", "Alter")
                        extracted_nodes.append(ET.tostring(child, encoding="utf-8").decode("utf-8"))
            else:
                body = root.find(".//BODY")
                if body is not None:
                    data = body.find(".//DATA") or body.find(".//IMPORTDATA")
                    if data is not None:
                        for child in list(data):
                            child.set("ACTION", "Alter")
                            extracted_nodes.append(ET.tostring(child, encoding="utf-8").decode("utf-8"))
        except Exception as e:
            logger.warning(f"Error parsing entity XML for Alter action injection: {e}")
        
        return extracted_nodes

    def _execute_restore_thread(
        self,
        restore_id: str,
        backup_id: str,
        target_company_name: str
    ):
        """Worker thread executing the step-by-step restoration into Tally Prime."""
        staging_dir = settings.BACKUP_DIR / f".staging_restore_{restore_id}"
        summary_stats: Dict[str, Dict[str, int]] = {}

        try:
            self._update_restore_progress(restore_id, 5, "Extracting backup archive...", "running")
            
            # 1. Fetch backup record
            with get_db() as conn:
                cur = conn.execute("SELECT * FROM backups WHERE id = ?", (backup_id,))
                backup_row = cur.fetchone()
                if not backup_row:
                    raise ValueError(f"Backup archive {backup_id} not found in database")
                backup_record = dict(backup_row)

            zip_path = Path(backup_record["file_path"])
            if not zip_path.exists():
                raise FileNotFoundError(f"Backup ZIP file not found on disk: {zip_path}")

            # 2. Extract archive
            storage.extract_zip(zip_path, staging_dir)
            
            # Read manifest
            manifest_file = staging_dir / "manifest.json"
            if manifest_file.exists():
                with open(manifest_file, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                    orig_company = manifest.get("company_name", "")
            else:
                orig_company = backup_record.get("company_name", "")

            # If user didn't specify target company, use original
            final_company = target_company_name or orig_company

            # 3. Check Tally connectivity
            self._update_restore_progress(restore_id, 10, f"Connecting to Tally for company '{final_company}'...")
            is_connected, health_msg, companies = tally_client.check_health()
            if not is_connected:
                raise RuntimeError(f"Tally Prime is not reachable: {health_msg}")

            # 4. Import entities in dependency order
            total_steps = len(ENTITY_IMPORT_ORDER)
            for idx, (entity_key, entity_label, report_name) in enumerate(ENTITY_IMPORT_ORDER):
                current_percent = 15 + int((idx / total_steps) * 80)
                self._update_restore_progress(
                    restore_id,
                    current_percent,
                    f"Restoring {entity_label}..."
                )

                xml_file = staging_dir / f"{entity_key}.xml"
                if not xml_file.exists():
                    continue

                with open(xml_file, "r", encoding="utf-8") as f:
                    xml_content = f.read()

                nodes = self._prepare_nodes_with_alter_action(xml_content)
                entity_stats = {"total": len(nodes), "created": 0, "altered": 0, "errors": 0}

                if nodes:
                    # Send in batches of BATCH_SIZE
                    for i in range(0, len(nodes), BATCH_SIZE):
                        batch = nodes[i : i + BATCH_SIZE]
                        batch_xml = "\n".join([f"<TALLYMESSAGE xmlns:UDF=\"TallyUDF\">{n}</TALLYMESSAGE>" for n in batch])
                        
                        success, resp, stats = tally_client.import_entity_data(
                            company_name=final_company,
                            messages_xml=batch_xml,
                            report_name=report_name
                        )
                        
                        entity_stats["created"] += stats.get("created", 0)
                        entity_stats["altered"] += stats.get("altered", 0)
                        entity_stats["errors"] += stats.get("errors", 0)

                summary_stats[entity_key] = entity_stats

            # 5. Clean staging directory
            self._update_restore_progress(restore_id, 98, "Cleaning temporary files...")
            storage.clean_staging_dir(staging_dir)

            # 6. Finalize in database
            completed_time = datetime.datetime.now().isoformat()
            with get_db() as conn:
                conn.execute("""
                    UPDATE restore_logs
                    SET status = 'completed',
                        progress_percent = 100,
                        progress_message = 'Restore completed successfully',
                        summary = ?,
                        completed_at = ?
                    WHERE id = ?
                """, (json.dumps(summary_stats), completed_time, restore_id))

            logger.info(f"✅ Restore {restore_id} completed successfully for company '{final_company}'")

        except Exception as e:
            logger.error(f"❌ Restore {restore_id} failed: {e}", exc_info=True)
            storage.clean_staging_dir(staging_dir)
            with get_db() as conn:
                conn.execute("""
                    UPDATE restore_logs
                    SET status = 'failed',
                        progress_message = 'Restore failed',
                        error_message = ?
                    WHERE id = ?
                """, (str(e), restore_id))
        finally:
            self._running_tasks.pop(restore_id, None)

    def start_restore(self, backup_id: str, target_company_name: Optional[str] = None) -> str:
        """
        Initiates restoration of a backup archive into Tally Prime asynchronously.
        Returns the generated restore_id immediately.
        """
        with get_db() as conn:
            cur = conn.execute("SELECT company_name FROM backups WHERE id = ?", (backup_id,))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Backup {backup_id} not found")
            orig_company = row["company_name"]

        now = datetime.datetime.now()
        timestamp_str = now.strftime("%Y%m%d-%H%M%S")
        short_hash = uuid.uuid4().hex[:6]
        restore_id = f"RST-{timestamp_str}-{short_hash}"
        final_target = target_company_name or orig_company
        started_at = now.isoformat()

        # Insert initial record into SQLite
        with get_db() as conn:
            conn.execute("""
                INSERT INTO restore_logs (
                    id, backup_id, company_name, target_company_name,
                    status, progress_percent, progress_message, started_at
                ) VALUES (?, ?, ?, ?, 'pending', 0, 'Initializing restore...', ?)
            """, (restore_id, backup_id, orig_company, final_target, started_at))

        # Launch background worker
        worker = threading.Thread(
            target=self._execute_restore_thread,
            args=(restore_id, backup_id, final_target),
            daemon=True
        )
        self._running_tasks[restore_id] = worker
        worker.start()

        return restore_id

restore_service = RestoreService()
