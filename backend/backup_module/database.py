import sqlite3
import contextlib
from typing import Generator
from .config import settings

def get_db_connection() -> sqlite3.Connection:
    """Returns a SQLite connection with Row factory and WAL mode enabled."""
    conn = sqlite3.connect(str(settings.SQLITE_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn

@contextlib.contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Context manager for safe database transactions."""
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    """Initializes tables for backups and restore logs in SQLite."""
    with get_db() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS backups (
            id TEXT PRIMARY KEY,
            company_name TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size_bytes INTEGER DEFAULT 0,
            record_counts TEXT DEFAULT '{}',
            total_masters INTEGER DEFAULT 0,
            total_vouchers INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            progress_percent INTEGER DEFAULT 0,
            progress_message TEXT DEFAULT '',
            error_message TEXT DEFAULT '',
            checksum_sha256 TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            completed_at TEXT
        )
        """)
        
        conn.execute("""
        CREATE TABLE IF NOT EXISTS restore_logs (
            id TEXT PRIMARY KEY,
            backup_id TEXT NOT NULL,
            company_name TEXT NOT NULL,
            target_company_name TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            progress_percent INTEGER DEFAULT 0,
            progress_message TEXT DEFAULT '',
            summary TEXT DEFAULT '{}',
            error_message TEXT DEFAULT '',
            started_at TEXT NOT NULL,
            completed_at TEXT,
            FOREIGN KEY (backup_id) REFERENCES backups (id) ON DELETE CASCADE
        )
        """)

# Initialize database on module load
init_db()
