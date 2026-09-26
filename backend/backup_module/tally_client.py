import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
import re
import logging
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path

from .config import settings

logger = logging.getLogger("backup_module.tally_client")

def is_valid_xml_char(cp: int) -> bool:
    """Validate character code point against XML 1.0 specifications."""
    return (
        cp == 0x9 or
        cp == 0xA or
        cp == 0xD or
        (0x20 <= cp <= 0xD7FF) or
        (0xE000 <= cp <= 0xFFFD) or
        (0x10000 <= cp <= 0x10FFFF)
    )

def sanitize_xml(xml_data: str) -> str:
    """Cleans numeric entity references, invalid control characters, and UDF prefixes."""
    if not xml_data:
        return ""
    
    # 1. Clean invalid numeric/hex references
    entity_pattern = re.compile(r'&#(\d+);|&#[xX]([0-9a-fA-F]+);')
    def entity_repl(match):
        dec_val = match.group(1)
        hex_val = match.group(2)
        try:
            cp = int(dec_val) if dec_val else int(hex_val, 16)
            return match.group(0) if is_valid_xml_char(cp) else ""
        except Exception:
            return ""
    sanitized = entity_pattern.sub(entity_repl, xml_data)

    # 2. Filter raw invalid XML 1.0 characters
    invalid_xml_raw_re = re.compile(
        r'[^\x09\x0A\x0D\x20-\uD7FF\uE000-\uFFFD\U00010000-\U0010FFFF]'
    )
    sanitized = invalid_xml_raw_re.sub("", sanitized)

    # 3. Strip unbound UDF: prefixes
    if "UDF:" in sanitized:
        sanitized = re.sub(r'</?UDF:', lambda m: m.group(0).replace('UDF:', ''), sanitized)

    return sanitized

def escape_xml(text: Any) -> str:
    """Escapes XML special characters."""
    if text is None:
        return ""
    s = str(text)
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
         .replace("'", "&apos;")
    )

class TallyClient:
    """Direct, robust communication client for Tally Prime's XML Server."""

    def __init__(self, tally_url: Optional[str] = None, timeout: Optional[int] = None):
        self.tally_url = (tally_url or settings.TALLY_URL).rstrip("/")
        self.timeout = timeout or settings.TALLY_TIMEOUT

    def post_xml(self, xml_payload: str, custom_timeout: Optional[int] = None) -> Tuple[bool, str]:
        """
        POST XML payload to Tally Prime using UTF-16LE encoding.
        Returns (success: bool, response_or_error_text: str).
        """
        timeout = custom_timeout or self.timeout
        encoded_data = xml_payload.encode('utf-16-le')
        
        req = urllib.request.Request(
            self.tally_url,
            data=encoded_data,
            headers={
                'Content-Type': 'text/xml;charset=utf-16',
                'Content-Length': str(len(encoded_data))
            },
            method='POST'
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw_bytes = response.read()
                try:
                    resp_data = raw_bytes.decode('utf-16')
                except (UnicodeDecodeError, UnicodeError):
                    resp_data = raw_bytes.decode('utf-8', errors='ignore')
                
                resp_data = sanitize_xml(resp_data)
                return True, resp_data
        except TimeoutError:
            err_msg = f"Connection timed out ({timeout}s). Check if Tally Prime is running at {self.tally_url}."
            return False, err_msg
        except urllib.error.URLError as e:
            reason = str(e.reason) if hasattr(e, 'reason') else str(e)
            if "timed out" in reason.lower():
                err_msg = f"Connection timed out ({timeout}s) connecting to Tally Prime at {self.tally_url}."
            else:
                err_msg = f"Cannot connect to Tally Prime at {self.tally_url} ({reason})."
            return False, err_msg
        except Exception as e:
            return False, f"Unexpected error communicating with Tally: {str(e)}"

    def check_health(self) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """
        Checks if Tally Prime XML server is reachable and fetches currently open companies.
        Returns (is_connected, message, list_of_companies).
        """
        companies_query_path = settings.QUERIES_DIR / "companies.xml"
        if not companies_query_path.exists():
            return False, f"Missing query template: {companies_query_path}", []

        try:
            with open(companies_query_path, "r", encoding="utf-8") as f:
                query_xml = f.read()
        except Exception as e:
            return False, f"Error reading companies query template: {e}", []

        success, response_text = self.post_xml(query_xml, custom_timeout=5)
        if not success:
            return False, response_text, []

        companies = []
        try:
            root = ET.fromstring(response_text)
            for c_node in root.findall(".//COMPANY"):
                name = c_node.get("NAME") or c_node.findtext("NAME")
                if not name:
                    continue
                name = name.strip()
                company_info = {
                    "name": name,
                    "guid": c_node.findtext("GUID") or "",
                    "address": c_node.findtext("ADDRESS") or "",
                    "state": c_node.findtext("STATENAME") or c_node.findtext("STATE") or "",
                    "country": c_node.findtext("COUNTRYNAME") or "",
                    "pincode": c_node.findtext("PINCODE") or "",
                    "phone": c_node.findtext("TELEPHONE") or c_node.findtext("BASICCOMPANYPHONE") or "",
                    "mobile": c_node.findtext("MOBILE") or c_node.findtext("BASICCOMPANYMOBILE") or "",
                    "email": c_node.findtext("EMAIL") or c_node.findtext("BASICCOMPANYEMAIL") or "",
                    "website": c_node.findtext("WEBSITE") or c_node.findtext("BASICCOMPANYWEBSITE") or "",
                    "gstin": c_node.findtext("GSTREGISTRATIONNUMBER") or c_node.findtext("GSTIN") or "",
                    "starting_from": c_node.findtext("STARTINGFROM") or c_node.findtext("FINANCIALYEARFROM") or "",
                    "books_from": c_node.findtext("BOOKSFROM") or c_node.findtext("BOOKSBEGINNINGFROM") or ""
                }
                companies.append(company_info)
        except Exception as e:
            logger.warning(f"Error parsing companies XML response: {e}")

        if companies:
            return True, f"Connected to Tally Prime ({len(companies)} company/companies open)", companies
        return True, "Connected to Tally Prime (No company currently open)", []

    def export_entity(self, template_name: str, company_name: str) -> Tuple[bool, str, int]:
        """
        Executes a TDL export query for a given entity template scoped to company_name.
        Returns (success: bool, xml_content_or_error: str, count: int).
        """
        query_file = settings.QUERIES_DIR / f"{template_name}.xml"
        if not query_file.exists():
            return False, f"Query template {template_name}.xml does not exist", 0

        with open(query_file, "r", encoding="utf-8") as f:
            template_content = f.read()

        company_tag = f"<SVCURRENTCOMPANY>{escape_xml(company_name)}</SVCURRENTCOMPANY>"
        query_xml = template_content.replace("{company_tag}", company_tag)

        success, response_text = self.post_xml(query_xml)
        if not success:
            return False, response_text, 0

        # Count exported objects
        count = 0
        try:
            root = ET.fromstring(response_text)
            # Count elements inside TALLYMESSAGE or collection children
            tally_messages = root.findall(".//TALLYMESSAGE")
            if tally_messages:
                count = len(tally_messages)
            else:
                body = root.find(".//BODY")
                if body is not None:
                    # Count direct children of DATA or IMPORTDATA
                    data_container = body.find(".//DATA") or body.find(".//IMPORTDATA")
                    if data_container is not None:
                        count = len(list(data_container))
        except Exception:
            count = 0

        return True, response_text, count

    def import_entity_data(
        self,
        company_name: str,
        messages_xml: str,
        report_name: str = "All Masters"
    ) -> Tuple[bool, str, Dict[str, int]]:
        """
        Imports one or more master/voucher nodes into Tally Prime under the target company.
        Wraps nodes inside <ENVELOPE><HEADER><TALLYREQUEST>Import Data...
        Returns (success, response_text, {created, altered, errors}).
        """
        esc_comp = escape_xml(company_name)
        envelope = f"""<ENVELOPE>
  <HEADER>
    <TALLYREQUEST>Import Data</TALLYREQUEST>
  </HEADER>
  <BODY>
    <IMPORTDATA>
      <REQUESTDESC>
        <REPORTNAME>{report_name}</REPORTNAME>
        <STATICVARIABLES>
          <SVCURRENTCOMPANY>{esc_comp}</SVCURRENTCOMPANY>
        </STATICVARIABLES>
      </REQUESTDESC>
      <REQUESTDATA>
{messages_xml}
      </REQUESTDATA>
    </IMPORTDATA>
  </BODY>
</ENVELOPE>"""

        success, response_text = self.post_xml(envelope)
        stats = {"created": 0, "altered": 0, "errors": 0}
        
        if not success:
            stats["errors"] = 1
            return False, response_text, stats

        # Parse stats from Tally XML response
        try:
            root = ET.fromstring(response_text)
            created_elem = root.find(".//CREATED")
            altered_elem = root.find(".//ALTERED")
            errors_elem = root.find(".//ERRORS")
            
            if created_elem is not None and created_elem.text:
                stats["created"] = int(created_elem.text.strip())
            if altered_elem is not None and altered_elem.text:
                stats["altered"] = int(altered_elem.text.strip())
            if errors_elem is not None and errors_elem.text:
                stats["errors"] = int(errors_elem.text.strip())
            
            # If no explicit CREATED/ALTERED tags, check for error presence
            if stats["errors"] > 0:
                return False, response_text, stats
            return True, response_text, stats
        except Exception as e:
            logger.warning(f"Could not parse Tally import response statistics: {e}")
            return True, response_text, stats

tally_client = TallyClient()
