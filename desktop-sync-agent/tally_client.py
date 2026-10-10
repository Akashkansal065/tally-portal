import os
import re
import time
import threading
from contextlib import contextmanager
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
import logging
from typing import Dict, Any, Optional, Tuple, List

from config import get_logs_dir

logger = logging.getLogger("TallyClient")

# Global lock to serialize requests to Tally Prime's single-threaded HTTP XML server
_TALLY_LOCK = threading.Lock()

# send_xml's reason when no answer came back from Tally (timeout, refused or dropped connection), as opposed to
# an answer that rejected the request
NETWORK_ERROR_PREFIX = "HTTP/Network Error"

_INVALID_XML_10_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x84\x86-\x9f]")
_COUNT = re.compile(r"<(CREATED|ALTERED|DELETED|CANCELLED|IGNORED|ERRORS|EXCEPTIONS)>\s*(\d+)\s*</\1>")

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
                 "ISCANCELLED,ISOPTIONAL,ALLLEDGERENTRIES.LIST,INVENTORYENTRIES.LIST,ALLINVENTORYENTRIES.LIST,"
                 "INVENTORYENTRIESIN.LIST,INVENTORYENTRIESOUT.LIST,ATTENDANCEENTRIES.*,CATEGORYENTRY.LIST")

# Two ways of asking Tally for the vouchers of a date range. Which one a Tally honours is found by trying:
# "sv" sets the report period; "filter" also filters the collection on the voucher date.
VOUCHER_RANGE_METHODS = ("sv", "filter")

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_VOUCHER_OPEN = re.compile(r"<VOUCHER[\s>]")
# One pass over a voucher: where its lists open and close, and every DATE on the way
_LIST_OR_DATE = re.compile(r"<(/?)[A-Z0-9_.]+\.LIST\b[^>]*?(/?)>|<DATE\b[^>]*>\s*(\d{8})\s*</DATE>")


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

class TallyClient:
    def __init__(self, tally_url: str = "http://127.0.0.1:9000", timeout: int = 15):
        self.tally_url = tally_url.rstrip("/") + "/"
        self.timeout = timeout
        # Labels of collections the last export_full_collections() call could not export
        self.last_export_failures: List[str] = []

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
                data = resp.read().decode("utf-8", errors="replace")
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
                raw_xml = resp.read().decode("utf-8", errors="replace")
                result["raw_response"] = raw_xml

                if "<ENVELOPE>" in raw_xml:
                    result["connected"] = True
                    try:
                        root = ET.fromstring(raw_xml)
                        cmp_node = root.find(".//COLLECTION/COMPANY") or root.find(".//DATA//COMPANY")
                        if cmp_node is not None:
                            result["company_name"] = cmp_node.get("NAME") or ""
                            
                            for child in cmp_node:
                                tag_upper = child.tag.upper()
                                val = (child.text or "").strip()
                                if tag_upper == "APPPATH":
                                    result["app_path"] = val
                                elif tag_upper in ("DATAPATH", "FULLDATAPATH"):
                                    result["data_path"] = val
                                elif tag_upper in ("SYSRELEASE", "RELEASE"):
                                    result["release"] = val
                                elif tag_upper in ("CMPNAME", "NAME") and not result["company_name"]:
                                    result["company_name"] = val

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
        Returns list of dicts: [{"name": ..., "guid": ..., "starting_from": ..., "ending_at": ...}]
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
            <FETCH>NAME,GUID,STARTINGFROM,ENDINGAT</FETCH>
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
                raw_xml = resp.read().decode("utf-8", errors="replace")
                if "<ENVELOPE>" in raw_xml:
                    root = ET.fromstring(raw_xml)
                    for cmp_node in root.findall(".//COLLECTION/COMPANY"):
                        name = cmp_node.get("NAME") or cmp_node.findtext("NAME") or ""
                        guid = cmp_node.findtext("GUID") or ""
                        s_from = cmp_node.findtext("STARTINGFROM") or ""
                        e_to = cmp_node.findtext("ENDINGAT") or ""
                        if name:
                            companies.append({
                                "name": name.strip(),
                                "guid": guid.strip(),
                                "starting_from": s_from.strip(),
                                "ending_at": e_to.strip()
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
            ("Company", "Company", "NAME,GUID,COMPANYNUMBER,STARTINGFROM,BOOKSFROM,ADDRESS.LIST,BASICCOMPANYADDRESS.LIST,STATENAME,COUNTRYNAME,PINCODE,LEDGERPHONE,TELEPHONENUMBER,BASICCOMPANYPHONE,MOBILENUMBER,BASICCOMPANYMOBILE,EMAIL,EMAILID,BASICCOMPANYEMAIL,WEBSITE,BASICCOMPANYWEBSITE,GSTREGISTRATIONNUMBER,INCOMETAXNUMBER,CURRENCYSYMBOL,FORMALNAME", False),
            ("Groups", "Group", "NAME,GUID,MASTERID,PARENT,ALTERID,ISREVENUE,ISDEEMEDPOSITIVE,AFFECTSGROSSPROFIT,ISADDABLE,ISSUBLEDGER,ISBILLWISEON,BASICGROUPISCALCULABLE,ADDLALLOCTYPE", True),
            ("Ledgers", "Ledger", "NAME,GUID,MASTERID,PARENT,ALTERID,PAYTYPE,PAYSLIPNAME,CALCULATIONTYPE,OPENINGBALANCE,CLOSINGBALANCE,ADDRESS.LIST,STATENAME,PINCODE,LEDGERPHONE,INCOMETAXNUMBER,PARTYGSTIN,ISBILLWISEON,LEDGSTREGDETAILS.LIST,LEDMAILINGDETAILS.LIST", True),
            ("VoucherTypes", "VoucherType", "NAME,PARENT,ALTERID,NUMBERINGMETHOD,USEZEROENTRIES,ISOPTIONAL,COMMONNARRATION,MULTINARRATION,PRINTAFTERSAVE", True),
            ("StockGroups", "StockGroup", "NAME,GUID,MASTERID,PARENT,ALTERID", True),
            ("UOMs", "Unit", "NAME,GUID,MASTERID,ALTERID,ORIGINALNAME,DECIMALPLACES,ISSIMPLEUNIT,BASEUNITS,ADDITIONALUNITS,CONVERSION", False),
            ("Godowns", "Godown", "NAME,GUID,ALTERID,PARENT", False),
            ("StockCategories", "StockCategory", "NAME,GUID,ALTERID,PARENT", False),
            ("CostCategories", "CostCategory", "NAME,GUID,ALTERID", False),
            ("CostCentres", "CostCentre", "NAME,GUID,MASTERID,ALTERID,PARENT,CATEGORY,FORPAYROLL,ISEMPLOYEEGROUP,DATEOFJOIN,DESIGNATION,GENDER,MAILINGNAME.LIST,EMPLOYEEPERIOD.LIST", False),
            ("AttendanceTypes", "AttendanceType", "NAME,GUID,MASTERID,ALTERID,PARENT,ATTENDANCEPRODUCTIONTYPE,ATTENDANCEPERIOD,BASEUNITS", False),
            ("StockItems", "StockItem", "NAME,GUID,MASTERID,ALTERID,PARENT,CATEGORY,BASEUNITS,ADDITIONALUNITS,CONVERSION,DENOMINATOR,OPENINGBALANCE,OPENINGVALUE,OPENINGRATE,DESCRIPTION,NARRATION,ISBATCHWISEON,ISPERISHABLEON,IGNORENEGATIVESTOCK,COSTINGMETHOD,VALUATIONMETHOD,GSTTYPEOFSUPPLY,BATCHALLOCATIONS.LIST", True),
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
            exported = False
            for attempt in range(max_retries + 1):
                try:
                    req = urllib.request.Request(
                        self.tally_url,
                        data=xml_req.encode("utf-8"),
                        headers={"Content-Type": "text/xml;charset=utf-8"}
                    )
                    with self._urlopen(req, timeout=120) as resp:
                        resp_xml = resp.read().decode("utf-8", errors="replace")
                        if "<ENVELOPE>" in resp_xml:
                            exported = True
                            # On incremental passes, check if any actual objects exist in collection to avoid sending empty payloads
                            if min_alter_id > 0 and not has_collection_records(resp_xml, obj_type):
                                break
                            results.append((label, resp_xml))
                            break
                except Exception as e:
                    if attempt < max_retries:
                        logger.debug(f"Retrying export '{label}' from Tally (attempt {attempt + 1}/{max_retries}): {e}")
                        time.sleep(1)
                    else:
                        logger.warning(f"Failed to export collection '{label}' from Tally after {max_retries + 1} attempts: {e}")
            if not exported:
                # Either every attempt raised or Tally never returned an ENVELOPE: the caller must not
                # treat this cycle as complete, or these records would fall behind the sync watermark.
                self.last_export_failures.append(label)

        return results

    def _export(self, xml_req: str, label: str, timeout: int = 120, retries: int = 2) -> Optional[str]:
        """Post one export request to Tally. The reply, or None when Tally did not answer with an export."""
        for attempt in range(retries + 1):
            try:
                req = urllib.request.Request(self.tally_url, data=xml_req.encode("utf-8"),
                                             headers={"Content-Type": "text/xml;charset=utf-8"})
                with self._urlopen(req, timeout=timeout) as resp:
                    resp_xml = resp.read().decode("utf-8", errors="replace")
                    if "<ENVELOPE>" in resp_xml:
                        return resp_xml
                    return None
            except Exception as e:
                if attempt < retries:
                    logger.debug(f"Retrying export '{label}' from Tally (attempt {attempt + 1}/{retries}): {e}")
                    time.sleep(1)
                else:
                    logger.warning(f"Failed to export '{label}' from Tally after {retries + 1} attempts: {e}")
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

    def export_vouchers_between(self, company_name: Optional[str], date_from: str, date_to: str,
                                method: str = "sv") -> Optional[str]:
        """The vouchers dated date_from..date_to (YYYYMMDD, both included), asked for by one of
        VOUCHER_RANGE_METHODS. The caller must check the answer really is that range: a Tally that ignores
        the range returns every voucher. None when Tally did not answer."""
        request = self._voucher_request(company_name, "MyTallyVouchersInRange", VOUCHER_FETCH, date_from, date_to,
                                        filter_on_date=(method == "filter"))
        return self._export(request, f"Vouchers {date_from}-{date_to}")

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
        Logs full request and response to tally_traffic.log and console.
        """
        self._log_traffic("📤 [REQUEST SENT TO TALLY]", f"POST {self.tally_url}", xml_payload)
        logger.info(f"\n=======================================================\n📤 [OUTBOUND REQUEST TO TALLY]\nURL: {self.tally_url}\nPAYLOAD:\n{xml_payload}\n=======================================================")
        try:
            req = urllib.request.Request(
                self.tally_url,
                data=xml_payload.encode("utf-8"),
                headers={"Content-Type": "text/xml;charset=utf-8"}
            )
            with self._urlopen(req, timeout=timeout) as resp:
                resp_str = resp.read().decode("utf-8", errors="replace")
                self._log_traffic("📥 [RESPONSE RECEIVED FROM TALLY]", f"STATUS {resp.status}", resp_str)
                logger.info(f"\n=======================================================\n📥 [INBOUND RESPONSE FROM TALLY]\nSTATUS: {resp.status}\nRESPONSE:\n{resp_str}\n=======================================================")
                
                ok, reason = parse_import_result(resp_str)
                return ok, (resp_str if ok else reason)
        except Exception as e:
            err_msg = f"{NETWORK_ERROR_PREFIX}: {str(e)}"
            self._log_traffic("❌ [REQUEST FAILED / ERROR]", f"URL: {self.tally_url}", err_msg)
            logger.error(f"❌ [TALLY COMMUNICATION ERROR]: {err_msg}")
            return False, err_msg

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
                resp_xml = resp.read().decode("utf-8", errors="replace")
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
                resp_xml = resp.read().decode("utf-8", errors="replace")
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
