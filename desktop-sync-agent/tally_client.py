import os
import re
import sys
import time
import threading
from contextlib import contextmanager
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
import logging
from html import unescape
from typing import Dict, Any, Optional, Tuple, List, Callable

from config import get_logs_dir

logger = logging.getLogger("TallyClient")

# Global lock to serialize requests to Tally Prime's single-threaded HTTP XML server
_TALLY_LOCK = threading.Lock()

# send_xml's reason when no answer came back from Tally (timeout, refused or dropped connection), as opposed to
# an answer that rejected the request
NETWORK_ERROR_PREFIX = "HTTP/Network Error"

_INVALID_XML_10_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x84\x86-\x9f]")
_COUNT = re.compile(r"<(CREATED|ALTERED|DELETED|CANCELLED|IGNORED|ERRORS|EXCEPTIONS)>\s*(\d+)\s*</\1>")

def decode_tally_reply(body: bytes) -> str:
    """Tally replies in UTF-8 or, with a byte order mark, UTF-16; same rule as the backend's sync upload."""
    if body.startswith(b"\xff\xfe") or body.startswith(b"\xfe\xff"):
        return body.decode("utf-16", errors="replace")
    return body.decode("utf-8", errors="replace")


def escape_xml(text: Any) -> str:
    """Safely escapes XML special characters and strips invalid control characters."""
    if text is None:
        return ""
    s = _INVALID_XML_10_CHARS.sub("", str(text))
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
         .replace("'", "&apos;")
    )

def parse_import_result(resp: str) -> Tuple[bool, str]:
    """True only when Tally reports no errors or exceptions and accepted at least one object."""
    if not resp or not resp.strip():
        return False, "Empty response (is a company open in Tally?)"
    if resp.lstrip().startswith("<EXCEPTION>"):
        return False, "Tally exception: " + re.sub(r"<[^>]+>", " ", resp).strip()[:300]
    line_errors = [e.strip() for e in re.findall(r"<LINEERROR>(.*?)</LINEERROR>", resp, re.S)]
    if line_errors:
        return False, " | ".join(line_errors)[:500]
    counts: Dict[str, int] = {}
    for key, value in _COUNT.findall(resp):
        counts[key] = counts.get(key, 0) + int(value)
    if counts.get("ERRORS") or counts.get("EXCEPTIONS"):
        return False, f"Tally reported {counts.get('ERRORS', 0)} error(s), {counts.get('EXCEPTIONS', 0)} exception(s)"
    # IGNORED is kept as accepted: it's what a resend of an already-saved object can return
    accepted = sum(counts.get(k, 0) for k in ("CREATED", "ALTERED", "DELETED", "CANCELLED", "IGNORED"))
    return (accepted > 0, "OK" if accepted else f"Tally changed nothing ({counts or 'no counts'})")

# What a voucher export fetches. Shared by the whole-company export and the date-range one.
VOUCHER_FETCH = ("GUID,MASTERID,REMOTEALTGUID,ALTERID,VOUCHERTYPENAME,VOUCHERNUMBER,DATE,NARRATION,PARTYLEDGERNAME,AMOUNT,"
                 "ISCANCELLED,ISOPTIONAL,ISPOSTDATED,ISINVOICE,PERSISTEDVIEW,EFFECTIVEDATE,REFERENCE,REFERENCEDATE,"
                 "PLACEOFSUPPLY,BASICBUYERNAME,BASICBUYERADDRESS.LIST,CONSIGNEEMAILINGNAME,CONSIGNEEADDRESS.LIST,"
                 "BASICORDERREF,BASICSHIPDELIVERYNOTE,IRN,IRNACKNO,IRNACKDATE,IRNQRCODE,IRNCANCELLED,IRNCANCELDATE,"
                 "IRNCANCELREASON,IRNIRPSOURCE,EWAYBILLDETAILS.LIST,ALLLEDGERENTRIES.LIST,INVENTORYENTRIES.LIST,ALLINVENTORYENTRIES.LIST,"
                 "INVENTORYENTRIESIN.LIST,INVENTORYENTRIESOUT.LIST,ATTENDANCEENTRIES.*,CATEGORYENTRY.LIST")

# What a ledger export fetches (see docs/Export Field Coverage Matrix.md)
LEDGER_FETCH = ("NAME,GUID,MASTERID,PARENT,ALTERID,PAYTYPE,PAYSLIPNAME,CALCULATIONTYPE,OPENINGBALANCE,CLOSINGBALANCE,ADDRESS.LIST,STATENAME,PINCODE,LEDGERPHONE,INCOMETAXNUMBER,PARTYGSTIN,ISBILLWISEON,LEDGSTREGDETAILS.LIST,LEDMAILINGDETAILS.LIST,"
                "CREDITLIMIT,BILLCREDITPERIOD,LEDGERCONTACT,LEDGERMOBILE,EMAIL,EMAILCC,WEBSITE,LEDGERFAX,COUNTRYNAME,"
                "TAXCLASSIFICATIONNAME,MSMEREGISTRATIONDETAILS.LIST,LOWERDEDUCTION.LIST,HSNDETAILS.LIST,LEDMULTIADDRESSLIST.LIST,"
                "MAILINGNAME.LIST,LANGUAGENAME.LIST")

# What a stock item export fetches. Only tags the importer reads and stores (see docs/Export Field Coverage Matrix.md);
# the MRP, BOM, price and reorder lists are not requested until the importer parses them.
STOCK_ITEM_FETCH = ("NAME,GUID,MASTERID,ALTERID,PARENT,CATEGORY,BASEUNITS,ADDITIONALUNITS,CONVERSION,DENOMINATOR,"
                    "OPENINGBALANCE,OPENINGVALUE,OPENINGRATE,DESCRIPTION,NARRATION,ISBATCHWISEON,ISPERISHABLEON,"
                    "IGNORENEGATIVESTOCK,COSTINGMETHOD,VALUATIONMETHOD,GSTTYPEOFSUPPLY,BATCHALLOCATIONS.LIST,"
                    "HSNDETAILS.LIST,INFGSTHSNCODE,INFGSTIGSTRATE,LANGUAGENAME.LIST")

# The currency fields the importer reads and stores
CURRENCY_FETCH = ("NAME,ORIGINALNAME,EXPANDEDNAME,ISOCURRENCYCODE,DECIMALPLACES,INMILLIONS,ISSUFFIX,HASSPACE,"
                  "DECIMALSYMBOL,DECIMALPLACESFORPRINTING,MAILINGNAME.LIST")

# Two ways of asking Tally for the vouchers of a date range. Which one a Tally honours is found by trying:
# "sv" sets the report period; "filter" also filters the collection on the voucher date.
VOUCHER_RANGE_METHODS = ("sv", "filter")

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_VOUCHER_OPEN = re.compile(r"<VOUCHER[\s>]")
# One pass over a voucher: where its lists open and close, and every DATE on the way
_LIST_OR_DATE = re.compile(r"<(/?)[A-Z0-9_.]+\.LIST\b[^>]*?(/?)>|<DATE\b[^>]*>\s*(\d{8})\s*</DATE>")


def _tag(block: str, tag: str) -> str:
    found = re.search(rf"<{tag}\b[^>]*>(.*?)</{tag}>", block, re.S)
    return unescape(found.group(1)).strip() if found else ""


def voucher_keys(resp_xml: str) -> List[Dict[str, str]]:
    """MASTERID, GUID, ALTERID and DATE of every voucher in a keys-only export. Read as text, like voucher_dates."""
    info = resp_xml.find("<CMPINFO>")
    info_end = resp_xml.find("</CMPINFO>", info) if info >= 0 else -1
    starts = [m.start() for m in _VOUCHER_OPEN.finditer(resp_xml) if not (info >= 0 and info < m.start() < info_end)]
    keys = []
    for n, start in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(resp_xml)
        block = resp_xml[start:end]
        vch_type = re.match(r'<VOUCHER\b[^>]*\bVCHTYPE="([^"]*)"', block)
        keys.append({"master_id": _tag(block, "MASTERID"), "guid": _tag(block, "GUID"),
                     "alter_id": _tag(block, "ALTERID"), "date": _tag(block, "DATE"),
                     "voucher_type": unescape(vch_type.group(1)).strip() if vch_type else _tag(block, "VOUCHERTYPENAME")})
    return keys


def master_keys(resp_xml: str, tag: str) -> List[Dict[str, str]]:
    """NAME, GUID and MASTERID of every <tag> object in a keys-only master export. The name is the NAME
    attribute, or a NAME element when Tally wrote it that way."""
    # The CMPINFO block of counts holds <LEDGER>217</LEDGER> and the like; it is not an object
    info = resp_xml.find("<CMPINFO>")
    info_end = resp_xml.find("</CMPINFO>", info) if info >= 0 else -1
    if info >= 0 and info_end >= 0:
        resp_xml = resp_xml[:info] + resp_xml[info_end + len("</CMPINFO>"):]
    keys = []
    for m in re.finditer(rf"<{tag}\b([^>]*)>(.*?)</{tag}>", resp_xml, re.S):
        attrs, block = m.group(1), m.group(2)
        named = re.search(r'\bNAME="([^"]*)"', attrs)
        key = {"name": unescape(named.group(1)) if named else _tag(block, "NAME"),
               "guid": _tag(block, "GUID"), "master_id": _tag(block, "MASTERID")}
        closing = _tag(block, "CLOSINGBALANCE")
        if closing:
            key["closing_balance"] = closing      # Tally's own figure, for the books-parity check
        elif re.search(r"<CLOSINGBALANCE\b", block):
            key["closing_balance"] = "0"          # Tally writes the tag empty for a ledger that nets to nothing
        keys.append(key)
    return keys


def parse_change_counters(resp_xml: Optional[str], company_name: str, company_guid: str = "") -> Optional[Tuple[int, int]]:
    """AltMstId and AltVchId of the one company this reply names, or None when that cannot be said for sure."""
    if not resp_xml:
        return None
    found = []
    for m in re.finditer(r"<COMPANY\b([^>]*)>(.*?)</COMPANY>", resp_xml, re.S):
        attrs, block = m.group(1), m.group(2)
        named = re.search(r'\bNAME="([^"]*)"', attrs)
        name = unescape(named.group(1)).strip() if named else _tag(block, "NAME")
        found.append((name, _tag(block, "GUID"), _tag(block, "ALTMSTID"), _tag(block, "ALTVCHID")))
    if company_guid:
        found = [c for c in found if c[1] == company_guid]
    elif company_name:
        found = [c for c in found if c[0] == company_name]
    if len(found) != 1:
        return None                      # not there, or two that cannot be told apart
    mst, vch = found[0][2], found[0][3]
    if not (mst.isdigit() and vch.isdigit()):
        return None
    return int(mst), int(vch)


def tally_date_text(yyyymmdd: str) -> str:
    """20250401 -> 1-Apr-2025, the form Tally's $$Date reads the same way in every regional setting."""
    return f"{int(yyyymmdd[6:8])}-{_MONTHS[int(yyyymmdd[4:6]) - 1]}-{yyyymmdd[0:4]}"


def voucher_dates(resp_xml: str) -> List[str]:
    """The date (YYYYMMDD) of every voucher in an export, one entry per voucher, '' where none is found.

    Read as text rather than parsed: Tally exports can carry characters an XML parser refuses, and a parser
    would hold a second copy of a large export in memory. Only a DATE that sits directly in the voucher
    counts; one inside an entry list (a cheque date, a bill date) is passed over."""
    dates = []
    # Tally ends an export with a CMPINFO block of counts, one of them written as <VOUCHER>44</VOUCHER>
    info = resp_xml.find("<CMPINFO>")
    info_end = resp_xml.find("</CMPINFO>", info) if info >= 0 else -1
    starts = [m.start() for m in _VOUCHER_OPEN.finditer(resp_xml) if not (info >= 0 and info < m.start() < info_end)]
    for n, start in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(resp_xml)
        depth, own_date = 0, ""
        for token in _LIST_OR_DATE.finditer(resp_xml, start, end):
            closing, self_closing, date = token.groups()
            if date:
                if depth == 0:
                    own_date = date
                    break
            elif closing:
                depth = max(0, depth - 1)
            elif not self_closing:
                depth += 1
        dates.append(own_date)
    return dates


def has_collection_records(resp_xml: str, obj_type: str) -> bool:
    """
    Checks whether a Tally XML response contains at least one actual entity record inside <DATA>.
    Prevents pushing empty XML collections (e.g. <DATA><COLLECTION></COLLECTION></DATA>)
    during incremental sync.
    """
    if not resp_xml or "<ENVELOPE>" not in resp_xml:
        return False
    upper_xml = resp_xml.upper()
    if "<DATA>" not in upper_xml:
        return False
    data_content = upper_xml.split("<DATA>", 1)[1]
    target_tag = f"<{obj_type.upper()}"
    return target_tag in data_content

# Official lightweight Tally Prime Collection ping payload
_PING_XML_PAYLOAD = (
    b"<ENVELOPE><HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST>"
    b"<TYPE>Collection</TYPE><ID>MyTallyPing</ID></HEADER><BODY><DESC>"
    b"<STATICVARIABLES><SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT></STATICVARIABLES>"
    b"<TDL><TDLMESSAGE><COLLECTION NAME=\"MyTallyPing\" ISMODIFY=\"No\">"
    b"<TYPE>Company</TYPE><FETCH>NAME</FETCH></COLLECTION></TDLMESSAGE></TDL>"
    b"</DESC></BODY></ENVELOPE>"
)

class TallyWaitTimer:
    """
    Live elapsed timer while waiting for TallyPrime to respond to an HTTP request.
    Displays live seconds in interactive terminal, logs heartbeats periodically,
    and invokes an optional progress callback for GUI / status bar updates.
    """
    def __init__(
        self,
        label: str,
        timeout: int,
        attempt: int = 1,
        total_attempts: int = 1,
        callback: Optional[Callable] = None,
        log_interval: float = 10.0,
    ):
        self.label = label
        self.timeout = timeout
        self.attempt = attempt
        self.total_attempts = total_attempts
        self.callback = callback
        self.log_interval = log_interval
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.start_time: float = 0.0
        self.elapsed: float = 0.0

    def start(self) -> "TallyWaitTimer":
        self.start_time = time.time()
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name=f"TallyWaitTimer-{self.label}"
        )
        self._thread.start()
        return self

    def stop(self) -> float:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)
        if self.start_time:
            self.elapsed = time.time() - self.start_time
        # Clear interactive terminal in-place line if applicable
        if sys.stdout and hasattr(sys.stdout, "isatty") and sys.stdout.isatty():
            try:
                sys.stdout.write("\r" + " " * 85 + "\r")
                sys.stdout.flush()
            except Exception:
                pass
        if self.callback:
            try:
                self.callback(self.label, self.elapsed, self.timeout, self.attempt, self.total_attempts, finished=True)
            except Exception:
                pass
        return self.elapsed

    def _run(self) -> None:
        last_logged = self.start_time
        while not self._stop_event.wait(1.0):
            self.elapsed = time.time() - self.start_time
            sec = int(self.elapsed)

            # 1. Callback for live status updates in GUI / webview
            if self.callback:
                try:
                    self.callback(self.label, self.elapsed, self.timeout, self.attempt, self.total_attempts, finished=False)
                except Exception:
                    pass

            # 2. Interactive terminal live timer
            if sys.stdout and hasattr(sys.stdout, "isatty") and sys.stdout.isatty():
                try:
                    attempt_str = f" [try {self.attempt}/{self.total_attempts}]" if self.total_attempts > 1 else ""
                    sys.stdout.write(f"\r   ⏳ Waiting for Tally ('{self.label}'): {sec}s / {self.timeout}s{attempt_str}... ")
                    sys.stdout.flush()
                except Exception:
                    pass

            # 3. Activity Log & file logger periodic heartbeat (every 10s by default)
            if (time.time() - last_logged) >= self.log_interval:
                last_logged = time.time()
                attempt_str = f" [try {self.attempt}/{self.total_attempts}]" if self.total_attempts > 1 else ""
                logger.info(f"   ⏳ Waiting for Tally ('{self.label}'): {sec}s elapsed (max {self.timeout}s){attempt_str}...")


class TallyClient:
    def __init__(self, tally_url: str = "http://127.0.0.1:9000", timeout: int = 15):
        self.tally_url = tally_url.rstrip("/") + "/"
        self.timeout = timeout
        # Labels of collections the last export_full_collections() call could not export
        self.last_export_failures: List[str] = []
        self.on_wait_progress: Optional[Callable] = None

    @contextmanager
    def _urlopen(self, req: urllib.request.Request, timeout: Optional[int] = None):
        """Opens a request to Tally and holds the agent-wide lock until the caller's `with` block ends, so the
        response is read before any other thread can send. Tally answers one request at a time."""
        tout = timeout if timeout is not None else self.timeout
        with _TALLY_LOCK:
            with urllib.request.urlopen(req, timeout=tout) as resp:
                yield resp

    def check_health(self) -> Tuple[bool, str]:
        """Pings Tally to check if the XML server is responding using non-destructive Collection query."""
        try:
            req = urllib.request.Request(
                self.tally_url,
                data=_PING_XML_PAYLOAD,
                headers={"Content-Type": "text/xml;charset=utf-8"}
            )
            with self._urlopen(req, timeout=self.timeout) as resp:
                data = decode_tally_reply(resp.read())
                return ("<ENVELOPE>" in data or "<RESPONSE>" in data), "Connected"
        except urllib.error.URLError as e:
            return False, f"Unreachable ({e.reason})"
        except Exception as e:
            return False, str(e)

    def discover_tally_host(self) -> Dict[str, Any]:
        """
        Discovers internal host paths from Tally using TDL system formulas:
        - $$ApplicationPath (where tally.exe, tallysave.tsf, and tally.ini reside)
        - $$DataPath (where company databases reside)
        - $$Release (TallyPrime version)
        - Active Company Name
        """
        discovery_xml = """<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>SystemInfoCollection</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="SystemInfoCollection">
            <TYPE>Company</TYPE>
            <COMPUTE>AppPath : $$ApplicationPath</COMPUTE>
            <COMPUTE>CmpName : $Name</COMPUTE>
            <COMPUTE>CmpNumber : $CompanyNumber</COMPUTE>
            <COMPUTE>CmpGuid : $Guid</COMPUTE>
            <COMPUTE>DataPath : $$DataPath</COMPUTE>
            <COMPUTE>SysRelease : $$Release</COMPUTE>
            <COMPUTE>SysVersion : $$Version</COMPUTE>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>"""

        result = {
            "connected": False,
            "company_name": "",
            "company_id": "",
            "company_number": "",
            "guid": "",
            "app_path": "",
            "data_path": "",
            "tallysave_path": "",
            "tally_ini_path": "",
            "release": "",
            "raw_response": ""
        }

        try:
            req = urllib.request.Request(
                self.tally_url,
                data=discovery_xml.encode("utf-8"),
                headers={"Content-Type": "text/xml;charset=utf-8"}
            )
            with self._urlopen(req, timeout=self.timeout) as resp:
                raw_xml = decode_tally_reply(resp.read())
                result["raw_response"] = raw_xml

                if "<ENVELOPE>" in raw_xml:
                    result["connected"] = True
                    try:
                        root = ET.fromstring(raw_xml)
                        cmp_node = root.find(".//COLLECTION/COMPANY")
                        if cmp_node is None:
                            cmp_node = root.find(".//DATA//COMPANY")
                        if cmp_node is not None:
                            result["company_name"] = cmp_node.get("NAME") or ""
                            
                            for child in cmp_node:
                                tag_upper = child.tag.upper()
                                val = (child.text or "").strip()
                                if tag_upper == "APPPATH" and not result["app_path"]:
                                    result["app_path"] = val
                                elif tag_upper in ("DATAPATH", "FULLDATAPATH") and not result["data_path"]:
                                    result["data_path"] = val
                                elif tag_upper in ("SYSRELEASE", "RELEASE") and not result["release"]:
                                    result["release"] = val
                                elif tag_upper in ("CMPNAME", "COMPANYNAME") and not result["company_name"]:
                                    result["company_name"] = val
                                elif tag_upper in ("CMPNUMBER", "COMPANYNUMBER") and not result["company_id"]:
                                    result["company_id"] = val
                                    result["company_number"] = val
                                elif tag_upper in ("CMPGUID", "COMPANYGUID") and not result["guid"]:
                                    result["guid"] = val

                            if result["app_path"]:
                                sep = "\\" if "\\" in result["app_path"] else "/"
                                result["tallysave_path"] = f"{result['app_path'].rstrip(sep)}{sep}tallysave.tsf"
                                result["tally_ini_path"] = f"{result['app_path'].rstrip(sep)}{sep}tally.ini"
                    except Exception as pe:
                        logger.warning(f"Error parsing discovery XML: {pe}")

        except Exception as e:
            logger.error(f"Error executing discovery query against Tally: {e}")

        return result

    def get_open_companies(self) -> List[Dict[str, str]]:
        """
        Queries Tally for all companies currently open/loaded in memory.
        Returns list of dicts: [{"name": ..., "guid": ..., "starting_from": ..., "ending_at": ..., "fingerprint": ..., "company_id": ...}].
        fingerprint is the Tally company number and books-from date: what differs between a company and a
        copied or restored one that still carries its GUID.
        """
        query = """<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>AllOpenCompanies</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="AllOpenCompanies">
            <TYPE>Company</TYPE>
            <FETCH>NAME,GUID,STARTINGFROM,ENDINGAT,COMPANYNUMBER,BOOKSFROM</FETCH>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>"""
        companies = []
        try:
            req = urllib.request.Request(
                self.tally_url,
                data=query.encode("utf-8"),
                headers={"Content-Type": "text/xml;charset=utf-8"}
            )
            with self._urlopen(req, timeout=self.timeout) as resp:
                raw_xml = decode_tally_reply(resp.read())
                if "<ENVELOPE>" in raw_xml:
                    root = ET.fromstring(raw_xml)
                    for cmp_node in root.findall(".//COLLECTION/COMPANY"):
                        name = cmp_node.get("NAME") or cmp_node.findtext("NAME") or ""
                        guid = cmp_node.findtext("GUID") or ""
                        s_from = cmp_node.findtext("STARTINGFROM") or ""
                        e_to = cmp_node.findtext("ENDINGAT") or ""
                        number = (cmp_node.findtext("COMPANYNUMBER") or "").strip()
                        books_from = (cmp_node.findtext("BOOKSFROM") or "").strip()
                        if name:
                            companies.append({
                                "name": name.strip(),
                                "guid": guid.strip(),
                                "starting_from": s_from.strip(),
                                "ending_at": e_to.strip(),
                                "fingerprint": f"{number}|{books_from}" if number and books_from else "",
                                "number": number,
                                "company_number": number,
                                "company_id": number,
                            })
        except Exception as e:
            logger.debug(f"Error checking open companies: {e}")
        return companies

    def export_full_collections(self, company_name: Optional[str] = None, min_alter_id: int = 0,
                                min_voucher_alter_id: Optional[int] = None, skip_vouchers: bool = False,
                                only_vouchers: bool = False) -> List[Tuple[str, str]]:
        """
        Exports master and transaction collections from TallyPrime for inbound sync.
        Supports full dump (min_alter_id=0) or incremental changes (min_alter_id > 0).
        skip_vouchers leaves the vouchers out (they are then pulled in date ranges, see
        export_vouchers_between); only_vouchers exports nothing else.
        """
        sv_cmp = f"<SVCURRENTCOMPANY>{escape_xml(company_name)}</SVCURRENTCOMPANY>" if company_name else ""
        
        collections = [
            ("Company", "Company", "NAME,GUID,COMPANYNUMBER,STARTINGFROM,BOOKSFROM,ADDRESS.LIST,BASICCOMPANYADDRESS.LIST,STATENAME,COUNTRYNAME,PINCODE,PHONENUMBER,LEDGERPHONE,TELEPHONENUMBER,BASICCOMPANYPHONE,MOBILENUMBERS.LIST,MOBILENUMBER,BASICCOMPANYMOBILE,EMAIL,EMAILID,BASICCOMPANYEMAIL,WEBSITE,BASICCOMPANYWEBSITE,GSTREGISTRATIONNUMBER,INCOMETAXNUMBER,CURRENCYSYMBOL,FORMALNAME", False),
            ("Groups", "Group", "NAME,GUID,MASTERID,PARENT,ALTERID,ISREVENUE,ISDEEMEDPOSITIVE,AFFECTSGROSSPROFIT,ISADDABLE,ISSUBLEDGER,ISBILLWISEON,BASICGROUPISCALCULABLE,ADDLALLOCTYPE", True),
            ("Ledgers", "Ledger", LEDGER_FETCH, True),
            ("VoucherTypes", "VoucherType", "NAME,PARENT,ALTERID,NUMBERINGMETHOD,USEZEROENTRIES,ISOPTIONAL,COMMONNARRATION,MULTINARRATION,PRINTAFTERSAVE", True),
            ("StockGroups", "StockGroup", "NAME,GUID,MASTERID,PARENT,ALTERID", True),
            # No ALTERID filter, so it comes with the full passes only, like units and godowns.
            # A PriceLevel collection request is NOT sent: on a real TallyPrime it never answered and left the
            # whole XML server hung until Tally was restarted (every later request timed out too).
            ("Currencies", "Currency", CURRENCY_FETCH, False),
            ("UOMs", "Unit", "NAME,GUID,MASTERID,ALTERID,ORIGINALNAME,DECIMALPLACES,ISSIMPLEUNIT,BASEUNITS,ADDITIONALUNITS,CONVERSION", False),
            ("Godowns", "Godown", "NAME,GUID,ALTERID,PARENT", False),
            ("StockCategories", "StockCategory", "NAME,GUID,ALTERID,PARENT", False),
            ("CostCategories", "CostCategory", "NAME,GUID,ALTERID", False),
            ("CostCentres", "CostCentre", "NAME,GUID,MASTERID,ALTERID,PARENT,CATEGORY,FORPAYROLL,ISEMPLOYEEGROUP,DATEOFJOIN,DESIGNATION,GENDER,MAILINGNAME.LIST,EMPLOYEEPERIOD.LIST", False),
            ("AttendanceTypes", "AttendanceType", "NAME,GUID,MASTERID,ALTERID,PARENT,ATTENDANCEPRODUCTIONTYPE,ATTENDANCEPERIOD,BASEUNITS", False),
            ("StockItems", "StockItem", STOCK_ITEM_FETCH, True),
            ("Vouchers", "Voucher", VOUCHER_FETCH, True)
        ]
        if skip_vouchers:
            collections = [c for c in collections if c[1] != "Voucher"]
        if only_vouchers:
            collections = [c for c in collections if c[1] == "Voucher"]
        
        results = []
        self.last_export_failures = []
        # Vouchers have their own change counter in Tally; without a separate watermark they share the masters'
        master_min_alter_id = min_alter_id
        for label, obj_type, fetch_fields, supports_alter_filter in collections:
            min_alter_id = master_min_alter_id
            if obj_type == "Voucher" and min_voucher_alter_id is not None:
                min_alter_id = min_voucher_alter_id
            # If incremental sync, only query collections that support ALTERID filtering
            if master_min_alter_id > 0 and not supports_alter_filter:
                continue

            date_filters = ""
            if obj_type == "Voucher":
                date_filters = '<SVFROMDATE TYPE="Date">20000101</SVFROMDATE><SVTODATE TYPE="Date">20991231</SVTODATE>'

            alter_filter_xml = ""
            alter_system_xml = ""
            if min_alter_id > 0 and supports_alter_filter:
                alter_filter_xml = "<FILTERS>AlteredFilter</FILTERS>"
                alter_system_xml = f"""
          <SYSTEM TYPE="Formulae" NAME="AlteredFilter">
            $ALTERID &gt; {min_alter_id}
          </SYSTEM>"""

            xml_req = f"""<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>Export{label}</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
        {date_filters}
        {sv_cmp}
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="Export{label}">
            <TYPE>{obj_type}</TYPE>
            <FETCH>{fetch_fields}</FETCH>
            {alter_filter_xml}
          </COLLECTION>{alter_system_xml}
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>"""
            max_retries = 2
            resp_xml = self._export(xml_req, label, timeout=120, retries=max_retries)
            if resp_xml is not None:
                # On incremental passes, check if any actual objects exist in collection to avoid sending empty payloads
                if min_alter_id > 0 and not has_collection_records(resp_xml, obj_type):
                    continue
                results.append((label, resp_xml))
            else:
                # Either every attempt raised or Tally never returned an ENVELOPE: the caller must not
                # treat this cycle as complete, or these records would fall behind the sync watermark.
                self.last_export_failures.append(label)

        return results

    def _export(self, xml_req: str, label: str, timeout: int = 120, retries: int = 2) -> Optional[str]:
        """Post one export request to Tally with a live progress timer. The reply, or None when Tally did not answer with an export."""
        for attempt in range(retries + 1):
            timer = TallyWaitTimer(
                label=label,
                timeout=timeout,
                attempt=attempt + 1,
                total_attempts=retries + 1,
                callback=getattr(self, "on_wait_progress", None)
            )
            timer.start()
            try:
                req = urllib.request.Request(self.tally_url, data=xml_req.encode("utf-8"),
                                             headers={"Content-Type": "text/xml;charset=utf-8"})
                with self._urlopen(req, timeout=timeout) as resp:
                    resp_xml = decode_tally_reply(resp.read())
                    elapsed = timer.stop()
                    if elapsed >= 2.0:
                        logger.info(f"   ⏱️ Tally answered '{label}' in {elapsed:.1f}s.")
                    if "<ENVELOPE>" in resp_xml:
                        return resp_xml
                    return None
            except Exception as e:
                elapsed = timer.stop()
                if attempt < retries:
                    logger.info(f"   ⏳ Tally did not respond to '{label}' after {elapsed:.1f}s ({e}). Retrying ({attempt + 2}/{retries + 1})...")
                    time.sleep(1)
                else:
                    logger.warning(f"Failed to export '{label}' from Tally after {retries + 1} attempts ({elapsed:.1f}s): {e}")
        return None

    def _voucher_request(self, company_name: Optional[str], label: str, fetch: str, date_from: str = "20000101",
                         date_to: str = "20991231", filter_on_date: bool = False) -> str:
        sv_cmp = f"<SVCURRENTCOMPANY>{escape_xml(company_name)}</SVCURRENTCOMPANY>" if company_name else ""
        filters = formula = ""
        if filter_on_date:
            filters = "<FILTERS>MyTallyInRange</FILTERS>"
            formula = (f'<SYSTEM TYPE="Formulae" NAME="MyTallyInRange">$Date &gt;= $$Date:"{tally_date_text(date_from)}" '
                       f'AND $Date &lt;= $$Date:"{tally_date_text(date_to)}"</SYSTEM>')
        return f"""<ENVELOPE>
  <HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Collection</TYPE><ID>{label}</ID></HEADER>
  <BODY><DESC>
    <STATICVARIABLES>
      <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
      <SVFROMDATE TYPE="Date">{date_from}</SVFROMDATE><SVTODATE TYPE="Date">{date_to}</SVTODATE>
      {sv_cmp}
    </STATICVARIABLES>
    <TDL><TDLMESSAGE>
      <COLLECTION NAME="{label}"><TYPE>Voucher</TYPE><FETCH>{fetch}</FETCH>{filters}</COLLECTION>
      {formula}
    </TDLMESSAGE></TDL>
  </DESC></BODY>
</ENVELOPE>"""

    def export_voucher_index(self, company_name: Optional[str]) -> Optional[List[str]]:
        """The date of every voucher in the company (YYYYMMDD), from an export that fetches nothing else, so it
        is small and quick even for a company whose full export is not. None when Tally did not answer."""
        resp_xml = self._export(self._voucher_request(company_name, "MyTallyVoucherIndex", "DATE,MASTERID"), "VoucherIndex")
        if resp_xml is None:
            return None
        return [d for d in voucher_dates(resp_xml) if d]

    def probe_change_counters(self, company_name: Optional[str], company_guid: str = "") -> Optional[Tuple[int, int]]:
        """(masters counter, vouchers counter): TallyPrime's company-level AltMstId and AltVchId, which rise
        whenever a master or a voucher is created, altered or deleted. One small request. None whenever there
        is any doubt (no answer, no such company, the fields missing or not numbers): the caller then runs its
        normal cycle. UNVERIFIED against a real TallyPrime: see docs/Multi-Tenant Rollout Runbook.md."""
        sv_cmp = f"<SVCURRENTCOMPANY>{escape_xml(company_name)}</SVCURRENTCOMPANY>" if company_name else ""
        request = f"""<ENVELOPE>
  <HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Collection</TYPE><ID>MyTallyChangeProbe</ID></HEADER>
  <BODY><DESC>
    <STATICVARIABLES><SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>{sv_cmp}</STATICVARIABLES>
    <TDL><TDLMESSAGE>
      <COLLECTION NAME="MyTallyChangeProbe">
        <TYPE>Company</TYPE>
        <NATIVEMETHOD>Name, Guid, AltMstId, AltVchId</NATIVEMETHOD>
      </COLLECTION>
    </TDLMESSAGE></TDL>
  </DESC></BODY>
</ENVELOPE>"""
        try:
            resp_xml = self._export(request, "ChangeProbe", timeout=15, retries=0)
        except Exception:
            return None
        return parse_change_counters(resp_xml, company_name or "", company_guid)

    def export_voucher_keys(self, company_name: Optional[str]) -> Optional[List[Dict[str, str]]]:
        """MASTERID, GUID, ALTERID and DATE of every voucher in the company, from an export that fetches nothing
        else. None when Tally did not answer."""
        resp_xml = self._export(self._voucher_request(company_name, "MyTallyVoucherKeys", "MASTERID,GUID,ALTERID,DATE,VOUCHERTYPENAME"),
                                "VoucherKeys")
        return None if resp_xml is None else voucher_keys(resp_xml)

    def export_master_keys(self, company_name: Optional[str], obj_type: str) -> Optional[List[Dict[str, str]]]:
        """NAME, GUID and MASTERID of every master of one type (Ledger, StockItem). None when Tally did not answer."""
        sv_cmp = f"<SVCURRENTCOMPANY>{escape_xml(company_name)}</SVCURRENTCOMPANY>" if company_name else ""
        label = f"MyTally{obj_type}Keys"
        request = f"""<ENVELOPE>
  <HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Collection</TYPE><ID>{label}</ID></HEADER>
  <BODY><DESC>
    <STATICVARIABLES><SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>{sv_cmp}</STATICVARIABLES>
    <TDL><TDLMESSAGE>
      <COLLECTION NAME="{label}"><TYPE>{obj_type}</TYPE><FETCH>NAME,GUID,MASTERID,CLOSINGBALANCE</FETCH></COLLECTION>
    </TDLMESSAGE></TDL>
  </DESC></BODY>
</ENVELOPE>"""
        resp_xml = self._export(request, f"{obj_type}Keys")
        return None if resp_xml is None else master_keys(resp_xml, obj_type.upper())

    def export_vouchers_between(self, company_name: Optional[str], date_from: str, date_to: str,
                                method: str = "sv", label: Optional[str] = None) -> Optional[str]:
        """The vouchers dated date_from..date_to (YYYYMMDD, both included), asked for by one of
        VOUCHER_RANGE_METHODS. The caller must check the answer really is that range: a Tally that ignores
        the range returns every voucher. None when Tally did not answer."""
        request = self._voucher_request(company_name, "MyTallyVouchersInRange", VOUCHER_FETCH, date_from, date_to,
                                        filter_on_date=(method == "filter"))
        lbl = label or f"Vouchers {date_from}-{date_to}"
        return self._export(request, lbl)

    def _log_traffic(self, direction: str, title: str, content: str):
        """Logs exact traffic to a dedicated rotating log file and console logger."""
        try:
            from datetime import datetime
            log_dir = get_logs_dir()
            log_file = os.path.join(log_dir, "tally_traffic.log")
            
            # Simple rotation: keep up to 5MB, rotate to .1
            if os.path.exists(log_file) and os.path.getsize(log_file) > 5 * 1024 * 1024:
                backup = log_file + ".1"
                try:
                    if os.path.exists(backup):
                        os.remove(backup)
                    os.rename(log_file, backup)
                except Exception:
                    pass

            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            header = f"\n{'=' * 80}\n[{ts}] {direction}: {title}\n{'=' * 80}\n"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(header)
                f.write(content.strip() + "\n")
        except Exception as e:
            logger.warning(f"Failed writing to tally_traffic.log: {e}")

    def send_xml(self, xml_payload: str, timeout: int = 60) -> Tuple[bool, str]:
        """
        Sends an XML payload (Voucher, Ledger, Master) to TallyPrime and returns (success, response_string_or_reason).
        Logs full request and response to tally_traffic.log and console with a live progress timer.
        """
        self._log_traffic("📤 [REQUEST SENT TO TALLY]", f"POST {self.tally_url}", xml_payload)
        logger.info(f"\n=======================================================\n📤 [OUTBOUND REQUEST TO TALLY]\nURL: {self.tally_url}\nPAYLOAD:\n{xml_payload}\n=======================================================")
        timer = TallyWaitTimer(
            label="Outbound Voucher",
            timeout=timeout,
            callback=getattr(self, "on_wait_progress", None)
        )
        timer.start()
        try:
            req = urllib.request.Request(
                self.tally_url,
                data=xml_payload.encode("utf-8"),
                headers={"Content-Type": "text/xml;charset=utf-8"}
            )
            with self._urlopen(req, timeout=timeout) as resp:
                resp_str = decode_tally_reply(resp.read())
                elapsed = timer.stop()
                if elapsed >= 2.0:
                    logger.info(f"   ⏱️ Tally answered outbound request in {elapsed:.1f}s.")
                self._log_traffic("📥 [RESPONSE RECEIVED FROM TALLY]", f"STATUS {resp.status}", resp_str)
                logger.info(f"\n=======================================================\n📥 [INBOUND RESPONSE FROM TALLY]\nSTATUS: {resp.status}\nRESPONSE:\n{resp_str}\n=======================================================")
                
                ok, reason = parse_import_result(resp_str)
                return ok, (resp_str if ok else reason)
        except Exception as e:
            timer.stop()
            err_msg = f"{NETWORK_ERROR_PREFIX}: {str(e)}"
            self._log_traffic("❌ [REQUEST FAILED / ERROR]", f"URL: {self.tally_url}", err_msg)
            logger.error(f"❌ [TALLY COMMUNICATION ERROR]: {err_msg}")
            return False, err_msg

    def import_batch(self, envelope: str, timeout: int = 120) -> Tuple[bool, str]:
        """Send one import (a restore batch) and return (Tally's reply was read, the reply or why not). Unlike
        send_xml, the payload is not written to the logs: a restore sends the whole of a company's books."""
        try:
            req = urllib.request.Request(self.tally_url, data=envelope.encode("utf-8"),
                                         headers={"Content-Type": "text/xml;charset=utf-8"})
            with self._urlopen(req, timeout=timeout) as resp:
                return True, decode_tally_reply(resp.read())
        except Exception as e:
            return False, f"{NETWORK_ERROR_PREFIX}: {e}"

    def find_voucher_by_master_id(self, company_name: str, master_id: int) -> Optional[Dict[str, Any]]:
        """
        The voucher Tally holds under this master id: its number, GUID and date. Tally numbers its automatic
        voucher types itself, so this is how the number of a voucher just pushed is learned.
        """
        xml_req = f"""<ENVELOPE><HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Collection</TYPE><ID>MyTallyFindVchById</ID></HEADER>
<BODY><DESC><STATICVARIABLES>
  <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
  <SVCURRENTCOMPANY>{escape_xml(company_name)}</SVCURRENTCOMPANY>
</STATICVARIABLES><TDL><TDLMESSAGE>
  <SYSTEM TYPE="Formulae" NAME="MyTallyByMasterId">$MasterID = {int(master_id)}</SYSTEM>
  <COLLECTION NAME="MyTallyFindVchById" ISMODIFY="No"><TYPE>Voucher</TYPE>
    <FETCH>GUID,MASTERID,ALTERID,VOUCHERNUMBER,DATE,ISCANCELLED</FETCH><FILTERS>MyTallyByMasterId</FILTERS>
  </COLLECTION>
</TDLMESSAGE></TDL></DESC></BODY></ENVELOPE>"""
        try:
            req = urllib.request.Request(self.tally_url, data=xml_req.encode("utf-8"),
                                         headers={"Content-Type": "text/xml;charset=utf-8"})
            with self._urlopen(req, timeout=15) as resp:
                resp_xml = decode_tally_reply(resp.read())
            found = re.search(r"<VOUCHER [^>]*>.*?</VOUCHER>", resp_xml, re.S)
            if not found:
                return None

            def field(tag: str) -> str:
                m = re.search(rf"<{tag}[^>]*>([^<]*)</{tag}>", found.group(0))
                return m.group(1).strip() if m else ""

            if not field("MASTERID").isdigit():
                return None
            return {"master_id": int(field("MASTERID")), "guid": field("GUID"), "number": field("VOUCHERNUMBER"),
                    "date": field("DATE"), "cancelled": field("ISCANCELLED").lower() == "yes"}
        except Exception as e:
            logger.debug(f"Error finding voucher by master id {master_id}: {e}")
        return None

    FULL_VOUCHER_FETCH = ("*,ALLLEDGERENTRIES.LIST,INVENTORYENTRIES.LIST,ALLINVENTORYENTRIES.LIST,BILLALLOCATIONS.LIST,"
                          "BANKALLOCATIONS.LIST,BATCHALLOCATIONS.LIST,EWAYBILLDETAILS.LIST,COSTCENTREALLOCATIONS.LIST")

    def fetch_voucher_block(self, company_name: str, master_id: int) -> Optional[str]:
        """The voucher Tally holds under this master id, whole, as `<VOUCHER ...>...</VOUCHER>`; None when Tally
        did not answer or holds none (or more than one, which is never guessed at)."""
        xml_req = f"""<ENVELOPE><HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Collection</TYPE><ID>MyTallyFullVchById</ID></HEADER>
<BODY><DESC><STATICVARIABLES>
  <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
  <SVCURRENTCOMPANY>{escape_xml(company_name)}</SVCURRENTCOMPANY>
  <SVFROMDATE TYPE="Date">20000101</SVFROMDATE><SVTODATE TYPE="Date">20991231</SVTODATE>
</STATICVARIABLES><TDL><TDLMESSAGE>
  <SYSTEM TYPE="Formulae" NAME="MyTallyByMasterId">$MasterID = {int(master_id)}</SYSTEM>
  <COLLECTION NAME="MyTallyFullVchById" ISMODIFY="No"><TYPE>Voucher</TYPE>
    <FETCH>{self.FULL_VOUCHER_FETCH}</FETCH><FILTERS>MyTallyByMasterId</FILTERS>
  </COLLECTION>
</TDLMESSAGE></TDL></DESC></BODY></ENVELOPE>"""
        resp = self._export(xml_req, "FullVoucher", timeout=30, retries=1)
        if resp is None:
            return None
        info = resp.find("<CMPINFO>")
        info_end = resp.find("</CMPINFO>", info) if info >= 0 else -1
        if info >= 0 and info_end >= 0:    # its counts hold <VOUCHER>44</VOUCHER>, which is not a voucher
            resp = resp[:info] + resp[info_end + len("</CMPINFO>"):]
        blocks = re.findall(r"<VOUCHER\b[^>]*>.*?</VOUCHER>", resp, re.S)
        return blocks[0] if len(blocks) == 1 else None

    def find_voucher_by_remote_id(self, company_name: str, remote_id: str, date_yyyymmdd: Optional[str] = None) -> Optional[Dict[str, str]]:
        """
        Looks up a voucher in Tally by REMOTEID. Useful after a timeout to verify if Tally
        actually committed the voucher before attempting a blind resend.
        """
        if not re.match(r"^[A-Za-z0-9-]+$", remote_id):
            return None
        from_date = date_yyyymmdd if date_yyyymmdd else "20000101"
        to_date = date_yyyymmdd if date_yyyymmdd else "20991231"
        esc_cmp = escape_xml(company_name)
        xml_req = f"""<ENVELOPE><HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Collection</TYPE><ID>MyTallyFindVch</ID></HEADER>
<BODY><DESC><STATICVARIABLES>
  <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
  <SVCURRENTCOMPANY>{esc_cmp}</SVCURRENTCOMPANY>
  <SVFROMDATE TYPE="Date">{from_date}</SVFROMDATE><SVTODATE TYPE="Date">{to_date}</SVTODATE>
</STATICVARIABLES><TDL><TDLMESSAGE>
  <SYSTEM TYPE="Formulae" NAME="MyTallyByRemoteId">$RemoteID = "{remote_id}"</SYSTEM>
  <COLLECTION NAME="MyTallyFindVch" ISMODIFY="No"><TYPE>Voucher</TYPE>
    <FETCH>GUID,ALTERID,VOUCHERNUMBER,DATE,ISCANCELLED</FETCH><FILTERS>MyTallyByRemoteId</FILTERS>
  </COLLECTION>
</TDLMESSAGE></TDL></DESC></BODY></ENVELOPE>"""
        try:
            req = urllib.request.Request(
                self.tally_url,
                data=xml_req.encode("utf-8"),
                headers={"Content-Type": "text/xml;charset=utf-8"}
            )
            with self._urlopen(req, timeout=15) as resp:
                resp_xml = decode_tally_reply(resp.read())
                if "<VOUCHER" in resp_xml:
                    root = ET.fromstring(resp_xml)
                    vch_node = root.find(".//COLLECTION/VOUCHER")
                    if vch_node is None:
                        vch_node = root.find(".//DATA//VOUCHER")
                    if vch_node is not None:
                        return {
                            "guid": vch_node.findtext("GUID") or "",
                            "alterid": vch_node.findtext("ALTERID") or "",
                            "vouchernumber": vch_node.findtext("VOUCHERNUMBER") or "",
                            "date": vch_node.findtext("DATE") or "",
                            "iscancelled": vch_node.findtext("ISCANCELLED") or "No",
                        }
        except Exception as e:
            logger.debug(f"Error finding voucher by RemoteID {remote_id}: {e}")
        return None
