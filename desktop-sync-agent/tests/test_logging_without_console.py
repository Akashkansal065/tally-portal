"""The windowed .exe has no console: stdout is None and stderr encodes cp1252. A log line with an emoji used to
raise UnicodeEncodeError out of logger.info(), stopping sign-in at its first line and the sync thread at start-up."""
import os
import subprocess
import sys

AGENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

LIKE_THE_EXE = r"""
import io, sys
sys.stdout = None
sys.stderr = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
import logging
import agent
logging.getLogger("MyTallySyncAgent").info("🔑 Signing this PC in to http://192.168.1.39:8000 as someone@example.com…")
logging.getLogger("Backups").warning("💾 Backups wait until a folder is chosen")
sys.__stdout__.write("logged without raising\n")
"""


def test_logging_an_emoji_never_raises_without_a_console(tmp_path):
    env = {**os.environ, "LOCALAPPDATA": str(tmp_path), "APPDATA": str(tmp_path), "PYTHONIOENCODING": ""}
    run = subprocess.run([sys.executable, "-c", LIKE_THE_EXE], cwd=AGENT_DIR, env=env, capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr[-2000:]
    assert "logged without raising" in run.stdout
