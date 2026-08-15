# MyTally Desktop Sync Agent (Windows / VM Connector)

The **MyTally Desktop Sync Agent** is a background sync connector that runs on the Windows computer or virtual machine where **TallyPrime** is installed. It connects local Tally on `http://127.0.0.1:9000/` with your **MyTally Cloud ERP** backend.

---

## 🌟 Key Features

1. **Automatic Tally Host Discovery**:
   - Automatically queries TallyPrime for host installation directory (`$$ApplicationPath`), company data path (`$$DataPath`), and active company name.
   - Automatically discovers the exact location of `tallysave.tsf` and `tally.ini`.
2. **Zero Router Port Forwarding Needed**:
   - Makes a secure outbound connection from your office PC to the MyTally Cloud Backend.
3. **Bidirectional Synchronization**:
   - **Outbound (Cloud $\to$ Tally)**: Automatically retrieves pending creations and edits (Ledgers, Vouchers, Voucher Types, Stock Items) from the cloud queue, pushes them to Tally on port 9000, and marks them acknowledged.
   - **Inbound (Tally $\to$ Cloud)**: Automatically extracts newly created vouchers and masters from Tally and syncs them to the cloud database.
4. **Resilient Retry & Health Monitoring**:
   - Gracefully handles network drops and Tally restarts without losing transactions.

---

## 🚀 Quick Start (Running via Python)

### 1. Requirements
- Python 3.8+ (No external third-party packages required — uses standard library).

### 2. Configuration (`agent_config.json`)
When you run the agent for the first time, it automatically generates `agent_config.json`:

```json
{
    "backend_url": "http://127.0.0.1:8000",
    "tally_url": "http://127.0.0.1:9000",
    "auth_token": "",
    "company_name": "Bhrama Enterprises",
    "sync_interval_seconds": 5,
    "inbound_interval_seconds": 60,
    "auto_discover_paths": true
}
```

### 3. Run Discovery & Health Check
```bash
python agent.py --discover
```

**Output Example:**
```
===========================================================================
  🚀  MyTally Desktop Sync Agent (TallyPrime Connector)
===========================================================================
  Bridging TallyPrime (Local Port 9000) ◄═══► MyTally Cloud ERP
===========================================================================

🔍 Contacting Tally XML Server at http://192.168.71.128:9000...
✅ Tally Connection: ACTIVE
🏢 Active Company:    Bhrama Enterprises
📂 Application Path:  C:\Users\Akash\Downloads\integration-setup\integration-setup
💾 Data Path:         C:\Users\Akash\Downloads\integration-setup\integration-setup\Data
⚙️ Config (tallysave): C:\Users\Akash\Downloads\integration-setup\integration-setup\tallysave.tsf
📄 Startup Settings:  C:\Users\Akash\Downloads\integration-setup\integration-setup\tally.ini
🏷️ Tally Release:     5.0
```

### 4. Start Background Daemon
```bash
python agent.py
```

---

## 📦 Building Standalone Windows Executable (`.exe`)

You can bundle the agent into a single `.exe` file that can be distributed to clients without installing Python:

1. Open a Windows Command Prompt (`cmd.exe`) in the `desktop-sync-agent\installer` directory.
2. Run:
   ```cmd
   build_windows_exe.bat
   ```
3. The standalone binary will be generated in:
   `desktop-sync-agent\dist\MyTallySyncAgent.exe`

---

## 🛠️ Auto-Start on Windows Boot

You can enable automatic startup on Windows boot in **two easy ways**:

### Option 1: 1-Click Batch Script (Recommended)
Simply double-click:
```cmd
desktop-sync-agent\installer\enable_autostart_on_boot.bat
```
*(To remove it later, double-click `desktop-sync-agent\installer\disable_autostart.bat`)*

### Option 2: CLI Command
```bash
# To enable auto-start
MyTallySyncAgent.exe --install-startup

# To disable auto-start
MyTallySyncAgent.exe --uninstall-startup
```

### Option 3: Windows Background Service (NSSM)
If you want the agent to run even before any user logs in (e.g. on a dedicated server / VM):
```cmd
nssm install MyTallySyncAgent "C:\path\to\MyTallySyncAgent.exe"
nssm start MyTallySyncAgent
```
