import urllib.request
import urllib.error
import urllib.parse
import hashlib
import json
import logging
import platform
import time
import socket
from typing import Callable, Dict, Any, List, Optional, Tuple

logger = logging.getLogger("CloudClient")

AGENT_VERSION = "1.1.0"

# Reasons (X-Auth-Reason) after which the agent may log in again by itself with the saved password.
# "replaced" means a newer login from this same PC (e.g. the GUI's Test Connection), so logging in
# again is safe. Anything else (signed out by an admin, device blocked, password changed, account
# deactivated, device limit) means a person decided this PC should stop, so the agent halts until
# someone re-enters the password in Settings.
AUTO_RELOGIN_REASONS = {None, "", "expired", "invalid", "replaced"}

HALT_MESSAGES = {
    "admin_revoke": "Signed out by an administrator. Re-enter the password in Settings to resume.",
    "admin_revoke_all": "Signed out by an administrator. Re-enter the password in Settings to resume.",
    "blocked": "This PC was blocked by an administrator.",
    "device_blocked": "This PC was blocked by an administrator.",
    "password_change": "The account password was changed. Enter the new password in Settings.",
    "deactivated": "The sync account was deactivated. Contact your administrator.",
    "device_limit": "Signed out because the account signed in on another device. Re-enter the password in Settings.",
    "self_revoke": "Signed out from another device. Re-enter the password in Settings to resume.",
    "logout": "Signed out. Re-enter the password in Settings to resume.",
    "device_signed_out": "This PC is signed out of the sync agent. Sign in again in Setup.",
}
DEVICE_TOKEN_PREFIX = "mta_"
# X-Sync-Reason on an HTTP 409: the server is still importing this company's previous push
SYNC_BUSY_REASON = "sync_in_progress"


def halt_message(reason: Optional[str]) -> str:
    return HALT_MESSAGES.get(reason or "", "Signed out by the server. Re-enter the password in Settings to resume.")


def _auth_reason(error: urllib.error.HTTPError) -> Optional[str]:
    try:
        return error.headers.get("X-Auth-Reason") if error.headers else None
    except Exception:
        return None


def device_identity_headers() -> Dict[str, str]:
    """Identifies this PC to the backend so admins can see, sign out and block it."""
    try:
        from security import _get_machine_identifier
        device_id = "agent-" + hashlib.sha256(_get_machine_identifier()).hexdigest()[:32]
    except Exception:
        device_id = "agent-" + hashlib.sha256(platform.node().encode("utf-8")).hexdigest()[:32]
    host = (platform.node() or "Windows PC").split(".")[0][:100]
    return {
        "User-Agent": f"SnehDistSyncAgent/{AGENT_VERSION} ({platform.system()} {platform.release()})",
        "X-Device-Id": device_id,
        "X-Client-Type": "sync-agent",
        "X-Device-Type": "desktop",
        "X-Device-Name": host,
        "X-App-Version": AGENT_VERSION,
    }

def _inbound_result(res_json: Dict[str, Any], status_code: int, endpoint: str) -> Tuple[bool, Dict[str, Any]]:
    """Only an explicit success counts: the server answers HTTP 200 {"status": "error"} for refused imports."""
    is_success = res_json.get("status") == "success"
    if not is_success:
        res_json.setdefault("error_type", "IMPORT_REJECTED")
        res_json.setdefault("error", res_json.get("message") or "Server reported an unsuccessful import")
        res_json.setdefault("status_code", status_code)
        res_json.setdefault("endpoint", endpoint)
    return is_success, res_json


class CloudClient:
    def __init__(
        self,
        backend_url: str = "http://127.0.0.1:8000",
        token: str = "",
        timeout: int = 10,
        email: str = "",
        password: str = "",
        on_token_refreshed: Optional[Any] = None,
        auth_halt_reason: str = "",
        on_auth_halted: Optional[Callable[[str], None]] = None
    ):
        self.backend_url = backend_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.email = email
        self.password = password
        self.on_token_refreshed = on_token_refreshed
        # Non-empty while the server has told this agent to stop (see AUTO_RELOGIN_REASONS)
        self.auth_halt_reason = auth_halt_reason or ""
        self.on_auth_halted = on_auth_halted
        self.identity_headers = device_identity_headers()
        # GUID of the Tally company this agent is tied to. Sent on every sync call so the server works on
        # that company, whichever company the account has active in the app.
        self.company_guid = ""
        # Which copy of that company's books is open in Tally (TallyClient.get_open_companies); '' when not known
        self.company_fingerprint = ""

    def _halt(self, reason: str) -> None:
        if self.auth_halt_reason == reason:
            return
        self.auth_halt_reason = reason
        logger.error(f"⛔ Sync paused: {halt_message(reason)} (reason: {reason})")
        if self.on_auth_halted:
            try:
                self.on_auth_halted(reason)
            except Exception as ex:
                logger.debug(f"Error calling on_auth_halted: {ex}")

    @property
    def device_mode(self) -> bool:
        """Signed in as this PC (a device token), not with a person's login."""
        return bool(self.token) and self.token.startswith(DEVICE_TOKEN_PREFIX)

    @property
    def machine_id(self) -> str:
        return self.identity_headers.get("X-Device-Id", "")

    def _device(self) -> Dict[str, str]:
        return {"machine_id": self.machine_id, "device_name": self.identity_headers.get("X-Device-Name", "")}

    def _call(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Tuple[int, Any, Dict[str, str]]:
        """One JSON call to the backend. Returns (HTTP status, decoded body or message, response headers);
        status 0 means the server was not reached."""
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(f"{self.backend_url}{path}", data=data, headers=self._get_headers(), method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8") or "null"), dict(resp.headers or {})
        except urllib.error.HTTPError as e:
            try:
                body = json.loads(e.read().decode("utf-8", errors="ignore"))
                detail = body.get("detail") if isinstance(body, dict) else body
                if isinstance(detail, list):   # request validation errors
                    detail = "; ".join(str(item.get("msg", item)) for item in detail)
            except Exception:
                detail = f"HTTP {e.code}"
            return e.code, detail or f"HTTP {e.code}", dict(e.headers or {})
        except Exception as e:
            return 0, f"Cannot reach {self.backend_url} ({e})", {}

    # ── Signing this PC in ──
    def start_code_sign_in(self) -> Tuple[bool, Any]:
        """Ask for a code to sign this PC in with. Returns (ok, {"code", "poll_token", "expires_in_minutes"} or
        why not). Nothing is signed in until someone enters the code in the MyTally app."""
        status, body, _ = self._call("POST", "/agent/pair/start", self._device())
        if status == 404:
            return False, "This server does not offer sign-in with a code yet. Sign in with email and password."
        return status == 200, body

    def collect_code_sign_in(self, poll_token: str) -> Tuple[str, Any]:
        """Whether the code has been entered in the app yet: ("pending", None), ("approved", who this PC is now
        signed in as) or ("error", why)."""
        status, body, _ = self._call("POST", "/agent/pair/claim", {"poll_token": poll_token, **self._device()})
        if status == 200 and isinstance(body, dict) and body.get("status") == "approved":
            self.token, self.auth_halt_reason = body["device_token"], ""
            return "approved", body
        if status == 200:
            return "pending", None
        if status in (0, 429) or status >= 500:
            return "pending", None   # a dropped connection or a busy server: ask again
        return "error", str(body)

    def sign_in_device(self, email: str, password: str) -> Tuple[bool, Any, int]:
        """Sign this PC in to an existing account. Returns (ok, body or message, HTTP status); a 404 means the
        server is older than device sign-in."""
        status, body, _ = self._call("POST", "/agent/signin", {"email": email, "password": password, **self._device()})
        if status == 200:
            self.token, self.auth_halt_reason = body["device_token"], ""
        return status == 200, body, status

    # ── Companies synced from this PC ──
    def list_companies(self) -> Tuple[bool, Any]:
        status, body, _ = self._call("GET", "/agent/companies")
        return status == 200, body

    def link_company(self, company: Dict[str, Any], take_over: bool = False) -> Tuple[bool, Any, str]:
        """Make this PC the one that syncs a Tally company. Returns (ok, body or message, reason); reason is
        "linked_to_another_device" when another PC syncs it and take_over was not asked for."""
        status, body, headers = self._call("POST", "/agent/companies/link", {**company, "take_over": take_over})
        return status == 200, body, headers.get("X-Sync-Reason") or headers.get("x-sync-reason") or ""

    def report_state(self, reports: List[Dict[str, Any]]) -> bool:
        """Tell the cloud how each linked company stands after a cycle. A server from before this exists
        answers 404, which is fine."""
        status, _, _ = self._call("POST", "/sync/state", reports)
        return status == 200

    def unlink_company(self, tally_guid: str) -> bool:
        status, _, _ = self._call("POST", "/agent/companies/unlink", {"tally_guid": tally_guid})
        return status == 200

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            **self.identity_headers,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if self.company_guid:
            headers["X-Tally-Company-GUID"] = self.company_guid
        if self.company_guid and getattr(self, "company_fingerprint", ""):
            headers["X-Tally-Company-Fingerprint"] = self.company_fingerprint
        return headers

    def authenticate(self, username_or_email: str, password: str) -> Tuple[bool, str]:
        """Logs into MyTally backend using email or username and obtains JWT token."""
        for endpoint in ["/auth/login", "/api/v1/auth/login"]:
            url = f"{self.backend_url}{endpoint}"
            try:
                payload = json.dumps({"email": username_or_email, "password": password}).encode("utf-8")
                req = urllib.request.Request(url, data=payload, headers={**self.identity_headers, "Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    token = data.get("access_token") or data.get("token")
                    if token:
                        self.token = token
                        self.email = username_or_email
                        self.password = password
                        self.auth_halt_reason = ""
                        return True, self.token
            except urllib.error.HTTPError as e:
                try:
                    err_json = json.loads(e.read().decode("utf-8", errors="ignore"))
                    detail = err_json.get("detail", f"HTTP {e.code}")
                except Exception:
                    detail = f"HTTP {e.code}"
                reason = _auth_reason(e)
                if e.code == 403 and reason in ("device_blocked", "device_limit"):
                    self._halt(reason)
                return False, detail
            except Exception as e:
                logger.debug(f"Auth attempt on {endpoint} failed: {e}")
        return False, "Incorrect email/username or password"

    def reauthenticate(self, reason: Optional[str] = None) -> bool:
        """Attempts to obtain a fresh access token if credentials are saved, unless the server ended
        the session on purpose (see AUTO_RELOGIN_REASONS) or the agent is already halted."""
        if self.auth_halt_reason:
            return False
        if self.device_mode:
            # A PC's sign-in is not renewed with a password: someone signs the PC in again
            self._halt(reason if reason in HALT_MESSAGES else "device_signed_out")
            return False
        if reason not in AUTO_RELOGIN_REASONS:
            self._halt(reason)
            return False
        if not self.email or not self.password:
            return False
        logger.info(f"🔄 Access token expired. Auto-reauthenticating as '{self.email}'...")
        ok, res = self.authenticate(self.email, self.password)
        if ok:
            logger.info("🔑 Auto-reauthenticated successfully with fresh token.")
            if self.on_token_refreshed:
                try:
                    self.on_token_refreshed(self.token)
                except Exception as ex:
                    logger.debug(f"Error calling on_token_refreshed: {ex}")
            return True
        else:
            logger.error(f"❌ Auto-reauthentication failed: {res}")
            return False

    def check_health(self) -> Tuple[bool, str]:
        """Checks if the cloud backend is reachable."""
        for endpoint in ["/health", "/", "/api/v1/health"]:
            url = f"{self.backend_url}{endpoint}"
            try:
                req = urllib.request.Request(url, headers={"Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    if resp.status in (200, 201, 301, 302):
                        return True, f"Connected ({resp.status})"
            except urllib.error.HTTPError as e:
                # If HTTP error code is returned, server is reachable
                return True, f"Reachable (HTTP {e.code})"
            except Exception as e:
                pass
        return False, f"Unreachable at {self.backend_url}"

    def fetch_outbound_queue(self) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Fetches pending tasks from MyTally backend with explicit error reporting."""
        last_error = None
        for endpoint in ["/sync/outbound-queue", "/api/v1/sync/outbound-queue"]:
            url = f"{self.backend_url}{endpoint}"
            try:
                req = urllib.request.Request(url, headers=self._get_headers())
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    items = json.loads(resp.read().decode("utf-8"))
                    if isinstance(items, list):
                        return items, None
            except urllib.error.HTTPError as e:
                if e.code == 401:
                    logger.warning("⚠️ Received HTTP 401 on outbound-queue. Attempting auto-reauth...")
                    if self.reauthenticate(_auth_reason(e)):
                        try:
                            req_retry = urllib.request.Request(url, headers=self._get_headers())
                            with urllib.request.urlopen(req_retry, timeout=self.timeout) as resp:
                                items = json.loads(resp.read().decode("utf-8"))
                                if isinstance(items, list):
                                    return items, None
                        except Exception as retry_ex:
                            logger.error(f"Retry after reauth failed: {retry_ex}")
                    last_error = halt_message(self.auth_halt_reason) if self.auth_halt_reason else "Authentication Required (HTTP 401). Please check email/password in config."
                    break  # Do not fallback to /api/v1 when auth fails
                elif e.code in (403, 409, 426):
                    # The server has no company linked to this agent's Tally company (yet), or this PC is not
                    # the one syncing it
                    try:
                        last_error = json.loads(e.read().decode("utf-8", errors="ignore")).get("detail") or "HTTP 409"
                    except Exception:
                        last_error = f"HTTP {e.code}: the server could not match this Tally company"
                else:
                    last_error = f"HTTP {e.code} on {endpoint}: {e.reason}"
                if e.code != 404:
                    break
            except urllib.error.URLError as e:
                last_error = f"Cannot connect to {self.backend_url} ({e.reason})"
            except Exception as e:
                last_error = str(e)
        return [], last_error

    def acknowledge_queue(self, sync_ids: List[int]) -> bool:
        """Notifies MyTally that outbound tasks were successfully written to Tally."""
        if not sync_ids:
            return True

        for endpoint in ["/sync/acknowledge", "/api/v1/sync/acknowledge"]:
            url = f"{self.backend_url}{endpoint}"
            try:
                payload = json.dumps(sync_ids).encode("utf-8")
                req = urllib.request.Request(url, data=payload, headers=self._get_headers())
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return resp.status == 200
            except urllib.error.HTTPError as e:
                if e.code == 401 and self.reauthenticate(_auth_reason(e)):
                    try:
                        req_retry = urllib.request.Request(url, data=payload, headers=self._get_headers())
                        with urllib.request.urlopen(req_retry, timeout=self.timeout) as resp:
                            return resp.status == 200
                    except Exception:
                        pass
                if e.code != 404:
                    break
            except Exception as e:
                logger.debug(f"Acknowledge on {endpoint} failed: {e}")
        return False

    def report_voucher_identities(self, identities: List[Dict[str, Any]]) -> bool:
        """
        Tells MyTally what Tally made of the vouchers just pushed: the number Tally gave each one, its master id,
        GUID and date. Without this the app keeps its provisional number and cannot address the voucher later.
        """
        if not identities:
            return True
        url = f"{self.backend_url}/sync/voucher-identities"
        payload = json.dumps(identities).encode("utf-8")
        for attempt in range(2):
            try:
                req = urllib.request.Request(url, data=payload, headers=self._get_headers())
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return resp.status == 200
            except urllib.error.HTTPError as e:
                if attempt == 0 and e.code == 401 and self.reauthenticate(_auth_reason(e)):
                    continue
                logger.warning(f"Reporting voucher numbers to MyTally failed: HTTP {e.code}")
                return False
            except Exception as e:
                logger.warning(f"Reporting voucher numbers to MyTally failed: {e}")
                return False
        return False

    def push_inbound_xml(self, xml_data: str, company_name: Optional[str] = None, force: bool = False) -> Tuple[bool, Dict[str, Any]]:
        """Uploads exported Tally XML to MyTally backend to update the database with comprehensive diagnostics."""
        headers = {
            **self.identity_headers,
            "Content-Type": "text/xml;charset=utf-8"
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if company_name:
            headers["x-company-name"] = company_name
        if self.company_guid:
            headers["X-Tally-Company-GUID"] = self.company_guid
        if self.company_guid and getattr(self, "company_fingerprint", ""):
            headers["X-Tally-Company-Fingerprint"] = self.company_fingerprint
        if force:
            headers["x-force-sync"] = "true"

        payload_bytes = xml_data.encode("utf-8")
        payload_size_kb = len(payload_bytes) / 1024.0

        last_diag = {
            "error_type": "UNKNOWN",
            "error": "Failed to post inbound XML to cloud backend",
            "status_code": None,
            "duration_seconds": 0.0,
            "endpoint": "",
            "payload_size_kb": payload_size_kb
        }

        for endpoint in ["/sync/inbound", "/api/v1/sync/inbound"]:
            url = f"{self.backend_url}{endpoint}"
            params = []
            if company_name:
                params.append(f"company_name={urllib.parse.quote(company_name)}")
            if force:
                params.append("force=true")
            if params:
                url += "?" + "&".join(params)
            
            start_t = time.time()
            try:
                req = urllib.request.Request(url, data=payload_bytes, headers=headers)
                with urllib.request.urlopen(req, timeout=300) as resp:
                    dur = time.time() - start_t
                    raw_body = resp.read().decode("utf-8", errors="replace")
                    try:
                        res_json = json.loads(raw_body)
                        res_json["duration_seconds"] = dur
                        return _inbound_result(res_json, resp.status, endpoint)
                    except json.JSONDecodeError:
                        last_diag = {
                            "error_type": "INVALID_JSON_RESPONSE",
                            "error": f"Server returned non-JSON response (HTTP {resp.status}): {raw_body[:200]}",
                            "status_code": resp.status,
                            "duration_seconds": dur,
                            "endpoint": endpoint,
                            "payload_size_kb": payload_size_kb
                        }
                        logger.error(f"Inbound push on {endpoint}: {last_diag['error']}")

            except urllib.error.HTTPError as e:
                dur = time.time() - start_t

                # Handle 401 token expiration with auto-reauthentication
                if e.code == 401:
                    logger.warning(f"⚠️ Inbound push returned HTTP 401 (token expired). Auto-reauthenticating...")
                    if self.reauthenticate(_auth_reason(e)):
                        headers["Authorization"] = f"Bearer {self.token}"
                        retry_start = time.time()
                        try:
                            req_retry = urllib.request.Request(url, data=payload_bytes, headers=headers)
                            with urllib.request.urlopen(req_retry, timeout=300) as retry_resp:
                                retry_dur = time.time() - retry_start
                                raw_retry = retry_resp.read().decode("utf-8", errors="replace")
                                res_json = json.loads(raw_retry)
                                res_json["duration_seconds"] = retry_dur
                                logger.info(f"✅ Inbound push retry completed after token refresh.")
                                return _inbound_result(res_json, retry_resp.status, endpoint)
                        except Exception as retry_ex:
                            logger.error(f"Inbound push retry failed after re-auth: {retry_ex}")

                try:
                    err_body = e.read().decode("utf-8", errors="ignore")
                    try:
                        err_json = json.loads(err_body)
                        detail = err_json.get("detail") or err_json.get("message") or err_body[:300]
                    except Exception:
                        detail = err_body[:300] if err_body else e.reason
                except Exception:
                    detail = str(e.reason)

                err_type = "HTTP_ERROR"
                if e.code == 401:
                    err_type = "AUTH_ERROR (HTTP 401)"
                elif e.code == 403:
                    err_type = "PERMISSION_DENIED (HTTP 403)"
                elif e.code == 413:
                    err_type = "PAYLOAD_TOO_LARGE (HTTP 413)"
                elif e.code == 500:
                    err_type = "BACKEND_INTERNAL_ERROR (HTTP 500)"
                elif e.code in (502, 503, 504):
                    err_type = f"GATEWAY_OR_TUNNEL_ERROR (HTTP {e.code})"

                last_diag = {
                    "error_type": err_type,
                    "error": f"HTTP {e.code}: {detail}",
                    "reason": (e.headers.get("X-Sync-Reason") if e.headers else None),
                    "status_code": e.code,
                    "duration_seconds": dur,
                    "endpoint": endpoint,
                    "payload_size_kb": payload_size_kb
                }
                if last_diag["reason"] != SYNC_BUSY_REASON:   # busy is reported by the caller, and is not an error
                    logger.error(f"❌ Inbound push on {endpoint} returned {err_type}: {last_diag['error']} (took {dur:.1f}s)")

                # If the endpoint exists and gave an error (not a 404), do not try fallback endpoint
                if e.code != 404:
                    break

            except (socket.timeout, TimeoutError):
                dur = time.time() - start_t
                last_diag = {
                    "error_type": "TIMEOUT",
                    "error": f"Network / Server timed out after {dur:.1f} seconds waiting for cloud backend response.",
                    "status_code": 408,
                    "duration_seconds": dur,
                    "endpoint": endpoint,
                    "payload_size_kb": payload_size_kb
                }
                logger.error(f"⏱️ Inbound push on {endpoint} timed out after {dur:.1f}s (Payload: {payload_size_kb:.1f} KB)")
                break

            except urllib.error.URLError as e:
                dur = time.time() - start_t
                reason_str = str(e.reason)
                if "timed out" in reason_str.lower():
                    err_type = "TIMEOUT"
                    err_msg = f"Connection timed out after {dur:.1f}s ({reason_str})"
                elif "connection refused" in reason_str.lower():
                    err_type = "CONNECTION_REFUSED"
                    err_msg = f"Cloud backend is unreachable / connection refused ({self.backend_url})"
                else:
                    err_type = "NETWORK_ERROR"
                    err_msg = f"URL error: {reason_str}"

                last_diag = {
                    "error_type": err_type,
                    "error": err_msg,
                    "status_code": None,
                    "duration_seconds": dur,
                    "endpoint": endpoint,
                    "payload_size_kb": payload_size_kb
                }
                logger.error(f"🌐 Inbound push on {endpoint} failed with {err_type}: {err_msg}")
                break

            except Exception as e:
                dur = time.time() - start_t
                last_diag = {
                    "error_type": "EXCEPTION",
                    "error": f"{type(e).__name__}: {str(e)}",
                    "status_code": None,
                    "duration_seconds": dur,
                    "endpoint": endpoint,
                    "payload_size_kb": payload_size_kb
                }
                logger.error(f"⚠️ Inbound push on {endpoint} encountered unexpected exception: {e}")
                break

        return False, last_diag

    def get_server_counts(self) -> Optional[Dict[str, int]]:
        """How many vouchers, ledgers and stock items the server holds for the company being synced.
        None when it could not be asked, or the server is too old to say."""
        try:
            req = urllib.request.Request(f"{self.backend_url}/sync/last-alter-id", headers=self._get_headers())
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                counts = json.loads(resp.read().decode("utf-8")).get("counts")
                return {k: int(v) for k, v in counts.items()} if isinstance(counts, dict) else None
        except Exception as e:
            logger.debug(f"Could not read the server's record counts: {e}")
            return None

    def get_last_alter_id(self) -> Tuple[int, int]:
        """
        The highest alter ids the backend holds: (masters, vouchers). Tally counts changes to masters and to
        vouchers separately, so the two are separate watermarks.
        """
        for endpoint in ["/sync/last-alter-id", "/api/v1/sync/last-alter-id"]:
            url = f"{self.backend_url}{endpoint}"
            try:
                req = urllib.request.Request(url, headers=self._get_headers())
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    max_alt = int(data.get("last_alter_id", 0))
                    led_alt = int(data.get("last_ledger_alter_id", 0))
                    vch_alt = int(data.get("last_voucher_alter_id", 0))
                    stk_alt = int(data.get("last_stock_item_alter_id", 0))
                    return (int(data["last_master_alter_id"]) if "last_master_alter_id" in data else max(max_alt, led_alt, stk_alt)), vch_alt
            except urllib.error.HTTPError as e:
                if e.code == 401 and self.reauthenticate(_auth_reason(e)):
                    try:
                        req_retry = urllib.request.Request(url, headers=self._get_headers())
                        with urllib.request.urlopen(req_retry, timeout=self.timeout) as resp:
                            data = json.loads(resp.read().decode("utf-8"))
                            max_alt = int(data.get("last_alter_id", 0))
                            led_alt = int(data.get("last_ledger_alter_id", 0))
                            vch_alt = int(data.get("last_voucher_alter_id", 0))
                            stk_alt = int(data.get("last_stock_item_alter_id", 0))
                            return (int(data["last_master_alter_id"]) if "last_master_alter_id" in data else max(max_alt, led_alt, stk_alt)), vch_alt
                    except Exception:
                        pass
                if e.code != 404:
                    break
            except Exception as e:
                logger.debug(f"Failed to fetch last alter id from {endpoint}: {e}")
        return 0, 0
