# SnehDistribuors Desktop Sync Agent (TallyPrime Connector)

The **SnehDistribuors Desktop Sync Agent** is a modern Windows desktop application (and background daemon) that runs on the Windows computer or virtual machine where **TallyPrime** is installed. It connects local Tally on `http://127.0.0.1:9000/` with your **SnehDistribuors Cloud ERP** backend in real time.

---

## 🌟 Key Features

1. **Premium Modern GUI Interface**:
   - Built with **CustomTkinter** featuring a sleek dark-themed interface.
   - Live status indicators for both **TallyPrime** and **Cloud ERP**.
   - Metric cards displaying synced **Vouchers**, **Ledgers**, **Stock Items**, and **Errors**.
   - Real-time scrolling activity log console with color-coded events.
   - Quick action controls: **🔄 Sync Delta**, **⚡ Sync All (Full Baseline)**, **⏸ Pause / Resume**, **⚙ Settings**, and **📥 Minimize to System Tray**.

2. **Single-Page Setup & Login**:
   - Simple, unified setup view: enter Cloud Server URL, Email, Password, and Tally host.
   - **🔍 Auto-Detect Company**: 1-click discovery that queries Tally XML server and automatically detects open company names and release version.
   - **🧪 Test Connection**: Live diagnostic test verifying connectivity to both Tally and Cloud before saving.

3. **LiveKeeping-Style Connection Settings**:
   - Customize Tally host, port, cloud backend URL, and sync intervals.
   - Auto-discover Tally application and data paths.
   - Toggle **"Always Sync All Records (Bypass Tally Alter ID Filter)"** for complete baseline synchronizations.
   - Switch user / re-login with ease.

4. **System Tray & Windows Boot Auto-Start**:
   - Minimizes cleanly to the Windows system tray (`pystray`) for uninterrupted background syncing.
   - System tray right-click menu: **Open**, **Sync Delta Now**, **Sync All (Full Refresh)**, **Pause / Resume**, and **Exit**.
   - Toggle switch in Settings or 1-click batch script to automatically start with Windows boot.

5. **Automatic Company Switch Detection**:
   - Dynamically detects when users open, close, or switch companies inside TallyPrime and adapts the sync target automatically without restarting.

6. **Bidirectional Synchronization & Incremental Optimization**:
   - **Outbound (Cloud $\to$ Tally)**: Pulls pending creations and edits (Ledgers, Vouchers, Stock Items) from the cloud queue and injects them directly into Tally.
   - **Inbound Delta (Tally $\to$ Cloud)**: Periodically pulls incremental changes (`ALTERID > min_alter_id`) across Ledgers, Vouchers, and Stock Items.
   - **Empty Payload Filtering**: Unchanged collections returning empty `<DATA><COLLECTION></COLLECTION></DATA>` are automatically discarded, preventing redundant network calls to `/sync/inbound`.
   - **Sync All Option**: Users can trigger an instant full baseline sync anytime from the Dashboard, Settings, Tray Menu, or CLI (`--sync-all`).

7. **Secure Credential Storage & Autonomous Token Refresh**:
   - Passwords and tokens are stored in the **OS credential vault** via `keyring` (Windows Credential Manager / DPAPI, macOS Keychain). `agent_config.json` only holds `keyring:<account>` references, so the file contains no secrets.
   - If no vault is available, secrets are encrypted on disk with Fernet (AES-128-CBC + HMAC-SHA256) using a machine-bound PBKDF2 key. If `cryptography` is missing too, secrets are **not saved at all**. There is no plaintext fallback.
   - Older configs with plaintext or file-encrypted secrets are migrated into the vault automatically the next time the agent starts.
   - The config defaults to `agent_config.json` next to the script or `.exe` (not the current directory). It is gitignored, and the `.exe` build no longer bundles the build machine's copy. See `agent_config.example.json` for the shape.
   - If an access token expires (HTTP 401), the agent re-authenticates in memory and saves the fresh token back to secure storage.

8. **Automated Log Rotation**:
   - System logs (`agent.log` and `tally_traffic.log`) automatically rotate at 5 MB (retaining up to 3 backup archives) to prevent unbounded disk usage.

---

## 🚀 Running the Application

### 1. Launch Modern GUI
```bash
python gui_app.py
```
*(On first launch, enter your Cloud URL and login credentials. Once connected, settings are saved to `agent_config.json` and the dashboard appears automatically.)*

### 2. Run in Headless CLI Mode (Optional)
```bash
# Run continuous background daemon in terminal
python agent.py

# Force a full baseline sync of all records (bypassing Alter ID)
python agent.py --sync-all

# Test a single sync pass
python agent.py --test-once

# Discover Tally host & company details
python agent.py --discover
```

---

## 📦 Building Standalone Windows Executable (`.exe`)

You can bundle the entire application into a single standalone `.exe` with icon and system tray support:

1. Open a Windows Command Prompt (`cmd.exe`) in `desktop-sync-agent\installer\`.
2. Run:
   ```cmd
   build_windows_exe.bat
   ```
3. The standalone binary will be created in:
   - 📂 `desktop-sync-agent\dist\SnehDistribuorsSync.exe`

Simply distribute `SnehDistribuorsSync.exe` to any 64-bit Windows client PC running TallyPrime, including ARM ones. No Python installation required! `agent_config.json` is created on first launch.

### If the build fails

The script explains each of these on screen and fixes the first three itself. They are listed here for reference.

| What you see | Cause | Fix |
| --- | --- | --- |
| No Python on the PC | — | Answer **Y** when the script offers to install Python 3.13 (64-bit) from python.org |
| `No module named 'tkinter'` | Python was installed with **tcl/tk and IDLE** unticked | Answer **Y** to the script's offer, or run the python.org installer → Modify → tick **tcl/tk and IDLE** |
| `No module named pip` | Python was installed with **pip** unticked | The script adds pip itself. By hand: `python -m ensurepip --upgrade --user` |
| `Failed building wheel for cryptography`, `link.exe not found`, Rust or Visual Studio messages | The Python is the **ARM64** build, or too new for ready-made packages | Install the python.org file ending in `-amd64.exe`, even on an ARM PC. The script skips ARM64 Pythons |
| Modify asks you to browse for a file | The original installer file is gone | Cancel, download the same installer from python.org, choose Uninstall, then install again with Customize |
| `python` still runs the old version after installing a new one | The old one is first on PATH | Nothing: the script checks every installed Python and uses the first that qualifies |
| `PermissionError` on `SnehDistribuorsSync.exe` | The agent is running | Quit it from the tray icon, then build again |
| The `.exe` disappears after the build | Antivirus removed it | Allow the `desktop-sync-agent\dist` folder |

The Python used for building must be the **64-bit Intel/AMD** one: the `.exe` takes its architecture from it, and an ARM64 build would not run on ordinary PCs.

---

## 🛠️ Auto-Start on Windows Boot

You can enable automatic startup on Windows boot through **three easy methods**:

### Option 1: In the App GUI (Easiest)
Go to **⚙ Settings** in the application and switch ON **"Start Automatically on Windows Boot"**.

### Option 2: 1-Click Batch Script
Double-click:
```cmd
desktop-sync-agent\installer\enable_autostart_on_boot.bat
```
*(To remove it, double-click `desktop-sync-agent\installer\disable_autostart.bat`)*

### Option 3: CLI Command
```bash
python agent.py --install-startup
# To remove:
python agent.py --uninstall-startup
```
