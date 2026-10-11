"""
MyTally Bridge — the web window. The page in ui/ draws it inside Edge WebView2 (pywebview); this file is what
the page can ask for. Where WebView2 or pywebview is missing, gui_app.py opens the CustomTkinter window instead.

The page never holds a secret: sign-in tokens stay in this process, and passwords pass through once, on sign-in.
"""

import os
import sys
import time
import platform
import threading
from collections import deque
from typing import Optional, Dict, Any, List, Tuple

import bridge_core as core
from bridge_core import APP_NAME, APP_SHORT, APP_VERSION
from config import load_config, save_config, AgentConfig, is_autostart_registered, get_default_config_path

# Edge WebView2 Runtime's registration: per machine (64-bit and 32-bit views) or per user
_WEBVIEW2_KEYS = (
    ("HKLM", r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
    ("HKLM", r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
    ("HKCU", r"Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
)


def available() -> bool:
    """Can the web window open here? Needs pywebview, the page files and, on Windows, the WebView2 runtime
    (part of Windows 11; most Windows 10 PCs have it). Without it pywebview would fall back to the old
    Internet Explorer engine, which cannot draw this page."""
    if not os.path.exists(core.get_asset_path("index.html", "ui")):
        return False
    try:
        import webview  # noqa: F401
    except Exception:
        return False
    if sys.platform != "win32":
        return True
    try:
        import winreg
        for hive, key in _WEBVIEW2_KEYS:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE if hive == "HKLM" else winreg.HKEY_CURRENT_USER, key) as k:
                    version, _ = winreg.QueryValueEx(k, "pv")
                    if version and version != "0.0.0.0":
                        return True
            except OSError:
                continue
    except Exception:
        pass
    return False


class Session:
    """The running agent and what the window needs around it. Also the "host" bridge_core works on."""

    def __init__(self, config_file: Optional[str] = None):
        from agent import DesktopSyncAgent
        self.config_file = config_file or get_default_config_path()
        self.config: AgentConfig = load_config(self.config_file)
        self.agent = DesktopSyncAgent(config_path=self.config_file)
        self.worker_thread: Optional[threading.Thread] = None
        # Log lines as the Activity page shows them, each with a running number so the page asks only for new ones
        self._logs: deque = deque(maxlen=1000)
        self._log_seq = 0
        self._log_lock = threading.Lock()
        self.agent.add_log_listener(self._on_agent_log)

    def _on_agent_log(self, msg: str, level: str):
        text, tag = core.log_line(msg, level)
        with self._log_lock:
            self._log_seq += 1
            self._logs.append((self._log_seq, text, tag))

    def logs_since(self, seq: int) -> Tuple[List[Dict[str, str]], int]:
        with self._log_lock:
            return [{"text": text, "tag": tag} for n, text, tag in self._logs if n > seq], self._log_seq

    def clear_logs(self):
        with self._log_lock:
            self._logs.clear()

    def start_sync(self):
        if self.worker_thread and self.worker_thread.is_alive():
            return
        self.worker_thread = threading.Thread(target=self.agent.run_daemon, daemon=True)
        self.worker_thread.start()


class Api:
    """What the page can call, as window.pywebview.api.<name>(...). pywebview runs each call on its own thread,
    so these may take as long as Tally or the server takes. Every answer is plain JSON. Only the methods
    without a leading underscore are reachable from the page."""

    def __init__(self, session: Session):
        self._session = session
        self._window = None
        self._on_quit = None
        self._open_companies: Dict[str, Dict[str, Any]] = {}   # what Tally had open at the last look, by GUID
        self._code_sign_in: Optional[Dict[str, str]] = None    # the code on screen: its server and its secret
        self._lock = threading.Lock()                          # one sign-in request at a time

    # -- start and state ----------------------------------------------------
    def boot(self) -> Dict[str, Any]:
        cfg = self._session.config
        return {
            "app": {"name": APP_NAME, "short": APP_SHORT, "version": APP_VERSION, "pc": platform.node() or "This PC"},
            "signed_in": core.has_credentials(cfg),
            "theme": cfg.theme if cfg.theme in core.THEMES else "system",
            "setup": {"server": cfg.backend_url or "", "tally": cfg.tally_url or core.DEFAULT_TALLY_URL,
                      "email": cfg.email or cfg.username or "", "company": cfg.company_name or "",
                      "autostart": bool(cfg.autostart_enabled or is_autostart_registered())},
        }

    def state(self, since: int = 0) -> Dict[str, Any]:
        agent = self._session.agent
        status = agent.get_status()
        health = core.health_from_status(status)
        logs, seq = self._session.logs_since(int(since or 0))
        # A requested sync shows as busy from the click until the agent has picked it up and finished it
        busy = bool(status.get("is_syncing") or (agent.immediate_sync_requested and health["action"] in ("sync", "retry")))
        return {"health": health, "busy": busy, "paused": bool(status.get("is_paused")),
                "tally_ok": bool(status.get("tally_connected")), "cloud_ok": bool(status.get("cloud_connected")),
                "halted": bool(status.get("auth_halt_reason")),
                "syncing_name": status.get("active_company_name") if status.get("is_syncing") else None,
                "logs": logs, "seq": seq}

    # -- syncing ------------------------------------------------------------
    def sync_now(self) -> Dict[str, Any]:
        self._session.agent.trigger_immediate_sync(force_full=False)
        return {"ok": True}

    def full_resync(self) -> Dict[str, Any]:
        self._session.agent.trigger_immediate_sync(force_full=True)
        return {"ok": True}

    def pause(self) -> Dict[str, Any]:
        self._session.agent.pause()
        return {"ok": True}

    def resume(self) -> Dict[str, Any]:
        self._session.agent.resume()
        return {"ok": True}

    # -- companies ----------------------------------------------------------
    def companies(self) -> Dict[str, Any]:
        overview = core.companies_overview(self._session.agent)
        self._open_companies = overview.pop("open")
        return overview

    def link_company(self, guid: str, take_over: bool = False) -> Dict[str, Any]:
        """Linking is always a choice made in the window: the agent never starts syncing a company just
        because it is open."""
        company = self._open_companies.get(guid)
        if not company:
            return {"ok": False, "message": "That company is no longer open in TallyPrime. Press Refresh.", "reason": ""}
        details = core.company_details(company, self._session.config.tally_url)
        ok, message, reason = self._session.agent.link_company(details, take_over=bool(take_over))
        if ok:
            self._session.agent.trigger_immediate_sync()
        return {"ok": ok, "message": str(message), "reason": reason}

    def unlink_company(self, guid: str) -> Dict[str, Any]:
        return {"ok": bool(self._session.agent.unlink_company(guid))}

    # -- settings and logs --------------------------------------------------
    def settings(self) -> Dict[str, Any]:
        cfg = self._session.config
        tally_host, tally_port = core.split_tally_url(cfg.tally_url)
        return {"tally_host": tally_host, "tally_port": tally_port, "backend_url": cfg.backend_url or "",
                "outbound_seconds": cfg.sync_interval_seconds or 5, "inbound_seconds": cfg.inbound_interval_seconds or 60,
                "vouchers_per_range": cfg.vouchers_per_range or 25, "auto_discover_paths": bool(cfg.auto_discover_paths),
                "force_full_sync": bool(getattr(cfg, "force_full_sync", False)),
                "autostart": bool(cfg.autostart_enabled or is_autostart_registered()),
                "theme": cfg.theme if cfg.theme in core.THEMES else "system",
                "email": cfg.email or cfg.username or ""}

    def save_settings(self, values: Dict[str, Any]) -> Dict[str, Any]:
        ok, message = core.apply_settings(self._session, values or {})
        return {"ok": ok, "message": message}

    def set_theme(self, theme: str) -> Dict[str, Any]:
        if theme not in core.THEMES:
            return {"ok": False}
        self._session.config.theme = theme
        save_config(self._session.config, self._session.config_file)
        return {"ok": True}

    def open_logs(self) -> Dict[str, Any]:
        ok, message = core.open_logs_folder()
        return {"ok": ok, "message": message}

    def export_logs(self) -> Dict[str, Any]:
        ok, message = core.export_logs_zip()
        return {"ok": ok, "message": message}

    def clear_logs(self) -> Dict[str, Any]:
        self._session.clear_logs()
        return {"ok": True}

    # -- first run ----------------------------------------------------------
    def detect_tally(self, tally_url: str = "") -> Dict[str, str]:
        return core.detect_tally(str(tally_url or "").strip())

    def test_connection(self, values: Dict[str, Any]) -> Dict[str, str]:
        v = values or {}
        return core.test_connection(str(v.get("server") or "").strip(), str(v.get("email") or "").strip(),
                                    str(v.get("password") or ""), str(v.get("tally") or "").strip())

    def sign_in(self, values: Dict[str, Any]) -> Dict[str, Any]:
        """Sign this PC in, link the chosen company and start syncing. If another PC syncs that company the
        answer says so (reason "linked_to_another_device") and the page asks before link_active(True)."""
        v = values or {}
        backend_url = str(v.get("server") or "").strip()
        if not backend_url:
            return {"ok": False, "message": "Enter the server address under Advanced.", "reason": ""}
        if not self._lock.acquire(blocking=False):
            return {"ok": False, "message": "Still signing in. Give it a moment.", "reason": ""}
        try:
            ok, message, as_device = core.sign_in_pc(
                self._session, backend_url, str(v.get("email") or "").strip(), str(v.get("password") or ""),
                str(v.get("tally") or "").strip(), str(v.get("company") or "").strip(), bool(v.get("autostart")))
            if not ok:
                return {"ok": False, "message": message, "reason": ""}
            if as_device:
                return self._link_active(False)
            self._session.start_sync()
            return {"ok": True}
        finally:
            self._lock.release()

    def link_active(self, take_over: bool = False) -> Dict[str, Any]:
        return self._link_active(bool(take_over))

    def _link_active(self, take_over: bool) -> Dict[str, Any]:
        """Make this PC the one syncing the chosen company, then start syncing."""
        ok, message, reason = self._session.agent.link_active_company(take_over=take_over)
        if ok:
            self._session.start_sync()
            return {"ok": True}
        if reason == "linked_to_another_device":
            return {"ok": False, "message": str(message), "reason": reason}
        return {"ok": False, "message": f"Signed in, but the company could not be linked: {message}", "reason": reason or ""}

    def code_start(self, values: Dict[str, Any]) -> Dict[str, Any]:
        """Sign in with a code, step 1: get the code to show. The secret that goes with it stays here."""
        backend_url = str((values or {}).get("server") or "").strip()
        if not backend_url:
            return {"ok": False, "message": "Enter the server address under Advanced."}
        if not self._lock.acquire(blocking=False):
            return {"ok": False, "message": "Still working. Give it a moment."}
        try:
            ok, body = core.start_code_sign_in(backend_url)
            if not ok:
                return {"ok": False, "message": str(body)}
            self._code_sign_in = {"server": backend_url, "poll_token": body["poll_token"]}
            return {"ok": True, "code": body["code"], "minutes": int(body.get("expires_in_minutes") or 10)}
        finally:
            self._lock.release()

    def code_check(self, values: Dict[str, Any]) -> Dict[str, Any]:
        """Step 2, asked every few seconds: has the code been entered in the app? Once it has, this PC is
        signed in and its company is linked as after sign_in. Answers {"status": "pending" | "done" | "error"}."""
        v = values or {}
        pending = self._code_sign_in
        if pending is None:
            return {"status": "error", "ok": False, "message": "Ask for a new code.", "reason": ""}
        if not self._lock.acquire(blocking=False):
            return {"status": "pending"}
        try:
            state, message = core.finish_code_sign_in(
                self._session, pending["server"], pending["poll_token"], str(v.get("tally") or "").strip(),
                str(v.get("company") or "").strip(), bool(v.get("autostart")))
            if state == "pending":
                return {"status": "pending"}
            self._code_sign_in = None
            if state == "error":
                return {"status": "error", "ok": False, "message": message, "reason": ""}
            return {"status": "done", **self._link_active(False)}
        finally:
            self._lock.release()

    # -- window -------------------------------------------------------------
    def hide(self) -> Dict[str, Any]:
        if self._window is not None:
            self._window.hide()
        return {"ok": True}

    def quit(self) -> Dict[str, Any]:
        if self._on_quit:
            threading.Thread(target=self._on_quit, daemon=True).start()
        return {"ok": True}


class Tray:
    """The tray icon. It is the whole interface most of the day, so it carries the same state as the health bar."""

    def __init__(self, session: Session, show, quit_app):
        self._session, self._show, self._quit = session, show, quit_app
        self._icon = None
        self._shown: Tuple[str, str] = ("", "")
        self._notice_shown = False
        self._base = None

    def start(self):
        if sys.platform == "darwin":   # pystray needs the main thread there, and the window has it
            return
        try:
            import pystray
            from pystray import MenuItem as item
            from PIL import Image
            png = core.get_asset_path("icon.png")
            self._base = Image.open(png) if os.path.exists(png) else None
            agent = self._session.agent
            menu = (
                item(f"Open {APP_SHORT}", lambda icon=None, item=None: self._show(), default=True),
                item("Sync now", lambda icon=None, item=None: agent.trigger_immediate_sync(force_full=False)),
                item("Full re-sync", lambda icon=None, item=None: agent.trigger_immediate_sync(force_full=True)),
                item("Pause or resume syncing", lambda icon=None, item=None: agent.resume() if agent.is_paused else agent.pause()),
                pystray.Menu.SEPARATOR,
                item(f"Quit {APP_SHORT}", lambda icon=None, item=None: self._quit()),
            )
            self._icon = pystray.Icon("SnehDistribuorsSync", core.tray_image(self._base), APP_NAME, menu)
            threading.Thread(target=self._icon.run, daemon=True).start()
            threading.Thread(target=self._follow, daemon=True).start()
        except Exception as e:
            print(f"System tray initialization notice: {e}")

    def _follow(self):
        """Keep the icon's dot and tooltip on the current sync state, window open or not."""
        while True:
            time.sleep(1)
            try:
                if not core.has_credentials(self._session.config):
                    continue
                health = core.health_from_status(self._session.agent.get_status())
                state = (health["kind"], health["title"])
                if state != self._shown and self._icon is not None:
                    self._shown = state
                    self._icon.icon = core.tray_image(self._base, health["kind"])
                    self._icon.title = f"{APP_NAME}: {health['title']}"[:120]   # Windows cuts tooltips at 127
            except Exception:
                pass

    def notify_hidden(self):
        if self._icon is not None and not self._notice_shown:
            self._notice_shown = True
            try:
                self._icon.notify(f"{APP_SHORT} keeps syncing in the background.", APP_NAME)
            except Exception:
                pass

    def stop(self):
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass


def run() -> None:
    """Open the web window and stay until Quit. Call available() first."""
    import webview

    session = Session()
    api = Api(session)
    signed_in = core.has_credentials(session.config)
    start_hidden = signed_in and ("--tray" in sys.argv or "--minimized" in sys.argv)

    window = webview.create_window(APP_NAME, url=core.get_asset_path("index.html", "ui"), js_api=api,
                                   width=920, height=600, min_size=(760, 520), hidden=start_hidden, text_select=True)
    api._window = window

    def show():
        window.show()
        try:
            window.restore()
        except Exception:
            pass

    def quit_app():
        session.agent.stop()
        tray.stop()
        try:
            window.destroy()
        except Exception:
            pass
        os._exit(0)

    tray = Tray(session, show, quit_app)
    api._on_quit = quit_app

    def on_closing():
        """When close (X) is clicked, hide to the tray so syncing continues. Without a tray icon to bring the
        window back, closing quits."""
        if tray._icon is None:
            threading.Thread(target=quit_app, daemon=True).start()
            return True
        window.hide()
        tray.notify_hidden()
        return False

    window.events.closing += on_closing
    tray.start()
    if signed_in:
        session.start_sync()
    webview.start(gui="edgechromium" if sys.platform == "win32" else None, debug="--debug-ui" in sys.argv)
    quit_app()
