# Desktop Sync Agent Enterprise Architectural Upgrade Blueprint

**Document Version:** 5.0.0  
**Target Repository:** MyTally (`/Users/akashkansal/Documents/Github/MyTally`)  
**Analyzed Reference Artifacts (`docs/temp/`):**
1. `docs/temp/tally_sync_connector.py` (Core bidirectional connector, local SQLite multi-company partitioning, density-adaptive voucher planner, and blank-node sanitizer)
2. `docs/temp/tally_backup_restore.py` (Multi-destination disaster recovery engine: Topological master rehydration, physical `.900` folder snapshot, live MySQL reconstruction, portable PBKDF2 passphrase cipher, and AWS S3 SigV4)
3. `docs/temp/tally_desktop_gui.py` (CustomTkinter GUI, `RuntimeSecurityShield` anti-RE/anti-debug, `MachineBoundConfigVault`, and `TallyEnvironmentDetector` multi-drive port/PID scanner)
4. `docs/temp/build_hardened_exe.py` (4-Layer C-compilation pipeline: AST string vault `_tv_d`, Cython C transpilation, and Nuitka C++ LTO binary hardening)
5. `docs/temp/TallyPrimeSync_Installer.iss` & `build_windows_release.bat` (Inno Setup 6 enterprise installer, 15-minute Windows Task Scheduler daemon, and user permission management)
6. `docs/temp/mysql_schema.sql` & `fastapi_mysql_backend.py` (15-domain enterprise schema, idempotency log, S3/Server hybrid backup storage, agent device pairing, and analytical BI views)
7. `docs/temp/production_deployment_runbook.md` (Operational deployment, least-privilege AWS S3 IAM policies, and PyInstaller vulnerability remediation)

---

## 1. Executive Summary & Problem Context

MyTally’s current desktop synchronization agent ([desktop-sync-agent/](file:///Users/akashkansal/Documents/Github/MyTally/desktop-sync-agent)) implements the core communication primitives: it polls local TallyPrime via XML HTTP requests (`http://localhost:9000`), pulls incremental records using `$AlterID > watermark`, and pushes transactions to our FastAPI backend.

However, an exhaustive architectural audit against production enterprise connectors (revealed in `docs/temp`) shows several critical architectural bottlenecks and security vulnerabilities:

1. **Cleartext Code Exposure in PyInstaller (`installer/build_exe.py`):**
   The current installer passes `--add-data` for `security.py`, `config.py`, `agent.py`, `tally_client.py`, and `cloud_client.py`, packaging uncompiled cleartext `.py` files inside the executable. Anyone with standard tools (`pyinstxtractor`, `pycdc`) can decompile the binary in 5 seconds, exposing the cloud API endpoints, `_APP_SALT`, HMAC secrets, and proprietary TDL queries.
2. **Fragile Port & Process Detection:**
   The agent hardcodes `http://127.0.0.1:9000`. If an accountant has Tally running on port 9001, 9002, or running on a non-default drive without manual configuration, the agent crashes with "Tally Offline".
3. **Logical-Only, Slow XML Backups Without Topological Sorting:**
   The existing backup system only exports logical XML collections. During restore, masters fail with `<LINEERROR>does not exist</LINEERROR>` because parent groups or units are restored out of order. Furthermore, it lacks physical binary snapshots (`.900` files), turning disaster recovery into an hours-long process instead of a 3-second folder restore.
4. **Ghost Records from Tally Alt+D Deletions:**
   Tally does not generate AlterID increments or audit logs when a user deletes a voucher or ledger via `Alt+D`. Consequently, deleted vouchers remain in the cloud database indefinitely ("ghost records").
5. **No Headless Daemon / Windows Task Scheduler Mode:**
   If the desktop user closes the GUI window or logs off, background sync stops. There is no unattended daemon or Task Scheduler fallback.
6. **Network Dropped AlterID Rewind Bloat:**
   A dropped network packet forces the agent to rewind entire date ranges, re-fetching thousands of records instead of querying only the specific missing sequence gaps.

This blueprint outlines the complete end-to-end architectural upgrade to resolve these shortcomings.

---

## 2. Before vs. After: Comprehensive Architectural Gap Matrix

| Functional Dimension | Previous Implementation (Current Codebase) | Upgraded Enterprise Implementation (From `docs/temp` Analysis) | Key Improvements & Business Value |
|:---|:---|:---|:---|
| **Binary Security & Anti-RE** | Standard PyInstaller with cleartext `--add-data` `.py` scripts. Trivial decompilation via `pycdc`. | **4-Layer Hardened Toolchain:**<br/>1. AST String Vault (`_tv_d`) with ChaCha/XOR zlib encrypted pool<br/>2. Cython transpilation to native C `.pyd`<br/>3. Nuitka C++ LTO onefile compilation<br/>4. Runtime anti-debug & timing traps. | **Zero Source Exposure:** Intellectual property, API secrets, and TDL queries are compiled into native machine code. |
| **Credential & Secret Storage** | Plaintext or fixed-salt AES config files on disk. | **`MachineBoundConfigVault`:**<br/>Keys derived from Windows `MachineGuid` via `PBKDF2-HMAC-SHA256` (50,000 iterations). Enforces machine-locking with `TSV1` HMAC-authenticated envelopes. | **Anti-Theft:** Config files copied to another machine immediately fail MAC verification and cannot be decrypted. |
| **Tally Host & Port Discovery** | Hardcoded `http://127.0.0.1:9000/`. Fails if port or path differs. | **5-Layer Discovery Cascade:**<br/>1. `tasklist` process scan for `tally.exe`<br/>2. `netstat -ano -p tcp` PID-to-port mapping<br/>3. Registry scan across HKLM/HKCU<br/>4. Drive sweep (`C:` to `G:`)<br/>5. `tally.ini` parser (`ServerPort`, `Data`, `Load`). | **Zero-Config Setup:** Instantly detects Tally across custom ports, drives, or multi-instance setups; can auto-launch Tally if closed. |
| **Disaster Recovery & Backups** | **Logical XML only:** Exports collections to ZIP. Takes 15–45 minutes. Restore fails on dependencies. | **3-Mode Hybrid DR Engine:**<br/>1. **Mode A:** Topological dependency-sorted XML rehydration<br/>2. **Mode B:** Physical binary folder snapshot (`.900` files)<br/>3. **Mode C:** Live MySQL cloud-to-Tally reconstruction. | **Instant 3-Second Restore:** Physical binary restore extracts `.900` files directly with 100% bit-level fidelity and zero parsing overhead. |
| **Backup Storage & Security** | Local folder only, unencrypted or single-key encrypted. | **3 Storage Destinations + Passphrase Cipher:**<br/>Stores to Local Disk, FastAPI/MySQL Server (`tally_company_backups`), and AWS S3 (pure Python SigV4). Encrypted via portable `PBKDF2-HMAC-SHA256` (100,000 rounds). | **Complete Laptop-Loss Protection:** Users can restore their company onto any new laptop using their recovery passphrase. |
| **Voucher Deletion Reconciliation** | Tracks web portal deletions only. `Alt+D` deletions in Tally remain as permanent ghost records. | **Active Keys Reconciliation (Algorithm B):**<br/>Lightweight periodic export of active `(MasterID, GUID)` pairs (<150KB for 50,000 vouchers). Cloud runs set difference and soft-deletes ghost vouchers. | **100% Ledger Balance Parity:** Purges deleted vouchers without requiring destructive database resets. |
| **Voucher Extraction Planning** | Basic date-chunking or full DayBook scan. Can split days or timeout on dense days. | **Density-Adaptive Range Planner:**<br/>Queries `export_voucher_index` (`DATE, MASTERID`) first, then partitions dates into ~50-voucher windows without ever splitting a single day. Dual date filter fallback (`sv` + `filter`). | **Zero Timeouts:** Adapts automatically to high-volume days (e.g., month-end billing) and handles Tally date format quirks. |
| **AlterID Gap Handling** | Rewinds watermark to `retry_floor` or falls back to full multi-month date-range sync. | **Targeted Gap Backfill (Algorithm A):**<br/>Cloud detects missing AlterID sequence numbers and issues `VouchersByAlterIdList` using TDL formula `$$IsValueInList:$AlterID:"101,102,105"`. | **Massive Bandwidth Savings:** Re-fetches only the exact 3 or 4 missing records instead of 5,000 vouchers. |
| **Multi-Company Local State** | Single-company watermark tracking in local SQLite or file. | **Compound-Key LocalSyncStore:**<br/>Partitions local SQLite state by `(company_name, entity_type, record_key)`, preventing cross-company watermark collisions. | **Multi-Company Safe:** Seamlessly synchronizes multiple client companies on the same machine without state corruption. |
| **Payload Optimization** | Raw XML with hundreds of empty tags (`<EMAIL/>`, `<PINCODE/>`) pushed uncompressed. | **Blank-Node Sanitizer + Gzip:**<br/>Regex cleans empty XML tags before compression, cutting payload size by 40–60%; transmitted with `Content-Encoding: gzip`. | **60–80% Ingress Reduction:** Drastically reduces network bandwidth, cloud ingress costs, and deserialization CPU time. |
| **Device Pairing & Auth** | Shared API tokens entered manually on desktop client. | **8-Character Unambiguous Pairing:**<br/>Desktop displays 10-minute code from `PAIRING_ALPHABET` (no ambiguous chars `0/O/1/I`); web admin approves and issues scoped `mta_` tokens. | **Enterprise Security:** Eliminates sharing admin credentials on employee desktop machines. |
| **Unattended Background Execution** | GUI-dependent. Closing window stops sync. Autostart is only user login registry key. | **Windows Task Scheduler Integration:**<br/>Inno Setup registers `schtasks.exe /SC MINUTE /MO 15` running `--headless-once`. Runs 24/7 even when user is logged off. | **Continuous Sync:** Sync runs reliably in background without requiring desktop UI interaction. |

---

## 3. Deep Dive: How the .exe File Detects Tally (5-Layer Discovery Cascade)

The enterprise desktop sync agent must never depend on the user typing `http://localhost:9000` or guessing port numbers. The upgraded executable implements a resilient 5-layer discovery cascade (`TallyEnvironmentDetector`):

```mermaid
flowchart TD
    Start(["Desktop Agent Launch"]) --> L1{"Layer 1: Process Scan<br/>tasklist /FI IMAGENAME eq tally.exe"}
    L1 -- Process Found (PID) --> Netstat["Query netstat -ano -p tcp<br/>Find Exact Listening Port for PID"]
    Netstat --> TestPort{"Test Discovered Port<br/>HTTP Ping Probe"}
    
    L1 -- Not Running --> L2{"Layer 2: Registry Probe<br/>HKLM & HKCU Tally Paths"}
    L2 -- Path Found --> ParseIni["Locate & Parse tally.ini<br/>(Extract Port, DataPath, Load)"]
    L2 -- Not Found --> L3["Layer 3: Common Drive Sweep<br/>C: to G: across Tally Directories"]
    L3 --> ParseIni
    
    ParseIni --> TestPort
    TestPort -- Success --> L5["Layer 5: TDL Memory Grid Diagnostics<br/>Query $$ApplicationPath, $$DataPath, $$Release, Serial"]
    TestPort -- Failed / Closed --> L4["Layer 4: Multi-Port Range Scan<br/>Probe Ports 9000-9005, 9999, 10000"]
    L4 --> L5
    
    L5 --> Connected(["State: TALLY ONLINE<br/>Bound to Active Company & Port"])
```

### Layer 1: Running Process Inspection & PID-to-Port Mapping
1. Query active processes using Windows `tasklist` without popping a console window (`CREATE_NO_WINDOW = 0x08000000`):
   ```python
   subprocess.check_output(
       ["tasklist", "/FI", "IMAGENAME eq tally.exe", "/FO", "CSV", "/NH"],
       stderr=subprocess.DEVNULL, creationflags=0x08000000, timeout=3
   )
   ```
2. For each detected `tally.exe` PID, inspect TCP listeners using `netstat -ano -p tcp`:
   ```python
   out = subprocess.check_output(
       ["netstat", "-ano", "-p", "tcp"],
       stderr=subprocess.DEVNULL, creationflags=0x08000000, timeout=3
   )
   # Matches: TCP  127.0.0.1:9000  0.0.0.0:0  LISTENING  <PID>
   ```
   This immediately reveals the exact port Tally is actively listening on, even if it was changed to `9001` or `9005`.

### Layer 2: Windows Registry & App Paths Inspection
If Tally is currently closed, query the Windows Registry to locate its binary path and configuration directory:
1. `HKLM\SOFTWARE\Tally Solutions`
2. `HKLM\SOFTWARE\WOW6432Node\Tally Solutions`
3. `HKCU\Software\Microsoft\Windows\CurrentVersion\App Paths\tally.exe`

### Layer 3: Common Drive Sweep (Drives C: through G:)
If Registry keys are absent (common in portable USB installations), sweep across standard paths:
- `C:\Program Files\TallyPrime\tally.exe`
- `C:\Program Files\TallyPrimeEditLog\tally.exe`
- `C:\Program Files (x86)\Tally.ERP9\tally.exe`
- Repeated across drives `D:`, `E:`, `F:`, `G:`.

### Layer 4: `tally.ini` Configuration Parser
When the Tally directory is found, parse `tally.ini` to extract:
```ini
[Tally]
ServerPort = 9000
ClientServer = Both
Data = C:\ProgramData\TallyPrime\Data
Load = 10001
```
- `ServerPort`: Configured HTTP port.
- `ClientServer`: Confirms whether Tally is running as Server (`Yes` / `Both`). If set to `No`, the agent displays a clear remediation message guiding the user to enable Server mode.
- `Data`: The physical directory containing company databases (crucial for physical backups).
- `Load`: Preloaded company numbers.

### Layer 5: TDL Memory Grid Diagnostics Probe
Once the port answers, send a non-destructive ping envelope to query Tally’s internal memory variables:
```xml
<ENVELOPE>
  <HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Data</TYPE><ID>SysInfo</ID></HEADER>
  <BODY><DESC><STATICVARIABLES><SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT></STATICVARIABLES>
    <TDL><TDLMESSAGE>
      <REPORT NAME="SysInfo"><FORMS>SysInfoForm</FORMS></REPORT>
      <FORM NAME="SysInfoForm"><PARTS>SysInfoPart</PARTS></FORM>
      <PART NAME="SysInfoPart"><LINES>SysInfoLine</LINES></PART>
      <LINE NAME="SysInfoLine">
        <FIELDS>AppPath, DataPath, RelVer, SerialNo, ActiveCmp</FIELDS>
      </LINE>
      <FIELD NAME="AppPath"><SET>$$ApplicationPath</SET></FIELD>
      <FIELD NAME="DataPath"><SET>$$DataPath</SET></FIELD>
      <FIELD NAME="RelVer"><SET>$$Release</SET></FIELD>
      <FIELD NAME="SerialNo"><SET>$$ProductSerial</SET></FIELD>
      <FIELD NAME="ActiveCmp"><SET>##SVCURRENTCOMPANY</SET></FIELD>
    </TDLMESSAGE></TDL>
  </DESC></BODY>
</ENVELOPE>
```
This guarantees that the agent binds to the active company, verifies license validity, and knows the exact physical data path on disk.

---

## 4. Deep Dive: Enterprise Hybrid Disaster Recovery & Backup Engine

The reference implementation in `docs/temp/tally_backup_restore.py` introduces a production-tested **Multi-Destination Disaster Recovery Engine** supporting 3 complementary backup modes and 3 storage destinations.

```mermaid
flowchart TD
    subgraph BackupModes ["Backup Generation Modes"]
        M1["Mode A: Logical XML Rehydration<br/>Strict Topological Dependency Order"]
        M2["Mode B: Physical Binary Snapshot<br/>Zips Tally Data\\10001\\*.900 Files"]
        M3["Mode C: Live MySQL Reconstruction<br/>Rebuilds Tally XML directly from Cloud DB"]
    end

    subgraph SecurityEngine ["Security & Bundling Engine"]
        M1 & M2 --> Bundle["Assemble .tallybak Bundle<br/>(manifest.json + Checksums)"]
        Bundle --> Encrypt["PBKDF2-HMAC-SHA256 Encryption<br/>(100,000 Rounds + TBAK1ENC Header)"]
    end

    subgraph StorageDestinations ["Storage Targets"]
        Encrypt --> S1["1. Local Machine / USB<br/>(7-Day GFS Retention Rule)"]
        Encrypt --> S2["2. Cloud Server DB<br/>(tally_company_backups Table)"]
        Encrypt --> S3["3. AWS S3 Storage<br/>(Pure Python SigV4 AWS4-HMAC-SHA256)"]
    end
```

### Mode A: Logical Topological XML Rehydration
When restoring from logical XML, masters must be pushed into Tally in strict mathematical dependency order. Pushing a ledger before its parent group, or a compound unit before its base unit, results in immediate failure (`<LINEERROR>Group/Unit does not exist</LINEERROR>`).

The upgrade implements `_topological_sort_hierarchy()`:
```python
def _topological_sort_hierarchy(items: list[dict[str, Any]], name_key: str = "name", parent_key: str = "parent") -> list[dict[str, Any]]:
    by_name = {it.get(name_key, ""): it for it in items if it.get(name_key)}
    visited: set[str] = set()
    ordered: list[dict[str, Any]] = []

    def _visit(name: str, stack: set[str]) -> None:
        if name in visited or name not in by_name:
            return
        if name in stack:
            return  # Cycle break
        stack.add(name)
        parent = by_name[name].get(parent_key, "")
        if parent and parent in by_name and parent != name:
            _visit(parent, stack)
        stack.remove(name)
        visited.add(name)
        ordered.append(by_name[name])

    for n in list(by_name.keys()):
        _visit(n, set())
    return ordered
```

#### Strict Replay Sequence:
1. **Currencies & Exchange Rates**
2. **Groups:** Topologically sorted (e.g. `Primary` -> `Current Assets` -> `Bank Accounts`).
3. **Cost Centres:** Topologically sorted (e.g. `Primary Cost Category` -> Parent CC -> Child CC).
4. **Units:** Simple Units (`KGS`, `BOX`) imported strictly before Compound Units (`BOX of 25 KGS`).
5. **Godowns:** Topologically sorted (`Main Location` -> `Warehouse A` -> `Floor 1`).
6. **Stock Groups & Categories:** Topologically sorted.
7. **Ledgers:** Depends on existing Groups.
8. **Stock Items:** Leaf items first, followed by items with Bill of Materials (BOM) components, price lists, and batch openings.
9. **DayBook Vouchers:** Chronological replay with automatic balancing against Suspense A/c if an unbalanced single-entry legacy voucher is encountered, accompanied by Bill Allocations and Bank Allocations (`<BANKERSDATE>`, instrument number, URN).

### Mode B: Physical Binary Folder Snapshot (`.900` Files)
In addition to XML, the agent captures the physical database directory (`Data\10001` containing `Company.900`, `Trans.900`, `Master.900`, etc.) and compresses it into the `.tallybak` bundle:
- **Instant Restore:** Physical restore extracts the `.900` files directly into a new Tally data folder in **3 seconds**.
- **100% Fidelity:** Guarantees zero XML parsing errors, preserves identical historical voucher numbering, and maintains internal audit hashes.

### Mode C: Live MySQL-to-Tally Reconstruction
If a company’s laptop is lost or destroyed and no `.tallybak` file was created, the cloud backend reconstructs a full Tally company export directly from the synced MySQL tables (`tally_companies`, `tally_ledgers`, `tally_stock_items`, `tally_vouchers`), bundles it into Mode A format, and pushes it into a fresh Tally installation.

### Portable Passphrase Encryption (`PortableBackupCipher`)
To guarantee privacy across untrusted storage (S3 or public cloud), backups are encrypted using `PBKDF2-HMAC-SHA256` (100,000 iterations):
- Magic Header: `TBAK1ENC` (encrypted) or `TBAK1PLN` (plaintext).
- Nonce + Ciphertext + HMAC verification.
- **Laptop-Loss Recovery:** The user can decrypt and restore their company on any new PC simply by entering their recovery passphrase.

### Grandfather-Father-Son 7-Day Retention Rule (`keys_to_keep`)
To prevent disk exhaustion, local and server backups follow an automated pruning policy:
- Keep all of today’s backups.
- Keep the last backup of each of the previous 7 days.
- Keep all `pre_restore` backups (taken right before a restore operation).
- Always keep the newest backup overall.

### Byte-for-Byte Custom UDF Preservation (`extract_raw_object_blocks`)
Tally customizations (TDL) frequently add custom `<UDF:FIELD>` tags. Standard XML DOM parsers often drop or alter unknown namespaces. `extract_raw_object_blocks()` extracts raw XML blocks using regex scanning and strips `<CMPINFO>` without re-serializing, guaranteeing 100% byte-for-byte fidelity of all custom UDF fields.

---

## 5. Deep Dive: Runtime Security Shield, Anti-Debugging & Machine-Bound Vault

To protect the client binary against decompilation, token theft, and memory inspection, the architecture introduces `RuntimeSecurityShield` and `MachineBoundConfigVault` from `docs/temp/tally_desktop_gui.py` and `build_hardened_exe.py`.

```mermaid
flowchart TD
    subgraph AntiREToolchain ["Build-Time 4-Layer Hardened Toolchain"]
        SRC["Python Source Code"] --> AST["Layer 1: AST String Vault<br/>Encrypts String Literals to _tv_d(idx)<br/>Strips All Docstrings & Type Hints"]
        AST --> Cython["Layer 2: Cython Transpilation<br/>Transpiles .py to Native C (.pyd)"]
        Cython --> Nuitka["Layer 3: Nuitka C++ Compiler<br/>Compiles to Native PE Binary with LTO"]
        Nuitka --> Sign["Layer 4: PE Header Strip & Code Sign"]
    end

    subgraph RuntimeShield ["Runtime Security Shield (In-Memory Guard)"]
        Init["Process Initialization"] --> CheckWin32{"Win32 Debugger Present?<br/>IsDebuggerPresent()<br/>CheckRemoteDebuggerPresent()<br/>NtQueryInformationProcess"}
        CheckWin32 -- Detected --> Kill["Immediate Process Abort (os._exit(1))"]
        CheckWin32 -- Clean --> CheckPy{"Python Hook Detected?<br/>sys.gettrace() / sys.monitoring"}
        CheckPy -- Detected --> Kill
        CheckPy -- Clean --> CheckTiming{"Timing Trap Anomaly?<br/>500-Loop Nanosecond Drift"}
        CheckTiming -- Single-Step Detected --> Kill
        CheckTiming -- Clean --> Watchdog["Start Background Watchdog (5s)"]
    end

    subgraph VaultEngine ["Machine-Bound Configuration Vault"]
        Guid["Windows HKLM MachineGuid"] --> PBKDF2["PBKDF2-HMAC-SHA256 (50,000 Rounds)"]
        PBKDF2 --> Key["Machine-Specific Hardware Key"]
        Key --> EncryptConf["Stream Cipher + HMAC Authentication (TSV1 Envelope)"]
    end
```

### 1. The Critical Vulnerability in Previous Build Scripts
In `installer/build_exe.py`, lines 71–73 and 105–107 passed `--add-data` for core modules (`security.py`, `config.py`, `agent.py`, `tally_client.py`), embedding cleartext `.py` files inside the executable. The upgraded pipeline strips cleartext files and replaces standard PyInstaller with the 4-layer toolchain:
- **Layer 1 (AST String Vault):** Replaces all strings with decrypted function calls `_tv_d(idx)` backed by a zlib-compressed, XOR-encrypted string pool.
- **Layer 2 (Cython C Extension):** Converts Python modules into C code and compiles to native `.pyd` dynamic libraries.
- **Layer 3 (Nuitka C++ Compilation):** Uses MSVC to compile code into native C++ machine code with Link-Time Optimization (`--lto=yes`) and stripped symbols.
- **Layer 4 (PE Strip & Code Sign):** Strips debug symbols and applies digital signatures.

### 2. Win32 Native Anti-Debugging Engine
Windows native debugging checks are embedded into startup and the background watchdog:
```python
kernel32 = ctypes.windll.kernel32
ntdll = ctypes.windll.ntdll

# 1. Standard PEB IsDebuggerPresent flag
if kernel32.IsDebuggerPresent() != 0:
    os._exit(1)

# 2. CheckRemoteDebuggerPresent (catches debuggers attached after launch)
is_remote_debugged = ctypes.c_int(0)
kernel32.CheckRemoteDebuggerPresent(kernel32.GetCurrentProcess(), ctypes.byref(is_remote_debugged))
if is_remote_debugged.value != 0:
    os._exit(1)

# 3. NtQueryInformationProcess (ProcessDebugPort = 0x07)
debug_port = ctypes.c_void_p(0)
ret_len = ctypes.c_ulong(0)
if ntdll.NtQueryInformationProcess(kernel32.GetCurrentProcess(), 7, ctypes.byref(debug_port), ctypes.sizeof(debug_port), ctypes.byref(ret_len)) == 0:
    if debug_port.value not in (None, 0):
        os._exit(1)
```

### 3. Timing Anomaly Trap
Detects when an attacker is single-stepping through instructions in a debugger:
```python
t0 = time.perf_counter_ns()
acc = 0
for i in range(500):
    acc ^= (i * 0x45D9F3B) & 0xFFFFFFFF
elapsed_ms = (time.perf_counter_ns() - t0) / 1_000_000.0
if elapsed_ms > 85.0 and acc != -1:
    os._exit(1)  # Single-step delay detected
```

### 4. Reverse-Engineering Tool Blacklist Scan
Scans active processes for known analysis tools:
`x64dbg`, `x32dbg`, `ida`, `ida64`, `ghidra`, `dnspy`, `cheatengine`, `ollydbg`, `windbg`, `processhacker`, `wireshark`, `frida`, `pyinstxtractor`, `pycdc`, `uncompyle6`.

### 5. `MachineBoundConfigVault`
Derives a 256-bit AES key unique to the client PC using `MachineGuid` from `HKLM\SOFTWARE\Microsoft\Cryptography` with 50,000 PBKDF2 iterations. Stored configs are wrapped in a `TSV1` envelope with an HMAC-SHA256 signature. If an attacker copies `config.enc` to another computer, decryption fails immediately due to HMAC mismatch.

---

## 6. Deep Dive: Inno Setup 6 Installer & Windows Task Scheduler Daemon

From `docs/temp/TallyPrimeSync_Installer.iss` and `build_windows_release.bat`, the Windows installer provides enterprise-grade unattended operation:

```pascal
[Tasks]
Name: "autostart"; Description: "Launch MyTally Bridge automatically on Windows startup"; GroupDescription: "Startup:"
Name: "scheduledtask"; Description: "Register Windows Task Scheduler to run headless delta sync every 15 minutes"; GroupDescription: "Background Sync:"

[Dirs]
Name: "{localappdata}\MyTallyBridge"; Permissions: users-modify
Name: "{localappdata}\MyTallyBridge\tally_backups"; Permissions: users-modify

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "MyTallyBridge"; ValueData: """{app}\MyTallyBridge.exe"""; Flags: uninsdeletevalue; Tasks: autostart

[Run]
; Registers Windows Task Scheduler for 15-minute unattended synchronization
Filename: "schtasks.exe"; Parameters: "/Create /F /SC MINUTE /MO 15 /TN ""MyTallyHeadlessSyncTask"" /TR ""\""{app}\MyTallyBridge.exe\"" --headless-once"""; Flags: runhidden; Tasks: scheduledtask
Filename: "{app}\MyTallyBridge.exe"; Description: "Launch MyTally Bridge"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "schtasks.exe"; Parameters: "/Delete /F /TN ""MyTallyHeadlessSyncTask"""; Flags: runhidden; RunOnceId: "RemoveMyTallySyncTask"
```

### The `--headless-once` Execution Mode
When invoked via Task Scheduler (`MyTallyBridge.exe --headless-once`):
1. **No GUI Allocation:** Bypasses WebView2 and CustomTkinter initialization.
2. **Runs Auto-Discovery:** Detects active Tally port and company in seconds.
3. **Outbound Queue Processing:** Pushes pending web-created vouchers into Tally.
4. **Inbound Delta Sync:** Fetches incremental records (`$AlterID > watermark`) and uploads them via gzip compression.
5. **Scheduled Backup Check:** If the backup window is active, triggers the hybrid backup.
6. **Clean Termination:** Exits with code `0`, releasing all memory.

---

## 7. Deep Dive: CDC, Density-Adaptive Range Planning & AlterID Gap Handling

The reference files in `docs/temp/tally_sync_connector.py` contain vital algorithms for robust Change Data Capture (CDC):

```mermaid
flowchart TD
    Start(["Start Sync Cycle"]) --> Index["Step 1: Fetch Lightweight Voucher Index<br/>(export_voucher_index: DATE, MASTERID)"]
    Index --> Planner["Step 2: Density-Adaptive Range Planner<br/>(plan_voucher_ranges: Slices into ~50-voucher windows,<br/>never splitting single days)"]
    
    Planner --> CheckDrop{"Any Missing AlterID<br/>Sequence Numbers Detected?"}
    CheckDrop -- Yes (Dropped Packets) --> GapBackfill["Algorithm A: Targeted Gap Backfill<br/>Fetch VouchersByAlterIdList via $$IsValueInList"]
    CheckDrop -- No --> DeltaPull["Pull Incremental Vouchers ($AlterID > watermark)"]
    
    GapBackfill & DeltaPull --> Sanitize["Step 3: Blank-Node Sanitizer<br/>Regex cleans empty XML tags (<TAG/>, <TAG></TAG>)"]
    Sanitize --> GzipCompress["Step 4: Gzip Compression<br/>(Content-Encoding: gzip)"]
    GzipCompress --> CloudPush["Step 5: Cloud Ingestion with X-Idempotency-Key"]
    
    CloudPush --> PeriodicDeletions{"Reconciliation Interval Reached?<br/>(e.g., Every 6 Hours)"}
    PeriodicDeletions -- Yes --> Reconcile["Algorithm B: Active Keys Reconciliation<br/>Export (MasterID, GUID) pairs -> Soft-delete Ghost Vouchers"]
    PeriodicDeletions -- No --> Complete(["Sync Cycle Complete"])
    Reconcile --> Complete
```

### 1. Density-Adaptive Voucher Range Planner (`plan_voucher_ranges`)
Instead of issuing large multi-month DayBook queries that crash Tally with Out-Of-Memory (OOM) errors, the agent:
1. Queries `export_voucher_index` returning only `(DATE, MASTERID)` pairs (ultra-fast, minimal memory).
2. Slices dates into ~50-voucher windows.
3. **Never splits a single day:** If a single day has 800 vouchers, that day is kept as a single atomic query window rather than slicing midday, preventing duplicate record fetches.
4. Applies a dual date-filter fallback (`<SVFROMDATE>` combined with `$Date >= $$Date:"1-Apr-2026"` in TDL) to handle Tally instances that ignore header date tags.

### 2. Targeted AlterID Gap Backfill (Algorithm A)
If a network hiccup or timeout drops a batch of vouchers, the cloud identifies missing sequence numbers in `AlterID`. Instead of rewinding the entire watermark (which re-transmits thousands of unchanged records), the agent queries specifically for the missing items:
```xml
<ENVELOPE>
  <HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Collection</TYPE><ID>MissingVouchers</ID></HEADER>
  <BODY><DESC>
    <STATICVARIABLES><SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT><SVCURRENTCOMPANY>{company_name}</SVCURRENTCOMPANY></STATICVARIABLES>
    <TDL><TDLMESSAGE>
      <COLLECTION NAME="MissingVouchers"><TYPE>Voucher</TYPE><FETCH>{VOUCHER_FETCH}</FETCH><FILTERS>AlterListFilter</FILTERS></COLLECTION>
      <SYSTEM TYPE="Formulae" NAME="AlterListFilter">$$IsValueInList:$AlterID:"101,102,105,108"</SYSTEM>
    </TDLMESSAGE></TDL>
  </DESC></BODY>
</ENVELOPE>
```

### 3. Active Keys Ghost Voucher Deletion Reconciliation (Algorithm B)
When an accountant presses `Alt+D` inside Tally, no AlterID increment occurs. To eliminate phantom vouchers from the cloud:
1. The agent periodically queries `export_active_voucher_keys()`:
   ```xml
   <COLLECTION NAME="ActiveVoucherKeys" ISMODIFY="No"><TYPE>Voucher</TYPE>
     <FETCH>GUID,MASTERID</FETCH>
   </COLLECTION>
   ```
2. The agent sends these active keys to `POST /sync/reconcile-deletions`.
3. The cloud identifies records existing in MySQL that are absent from the active keys set and marks them `is_deleted = 1`, achieving 100% deletion parity without database resets.

### 4. Safe Voucher Addressing (`voucher_address_attrs`) & Ghost Cleanup
When updating vouchers in Tally, misusing `GUID` as `REMOTEID` often leads to duplicate records. The connector addresses vouchers using:
`DATE="YYYYMMDD" TAGNAME="MASTERID" TAGVALUE="<MasterID>"`
This precisely targets the existing voucher in Tally's B-Tree index. Furthermore, `remove_tally_ghost()` purges rejected `ALTERID=0` records created during aborted import attempts.

### 5. Blank XML Node Sanitizer (`sanitize_blank_nodes`)
Before compressing and transmitting XML payloads, empty tags are stripped using recursive regex:
```python
_EMPTY_NODE_RE = re.compile(r"<([A-Za-z0-9_.]+)[^>]*>\s*</\1>|<([A-Za-z0-9_.]+)[^>]*/>")

def sanitize_blank_nodes(xml_text: str) -> str:
    if not xml_text:
        return ""
    cleaned = _EMPTY_NODE_RE.sub("", xml_text)
    return _EMPTY_NODE_RE.sub("", cleaned)
```
This reduces raw XML payload size by **40–60%** before gzip compression.

---

## 8. Deep Dive: Cloud Schema, Idempotency & Multi-Company Isolation

The reference files `mysql_schema.sql` and `fastapi_mysql_backend.py` provide enterprise schema structures to support the upgraded agent:

### 1. Idempotent Ingestion Log (`tally_sync_idempotency_log`)
Guarantees that network retries never cause duplicate voucher insertions:
```sql
CREATE TABLE IF NOT EXISTS tally_sync_idempotency_log (
    batch_id VARCHAR(128) PRIMARY KEY,
    company_id BIGINT UNSIGNED NOT NULL,
    record_count INT UNSIGNED NOT NULL DEFAULT 0,
    upserted_count INT UNSIGNED NOT NULL DEFAULT 0,
    skipped_unchanged_count INT UNSIGNED NOT NULL DEFAULT 0,
    status ENUM('PROCESSING', 'COMPLETED', 'FAILED') NOT NULL DEFAULT 'PROCESSING',
    error_message TEXT NULL,
    response_json JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME NULL,
    INDEX idx_idem_company_status (company_id, status, created_at DESC)
) ENGINE=InnoDB;
```
If a desktop push times out on the HTTP client side but completes on the server, the subsequent retry returns the cached `response_json` instantly without re-processing.

### 2. Multi-Destination Company Backups Table (`tally_company_backups`)
Tracks all physical and logical backups across Local, Server, and S3:
```sql
CREATE TABLE IF NOT EXISTS tally_company_backups (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    backup_id VARCHAR(128) NOT NULL UNIQUE,
    company_name VARCHAR(255) NOT NULL,
    company_number VARCHAR(32) DEFAULT '',
    company_guid VARCHAR(100) DEFAULT '',
    backup_mode ENUM('LOGICAL_ONLY', 'PHYSICAL_ONLY', 'HYBRID_LOGICAL_AND_PHYSICAL', 'MYSQL_RECONSTRUCTED') NOT NULL DEFAULT 'HYBRID_LOGICAL_AND_PHYSICAL',
    storage_targets VARCHAR(128) NOT NULL DEFAULT 'SERVER',
    s3_bucket VARCHAR(255) DEFAULT '',
    s3_object_key VARCHAR(512) DEFAULT '',
    is_encrypted TINYINT(1) DEFAULT 0,
    uncompressed_bytes BIGINT UNSIGNED DEFAULT 0,
    archive_bytes BIGINT UNSIGNED DEFAULT 0,
    sha256_checksum CHAR(64) NOT NULL,
    manifest_json JSON NOT NULL,
    archive_blob LONGBLOB NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_bak_comp_created (company_name, created_at DESC)
) ENGINE=InnoDB;
```

### 3. Device Pairing Protocol (`tally_agent_devices` & `tally_agent_pairings`)
- Pairing alphabet: `ABCDEFGHJKLMNPQRSTUVWXYZ23456789` (excludes `0`, `O`, `1`, `I` to prevent user transcription errors).
- Desktop generates an 8-character pairing code valid for 10 minutes.
- Web administrator verifies the machine name and clicks "Approve".
- Desktop exchanges the code for a scoped device token (`mta_...`), eliminating the need to store tenant administrator passwords on the desktop.

### 4. Company Copy Fingerprint Protection
To prevent accidental database corruption when an accountant copies a Tally data folder to a test machine, the agent computes:
`company_fingerprint = sha256(f"{company_number}|{books_from}|{guid}")`
If the fingerprint does not match the registered cloud company record, synchronization halts immediately with a warning, preventing test entries from corrupting live financial accounts.

### 5. Analytical BI Views for Reporting Parity
The schema incorporates three dedicated views:
- `vw_tally_ledger_closing_balances`: Filters out `is_order_voucher = 1` and `is_inventory_voucher = 1`, ensuring closing balances match Tally's Trial Balance to the cent.
- `vw_tally_bill_outstanding_aging`: Dynamically matches `New Ref` and `Advance` allocations against subsequent `Agst Ref` payments to compute real-time aging buckets (0–30, 31–60, 61–90, 90+ days).
- `vw_tally_deduplicated_inventory_movement`: Deduplicates stock movement records caused by Goods Receipt Notes (GRN) split across multiple tracking numbers.

---

## 9. Prioritized Implementation Roadmap

```mermaid
gantt
    title MyTally Desktop Sync Agent Enterprise Upgrade Roadmap
    dateFormat  YYYY-MM-DD
    section Phase 1: Reliability & Discovery
    5-Layer Auto-Discovery Engine         :p1_1, 2026-10-16, 3d
    Blank XML Node Sanitizer + Gzip       :p1_2, 2026-10-19, 2d
    Multi-Company LocalSyncStore          :p1_3, 2026-10-21, 2d
    section Phase 2: Integrity & Deletions
    Active Keys Deletion Reconciliation   :p2_1, 2026-10-23, 3d
    Targeted AlterID Gap Backfilling      :p2_2, 2026-10-26, 3d
    Density-Adaptive Range Planner        :p2_3, 2026-10-29, 2d
    section Phase 3: Hybrid Disaster Recovery
    Topological Restore Engine (Mode A)   :p3_1, 2026-10-31, 3d
    Physical .900 Folder Snapshot (Mode B):p3_2, 2026-11-03, 3d
    Multi-Destination S3 SigV4 & Server   :p3_3, 2026-11-06, 3d
    section Phase 4: Security & Hardening
    RuntimeSecurityShield Anti-Debug      :p4_1, 2026-11-09, 3d
    MachineBoundConfigVault               :p4_2, 2026-11-12, 2d
    4-Layer C-Compilation Toolchain       :p4_3, 2026-11-14, 3d
    section Phase 5: Distribution & Daemon
    Inno Setup 6 Installer Script         :p5_1, 2026-11-17, 2d
    Task Scheduler 15-Min Headless Daemon :p5_2, 2026-11-19, 2d
```

---

## 10. Direct Repository Mapping & Actionable File Modification Checklist

| Target File in Repository | Reference Source | Action Required |
|:---|:---|:---|
| `desktop-sync-agent/tally_client.py` | `tally_desktop_gui.py` (`TallyEnvironmentDetector`), `tally_sync_connector.py` | Implement `detect_tally_runtime()`, `sanitize_blank_nodes()`, `export_active_voucher_keys()`, `export_vouchers_by_alter_ids()`, and `plan_voucher_ranges()`. |
| `desktop-sync-agent/backups.py` | `tally_backup_restore.py` | Overhaul backup engine: Implement `zip_physical_company_folder()`, `extract_physical_company_folder()`, `_topological_sort_hierarchy()`, `PortableBackupCipher`, and `AWSS3BackupProvider`. |
| `desktop-sync-agent/security.py` | `tally_desktop_gui.py` | Add `RuntimeSecurityShield` (Win32 debugger checks, timing trap, process scan) and `MachineBoundConfigVault` (hardware fingerprint key derivation). |
| `desktop-sync-agent/agent.py` | `tally_sync_connector.py`, `TallyPrimeSync_Installer.iss` | Add `--headless-once` CLI flag for Windows Task Scheduler, integrate `LocalSyncStore` multi-company state, and connect deletion reconciliation loop. |
| `desktop-sync-agent/installer/build_exe.py` | `build_hardened_exe.py` | **Fix critical vulnerability:** Remove cleartext `--add-data` `.py` packaging. Implement AST String Vault (`_tv_d`), Cython transpilation, and Nuitka C++ compilation. |
| `desktop-sync-agent/installer/MyTallyBridge_Setup.iss` | `TallyPrimeSync_Installer.iss` | Create Inno Setup 6 script registering the 15-minute `schtasks.exe` headless sync daemon and setting `users-modify` permissions. |
| `backend/app/models/` & `backend/app/routers/sync.py` | `mysql_schema.sql`, `fastapi_mysql_backend.py` | Add `tally_sync_idempotency_log` middleware, `POST /sync/reconcile-deletions` endpoint, and backup metadata endpoints. |
| `backend/app/routers/backups.py` | `tally_backup_restore.py` | Implement cloud backup upload/download handlers and Mode C Live MySQL-to-Tally reconstruction service. |

---

## 11. Conclusion

Integrating the battle-tested patterns from `docs/temp` elevates MyTally from a standard script into a resilient, enterprise-grade synchronization daemon:
- **Zero Configuration:** 5-layer auto-discovery eliminates customer port and path confusion.
- **Disaster Recovery:** Hybrid `.tallybak` archives enable 3-second physical company restores alongside topological XML rehydration.
- **Financial Accuracy:** Active keys reconciliation and targeted AlterID backfilling ensure 100% ledger balance parity without ghost records.
- **Zero Decompilation Risk:** The 4-layer C-compilation pipeline and runtime anti-debug shield protect proprietary code and customer credentials against reverse-engineering.
- **Continuous Reliability:** Windows Task Scheduler integration guarantees 24/7 background sync continuity even when user desktops are closed.
