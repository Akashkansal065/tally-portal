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
    hold_single_instance,
    install_startup as cfg_install_startup,
    uninstall_startup as cfg_uninstall_startup
)
from tally_client import TallyClient, escape_xml, NETWORK_ERROR_PREFIX
from cloud_client import CloudClient, halt_message, SYNC_BUSY_REASON
from xml.sax.saxutils import unescape

# A full voucher sync is cut into date ranges of about this many vouchers each, so neither Tally nor the
# server is given everything at once (a proxy in front of the server waits only so long for an answer).
# Settings can change it (config.vouchers_per_range). A company with no more vouchers than one range is
# exported whole.
VOUCHERS_PER_RANGE = 50
# Every kind of record the server reports back after an import, in the order they are synced
IMPORTED_KINDS = (
    ("imported_groups", "Groups"), ("imported_ledgers", "Ledgers"), ("imported_voucher_types", "Voucher types"),
    ("imported_currencies", "Currencies"), ("imported_stock_groups", "Stock groups"), ("imported_uoms", "Units"),
    ("imported_godowns", "Godowns"), ("imported_stock_categories", "Stock categories"),
    ("imported_cost_categories", "Cost categories"), ("imported_cost_centres", "Cost centres"),
    ("imported_attendance_types", "Attendance types"), ("imported_stock_items", "Stock items"),
    ("imported_vouchers", "Vouchers"),
)
# How long one company's full sync may run in a cycle before the other companies, and the entries waiting to
# reach Tally, get their turn. It carries on in the next cycle.
FULL_SYNC_SLICE_SECONDS = 90
# A plan older than this is made again: its counts no longer describe what is in Tally
FULL_SYNC_PLAN_MAX_AGE_SECONDS = 6 * 3600
SERVER_BUSY_MESSAGE = "the server is still importing this company's previous sync."


def plan_voucher_ranges(dates: List[str], per_range: int = VOUCHERS_PER_RANGE) -> List[List[Any]]:
    """Cut a company's voucher dates (YYYYMMDD) into consecutive ranges of about per_range vouchers.
    Each range is [first date, last date, vouchers in it]; ranges start and end on dates that have vouchers,
    never overlap, and together cover every voucher. One busy day is never split."""
    counts: Dict[str, int] = {}
    for day in dates:
        counts[day] = counts.get(day, 0) + 1
    ranges: List[List[Any]] = []
    start, held = None, 0
    for day in sorted(counts):
        start = start or day
        held += counts[day]
        if held >= per_range:
            ranges.append([start, day, held])
            start, held = None, 0
    if start is not None:
        ranges.append([start, max(counts), held])
    return ranges


_SV_CURRENT_COMPANY = re.compile(r"<SVCURRENTCOMPANY>(.*?)</SVCURRENTCOMPANY>", re.DOTALL)


def unescape_xml(text: str) -> str:
    return unescape(text, {"&quot;": '"', "&apos;": "'"})

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
    # Whether this Tally returns vouchers by date range, and by which request: not known until tried
    _voucher_ranges_work: Optional[bool] = None
    _voucher_range_method: Optional[str] = None
    _restart_full_sync = False
    # Company GUID -> the highest master and voucher ALTERIDs the cloud held at the last cycle, for the state report
    _watermarks: Dict[str, Tuple[int, int]] = {}
    _last_push_error = ""

    def __init__(self, config_path: Optional[str] = None):
        # Default to the file next to the script/.exe (gitignored), never the current working directory
        self.config_path = config_path or get_default_config_path()
        self.config: AgentConfig = load_config(config_path)
        self.tally = TallyClient(tally_url=self.config.tally_url)
        self.cloud = self._new_cloud_client()
        self.last_inbound_time = 0
        self.active_company_name = self.config.company_name
        self.active_company_guid = getattr(self.config, "company_guid", "") or ""
        self.cloud.company_guid = self.active_company_guid
        self.company_paused = False
        self.open_companies_count = 0
        # Each linked company as last resolved against Tally: name, GUID and open / closed / ambiguous
        self.company_states: List[Dict[str, str]] = []
        self._last_skip_note = ""

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
        self._watermarks = {}
        self.last_sync_time = None
        self.last_sync_timestr = "Never"
        self.last_sync_status = "Ready"
        self._server_counts: Optional[Dict[str, int]] = None   # what the server holds for the active company
        self._cycle_counts: Dict[str, int] = {}                # what the server added or changed this cycle
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
            "linked_companies_count": len(self.linked_companies()),
            "tally_release": self.tally_release,
            # What the server holds for the company on screen. Falls back to what this run has sent, for a
            # server too old to say; that number grows with every repeated sync and is not a count of records.
            "total_vouchers": (self._server_counts or {}).get("vouchers", self.total_vouchers),
            "total_ledgers": (self._server_counts or {}).get("ledgers", self.total_ledgers),
            "total_items": (self._server_counts or {}).get("stock_items", self.total_items),
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
        self.cloud = self._new_cloud_client()
        self.active_company_name = self.config.company_name
        self.active_company_guid = getattr(self.config, "company_guid", "") or ""
        self.cloud.company_guid = self.active_company_guid
        self.company_paused = False
        logger.info("🔄 Agent configuration reloaded.")

    def _new_cloud_client(self) -> CloudClient:
        # Signed in as this PC: the device token is the sign-in, and no password is kept or sent
        device_token = getattr(self.config, "device_token", "") or ""
        return CloudClient(
            backend_url=self.config.backend_url,
            token=device_token or self.config.auth_token,
            email="" if device_token else (self.config.email or self.config.username),
            password="" if device_token else self.config.password,
            on_token_refreshed=self._on_token_refreshed,
            auth_halt_reason=self.config.auth_halt_reason,
            on_auth_halted=self._on_auth_halted
        )

    def tally_company_to_link(self) -> Optional[Dict[str, Any]]:
        """The Tally company this agent is tied to, as the cloud needs it for linking: found among the companies
        open in Tally by GUID once pinned, by name before that. None when it is not open."""
        open_cmps = self.tally.get_open_companies()
        match = next((c for c in open_cmps if self.active_company_guid and c.get("guid") == self.active_company_guid), None)
        if match is None and not self.active_company_guid:
            match = next((c for c in open_cmps if c.get("name") == self.active_company_name), None)
        if match is None or not match.get("guid"):
            return None
        return {"tally_guid": match["guid"], "name": match["name"], "books_from": match.get("starting_from") or None,
                "tally_url": self.config.tally_url}

    def link_active_company(self, take_over: bool = False) -> Tuple[bool, str, str]:
        """Make this PC the one that syncs the agent's company. Returns (ok, message, reason)."""
        company = self.tally_company_to_link()
        if company is None:
            return False, f"'{self.active_company_name}' is not open in Tally. Open it and try again.", "not_open"
        return self.link_company(company, take_over=take_over)

    def link_company(self, company: Dict[str, Any], take_over: bool = False) -> Tuple[bool, str, str]:
        """Make this PC the one that syncs a company open in Tally ({"tally_guid", "name", ...}), and keep
        syncing it from now on. Returns (ok, message, reason)."""
        ok, body, reason = self.cloud.link_company(company, take_over=take_over)
        if not ok:
            return False, str(body), reason
        guid, name = company["tally_guid"], company["name"]
        linked = [dict(c) for c in self.linked_companies() if c.get("guid")]
        if guid not in [c["guid"] for c in linked]:
            linked.append({"guid": guid, "name": name})
        self.config.companies = linked
        self.config.company_guid, self.config.company_name = linked[0]["guid"], linked[0]["name"]
        self.active_company_guid, self.active_company_name = linked[0]["guid"], linked[0]["name"]
        self.cloud.company_guid = self.active_company_guid
        save_config(self.config, self.config_path)
        logger.info(f"🔗 '{name}' is now synced from this PC.")
        return True, "", ""

    def unlink_company(self, guid: str) -> bool:
        """Stop syncing a company from this PC. Its data in the cloud stays, and another PC can link it."""
        if not self.cloud.unlink_company(guid):
            return False
        remaining = [dict(c) for c in self.linked_companies() if c.get("guid") != guid]
        self.config.companies = remaining
        first = remaining[0] if remaining else {"guid": "", "name": ""}
        self.config.company_guid, self.config.company_name = first["guid"], first["name"]
        self.active_company_guid, self.active_company_name = first["guid"], first["name"]
        self.cloud.company_guid = self.active_company_guid
        (self.config.inbound_retry_floors or {}).pop(guid, None)
        save_config(self.config, self.config_path)
        logger.info("🔗 A company was unlinked from this PC.")
        return True

    def _on_token_refreshed(self, new_token: str):
        self.config.auth_token = new_token
        save_config(self.config, self.config_path)

    def _on_auth_halted(self, reason: str):
        """The server signed this PC out on purpose or blocked it: stop syncing until credentials are re-entered."""
        self.config.auth_halt_reason = reason
        self.config.auth_token = ""
        self.config.device_token = ""
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
        elif self.cloud.device_mode:
            logger.info("🔑 Signed in as this PC.")
        elif self.config.email and self.config.password:
            auth_ok, auth_res = self.cloud.authenticate(self.config.email, self.config.password)
            if auth_ok:
                logger.info(f"🔑 Authenticated as '{self.config.email}' successfully.")
                self.config.auth_token = auth_res
                save_config(self.config, self.config_path)
            else:
                logger.warning(f"⚠️ Authentication failed: {auth_res}. Using cached token.")
        
        return tally_info.get("connected", False) and cloud_ok

    def linked_companies(self) -> List[Dict[str, str]]:
        """The Tally companies this PC syncs. Before any company was linked from this agent there is the one
        company it has always been tied to."""
        linked = [c for c in (getattr(self.config, "companies", None) or []) if c.get("guid") or c.get("name")]
        if linked:
            return linked
        if self.active_company_guid or self.active_company_name:
            return [{"guid": self.active_company_guid, "name": self.active_company_name}]
        return []

    def resolve_companies(self) -> List[Dict[str, str]]:
        """
        Each linked company as it stands in Tally right now: "open", "closed", or "ambiguous" when two open
        companies carry its name. A company is followed by its GUID; its name is only what Tally shows today,
        and is all Tally accepts to address it, so two open companies with one name cannot be told apart safely.
        """
        open_cmps = self.tally.get_open_companies()
        self.open_companies_count = len(open_cmps)
        same_name: Dict[str, int] = {}
        for c in open_cmps:
            same_name[c.get("name", "")] = same_name.get(c.get("name", ""), 0) + 1
        legacy_single = not (getattr(self.config, "companies", None) or [])
        if not open_cmps:
            # Tally did not say what is open (not running, or not answering). As before, the cycle goes on:
            # nothing can be written to a Tally that is not there, and the cloud is still asked, which is how
            # a PC learns it was signed out.
            return [{"guid": c.get("guid") or "", "name": c.get("name") or "", "state": "open"} for c in self.linked_companies()]

        resolved, changed = [], False
        for entry in self.linked_companies():
            guid, name = entry.get("guid") or "", entry.get("name") or ""
            if guid:
                match = next((c for c in open_cmps if c.get("guid") == guid), None)
            else:
                # Not pinned yet: found by name once, then followed by GUID (a same-name restore is another company)
                match = next((c for c in open_cmps if c.get("name") == name), None)
            if match is None:
                resolved.append({"guid": guid, "name": name, "state": "closed"})
                continue
            if (not guid and match.get("guid")) or match["name"] != name:
                guid, name, changed = guid or match.get("guid", ""), match["name"], True   # a rename in Tally is fine
                entry["guid"], entry["name"] = guid, name
            state = "ambiguous" if same_name.get(name, 0) > 1 else "open"
            resolved.append({"guid": guid, "name": name, "state": state, "starting_from": match.get("starting_from", ""),
                             "fingerprint": match.get("fingerprint", "")})

        if resolved and (legacy_single or changed):
            first = resolved[0]
            if (first["guid"], first["name"]) != (self.config.company_guid, self.config.company_name) and first["state"] != "closed":
                self.config.company_guid, self.config.company_name = first["guid"], first["name"]
                changed = True
        if changed:
            save_config(self.config, self.config_path)
        return resolved

    def _activate(self, company: Dict[str, str]) -> None:
        """Point the agent and its cloud calls at one company for the work that follows."""
        if company["guid"] != self.active_company_guid:
            self._server_counts = None      # the tiles show one company's records, never the last one's
        self.active_company_name, self.active_company_guid = company["name"], company["guid"]
        self.cloud.company_guid = self.active_company_guid
        self.cloud.company_fingerprint = company.get("fingerprint", "")

    def _companies_to_work_on(self) -> List[Dict[str, str]]:
        """Resolve the linked companies, note what is stopping the others, and return the ones that can be synced."""
        companies = self.resolve_companies()
        self.company_states = companies
        workable = [c for c in companies if c["state"] == "open"]
        skipped = [c for c in companies if c["state"] != "open"]
        note = "; ".join(self._why_skipped(c) for c in skipped)
        if note != self._last_skip_note:
            self._last_skip_note = note
            if note:
                logger.warning(f"⏸️ {note}")
        self.company_paused = not workable
        if companies:
            # What the rest of the agent and the window call "the company" is the first linked one
            self._activate(workable[0] if workable else companies[0])
        return workable

    @staticmethod
    def _why_skipped(company: Dict[str, str]) -> str:
        if company["state"] == "ambiguous":
            return f"Two companies named '{company['name']}' are open in Tally; close one to sync it"
        return f"'{company['name']}' is not open in Tally"

    def _address_to_active_company(self, xml_payload: str, task_company_guid: Optional[str]) -> Tuple[str, Optional[str]]:
        """
        Check a queued payload is for the Tally company this agent is tied to. Returns (payload, why it must not
        be sent or None).

        When the server says which Tally company the task belongs to (by GUID), that decides, and the payload is
        addressed to the name Tally shows for that company right now (the server may still hold an older name).
        A server that does not say is trusted only as far as the company name in the payload matches.
        """
        m_cmp = _SV_CURRENT_COMPANY.search(xml_payload)
        if task_company_guid and self.active_company_guid:
            if task_company_guid != self.active_company_guid:
                return xml_payload, (f"it is for Tally company GUID {task_company_guid}, and this agent is tied to "
                                     f"'{self.active_company_name}' (GUID {self.active_company_guid}).")
            if m_cmp and self.active_company_name:
                xml_payload = xml_payload[:m_cmp.start(1)] + escape_xml(self.active_company_name) + xml_payload[m_cmp.end(1):]
            return xml_payload, None
        if m_cmp and self.active_company_name and unescape_xml(m_cmp.group(1)).strip() != self.active_company_name:
            return xml_payload, (f"it is addressed to company '{unescape_xml(m_cmp.group(1)).strip()}', and this agent is "
                                 f"tied to '{self.active_company_name}'.")
        return xml_payload, None

    def _paused_status(self) -> str:
        states = getattr(self, "company_states", None) or []
        if not states:
            return "Paused: no company is linked to this PC"
        return "Paused: " + "; ".join(self._why_skipped(c) for c in states if c["state"] != "open")

    def sync_outbound_cycle(self) -> int:
        """Pulls pending voucher/ledger creation requests from Cloud and pushes them to Tally."""
        if self.cloud.auth_halt_reason:
            return 0
        workable = self._companies_to_work_on()
        if not workable:
            # Shown in the GUI: nothing is sent to Tally until a linked company is open again
            self.last_sync_status = self._paused_status()
            return 0
        done = 0
        for company in workable:   # one company at a time: Tally answers one request at a time
            self._activate(company)
            try:
                done += self._sync_outbound_company()
            except Exception as e:   # one company's trouble never stops the others
                logger.error(f"Outbound sync for '{company['name']}' failed: {e}", exc_info=True)
        self._activate(workable[0])
        return done

    def _sync_outbound_company(self) -> int:
        """Outbound work for the company the agent is pointed at."""
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

            xml_payload, refusal = self._address_to_active_company(xml_payload, task.get("company_guid"))
            if refusal:
                logger.error(f"⛔ Not sending {rec_type} #{rec_id} ({action}) to Tally: {refusal}")
                continue

            # Ensure SVCURRENTCOMPANY is explicitly set in STATICVARIABLES to avoid multi-company cross-talk
            if "<SVCURRENTCOMPANY>" not in xml_payload and self.active_company_name:
                esc_cmp = escape_xml(self.active_company_name)
                sv_tag = f"<STATICVARIABLES><SVCURRENTCOMPANY>{esc_cmp}</SVCURRENTCOMPANY>"
                if "<STATICVARIABLES>" in xml_payload:
                    xml_payload = xml_payload.replace("<STATICVARIABLES>", sv_tag)
                elif "<DESC>" in xml_payload:
                    xml_payload = xml_payload.replace("<DESC>", f"<DESC><STATICVARIABLES><SVCURRENTCOMPANY>{esc_cmp}</SVCURRENTCOMPANY></STATICVARIABLES>")

            if "<SVCURRENTCOMPANY>" not in xml_payload and "svCurrentCompany" not in xml_payload:
                # Without it Tally writes to whichever company is in front of the operator
                logger.error(f"⛔ Not sending {rec_type} #{rec_id} ({action}) to Tally: the payload names no company.")
                continue

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
                # Tally answering that the thing to delete is not there means the delete is already done (it was
                # sent before and the answer was lost, or it never reached Tally in the first place)
                if not is_network_failure and str(action or "").lower() == "delete" and "does not exist" in resp_str.lower():
                    logger.info(f"✅ {rec_type} #{rec_id} is already gone from Tally. Acknowledging the delete.")
                    successful_ids.append(sync_id)
                    recovered = True
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
        if self.cloud.auth_halt_reason:
            return
        workable = self._companies_to_work_on()
        if not workable:
            self.last_sync_status = self._paused_status()
            self._report_company_states({})
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

        # A requested full sync (Sync All, or force_full_sync) applies to every company in this pass
        force_all = getattr(self.config, "force_full_sync", False) or self.force_full_sync_next
        # "Sync All" was pressed: a full sync that is under way starts again. The standing force_full_sync
        # setting does not restart one, or a sync that needs several cycles would never finish.
        self._restart_full_sync = self.force_full_sync_next
        self.force_full_sync_next = False
        outcomes: Dict[str, Tuple[bool, str]] = {}
        statuses = []
        for company in workable:   # one company at a time: Tally answers one request at a time
            self._activate(company)
            try:
                ok = self._sync_inbound_company(is_incremental, force_all)
                outcomes[company["guid"]] = (ok, "" if ok else self.last_sync_status)
            except Exception as e:   # one company's trouble never stops the others
                logger.error(f"Inbound sync for '{company['name']}' failed: {e}", exc_info=True)
                outcomes[company["guid"]] = (False, str(e))
                self.last_sync_status = f"Sync failed: {e}"
            statuses.append(self.last_sync_status if len(workable) == 1 else f"{company['name']}: {self.last_sync_status}")
        self._activate(workable[0])
        skipped = [self._why_skipped(c) for c in self.company_states if c["state"] != "open"]
        self.last_sync_status = " | ".join(statuses + skipped)
        self._report_company_states(outcomes)

    def _report_company_states(self, outcomes: Dict[str, Tuple[bool, str]]) -> None:
        """Tell the cloud how each linked company stands, closed ones included: the app's "Last synced"."""
        reports = []
        for company in getattr(self, "company_states", None) or []:
            if not company.get("guid"):
                continue
            ok, error = outcomes.get(company["guid"], (False, ""))
            state = {"closed": "closed", "ambiguous": "ambiguous"}.get(company["state"], "live" if ok else "error")
            report = {"tally_guid": company["guid"], "state": state, "ok": ok and company["state"] == "open",
                      "error": error or None, "fingerprint": company.get("fingerprint") or None,
                      "progress": self._full_sync_progress(company["guid"]) or None}
            masters, vouchers = self._watermarks.get(company["guid"], (None, None))
            if masters is not None:
                report["master_alter_id"], report["voucher_alter_id"] = masters, vouchers
            reports.append(report)
        if reports:
            try:
                self.cloud.report_state(reports)
            except Exception as e:
                logger.debug(f"Could not report sync state: {e}")

    def _sync_inbound_company(self, is_incremental: bool, force_all: bool = False) -> bool:
        """Inbound work for the company the agent is pointed at. True when the whole pass was clean."""
        self._last_company_ok = False
        self.is_syncing = True
        try:
            if force_all:
                is_incremental = False

            # Per company and by GUID: a failure in one company never moves another's retry point
            company_key = self.active_company_guid or self.active_company_name
            floors = self.config.inbound_retry_floors or {}
            if self.active_company_guid and self.active_company_name in floors and company_key not in floors:
                floors[company_key] = floors.pop(self.active_company_name)   # kept by name before GUIDs were used
                self.config.inbound_retry_floors = floors
            retry_floor = floors.get(company_key)

            # Vouchers of a full sync are pulled in date ranges when the Tally client can do it. A full sync
            # that is under way (or one that failed at the start, which leaves a retry point of 0) carries on
            # here rather than falling back to one export of everything.
            can_range = hasattr(self.tally, "export_voucher_index") and self._voucher_ranges_work is not False
            if force_all and self._restart_full_sync:
                self._drop_full_sync_cursor(company_key)   # "Sync All" starts again from the beginning
            if can_range and is_incremental and retry_floor == 0:
                is_incremental = False
            vouchers_in_ranges = can_range and (not is_incremental or company_key in (self.config.full_sync_cursors or {}))

            min_alter = 0
            min_voucher_alter = 0
            if is_incremental:
                # Masters and vouchers have separate change counters in Tally, hence separate watermarks
                master_watermark, voucher_watermark = self.cloud.get_last_alter_id()
                self._watermarks[company_key] = (master_watermark, voucher_watermark)
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
            if vouchers_in_ranges and not is_incremental:
                collections = self.tally.export_full_collections(self.active_company_name, min_alter_id=0,
                                                                 min_voucher_alter_id=None, skip_vouchers=True)
            else:
                collections = self.tally.export_full_collections(self.active_company_name, min_alter_id=min_alter,
                                                                 min_voucher_alter_id=min_voucher_alter if is_incremental else None)
            export_failures = list(getattr(self.tally, "last_export_failures", []) or [])
            if export_failures:
                logger.error(f"   ❌ Could not export from Tally: {', '.join(export_failures)}")

            if not collections and not vouchers_in_ranges:
                self._update_inbound_retry_floor(company_key, min(min_alter, min_voucher_alter) if is_incremental else min_alter, failed=bool(export_failures))
                self._last_company_ok = not export_failures
                self.last_inbound_time = time.time()
                self.last_sync_time = time.time()
                self.last_sync_timestr = time.strftime("%d %b %Y, %I:%M:%S %p")
                if export_failures:
                    self.last_sync_status = f"Tally export failed ({', '.join(export_failures)})"
                else:
                    logger.info("   ✨ 0 changes detected in Tally. Database is 100% up-to-date.")
                    self.last_sync_status = "Up-to-date (0 changes)"
                    if self._server_counts is None:
                        self._refresh_server_counts()
                return self._last_company_ok

            self._cycle_counts = {}
            total_vouchers, total_ledgers, total_items, total_errors = self._push_collections(collections, force_all)

            # Vouchers of a full sync come in date ranges, a slice at a time (see _sync_vouchers_in_ranges)
            range_failed = False
            if vouchers_in_ranges and not (export_failures or total_errors):
                ranged = self._sync_vouchers_in_ranges(company_key, force_all)
                if ranged is None:
                    # Too few vouchers to be worth cutting up, or this Tally does not honour a date range
                    whole = self.tally.export_full_collections(self.active_company_name, min_alter_id=0,
                                                               min_voucher_alter_id=None, only_vouchers=True)
                    export_failures += list(getattr(self.tally, "last_export_failures", []) or [])
                    if export_failures:
                        logger.error(f"   ❌ Could not export from Tally: {', '.join(export_failures)}")
                    pushed = self._push_collections(whole, force_all)
                    total_vouchers += pushed[0]
                    total_errors += pushed[3]
                else:
                    range_ok, range_vouchers = ranged
                    total_vouchers += range_vouchers
                    range_failed = not range_ok

            self.total_vouchers += total_vouchers
            self.total_ledgers += total_ledgers
            self.total_items += total_items
            self.total_errors += total_errors
            self._update_inbound_retry_floor(company_key, min(min_alter, min_voucher_alter) if is_incremental else min_alter, failed=bool(export_failures) or total_errors > 0)
            self._last_company_ok = not (export_failures or total_errors > 0 or range_failed)
            self.last_sync_time = time.time()
            self.last_sync_timestr = time.strftime("%d %b %Y, %I:%M:%S %p")

            if total_errors and self._last_push_error:
                # The server's own words (a company refused as a different copy, for one) reach the status line
                self.last_sync_status = f"Sync failed: {self._last_push_error}"
            elif (total_vouchers + total_ledgers + total_items) > 0 or not is_incremental:
                msg = f"🎉 [DATABASE UPDATED] Synced {total_vouchers} Vouchers, {total_ledgers} Ledgers, {total_items} Items for '{self.active_company_name}'! (Errors: {total_errors})"
                logger.info(msg)
                self._refresh_server_counts()
                self._log_cycle_summary()
                self.last_sync_status = f"Synced {total_vouchers} Vouchers, {total_ledgers} Ledgers"
            else:
                msg = f"   ✨ 0 changes detected in Tally. Database is up-to-date. (Errors: {total_errors})"
                logger.info(msg)
                self.last_sync_status = "Up-to-date"

            progress = self._full_sync_progress(company_key)
            if progress:
                self.last_sync_status += f" · {progress}"
            self.last_inbound_time = time.time()
        finally:
            self.is_syncing = False
        return self._last_company_ok

    def _note_imported(self, res: Dict[str, Any]) -> str:
        """Add one push's counts to the cycle's totals. Returns them as text, every kind the server changed."""
        parts = []
        for key, name in IMPORTED_KINDS:
            n = int(res.get(key) or 0)
            if n:
                self._cycle_counts[key] = self._cycle_counts.get(key, 0) + n
                parts.append(f"{name}: {n}")
        return ", ".join(parts) or "nothing new or changed"

    def _log_cycle_summary(self):
        """One block at the end of a sync: every kind of record, what the server added or changed, and what
        it now holds."""
        logger.info(f"   📊 Sync summary for '{self.active_company_name}' (new or changed on the server):")
        for key, name in IMPORTED_KINDS:
            logger.info(f"      {name + ':':<18}{self._cycle_counts.get(key, 0)}")
        if self._server_counts:
            held = self._server_counts
            logger.info(f"      Server now holds:  {held.get('vouchers', 0)} vouchers, {held.get('ledgers', 0)} ledgers, "
                        f"{held.get('stock_items', 0)} stock items")

    def _refresh_server_counts(self):
        ask = getattr(self.cloud, "get_server_counts", None)
        counts = ask() if ask else None
        if counts is not None:
            self._server_counts = counts

    def _push_collections(self, collections: List[Tuple[str, str]], force_all: bool) -> Tuple[int, int, int, int]:
        """Push exported collections to the cloud. Returns (vouchers, ledgers, items imported, pushes that failed)."""
        total_vouchers = total_ledgers = total_items = total_errors = total_record_errors = 0
        self._last_push_error = ""
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
                logger.info(f"   • ✅ '{label}' Synced in {dur:.2f}s ({self._note_imported(res)})")
                record_errors = res.get("errors") or []
                if record_errors:
                    # Individual records the server rejected. They would fail the same way on a re-pull,
                    # so they are reported rather than retried; fix them in Tally and they re-sync on next edit.
                    total_record_errors += len(record_errors)
                    logger.warning(f"   ⚠️ '{label}': {len(record_errors)} record(s) rejected by the server, e.g. {record_errors[:3]}")
            elif res.get("reason") == SYNC_BUSY_REASON:
                # Not sent again and again while the server works: the rest of this cycle would be refused too
                total_errors += 1
                self._last_push_error = SERVER_BUSY_MESSAGE
                logger.warning(f"   ⏳ '{label}' not sent: {SERVER_BUSY_MESSAGE} It is sent again next cycle.")
                break
            else:
                total_errors += 1
                err_type = res.get("error_type", "SYNC_ERROR")
                err_msg = res.get("error", "Unknown error")
                self._last_push_error = str(err_msg)[:300]
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
        return total_vouchers, total_ledgers, total_items, total_errors

    # ─── Full voucher sync in date ranges ────────────────────────────────────────

    def _save_full_sync_cursor(self, company_key: str, cursor: Optional[Dict[str, Any]]) -> None:
        cursors = dict(self.config.full_sync_cursors or {})
        if cursor is None:
            cursors.pop(company_key, None)
        else:
            cursors[company_key] = cursor
        self.config.full_sync_cursors = cursors
        save_config(self.config, self.config_path)

    def _drop_full_sync_cursor(self, company_key: str) -> None:
        if company_key in (self.config.full_sync_cursors or {}):
            self._save_full_sync_cursor(company_key, None)

    def _full_sync_progress(self, company_key: str) -> str:
        """"Full sync 3 of 12" while one is under way, else ''."""
        cursor = (self.config.full_sync_cursors or {}).get(company_key)
        if not cursor or not cursor.get("ranges"):
            return ""
        return f"Full sync {cursor.get('next', 0)} of {len(cursor['ranges'])}"

    def _export_voucher_range(self, date_from: str, date_to: str, expected: int):
        """The vouchers of one range, checked: every voucher returned is dated inside the range and none the
        plan counted is missing. Returns the export, None when Tally did not answer (try again later), or
        False when Tally does not honour a date range at all (the caller exports everything in one go)."""
        from tally_client import VOUCHER_RANGE_METHODS, voucher_dates
        methods = [self._voucher_range_method] if self._voucher_range_method else list(VOUCHER_RANGE_METHODS)
        recounted = False
        for method in methods:
            xml_data = self.tally.export_vouchers_between(self.active_company_name, date_from, date_to, method)
            if xml_data is None:
                return None
            got = voucher_dates(xml_data)
            if any(not (date_from <= day <= date_to) for day in got):
                logger.debug(f"   Tally returned vouchers outside {date_from}..{date_to} with the '{method}' request.")
                continue
            if len(got) < expected and not recounted:
                # A voucher may have been deleted or re-dated since the plan was made: count again before
                # concluding that the request loses vouchers
                recounted = True
                fresh = self.tally.export_voucher_index(self.active_company_name)
                if fresh is None:
                    return None
                expected = sum(1 for day in fresh if date_from <= day <= date_to)
            if len(got) < expected:
                logger.debug(f"   Tally returned {len(got)} of {expected} vouchers for {date_from}..{date_to} with the '{method}' request.")
                continue
            self._voucher_range_method = method
            return xml_data
        return False

    def _vouchers_per_range(self) -> int:
        try:
            return max(1, int(getattr(self.config, "vouchers_per_range", None) or VOUCHERS_PER_RANGE))
        except (TypeError, ValueError):
            return VOUCHERS_PER_RANGE

    def _replan_remaining_ranges(self, company_key: str, cursor: Dict[str, Any], per_range: int) -> Optional[Dict[str, Any]]:
        """The range size was changed while a full sync is under way: plan what is left again at the new
        size. The ranges already done stay done. None when Tally did not answer (try again later)."""
        ranges, position = cursor["ranges"], cursor["next"]
        dates = self.tally.export_voucher_index(self.active_company_name)
        if dates is None:
            return None
        date_from = ranges[position][0]
        cursor["ranges"] = ranges[:position] + plan_voucher_ranges([day for day in dates if day >= date_from], per_range)
        cursor["per_range"] = per_range
        self._save_full_sync_cursor(company_key, cursor)
        logger.info(f"   🗓️ The rest of the full sync is planned again in ranges of about {per_range} vouchers "
                    f"({len(cursor['ranges'])} ranges in all).")
        return cursor

    def _sync_vouchers_in_ranges(self, company_key: str, force_all: bool) -> Optional[Tuple[bool, int]]:
        """Carry a full voucher sync forward by one time slice: plan it if it has no plan, then export and push
        range after range, saving the position after each. Returns (clean, vouchers imported), or None when
        the vouchers should be exported in one go instead (few vouchers, or Tally ignores date ranges)."""
        cursor = (self.config.full_sync_cursors or {}).get(company_key)
        if cursor and cursor.get("ranges") and time.time() - cursor.get("planned_at", 0) > FULL_SYNC_PLAN_MAX_AGE_SECONDS:
            logger.info("   🗓️ The full sync plan is old; planning it again.")
            cursor = {"ranges": None, "next": 0, "force": cursor.get("force", False), "planned_at": 0}
        per_range = self._vouchers_per_range()
        if cursor is None:
            # Written before anything else, so a full sync that could not even be planned is still owed
            cursor = {"ranges": None, "next": 0, "force": force_all, "planned_at": 0}
            self._save_full_sync_cursor(company_key, cursor)
        if not cursor.get("ranges"):
            dates = self.tally.export_voucher_index(self.active_company_name)
            if dates is None:
                logger.error("   ❌ Could not list the vouchers in Tally; the full sync will be tried again.")
                return False, 0
            if len(dates) <= per_range:
                self._drop_full_sync_cursor(company_key)
                return None
            cursor = {"ranges": plan_voucher_ranges(dates, per_range), "next": 0, "force": cursor.get("force", False),
                      "planned_at": time.time(), "per_range": per_range}
            self._save_full_sync_cursor(company_key, cursor)
            logger.info(f"   🗓️ Full sync of {len(dates)} vouchers planned in {len(cursor['ranges'])} date ranges.")
        elif cursor.get("per_range") != per_range and cursor["next"] < len(cursor["ranges"]):
            # Also a plan saved by an agent that had one fixed size and did not record it
            cursor = self._replan_remaining_ranges(company_key, cursor, per_range)
            if cursor is None:
                logger.error("   ❌ Could not list the vouchers in Tally; the full sync will be tried again.")
                return False, 0

        ranges = cursor["ranges"]
        deadline = time.time() + FULL_SYNC_SLICE_SECONDS
        imported = 0
        while cursor["next"] < len(ranges):
            date_from, date_to, expected = ranges[cursor["next"]]
            label = f"Vouchers {date_from}–{date_to} ({cursor['next'] + 1}/{len(ranges)})"
            xml_data = self._export_voucher_range(date_from, date_to, expected)
            if xml_data is False:
                logger.warning("   ⚠️ This Tally does not return vouchers by date range; exporting them in one go instead.")
                self._voucher_ranges_work = False
                self._drop_full_sync_cursor(company_key)
                return None
            if xml_data is None:
                logger.error(f"   ❌ Could not export '{label}' from Tally; the full sync carries on from here next cycle.")
                return False, imported
            ok, res = self.cloud.push_inbound_xml(xml_data, self.active_company_name, force=bool(cursor.get("force")))
            if not ok and res.get("reason") == SYNC_BUSY_REASON:
                logger.warning(f"   ⏳ '{label}' not sent: {SERVER_BUSY_MESSAGE} The full sync carries on from here next cycle.")
                return False, imported
            if not ok:
                logger.error(f"   ❌ '{label}' could not be pushed ({res.get('error', 'unknown error')}); "
                             "the full sync carries on from here next cycle.")
                return False, imported
            imported += res.get("imported_vouchers", 0)
            self._note_imported(res)
            # The server only counts what it added or changed; a voucher it already holds unchanged is not counted
            logger.info(f"   • ✅ '{label}' sent: {expected} vouchers, {res.get('imported_vouchers', 0)} new or changed on the server")
            cursor["next"] += 1
            self._save_full_sync_cursor(company_key, cursor)
            if time.time() >= deadline:
                break
        if cursor["next"] >= len(ranges):
            self._drop_full_sync_cursor(company_key)
            logger.info(f"   🎉 Full voucher sync of '{self.active_company_name}' finished ({len(ranges)} ranges).")
        else:
            logger.info(f"   ⏸️ Full sync paused at {cursor['next']} of {len(ranges)} ranges; it carries on in the next cycle.")
        return True, imported

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

    if not args.discover and not hold_single_instance():
        print("Another SnehDistribuors Sync Agent is already running on this PC (look in the system tray). "
              "Two agents would sync the same companies at once, so this one has not started.")
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
