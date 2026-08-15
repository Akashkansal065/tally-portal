import os
import sys
import json
from dataclasses import dataclass, asdict
from typing import Optional

def get_default_config_path() -> str:
    """Returns absolute path to agent_config.json next to the running .exe or script."""
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "agent_config.json")

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

def load_config(config_path: Optional[str] = None) -> AgentConfig:
    """Loads configuration from JSON file or environment variables, creates default if missing."""
    if not config_path:
        config_path = get_default_config_path()

    cfg = AgentConfig()
    
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in data.items():
                    if hasattr(cfg, k):
                        setattr(cfg, k, v)
        except Exception as e:
            print(f"⚠️ Warning reading {config_path}: {e}. Using defaults.")
    else:
        save_config(cfg, config_path)

    # Environment variable overrides
    cfg.backend_url = os.environ.get("MYTALLY_BACKEND_URL", cfg.backend_url)
    cfg.tally_url = os.environ.get("TALLY_URL", cfg.tally_url)
    cfg.auth_token = os.environ.get("MYTALLY_AUTH_TOKEN", cfg.auth_token)
    cfg.company_name = os.environ.get("TALLY_COMPANY_NAME", cfg.company_name)

    return cfg

def save_config(cfg: AgentConfig, config_path: str = CONFIG_FILE) -> None:
    """Saves configuration to JSON file."""
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(asdict(cfg), f, indent=4)
    except Exception as e:
        print(f"❌ Error writing config to {config_path}: {e}")
