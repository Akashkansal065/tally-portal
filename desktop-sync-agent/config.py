import os
import sys
import json
from dataclasses import dataclass, asdict
from typing import Optional

from security import encrypt_secret, decrypt_secret, is_encrypted

def get_app_dir() -> str:
    """Returns absolute path to the directory containing the running .exe or script."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

def get_logs_dir() -> str:
    """Returns absolute path to logs directory, safe for Windows autostart & restricted permissions."""
    app_dir = get_app_dir()
    logs_dir = os.path.join(app_dir, "logs")
    try:
        os.makedirs(logs_dir, exist_ok=True)
        test_file = os.path.join(logs_dir, ".write_test")
        with open(test_file, "w") as f:
            f.write("ok")
        os.remove(test_file)
        return logs_dir
    except Exception:
        appdata = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or os.path.expanduser("~")
        logs_dir = os.path.join(appdata, "SnehDistribuorsSync", "logs")
        os.makedirs(logs_dir, exist_ok=True)
        return logs_dir

def get_default_config_path() -> str:
    """Returns absolute path to agent_config.json next to the running .exe or script."""
    return os.path.join(get_app_dir(), "agent_config.json")

CONFIG_FILE = get_default_config_path()

@dataclass
class AgentConfig:
    backend_url: str = "http://MacBook-Air.local:8000"
    tally_url: str = "http://127.0.0.1:9000"
    auth_token: str = ""
    email: str = ""
    username: str = ""
    password: str = ""
    company_name: str = "Bhrama Enterprises"
    sync_interval_seconds: int = 5
    inbound_interval_seconds: int = 60
    tally_app_path: Optional[str] = None
    tally_data_path: Optional[str] = None
    auto_discover_paths: bool = True
    autostart_enabled: bool = False
    force_full_sync: bool = False

def is_autostart_registered() -> bool:
    """Checks if the application is currently registered to start with Windows."""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_READ
        )
        for app_name in ["SnehDistribuorsSyncAgent", "MyTallySyncAgent"]:
            try:
                val, _ = winreg.QueryValueEx(key, app_name)
                winreg.CloseKey(key)
                return bool(val)
            except FileNotFoundError:
                continue
        winreg.CloseKey(key)
        return False
    except Exception:
        return False

def install_startup(target_script: Optional[str] = None) -> bool:
    """Registers the agent into Windows Startup Registry to launch automatically on boot in tray."""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE
        )
        if getattr(sys, 'frozen', False):
            cmd = f'"{os.path.abspath(sys.executable)}" --tray'
        else:
            script = target_script or os.path.join(get_app_dir(), "gui_app.py")
            if not os.path.exists(script):
                script = os.path.join(get_app_dir(), "agent.py")
            cmd = f'"{sys.executable}" "{os.path.abspath(script)}" --tray'
            
        winreg.SetValueEx(key, "SnehDistribuorsSyncAgent", 0, winreg.REG_SZ, cmd)
        winreg.CloseKey(key)
        return True
    except Exception as e:
        print(f"❌ Failed to configure Windows autostart: {e}")
        return False

def uninstall_startup() -> bool:
    """Removes the agent from Windows Startup Registry."""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE
        )
        for app_name in ["SnehDistribuorsSyncAgent", "MyTallySyncAgent"]:
            try:
                winreg.DeleteValue(key, app_name)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        return True
    except Exception as e:
        print(f"❌ Failed to remove Windows autostart: {e}")
        return False

def load_config(config_path: Optional[str] = None) -> AgentConfig:
    """Loads configuration from JSON file or environment variables, creates default if missing.
    Automatically decrypts sensitive credentials into memory, and migrates legacy plaintext credentials to encrypted format."""
    if not config_path:
        config_path = get_default_config_path()

    cfg = AgentConfig()
    needs_re_encryption = False
    
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in data.items():
                    if hasattr(cfg, k):
                        if k in ("password", "auth_token") and isinstance(v, str) and v:
                            if not is_encrypted(v):
                                # Existing plaintext in JSON: mark for auto-migration
                                needs_re_encryption = True
                            v = decrypt_secret(v)
                        setattr(cfg, k, v)
        except Exception as e:
            print(f"⚠️ Warning reading {config_path}: {e}. Using defaults.")
    else:
        save_config(cfg, config_path)

    # Check autostart if on Windows
    if sys.platform == "win32":
        cfg.autostart_enabled = is_autostart_registered()

    # Environment variable overrides
    cfg.backend_url = os.environ.get("MYTALLY_BACKEND_URL", cfg.backend_url)
    cfg.tally_url = os.environ.get("TALLY_URL", cfg.tally_url)
    cfg.auth_token = os.environ.get("MYTALLY_AUTH_TOKEN", cfg.auth_token)
    cfg.company_name = os.environ.get("TALLY_COMPANY_NAME", cfg.company_name)
    if os.environ.get("MYTALLY_FORCE_FULL_SYNC"):
        cfg.force_full_sync = os.environ.get("MYTALLY_FORCE_FULL_SYNC", "").lower() in ("1", "true", "yes")

    # If legacy plaintext credentials were found on disk, auto-encrypt and update the file
    if needs_re_encryption:
        try:
            save_config(cfg, config_path)
            print("🔒 Migrated plaintext credentials to encrypted format in config.")
        except Exception:
            pass

    return cfg

def save_config(cfg: AgentConfig, config_path: str = CONFIG_FILE) -> None:
    """Saves configuration to JSON file with machine-bound encrypted credentials."""
    try:
        data = asdict(cfg)
        # Encrypt sensitive fields before saving to disk
        if data.get("password"):
            data["password"] = encrypt_secret(data["password"])
        if data.get("auth_token"):
            data["auth_token"] = encrypt_secret(data["auth_token"])

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"❌ Error writing config to {config_path}: {e}")
