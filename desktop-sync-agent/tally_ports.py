"""Finding where TallyPrime's XML server really is, when the configured address does not answer (WS-12).

Guided, never silent: nothing here changes the configured URL. The agent offers a port that answered *and* named
a company already linked to this PC, and the person accepts it in the health bar.

Order tried: the ServerPort in tally.ini (found from a remembered path or the standard install folders), then the
common ports. "Is Tally running" only words the message; it is read from `tasklist` and never from netstat, and
tally.exe is never started from here.
"""
import os
import re
import subprocess
import sys
from typing import Callable, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

COMMON_PORTS = (9000, 9001, 9002, 9003, 9004, 9005, 9999)
_SERVER_PORT = re.compile(r"^\s*ServerPort\s*=\s*(\d{2,5})\s*$", re.I | re.M)


def read_server_port(ini_text: str) -> Optional[int]:
    """ServerPort= from tally.ini text, or None when it is absent or not a usable port."""
    found = _SERVER_PORT.search(ini_text or "")
    if not found:
        return None
    port = int(found.group(1))
    return port if 1 <= port <= 65535 else None


def standard_ini_paths(hint: str = "") -> List[str]:
    """Where tally.ini may be: the path Tally itself reported earlier, then the standard install folders."""
    paths: List[str] = []
    if hint:
        paths.append(hint)
    for env in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432", "SystemDrive"):
        base = os.environ.get(env)
        if not base:
            continue
        base = base + "\\" if env == "SystemDrive" else base
        for folder in ("TallyPrime", "Tally.ERP9", "TallyPrime Edit Log"):
            paths.append(os.path.join(base, folder, "tally.ini"))
    seen, ordered = set(), []
    for p in paths:
        if p and p not in seen:
            seen.add(p)
            ordered.append(p)
    return ordered


def candidate_ports(current_port: int, ini_paths: Iterable[str],
                    read_text: Callable[[str], Optional[str]] = None) -> List[int]:
    """The ports worth trying, in order, without the one already tried."""
    def default_read(path: str) -> Optional[str]:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except OSError:
            return None
    reader = read_text or default_read
    ports: List[int] = []
    for path in ini_paths:
        port = read_server_port(reader(path) or "")
        if port:
            ports.append(port)
    ports += list(COMMON_PORTS)
    out: List[int] = []
    for p in ports:
        if p != current_port and p not in out:
            out.append(p)
    return out


def tally_is_running(runner: Callable = None) -> Optional[bool]:
    """Whether a tally.exe process exists, from `tasklist`. None when that cannot be asked (not Windows, or the
    command failed): the message then says nothing about it."""
    if not sys.platform.startswith("win") and runner is None:
        return None
    run = runner or (lambda: subprocess.run(["tasklist", "/FI", "IMAGENAME eq tally.exe", "/NH"],
                                            capture_output=True, text=True, timeout=10).stdout)
    try:
        out = run() or ""
    except Exception:
        return None
    return "tally.exe" in out.lower()


def diagnosis_text(url: str, running: Optional[bool]) -> str:
    port = urlparse(url).port or 9000
    if running is False:
        return "TallyPrime isn't running on this PC. Open it and syncing resumes by itself."
    if running is True:
        return (f"TallyPrime is running but isn't answering on port {port}. In TallyPrime press F1 (Help) > Settings > "
                "Connectivity and switch the ODBC/XML server on, or check the port there.")
    return f"TallyPrime isn't answering on {url}. Open it, and check F1 (Help) > Settings > Connectivity."


def find_port_offer(current_url: str, linked_guids: Iterable[str], probe: Callable[[str], List[Dict[str, str]]],
                    ini_paths: Iterable[str], read_text: Callable[[str], Optional[str]] = None) -> Optional[Dict[str, object]]:
    """Try the candidate ports. `probe(url)` returns the open companies [{name, guid}] of a Tally answering there,
    or []. An offer is made only for a port that names a company whose GUID is already linked."""
    parsed = urlparse(current_url)
    host = parsed.hostname or "127.0.0.1"
    scheme = parsed.scheme or "http"
    linked = {g for g in linked_guids if g}
    if not linked:
        return None
    for port in candidate_ports(parsed.port or 80, ini_paths, read_text):
        url = f"{scheme}://{host}:{port}"
        try:
            companies = probe(url) or []
        except Exception:
            continue
        for company in companies:
            if company.get("guid") in linked:
                return {"url": url, "port": port, "company": company.get("name", "")}
    return None
