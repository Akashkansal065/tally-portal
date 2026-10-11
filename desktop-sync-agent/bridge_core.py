"""
What the MyTally Bridge window does, apart from drawing it: sign-in, sign-up, companies, settings and the
one-sentence sync health. Both windows use it: the web one (webview_app.py) and the CustomTkinter one
(gui_app.py), which runs where Edge WebView2 is missing.

A "host" below is whatever holds the running agent: it has .config (AgentConfig), .config_file and .agent.
"""

import os
import re
import sys
import time
import subprocess
from typing import Optional, Dict, Any, List, Tuple

from config import save_config, install_startup, uninstall_startup, get_logs_dir, hold_single_instance
from tally_client import TallyClient
from cloud_client import CloudClient

APP_NAME = "MyTally Bridge"
APP_SHORT = "Bridge"
APP_VERSION = "2.0.0"
DEFAULT_TALLY_URL = "http://127.0.0.1:9000"
THEMES = ("system", "light", "dark")

# The agent's own log lines carry emoji; the Activity page shows them without
_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿⏩-⏺️]+\\s*")


def log_line(message: str, level: str) -> Tuple[str, str]:
    """A log message as the Activity page shows it: (text without emoji, "error" / "warning" / "success" / "info")."""
    tag = "info"
    if level in ("ERROR", "CRITICAL") or "❌" in message:
        tag = "error"
    elif level == "WARNING" or "⚠️" in message:
        tag = "warning"
    elif "✅" in message or "🎉" in message or "SUCCESS" in message:
        tag = "success"
    return _EMOJI.sub("", message), tag


def health_from_status(status: Dict[str, Any]) -> Dict[str, str]:
    """The one state the health bar shows: its kind ("idle", "paused", "sync", "ok", "warn" or "error"),
    headline, detail line and what the main button does ("sync", "resume", "retry" or "signin"). The most
    urgent condition wins."""
    last = status.get("last_sync_status") or ""
    state = status.get("status", "")
    if status.get("auth_halt_reason"):
        blocked = status["auth_halt_reason"] in ("blocked", "device_blocked")
        return {"kind": "error", "title": "This PC was blocked by an admin" if blocked else "This PC was signed out",
                "detail": status.get("auth_halt_message") or "", "action": "signin"}
    if state == "PAUSED":
        return {"kind": "paused", "title": "Syncing is paused", "detail": "Changes will sync when you resume.", "action": "resume"}
    if state == "SYNCING":
        name = status.get("active_company_name") or "your companies"
        return {"kind": "sync", "title": f"Syncing {name}", "detail": "This can take a while for a large company.", "action": "sync"}
    if state == "TALLY OFFLINE":
        return {"kind": "error", "title": "Can't reach TallyPrime",
                "detail": "Open TallyPrime on this PC. Syncing resumes on its own once it is back.", "action": "retry"}
    if state == "CLOUD OFFLINE":
        return {"kind": "error", "title": "Can't reach the MyTally server",
                "detail": status.get("cloud_message") or "Check the internet connection. Bridge keeps trying.", "action": "retry"}
    lowered = last.lower()
    if any(sign in lowered for sign in ("failed", "not open", "close one", "no company is linked")):
        return {"kind": "warn", "title": "Syncing, with something to check", "detail": last, "action": "sync"}
    synced_at = status.get("last_sync_time")
    if not synced_at:
        return {"kind": "idle", "title": "Ready", "detail": "Waiting for the first sync.", "action": "sync"}
    if time.time() - synced_at < 6:
        return {"kind": "ok", "title": "Synced just now", "detail": last, "action": "sync"}
    return {"kind": "idle", "title": "Up to date", "detail": f"Last synced {status.get('last_sync_timestr', '')}", "action": "sync"}


def check_single_instance() -> bool:
    """Ensures only one sync agent runs at a time, window or command line; brings the open window forward."""
    if hold_single_instance():
        return True
    if sys.platform == "win32":
        try:
            import ctypes
            user32 = ctypes.windll.user32
            hwnd = user32.FindWindowW(None, APP_NAME)
            if hwnd:
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                user32.SetForegroundWindow(hwnd)
        except Exception:
            pass
    return False


def get_asset_path(filename: str, folder: str = "assets") -> str:
    """Finds a bundled file in sys._MEIPASS (PyInstaller bundled), next to executable, or in source."""
    candidates = []

    # 1. PyInstaller extraction directory
    if getattr(sys, '_MEIPASS', None):
        candidates.append(os.path.join(sys._MEIPASS, folder, filename))
        candidates.append(os.path.join(sys._MEIPASS, filename))

    # 2. Executable or script base directory
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base = os.path.dirname(os.path.abspath(__file__))

    candidates.append(os.path.join(base, folder, filename))
    candidates.append(os.path.join(base, filename))

    for c in candidates:
        if os.path.exists(c):
            return c
    return candidates[0] if candidates else filename


# The dot on the tray icon, per health kind (the light-theme solid colours)
STATE_SOLID = {"idle": "#8A8D9C", "paused": "#8A8D9C", "sync": "#5367FF", "ok": "#00B386", "warn": "#E5A100", "error": "#EB5B3C"}


def tray_image(base=None, kind: str = "idle"):
    """The app icon (a PIL image, or None for a plain green tile) with the sync state as a dot in its corner."""
    from PIL import Image, ImageDraw
    image = (base or Image.new("RGBA", (64, 64), "#008565")).convert("RGBA").resize((64, 64))
    ImageDraw.Draw(image).ellipse((38, 38, 63, 63), fill=STATE_SOLID.get(kind, STATE_SOLID["idle"]), outline="#FFFFFF", width=3)
    return image


def has_credentials(config) -> bool:
    return bool(config.backend_url and (config.device_token or config.auth_token or (config.email and config.password)))


# ---------------------------------------------------------------------------
# TallyPrime and the server, before sign-in
# ---------------------------------------------------------------------------
def detect_tally(tally_url: str) -> Dict[str, str]:
    """What is at the TallyPrime address, as one line to show: {"company", "text", "kind"}."""
    info = TallyClient(tally_url=tally_url or DEFAULT_TALLY_URL).discover_tally_host()
    if not info.get("connected"):
        return {"company": "", "kind": "error", "text": "Can't find TallyPrime. Open it on this PC, then press Detect."}
    name = info.get("company_name") or ""
    if not name:
        return {"company": "", "kind": "warn", "text": "TallyPrime is running, but no company is open. Open your company, then press Detect."}
    return {"company": name, "kind": "ok", "text": f"Found in TallyPrime: '{name}'."}


def test_connection(backend_url: str, email: str, password: str, tally_url: str) -> Dict[str, str]:
    t_info = TallyClient(tally_url=tally_url).discover_tally_host()
    c_client = CloudClient(backend_url=backend_url, email=email, password=password)
    cloud_ok, _ = c_client.check_health()
    auth_ok, auth_msg = False, ""
    if email and password:
        auth_ok, auth_msg = c_client.authenticate(email, password)

    t_ok = t_info.get("connected", False)
    lines = []
    if t_ok:
        lines.append(f"TallyPrime: connected ({t_info.get('company_name') or 'no company open'}).")
    else:
        lines.append("TallyPrime: not reachable. Open it on this PC.")
    if cloud_ok:
        if auth_ok:
            lines.append("Server: signed in.")
        elif password:
            lines.append(f"Server: reachable, but sign-in failed ({auth_msg}).")
        else:
            lines.append("Server: reachable.")
    else:
        lines.append(f"Server: can't connect to {backend_url or 'the address given'}.")
    overall_ok = t_ok and cloud_ok and (auth_ok or not password)
    return {"text": " ".join(lines), "kind": "ok" if overall_ok else ("warn" if (t_ok or cloud_ok) else "error")}


# ---------------------------------------------------------------------------
# Sign in: with email and password, or with a code entered in the MyTally app
# ---------------------------------------------------------------------------
def sign_in_pc(host, backend_url: str, email: str, password: str, tally_url: str, company_name: str,
               autostart: bool) -> Tuple[bool, str, bool]:
    """Sign this PC in and save that. Returns (ok, why not, signed in as a device). A PC signed in as a device
    still has its company to link (link_active_company) before syncing starts."""
    cloud_client = CloudClient(backend_url=backend_url, email=email, password=password)
    cloud_client.check_health()

    token = ""
    device_token = ""
    if email and password:
        # Sign this PC in. A server from before PC sign-in answers 404: use the person's login as before.
        signed_in, sign_res, sign_status = cloud_client.sign_in_device(email, password)
        if signed_in:
            device_token = sign_res["device_token"]
        elif sign_status == 404:
            auth_ok, auth_res = cloud_client.authenticate(email, password)
            if auth_ok:
                token = auth_res
            else:
                return False, f"Sign-in failed: {auth_res}", False
        else:
            return False, f"Sign-in failed: {sign_res}", False

    config = host.config
    config.backend_url = backend_url
    config.email = email
    config.username = email
    # A signed-in PC keeps no password: its device token is the sign-in
    config.password = "" if device_token else password
    config.auth_token = token
    config.device_token = device_token
    # Re-entering credentials resumes an agent an admin had signed out (a blocked PC still can't sign in)
    config.auth_halt_reason = ""
    config.tally_url = tally_url
    if company_name:
        if company_name != config.company_name:
            # A different company: drop the old pin, or the agent keeps waiting for the previous one.
            # The new company's GUID is pinned the first time it's seen open in Tally.
            config.company_guid = ""
        config.company_name = company_name
    config.autostart_enabled = autostart

    save_config(config, host.config_file)

    # Handle autostart registry
    if autostart:
        install_startup()
    else:
        uninstall_startup()

    host.agent.reload_config(config)
    return True, "", bool(device_token)


def company_details(company: Dict[str, Any], tally_url: str) -> Dict[str, Any]:
    """An open Tally company as the server is told about it when it is linked."""
    return {"tally_guid": company["guid"], "name": company["name"],
            "books_from": company.get("starting_from") or None, "tally_url": tally_url,
            "fingerprint": company.get("fingerprint") or None}


def start_code_sign_in(backend_url: str) -> Tuple[bool, Any]:
    """Ask the server for a code to show. Returns (ok, {"code", "poll_token", "expires_in_minutes"} or why not)."""
    client = CloudClient(backend_url=backend_url)
    client.check_health()
    return client.start_code_sign_in()


def finish_code_sign_in(host, backend_url: str, poll_token: str, tally_url: str, company_name: str,
                        autostart: bool) -> Tuple[str, str]:
    """Ask whether the code has been entered in the MyTally app. Returns ("pending", ""), ("error", why) or
    ("approved", ""): this PC is then signed in and that is saved. Its company is still to be linked
    (link_active_company), as after signing in with email and password."""
    state, signed = CloudClient(backend_url=backend_url).collect_code_sign_in(poll_token)
    if state != "approved":
        return state, "" if state == "pending" else str(signed)
    cfg = host.config
    email = (signed.get("user") or {}).get("email") or ""
    cfg.backend_url, cfg.email, cfg.username, cfg.tally_url = backend_url, email, email, tally_url
    cfg.password, cfg.auth_token, cfg.auth_halt_reason = "", "", ""
    cfg.device_token = signed["device_token"]
    if company_name:
        if company_name != cfg.company_name:
            cfg.company_guid = ""   # a different company: its GUID is pinned when it is next seen open in Tally
        cfg.company_name = company_name
    cfg.autostart_enabled = autostart
    save_config(cfg, host.config_file)
    if autostart:
        install_startup()
    else:
        uninstall_startup()
    host.agent.reload_config(cfg)
    return "approved", ""


# ---------------------------------------------------------------------------
# Companies
# ---------------------------------------------------------------------------
def companies_overview(agent) -> Dict[str, Any]:
    """The companies this PC syncs and the ones open in Tally that it could, each with the line to show under
    its name. "open" keeps the full Tally records by GUID, for linking one."""
    if not agent.cloud.device_mode:
        return {"device_mode": False, "linked": [], "unlinked": [], "open": {}, "any_open": False}
    open_cmps = agent.tally.get_open_companies()
    linked = [dict(c) for c in agent.linked_companies() if c.get("guid")]
    open_by_guid = {c.get("guid"): c for c in open_cmps if c.get("guid")}
    linked_guids = {c["guid"] for c in linked}
    names_open = [c.get("name") for c in open_cmps]
    rows: List[Dict[str, str]] = []
    for company in linked:
        now = open_by_guid.get(company["guid"])
        if now is None:
            note, kind = "Closed in Tally. Open it there to sync it.", "idle"
        elif names_open.count(now["name"]) > 1:
            note, kind = "Two open companies share this name, so it is not syncing. Close one.", "warn"
        else:
            note, kind = "Syncing from this PC", "ok"
        rows.append({"guid": company["guid"], "name": (now or company)["name"], "note": note, "kind": kind})
    unlinked = [{"guid": c["guid"], "name": c["name"], "note": "Not synced from this PC", "kind": "idle"}
                for c in open_cmps if c.get("guid") and c["guid"] not in linked_guids]
    return {"device_mode": True, "linked": rows, "unlinked": unlinked, "open": open_by_guid, "any_open": bool(open_cmps)}


# ---------------------------------------------------------------------------
# Settings and logs
# ---------------------------------------------------------------------------
def split_tally_url(tally_url: str) -> Tuple[str, str]:
    host_part, port_part = "localhost", "9000"
    t_url = tally_url or DEFAULT_TALLY_URL
    if "//" in t_url:
        raw = t_url.split("//", 1)[1]
        if ":" in raw:
            host_part, port_part = raw.split(":", 1)
            port_part = port_part.split("/")[0]
    return host_part, port_part


def apply_settings(host, values: Dict[str, Any]) -> Tuple[bool, str]:
    """Save the Settings page. values: tally_host, tally_port, backend_url, outbound_seconds, inbound_seconds,
    vouchers_per_range, auto_discover_paths, force_full_sync, autostart."""
    try:
        out_sec = int(str(values.get("outbound_seconds") or "5").strip())
        in_sec = int(str(values.get("inbound_seconds") or "60").strip())
        per_range = int(str(values.get("vouchers_per_range") or "25").strip())
    except ValueError:
        return False, "The schedule and vouchers per request must be whole numbers."

    tally_host = str(values.get("tally_host") or "").strip() or "localhost"
    tally_port = str(values.get("tally_port") or "").strip() or "9000"
    autostart = bool(values.get("autostart"))
    config = host.config
    config.tally_url = f"http://{tally_host}:{tally_port}"
    config.backend_url = str(values.get("backend_url") or "").strip()
    config.sync_interval_seconds = max(1, out_sec)
    config.inbound_interval_seconds = max(5, in_sec)
    config.vouchers_per_range = max(1, per_range)
    config.auto_discover_paths = bool(values.get("auto_discover_paths"))
    config.force_full_sync = bool(values.get("force_full_sync"))
    config.autostart_enabled = autostart

    save_config(config, host.config_file)

    if autostart:
        install_startup()
    else:
        uninstall_startup()

    host.agent.reload_config(config)
    return True, "Saved"


def open_logs_folder() -> Tuple[bool, str]:
    log_dir = get_logs_dir()
    try:
        if sys.platform == "win32":
            os.startfile(log_dir)
        elif sys.platform == "darwin":
            subprocess.run(["open", log_dir])
        else:
            subprocess.run(["xdg-open", log_dir])
        return True, ""
    except Exception as e:
        return False, f"Could not open the folder: {e}"


def export_logs_zip() -> Tuple[bool, str]:
    import zipfile
    from datetime import datetime
    log_dir = get_logs_dir()
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    if not os.path.exists(desktop):
        desktop = log_dir

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = os.path.join(desktop, f"MyTallyBridge_Logs_{ts}.zip")
    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for fn in ["agent.log", "tally_traffic.log"]:
                fp = os.path.join(log_dir, fn)
                if os.path.exists(fp):
                    zf.write(fp, arcname=fn)
        return True, f"Exported to the Desktop: {os.path.basename(zip_path)}"
    except Exception as e:
        return False, f"Could not export the logs: {e}"
