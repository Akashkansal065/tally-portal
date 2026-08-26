import os
import sys
import time
import signal
import argparse
import logging
from typing import List

from config import load_config, save_config, AgentConfig
from tally_client import TallyClient
from cloud_client import CloudClient

# Configure Logging with both Console and File Handler
os.makedirs("logs", exist_ok=True)
file_handler = logging.FileHandler("logs/agent.log", encoding="utf-8")
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))

logger = logging.getLogger("MyTallySyncAgent")
logger.setLevel(logging.INFO)
logger.handlers.clear()
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Global stop flag
running = True

def signal_handler(signum, frame):
    global running
    print("\n🛑 Shutdown signal received. Gracefully stopping MyTally Sync Agent...")
    running = False

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def print_banner():
    banner = r"""
===========================================================================
  🚀  MyTally Desktop Sync Agent (TallyPrime Connector)
===========================================================================
  Bridging TallyPrime (Local Port 9000) ◄═══► MyTally Cloud ERP
===========================================================================
"""
    print(banner)

class DesktopSyncAgent:
    def __init__(self, config_path: str = "agent_config.json"):
        self.config_path = config_path
        self.config: AgentConfig = load_config(config_path)
        self.tally = TallyClient(tally_url=self.config.tally_url)
        self.cloud = CloudClient(backend_url=self.config.backend_url, token=self.config.auth_token)
        self.last_inbound_time = 0
        self.active_company_name = self.config.company_name
        self.active_company_guid = ""
        self.open_companies_count = 0

    def discover_and_report(self):
        print(f"🔍 Contacting Tally XML Server at {self.config.tally_url}...")
        tally_info = self.tally.discover_tally_host()
        
        if tally_info["connected"]:
            print(f"✅ Tally Connection: ACTIVE")
            print(f"🏢 Active Company:    {tally_info['company_name'] or self.config.company_name}")
            print(f"📂 Application Path:  {tally_info['app_path']}")
            print(f"💾 Data Path:         {tally_info['data_path']}")
            print(f"⚙️ Config (tallysave): {tally_info['tallysave_path']}")
            print(f"📄 Startup Settings:  {tally_info['tally_ini_path']}")
            print(f"🏷️ Tally Release:     {tally_info['release']}\n")

            if tally_info["company_name"]:
                self.active_company_name = tally_info["company_name"]
            
            # Save discovered paths to config if enabled
            if self.config.auto_discover_paths and tally_info["app_path"]:
                self.config.tally_app_path = tally_info["app_path"]
                self.config.tally_data_path = tally_info["data_path"]
                self.config.company_name = self.active_company_name
                save_config(self.config, self.config_path)
        else:
            print(f"❌ Tally Connection: INACTIVE (Tally Prime not responding on {self.config.tally_url})\n")

        # Also check open companies count
        open_cmps = self.tally.get_open_companies()
        self.open_companies_count = len(open_cmps)
        if open_cmps:
            print(f"📚 Open Companies in Tally ({len(open_cmps)}):")
            for c in open_cmps:
                is_active = (c["name"] == self.active_company_name)
                marker = "👉 [ACTIVE]" if is_active else "  "
                print(f"   {marker} {c['name']} (Period: {c['starting_from']} to {c['ending_at']})")
            print()

        print(f"🔍 Contacting MyTally Cloud at {self.config.backend_url}...")
        cloud_ok, cloud_msg = self.cloud.check_health()
        if cloud_ok:
            print(f"✅ Cloud Connection: ACTIVE ({cloud_msg})\n")
        else:
            print(f"⚠️ Cloud Connection: WARNING ({cloud_msg})\n")

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

        # The first or main active company in Tally
        current_active = open_cmps[0]["name"]
        current_guid = open_cmps[0].get("guid", "")

        if self.active_company_name != current_active:
            print("\n" + "=" * 75)
            print("🏢 [COMPANY SWITCH DETECTED IN TALLY]")
            print(f"   Previous Company: '{self.active_company_name}'")
            print(f"   Active Company:   '{current_active}' (GUID: {current_guid})")
            if len(open_cmps) > 1:
                print(f"   ℹ️ Total Open Companies in Tally: {len(open_cmps)} ({', '.join(c['name'] for c in open_cmps)})")
            print(f"   ⚡ Auto-switching MyTally Cloud Sync Target to '{current_active}'...")
            print("=" * 75 + "\n")

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

        min_alter = 0
        if is_incremental:
            last_led_alter, last_vch_alter = self.cloud.get_last_alter_id()
            min_alter = max(last_led_alter, last_vch_alter)
            prefix = f"⚡ [INBOUND DELTA SYNC] Checking Tally changes (ALTERID > {min_alter})..."
        else:
            prefix = f"📥 [INITIAL INBOUND SYNC] Pulling full baseline data from Tally..."

        print(f"{prefix}")
        collections = self.tally.export_full_collections(self.active_company_name, min_alter_id=min_alter)
        
        if not collections:
            print(f"   ✨ 0 changes detected in Tally. Database is 100% up-to-date.\n")
            self.last_inbound_time = time.time()
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
                    f"   ║ • Target Endpoint:      {self.config.backend_url}{endpoint}\n"
                    f"   ║ • Payload Size:         {size_kb:.1f} KB\n"
                    f"   ║ • Request Duration:     {dur:.2f} seconds\n"
                    f"   ║ • Possible Cause:       {'Network timeout or server took too long to process XML' if 'TIMEOUT' in err_type else 'Server code exception or invalid credentials' if '500' in str(status_code) or 'AUTH' in err_type else 'Tunnel/network drop'}\n"
                    f"   ╚═══════════════════════════════════════════════════════════════════════\n"
                )

        if (total_vouchers + total_ledgers + total_items) > 0 or not is_incremental:
            print(f"🎉 [DATABASE UPDATED] Synced {total_vouchers} Vouchers, {total_ledgers} Ledgers, {total_items} Items for '{self.active_company_name}'! (Errors: {total_errors})\n")
        else:
            print(f"   ✨ 0 changes detected in Tally. Database is up-to-date. (Errors: {total_errors})\n")

        self.last_inbound_time = time.time()

    def run_single_cycle(self):
        """Runs a single pass of discovery, inbound, and outbound synchronization."""
        print_banner()
        self.discover_and_report()
        self.sync_inbound_cycle(is_incremental=False)
        synced = self.sync_outbound_cycle()
        print(f"🏁 Single sync cycle completed. Synced {synced} outbound tasks.")

    def run_daemon(self):
        """Runs continuously in the background."""
        print_banner()
        self.discover_and_report()

        # Run initial baseline inbound sync to populate project DB right away
        self.sync_inbound_cycle(is_incremental=False)

        print(f"🔄 Starting background sync daemon (outbound: {self.config.sync_interval_seconds}s, inbound: {self.config.inbound_interval_seconds}s)...")
        print(f"Press Ctrl + C at any time to exit.\n")

        while running:
            try:
                # 1. Outbound Sync (Cloud -> Tally)
                self.sync_outbound_cycle()

                # 2. Periodic Incremental Inbound Sync (Tally -> Cloud DB)
                if (time.time() - self.last_inbound_time) >= self.config.inbound_interval_seconds:
                    self.sync_inbound_cycle(is_incremental=True)

                # Sleep interval
                for _ in range(self.config.sync_interval_seconds):
                    if not running:
                        break
                    time.sleep(1)

            except Exception as e:
                logger.error(f"Error in sync daemon loop: {e}", exc_info=True)
                time.sleep(5)

        print("\n👋 MyTally Desktop Sync Agent stopped cleanly.")

def install_startup():
    """Registers the agent into Windows Startup Registry to launch automatically on boot."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE
        )
        if getattr(sys, 'frozen', False):
            cmd = f'"{os.path.abspath(sys.executable)}"'
        else:
            cmd = f'"{sys.executable}" "{os.path.abspath(__file__)}"'
            
        winreg.SetValueEx(key, "MyTallySyncAgent", 0, winreg.REG_SZ, cmd)
        winreg.CloseKey(key)
        print("🎉 [AUTOSTART ENABLED] MyTally Sync Agent will now launch automatically on Windows system start!")
        return True
    except Exception as e:
        print(f"❌ Failed to configure Windows autostart: {e}")
        return False

def uninstall_startup():
    """Removes the agent from Windows Startup Registry."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE
        )
        winreg.DeleteValue(key, "MyTallySyncAgent")
        winreg.CloseKey(key)
        print("ℹ️ [AUTOSTART DISABLED] MyTally Sync Agent removed from Windows system startup.")
        return True
    except Exception as e:
        print(f"❌ Failed to remove Windows autostart: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="MyTally Windows Desktop Sync Agent")
    parser.add_argument("--test-once", action="store_true", help="Run a single discovery & sync pass then exit")
    parser.add_argument("--discover", action="store_true", help="Run Tally host discovery only")
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
