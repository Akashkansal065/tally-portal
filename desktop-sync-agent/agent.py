import os
import sys
import time
import signal
import argparse
import logging
import threading
from logging.handlers import RotatingFileHandler
from typing import List, Optional, Dict, Any, Tuple

import re
from config import (
    load_config,
    save_config,
    AgentConfig,
    get_logs_dir,
    get_default_config_path,
    install_startup as cfg_install_startup,
    uninstall_startup as cfg_uninstall_startup
)
from tally_client import TallyClient, escape_xml, NETWORK_ERROR_PREFIX
from cloud_client import CloudClient, halt_message

# Configure Logging with both Console and Rotating File Handler in safe logs directory
logs_dir = get_logs_dir()
file_handler = RotatingFileHandler(
    os.path.join(logs_dir, "agent.log"),
    maxBytes=5 * 1024 * 1024,  # 5 MB per file
    backupCount=3,
    encoding="utf-8"
)
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))

logger = logging.getLogger("MyTallySyncAgent")
logger.setLevel(logging.INFO)
logger.handlers.clear()
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Configure sub-client loggers
for sub_logger_name in ["TallyClient", "CloudClient"]:
    sub_l = logging.getLogger(sub_logger_name)
    sub_l.setLevel(logging.INFO)
    sub_l.handlers.clear()
    sub_l.addHandler(file_handler)
    sub_l.addHandler(console_handler)

class CallbackLogHandler(logging.Handler):
    """Custom logging handler to route log records to GUI listeners in real-time."""
    def __init__(self, agent):
        super().__init__()
        self.agent = agent
        self.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))

    def emit(self, record):
        try:
            msg = self.format(record)
            lock = getattr(self.agent, "_log_lock", None)
            if lock:
                with lock:
                    callbacks = list(self.agent.log_callbacks)
            else:
                callbacks = list(self.agent.log_callbacks)

            for cb in callbacks:
                try:
                    cb(msg, record.levelname)
                except Exception:
                    pass
        except Exception:
            pass

# Global stop flag
running = True

def signal_handler(signum, frame):
    global running
    logger.info("🛑 Shutdown signal received. Gracefully stopping MyTally Sync Agent...")
    running = False

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def print_banner():
    banner = (
        "\n"
        "===========================================================================\n"
        "  🚀  SnehDistribuors Desktop Sync Agent (TallyPrime Connector)\n"
        "===========================================================================\n"
        "  Bridging TallyPrime (Local Port 9000) ◄═══► SnehDistribuors Cloud ERP\n"
        "==========================================================================="
    )
    logger.info(banner)

class DesktopSyncAgent:
    def __init__(self, config_path: Optional[str] = None):
        # Default to the file next to the script/.exe (gitignored), never the current working directory
        self.config_path = config_path or get_default_config_path()
        self.config: AgentConfig = load_config(config_path)
        self.tally = TallyClient(tally_url=self.config.tally_url)
        self.cloud = CloudClient(
            backend_url=self.config.backend_url,
            token=self.config.auth_token,
            email=self.config.email or self.config.username,
            password=self.config.password,
            on_token_refreshed=self._on_token_refreshed,
            auth_halt_reason=self.config.auth_halt_reason,
            on_auth_halted=self._on_auth_halted
        )
        self.last_inbound_time = 0
        self.active_company_name = self.config.company_name
        self.active_company_guid = getattr(self.config, "company_guid", "") or ""
        self.company_paused = False
        self.open_companies_count = 0

        # State tracking for GUI
        self.tally_connected = False
        self.cloud_connected = False
        self.cloud_message = ""
        self.tally_release = ""
        self.is_paused = False
        self.is_running = False
        self.is_syncing = False
        self.immediate_sync_requested = False
        self.force_full_sync_next = False
        self.last_sync_time = None
        self.last_sync_timestr = "Never"
        self.last_sync_status = "Ready"
        self.total_vouchers = 0
        self.total_ledgers = 0
        self.total_items = 0
        self.total_errors = 0
        self._log_lock = threading.Lock()
        self.log_callbacks = []
        # Hook log handler into logger and sub-client loggers
        self._gui_handler = CallbackLogHandler(self)
        logger.addHandler(self._gui_handler)
        for sub_name in ["TallyClient", "CloudClient"]:
            logging.getLogger(sub_name).addHandler(self._gui_handler)

    def add_log_listener(self, cb):
        with self._log_lock:
            if cb not in self.log_callbacks:
                self.log_callbacks.append(cb)

    def remove_log_listener(self, cb):
        with self._log_lock:
            if cb in self.log_callbacks:
                self.log_callbacks.remove(cb)

    def pause(self):
        self.is_paused = True
        logger.info("⏸ Syncing has been paused.")

    def resume(self):
        self.is_paused = False
        logger.info("▶ Syncing has resumed.")

    def stop(self):
        self.is_running = False

    def trigger_immediate_sync(self, force_full: bool = False):
        if force_full:
            self.force_full_sync_next = True
            logger.info("⚡ Immediate FULL baseline sync requested (ALTERID bypassed).")
        else:
            logger.info("⚡ Immediate delta sync pass requested.")
        self.immediate_sync_requested = True

    def get_status(self) -> dict:
        halt_reason = self.cloud.auth_halt_reason
        if halt_reason:
            status_text = "BLOCKED" if halt_reason in ("blocked", "device_blocked") else "SIGNED OUT"
        elif self.is_paused:
            status_text = "PAUSED"
        elif self.is_syncing:
            status_text = "SYNCING"
        elif self.tally_connected and self.cloud_connected:
            status_text = "ONLINE"
        elif not self.tally_connected:
            status_text = "TALLY OFFLINE"
        else:
            status_text = "CLOUD OFFLINE"

        return {
            "status": status_text,
            "tally_connected": self.tally_connected,
            "cloud_connected": self.cloud_connected,
            "cloud_message": self.cloud_message,
            "active_company_name": self.active_company_name,
            "open_companies_count": self.open_companies_count,
            "tally_release": self.tally_release,
            "total_vouchers": self.total_vouchers,
            "total_ledgers": self.total_ledgers,
            "total_items": self.total_items,
            "total_errors": self.total_errors,
            "last_sync_time": self.last_sync_time,
            "last_sync_timestr": self.last_sync_timestr,
            "last_sync_status": self.last_sync_status,
            "is_paused": self.is_paused,
            "is_syncing": self.is_syncing,
            "auth_halt_reason": halt_reason,
            "auth_halt_message": halt_message(halt_reason) if halt_reason else "",
        }

    def reload_config(self, new_config: Optional[AgentConfig] = None):
        if new_config:
            self.config = new_config
        else:
            self.config = load_config(self.config_path)
        self.tally = TallyClient(tally_url=self.config.tally_url)
        self.cloud = CloudClient(
            backend_url=self.config.backend_url,
            token=self.config.auth_token,
            email=self.config.email or self.config.username,
            password=self.config.password,
            on_token_refreshed=self._on_token_refreshed,
            auth_halt_reason=self.config.auth_halt_reason,
            on_auth_halted=self._on_auth_halted
        )
        self.active_company_name = self.config.company_name
        self.active_company_guid = getattr(self.config, "company_guid", "") or ""
        self.company_paused = False
        logger.info("🔄 Agent configuration reloaded.")

    def _on_token_refreshed(self, new_token: str):
        self.config.auth_token = new_token
        save_config(self.config, self.config_path)

    def _on_auth_halted(self, reason: str):
        """The server signed this PC out on purpose or blocked it: stop syncing until credentials are re-entered."""
        self.config.auth_halt_reason = reason
        self.config.auth_token = ""
        save_config(self.config, self.config_path)
        self.cloud_message = halt_message(reason)
        self.last_sync_status = halt_message(reason)

    def discover_and_report(self):
        logger.info(f"🔍 Contacting Tally XML Server at {self.config.tally_url}...")
        tally_info = self.tally.discover_tally_host()
        
        self.tally_connected = tally_info.get("connected", False)
        self.tally_release = tally_info.get("release", "")

        if tally_info["connected"]:
            logger.info(f"✅ Tally Connection: ACTIVE")
            logger.info(f"🏢 Active Company:    {tally_info['company_name'] or self.config.company_name}")
            logger.info(f"📂 Application Path:  {tally_info['app_path']}")
            logger.info(f"💾 Data Path:         {tally_info['data_path']}")
            logger.info(f"🏷️ Tally Release:     {tally_info['release']}")

            # The first open company only names the target while none is pinned by GUID; once pinned,
            # check_and_handle_company_switch() keeps following that GUID
            if tally_info["company_name"] and not self.active_company_guid:
                self.active_company_name = tally_info["company_name"]
            
            # Save discovered paths to config if enabled
            if self.config.auto_discover_paths and tally_info["app_path"]:
                self.config.tally_app_path = tally_info["app_path"]
                self.config.tally_data_path = tally_info["data_path"]
                self.config.company_name = self.active_company_name
                save_config(self.config, self.config_path)
        else:
            logger.warning(f"❌ Tally Connection: INACTIVE (Tally Prime not responding on {self.config.tally_url})")

        # Also check open companies count
        open_cmps = self.tally.get_open_companies()
        self.open_companies_count = len(open_cmps)
        if open_cmps:
            logger.info(f"📚 Open Companies in Tally ({len(open_cmps)}):")
            for c in open_cmps:
                is_active = (c["name"] == self.active_company_name)
                marker = "👉 [ACTIVE]" if is_active else "  "
                logger.info(f"   {marker} {c['name']} (Period: {c['starting_from']} to {c['ending_at']})")

        logger.info(f"🔍 Contacting SnehDistribuors Cloud at {self.config.backend_url}...")
        cloud_ok, cloud_msg = self.cloud.check_health()
        self.cloud_connected = cloud_ok
        self.cloud_message = cloud_msg

        if cloud_ok:
            logger.info(f"✅ Cloud Connection: ACTIVE ({cloud_msg})")
        else:
            logger.warning(f"⚠️ Cloud Connection: WARNING ({cloud_msg})")

        # Authenticate if credentials are provided (not while an admin has signed this PC out or blocked it)
        if self.config.auth_halt_reason:
            self.cloud_message = halt_message(self.config.auth_halt_reason)
            logger.warning(f"⛔ Not signing in: {self.cloud_message}")
        elif self.config.email and self.config.password:
            auth_ok, auth_res = self.cloud.authenticate(self.config.email, self.config.password)
            if auth_ok:
                logger.info(f"🔑 Authenticated as '{self.config.email}' successfully.")
                self.config.auth_token = auth_res
                save_config(self.config, self.config_path)
            else:
                logger.warning(f"⚠️ Authentication failed: {auth_res}. Using cached token.")
        
        return tally_info.get("connected", False) and cloud_ok

    def check_and_handle_company_switch(self):
        """
        Detects if user opened, closed, or switched companies in TallyPrime.
        Dynamically adapts synchronization target, pinning strictly by GUID if configured.
        """
        open_cmps = self.tally.get_open_companies()
        self.open_companies_count = len(open_cmps)

        if not open_cmps:
            return

        # If company GUID is pinned, strictly match against GUID
        if self.active_company_guid:
            match = next((c for c in open_cmps if c.get("guid") == self.active_company_guid), None)
            if match is None:
                # Same name but different GUID is a different company (a restore, or copy)
                if not self.company_paused:
                    logger.warning(
                        f"⏸️ '{self.active_company_name}' (GUID {self.active_company_guid}) isn't open in Tally; "
                        f"sync paused. Open companies: {', '.join(c.get('name', '') for c in open_cmps)}"
                    )
                self.company_paused = True
                return
            self.company_paused = False
            self.active_company_name = match["name"]  # A rename in Tally is fine; GUID is what identifies it
            return

        # Fallback when no GUID was previously stored: match by company name
        match = next((c for c in open_cmps if c.get("name") == self.active_company_name), None)
        if match:
            self.company_paused = False
            self.active_company_guid = match.get("guid", "")
            if self.active_company_guid:
                self.config.company_guid = self.active_company_guid
                save_config(self.config, self.config_path)
            return

        # Target company is not open in Tally; pause sync rather than switching to another company!
        if not self.company_paused:
            logger.warning(
                f"⏸️ '{self.active_company_name}' isn't open in Tally; sync paused. "
                f"Open companies: {', '.join(c.get('name', '') for c in open_cmps)}"
            )
        self.company_paused = True

    def _paused_status(self) -> str:
        return f"Paused: '{self.active_company_name}' is not open in Tally"

    def sync_outbound_cycle(self) -> int:
        """Pulls pending voucher/ledger creation requests from Cloud and pushes them to Tally."""
        if self.cloud.auth_halt_reason:
            return 0
        self.check_and_handle_company_switch()
        if self.company_paused:
            # Shown in the GUI: nothing is sent to Tally until the company this agent is tied to is open again
            self.last_sync_status = self._paused_status()
            return 0

        tasks, err = self.cloud.fetch_outbound_queue()
        if err:
            logger.warning(f"⚠️ Could not fetch outbound tasks from Cloud Backend: {err}")
            return 0

        if not tasks:
            return 0

        logger.info(f"📥 Received {len(tasks)} outbound task(s) from MyTally Cloud Queue.")
        successful_ids: List[int] = []
        voucher_identities: List[Dict[str, Any]] = []

        for task in tasks:
            sync_id = task.get("sync_id")
            rec_type = task.get("record_type")
            rec_id = task.get("record_id")
            action = task.get("action")
            xml_payload = task.get("xml_payload")

            if not xml_payload:
                logger.warning(f"Task #{sync_id} ({rec_type} #{rec_id}) has no XML payload. Skipping.")
                continue

            # Ensure SVCURRENTCOMPANY is explicitly set in STATICVARIABLES to avoid multi-company cross-talk
            if "<SVCURRENTCOMPANY>" not in xml_payload and self.active_company_name:
                esc_cmp = escape_xml(self.active_company_name)
                sv_tag = f"<STATICVARIABLES><SVCURRENTCOMPANY>{esc_cmp}</SVCURRENTCOMPANY>"
                if "<STATICVARIABLES>" in xml_payload:
                    xml_payload = xml_payload.replace("<STATICVARIABLES>", sv_tag)
                elif "<DESC>" in xml_payload:
                    xml_payload = xml_payload.replace("<DESC>", f"<DESC><STATICVARIABLES><SVCURRENTCOMPANY>{esc_cmp}</SVCURRENTCOMPANY></STATICVARIABLES>")

            # A voucher addressed by master id is only found under the date it has in Tally right now. If
            # someone moved it in Tally since the backend last heard, the old date would make a second voucher.
            m_addr = re.search(r'<VOUCHER DATE="(\d{8})" TAGNAME="MASTERID" TAGVALUE="(\d+)"', xml_payload)
            if m_addr:
                held = self.tally.find_voucher_by_master_id(self.active_company_name, int(m_addr.group(2)))
                if held and held.get("date") and held["date"] != m_addr.group(1):
                    logger.info(f"Voucher #{rec_id} is dated {held['date']} in Tally, not {m_addr.group(1)}; addressing it there.")
                    xml_payload = xml_payload.replace(m_addr.group(0), f'<VOUCHER DATE="{held["date"]}" TAGNAME="MASTERID" TAGVALUE="{m_addr.group(2)}"', 1)

            logger.info(f"⏳ Pushing {rec_type} #{rec_id} ({action}) to Tally for company '{self.active_company_name}'...")
            success, resp_str = self.tally.send_xml(xml_payload)

            if success:
                logger.info(f"✅ Tally Ingested: {rec_type} #{rec_id} successfully.")
                successful_ids.append(sync_id)
                if str(rec_type or "").lower() == "voucher" and str(action or "").lower() != "delete":
                    # Tally numbers the voucher itself; read back what it made of it for the app
                    m_last = re.search(r"<LASTVCHID>\s*(\d+)\s*</LASTVCHID>", resp_str)
                    found_vch = self.tally.find_voucher_by_master_id(self.active_company_name, int(m_last.group(1))) if m_last and int(m_last.group(1)) else None
                    if found_vch:
                        voucher_identities.append({"voucher_id": rec_id, **found_vch})
            else:
                # A Create that timed out or lost its connection may still have been saved by Tally. Look it up by
                # REMOTEID before resending: a resend would alter it again and could undo a cancel made in Tally
                # meanwhile. Only for a network failure on a Create; when Tally answered and rejected the request,
                # or for an Alter/Delete/Cancel (the voucher exists either way), finding it proves nothing.
                recovered = False
                is_network_failure = resp_str.startswith(NETWORK_ERROR_PREFIX)
                if is_network_failure and str(rec_type or "").lower() == "voucher" and str(action or "").lower() == "create":
                    m_remote = re.search(r'REMOTEID="([^"]+)"', xml_payload)
                    remote_id = m_remote.group(1) if m_remote else f"MYTALLY-VCH-{rec_id}"
                    m_date = re.search(r"<DATE>(\d{8})</DATE>", xml_payload)
                    found_vch = self.tally.find_voucher_by_remote_id(
                        self.active_company_name, remote_id, m_date.group(1) if m_date else None)
                    if found_vch:
                        logger.info(
                            f"✨ Voucher #{rec_id} was saved in Tally despite the {resp_str[:80]} "
                            f"(RemoteID: {remote_id}, GUID: {found_vch.get('guid')}). Acknowledging."
                        )
                        successful_ids.append(sync_id)
                        recovered = True
                if not recovered:
                    logger.error(f"❌ Tally Rejected {rec_type} #{rec_id}. Response: {resp_str[:300]}")

        if successful_ids:
            ack_ok = self.cloud.acknowledge_queue(successful_ids)
            if ack_ok:
                logger.info(f"🎉 Successfully acknowledged {len(successful_ids)} task(s) to Cloud Backend.\n")
        if voucher_identities:
            self.cloud.report_voucher_identities(voucher_identities)

        return len(successful_ids)

    def sync_inbound_cycle(self, is_incremental: bool = False):
        """Pulls masters and vouchers from Tally and pushes them into MyTally Cloud database with deep diagnostics."""
        if not self.active_company_name or self.cloud.auth_halt_reason:
            return

        self.check_and_handle_company_switch()
        if self.company_paused:
            self.last_sync_status = self._paused_status()
            return

        # Pre-flight check: if Tally was offline, quickly test before attempting 9 collection exports
        if not self.tally_connected:
            t_ok, _ = self.tally.check_health()
            if not t_ok:
                self.last_sync_status = "Tally Offline"
                return
            else:
                self.tally_connected = True
                logger.info("🎉 TallyPrime connection restored! Resuming synchronization.")

        self.is_syncing = True
        try:
            # Check if user requested a full sync (Sync All) or configured force_full_sync
            force_all = getattr(self.config, "force_full_sync", False) or self.force_full_sync_next
            if force_all:
                self.force_full_sync_next = False
                is_incremental = False

            company_key = self.active_company_name
            retry_floor = (self.config.inbound_retry_floors or {}).get(company_key)

            min_alter = 0
            min_voucher_alter = 0
            if is_incremental:
                # Masters and vouchers have separate change counters in Tally, hence separate watermarks
                master_watermark, voucher_watermark = self.cloud.get_last_alter_id()
                server_watermark = max(master_watermark, voucher_watermark)
                # After a failed cycle, re-pull from where that cycle started: the server's watermark is
                # the highest AlterID it holds, which can be past records that never arrived.
                min_alter = master_watermark if retry_floor is None else min(retry_floor, master_watermark)
                min_voucher_alter = voucher_watermark if retry_floor is None else min(retry_floor, voucher_watermark)
                prefix = f"⚡ [INBOUND DELTA SYNC] Checking Tally changes (masters ALTERID > {min_alter}, vouchers ALTERID > {min_voucher_alter})..."
                if retry_floor is not None and retry_floor < server_watermark:
                    prefix += f" [re-pulling from {retry_floor} after an earlier failed cycle]"
            elif force_all:
                prefix = f"📥 [INBOUND FULL SYNC ALL] Pulling all baseline data from Tally (ALTERID bypassed)..."
            else:
                prefix = f"📥 [INITIAL INBOUND SYNC] Pulling full baseline data from Tally..."

            logger.info(f"{prefix}")
            collections = self.tally.export_full_collections(self.active_company_name, min_alter_id=min_alter,
                                                             min_voucher_alter_id=min_voucher_alter if is_incremental else None)
            export_failures = list(getattr(self.tally, "last_export_failures", []) or [])
            if export_failures:
                logger.error(f"   ❌ Could not export from Tally: {', '.join(export_failures)}")

            if not collections:
                self._update_inbound_retry_floor(company_key, min(min_alter, min_voucher_alter) if is_incremental else min_alter, failed=bool(export_failures))
                self.last_inbound_time = time.time()
                self.last_sync_time = time.time()
                self.last_sync_timestr = time.strftime("%d %b %Y, %I:%M:%S %p")
                if export_failures:
                    self.last_sync_status = f"Tally export failed ({', '.join(export_failures)})"
                else:
                    logger.info("   ✨ 0 changes detected in Tally. Database is 100% up-to-date.")
                    self.last_sync_status = "Up-to-date (0 changes)"
                return

            total_vouchers = 0
            total_ledgers = 0
            total_items = 0
            total_errors = 0
            total_record_errors = 0

            for idx, (label, xml_data) in enumerate(collections, 1):
                size_kb = len(xml_data.encode("utf-8")) / 1024.0
                logger.info(f"   • [{idx}/{len(collections)}] Exported '{label}' from Tally ({size_kb:.1f} KB). Pushing to cloud...")
                
                ok, res = self.cloud.push_inbound_xml(xml_data, self.active_company_name, force=force_all)
                dur = res.get("duration_seconds", 0.0)
                
                if ok:
                    v_count = res.get("imported_vouchers", 0)
                    l_count = res.get("imported_ledgers", 0)
                    g_count = res.get("imported_groups", 0)
                    s_count = res.get("imported_stock_items", 0)
                    total_vouchers += v_count
                    total_ledgers += l_count
                    total_items += s_count
                    logger.info(f"   • ✅ '{label}' Synced in {dur:.2f}s (Vouchers: {v_count}, Ledgers: {l_count}, Items: {s_count}, Groups: {g_count})")
                    record_errors = res.get("errors") or []
                    if record_errors:
                        # Individual records the server rejected. They would fail the same way on a re-pull,
                        # so they are reported rather than retried; fix them in Tally and they re-sync on next edit.
                        total_record_errors += len(record_errors)
                        logger.warning(f"   ⚠️ '{label}': {len(record_errors)} record(s) rejected by the server, e.g. {record_errors[:3]}")
                else:
                    total_errors += 1
                    err_type = res.get("error_type", "SYNC_ERROR")
                    err_msg = res.get("error", "Unknown error")
                    status_code = res.get("status_code")
                    endpoint = res.get("endpoint", "/sync/inbound")

                    logger.error(
                        f"\n"
                        f"   ╔═══════════════════════════════════════════════════════════════════════\n"
                        f"   ║ ❌ INBOUND PUSH FAILED: '{label}'\n"
                        f"   ╠═══════════════════════════════════════════════════════════════════════\n"
                        f"   ║ • Error Classification: {err_type}\n"
                        f"   ║ • Error Details:        {err_msg}\n"
                        f"   ║ • HTTP Status Code:     {status_code or 'None (Connection/Timeout Issue)'}\n"
                        f"   ║ • Target Endpoint:      {self.config.backend_url.rstrip('/')}{endpoint}\n"
                        f"   ║ • Payload Size:         {size_kb:.1f} KB\n"
                        f"   ║ • Request Duration:     {dur:.2f} seconds\n"
                        f"   ║ • Possible Cause:       {'Network timeout or server took too long to process XML' if 'TIMEOUT' in err_type else 'Server code exception or invalid credentials' if '500' in str(status_code) or 'AUTH' in err_type else 'Tunnel/network drop'}\n"
                        f"   ╚═══════════════════════════════════════════════════════════════════════\n"
                    )

            self.total_vouchers += total_vouchers
            self.total_ledgers += total_ledgers
            self.total_items += total_items
            self.total_errors += total_errors
            self._update_inbound_retry_floor(company_key, min(min_alter, min_voucher_alter) if is_incremental else min_alter, failed=bool(export_failures) or total_errors > 0)
            self.last_sync_time = time.time()
            self.last_sync_timestr = time.strftime("%d %b %Y, %I:%M:%S %p")

            if (total_vouchers + total_ledgers + total_items) > 0 or not is_incremental:
                msg = f"🎉 [DATABASE UPDATED] Synced {total_vouchers} Vouchers, {total_ledgers} Ledgers, {total_items} Items for '{self.active_company_name}'! (Errors: {total_errors})"
                logger.info(msg)
                self.last_sync_status = f"Synced {total_vouchers} Vouchers, {total_ledgers} Ledgers"
            else:
                msg = f"   ✨ 0 changes detected in Tally. Database is up-to-date. (Errors: {total_errors})"
                logger.info(msg)
                self.last_sync_status = "Up-to-date"

            self.last_inbound_time = time.time()
        finally:
            self.is_syncing = False

    def _update_inbound_retry_floor(self, company_key: str, cycle_min_alter: int, failed: bool):
        """Remember (persistently) where a failed inbound cycle started, and forget it once a cycle is clean."""
        floors = dict(self.config.inbound_retry_floors or {})
        current = floors.get(company_key)
        if failed:
            new_floor = cycle_min_alter if current is None else min(current, cycle_min_alter)
            if new_floor != current:
                floors[company_key] = new_floor
                self.config.inbound_retry_floors = floors
                save_config(self.config, self.config_path)
            logger.warning(f"   ↩️ Inbound cycle incomplete for '{company_key}': next cycle re-pulls changes with ALTERID > {new_floor}.")
        elif current is not None:
            floors.pop(company_key, None)
            self.config.inbound_retry_floors = floors
            save_config(self.config, self.config_path)
            logger.info(f"   ✅ Inbound sync for '{company_key}' caught up; cleared retry point {current}.")

    def run_single_cycle(self):
        """Runs a single pass of discovery, inbound, and outbound synchronization."""
        print_banner()
        self.discover_and_report()
        self.sync_inbound_cycle(is_incremental=False)
        synced = self.sync_outbound_cycle()
        logger.info(f"🏁 Single sync cycle completed. Synced {synced} outbound tasks.")

    def run_daemon(self):
        """Runs continuously in the background."""
        global running
        self.is_running = True
        print_banner()
        self.discover_and_report()

        # Run initial baseline inbound sync to populate project DB right away
        if not self.is_paused:
            self.sync_inbound_cycle(is_incremental=False)

        logger.info(f"🔄 Starting background sync daemon (outbound: {self.config.sync_interval_seconds}s, inbound: {self.config.inbound_interval_seconds}s)...")
        logger.info("Press Ctrl + C at any time to exit.\n")

        while running and self.is_running:
            try:
                if not self.is_paused:
                    # 1. Outbound Sync (Cloud -> Tally)
                    self.sync_outbound_cycle()

                    # 2. Periodic Incremental Inbound Sync (Tally -> Cloud DB)
                    if self.immediate_sync_requested or (time.time() - self.last_inbound_time) >= self.config.inbound_interval_seconds:
                        self.immediate_sync_requested = False
                        self.sync_inbound_cycle(is_incremental=True)

                # Sleep interval
                for _ in range(max(1, self.config.sync_interval_seconds)):
                    if not running or not self.is_running or self.immediate_sync_requested:
                        break
                    time.sleep(1)

            except Exception as e:
                logger.error(f"Error in sync daemon loop: {e}", exc_info=True)
                time.sleep(5)

        logger.info("👋 SnehDistribuors Desktop Sync Agent stopped cleanly.")

def install_startup():
    """Registers the agent into Windows Startup Registry to launch automatically on boot."""
    ok = cfg_install_startup()
    if ok:
        print("🎉 [AUTOSTART ENABLED] SnehDistribuors Sync Agent will launch automatically on Windows startup!")
    return ok

def uninstall_startup():
    """Removes the agent from Windows Startup Registry."""
    ok = cfg_uninstall_startup()
    if ok:
        print("ℹ️ [AUTOSTART DISABLED] SnehDistribuors Sync Agent removed from Windows startup.")
    return ok

def main():
    parser = argparse.ArgumentParser(description="MyTally Windows Desktop Sync Agent")
    parser.add_argument("--test-once", action="store_true", help="Run a single discovery & sync pass then exit")
    parser.add_argument("--discover", action="store_true", help="Run Tally host discovery only")
    parser.add_argument("--sync-all", "--full-sync", dest="sync_all", action="store_true", help="Force full baseline sync of all records (bypass Tally Alter ID incremental filter)")
    parser.add_argument("--install-startup", action="store_true", help="Configure agent to start automatically on Windows boot")
    parser.add_argument("--uninstall-startup", action="store_true", help="Remove agent from Windows system startup")
    parser.add_argument("--config", default=None, help="Path to config file (default: agent_config.json next to the agent)")

    args = parser.parse_args()

    if args.install_startup:
        print_banner()
        install_startup()
        return

    if args.uninstall_startup:
        print_banner()
        uninstall_startup()
        return

    agent = DesktopSyncAgent(config_path=args.config)
    if args.sync_all:
        agent.config.force_full_sync = True
        logger.info("⚡ Flag '--sync-all' provided: Bypassing Alter ID incremental filter.")

    if args.discover:
        print_banner()
        agent.discover_and_report()
    elif args.test_once:
        agent.run_single_cycle()
    else:
        agent.run_daemon()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        import traceback
        print("\n" + "=" * 75)
        print("❌ [FATAL ERROR] MyTally Sync Agent encountered an error:")
        print("=" * 75)
        traceback.print_exc()
        print("=" * 75)
        try:
            input("\nPress Enter to exit...")
        except Exception:
            pass
