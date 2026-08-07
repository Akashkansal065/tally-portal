import urllib.request
import urllib.error
import json
import time
import sys
import os
import argparse

def load_env_file(filepath=None):
    """Loads key-value pairs from a local .env file into os.environ if the file exists."""
    if filepath is None:
        # First try parent directory of the script (backend/.env), then the current working directory
        parent_env = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
        if os.path.exists(parent_env):
            filepath = parent_env
        else:
            filepath = ".env"
            
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    # Ignore empty lines and comments
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, val = line.split("=", 1)
                        key = key.strip()
                        val = val.strip().strip("'\"")
                        os.environ[key] = val
        except Exception as e:
            print(f"Warning: Could not read .env file: {str(e)}")

# Load local .env if present
load_env_file()

# Configuration (overridden by environment variables or command-line arguments)
TALLY_URL = os.environ.get("TALLY_URL")
ERP_URL = os.environ.get("ERP_URL")

def get_erp_token(email, password):
    login_url = f"{ERP_URL}/auth/login"
    data = json.dumps({"email": email, "password": password}).encode('utf-8')
    req = urllib.request.Request(
        login_url, 
        data=data, 
        headers={'Content-Type': 'application/json'}, 
        method='POST'
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            res = json.loads(response.read().decode('utf-8'))
            return res.get("access_token")
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode('utf-8')
            err_json = json.loads(err_body)
            detail = err_json.get("detail", err_body)
            print(f"Failed to login to ERP: HTTP Error {e.code}: {e.reason} - {detail}")
        except Exception:
            print(f"Failed to login to ERP: HTTP Error {e.code}: {e.reason}")
        return None
    except Exception as e:
        print(f"Failed to login to ERP: {str(e)}")
        return None

def post_to_tally(xml_payload):
    # Tally Prime natively uses UTF-16LE encoding for XML communication
    encoded_data = xml_payload.encode('utf-16-le')
    req = urllib.request.Request(
        TALLY_URL,
        data=encoded_data,
        headers={
            'Content-Type': 'text/xml;charset=utf-16',
            'Content-Length': str(len(encoded_data))
        },
        method='POST'
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as response:
            raw_bytes = response.read()
            # Decode response as UTF-16 (Tally responds in UTF-16)
            try:
                resp_data = raw_bytes.decode('utf-16')
            except (UnicodeDecodeError, UnicodeError):
                resp_data = raw_bytes.decode('utf-8', errors='ignore')
            # Check for success indicators in Tally XML response
            if "<CREATED>1</CREATED>" in resp_data or "<UPDATED>1</UPDATED>" in resp_data or "<ERRORS>0</ERRORS>" in resp_data:
                return True, resp_data
            return False, resp_data
    except TimeoutError as e:
        msg = f"Connection timed out. Please ensure Tally Prime is running, XML Server is enabled on port {TALLY_URL.split(':')[-1]}, or try using '127.0.0.1' instead of 'localhost'."
        return False, msg
    except urllib.error.URLError as e:
        reason = str(e.reason) if hasattr(e, 'reason') else str(e)
        if "timed out" in reason.lower():
            msg = f"Connection timed out. Please ensure Tally Prime is running, XML Server is enabled on port {TALLY_URL.split(':')[-1]}, or try using '127.0.0.1' instead of 'localhost'."
        else:
            msg = f"Connection error: {reason}. Please ensure Tally Prime is running, XML Server is enabled on port {TALLY_URL.split(':')[-1]}, and firewall/antivirus is not blocking the connection."
        return False, msg
    except Exception as e:
        return False, str(e)

def run_sync_cycle(token):
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    # ---------------------------------------------
    # PHASE 1: Outbound Sync (ERP -> Tally)
    # ---------------------------------------------
    queue_url = f"{ERP_URL}/sync/outbound-queue"
    req = urllib.request.Request(queue_url, headers=headers, method='GET')
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            queue = json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        print(f"Error fetching sync queue from ERP: {str(e)}")
        if e.code == 401:
            raise e
        return
    except Exception as e:
        print(f"Error fetching sync queue from ERP: {str(e)}")
        return
        
    if queue:
        print(f"Found {len(queue)} outbound sync items pending.")
        successful_ids = []
        for item in queue:
            sync_id = item["sync_id"]
            xml_payload = item["xml_payload"]
            
            success, response = post_to_tally(xml_payload)
            if success:
                print(f"Successfully synced sync_id {sync_id} to Tally.")
                successful_ids.append(sync_id)
            else:
                print(f"Failed to sync sync_id {sync_id} to Tally. Error/Response: {response}")
                
        if successful_ids:
            ack_url = f"{ERP_URL}/sync/acknowledge"
            ack_req = urllib.request.Request(
                ack_url,
                data=json.dumps(successful_ids).encode('utf-8'),
                headers=headers,
                method='POST'
            )
            try:
                with urllib.request.urlopen(ack_req, timeout=10) as response:
                    print(f"Acknowledged {len(successful_ids)} items on ERP.")
            except Exception as e:
                print(f"Error acknowledging sync items on ERP: {str(e)}")

    # ---------------------------------------------
    # PHASE 2: Inbound Sync (Tally -> ERP) with ALTERID
    # ---------------------------------------------
    # Step A: Get last alter IDs from ERP
    alter_url = f"{ERP_URL}/sync/last-alter-id"
    req = urllib.request.Request(alter_url, headers=headers, method='GET')
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            last_alters = json.loads(response.read().decode('utf-8'))
            last_ledger_alter = last_alters.get("last_ledger_alter_id", 0)
            last_voucher_alter = last_alters.get("last_voucher_alter_id", 0)
            last_ledger_alter_id = last_alters.get("last_ledger_alter_id", 0)
            last_voucher_alter_id = last_alters.get("last_voucher_alter_id", 0)
    except Exception as e:
        print(f"Error fetching last alter IDs from ERP: {str(e)}")
        return

    print(f"Current ERP state - Last Ledger AlterID: {last_ledger_alter_id}, Last Voucher AlterID: {last_voucher_alter_id}")

    # Step B: Fetch Companies first to auto-provision and discover all open companies
    company_query_xml = """<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>ListofCompanies</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="ListofCompanies">
            <TYPE>Company</TYPE>
            <FETCH>NAME,GUID,ADDRESS,STATENAME,COUNTRYNAME,PINCODE,TELEPHONE,BASICCOMPANYPHONE,TELEPHONENUMBER,MOBILE,BASICCOMPANYMOBILE,MOBILENUMBER,EMAIL,BASICCOMPANYEMAIL,EMAILID,WEBSITE,BASICCOMPANYWEBSITE,BOOKSFROM,BOOKSBEGINNINGFROM,STARTINGFROM,FINANCIALYEARFROM,GSTREGISTRATIONNUMBER,GSTIN,PARTYGSTIN</FETCH>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>"""

    target_companies = []
    print("  [Companies] Fetching open companies from Tally...")
    try:
        encoded_data = company_query_xml.encode('utf-16-le')
        comp_req = urllib.request.Request(
            TALLY_URL,
            data=encoded_data,
            headers={'Content-Type': 'text/xml;charset=utf-16', 'Content-Length': str(len(encoded_data))},
            method='POST'
        )
        with urllib.request.urlopen(comp_req, timeout=300) as response:
            raw_bytes = response.read()
            try:
                comp_xml = raw_bytes.decode('utf-16')
            except Exception:
                comp_xml = raw_bytes.decode('utf-8', errors='ignore')
                
            if comp_xml and "<COMPANY" in comp_xml:
                import xml.etree.ElementTree as ET
                try:
                    c_root = ET.fromstring(comp_xml)
                    for c_node in c_root.findall(".//COMPANY"):
                        c_name = c_node.get("NAME") or c_node.findtext("NAME")
                        if c_name:
                            target_companies.append(c_name.strip())
                            
                            c_phone = c_node.findtext("TELEPHONE") or c_node.findtext("BASICCOMPANYPHONE") or ""
                            c_mobile = c_node.findtext("MOBILE") or c_node.findtext("BASICCOMPANYMOBILE") or ""
                            c_email = c_node.findtext("EMAIL") or c_node.findtext("BASICCOMPANYEMAIL") or ""
                            c_site = c_node.findtext("WEBSITE") or c_node.findtext("BASICCOMPANYWEBSITE") or ""
                            c_gst = c_node.findtext("GSTREGISTRATIONNUMBER") or c_node.findtext("GSTIN") or ""
                            c_state = c_node.findtext("STATENAME") or c_node.findtext("STATE") or ""
                            
                            print(f"  🏢 [Tally Company Profile] '{c_name.strip()}' | State: '{c_state}' | Phone: '{c_phone}' | Mobile: '{c_mobile}' | Email: '{c_email}' | Website: '{c_site}' | GSTIN: '{c_gst}'")
                except Exception:
                    pass
                
                # Post company profiles payload to ERP so it auto-provisions missing companies
                print(f"  [Companies] Discovered {len(target_companies)} companies: {target_companies}")
                print(f"  [Companies] Posting company profiles to ERP...")
                post_data = comp_xml.encode('utf-8')
                inbound_req = urllib.request.Request(
                    f"{ERP_URL}/sync/inbound",
                    data=post_data,
                    headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/xml'},
                    method='POST'
                )
                with urllib.request.urlopen(inbound_req, timeout=30) as erp_res:
                    print(f"  [Companies] ERP Provisioned Response: {erp_res.read().decode('utf-8')}")
    except Exception as e:
        print(f"  [Companies] Warning: Could not fetch company list ({str(e)})")

    if not target_companies:
        target_companies = [None]

    # Step C: Execute queries per company
    for company_name in target_companies:
        sv_company = f"<SVCURRENTCOMPANY>{company_name}</SVCURRENTCOMPANY>" if company_name else ""
        comp_label = f"[{company_name}] " if company_name else ""
        
        queries = {
            f"{comp_label}Groups": f"""<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>AllAlteredGroups</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
        {sv_company}
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="AllAlteredGroups">
            <TYPE>Group</TYPE>
            <FETCH>NAME,PARENT</FETCH>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>""",
            f"{comp_label}Ledgers": f"""<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>IncrementalLedgers</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
        {sv_company}
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="IncrementalLedgers">
            <TYPE>Ledger</TYPE>
            <FETCH>GUID,ALTERID,NAME,PARENT,OPENINGBALANCE,GSTIN,LWLEDADHARNOSTORE,LEDGSTREGDETAILS.LIST,LEDMAILINGDETAILS.LIST</FETCH>
            <FILTERS>AlteredFilter</FILTERS>
          </COLLECTION>
          <SYSTEM TYPE="Formulae" NAME="AlteredFilter">
            $ALTERID &gt; {last_ledger_alter_id}
          </SYSTEM>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>""",
            f"{comp_label}Vouchers": f"""<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>IncrementalVouchers</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
        <SVFROMDATE TYPE="Date">20000101</SVFROMDATE>
        <SVTODATE TYPE="Date">20991231</SVTODATE>
        {sv_company}
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="IncrementalVouchers">
            <TYPE>Voucher</TYPE>
            <FETCH>GUID,ALTERID,VOUCHERTYPENAME,VOUCHERNUMBER,DATE,NARRATION,PARTYLEDGERNAME,AMOUNT,ALLLEDGERENTRIES.LIST,INVENTORYENTRIES.LIST,ALLINVENTORYENTRIES.LIST</FETCH>
            <FILTERS>AlteredVoucherFilter</FILTERS>
          </COLLECTION>
          <SYSTEM TYPE="Formulae" NAME="AlteredVoucherFilter">
            $ALTERID &gt; {last_voucher_alter_id}
          </SYSTEM>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>""",
            f"{comp_label}StockGroups": f"""<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>AllStockGroups</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
        {sv_company}
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="AllStockGroups">
            <TYPE>StockGroup</TYPE>
            <FETCH>NAME,PARENT</FETCH>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>""",
            f"{comp_label}Units": f"""<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>AllUnits</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
        {sv_company}
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="AllUnits">
            <TYPE>Unit</TYPE>
            <FETCH>NAME,SYMBOL,DECIMALPLACES</FETCH>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>""",
            f"{comp_label}Godowns": f"""<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>AllGodowns</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
        {sv_company}
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="AllGodowns">
            <TYPE>Godown</TYPE>
            <FETCH>NAME,ADDRESS</FETCH>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>""",
            f"{comp_label}StockCategories": f"""<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>AllStockCategories</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
        {sv_company}
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="AllStockCategories">
            <TYPE>StockCategory</TYPE>
            <FETCH>NAME,PARENT</FETCH>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>""",
            f"{comp_label}StockItems": f"""<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>IncrementalStockItems</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
        {sv_company}
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="IncrementalStockItems">
            <TYPE>StockItem</TYPE>
            <FETCH>GUID,ALTERID,NAME,PARENT,CATEGORY,BASEUNITS,OPENINGBALANCE,OPENINGVALUE,INFGSTHSNCODE,INFGSTIGSTRATE</FETCH>
            <FILTERS>AlteredStockItemFilter</FILTERS>
          </COLLECTION>
          <SYSTEM TYPE="Formulae" NAME="AlteredStockItemFilter">
            $ALTERID &gt; 0
          </SYSTEM>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>"""
        }

        # Step C: Execute queries for this company
        for name, xml_payload in queries.items():
            import time as _time
            step_start = _time.time()
            try:
                # 1. Encode request as UTF-16LE for Tally Prime
                encoded_data = xml_payload.encode('utf-16-le')
                tally_req = urllib.request.Request(
                    TALLY_URL,
                    data=encoded_data,
                    headers={
                        'Content-Type': 'text/xml;charset=utf-16',
                        'Content-Length': str(len(encoded_data))
                    },
                    method='POST'
                )
                
                # 2. Fetch XML from Tally (600s timeout for large payloads like Vouchers/StockItems over tunnels)
                print(f"  [{name}] Fetching from Tally ({TALLY_URL})...")
                fetch_start = _time.time()
                with urllib.request.urlopen(tally_req, timeout=600) as response:
                    raw_bytes = response.read()
                    fetch_elapsed = _time.time() - fetch_start
                    print(f"  [{name}] Received {len(raw_bytes):,} bytes from Tally in {fetch_elapsed:.1f}s")
                    
                    # Decode response from UTF-16 (Tally responds in UTF-16)
                    try:
                        tally_xml_response = raw_bytes.decode('utf-16')
                    except (UnicodeDecodeError, UnicodeError):
                        tally_xml_response = raw_bytes.decode('utf-8', errors='ignore')
                    
                    # If Tally returns an empty envelope or error
                    if not tally_xml_response or "<ENVELOPE>" not in tally_xml_response:
                        print(f"  [{name}] Skipped: Tally returned empty/invalid response ({len(tally_xml_response)} chars)")
                        continue
                    
                    # 3. Post this XML payload to ERP inbound endpoint
                    post_data = tally_xml_response.encode('utf-8')
                    print(f"  [{name}] Posting {len(post_data):,} bytes to ERP ({ERP_URL}/sync/inbound)...")
                    inbound_url = f"{ERP_URL}/sync/inbound"
                    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/xml'}
                    if company_name:
                        headers['X-Company-Name'] = company_name

                    inbound_req = urllib.request.Request(
                        inbound_url,
                        data=post_data,
                        headers=headers,
                        method='POST'
                    )
                    post_start = _time.time()
                    with urllib.request.urlopen(inbound_req, timeout=600) as erp_response:
                        result = json.loads(erp_response.read().decode('utf-8'))
                        post_elapsed = _time.time() - post_start
                        total_elapsed = _time.time() - step_start
                        print(f"  [{name}] ERP responded in {post_elapsed:.1f}s (total: {total_elapsed:.1f}s): {result}")
            except TimeoutError as e:
                elapsed = _time.time() - step_start
                print(f"  [{name}] TIMEOUT after {elapsed:.1f}s - Tally or ERP did not respond in time")
            except urllib.error.HTTPError as e:
                elapsed = _time.time() - step_start
                try:
                    err_body = e.read().decode('utf-8')
                    print(f"  [{name}] HTTP ERROR {e.code} after {elapsed:.1f}s: {err_body[:200]}")
                except Exception:
                    print(f"  [{name}] HTTP ERROR {e.code} {e.reason} after {elapsed:.1f}s")
            except urllib.error.URLError as e:
                elapsed = _time.time() - step_start
                reason = str(e.reason) if hasattr(e, 'reason') else str(e)
                if "timed out" in reason.lower():
                    print(f"  [{name}] TIMEOUT (URLError) after {elapsed:.1f}s: {reason}")
                else:
                    print(f"  [{name}] CONNECTION ERROR after {elapsed:.1f}s: {reason}")
            except Exception as e:
                elapsed = _time.time() - step_start
                print(f"  [{name}] UNEXPECTED ERROR after {elapsed:.1f}s: {type(e).__name__}: {str(e)}")

def main():
    global TALLY_URL, ERP_URL
    
    parser = argparse.ArgumentParser(description="Bidirectional Tally Sync Daemon")
    parser.add_argument("--tally-url", help="Local Tally Prime URL (e.g. http://127.0.0.1:9000)")
    parser.add_argument("--erp-url", help="ERP Web Server URL (e.g. https://my-erp-domain.com)")
    parser.add_argument("--email", help="ERP Login Email")
    parser.add_argument("--password", help="ERP Login Password")
    parser.add_argument("--frequency", type=int, help="Polling frequency in seconds (default: 120)")
    args = parser.parse_args()
    
    # Override defaults with CLI arguments or environment variables
    if args.tally_url:
        TALLY_URL = args.tally_url
    if args.erp_url:
        ERP_URL = args.erp_url
        
    if not TALLY_URL:
        print("Fatal: TALLY_URL is not set in environment or .env file. Exiting.")
        sys.exit(1)
    if not ERP_URL:
        print("Fatal: ERP_URL is not set in environment or .env file. Exiting.")
        sys.exit(1)
        
    email = args.email or os.environ.get("ERP_EMAIL")
    password = args.password or os.environ.get("ERP_PASSWORD")
    frequency = args.frequency or int(os.environ.get("SYNC_FREQUENCY", "120"))
    
    if not email:
        print("Fatal: ERP_EMAIL is not set in environment or .env file. Exiting.")
        sys.exit(1)
    if not password:
        print("Fatal: ERP_PASSWORD is not set in environment or .env file. Exiting.")
        sys.exit(1)
    
    print("====================================================")
    print("Starting Bidirectional Tally Sync Daemon")
    print(f"Local Tally Server: {TALLY_URL}")
    print(f"ERP Web Server: {ERP_URL}")
    print(f"ERP Login Email: {email}")
    print(f"Polling frequency: {frequency} seconds")
    print("====================================================")
    
    # Authenticate
    token = get_erp_token(email, password)
    if not token:
        print("Fatal: Could not authenticate sync daemon against ERP. Exiting.")
        sys.exit(1)
        
    print("Daemon authenticated successfully. Commencing sync loop...")
    
    while True:
        try:
            print(f"\n--- Sync Cycle Started at {time.strftime('%Y-%m-%d %H:%M:%S')} ---")
            run_sync_cycle(token)
            print("--- Sync Cycle Completed ---")
        except urllib.error.HTTPError as e:
            if e.code == 401:
                print("Session token expired or revoked (401 Unauthorized). Attempting to re-authenticate...")
                new_token = get_erp_token(email, password)
                if new_token:
                    token = new_token
                    print("Re-authenticated successfully. Retrying cycle...")
                    try:
                        run_sync_cycle(token)
                    except Exception as err:
                        print(f"Retry failed: {str(err)}")
                else:
                    print("Re-authentication failed. Will retry in next cycle.")
            else:
                print(f"HTTP Error in sync cycle: {e.code} {e.reason}")
        except KeyboardInterrupt:
            print("\nSync Daemon stopped by user. Exiting.")
            break
        except Exception as e:
            print(f"Unexpected error in sync loop: {str(e)}")
            
        time.sleep(frequency)

if __name__ == "__main__":
    main()
