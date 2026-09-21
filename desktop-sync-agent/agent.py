import os
import sys
import time
import signal
import argparse
import logging
import threading
from logging.handlers import RotatingFileHandler
from typing import List, Optional, Dict, Any, Tuple

from config import (
    load_config,
    save_config,
    AgentConfig,
    get_logs_dir,
    install_startup as cfg_install_startup,
    uninstall_startup as cfg_uninstall_startup
)
from tally_client import TallyClient
from cloud_client import CloudClient

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
    def __init__(self, config_path: str = "agent_config.json"):
        self.config_path = config_path
        self.config: AgentConfig = load_config(config_path)
        self.tally = TallyClient(tally_url=self.config.tally_url)
        self.cloud = CloudClient(
            backend_url=self.config.backend_url,
            token=self.config.auth_token,
            email=self.config.email or self.config.username,
            password=self.config.password,
            on_token_refreshed=self._on_token_refreshed
        )
        self.last_inbound_time = 0
        self.active_company_name = self.config.company_name
        self.active_company_guid = ""
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
        if self.is_paused:
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
            on_token_refreshed=self._on_token_refreshed
        )
        self.active_company_name = self.config.company_name
        logger.info("🔄 Agent configuration reloaded.")

    def _on_token_refreshed(self, new_token: str):
        self.config.auth_token = new_token
        save_config(self.config, self.config_path)

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

            if tally_info["company_name"]:
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

        # Authenticate if credentials are provided
        if self.config.email and self.config.password:
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
        Dynamically adapts synchronization target.
        """
        open_cmps = self.tally.get_open_companies()
        self.open_companies_count = len(open_cmps)

        if not open_cmps:
            return

        # Check if currently active company is still open in Tally
        open_names = [c["name"] for c in open_cmps]
        matching_current = next((c for c in open_cmps if c["name"] == self.active_company_name), None)

        if matching_current:
            # Current company is still open and valid; update GUID if needed
            self.active_company_guid = matching_current.get("guid", self.active_company_guid)
            return

        # Otherwise, the previous company was closed; switch to the first open company
        current_active = open_cmps[0]["name"]
        current_guid = open_cmps[0].get("guid", "")

        if self.active_company_name != current_active:
            other_info = f" (Total Open: {len(open_cmps)} - {', '.join(open_names)})" if len(open_cmps) > 1 else ""
            logger.info(
                f"\n{'=' * 75}\n"
                f"🏢 [COMPANY SWITCH DETECTED IN TALLY]\n"
                f"   Previous Company: '{self.active_company_name}'\n"
                f"   Active Company:   '{current_active}' (GUID: {current_guid}){other_info}\n"
                f"   ⚡ Auto-switching Cloud Sync Target to '{current_active}'...\n"
                f"{'=' * 75}\n"
            )

            self.active_company_name = current_active
            self.active_company_guid = current_guid
            self.config.company_name = current_active
            save_config(self.config, self.config_path)

    def sync_outbound_cycle(self) -> int:
        """Pulls pending voucher/ledger creation requests from Cloud and pushes them to Tally."""
        self.check_and_handle_company_switch()

        tasks, err = self.cloud.fetch_outbound_queue()
        if err:
            logger.warning(f"⚠️ Could not fetch outbound tasks from Cloud Backend: {err}")
            return 0

        if not tasks:
            return 0

        logger.info(f"📥 Received {len(tasks)} outbound task(s) from MyTally Cloud Queue.")
        successful_ids: List[int] = []

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
                sv_tag = f"<STATICVARIABLES><SVCURRENTCOMPANY>{self.active_company_name}</SVCURRENTCOMPANY>"
                if "<STATICVARIABLES>" in xml_payload:
                    xml_payload = xml_payload.replace("<STATICVARIABLES>", sv_tag)
                elif "<DESC>" in xml_payload:
                    xml_payload = xml_payload.replace("<DESC>", f"<DESC><STATICVARIABLES><SVCURRENTCOMPANY>{self.active_company_name}</SVCURRENTCOMPANY></STATICVARIABLES>")

            logger.info(f"⏳ Pushing {rec_type} #{rec_id} ({action}) to Tally for company '{self.active_company_name}'...")
            success, resp_str = self.tally.send_xml(xml_payload)

            if success:
                logger.info(f"✅ Tally Ingested: {rec_type} #{rec_id} successfully.")
                successful_ids.append(sync_id)
            else:
                logger.error(f"❌ Tally Rejected {rec_type} #{rec_id}. Response: {resp_str[:300]}")

        if successful_ids:
            ack_ok = self.cloud.acknowledge_queue(successful_ids)
            if ack_ok:
                logger.info(f"🎉 Successfully acknowledged {len(successful_ids)} task(s) to Cloud Backend.\n")

        return len(successful_ids)

    def sync_inbound_cycle(self, is_incremental: bool = False):
        """Pulls masters and vouchers from Tally and pushes them into MyTally Cloud database with deep diagnostics."""
        if not self.active_company_name:
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

            min_alter = 0
            if is_incremental:
                alt1, alt2 = self.cloud.get_last_alter_id()
                min_alter = max(alt1, alt2)
                prefix = f"⚡ [INBOUND DELTA SYNC] Checking Tally changes (ALTERID > {min_alter})..."
            elif force_all:
                prefix = f"📥 [INBOUND FULL SYNC ALL] Pulling all baseline data from Tally (ALTERID bypassed)..."
            else:
                prefix = f"📥 [INITIAL INBOUND SYNC] Pulling full baseline data from Tally..."

            logger.info(f"{prefix}")
            collections = self.tally.export_full_collections(self.active_company_name, min_alter_id=min_alter)
            
            if not collections:
                logger.info("   ✨ 0 changes detected in Tally. Database is 100% up-to-date.")
                self.last_inbound_time = time.time()
                self.last_sync_time = time.time()
                self.last_sync_timestr = time.strftime("%d %b %Y, %I:%M:%S %p")
                self.last_sync_status = "Up-to-date (0 changes)"
                return

            total_vouchers = 0
            total_ledgers = 0
            total_items = 0
            total_errors = 0

            for idx, (label, xml_data) in enumerate(collections, 1):
                size_kb = len(xml_data.encode("utf-8")) / 1024.0
                logger.info(f"   • [{idx}/{len(collections)}] Exported '{label}' from Tally ({size_kb:.1f} KB). Pushing to cloud...")
                
                ok, res = self.cloud.push_inbound_xml(xml_data, self.active_company_name)
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
    parser.add_argument("--config", default="agent_config.json", help="Path to config file")

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
