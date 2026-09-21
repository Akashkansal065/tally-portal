import urllib.request
import urllib.error
import urllib.parse
import json
import logging
import time
import socket
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("CloudClient")

class CloudClient:
    def __init__(
        self,
        backend_url: str = "http://127.0.0.1:8000",
        token: str = "",
        timeout: int = 10,
        email: str = "",
        password: str = "",
        on_token_refreshed: Optional[Any] = None
    ):
        self.backend_url = backend_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.email = email
        self.password = password
        self.on_token_refreshed = on_token_refreshed

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def authenticate(self, username_or_email: str, password: str) -> Tuple[bool, str]:
        """Logs into MyTally backend using email or username and obtains JWT token."""
        for endpoint in ["/auth/login", "/api/v1/auth/login"]:
            url = f"{self.backend_url}{endpoint}"
            try:
                payload = json.dumps({"email": username_or_email, "password": password}).encode("utf-8")
                req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    token = data.get("access_token") or data.get("token")
                    if token:
                        self.token = token
                        self.email = username_or_email
                        self.password = password
                        return True, self.token
            except urllib.error.HTTPError as e:
                try:
                    err_json = json.loads(e.read().decode("utf-8", errors="ignore"))
                    detail = err_json.get("detail", f"HTTP {e.code}")
                except Exception:
                    detail = f"HTTP {e.code}"
                return False, detail
            except Exception as e:
                logger.debug(f"Auth attempt on {endpoint} failed: {e}")
        return False, "Incorrect email/username or password"

    def reauthenticate(self) -> bool:
        """Attempts to obtain a fresh access token if credentials are saved."""
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
                    if self.reauthenticate():
                        try:
                            req_retry = urllib.request.Request(url, headers=self._get_headers())
                            with urllib.request.urlopen(req_retry, timeout=self.timeout) as resp:
                                items = json.loads(resp.read().decode("utf-8"))
                                if isinstance(items, list):
                                    return items, None
                        except Exception as retry_ex:
                            logger.error(f"Retry after reauth failed: {retry_ex}")
                    last_error = f"Authentication Required (HTTP 401). Please check email/password in config."
                    break  # Do not fallback to /api/v1 when auth fails
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
                if e.code == 401 and self.reauthenticate():
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

    def push_inbound_xml(self, xml_data: str, company_name: Optional[str] = None) -> Tuple[bool, Dict[str, Any]]:
        """Uploads exported Tally XML to MyTally backend to update the database with comprehensive diagnostics."""
        headers = {
            "Content-Type": "text/xml;charset=utf-8"
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if company_name:
            headers["x-company-name"] = company_name

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
            if company_name:
                url += f"?company_name={urllib.parse.quote(company_name)}"
            
            start_t = time.time()
            try:
                req = urllib.request.Request(url, data=payload_bytes, headers=headers)
                with urllib.request.urlopen(req, timeout=300) as resp:
                    dur = time.time() - start_t
                    raw_body = resp.read().decode("utf-8", errors="replace")
                    try:
                        res_json = json.loads(raw_body)
                        res_json["duration_seconds"] = dur
                        is_success = (res_json.get("status") == "success" or res_json.get("imported_vouchers", 0) >= 0)
                        return is_success, res_json
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
                    if self.reauthenticate():
                        headers["Authorization"] = f"Bearer {self.token}"
                        retry_start = time.time()
                        try:
                            req_retry = urllib.request.Request(url, data=payload_bytes, headers=headers)
                            with urllib.request.urlopen(req_retry, timeout=300) as retry_resp:
                                retry_dur = time.time() - retry_start
                                raw_retry = retry_resp.read().decode("utf-8", errors="replace")
                                res_json = json.loads(raw_retry)
                                res_json["duration_seconds"] = retry_dur
                                is_success = (res_json.get("status") == "success" or res_json.get("imported_vouchers", 0) >= 0)
                                logger.info(f"✅ Inbound push retry succeeded after token refresh!")
                                return is_success, res_json
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
                    "status_code": e.code,
                    "duration_seconds": dur,
                    "endpoint": endpoint,
                    "payload_size_kb": payload_size_kb
                }
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

    def get_last_alter_id(self) -> Tuple[int, int]:
        """Fetches the latest alter IDs from the cloud backend (max_alter_id across ledgers, vouchers, items)."""
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
                    return max(max_alt, led_alt, vch_alt, stk_alt), vch_alt
            except urllib.error.HTTPError as e:
                if e.code == 401 and self.reauthenticate():
                    try:
                        req_retry = urllib.request.Request(url, headers=self._get_headers())
                        with urllib.request.urlopen(req_retry, timeout=self.timeout) as resp:
                            data = json.loads(resp.read().decode("utf-8"))
                            max_alt = int(data.get("last_alter_id", 0))
                            led_alt = int(data.get("last_ledger_alter_id", 0))
                            vch_alt = int(data.get("last_voucher_alter_id", 0))
                            stk_alt = int(data.get("last_stock_item_alter_id", 0))
                            return max(max_alt, led_alt, vch_alt, stk_alt), vch_alt
                    except Exception:
                        pass
                if e.code != 404:
                    break
            except Exception as e:
                logger.debug(f"Failed to fetch last alter id from {endpoint}: {e}")
        return 0, 0
