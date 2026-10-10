"""
MyTally Bridge — the Windows window and tray icon of the desktop sync agent.
Keeps the companies open in TallyPrime on this PC in step with the MyTally cloud.
"""

import os
import sys
import queue
import platform
import threading
import tkinter as tk
from collections import deque
from typing import Optional, Dict, Any, List, Tuple

import customtkinter as ctk
from PIL import Image, ImageTk
import pystray
from pystray import MenuItem as item

from config import load_config, save_config, AgentConfig, is_autostart_registered, get_default_config_path
from agent import DesktopSyncAgent
import bridge_core as core
from bridge_core import APP_NAME, APP_SHORT, APP_VERSION, health_from_status, check_single_instance, get_asset_path

# ---------------------------------------------------------------------------
# Design tokens: every colour is a (light, dark) pair.
# ---------------------------------------------------------------------------
ctk.set_default_color_theme("green")

BG = ("#F8F8FA", "#121212")            # window
SURFACE = ("#FFFFFF", "#1B1B1B")       # cards, rail, health bar, inputs
SUBTLE = ("#F0F1F5", "#262626")        # hover, selected nav, progress track
BORDER = ("#E3E5EC", "#333333")
BORDER_INPUT = ("#8A8D9C", "#7A7A7A")
TEXT = ("#1E2032", "#F5F5F5")
TEXT_2 = ("#44475B", "#B8B8B8")
TEXT_3 = ("#6B6E80", "#949494")
PRIMARY = ("#008565", "#0ABB92")       # 4.6:1 under a white label; the brighter brand green is not
PRIMARY_HOVER = ("#00735A", "#2ACFA6")
ON_PRIMARY = ("#FFFFFF", "#0B1F19")

# One entry per sync state: text/icon, solid (dots, progress, tray badge), tinted fill, outline
STATE = {
    "idle":   {"fg": ("#44475B", "#B8B8B8"), "solid": ("#8A8D9C", "#7A7A7A"), "bg": ("#F0F1F5", "#262626"), "border": ("#E3E5EC", "#333333"), "glyph": "○"},
    "paused": {"fg": ("#44475B", "#B8B8B8"), "solid": ("#8A8D9C", "#7A7A7A"), "bg": ("#F0F1F5", "#262626"), "border": ("#E3E5EC", "#333333"), "glyph": "II"},
    "sync":   {"fg": ("#3D4FD9", "#9AA6FF"), "solid": ("#5367FF", "#6B7CFF"), "bg": ("#EEF0FF", "#1B1F42"), "border": ("#CBD1FF", "#2E3570"), "glyph": "↻"},
    "ok":     {"fg": ("#00735A", "#4CD9B4"), "solid": ("#00B386", "#0ABB92"), "bg": ("#E6F7F2", "#0E2B24"), "border": ("#B0E6D7", "#17493C"), "glyph": "✓"},
    "warn":   {"fg": ("#8A5A00", "#F2C14E"), "solid": ("#E5A100", "#E0A82E"), "bg": ("#FFF5D6", "#33270C"), "border": ("#F2D98A", "#5C4514"), "glyph": "!"},
    "error":  {"fg": ("#B93217", "#FF8F75"), "solid": ("#EB5B3C", "#EB5B3C"), "bg": ("#FDEEEA", "#3A1810"), "border": ("#F7C6BA", "#6B2A1B"), "glyph": "✕"},
}

RADIUS_CONTROL = 6
RADIUS_CARD = 10
UI_FONT = "Segoe UI" if sys.platform == "win32" else None
MONO_FONT = "Consolas" if sys.platform == "win32" else "Courier"
THEMES = {"System": "system", "Light": "light", "Dark": "dark"}


def font(size: int = 13, bold: bool = False) -> ctk.CTkFont:
    kwargs: Dict[str, Any] = {"size": size, "weight": "bold" if bold else "normal"}
    if UI_FONT:
        kwargs["family"] = UI_FONT
    return ctk.CTkFont(**kwargs)


def card(parent, **kwargs) -> ctk.CTkFrame:
    return ctk.CTkFrame(parent, fg_color=SURFACE, corner_radius=RADIUS_CARD, border_width=1, border_color=BORDER, **kwargs)


def primary_button(parent, text: str, command, height: int = 32, **kwargs) -> ctk.CTkButton:
    return ctk.CTkButton(parent, text=text, command=command, height=height, corner_radius=RADIUS_CONTROL, font=font(13, True),
                         fg_color=PRIMARY, hover_color=PRIMARY_HOVER, text_color=ON_PRIMARY, text_color_disabled=ON_PRIMARY, **kwargs)


def secondary_button(parent, text: str, command, height: int = 32, **kwargs) -> ctk.CTkButton:
    return ctk.CTkButton(parent, text=text, command=command, height=height, corner_radius=RADIUS_CONTROL, font=font(13, True),
                         fg_color=SURFACE, hover_color=SUBTLE, text_color=TEXT, border_width=1, border_color=BORDER_INPUT, **kwargs)


def danger_button(parent, text: str, command, height: int = 32, **kwargs) -> ctk.CTkButton:
    return ctk.CTkButton(parent, text=text, command=command, height=height, corner_radius=RADIUS_CONTROL, font=font(13, True),
                         fg_color=SURFACE, hover_color=STATE["error"]["bg"], text_color=STATE["error"]["fg"],
                         border_width=1, border_color=STATE["error"]["border"], **kwargs)


def link_button(parent, text: str, command) -> ctk.CTkButton:
    return ctk.CTkButton(parent, text=text, command=command, height=24, width=0, corner_radius=RADIUS_CONTROL,
                         font=ctk.CTkFont(family=UI_FONT, size=12, underline=True) if UI_FONT else ctk.CTkFont(size=12, underline=True),
                         fg_color="transparent", hover_color=SUBTLE, text_color=TEXT_2)


def entry(parent, variable: Optional[tk.Variable] = None, secret: bool = False, **kwargs) -> ctk.CTkEntry:
    return ctk.CTkEntry(parent, textvariable=variable, show="•" if secret else "", height=34, corner_radius=RADIUS_CONTROL,
                        border_width=1, border_color=BORDER_INPUT, fg_color=SURFACE, text_color=TEXT, font=font(13), **kwargs)


def field(parent, label: str, variable: Optional[tk.Variable] = None, help_text: str = "", secret: bool = False,
          padx: int = 24) -> ctk.CTkEntry:
    """A labelled input: label above, optional helper line below."""
    ctk.CTkLabel(parent, text=label, font=font(12, True), text_color=TEXT_2).pack(anchor="w", padx=padx, pady=(0, 2))
    box = entry(parent, variable, secret)
    box.pack(fill="x", padx=padx, pady=(0, 2 if help_text else 10))
    if help_text:
        ctk.CTkLabel(parent, text=help_text, font=font(11), text_color=TEXT_3).pack(anchor="w", padx=padx, pady=(0, 10))
    return box




# ---------------------------------------------------------------------------
# Main Application Window
# ---------------------------------------------------------------------------
class BridgeApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(APP_NAME)
        self.geometry("920x600")   # landscape: fits a 1366x768 laptop with the taskbar showing
        self.minsize(760, 520)
        self.configure(fg_color=BG)

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
        ctk.set_appearance_mode(self.config.theme if self.config.theme in THEMES.values() else "system")

        # Agent & Background Worker
        self.agent = DesktopSyncAgent(config_path=self.config_file)
        self.worker_thread: Optional[threading.Thread] = None
        self.log_queue = queue.Queue()
        # Kept whichever page is showing, so Activity has the history when it is opened
        self.log_history: deque = deque(maxlen=1000)

        # Connect Agent Logger to Queue
        self.agent.add_log_listener(self._on_agent_log)

        # System Tray State
        self.tray_icon: Optional[pystray.Icon] = None
        self.is_minimized_to_tray = False
        self._tray_notice_shown = False
        self._tray_state: Tuple[str, str] = ("", "")
        self._init_system_tray()

        # Handle Window Close
        self.protocol("WM_DELETE_WINDOW", self._on_window_close)

        # Current view tracking
        self.current_frame: Optional[ctk.CTkFrame] = None

        # Determine start screen
        has_credentials = core.has_credentials(self.config)
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
    def _tray_image(self, kind: str = "idle") -> Image.Image:
        return core.tray_image(self.pil_icon, kind)

    def _init_system_tray(self):
        """Initializes pystray icon for background operation."""
        try:
            tray_menu = (
                item(f"Open {APP_SHORT}", self._tray_restore_window, default=True),
                item("Sync now", self._tray_sync_now),
                item("Full re-sync", self._tray_sync_all),
                item("Pause or resume syncing", self._tray_toggle_pause),
                pystray.Menu.SEPARATOR,
                item(f"Quit {APP_SHORT}", self._tray_exit_app)
            )
            self.tray_icon = pystray.Icon(
                "SnehDistribuorsSync",
                self._tray_image(),
                APP_NAME,
                tray_menu
            )
            tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
            tray_thread.start()
        except Exception as e:
            print(f"System tray initialization notice: {e}")

    def _update_tray(self, health: Dict[str, str]):
        """The tray icon is the whole interface most of the day: it carries the same state as the health bar."""
        if not self.tray_icon:
            return
        state = (health["kind"], health["title"])
        if state == self._tray_state:
            return
        self._tray_state = state
        try:
            self.tray_icon.icon = self._tray_image(health["kind"])
            self.tray_icon.title = f"{APP_NAME}: {health['title']}"[:120]   # Windows cuts tooltips at 127
        except Exception:
            pass

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
        if self.tray_icon and not self._tray_notice_shown:
            self._tray_notice_shown = True
            try:
                self.tray_icon.notify(f"{APP_SHORT} keeps syncing in the background.", APP_NAME)
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

    def set_theme(self, theme: str):
        self.config.theme = theme
        save_config(self.config, self.config_file)
        ctk.set_appearance_mode(theme)
        if isinstance(self.current_frame, MainView):
            self.current_frame.theme_changed()

    # -----------------------------------------------------------------------
    # Screen Switching Helpers
    # -----------------------------------------------------------------------
    def _show(self, frame: ctk.CTkFrame):
        if self.current_frame:
            self.current_frame.destroy()
        self.current_frame = frame
        frame.pack(fill="both", expand=True)

    def show_setup(self):
        self._show(SetupView(self, self))

    def show_dashboard(self, page: str = "companies"):
        self._show(MainView(self, self, page))

    def show_settings(self):
        self.show_dashboard("settings")

    # -----------------------------------------------------------------------
    # Status Polling Loop
    # -----------------------------------------------------------------------
    def _periodic_status_refresh(self):
        fresh: List[Tuple[str, str]] = []
        while True:
            try:
                fresh.append(self.log_queue.get_nowait())
            except queue.Empty:
                break
        self.log_history.extend(fresh)

        if isinstance(self.current_frame, MainView):
            status = self.agent.get_status()
            health = health_from_status(status)
            self._update_tray(health)
            self.current_frame.refresh(status, health, fresh)

        self.after(1000, self._periodic_status_refresh)


# ---------------------------------------------------------------------------
# VIEW 1: First run. Welcome, then sign in or create an account, all in one card
# ---------------------------------------------------------------------------
class SetupView(ctk.CTkFrame):
    CARD_WIDTH = 372

    def __init__(self, parent, app: BridgeApp):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        cfg = app.config

        # What has been typed lives here, not in the widgets, so moving between screens loses nothing
        self.v_server = tk.StringVar(value=cfg.backend_url or "")
        self.v_tally = tk.StringVar(value=cfg.tally_url or core.DEFAULT_TALLY_URL)
        self.v_email = tk.StringVar(value=cfg.email or cfg.username or "")
        self.v_password = tk.StringVar(value=cfg.password or "")
        self.v_company = tk.StringVar(value=cfg.company_name or "")
        self.v_name = tk.StringVar()
        self.v_business = tk.StringVar()
        self.v_phone = tk.StringVar()
        self.v_code = tk.StringVar()
        self.v_terms = tk.BooleanVar(value=False)
        self.v_autostart = tk.BooleanVar(value=cfg.autostart_enabled or is_autostart_registered())
        self.advanced_open = False
        self.tally_note: Tuple[str, str] = ("Looking for TallyPrime...", "idle")
        self.company: Optional[Dict[str, Any]] = None   # the Tally company a new account starts with
        self._sending = False

        # Scrollable container for smaller screens
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True)
        self.card = card(self.scroll)
        self.card.pack(pady=24)

        self.msg: Optional[ctk.CTkLabel] = None
        self.note_lbl: Optional[ctk.CTkLabel] = None
        self.main_btn: Optional[ctk.CTkButton] = None
        self.screen = ""
        # Someone who has signed in before is coming back to sign in again, not to choose
        self._show("signin" if self.v_email.get() else "welcome")
        self._detect_tally_company()

    # -- shared pieces ------------------------------------------------------
    def _show(self, screen: str):
        for child in self.card.winfo_children():
            child.destroy()
        self.screen = screen
        self.msg = self.note_lbl = self.main_btn = None
        ctk.CTkFrame(self.card, fg_color="transparent", height=14, width=self.CARD_WIDTH + 48).pack()
        getattr(self, f"_build_{screen}")()
        ctk.CTkFrame(self.card, fg_color="transparent", height=14).pack()

    def _title(self, title: str, text: str = ""):
        ctk.CTkLabel(self.card, text=title, font=font(20, True), text_color=TEXT).pack(anchor="w", padx=24, pady=(4, 2))
        if text:
            ctk.CTkLabel(self.card, text=text, font=font(13), text_color=TEXT_2, wraplength=self.CARD_WIDTH,
                         justify="left").pack(anchor="w", padx=24, pady=(0, 12))

    def _message_line(self):
        self.msg = ctk.CTkLabel(self.card, text="", font=font(12), text_color=TEXT_3, wraplength=self.CARD_WIDTH, justify="left")
        self.msg.pack(anchor="w", padx=24, pady=(6, 0))

    def _say(self, text: str, kind: str = "idle"):
        if self.msg is not None and self.msg.winfo_exists():
            self.msg.configure(text=text, text_color=STATE[kind]["fg"])

    def _busy(self, text: Optional[str], idle_text: str = ""):
        """The screen's main button while a request runs: disabled with what is happening, then back."""
        if self.main_btn is not None and self.main_btn.winfo_exists():
            self.main_btn.configure(text=text or idle_text, state="disabled" if text else "normal")

    def _tally_line(self):
        text, kind = self.tally_note
        self.note_lbl = ctk.CTkLabel(self.card, text=text, font=font(11), text_color=STATE[kind]["fg"],
                                     wraplength=self.CARD_WIDTH, justify="left")
        self.note_lbl.pack(anchor="w", padx=24, pady=(0, 10))

    def _password_field(self, label: str, help_text: str = ""):
        ctk.CTkLabel(self.card, text=label, font=font(12, True), text_color=TEXT_2).pack(anchor="w", padx=24, pady=(0, 2))
        row = ctk.CTkFrame(self.card, fg_color="transparent")
        row.pack(fill="x", padx=24, pady=(0, 2 if help_text else 10))
        box = entry(row, self.v_password, secret=True)
        box.pack(side="left", fill="x", expand=True)
        toggle = secondary_button(row, "Show", None, height=34, width=58)
        toggle.configure(command=lambda: (box.configure(show="" if box.cget("show") else "•"),
                                          toggle.configure(text="Show" if box.cget("show") else "Hide")))
        toggle.pack(side="left", padx=(8, 0))
        if help_text:
            ctk.CTkLabel(self.card, text=help_text, font=font(11), text_color=TEXT_3).pack(anchor="w", padx=24, pady=(0, 10))

    def _advanced(self):
        """Where the server and TallyPrime are. Almost nobody needs to change these, so they stay folded away."""
        if not self.advanced_open:
            return
        field(self.card, "Server address", self.v_server)
        field(self.card, "TallyPrime address", self.v_tally, "TallyPrime's default is http://127.0.0.1:9000")
        self.test_btn = secondary_button(self.card, "Test connection", self._run_connection_test)
        self.test_btn.pack(anchor="w", padx=24, pady=(0, 6))

    def _toggle_advanced(self):
        self.advanced_open = not self.advanced_open
        self._show(self.screen)

    # -- screens ------------------------------------------------------------
    def _build_welcome(self):
        self._title("Connect TallyPrime to MyTally",
                    f"{APP_SHORT} runs on this PC and keeps your Tally companies in step with the MyTally app.")
        primary_button(self.card, "Create an account", lambda: self._show("create"), height=40).pack(fill="x", padx=24, pady=(4, 8))
        secondary_button(self.card, "My business already uses MyTally", lambda: self._show("signin"), height=40).pack(fill="x", padx=24, pady=(0, 14))
        ctk.CTkFrame(self.card, fg_color=BORDER, height=1).pack(fill="x", padx=24)
        ctk.CTkLabel(self.card, text=f"Invited by your admin? You don't need {APP_SHORT}. Accept the invitation in the MyTally app.",
                     font=font(12), text_color=TEXT_3, wraplength=self.CARD_WIDTH, justify="left").pack(anchor="w", padx=24, pady=(12, 0))

    def _build_signin(self):
        self._title("Sign in to link this PC", "Use an account that can manage the sync agent. Admins can by default.")
        field(self.card, "Email", self.v_email)
        self._password_field("Password")

        ctk.CTkLabel(self.card, text="Company", font=font(12, True), text_color=TEXT_2).pack(anchor="w", padx=24, pady=(0, 2))
        row = ctk.CTkFrame(self.card, fg_color="transparent")
        row.pack(fill="x", padx=24, pady=(0, 2))
        entry(row, self.v_company).pack(side="left", fill="x", expand=True)
        self.detect_btn = secondary_button(row, "Detect", self._detect_tally_company, height=34, width=70)
        self.detect_btn.pack(side="left", padx=(8, 0))
        self._tally_line()

        ctk.CTkCheckBox(self.card, text="Start with Windows", variable=self.v_autostart, font=font(13), text_color=TEXT_2,
                        fg_color=PRIMARY, hover_color=PRIMARY_HOVER, border_color=BORDER_INPUT, checkmark_color=ON_PRIMARY,
                        checkbox_width=18, checkbox_height=18, border_width=1, corner_radius=4).pack(anchor="w", padx=24, pady=(0, 14))

        self.main_btn = primary_button(self.card, "Sign in and start syncing", self._connect_and_launch, height=40)
        self.main_btn.pack(fill="x", padx=24)
        self._message_line()

        links = ctk.CTkFrame(self.card, fg_color="transparent")
        links.pack(fill="x", padx=20, pady=(8, 6))
        link_button(links, "Create an account", lambda: self._show("create")).pack(side="left")
        link_button(links, "Hide advanced" if self.advanced_open else "Advanced", self._toggle_advanced).pack(side="right")
        self._advanced()

    def _build_create(self):
        self._title("Create your account")
        if not self.v_business.get():
            self.v_business.set(self.v_company.get())
        field(self.card, "Your name", self.v_name)
        field(self.card, "Mobile number", self.v_phone)
        field(self.card, "Business name", self.v_business)
        self._tally_line()
        field(self.card, "Email", self.v_email)
        self._password_field("Password", "At least 8 characters")

        ctk.CTkCheckBox(self.card, text="I accept the terms of service", variable=self.v_terms, font=font(13), text_color=TEXT_2,
                        fg_color=PRIMARY, hover_color=PRIMARY_HOVER, border_color=BORDER_INPUT, checkmark_color=ON_PRIMARY,
                        checkbox_width=18, checkbox_height=18, border_width=1, corner_radius=4).pack(anchor="w", padx=24, pady=(0, 14))

        self.main_btn = primary_button(self.card, "Email me a code", self._send_code, height=40)
        self.main_btn.pack(fill="x", padx=24)
        self._message_line()

        links = ctk.CTkFrame(self.card, fg_color="transparent")
        links.pack(fill="x", padx=20, pady=(8, 6))
        link_button(links, "I already have an account", lambda: self._show("signin")).pack(side="left")
        link_button(links, "Hide advanced" if self.advanced_open else "Advanced", self._toggle_advanced).pack(side="right")
        self._advanced()

    def _build_code(self):
        first = f" Your first company will be '{self.company['name']}'." if self.company else ""
        self._title("Check your email",
                    f"We emailed a 6-digit code to {self.v_email.get().strip()}. It is valid for 10 minutes.{first}")
        field(self.card, "Code from the email", self.v_code).focus_set()
        self.main_btn = primary_button(self.card, "Create account", self._create, height=40)
        self.main_btn.pack(fill="x", padx=24)
        self._message_line()
        links = ctk.CTkFrame(self.card, fg_color="transparent")
        links.pack(fill="x", padx=20, pady=(8, 6))
        link_button(links, "Change email", lambda: self._show("create")).pack(side="left")
        link_button(links, "Send the code again", self._send_code).pack(side="right")

    # -- TallyPrime ---------------------------------------------------------
    def _detect_tally_company(self):
        t_url = self.v_tally.get().strip()
        self._set_tally_note("Looking for TallyPrime...", "idle")

        def worker():
            found = core.detect_tally(t_url)
            self.after(0, lambda: self._on_detect_finish(found))

        threading.Thread(target=worker, daemon=True).start()

    def _set_tally_note(self, text: str, kind: str):
        self.tally_note = (text, kind)
        if self.note_lbl is not None and self.note_lbl.winfo_exists():
            self.note_lbl.configure(text=text, text_color=STATE[kind]["fg"])

    def _on_detect_finish(self, found: Dict[str, str]):
        if not self.winfo_exists():
            return
        if found["company"]:
            self.v_company.set(found["company"])
            if self.screen == "create" and not self.v_business.get():
                self.v_business.set(found["company"])
        self._set_tally_note(found["text"], found["kind"])

    def _run_connection_test(self):
        self.test_btn.configure(text="Testing...", state="disabled")
        self._say("Checking TallyPrime and the server...")
        args = (self.v_server.get().strip(), self.v_email.get().strip(), self.v_password.get(), self.v_tally.get().strip())

        def test_worker():
            result = core.test_connection(*args)
            self.after(0, lambda: self._on_test_done(result))

        threading.Thread(target=test_worker, daemon=True).start()

    def _on_test_done(self, result: Dict[str, str]):
        if not self.winfo_exists():
            return
        if self.advanced_open and self.test_btn.winfo_exists():
            self.test_btn.configure(text="Test connection", state="normal")
        self._say(result["text"], result["kind"])

    # -- sign in ------------------------------------------------------------
    def _need_server(self) -> str:
        backend_url = self.v_server.get().strip()
        if not backend_url:
            if not self.advanced_open:
                self._toggle_advanced()
            self._say("Enter the server address under Advanced.", "error")
        return backend_url

    def _connect_and_launch(self):
        backend_url = self._need_server()
        if not backend_url:
            return
        args = (backend_url, self.v_email.get().strip(), self.v_password.get(), self.v_tally.get().strip(),
                self.v_company.get().strip(), self.v_autostart.get())
        self._busy("Signing in...")

        def connect_worker():
            ok, message, as_device = core.sign_in_pc(self.app, *args)
            if not ok:
                self.after(0, lambda: self._on_connect_failed(message))
            elif as_device:
                self._link_company_then_launch()
            else:
                self.after(0, self._on_connect_success)

        threading.Thread(target=connect_worker, daemon=True).start()

    def _link_company_then_launch(self, take_over: bool = False):
        """Worker thread: make this PC the one syncing the chosen company, then open the dashboard. If another PC
        syncs it, ask before moving it here."""
        ok, message, reason = self.app.agent.link_active_company(take_over=take_over)
        if ok:
            self.after(0, self._on_connect_success)
        elif reason == "linked_to_another_device":
            self.after(0, lambda: self._ask_to_move_company(message))
        else:
            self.after(0, lambda: self._on_connect_failed(f"Signed in, but the company could not be linked: {message}"))

    def _ask_to_move_company(self, message: str):
        from tkinter import messagebox
        if messagebox.askyesno("Move sync to this PC?", f"{message}\n\nThe other PC will stop syncing this company."):
            threading.Thread(target=lambda: self._link_company_then_launch(take_over=True), daemon=True).start()
        else:
            self._on_connect_failed("Not linked: the company is still synced from the other PC.")

    def _on_connect_failed(self, msg: str):
        self._busy(None, "Sign in and start syncing")
        self._say(msg, "error")

    def _on_connect_success(self):
        self.app.show_dashboard()
        self.app.start_sync_thread()

    # -- create an account --------------------------------------------------
    # Details, then the code emailed to confirm them. The company open in Tally becomes the account's first
    # company. For joining an existing business there is no form here: an admin of that business sends an
    # invitation from the app.
    def _send_code(self):
        backend_url = self._need_server()
        if not backend_url:
            return
        details = {"full_name": self.v_name.get().strip(), "business_name": self.v_business.get().strip(),
                   "email": self.v_email.get().strip(), "phone": self.v_phone.get().strip(), "password": self.v_password.get()}
        if not all(details.values()):
            self._say("Fill in every field.", "error")
            return
        if not self.v_terms.get():
            self._say("Accept the terms to create an account.", "error")
            return
        if self._sending:
            return
        self._sending = True
        details["accept_terms"] = True
        tally_url, company_name = self.v_tally.get().strip(), self.v_company.get().strip()
        idle_text = "Email me a code" if self.screen == "create" else "Create account"
        self._busy("Sending...")

        def worker():
            ok, message, company = core.request_sign_up_code(backend_url, tally_url, company_name, details)
            if company:
                self.company = company
            self.after(0, lambda: self._code_sent(ok, message, idle_text))

        threading.Thread(target=worker, daemon=True).start()

    def _code_sent(self, ok: bool, message: str, idle_text: str):
        self._sending = False
        if not self.winfo_exists():
            return
        self._busy(None, idle_text)
        if not ok:
            self._say(message, "error")
        elif self.screen == "code":
            self._say("We sent a new code.", "ok")
        else:
            self.v_code.set("")
            self._show("code")

    def _create(self):
        code = self.v_code.get().strip()
        if not code or self.company is None:
            self._say("Enter the code from the email.", "error")
            return
        args = (self.v_server.get().strip(), self.v_email.get().strip(), code, self.company, self.v_tally.get().strip(),
                self.v_autostart.get())
        self._busy("Creating...")

        def worker():
            ok, message = core.finish_sign_up(self.app, *args)
            self.after(0, lambda: self._created(ok, message))

        threading.Thread(target=worker, daemon=True).start()

    def _created(self, ok: bool, message: str):
        if not ok:
            self._busy(None, "Create account")
            self._say(message, "error")
            return
        self._on_connect_success()



# ---------------------------------------------------------------------------
# VIEW 2: The signed-in window. Navigation rail, the health bar, and one page
# ---------------------------------------------------------------------------
class MainView(ctk.CTkFrame):
    PAGES = (("companies", "Companies"), ("activity", "Activity"), ("settings", "Settings"))

    def __init__(self, parent, app: BridgeApp, page: str = "companies"):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.page: Optional[ctk.CTkFrame] = None
        self.page_name = ""
        self._health_key: Tuple = ()
        self._action = "sync"
        self._bar_running = False

        self._build_rail()
        ctk.CTkFrame(self, fg_color=BORDER, width=1).pack(side="left", fill="y")
        self.column = ctk.CTkFrame(self, fg_color="transparent")
        self.column.pack(side="left", fill="both", expand=True)
        self._build_health_bar()
        ctk.CTkFrame(self.column, fg_color=BORDER, height=1).pack(fill="x")
        self.body = ctk.CTkFrame(self.column, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=20, pady=16)

        self.show_page(page)
        status = app.agent.get_status()
        self.refresh(status, health_from_status(status), [])

    # -- navigation ---------------------------------------------------------
    def _build_rail(self):
        rail = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=0, width=176)
        rail.pack(side="left", fill="y")
        rail.pack_propagate(False)

        brand = ctk.CTkFrame(rail, fg_color="transparent")
        brand.pack(fill="x", padx=14, pady=(16, 14))
        if self.app.pil_icon:
            logo = ctk.CTkImage(light_image=self.app.pil_icon, dark_image=self.app.pil_icon, size=(24, 24))
            ctk.CTkLabel(brand, text="", image=logo).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(brand, text=APP_SHORT, font=font(16, True), text_color=TEXT).pack(side="left")

        self.nav: Dict[str, ctk.CTkButton] = {}
        for name, label in self.PAGES:
            self.nav[name] = ctk.CTkButton(rail, text=label, anchor="w", height=32, corner_radius=RADIUS_CONTROL, font=font(13),
                                           fg_color="transparent", hover_color=SUBTLE, text_color=TEXT_2,
                                           command=lambda n=name: self.show_page(n))
            self.nav[name].pack(fill="x", padx=10, pady=1)

        ctk.CTkLabel(rail, text=f"{platform.node() or 'This PC'}\nVersion {APP_VERSION}", font=font(11), text_color=TEXT_3,
                     justify="left").pack(side="bottom", anchor="w", padx=18, pady=12)

    def show_page(self, name: str):
        if self.page is not None:
            self.page.destroy()
        self.page_name = name
        for key, button in self.nav.items():
            button.configure(fg_color=SUBTLE if key == name else "transparent", text_color=TEXT if key == name else TEXT_2,
                             font=font(13, key == name))
        self.page = {"companies": CompaniesPage, "activity": ActivityPage, "settings": SettingsPage}[name](self.body, self.app)
        self.page.pack(fill="both", expand=True)

    def theme_changed(self):
        self._health_key = ()   # the tray badge and the log colours are fixed colours, not pairs
        if isinstance(self.page, ActivityPage):
            self.page.apply_tag_colors()

    # -- health bar ---------------------------------------------------------
    def _build_health_bar(self):
        bar = ctk.CTkFrame(self.column, fg_color=SURFACE, corner_radius=0)
        bar.pack(fill="x")
        top = ctk.CTkFrame(bar, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=(14, 8))

        self.badge = ctk.CTkLabel(top, text="", width=36, height=36, corner_radius=18, font=font(15, True))
        self.badge.pack(side="left", padx=(0, 12))

        # Buttons first, so a long sentence wraps beside them and never pushes them off the window
        self.more_btn = secondary_button(top, "More", self._open_more_menu, width=58)
        self.more_btn.pack(side="right", padx=(8, 0))
        self.main_btn = primary_button(top, "Sync now", self._on_main_action, width=108)
        self.main_btn.pack(side="right")

        words = ctk.CTkFrame(top, fg_color="transparent")
        words.pack(side="left", fill="x", expand=True)
        self.title_lbl = ctk.CTkLabel(words, text="", font=font(16, True), text_color=TEXT, anchor="w")
        self.title_lbl.pack(fill="x")
        self.detail_lbl = ctk.CTkLabel(words, text="", font=font(12), text_color=TEXT_2, anchor="w", justify="left", wraplength=470)
        self.detail_lbl.pack(fill="x")

        self.progress = ctk.CTkProgressBar(bar, height=4, corner_radius=2, fg_color=SUBTLE, progress_color=STATE["sync"]["solid"],
                                           mode="indeterminate")
        self.progress_slot = ctk.CTkFrame(bar, fg_color="transparent", height=4)
        self.progress_slot.pack(fill="x", padx=20)

        chips = ctk.CTkFrame(bar, fg_color="transparent")
        chips.pack(fill="x", padx=20, pady=(8, 12))
        self.tally_dot = ctk.CTkLabel(chips, text="●", font=font(11), text_color=STATE["idle"]["solid"])
        self.tally_dot.pack(side="left")
        self.tally_chip = ctk.CTkLabel(chips, text="TallyPrime", font=font(12), text_color=TEXT_2)
        self.tally_chip.pack(side="left", padx=(5, 16))
        self.cloud_dot = ctk.CTkLabel(chips, text="●", font=font(11), text_color=STATE["idle"]["solid"])
        self.cloud_dot.pack(side="left")
        self.cloud_chip = ctk.CTkLabel(chips, text="Server", font=font(12), text_color=TEXT_2)
        self.cloud_chip.pack(side="left", padx=(5, 0))

    def _on_main_action(self):
        agent = self.app.agent
        if self._action == "resume":
            agent.resume()
        elif self._action == "signin":
            self.app.show_setup()
        else:
            agent.trigger_immediate_sync(force_full=False)

    def _open_more_menu(self):
        agent = self.app.agent
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Full re-sync...", command=self._full_resync)
        menu.add_command(label="Resume syncing" if agent.is_paused else "Pause syncing",
                         command=agent.resume if agent.is_paused else agent.pause)
        menu.add_separator()
        menu.add_command(label="Hide to tray", command=self.app.minimize_to_tray)
        menu.tk_popup(self.more_btn.winfo_rootx(), self.more_btn.winfo_rooty() + self.more_btn.winfo_height() + 2)

    def _full_resync(self):
        from tkinter import messagebox
        if messagebox.askyesno("Run a full re-sync?", "Every record of every linked company is checked again, not just what "
                               "changed. This can take a long time for a large company.\n\nNothing is deleted."):
            self.app.agent.trigger_immediate_sync(force_full=True)

    def refresh(self, status: Dict[str, Any], health: Dict[str, str], fresh_logs: List[Tuple[str, str]]):
        """Once a second. Widgets are only touched when what they show has changed."""
        agent = self.app.agent
        # A requested sync shows as busy from the click until the agent has picked it up and finished it
        busy = bool(status.get("is_syncing") or (agent.immediate_sync_requested and health["action"] in ("sync", "retry")))
        t_ok, c_ok, halted = status.get("tally_connected", False), status.get("cloud_connected", False), bool(status.get("auth_halt_reason"))
        key = (health["kind"], health["title"], health["detail"], busy, t_ok, c_ok, halted, ctk.get_appearance_mode())
        if key != self._health_key:
            self._health_key = key
            look = STATE[health["kind"]]
            self._action = health["action"]
            self.badge.configure(text=look["glyph"], fg_color=look["bg"], text_color=look["fg"])
            self.title_lbl.configure(text=health["title"])
            self.detail_lbl.configure(text=health["detail"])
            label = {"resume": "Resume", "retry": "Retry", "signin": "Sign in again"}.get(health["action"], "Sync now")
            self.main_btn.configure(text="Syncing..." if busy else label, state="disabled" if busy else "normal")

            if busy and not self._bar_running:
                self.progress.pack(in_=self.progress_slot, fill="x")
                self.progress.start()
            elif not busy and self._bar_running:
                self.progress.stop()
                self.progress.pack_forget()
            self._bar_running = busy

            self.tally_dot.configure(text_color=STATE["ok" if t_ok else "error"]["solid"])
            self.tally_chip.configure(text="TallyPrime connected" if t_ok else "TallyPrime not running")
            self.cloud_dot.configure(text_color=STATE["ok" if c_ok and not halted else "error"]["solid"])
            self.cloud_chip.configure(text="Signed out" if halted else ("Server connected" if c_ok else "Server offline"))

        if isinstance(self.page, ActivityPage):
            for message, level in fresh_logs:
                self.page.append_log(message, level)
        elif isinstance(self.page, CompaniesPage):
            self.page.tick(status)


class CompaniesPage(ctk.CTkFrame):
    """The companies this PC syncs, and the ones open in Tally that it could. Linking is always a choice made
    here: the agent never starts syncing a company just because it is open."""

    def __init__(self, parent, app: BridgeApp):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._syncing_name: Optional[str] = None
        self._notes: Dict[str, Tuple[ctk.CTkLabel, str, str]] = {}   # company name -> its status line, text, kind
        self._open: Dict[str, Dict[str, Any]] = {}                  # what is open in Tally, by GUID

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", pady=(0, 2))
        ctk.CTkLabel(head, text="Companies", font=font(20, True), text_color=TEXT).pack(side="left")
        secondary_button(head, "Refresh", self.refresh, width=76).pack(side="right")
        ctk.CTkLabel(self, text="Open a company in TallyPrime to link it. A company is synced from one PC at a time.",
                     font=font(12), text_color=TEXT_3).pack(anchor="w", pady=(0, 8))
        self.status = ctk.CTkLabel(self, text="", font=font(12), text_color=TEXT_3, wraplength=640, justify="left")
        self.status.pack(side="bottom", anchor="w", pady=(6, 0))
        self.rows = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.rows.pack(fill="both", expand=True)
        self.refresh()

    def _say(self, text: str, kind: str = "idle"):
        if self.winfo_exists():
            self.status.configure(text=text, text_color=STATE[kind]["fg"])

    def refresh(self):
        agent = self.app.agent
        if agent.cloud.device_mode:
            self._say("Checking TallyPrime...")

        def worker():
            overview = core.companies_overview(agent)
            self.after(0, lambda: self._drawn(overview))

        threading.Thread(target=worker, daemon=True).start()

    def _drawn(self, overview: Dict[str, Any]):
        if not self.winfo_exists():
            return
        self._open = overview["open"]
        self._render_rows(overview)
        if not overview["device_mode"]:
            self._say("This PC is not signed in as a sync device yet. Sign in again from Settings to manage companies here.", "warn")
        else:
            self._say("" if overview["any_open"] else "No company is open in TallyPrime.")

    def _section(self, text: str):
        ctk.CTkLabel(self.rows, text=text.upper(), font=font(11, True), text_color=TEXT_3).pack(anchor="w", padx=6, pady=(10, 2))

    def _render_rows(self, overview: Dict[str, Any]):
        for child in self.rows.winfo_children():
            child.destroy()
        self._notes, self._syncing_name = {}, None
        if overview["linked"]:
            self._section("Linked to this PC")
        for company in overview["linked"]:
            self._row(company["name"], company["note"], company["kind"], "Unlink", lambda c=company: self._unlink(c))
        if overview["unlinked"]:
            self._section("Open in Tally, not linked")
        for company in overview["unlinked"]:
            self._row(company["name"], company["note"], company["kind"], "Link", lambda c=company: self._link(self._open[c["guid"]]))
        if overview["device_mode"] and not overview["linked"] and not overview["unlinked"]:
            ctk.CTkLabel(self.rows, text="No companies yet. Open one in TallyPrime, then press Refresh.",
                         font=font(13), text_color=TEXT_2).pack(anchor="w", padx=6, pady=16)

    def _row(self, name: str, note: str, kind: str, action: str, command):
        row = card(self.rows)
        row.pack(fill="x", pady=4, padx=4)
        make = danger_button if action == "Unlink" else secondary_button
        make(row, action, command, width=76).pack(side="right", padx=12, pady=10)
        text = ctk.CTkFrame(row, fg_color="transparent")
        text.pack(side="left", fill="x", expand=True, padx=14, pady=9)
        ctk.CTkLabel(text, text=name, font=font(14, True), text_color=TEXT, anchor="w").pack(fill="x")
        note_lbl = ctk.CTkLabel(text, text=note, font=font(12), text_color=STATE[kind]["fg"], anchor="w")
        note_lbl.pack(fill="x")
        if action == "Unlink":
            self._notes[name] = (note_lbl, note, kind)

    def tick(self, status: Dict[str, Any]):
        """Show which linked company is being synced right now, from what the agent already knows."""
        name = status.get("active_company_name") if status.get("is_syncing") else None
        if name == self._syncing_name:
            return
        for company, (label, note, kind) in self._notes.items():
            if label.winfo_exists():
                syncing = company == name
                label.configure(text="Syncing now..." if syncing else note, text_color=STATE["sync" if syncing else kind]["fg"])
        self._syncing_name = name

    def _link(self, company, take_over: bool = False):
        self._say(f"Linking '{company['name']}'...")
        details = core.company_details(company, self.app.config.tally_url)

        def worker():
            ok, message, reason = self.app.agent.link_company(details, take_over=take_over)
            self.after(0, lambda: self._linked(company, ok, message, reason))

        threading.Thread(target=worker, daemon=True).start()

    def _linked(self, company, ok: bool, message: str, reason: str):
        if ok:
            self.app.agent.trigger_immediate_sync()
            self.refresh()
            return
        if reason == "linked_to_another_device":
            from tkinter import messagebox
            if messagebox.askyesno("Move sync to this PC?", f"{message}\n\nThe other PC will stop syncing this company.", parent=self):
                self._link(company, take_over=True)
                return
        self._say(message, "error")

    def _unlink(self, company):
        from tkinter import messagebox
        if not messagebox.askyesno("Stop syncing this company?",
                                   f"'{company['name']}' will no longer be synced from this PC. Its data in the app stays.", parent=self):
            return

        def worker():
            ok = self.app.agent.unlink_company(company["guid"])
            self.after(0, lambda: (self.refresh() if ok else self._say("Could not unlink. Check the connection and try again.", "error")))

        threading.Thread(target=worker, daemon=True).start()


class ActivityPage(ctk.CTkFrame):
    """What the agent has been doing, newest at the bottom."""

    def __init__(self, parent, app: BridgeApp):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", pady=(0, 2))
        ctk.CTkLabel(head, text="Activity", font=font(20, True), text_color=TEXT).pack(side="left")
        secondary_button(head, "Clear", self.clear_logs, width=64).pack(side="right")
        ctk.CTkLabel(self, text="Everything the agent has done since it started. Support may ask for this.",
                     font=font(12), text_color=TEXT_3).pack(anchor="w", pady=(0, 8))

        self.log_textbox = ctk.CTkTextbox(self, fg_color=SURFACE, text_color=TEXT_2, border_width=1, border_color=BORDER,
                                          font=ctk.CTkFont(family=MONO_FONT, size=11), wrap="word", corner_radius=RADIUS_CARD)
        self.log_textbox.pack(fill="both", expand=True)
        self.apply_tag_colors()
        for message, level in list(app.log_history):
            self.append_log(message, level, scroll=False)
        self.log_textbox.see("end")

    def apply_tag_colors(self):
        try:
            tb = getattr(self.log_textbox, "_textbox", None)
            if tb:
                dark = 1 if ctk.get_appearance_mode() == "Dark" else 0
                tb.tag_config("error", foreground=STATE["error"]["fg"][dark])
                tb.tag_config("warning", foreground=STATE["warn"]["fg"][dark])
                tb.tag_config("success", foreground=STATE["ok"]["fg"][dark])
                tb.tag_config("info", foreground=TEXT_2[dark])
        except Exception:
            pass

    def append_log(self, message: str, level: str, scroll: bool = True):
        message, tag = core.log_line(message, level)

        try:
            tb = getattr(self.log_textbox, "_textbox", None)
            if tb:
                tb.insert("end", f"{message}\n", tag)
                line_count = int(tb.index('end-1c').split('.')[0])
                if line_count > 1500:
                    tb.delete("1.0", f"{line_count - 1000}.0")
                if scroll:
                    tb.see("end")
            else:
                self.log_textbox.insert("end", f"{message}\n")
                self.log_textbox.see("end")
        except Exception:
            self.log_textbox.insert("end", f"{message}\n")
            self.log_textbox.see("end")

    def clear_logs(self):
        self.app.log_history.clear()
        self.log_textbox.delete("1.0", "end")


class SettingsPage(ctk.CTkFrame):
    def __init__(self, parent, app: BridgeApp):
        super().__init__(parent, fg_color="transparent")
        self.app = app

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(head, text="Settings", font=font(20, True), text_color=TEXT).pack(side="left")
        self.save_btn = primary_button(head, "Save", self._save_settings, width=76)
        self.save_btn.pack(side="right")
        self.feedback_lbl = ctk.CTkLabel(head, text="", font=font(12), text_color=TEXT_3)
        self.feedback_lbl.pack(side="right", padx=12)

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True)

        self._build_connection()
        self._build_schedule()
        self._build_this_pc()
        self._build_account()
        self._build_support()
        self._build_advanced()
        self._build_quit()

    def _group(self, title: str, text: str = "") -> ctk.CTkFrame:
        box = card(self.scroll)
        box.pack(fill="x", pady=(0, 12), padx=4)
        ctk.CTkLabel(box, text=title, font=font(14, True), text_color=TEXT).pack(anchor="w", padx=16, pady=(12, 2 if text else 8))
        if text:
            ctk.CTkLabel(box, text=text, font=font(12), text_color=TEXT_3, wraplength=600, justify="left").pack(anchor="w", padx=16, pady=(0, 10))
        return box

    def _number_row(self, parent, label: str, value: Any, help_text: str = "") -> ctk.CTkEntry:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 10))
        box = entry(row, width=70)
        box.insert(0, str(value))
        box.pack(side="left")
        ctk.CTkLabel(row, text=label, font=font(13), text_color=TEXT_2).pack(side="left", padx=(10, 0))
        if help_text:
            ctk.CTkLabel(row, text=help_text, font=font(11), text_color=TEXT_3).pack(side="left", padx=(10, 0))
        return box

    def _switch(self, parent, text: str, variable: tk.BooleanVar, last: bool = False):
        ctk.CTkSwitch(parent, text=text, variable=variable, font=font(13), text_color=TEXT_2, progress_color=PRIMARY,
                      fg_color=BORDER_INPUT, button_color=SURFACE, button_hover_color=SUBTLE).pack(anchor="w", padx=16, pady=(0, 14 if last else 10))

    def _build_connection(self):
        box = self._group("Connection")

        host_part, port_part = core.split_tally_url(self.app.config.tally_url)

        ctk.CTkLabel(box, text="TallyPrime computer and port", font=font(12, True), text_color=TEXT_2).pack(anchor="w", padx=16, pady=(0, 2))
        host_port_row = ctk.CTkFrame(box, fg_color="transparent")
        host_port_row.pack(fill="x", padx=16, pady=(0, 2))
        self.host_entry = entry(host_port_row, placeholder_text="localhost")
        self.host_entry.insert(0, host_part)
        self.host_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.port_entry = entry(host_port_row, placeholder_text="9000", width=80)
        self.port_entry.insert(0, port_part)
        self.port_entry.pack(side="left")
        ctk.CTkLabel(box, text="Use localhost when TallyPrime runs on this PC. Its default port is 9000.",
                     font=font(11), text_color=TEXT_3).pack(anchor="w", padx=16, pady=(0, 10))

        self.backend_url_entry = field(box, "Server address", padx=16)
        self.backend_url_entry.insert(0, self.app.config.backend_url or "")
        ctk.CTkFrame(box, fg_color="transparent", height=4).pack()

    def _build_schedule(self):
        box = self._group("Schedule", "How often Bridge looks for changes, in seconds.")
        self.outbound_entry = self._number_row(box, "Send changes made in the app to Tally", self.app.config.sync_interval_seconds or 5)
        self.inbound_entry = self._number_row(box, "Check Tally for new and changed records", self.app.config.inbound_interval_seconds or 60)
        ctk.CTkFrame(box, fg_color="transparent", height=4).pack()

    def _build_this_pc(self):
        box = self._group("This PC")
        self.autostart_var = tk.BooleanVar(value=self.app.config.autostart_enabled or is_autostart_registered())
        self._switch(box, "Start with Windows", self.autostart_var)

        row = ctk.CTkFrame(box, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 14))
        ctk.CTkLabel(row, text="Theme", font=font(13), text_color=TEXT_2).pack(side="left", padx=(0, 12))
        current = next((label for label, value in THEMES.items() if value == self.app.config.theme), "System")
        theme = ctk.CTkSegmentedButton(row, values=list(THEMES), font=font(12, True), corner_radius=RADIUS_CONTROL,
                                       fg_color=SUBTLE, unselected_color=SUBTLE, unselected_hover_color=BORDER,
                                       selected_color=PRIMARY, selected_hover_color=PRIMARY_HOVER, text_color=TEXT,
                                       command=lambda label: self.app.set_theme(THEMES[label]))
        theme.set(current)
        theme.pack(side="left")

    def _build_account(self):
        box = self._group("Account")
        user_str = self.app.config.email or self.app.config.username or "a saved sign-in"
        ctk.CTkLabel(box, text=f"Signed in as {user_str}", font=font(13), text_color=TEXT_2).pack(anchor="w", padx=16, pady=(0, 10))
        secondary_button(box, "Sign in as someone else", self.app.show_setup).pack(anchor="w", padx=16, pady=(0, 14))

    def _build_support(self):
        box = self._group("Support", "Support may ask for the log files. Export puts them in one zip file on the Desktop.")
        row = ctk.CTkFrame(box, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 14))
        secondary_button(row, "Open logs folder", self._open_logs_folder).pack(side="left", padx=(0, 8))
        secondary_button(row, "Export logs", self._export_logs_zip).pack(side="left")

    def _build_advanced(self):
        box = self._group("Advanced", "Change these only if support asks you to.")
        self.range_entry = self._number_row(box, "Vouchers sent per request in a full re-sync", self.app.config.vouchers_per_range or 25,
                                            "Lower it if a full re-sync times out.")
        self.auto_discover_var = tk.BooleanVar(value=self.app.config.auto_discover_paths)
        self._switch(box, "Find the TallyPrime program and data folders automatically", self.auto_discover_var)
        self.force_full_sync_var = tk.BooleanVar(value=getattr(self.app.config, "force_full_sync", False))
        self._switch(box, "Re-check every record on each sync (slower)", self.force_full_sync_var, last=True)

    def _build_quit(self):
        box = self._group(f"Quit {APP_SHORT}", "Syncing stops until Bridge is opened again. Closing the window only hides it to the tray.")
        danger_button(box, f"Quit {APP_SHORT}", self.app._shutdown_app).pack(anchor="w", padx=16, pady=(0, 14))

    def _feedback(self, text: str, kind: str = "idle"):
        self.feedback_lbl.configure(text=text, text_color=STATE[kind]["fg"])

    def _save_settings(self):
        ok, message = core.apply_settings(self.app, {
            "tally_host": self.host_entry.get(), "tally_port": self.port_entry.get(), "backend_url": self.backend_url_entry.get(),
            "outbound_seconds": self.outbound_entry.get(), "inbound_seconds": self.inbound_entry.get(),
            "vouchers_per_range": self.range_entry.get(), "auto_discover_paths": self.auto_discover_var.get(),
            "force_full_sync": self.force_full_sync_var.get(), "autostart": self.autostart_var.get()})
        self._feedback(message, "ok" if ok else "error")
        if ok:
            self.after(3000, lambda: self.winfo_exists() and self._feedback(""))

    def _open_logs_folder(self):
        ok, message = core.open_logs_folder()
        if not ok:
            self._feedback(message, "warn")

    def _export_logs_zip(self):
        ok, message = core.export_logs_zip()
        self._feedback(message, "ok" if ok else "error")



# ---------------------------------------------------------------------------
# Application Entry Point
# ---------------------------------------------------------------------------
def main():
    if not check_single_instance():
        sys.exit(0)
    # The web window where Edge WebView2 is there to draw it; this CustomTkinter one everywhere else, and
    # always with --classic.
    if "--classic" not in sys.argv:
        try:
            import webview_app
            if webview_app.available():
                webview_app.run()
                return
        except Exception as e:
            print(f"The web window could not open ({e}); opening the classic one.")
    app = BridgeApp()
    app.mainloop()

if __name__ == "__main__":
    main()
