"""Finding where TallyPrime's XML server really is, where it is installed, and launching it when requested (WS-12).

Guided, never silent: the agent offers a discovered port or address, and the person accepts it.
Features:
- Detect TallyPrime installation folder and executable across drives and registry (cached for speed)
- Find active listening TCP ports specifically belonging to the tally.exe process
- Read ServerPort from tally.ini
- Launch TallyPrime safely with repeat-protection when it is not running
- Auto-detect Tally server URL, port, company name, and company ID
"""
import os
import re
import subprocess
import sys
import threading
import time
from typing import Callable, Dict, Iterable, List, Optional, Tuple, Any
from urllib.parse import urlparse

COMMON_PORTS = (9000, 9001, 9002, 9003, 9004, 9005, 9999)
_SERVER_PORT = re.compile(r"^\s*ServerPort\s*=\s*(\d{2,5})\s*$", re.I | re.M)

# Lock preventing simultaneous launch attempts across threads
_launch_lock = threading.Lock()

# Cache installation lookup for 5 minutes so background checks don't hit the disk/registry every minute
_cached_installation: Optional[Dict[str, Any]] = None
_cached_installation_at: float = 0.0

# Track when Tally was launched by the agent so diagnosis knows it is warming up
_tally_launched_at: float = 0.0
STARTUP_GRACE_SECONDS = 30.0


def is_tally_starting() -> bool:
    """Whether Tally was launched recently and may still be initializing its server."""
    return (time.time() - _tally_launched_at) < STARTUP_GRACE_SECONDS


def forget_installation_cache() -> None:
    """Clear cached installation path (useful for tests or after reinstall)."""
    global _cached_installation, _cached_installation_at, _tally_launched_at
    _cached_installation = None
    _cached_installation_at = 0.0
    _tally_launched_at = 0.0


def read_server_port(ini_text: str) -> Optional[int]:
    """ServerPort= from tally.ini text, or None when it is absent or not a usable port."""
    found = _SERVER_PORT.search(ini_text or "")
    if not found:
        return None
    port = int(found.group(1))
    return port if 1 <= port <= 65535 else None


def find_tally_installation(hint: str = "", use_cache: bool = True, is_running: Optional[bool] = None) -> Dict[str, Any]:
    """Finds where Tally is installed on this PC.
    Returns: {"exe_path": str, "ini_path": str, "install_dir": str, "is_running": bool}
    """
    global _cached_installation, _cached_installation_at

    now = time.time()
    if use_cache and not hint and _cached_installation and (now - _cached_installation_at < 300):
        running = tally_is_running() if is_running is None else is_running
        return {**_cached_installation, "is_running": running}
    if use_cache and hint and _cached_installation and (now - _cached_installation_at < 300):
        if _cached_installation.get("exe_path") == hint or _cached_installation.get("ini_path") == hint:
            running = tally_is_running() if is_running is None else is_running
            return {**_cached_installation, "is_running": running}

    if is_running is None:
        is_running = tally_is_running()

    exe_path = ""
    ini_path = ""

    # 1. If running on Windows, query the actual running process executable path
    if sys.platform.startswith("win") and is_running is True:
        try:
            ps_cmd = "(Get-Process -Name tally -ErrorAction SilentlyContinue).Path"
            proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd],
                                  capture_output=True, text=True, timeout=5)
            out = (proc.stdout or "").strip().splitlines()
            if out and os.path.isfile(out[0].strip()):
                exe_path = out[0].strip()
        except Exception:
            pass

        if not exe_path:
            try:
                proc = subprocess.run(["wmic", "process", "where", "name='tally.exe'", "get", "ExecutablePath", "/value"],
                                      capture_output=True, text=True, timeout=5)
                for line in (proc.stdout or "").splitlines():
                    if line.lower().startswith("executablepath=") and "=" in line:
                        candidate = line.split("=", 1)[1].strip()
                        if os.path.isfile(candidate):
                            exe_path = candidate
                            break
            except Exception:
                pass

    # 2. Check hint path
    if not exe_path and hint:
        h = str(hint).strip()
        if h.lower().endswith("tally.exe") and os.path.isfile(h):
            exe_path = h
        elif h.lower().endswith("tally.ini") and os.path.isfile(h):
            candidate = os.path.join(os.path.dirname(h), "tally.exe")
            if os.path.isfile(candidate):
                exe_path = candidate
            ini_path = h
        elif os.path.isdir(h):
            candidate = os.path.join(h, "tally.exe")
            if os.path.isfile(candidate):
                exe_path = candidate

    # 3. Check Windows Registry
    if not exe_path and sys.platform.startswith("win"):
        try:
            import winreg
            for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                try:
                    with winreg.OpenKey(root, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\tally.exe") as k:
                        val, _ = winreg.QueryValueEx(k, "")
                        if val and os.path.isfile(str(val).strip()):
                            exe_path = str(val).strip()
                            break
                except OSError:
                    pass

            if not exe_path:
                for u_path in (r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                               r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"):
                    try:
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, u_path) as uk:
                            count, _, _ = winreg.QueryInfoKey(uk)
                            for i in range(count):
                                sub = winreg.EnumKey(uk, i)
                                try:
                                    with winreg.OpenKey(uk, sub) as sk:
                                        disp, _ = winreg.QueryValueEx(sk, "DisplayName")
                                        if "tally" in str(disp).lower():
                                            loc, _ = winreg.QueryValueEx(sk, "InstallLocation")
                                            candidate = os.path.join(str(loc).strip(), "tally.exe")
                                            if os.path.isfile(candidate):
                                                exe_path = candidate
                                                break
                                except OSError:
                                    pass
                            if exe_path:
                                break
                    except OSError:
                        pass
        except Exception:
            pass

    # 4. Check common directories and drive letters across Windows
    if not exe_path:
        drives = []
        for d in ("C", "D", "E", "F"):
            drives.append(f"{d}:\\")
        for env in ("SystemDrive", "ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
            base = os.environ.get(env)
            if base:
                drives.append(base + "\\" if env == "SystemDrive" and not base.endswith("\\") else base)

        subfolders = (
            "TallyPrime",
            "TallyPrime Edit Log",
            "TallyPrime1",
            "TallyPrime2",
            "Tally.ERP9",
            "Tally.ERP 9",
            "Tally",
        )
        for base in drives:
            for folder in subfolders:
                candidate = os.path.join(base, folder, "tally.exe")
                if os.path.isfile(candidate):
                    exe_path = candidate
                    break
            if exe_path:
                break

    install_dir = os.path.dirname(exe_path) if exe_path else ""
    if exe_path and not ini_path:
        cand_ini = os.path.join(install_dir, "tally.ini")
        if os.path.isfile(cand_ini):
            ini_path = cand_ini

    result = {
        "exe_path": exe_path,
        "ini_path": ini_path,
        "install_dir": install_dir,
        "is_running": is_running,
    }
    if exe_path:
        _cached_installation = {
            "exe_path": exe_path,
            "ini_path": ini_path,
            "install_dir": install_dir,
        }
        _cached_installation_at = now
    return result


def find_tally_listening_ports(runner: Callable = None, target_pids: Optional[Iterable[str]] = None) -> List[int]:
    """Finds TCP ports that tally.exe is actively listening on using netstat or PowerShell.
    Only returns ports belonging to Tally processes."""
    ports: List[int] = []
    if runner is not None:
        try:
            out = runner() or ""
            target_set = {str(p) for p in target_pids} if target_pids else None
            for line in out.splitlines():
                if "LISTENING" in line:
                    tokens = line.strip().split()
                    if len(tokens) >= 5:
                        pid = tokens[-1]
                        if target_set is not None and pid not in target_set:
                            continue
                        addr = tokens[1]
                        if ":" in addr:
                            port_str = addr.rsplit(":", 1)[1]
                            if port_str.isdigit():
                                p = int(port_str)
                                if 1 <= p <= 65535 and p not in ports:
                                    ports.append(p)
            return ports
        except Exception:
            return []

    if not sys.platform.startswith("win"):
        return []

    # 1. Try PowerShell to find ports of process tally
    try:
        ps_cmd = "Get-NetTCPConnection -OwningProcess (Get-Process tally -ErrorAction SilentlyContinue).Id -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty LocalPort"
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd],
                              capture_output=True, text=True, timeout=5)
        for line in (proc.stdout or "").splitlines():
            line = line.strip()
            if line.isdigit():
                p = int(line)
                if 1 <= p <= 65535 and p not in ports:
                    ports.append(p)
        if ports:
            return ports
    except Exception:
        pass

    # 2. Fallback: tasklist PID + netstat -ano
    try:
        proc = subprocess.run(["tasklist", "/FI", "IMAGENAME eq tally.exe", "/FO", "CSV", "/NH"],
                              capture_output=True, text=True, timeout=5)
        pids = set()
        for line in (proc.stdout or "").splitlines():
            parts = line.split(",")
            if len(parts) >= 2 and "tally.exe" in parts[0].lower():
                pid_str = parts[1].strip(' "')
                if pid_str.isdigit():
                    pids.add(pid_str)

        if pids:
            net = subprocess.run(["netstat", "-ano", "-p", "tcp"],
                                 capture_output=True, text=True, timeout=5)
            for line in (net.stdout or "").splitlines():
                if "LISTENING" in line:
                    tokens = line.strip().split()
                    if len(tokens) >= 5 and tokens[-1] in pids:
                        addr = tokens[1]
                        if ":" in addr:
                            port_str = addr.rsplit(":", 1)[1]
                            if port_str.isdigit():
                                p = int(port_str)
                                if 1 <= p <= 65535 and p not in ports:
                                    ports.append(p)
    except Exception:
        pass

    return ports


def launch_tally(exe_path: Optional[str] = None) -> Tuple[bool, str]:
    """Starts TallyPrime on this computer if installed and not already running.
    Safe against repeat clicks: rejects starting if Tally is already running or currently starting up."""
    global _tally_launched_at

    with _launch_lock:
        running = tally_is_running()
        if running is not False:
            if running is True:
                return False, "TallyPrime is already running on this PC."
            return False, "Could not determine if TallyPrime is running. Please check or open it manually."

        if is_tally_starting():
            return False, "TallyPrime was just launched and is currently starting up. Please wait."

        if not exe_path:
            info = find_tally_installation(use_cache=True)
            exe_path = info.get("exe_path")

        if not exe_path or not os.path.isfile(exe_path):
            return False, "Could not find tally.exe on this computer. Please install TallyPrime or open it manually."

        install_dir = os.path.dirname(exe_path)
        creationflags = 0x00000008 if sys.platform.startswith("win") else 0  # DETACHED_PROCESS

        try:
            subprocess.Popen([exe_path], cwd=install_dir, creationflags=creationflags, close_fds=True)
            _tally_launched_at = time.time()
            return True, f"Started TallyPrime from {exe_path}"
        except Exception as e:
            return False, f"Failed to start TallyPrime: {e}"


def standard_ini_paths(hint: str = "") -> List[str]:
    """Where tally.ini may be: the path Tally itself reported earlier, the detected installation,
    then the standard install folders."""
    paths: List[str] = []
    if hint:
        paths.append(hint)

    install = find_tally_installation(hint, use_cache=True)
    if install.get("ini_path") and install["ini_path"] not in paths:
        paths.append(install["ini_path"])

    for env in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432", "SystemDrive"):
        base = os.environ.get(env)
        if not base:
            continue
        base = base + "\\" if env == "SystemDrive" and not base.endswith("\\") else base
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


def diagnosis_text(url: str, running: Optional[bool], can_launch: bool = False, starting: bool = False) -> str:
    port = urlparse(url).port or 9000
    if starting or is_tally_starting():
        return "TallyPrime was recently started and is warming up. Waiting for its XML/ODBC server to answer..."
    if running is False:
        if can_launch:
            return "TallyPrime isn't running on this PC. You can start TallyPrime directly from here."
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


def match_open_company(open_cmps: List[Dict[str, Any]], host_info: Dict[str, Any]) -> Dict[str, Any]:
    """Finds the open company matching host_info by GUID or name, falling back to the first open company."""
    if not open_cmps:
        return {}
    target_guid = host_info.get("guid") or ""
    if target_guid:
        for c in open_cmps:
            if c.get("guid") == target_guid:
                return c
    target_name = host_info.get("company_name") or ""
    if target_name:
        for c in open_cmps:
            if c.get("name") == target_name:
                return c
    return open_cmps[0]


def auto_detect_tally_server(current_url: str = "", probe: Optional[Callable[[str], Any]] = None) -> Dict[str, Any]:
    """Scans for an active TallyPrime XML server on this computer, identifying port and open company details."""
    install_info = find_tally_installation(use_cache=True)
    exe_path = install_info.get("exe_path") or ""
    ini_path = install_info.get("ini_path") or ""
    is_running = install_info.get("is_running")

    # Gather candidate ports
    active_listening = find_tally_listening_ports()
    ini_ports = []
    if ini_path and os.path.isfile(ini_path):
        try:
            with open(ini_path, "r", encoding="utf-8", errors="ignore") as f:
                p = read_server_port(f.read())
                if p:
                    ini_ports.append(p)
        except Exception:
            pass

    parsed = urlparse(current_url or "")
    current_port = parsed.port if parsed.port else 0

    candidates: List[int] = []
    for p in active_listening + ini_ports + ([current_port] if current_port else []) + list(COMMON_PORTS):
        if 1 <= p <= 65535 and p not in candidates:
            candidates.append(p)

    for port in candidates:
        url = f"http://127.0.0.1:{port}"
        try:
            if probe is not None:
                res = probe(url)
                if res:
                    # Ignore probe results that explicitly say connected: False
                    if isinstance(res, dict) and (res.get("connected") is False or ("connected" in res and not res["connected"])):
                        continue
                    company_name = ""
                    company_id = ""
                    guid = ""
                    if isinstance(res, list) and len(res) > 0 and isinstance(res[0], dict):
                        company_name = res[0].get("name", "")
                        company_id = res[0].get("company_id") or res[0].get("company_number") or res[0].get("number") or ""
                        guid = res[0].get("guid", "")
                    elif isinstance(res, dict):
                        company_name = res.get("company_name") or ""
                        company_id = res.get("company_id") or res.get("company_number") or ""
                        guid = res.get("guid") or ""
                    return {
                        "connected": True,
                        "url": url,
                        "port": port,
                        "company_name": company_name,
                        "company_id": company_id,
                        "guid": guid,
                        "is_running": True,
                        "exe_path": exe_path,
                    }
            else:
                from tally_client import TallyClient
                client = TallyClient(tally_url=url, timeout=1.5)
                info = client.discover_tally_host()
                if info.get("connected"):
                    open_cmps = client.get_open_companies()
                    first = match_open_company(open_cmps, info)
                    cmp_name = first.get("name") or info.get("company_name") or ""
                    cmp_id = first.get("company_id") or first.get("company_number") or info.get("company_id") or ""
                    guid = first.get("guid") or info.get("guid") or ""
                    return {
                        "connected": True,
                        "url": url,
                        "port": port,
                        "company_name": cmp_name,
                        "company_id": cmp_id,
                        "guid": guid,
                        "is_running": True,
                        "exe_path": exe_path,
                    }
        except Exception:
            continue

    return {
        "connected": False,
        "url": current_url or "http://127.0.0.1:9000",
        "port": current_port or 9000,
        "company_name": "",
        "company_id": "",
        "guid": "",
        "is_running": is_running,
        "exe_path": exe_path,
        "can_launch": bool(exe_path and is_running is False),
    }
