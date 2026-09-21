"""
SnehDistribuors Desktop Sync Agent — Modern Windows GUI
Real-time synchronization bridge between TallyPrime and SnehDistribuors Cloud ERP.
"""

import os
import sys
import time
import queue
import logging
import threading
import subprocess
from typing import Optional, Dict, Any

import customtkinter as ctk
from PIL import Image, ImageTk
import pystray
from pystray import MenuItem as item

from config import (
    load_config,
    save_config,
    AgentConfig,
    install_startup,
    uninstall_startup,
    is_autostart_registered,
    get_default_config_path,
    get_logs_dir
)
from agent import DesktopSyncAgent
from tally_client import TallyClient
from cloud_client import CloudClient

# ---------------------------------------------------------------------------
# Appearance & Theme Configuration
# ---------------------------------------------------------------------------
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Theme Palette (Rich Slate & Vibrant Accents)
BG_COLOR = "#0F172A"         # Slate 900
CARD_BG = "#1E293B"          # Slate 800
CARD_BORDER = "#334155"      # Slate 700
INPUT_BG = "#0B1329"         # Slate 950
ACCENT_BLUE = "#2563EB"      # Blue 600
ACCENT_HOVER = "#1D4ED8"     # Blue 700
SUCCESS_GREEN = "#10B981"    # Emerald 500
WARNING_AMBER = "#F59E0B"    # Amber 500
ERROR_RED = "#EF4444"        # Red 500
TEXT_MAIN = "#F8FAFC"        # Slate 50
TEXT_MUTED = "#94A3B8"       # Slate 400
# Global reference to prevent garbage collection of Windows single-instance mutex
_app_single_instance_mutex = None

def check_single_instance() -> bool:
    """Ensures only one instance of SnehDistribuorsSync runs at a time."""
    if sys.platform == "win32":
        try:
            import ctypes
            global _app_single_instance_mutex
            mutex_name = "Global\\SnehDistribuorsSyncAgent_SingleInstance_Mutex"
            kernel32 = ctypes.windll.kernel32
            _app_single_instance_mutex = kernel32.CreateMutexW(None, False, mutex_name)
            last_error = kernel32.GetLastError()
            ERROR_ALREADY_EXISTS = 183
            if last_error == ERROR_ALREADY_EXISTS:
                # Find and restore the existing window
                user32 = ctypes.windll.user32
                hwnd = user32.FindWindowW(None, "SnehDistribuors — Tally Sync Agent")
                if hwnd:
                    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                    user32.SetForegroundWindow(hwnd)
                return False
        except Exception:
            pass
    return True

def get_asset_path(filename: str) -> str:
    """Finds asset path in sys._MEIPASS (PyInstaller bundled), next to executable, or in source."""
    candidates = []
    
    # 1. PyInstaller extraction directory
    if getattr(sys, '_MEIPASS', None):
        candidates.append(os.path.join(sys._MEIPASS, "assets", filename))
        candidates.append(os.path.join(sys._MEIPASS, filename))
        
    # 2. Executable or script base directory
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
        
    candidates.append(os.path.join(base, "assets", filename))
    candidates.append(os.path.join(base, filename))
    
    for c in candidates:
        if os.path.exists(c):
            return c
    return candidates[0] if candidates else filename


# ---------------------------------------------------------------------------
# Main Application Window
# ---------------------------------------------------------------------------
class SnehDistribuorsApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("SnehDistribuors — Tally Sync Agent")
        self.geometry("640x780")
        self.minsize(580, 700)
        self.configure(fg_color=BG_COLOR)

        # App Icon
        self.icon_path_ico = get_asset_path("icon.ico")
        self.icon_path_png = get_asset_path("icon.png")
        if os.path.exists(self.icon_path_ico) and sys.platform == "win32":
            try:
                self.iconbitmap(self.icon_path_ico)
            except Exception:
                pass
        
        self.pil_icon = None
        if os.path.exists(self.icon_path_png):
            try:
                self.pil_icon = Image.open(self.icon_path_png)
                self.tk_icon = ImageTk.PhotoImage(self.pil_icon)
                self.iconphoto(True, self.tk_icon)
            except Exception:
                pass

        # Load Configuration
        self.config_file = get_default_config_path()
        self.config: AgentConfig = load_config(self.config_file)

        # Agent & Background Worker
        self.agent = DesktopSyncAgent(config_path=self.config_file)
        self.worker_thread: Optional[threading.Thread] = None
        self.log_queue = queue.Queue()

        # Connect Agent Logger to Queue
        self.agent.add_log_listener(self._on_agent_log)

        # System Tray State
        self.tray_icon: Optional[pystray.Icon] = None
        self.is_minimized_to_tray = False
        self._init_system_tray()

        # Handle Window Close
        self.protocol("WM_DELETE_WINDOW", self._on_window_close)

        # Main Container
        self.container = ctk.CTkFrame(self, fg_color=BG_COLOR)
        self.container.pack(fill="both", expand=True, padx=16, pady=16)

        # Current view tracking
        self.current_frame: Optional[ctk.CTkFrame] = None

        # Determine start screen
        has_credentials = bool(self.config.backend_url and (self.config.auth_token or (self.config.email and self.config.password)))
        start_minimized = ("--tray" in sys.argv or "--minimized" in sys.argv)

        if has_credentials:
            self.show_dashboard()
            self.start_sync_thread()
            if start_minimized:
                self.after(200, self.minimize_to_tray)
        else:
            self.show_setup()

        # Periodic UI Status Refresh
        self.after(1000, self._periodic_status_refresh)

    # -----------------------------------------------------------------------
    # System Tray Integration
    # -----------------------------------------------------------------------
    def _init_system_tray(self):
        """Initializes pystray icon for background operation."""
        try:
            icon_img = self.pil_icon or Image.new('RGBA', (64, 64), (37, 99, 235, 255))
            tray_menu = (
                item("Open SnehDistribuors", self._tray_restore_window, default=True),
                item("Sync Delta Now", self._tray_sync_now),
                item("Sync All (Full Refresh)", self._tray_sync_all),
                item("Pause / Resume Sync", self._tray_toggle_pause),
                pystray.Menu.SEPARATOR,
                item("Exit", self._tray_exit_app)
            )
            self.tray_icon = pystray.Icon(
                "SnehDistribuorsSync",
                icon_img,
                "SnehDistribuors Tally Sync",
                tray_menu
            )
            tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
            tray_thread.start()
        except Exception as e:
            print(f"⚠️ System tray initialization notice: {e}")

    def _tray_restore_window(self, icon=None, item=None):
        self.after(0, self._restore_from_tray)

    def _restore_from_tray(self):
        self.deiconify()
        try:
            self.state("normal")
        except Exception:
            pass
        self.lift()
        self.focus_force()
        self.attributes("-topmost", True)
        self.attributes("-topmost", False)
        self.is_minimized_to_tray = False

    def minimize_to_tray(self):
        self.withdraw()
        self.is_minimized_to_tray = True
        if self.tray_icon:
            try:
                self.tray_icon.notify(
                    "SnehDistribuors Sync is running silently in the background.",
                    "Minimized to System Tray"
                )
            except Exception:
                pass

    def _tray_sync_now(self, icon=None, item=None):
        if self.agent:
            self.agent.trigger_immediate_sync(force_full=False)

    def _tray_sync_all(self, icon=None, item=None):
        if self.agent:
            self.agent.trigger_immediate_sync(force_full=True)

    def _tray_toggle_pause(self, icon=None, item=None):
        if self.agent:
            if self.agent.is_paused:
                self.agent.resume()
            else:
                self.agent.pause()

    def _tray_exit_app(self, icon=None, item=None):
        self.after(0, self._shutdown_app)

    def _on_window_close(self):
        """When close (X) is clicked, minimize to tray so syncing continues."""
        self.minimize_to_tray()

    def _shutdown_app(self):
        if self.agent:
            self.agent.stop()
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        try:
            self.destroy()
        except Exception:
            pass
        os._exit(0)

    # -----------------------------------------------------------------------
    # Logging & Thread Management
    # -----------------------------------------------------------------------
    def _on_agent_log(self, msg: str, level: str):
        self.log_queue.put((msg, level))

    def start_sync_thread(self):
        if self.worker_thread and self.worker_thread.is_alive():
            return
        self.worker_thread = threading.Thread(target=self.agent.run_daemon, daemon=True)
        self.worker_thread.start()

    # -----------------------------------------------------------------------
    # Screen Switching Helpers
    # -----------------------------------------------------------------------
    def show_setup(self):
        if self.current_frame:
            self.current_frame.destroy()
        self.current_frame = SetupView(self.container, self)
        self.current_frame.pack(fill="both", expand=True)

    def show_dashboard(self):
        if self.current_frame:
            self.current_frame.destroy()
        self.current_frame = DashboardView(self.container, self)
        self.current_frame.pack(fill="both", expand=True)

    def show_settings(self):
        if self.current_frame:
            self.current_frame.destroy()
        self.current_frame = SettingsView(self.container, self)
        self.current_frame.pack(fill="both", expand=True)

    # -----------------------------------------------------------------------
    # Status Polling Loop
    # -----------------------------------------------------------------------
    def _periodic_status_refresh(self):
        # 1. Update logs in dashboard if active
        if isinstance(self.current_frame, DashboardView):
            while not self.log_queue.empty():
                try:
                    msg, level = self.log_queue.get_nowait()
                    self.current_frame.append_log(msg, level)
                except queue.Empty:
                    break

            # 2. Update dashboard indicators
            status = self.agent.get_status()
            self.current_frame.update_status(status)

        self.after(1000, self._periodic_status_refresh)


# ---------------------------------------------------------------------------
# VIEW 1: Setup & Login Screen (Single-Page Unified Setup)
# ---------------------------------------------------------------------------
class SetupView(ctk.CTkFrame):
    def __init__(self, parent, app: SnehDistribuorsApp):
        super().__init__(parent, fg_color="transparent")
        self.app = app

        # Scrollable container for smaller screens
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True)

        self._build_header()
        self._build_cloud_card()
        self._build_tally_card()
        self._build_options_card()
        self._build_action_bar()

    def _build_header(self):
        header_box = ctk.CTkFrame(self.scroll, fg_color="transparent")
        header_box.pack(fill="x", pady=(8, 16))

        # Brand Icon & Title
        title_row = ctk.CTkFrame(header_box, fg_color="transparent")
        title_row.pack()

        if self.app.pil_icon:
            logo_img = ctk.CTkImage(light_image=self.app.pil_icon, dark_image=self.app.pil_icon, size=(44, 44))
            logo_label = ctk.CTkLabel(title_row, text="", image=logo_img)
            logo_label.pack(side="left", padx=(0, 12))

        brand_lbl = ctk.CTkLabel(
            title_row,
            text="SnehDistribuors",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=TEXT_MAIN
        )
        brand_lbl.pack(side="left")

        subtitle_lbl = ctk.CTkLabel(
            header_box,
            text="TallyPrime Real-Time Cloud Synchronization Agent",
            font=ctk.CTkFont(size=13),
            text_color=TEXT_MUTED
        )
        subtitle_lbl.pack(pady=(4, 0))

    def _build_cloud_card(self):
        card = ctk.CTkFrame(self.scroll, fg_color=CARD_BG, corner_radius=12, border_width=1, border_color=CARD_BORDER)
        card.pack(fill="x", pady=(0, 14), padx=4)

        title = ctk.CTkLabel(
            card,
            text="☁️  Cloud ERP Backend Connection",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=TEXT_MAIN
        )
        title.pack(anchor="w", padx=16, pady=(14, 10))

        # Cloud Backend URL
        ctk.CTkLabel(card, text="Cloud Server URL:", font=ctk.CTkFont(size=12), text_color=TEXT_MUTED).pack(anchor="w", padx=16)
        self.backend_url_entry = ctk.CTkEntry(
            card,
            placeholder_text="http://MacBook-Air.local:8000",
            fg_color=INPUT_BG,
            border_color=CARD_BORDER,
            height=36
        )
        self.backend_url_entry.insert(0, self.app.config.backend_url or "http://MacBook-Air.local:8000")
        self.backend_url_entry.pack(fill="x", padx=16, pady=(4, 10))

        # Email / Username
        ctk.CTkLabel(card, text="Account Email / Username:", font=ctk.CTkFont(size=12), text_color=TEXT_MUTED).pack(anchor="w", padx=16)
        self.email_entry = ctk.CTkEntry(
            card,
            placeholder_text="admin@snehdistributors.com",
            fg_color=INPUT_BG,
            border_color=CARD_BORDER,
            height=36
        )
        self.email_entry.insert(0, self.app.config.email or self.app.config.username or "")
        self.email_entry.pack(fill="x", padx=16, pady=(4, 10))

        # Password
        ctk.CTkLabel(card, text="Password:", font=ctk.CTkFont(size=12), text_color=TEXT_MUTED).pack(anchor="w", padx=16)
        pass_row = ctk.CTkFrame(card, fg_color="transparent")
        pass_row.pack(fill="x", padx=16, pady=(4, 16))

        self.password_entry = ctk.CTkEntry(
            pass_row,
            placeholder_text="••••••••",
            show="•",
            fg_color=INPUT_BG,
            border_color=CARD_BORDER,
            height=36
        )
        self.password_entry.insert(0, self.app.config.password or "")
        self.password_entry.pack(side="left", fill="x", expand=True)

        self.show_pass_btn = ctk.CTkButton(
            pass_row,
            text="👁",
            width=36,
            height=36,
            fg_color=CARD_BORDER,
            hover_color=CARD_BG,
            command=self._toggle_password
        )
        self.show_pass_btn.pack(side="left", padx=(8, 0))

    def _toggle_password(self):
        if self.password_entry.cget("show") == "•":
            self.password_entry.configure(show="")
        else:
            self.password_entry.configure(show="•")

    def _build_tally_card(self):
        card = ctk.CTkFrame(self.scroll, fg_color=CARD_BG, corner_radius=12, border_width=1, border_color=CARD_BORDER)
        card.pack(fill="x", pady=(0, 14), padx=4)

        title = ctk.CTkLabel(
            card,
            text="📊  TallyPrime Configuration",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=TEXT_MAIN
        )
        title.pack(anchor="w", padx=16, pady=(14, 10))

        # Tally URL
        ctk.CTkLabel(card, text="Tally XML Server URL (Local Port):", font=ctk.CTkFont(size=12), text_color=TEXT_MUTED).pack(anchor="w", padx=16)
        self.tally_url_entry = ctk.CTkEntry(
            card,
            placeholder_text="http://127.0.0.1:9000",
            fg_color=INPUT_BG,
            border_color=CARD_BORDER,
            height=36
        )
        self.tally_url_entry.insert(0, self.app.config.tally_url or "http://127.0.0.1:9000")
        self.tally_url_entry.pack(fill="x", padx=16, pady=(4, 10))

        # Company Name with Auto-Detect Button
        ctk.CTkLabel(card, text="Target Company Name (or auto-detect):", font=ctk.CTkFont(size=12), text_color=TEXT_MUTED).pack(anchor="w", padx=16)
        cmp_row = ctk.CTkFrame(card, fg_color="transparent")
        cmp_row.pack(fill="x", padx=16, pady=(4, 16))

        self.company_entry = ctk.CTkEntry(
            cmp_row,
            placeholder_text="Bhrama Enterprises",
            fg_color=INPUT_BG,
            border_color=CARD_BORDER,
            height=36
        )
        self.company_entry.insert(0, self.app.config.company_name or "")
        self.company_entry.pack(side="left", fill="x", expand=True)

        self.detect_btn = ctk.CTkButton(
            cmp_row,
            text="🔍 Auto-Detect",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=CARD_BORDER,
            hover_color=ACCENT_BLUE,
            height=36,
            command=self._detect_tally_company
        )
        self.detect_btn.pack(side="left", padx=(8, 0))

    def _build_options_card(self):
        card = ctk.CTkFrame(self.scroll, fg_color=CARD_BG, corner_radius=12, border_width=1, border_color=CARD_BORDER)
        card.pack(fill="x", pady=(0, 14), padx=4)

        self.autostart_var = ctk.BooleanVar(value=self.app.config.autostart_enabled or is_autostart_registered())
        self.autostart_chk = ctk.CTkCheckBox(
            card,
            text="Start automatically with Windows boot",
            variable=self.autostart_var,
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MAIN,
            fg_color=ACCENT_BLUE,
            hover_color=ACCENT_HOVER
        )
        self.autostart_chk.pack(anchor="w", padx=16, pady=14)

    def _build_action_bar(self):
        # Status feedback label
        self.status_lbl = ctk.CTkLabel(
            self.scroll,
            text="Configure your credentials and click Connect to start real-time syncing.",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MUTED,
            wraplength=540
        )
        self.status_lbl.pack(pady=(4, 10))

        btn_row = ctk.CTkFrame(self.scroll, fg_color="transparent")
        btn_row.pack(fill="x", pady=(0, 12))

        self.test_btn = ctk.CTkButton(
            btn_row,
            text="🧪 Test Connection",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=CARD_BORDER,
            hover_color=CARD_BG,
            height=42,
            corner_radius=8,
            command=self._run_connection_test
        )
        self.test_btn.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.connect_btn = ctk.CTkButton(
            btn_row,
            text="🚀 Connect & Start Sync",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=ACCENT_BLUE,
            hover_color=ACCENT_HOVER,
            height=42,
            corner_radius=8,
            command=self._connect_and_launch
        )
        self.connect_btn.pack(side="left", fill="x", expand=True, padx=(8, 0))

    def _detect_tally_company(self):
        t_url = self.tally_url_entry.get().strip() or "http://127.0.0.1:9000"
        self.detect_btn.configure(text="Detecting...", state="disabled")
        self.update()

        def worker():
            client = TallyClient(tally_url=t_url)
            info = client.discover_tally_host()
            self.after(0, lambda: self._on_detect_finish(info))

        threading.Thread(target=worker, daemon=True).start()

    def _on_detect_finish(self, info: Dict[str, Any]):
        self.detect_btn.configure(text="🔍 Auto-Detect", state="normal")
        if info.get("connected"):
            cmp_name = info.get("company_name", "")
            if cmp_name:
                self.company_entry.delete(0, "end")
                self.company_entry.insert(0, cmp_name)
                self.status_lbl.configure(
                    text=f"✅ Connected to Tally! Active company: '{cmp_name}' (Release: {info.get('release')})",
                    text_color=SUCCESS_GREEN
                )
            else:
                self.status_lbl.configure(
                    text="⚠️ Tally is active on port 9000, but no company is currently open.",
                    text_color=WARNING_AMBER
                )
        else:
            self.status_lbl.configure(
                text=f"❌ Could not connect to Tally XML server at {self.tally_url_entry.get()}. Ensure TallyPrime is open with port 9000 enabled.",
                text_color=ERROR_RED
            )

    def _run_connection_test(self):
        self.test_btn.configure(text="Testing...", state="disabled")
        self.status_lbl.configure(text="🔍 Verifying Tally and Cloud connections...", text_color=TEXT_MUTED)

        backend_url = self.backend_url_entry.get().strip()
        email = self.email_entry.get().strip()
        password = self.password_entry.get()
        tally_url = self.tally_url_entry.get().strip()

        def test_worker():
            # Test Tally
            t_client = TallyClient(tally_url=tally_url)
            t_info = t_client.discover_tally_host()

            # Test Cloud
            c_client = CloudClient(backend_url=backend_url, email=email, password=password)
            cloud_ok, cloud_msg = c_client.check_health()
            auth_ok, auth_msg = False, ""
            if email and password:
                auth_ok, auth_msg = c_client.authenticate(email, password)

            self.after(0, lambda: self._on_test_done(t_info, cloud_ok, cloud_msg, auth_ok, auth_msg))

        threading.Thread(target=test_worker, daemon=True).start()

    def _on_test_done(self, t_info, cloud_ok, cloud_msg, auth_ok, auth_msg):
        self.test_btn.configure(text="🧪 Test Connection", state="normal")
        t_ok = t_info.get("connected", False)

        lines = []
        if t_ok:
            lines.append(f"✅ Tally: Connected ({t_info.get('company_name') or 'No company open'})")
        else:
            lines.append("❌ Tally: Inactive on port 9000")

        if cloud_ok:
            if auth_ok:
                lines.append("✅ Cloud: Authenticated successfully")
            else:
                lines.append(f"⚠️ Cloud: Reachable, but auth failed ({auth_msg})")
        else:
            lines.append(f"❌ Cloud: Cannot connect to {self.backend_url_entry.get()}")

        overall_ok = t_ok and cloud_ok and (auth_ok or not self.password_entry.get())
        color = SUCCESS_GREEN if overall_ok else (WARNING_AMBER if (t_ok or cloud_ok) else ERROR_RED)
        self.status_lbl.configure(text=" | ".join(lines), text_color=color)

    def _connect_and_launch(self):
        backend_url = self.backend_url_entry.get().strip()
        email = self.email_entry.get().strip()
        password = self.password_entry.get()
        tally_url = self.tally_url_entry.get().strip()
        company_name = self.company_entry.get().strip()
        autostart = self.autostart_var.get()

        if not backend_url:
            self.status_lbl.configure(text="❌ Please enter your Cloud Server URL.", text_color=ERROR_RED)
            return

        self.connect_btn.configure(text="Authenticating...", state="disabled")

        def connect_worker():
            cloud_client = CloudClient(backend_url=backend_url, email=email, password=password)
            cloud_ok, _ = cloud_client.check_health()
            
            token = ""
            if email and password:
                auth_ok, auth_res = cloud_client.authenticate(email, password)
                if auth_ok:
                    token = auth_res
                else:
                    self.after(0, lambda: self._on_connect_failed(f"Authentication failed: {auth_res}"))
                    return

            # Update Config
            self.app.config.backend_url = backend_url
            self.app.config.email = email
            self.app.config.username = email
            self.app.config.password = password
            self.app.config.auth_token = token
            self.app.config.tally_url = tally_url
            if company_name:
                self.app.config.company_name = company_name
            self.app.config.autostart_enabled = autostart

            save_config(self.app.config, self.app.config_file)

            # Handle autostart registry
            if autostart:
                install_startup()
            else:
                uninstall_startup()

            # Reload agent
            self.app.agent.reload_config(self.app.config)

            # Transition to Dashboard
            self.after(0, self._on_connect_success)

        threading.Thread(target=connect_worker, daemon=True).start()

    def _on_connect_failed(self, msg: str):
        self.connect_btn.configure(text="🚀 Connect & Start Sync", state="normal")
        self.status_lbl.configure(text=f"❌ {msg}", text_color=ERROR_RED)

    def _on_connect_success(self):
        self.app.show_dashboard()
        self.app.start_sync_thread()


# ---------------------------------------------------------------------------
# VIEW 2: Dashboard Screen (Live Synchronization Dashboard)
# ---------------------------------------------------------------------------
class DashboardView(ctk.CTkFrame):
    def __init__(self, parent, app: SnehDistribuorsApp):
        super().__init__(parent, fg_color="transparent")
        self.app = app

        self._build_top_bar()
        self._build_connection_cards()
        self._build_metric_cards()
        self._build_status_banner()
        self._build_log_console()
        self._build_toolbar()

    def _build_top_bar(self):
        top_row = ctk.CTkFrame(self, fg_color="transparent")
        top_row.pack(fill="x", pady=(0, 12))

        # Brand on left
        brand_box = ctk.CTkFrame(top_row, fg_color="transparent")
        brand_box.pack(side="left")

        if self.app.pil_icon:
            logo_img = ctk.CTkImage(light_image=self.app.pil_icon, dark_image=self.app.pil_icon, size=(32, 32))
            logo_lbl = ctk.CTkLabel(brand_box, text="", image=logo_img)
            logo_lbl.pack(side="left", padx=(0, 8))

        brand_lbl = ctk.CTkLabel(
            brand_box,
            text="SnehDistribuors",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=TEXT_MAIN
        )
        brand_lbl.pack(side="left")

        # Live Status Pill on right
        self.status_pill = ctk.CTkFrame(top_row, fg_color="#064E3B", corner_radius=16)
        self.status_pill.pack(side="right")

        self.status_dot = ctk.CTkLabel(
            self.status_pill,
            text="●",
            font=ctk.CTkFont(size=14),
            text_color=SUCCESS_GREEN
        )
        self.status_dot.pack(side="left", padx=(10, 4), pady=4)

        self.status_text_lbl = ctk.CTkLabel(
            self.status_pill,
            text="ONLINE",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#A7F3D0"
        )
        self.status_text_lbl.pack(side="left", padx=(0, 12), pady=4)

    def _build_connection_cards(self):
        cards_row = ctk.CTkFrame(self, fg_color="transparent")
        cards_row.pack(fill="x", pady=(0, 10))

        # 1. Tally Card
        self.tally_card = ctk.CTkFrame(cards_row, fg_color=CARD_BG, corner_radius=12, border_width=1, border_color=CARD_BORDER)
        self.tally_card.pack(side="left", fill="both", expand=True, padx=(0, 6))

        tally_top = ctk.CTkFrame(self.tally_card, fg_color="transparent")
        tally_top.pack(fill="x", padx=12, pady=(10, 2))

        ctk.CTkLabel(tally_top, text="📊 TallyPrime", font=ctk.CTkFont(size=13, weight="bold"), text_color=TEXT_MAIN).pack(side="left")
        self.tally_badge = ctk.CTkLabel(tally_top, text="● Connected", font=ctk.CTkFont(size=11, weight="bold"), text_color=SUCCESS_GREEN)
        self.tally_badge.pack(side="right")

        self.tally_company_lbl = ctk.CTkLabel(
            self.tally_card,
            text="Company: Detecting...",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MUTED
        )
        self.tally_company_lbl.pack(anchor="w", padx=12, pady=(2, 10))

        # 2. Cloud Card
        self.cloud_card = ctk.CTkFrame(cards_row, fg_color=CARD_BG, corner_radius=12, border_width=1, border_color=CARD_BORDER)
        self.cloud_card.pack(side="left", fill="both", expand=True, padx=(6, 0))

        cloud_top = ctk.CTkFrame(self.cloud_card, fg_color="transparent")
        cloud_top.pack(fill="x", padx=12, pady=(10, 2))

        ctk.CTkLabel(cloud_top, text="☁️ Cloud ERP", font=ctk.CTkFont(size=13, weight="bold"), text_color=TEXT_MAIN).pack(side="left")
        self.cloud_badge = ctk.CTkLabel(cloud_top, text="● Connected", font=ctk.CTkFont(size=11, weight="bold"), text_color=SUCCESS_GREEN)
        self.cloud_badge.pack(side="right")

        user_display = self.app.config.email or "Active"
        self.cloud_user_lbl = ctk.CTkLabel(
            self.cloud_card,
            text=f"User: {user_display}",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MUTED
        )
        self.cloud_user_lbl.pack(anchor="w", padx=12, pady=(2, 10))

    def _build_metric_cards(self):
        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.pack(fill="x", pady=(0, 10))

        # 4 Metric Boxes: Vouchers, Ledgers, Stock Items, Errors
        self.vouchers_box = self._create_metric_tile(grid, "📦 Vouchers", "0", 0)
        self.ledgers_box = self._create_metric_tile(grid, "📒 Ledgers", "0", 1)
        self.items_box = self._create_metric_tile(grid, "🏷️ Items", "0", 2)
        self.errors_box = self._create_metric_tile(grid, "⚠️ Errors", "0", 3, is_error=True)

    def _create_metric_tile(self, parent, title: str, val: str, col: int, is_error: bool = False):
        card = ctk.CTkFrame(parent, fg_color=CARD_BG, corner_radius=10, border_width=1, border_color=CARD_BORDER)
        card.grid(row=0, column=col, sticky="ew", padx=4)
        parent.grid_columnconfigure(col, weight=1)

        ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=11), text_color=TEXT_MUTED).pack(pady=(8, 2))
        val_lbl = ctk.CTkLabel(
            card,
            text=val,
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=ERROR_RED if is_error else TEXT_MAIN
        )
        val_lbl.pack(pady=(0, 8))
        return val_lbl

    def _build_status_banner(self):
        self.status_card = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=10, border_width=1, border_color=CARD_BORDER)
        self.status_card.pack(fill="x", pady=(0, 10))

        row = ctk.CTkFrame(self.status_card, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=8)

        self.last_sync_lbl = ctk.CTkLabel(
            row,
            text="⏳ Last Sync: Initializing...",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MUTED
        )
        self.last_sync_lbl.pack(side="left")

        self.sync_progress = ctk.CTkProgressBar(row, height=8, width=120, fg_color=INPUT_BG, progress_color=ACCENT_BLUE)
        self.sync_progress.pack(side="right", padx=(8, 0))
        self.sync_progress.set(0)

    def _build_log_console(self):
        console_frame = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=12, border_width=1, border_color=CARD_BORDER)
        console_frame.pack(fill="both", expand=True, pady=(0, 12))

        # Console Header
        hdr = ctk.CTkFrame(console_frame, fg_color="transparent")
        hdr.pack(fill="x", padx=12, pady=(8, 4))

        ctk.CTkLabel(
            hdr,
            text="📋 Activity Log",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=TEXT_MAIN
        ).pack(side="left")

        clear_btn = ctk.CTkButton(
            hdr,
            text="Clear",
            font=ctk.CTkFont(size=11),
            width=48,
            height=24,
            fg_color=CARD_BORDER,
            hover_color=CARD_BG,
            command=self.clear_logs
        )
        clear_btn.pack(side="right")

        # Monospace Text Box
        self.log_textbox = ctk.CTkTextbox(
            console_frame,
            fg_color=INPUT_BG,
            text_color=TEXT_MAIN,
            font=ctk.CTkFont(family="Consolas" if sys.platform == "win32" else "Courier", size=11),
            wrap="word",
            corner_radius=8
        )
        self.log_textbox.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        try:
            tb = getattr(self.log_textbox, "_textbox", None)
            if tb:
                tb.tag_config("error", foreground="#F87171")
                tb.tag_config("warning", foreground="#FBBF24")
                tb.tag_config("success", foreground="#34D399")
                tb.tag_config("info", foreground="#CBD5E1")
        except Exception:
            pass

    def _build_toolbar(self):
        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", pady=(0, 4))

        # 1. Sync Delta (Incremental)
        self.sync_now_btn = ctk.CTkButton(
            toolbar,
            text="🔄 Sync Delta",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=ACCENT_BLUE,
            hover_color=ACCENT_HOVER,
            height=38,
            corner_radius=8,
            command=self._on_sync_now
        )
        self.sync_now_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))

        # 2. Sync All (Full baseline)
        self.sync_all_btn = ctk.CTkButton(
            toolbar,
            text="⚡ Sync All",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#0D9488",
            hover_color="#0F766E",
            height=38,
            corner_radius=8,
            command=self._on_sync_all
        )
        self.sync_all_btn.pack(side="left", fill="x", expand=True, padx=4)

        # 3. Pause / Resume
        self.pause_btn = ctk.CTkButton(
            toolbar,
            text="⏸ Pause",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=CARD_BORDER,
            hover_color=CARD_BG,
            height=38,
            corner_radius=8,
            command=self._on_toggle_pause
        )
        self.pause_btn.pack(side="left", fill="x", expand=True, padx=4)

        # 3. Settings
        self.settings_btn = ctk.CTkButton(
            toolbar,
            text="⚙ Settings",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=CARD_BORDER,
            hover_color=CARD_BG,
            height=38,
            corner_radius=8,
            command=self.app.show_settings
        )
        self.settings_btn.pack(side="left", fill="x", expand=True, padx=4)

        # 4. Minimize to Tray
        self.tray_btn = ctk.CTkButton(
            toolbar,
            text="📥 To Tray",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=CARD_BORDER,
            hover_color=CARD_BG,
            height=38,
            corner_radius=8,
            command=self.app.minimize_to_tray
        )
        self.tray_btn.pack(side="left", fill="x", expand=True, padx=(4, 0))

    def _on_sync_now(self):
        self.sync_now_btn.configure(text="Syncing...", state="disabled")
        self.sync_progress.configure(mode="indeterminate")
        self.sync_progress.start()
        self.app.agent.trigger_immediate_sync(force_full=False)
        self.after(3000, lambda: self.sync_now_btn.configure(text="🔄 Sync Delta", state="normal"))

    def _on_sync_all(self):
        self.sync_all_btn.configure(text="Syncing All...", state="disabled")
        self.sync_progress.configure(mode="indeterminate")
        self.sync_progress.start()
        self.app.agent.trigger_immediate_sync(force_full=True)
        self.after(3000, lambda: self.sync_all_btn.configure(text="⚡ Sync All", state="normal"))

    def _on_toggle_pause(self):
        if self.app.agent.is_paused:
            self.app.agent.resume()
            self.pause_btn.configure(text="⏸ Pause")
        else:
            self.app.agent.pause()
            self.pause_btn.configure(text="▶ Resume")

    def append_log(self, message: str, level: str):
        tag = "info"
        if level in ("ERROR", "CRITICAL") or "❌" in message:
            tag = "error"
        elif level == "WARNING" or "⚠️" in message:
            tag = "warning"
        elif "✅" in message or "🎉" in message or "SUCCESS" in message:
            tag = "success"

        try:
            tb = getattr(self.log_textbox, "_textbox", None)
            if tb:
                tb.insert("end", f"{message}\n", tag)
                line_count = int(tb.index('end-1c').split('.')[0])
                if line_count > 1500:
                    tb.delete("1.0", f"{line_count - 1000}.0")
                tb.see("end")
            else:
                self.log_textbox.insert("end", f"{message}\n")
                self.log_textbox.see("end")
        except Exception:
            self.log_textbox.insert("end", f"{message}\n")
            self.log_textbox.see("end")

    def clear_logs(self):
        self.log_textbox.delete("1.0", "end")

    def update_status(self, status: Dict[str, Any]):
        # Update top badge
        st_text = status.get("status", "STANDBY")
        if st_text == "ONLINE":
            self.status_pill.configure(fg_color="#064E3B")
            self.status_dot.configure(text_color=SUCCESS_GREEN)
            self.status_text_lbl.configure(text="LIVE SYNCING", text_color="#A7F3D0")
            self.sync_progress.stop()
            self.sync_progress.configure(mode="determinate")
            self.sync_progress.set(1.0)
        elif st_text == "SYNCING":
            self.status_pill.configure(fg_color="#1E3A8A")
            self.status_dot.configure(text_color="#60A5FA")
            self.status_text_lbl.configure(text="SYNCING...", text_color="#BFDBFE")
            self.sync_progress.configure(mode="indeterminate")
            self.sync_progress.start()
        elif st_text == "PAUSED":
            self.status_pill.configure(fg_color="#78350F")
            self.status_dot.configure(text_color=WARNING_AMBER)
            self.status_text_lbl.configure(text="PAUSED", text_color="#FDE68A")
            self.pause_btn.configure(text="▶ Resume")
        else:
            self.status_pill.configure(fg_color="#7F1D1D")
            self.status_dot.configure(text_color=ERROR_RED)
            self.status_text_lbl.configure(text=st_text, text_color="#FECACA")

        # Tally card
        t_ok = status.get("tally_connected", False)
        if t_ok:
            self.tally_badge.configure(text="● Connected", text_color=SUCCESS_GREEN)
            cmp_str = status.get("active_company_name") or "No company open"
            open_cnt = status.get("open_companies_count", 0)
            if open_cnt > 1:
                self.tally_company_lbl.configure(text=f"Company: {cmp_str} (+{open_cnt - 1} open)")
            else:
                self.tally_company_lbl.configure(text=f"Company: {cmp_str}")
        else:
            self.tally_badge.configure(text="● Disconnected", text_color=ERROR_RED)
            self.tally_company_lbl.configure(text="Company: Tally not running")

        # Cloud card
        c_ok = status.get("cloud_connected", False)
        if c_ok:
            self.cloud_badge.configure(text="● Connected", text_color=SUCCESS_GREEN)
        else:
            self.cloud_badge.configure(text="● Offline", text_color=ERROR_RED)

        # Metric Tiles
        self.vouchers_box.configure(text=str(status.get("total_vouchers", 0)))
        self.ledgers_box.configure(text=str(status.get("total_ledgers", 0)))
        self.items_box.configure(text=str(status.get("total_items", 0)))
        self.errors_box.configure(text=str(status.get("total_errors", 0)))

        # Last Sync
        last_t = status.get("last_sync_timestr", "Never")
        last_s = status.get("last_sync_status", "Ready")
        self.last_sync_lbl.configure(text=f"⏳ Last Sync: {last_t} — {last_s}")


# ---------------------------------------------------------------------------
# VIEW 3: Settings Screen (LiveKeeping-Style Connection Settings)
# ---------------------------------------------------------------------------
class SettingsView(ctk.CTkFrame):
    def __init__(self, parent, app: SnehDistribuorsApp):
        super().__init__(parent, fg_color="transparent")
        self.app = app

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True)

        self._build_header()
        self._build_settings_form()
        self._build_footer()

    def _build_header(self):
        hdr = ctk.CTkFrame(self.scroll, fg_color="transparent")
        hdr.pack(fill="x", pady=(4, 14))

        back_btn = ctk.CTkButton(
            hdr,
            text="← Back to Dashboard",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=CARD_BORDER,
            hover_color=CARD_BG,
            height=32,
            width=160,
            command=self.app.show_dashboard
        )
        back_btn.pack(side="left")

        title_lbl = ctk.CTkLabel(
            hdr,
            text="⚙ Connection Settings",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=TEXT_MAIN
        )
        title_lbl.pack(side="right")

    def _build_settings_form(self):
        card = ctk.CTkFrame(self.scroll, fg_color=CARD_BG, corner_radius=12, border_width=1, border_color=CARD_BORDER)
        card.pack(fill="x", pady=(0, 14), padx=4)

        # 1. Tally Host & Port
        ctk.CTkLabel(card, text="Tally Host Name:", font=ctk.CTkFont(size=12), text_color=TEXT_MUTED).pack(anchor="w", padx=16, pady=(12, 2))
        
        host_port_row = ctk.CTkFrame(card, fg_color="transparent")
        host_port_row.pack(fill="x", padx=16, pady=(0, 10))

        # Parse host & port from config.tally_url
        t_url = self.app.config.tally_url or "http://127.0.0.1:9000"
        host_part = "localhost"
        port_part = "9000"
        if "//" in t_url:
            raw = t_url.split("//", 1)[1]
            if ":" in raw:
                host_part, port_part = raw.split(":", 1)
                port_part = port_part.split("/")[0]

        self.host_entry = ctk.CTkEntry(host_port_row, placeholder_text="localhost", fg_color=INPUT_BG, border_color=CARD_BORDER, height=36)
        self.host_entry.insert(0, host_part)
        self.host_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkLabel(host_port_row, text="Port:", font=ctk.CTkFont(size=12), text_color=TEXT_MUTED).pack(side="left", padx=(0, 6))
        self.port_entry = ctk.CTkEntry(host_port_row, placeholder_text="9000", width=80, fg_color=INPUT_BG, border_color=CARD_BORDER, height=36)
        self.port_entry.insert(0, port_part)
        self.port_entry.pack(side="left")

        # 2. Cloud URL
        ctk.CTkLabel(card, text="Cloud Backend URL:", font=ctk.CTkFont(size=12), text_color=TEXT_MUTED).pack(anchor="w", padx=16, pady=(4, 2))
        self.backend_url_entry = ctk.CTkEntry(card, fg_color=INPUT_BG, border_color=CARD_BORDER, height=36)
        self.backend_url_entry.insert(0, self.app.config.backend_url or "")
        self.backend_url_entry.pack(fill="x", padx=16, pady=(0, 12))

        # 3. Advanced Intervals
        ctk.CTkLabel(card, text="⏱ Advanced Sync Intervals", font=ctk.CTkFont(size=13, weight="bold"), text_color=TEXT_MAIN).pack(anchor="w", padx=16, pady=(4, 8))

        int_row = ctk.CTkFrame(card, fg_color="transparent")
        int_row.pack(fill="x", padx=16, pady=(0, 12))

        ctk.CTkLabel(int_row, text="Outbound Check (sec):", font=ctk.CTkFont(size=12), text_color=TEXT_MUTED).pack(side="left")
        self.outbound_entry = ctk.CTkEntry(int_row, width=70, fg_color=INPUT_BG, border_color=CARD_BORDER, height=34)
        self.outbound_entry.insert(0, str(self.app.config.sync_interval_seconds or 5))
        self.outbound_entry.pack(side="left", padx=(8, 16))

        ctk.CTkLabel(int_row, text="Inbound Delta (sec):", font=ctk.CTkFont(size=12), text_color=TEXT_MUTED).pack(side="left")
        self.inbound_entry = ctk.CTkEntry(int_row, width=70, fg_color=INPUT_BG, border_color=CARD_BORDER, height=34)
        self.inbound_entry.insert(0, str(self.app.config.inbound_interval_seconds or 60))
        self.inbound_entry.pack(side="left", padx=(8, 0))

        # 4. Toggles
        self.auto_discover_var = ctk.BooleanVar(value=self.app.config.auto_discover_paths)
        self.auto_discover_switch = ctk.CTkSwitch(
            card,
            text="Auto-discover Tally Application & Data Paths",
            variable=self.auto_discover_var,
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MAIN,
            progress_color=ACCENT_BLUE
        )
        self.auto_discover_switch.pack(anchor="w", padx=16, pady=(4, 10))

        self.force_full_sync_var = ctk.BooleanVar(value=getattr(self.app.config, "force_full_sync", False))
        self.force_full_sync_switch = ctk.CTkSwitch(
            card,
            text="Always Sync All Records (Bypass Tally Alter ID Filter)",
            variable=self.force_full_sync_var,
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MAIN,
            progress_color=ACCENT_BLUE
        )
        self.force_full_sync_switch.pack(anchor="w", padx=16, pady=(0, 10))

        self.autostart_var = ctk.BooleanVar(value=self.app.config.autostart_enabled or is_autostart_registered())
        self.autostart_switch = ctk.CTkSwitch(
            card,
            text="Start Automatically on Windows Boot",
            variable=self.autostart_var,
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MAIN,
            progress_color=ACCENT_BLUE
        )
        self.autostart_switch.pack(anchor="w", padx=16, pady=(0, 16))

        # 5. Account Switch / Reconfigure Section
        acct_card = ctk.CTkFrame(self.scroll, fg_color=CARD_BG, corner_radius=12, border_width=1, border_color=CARD_BORDER)
        acct_card.pack(fill="x", pady=(0, 14), padx=4)

        ctk.CTkLabel(acct_card, text="👤 Account & Authentication", font=ctk.CTkFont(size=13, weight="bold"), text_color=TEXT_MAIN).pack(anchor="w", padx=16, pady=(12, 6))
        user_str = self.app.config.email or self.app.config.username or "Configured via Token"
        ctk.CTkLabel(acct_card, text=f"Logged in as: {user_str}", font=ctk.CTkFont(size=12), text_color=TEXT_MUTED).pack(anchor="w", padx=16, pady=(0, 10))

        relogin_btn = ctk.CTkButton(
            acct_card,
            text="🔐 Re-login / Switch User",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=CARD_BORDER,
            hover_color=CARD_BG,
            height=34,
            command=self.app.show_setup
        )
        relogin_btn.pack(anchor="w", padx=16, pady=(0, 12))

        # 6. Diagnostic Logs Section
        diag_card = ctk.CTkFrame(self.scroll, fg_color=CARD_BG, corner_radius=12, border_width=1, border_color=CARD_BORDER)
        diag_card.pack(fill="x", pady=(0, 14), padx=4)

        ctk.CTkLabel(diag_card, text="📋 Diagnostic Logs & Support", font=ctk.CTkFont(size=13, weight="bold"), text_color=TEXT_MAIN).pack(anchor="w", padx=16, pady=(12, 4))
        ctk.CTkLabel(diag_card, text="Inspect synchronization logs (agent.log, tally_traffic.log) or export a support archive.", font=ctk.CTkFont(size=12), text_color=TEXT_MUTED).pack(anchor="w", padx=16, pady=(0, 10))

        log_btn_row = ctk.CTkFrame(diag_card, fg_color="transparent")
        log_btn_row.pack(fill="x", padx=16, pady=(0, 12))

        open_logs_btn = ctk.CTkButton(
            log_btn_row,
            text="📂 Open Logs Folder",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=CARD_BORDER,
            hover_color=CARD_BG,
            height=34,
            width=160,
            command=self._open_logs_folder
        )
        open_logs_btn.pack(side="left", padx=(0, 8))

        export_logs_btn = ctk.CTkButton(
            log_btn_row,
            text="📦 Export Logs (.zip)",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=CARD_BORDER,
            hover_color=CARD_BG,
            height=34,
            width=160,
            command=self._export_logs_zip
        )
        export_logs_btn.pack(side="left")

        # 7. Exit Application Section
        exit_card = ctk.CTkFrame(self.scroll, fg_color=CARD_BG, corner_radius=12, border_width=1, border_color=CARD_BORDER)
        exit_card.pack(fill="x", pady=(0, 14), padx=4)

        ctk.CTkLabel(exit_card, text="🛑 Exit Application", font=ctk.CTkFont(size=13, weight="bold"), text_color=TEXT_MAIN).pack(anchor="w", padx=16, pady=(12, 4))
        ctk.CTkLabel(exit_card, text="Stop all background sync processes and completely quit SnehDistribuors.", font=ctk.CTkFont(size=12), text_color=TEXT_MUTED).pack(anchor="w", padx=16, pady=(0, 10))

        exit_btn = ctk.CTkButton(
            exit_card,
            text="❌ Exit SnehDistribuors",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#7F1D1D",
            hover_color="#991B1B",
            height=34,
            command=self.app._shutdown_app
        )
        exit_btn.pack(anchor="w", padx=16, pady=(0, 12))

        # Actions
        self.feedback_lbl = ctk.CTkLabel(self.scroll, text="", font=ctk.CTkFont(size=12))
        self.feedback_lbl.pack(pady=(0, 8))

        btn_row = ctk.CTkFrame(self.scroll, fg_color="transparent")
        btn_row.pack(fill="x", pady=(0, 12))

        self.save_btn = ctk.CTkButton(
            btn_row,
            text="💾 Save Settings",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=ACCENT_BLUE,
            hover_color=ACCENT_HOVER,
            height=40,
            command=self._save_settings
        )
        self.save_btn.pack(side="left", fill="x", expand=True, padx=(0, 6))

    def _save_settings(self):
        host = self.host_entry.get().strip() or "localhost"
        port = self.port_entry.get().strip() or "9000"
        backend_url = self.backend_url_entry.get().strip()
        autostart = self.autostart_var.get()
        auto_disc = self.auto_discover_var.get()
        force_full = self.force_full_sync_var.get()

        try:
            out_sec = int(self.outbound_entry.get().strip() or "5")
            in_sec = int(self.inbound_entry.get().strip() or "60")
        except ValueError:
            self.feedback_lbl.configure(text="❌ Intervals must be numbers.", text_color=ERROR_RED)
            return

        tally_url = f"http://{host}:{port}"
        self.app.config.tally_url = tally_url
        self.app.config.backend_url = backend_url
        self.app.config.sync_interval_seconds = max(1, out_sec)
        self.app.config.inbound_interval_seconds = max(5, in_sec)
        self.app.config.auto_discover_paths = auto_disc
        self.app.config.force_full_sync = force_full
        self.app.config.autostart_enabled = autostart

        save_config(self.app.config, self.app.config_file)

        if autostart:
            install_startup()
        else:
            uninstall_startup()

        # Reload agent
        self.app.agent.reload_config(self.app.config)

        self.feedback_lbl.configure(text="✅ Settings saved successfully!", text_color=SUCCESS_GREEN)
        self.after(1500, self.app.show_dashboard)

    def _open_logs_folder(self):
        log_dir = get_logs_dir()
        try:
            if sys.platform == "win32":
                os.startfile(log_dir)
            elif sys.platform == "darwin":
                subprocess.run(["open", log_dir])
            else:
                subprocess.run(["xdg-open", log_dir])
        except Exception as e:
            self.feedback_lbl.configure(text=f"⚠️ Could not open folder: {e}", text_color=WARNING_AMBER)

    def _export_logs_zip(self):
        import zipfile
        from datetime import datetime
        log_dir = get_logs_dir()
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        if not os.path.exists(desktop):
            desktop = log_dir

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_path = os.path.join(desktop, f"SnehDistribuors_Logs_{ts}.zip")
        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for fn in ["agent.log", "tally_traffic.log"]:
                    fp = os.path.join(log_dir, fn)
                    if os.path.exists(fp):
                        zf.write(fp, arcname=fn)
            self.feedback_lbl.configure(text=f"✅ Exported logs to Desktop: {os.path.basename(zip_path)}", text_color=SUCCESS_GREEN)
        except Exception as e:
            self.feedback_lbl.configure(text=f"❌ Failed to export logs: {e}", text_color=ERROR_RED)

    def _build_footer(self):
        footer = ctk.CTkFrame(self.scroll, fg_color="transparent")
        footer.pack(fill="x", pady=(10, 8))

        ctk.CTkLabel(
            footer,
            text="SnehDistribuors Tally Sync Connector • v1.0.0 (Build 2026.09.21)",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=TEXT_MUTED
        ).pack()

        ctk.CTkLabel(
            footer,
            text="TallyPrime XML Connector (Port 9000) • AES-128 Machine Vault • SnehDistribuors Cloud ERP",
            font=ctk.CTkFont(size=10),
            text_color=TEXT_MUTED
        ).pack(pady=(2, 0))


# ---------------------------------------------------------------------------
# Application Entry Point
# ---------------------------------------------------------------------------
def main():
    if not check_single_instance():
        sys.exit(0)
    app = SnehDistribuorsApp()
    app.mainloop()

if __name__ == "__main__":
    main()
