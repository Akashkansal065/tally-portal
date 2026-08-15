import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
import logging
from typing import Dict, Any, Optional, Tuple, List

logger = logging.getLogger("TallyClient")

class TallyClient:
    def __init__(self, tally_url: str = "http://127.0.0.1:9000", timeout: int = 6):
        self.tally_url = tally_url.rstrip("/") + "/"
        self.timeout = timeout

    def check_health(self) -> Tuple[bool, str]:
        """Pings Tally to check if the XML server is responding."""
        try:
            req = urllib.request.Request(
                self.tally_url,
                data=b"<ENVELOPE><HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Data</TYPE><ID>Company</ID></HEADER><BODY><DESC><STATICVARIABLES><SVEXPORTFORMAT>XML</SVEXPORTFORMAT></STATICVARIABLES></DESC></BODY></ENVELOPE>",
                headers={"Content-Type": "text/xml;charset=utf-8"}
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
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
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
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
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
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

    def export_full_collections(self, company_name: Optional[str] = None, min_alter_id: int = 0) -> List[Tuple[str, str]]:
        """
        Exports master and transaction collections from TallyPrime for inbound sync.
        Supports full dump (min_alter_id=0) or incremental changes (min_alter_id > 0).
        """
        sv_cmp = f"<SVCURRENTCOMPANY>{company_name}</SVCURRENTCOMPANY>" if company_name else ""
        
        collections = [
            ("Groups", "Group", "NAME,PARENT,ALTERID", True),
            ("Ledgers", "Ledger", "NAME,PARENT,ALTERID,OPENINGBALANCE,CLOSINGBALANCE,ADDRESS.LIST,STATENAME,PINCODE,LEDGERPHONE,INCOMETAXNUMBER,PARTYGSTIN,ISBILLWISEON", True),
            ("VoucherTypes", "VoucherType", "NAME,PARENT,ALTERID,NUMBERINGMETHOD,USEZEROENTRIES,ISOPTIONAL,COMMONNARRATION,MULTINARRATION,PRINTAFTERSAVE", True),
            ("StockGroups", "StockGroup", "NAME,PARENT,ALTERID", True),
            ("UOMs", "Unit", "NAME,ORIGINALNAME,DECIMALPLACES", False),
            ("Godowns", "Godown", "NAME,PARENT,ADDRESS.LIST", False),
            ("StockItems", "StockItem", "NAME,PARENT,ALTERID,BASEUNITS,OPENINGBALANCE,OPENINGVALUE,OPENINGRATE,CLOSINGBALANCE,CLOSINGVALUE,CLOSINGRATE,GSTAPPLICABLE,HSNCODE", True),
            ("Vouchers", "Voucher", "GUID,ALTERID,VOUCHERTYPENAME,VOUCHERNUMBER,DATE,NARRATION,PARTYLEDGERNAME,AMOUNT,ALLLEDGERENTRIES.LIST,INVENTORYENTRIES.LIST,ALLINVENTORYENTRIES.LIST,BANKALLOCATIONS.LIST,BILLALLOCATIONS.LIST", True)
        ]
        
        results = []
        for label, obj_type, fetch_fields, supports_alter_filter in collections:
            # If incremental sync, only query collections that support ALTERID filtering or if full sync
            if min_alter_id > 0 and not supports_alter_filter:
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
            try:
                req = urllib.request.Request(
                    self.tally_url,
                    data=xml_req.encode("utf-8"),
                    headers={"Content-Type": "text/xml;charset=utf-8"}
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    resp_xml = resp.read().decode("utf-8", errors="replace")
                    if "<ENVELOPE>" in resp_xml:
                        results.append((label, resp_xml))
            except Exception as e:
                logger.warning(f"Failed to export collection '{label}' from Tally: {e}")

        return results

    def send_xml(self, xml_payload: str) -> Tuple[bool, str]:
        """
        Sends an XML payload (Voucher, Ledger, Master) to TallyPrime and returns (success, response_string).
        """
        try:
            req = urllib.request.Request(
                self.tally_url,
                data=xml_payload.encode("utf-8"),
                headers={"Content-Type": "text/xml;charset=utf-8"}
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                resp_str = resp.read().decode("utf-8", errors="replace")
                success = (
                    "<CREATED>1</CREATED>" in resp_str or 
                    "<ALTERED>1</ALTERED>" in resp_str or 
                    "<DELETED>1</DELETED>" in resp_str or 
                    "<STATUS>1</STATUS>" in resp_str or
                    "<IGNORED>1</IGNORED>" in resp_str
                )
                return success, resp_str
        except Exception as e:
            return False, str(e)
