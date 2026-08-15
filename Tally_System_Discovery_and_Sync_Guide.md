# Tally System Discovery & Synchronization Guide

This guide documents the automated mechanisms for discovering Tally host system properties, resolving internal file paths (such as `tallysave.tsf` and `tally.ini`), and the architecture of the **Desktop Sync Agent**.

---

## 1. Automated Tally Host System Discovery via XML API

TallyPrime exposes internal system formulas via TDL that can be queried over its HTTP XML server (Port 9000) without requiring administrative operator intervention.

### A. Discovery XML Request Payload

```xml
<ENVELOPE>
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
</ENVELOPE>
```

### B. Complete cURL Execution Commands

#### 1. Direct Inline cURL Command (macOS / Linux / WSL):
```bash
curl -X POST "http://192.168.71.128:9000/" \
  -H "Content-Type: text/xml;charset=utf-8" \
  -d '<ENVELOPE><HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Collection</TYPE><ID>SystemInfoCollection</ID></HEADER><BODY><DESC><STATICVARIABLES><SVEXPORTFORMAT>XML</SVEXPORTFORMAT></STATICVARIABLES><TDL><TDLMESSAGE><COLLECTION NAME="SystemInfoCollection"><TYPE>Company</TYPE><COMPUTE>AppPath : $$ApplicationPath</COMPUTE><COMPUTE>CmpName : $Name</COMPUTE><COMPUTE>DataPath : $$DataPath</COMPUTE><COMPUTE>SysRelease : $$Release</COMPUTE><COMPUTE>SysVersion : $$Version</COMPUTE></COLLECTION></TDLMESSAGE></TDL></DESC></BODY></ENVELOPE>'
```

#### 2. File-Based cURL Command:
```bash
# 1. Save payload to file
cat << 'EOF' > system_discovery.xml
<ENVELOPE>
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
</ENVELOPE>
EOF

# 2. Execute cURL
curl -X POST "http://192.168.71.128:9000/" \
  -H "Content-Type: text/xml;charset=utf-8" \
  -d @system_discovery.xml
```

#### 3. Windows PowerShell Command:
```powershell
$xmlPayload = @"
<ENVELOPE>
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
</ENVELOPE>
"@

Invoke-RestMethod -Uri "http://192.168.71.128:9000/" -Method Post -Body $xmlPayload -ContentType "text/xml;charset=utf-8"
```

### C. Live TallyPrime Response

```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <VOUCHERTYPE>3</VOUCHERTYPE>
   </CMPINFO>
  </DESC>
  <DATA>
   <COLLECTION>
    <COMPANY NAME="Bhrama Enterprises" RESERVEDNAME="">
     <CMPNAME TYPE="String">Bhrama Enterprises</CMPNAME>
     <APPPATH TYPE="String">C:\Users\Akash\Downloads\integration-setup\integration-setup</APPPATH>
    </COMPANY>
   </COLLECTION>
  </DATA>
 </BODY>
</ENVELOPE>
```

### C. Host Path Resolution Matrix

| Discovered Parameter | Resolved Host Location | Purpose |
| :--- | :--- | :--- |
| **`APPPATH`** | `C:\Users\Akash\Downloads\integration-setup\integration-setup` | Tally executable directory where `tally.exe`, `tallysave.tsf`, and `tally.ini` reside. |
| **`tallysave.tsf`** | `C:\Users\Akash\Downloads\integration-setup\integration-setup\tallysave.tsf` | Binary configuration store holding workstation-specific F12 prompt settings and session state. |
| **`tally.ini`** | `C:\Users\Akash\Downloads\integration-setup\integration-setup\tally.ini` | Core startup settings (ODBC port, XML server port `9000`, license server configuration). |
| **`DataPath`** | `C:\Users\Akash\Downloads\integration-setup\integration-setup\Data` | Location of numerical company data folders (e.g. `10000`, `10001`). |

---

## 2. What is a Desktop Sync Agent?

A **Desktop Sync Agent** (or Tally Connector) is a lightweight background application (built in Python, Go, or Node.js) that runs on the **Windows host computer or virtual machine where Tally is installed**.

```
┌─────────────────────────────────────────────────────────────┐
│                    Windows PC / Server                      │
│                                                             │
│  ┌──────────────┐         HTTP XML         ┌─────────────┐  │
│  │  TallyPrime  │ ◄──────────────────────► │ Desktop     │  │
│  │ (Port 9000)  │   (Localhost:9000)       │ Sync Agent  │  │
│  └──────────────┘                          └──────┬──────┘  │
│         ▲                                         │         │
│         │ (Reads tallysave.tsf, tally.ini)        │         │
│         └─────────────────────────────────────────┘         │
└───────────────────────────────────────────────────┼─────────┘
                                                    │
                                   Secure Outbound  │
                                   HTTPS / WSS      │
                                                    ▼
                                    ┌───────────────────────┐
                                    │    MyTally Cloud      │
                                    │    Web Application    │
                                    │ (FastAPI + Next.js)   │
                                    └───────────────────────┘
```

### Why is a Desktop Sync Agent Useful?

1. **Firewall & NAT Traversal (No Static IP / Port Forwarding Needed)**:
   - When MyTally is hosted on cloud servers (e.g. AWS, Vercel, VPS), it cannot reach your local office PC behind a private WiFi router (`192.168.x.x`).
   - The Desktop Sync Agent makes a **secure outbound connection** to the cloud server, eliminating the need for complex VPNs or open router ports.

2. **Direct Local File Access (`tallysave.tsf`, `tally.log`, `tally.ini`)**:
   - Because the Agent runs on the same Windows PC, it can directly read and monitor local files that Tally’s HTTP XML server does not expose over the network.

3. **Auto-Reconnection & Offline Buffering**:
   - If the internet disconnects, the Agent queues all outgoing transactions locally and pushes them to Tally as soon as the connection is restored.

4. **Background Service Execution**:
   - Runs silently in the Windows system tray as a Windows Service, launching automatically on system startup.

---

## 3. Comparison: Direct LAN Connection vs. Desktop Sync Agent

| Feature | Direct LAN Connection (Current) | Desktop Sync Agent (Enterprise) |
| :--- | :--- | :--- |
| **Network Setup** | Backend and Tally must be on the same WiFi/LAN or VPN (e.g. `192.168.71.128:9000`). | Works anywhere worldwide via secure outbound HTTPS/WSS. |
| **Router Configuration** | Requires static IP or port forwarding if hosted on cloud. | Zero router configuration / firewall rules needed. |
| **Host File Access** | Limited to XML API data responses. | Direct access to `tallysave.tsf`, `tally.ini`, and log files. |
| **Deployment Complexity**| Extremely simple for local development. | Requires running a small helper executable on the Windows PC. |
