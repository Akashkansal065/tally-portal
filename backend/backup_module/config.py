import os
from pathlib import Path

# Base directories
MODULE_DIR = Path(__file__).resolve().parent
DEFAULT_BACKUP_DIR = MODULE_DIR / "backups"
DEFAULT_DB_PATH = MODULE_DIR / "backup.db"
DEFAULT_QUERIES_DIR = MODULE_DIR / "tally_queries"

def load_env_file():
    """Load backend/.env if environment variables are not already set."""
    backend_env = MODULE_DIR.parent / ".env"
    if backend_env.exists():
        try:
            with open(backend_env, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    if key and key not in os.environ:
                        os.environ[key] = val
        except Exception:
            pass

load_env_file()

class BackupSettings:
    """Isolated configuration for Tally Backup & Restore Module."""
    
    TALLY_URL: str = os.getenv("TALLY_URL", "http://192.168.1.42:9000").rstrip("/")
    TALLY_TIMEOUT: int = int(os.getenv("TALLY_BACKUP_TIMEOUT", "600"))  # seconds
    
    BACKUP_DIR: Path = Path(os.getenv("BACKUP_STORAGE_DIR", str(DEFAULT_BACKUP_DIR)))
    SQLITE_DB_PATH: Path = Path(os.getenv("BACKUP_DB_PATH", str(DEFAULT_DB_PATH)))
    QUERIES_DIR: Path = DEFAULT_QUERIES_DIR
    
    # Standalone server settings
    SERVER_HOST: str = os.getenv("BACKUP_SERVER_HOST", "0.0.0.0")
    SERVER_PORT: int = int(os.getenv("BACKUP_SERVER_PORT", "8001"))

settings = BackupSettings()
settings.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
