# SnehDistribuors Desktop Sync Agent (TallyPrime Connector)

The **SnehDistribuors Desktop Sync Agent** is a modern Windows desktop application (and background daemon) that runs on the Windows computer or virtual machine where **TallyPrime** is installed. It connects local Tally on `http://127.0.0.1:9000/` with your **SnehDistribuors Cloud ERP** backend in real time.

---

## 🌟 Key Features

1. **Premium Modern GUI Interface**:
   - Built with **CustomTkinter** featuring a sleek dark-themed interface.
   - Live status indicators for both **TallyPrime** and **Cloud ERP**.
   - Metric cards displaying synced **Vouchers**, **Ledgers**, **Stock Items**, and **Errors**.
   - Real-time scrolling activity log console with color-coded events.
   - Quick action controls: **🔄 Sync Delta**, **⚡ Sync All (Full Baseline)**, **⏸ Pause / Resume**, **🏢 Companies**, **⚙ Settings**, and **📥 Minimize to System Tray**.

2. **Single-Page Setup: Sign Up or Sign This PC In**:
   - Enter the Cloud Server URL and the Tally host, with the company open in TallyPrime.
   - **New business**: press **New here? Create an account for your business**, fill in your details, press **Email me a code**, and enter the code. This creates the account, its first admin, this PC's device and the first company (the one open in Tally) in one step.
   - **Existing account**: enter the email and password of someone who holds the **Manage sync agent** permission (admins do by default) and press **🚀 Connect & Start Sync**. Everyone else joins the business by invitation from the web app, not from the agent.
   - Either way the PC is signed in **as a device**: it gets its own token and stores no password afterwards. The PC is listed in the web app under Admin → Sync agent & team, where an admin can sign it out.
   - **🔍 Auto-Detect**: 1-click discovery that queries Tally XML server and automatically detects open company names and release version.
   - **🧪 Test Connection**: Live diagnostic test verifying connectivity to both Tally and Cloud before saving.

3. **LiveKeeping-Style Connection Settings**:
   - Customize Tally host, port, cloud backend URL, sync intervals, and vouchers per full sync range.
   - Auto-discover Tally application and data paths.
   - Toggle **"Always Sync All Records (Bypass Tally Alter ID Filter)"** for complete baseline synchronizations.
   - **🔐 Re-login / Switch User** returns to Setup to sign the PC in again.

4. **System Tray & Windows Boot Auto-Start**:
   - Minimizes cleanly to the Windows system tray (`pystray`) for uninterrupted background syncing.
   - System tray right-click menu: **Open**, **Sync Delta Now**, **Sync All (Full Refresh)**, **Pause / Resume**, and **Exit**.
   - Toggle switch in Settings or 1-click batch script to automatically start with Windows boot.

5. **Several Companies, Each Bound to Its Tally Identity**:
   - One agent syncs every company linked to this PC. **🏢 Companies** lists them; a company open in Tally but not yet linked shows as "Open in Tally · not synced" with a **Link** button, and **Unlink** stops syncing one from this PC (its data in the app stays).
   - Each company is tied to its Tally GUID, not its name, and every request names that GUID. Opening, closing or switching companies in TallyPrime never redirects a sync to a different company: a linked company that is not open is skipped ("is not open in Tally") while the others keep syncing.
   - A company is synced from one PC at a time. Linking one that another PC holds asks **"Move sync to this PC?"** first.
   - A copy or restored backup of a synced company is refused as "a different copy of the books". If two companies with the same name are open, neither is synced until one is closed.

6. **Bidirectional Synchronization & Incremental Optimization**:
   - **Outbound (Cloud $\to$ Tally)**: Pulls pending creations and edits (Ledgers, Vouchers, Stock Items) from the cloud queue and injects them directly into Tally.
   - **Inbound Delta (Tally $\to$ Cloud)**: Periodically pulls incremental changes (`ALTERID > min_alter_id`) across Ledgers, Vouchers, and Stock Items.
   - **Empty Payload Filtering**: Unchanged collections returning empty `<DATA><COLLECTION></COLLECTION></DATA>` are automatically discarded, preventing redundant network calls to `/sync/inbound`.
   - **One Sync at a Time**: The server imports one push per company at a time. If the previous push is still being imported (for instance after a proxy timed out on it), the next one is refused with "the server is still importing this company's previous sync"; the agent stops pushing for that cycle and sends it again in the next. Only one agent process runs per PC, whether started as the window or from the command line.
   - **Sync All Option**: Users can trigger an instant full baseline sync anytime from the Dashboard, Settings, Tray Menu, or CLI (`--sync-all`).
   - **Full Sync in Date Ranges**: A full sync sends vouchers in date ranges of about 50 vouchers each, a few ranges each cycle (log: `Full sync of N vouchers planned in M date ranges`), so no single request is too big for the server to answer in time. The size is **Vouchers per Full Sync Range** in ⚙ Settings; lower it if a range fails with a timeout or HTTP 524. Changing it while a full sync is under way plans the rest again at the new size; ranges already done are not sent again. Progress is saved, so a restart or a failed range carries on from where it stopped. A company with no more vouchers than one range is exported whole, and so is one whose Tally does not return vouchers by date range.

7. **Secure Credential Storage & Sign-In State**:
   - Once the PC is signed in as a device, the agent uses its device token and needs no password. An older install keeps syncing on its saved per-person login until the PC is signed in from Setup; a server with `REQUIRE_AGENT_DEVICE_SIGNIN` on refuses that older login.
   - If the server signs this PC out on purpose (an admin did it, or the person who signed it in was deactivated), the agent stops and says "This PC is signed out of the sync agent". It does not sign itself back in, also after a restart: sign in again from Setup.
   - Passwords and tokens are stored in the **OS credential vault** via `keyring` (Windows Credential Manager / DPAPI, macOS Keychain). `agent_config.json` only holds `keyring:<account>` references, so the file contains no secrets.
   - If no vault is available, secrets are encrypted on disk with Fernet (AES-128-CBC + HMAC-SHA256) using a machine-bound PBKDF2 key. If `cryptography` is missing too, secrets are **not saved at all**. There is no plaintext fallback.
   - Older configs with plaintext or file-encrypted secrets are migrated into the vault automatically the next time the agent starts.
   - The config defaults to `agent_config.json` next to the script or `.exe` (not the current directory). It is gitignored, and the `.exe` build no longer bundles the build machine's copy. See `agent_config.example.json` for the shape.
   - On the older per-person login, an expired access token (HTTP 401) makes the agent re-authenticate in memory and save the fresh token back to secure storage.

8. **Automated Log Rotation**:
   - System logs (`agent.log` and `tally_traffic.log`) automatically rotate at 5 MB (retaining up to 3 backup archives) to prevent unbounded disk usage.

---

## 🚀 Running the Application

### 1. Launch Modern GUI
```bash
python gui_app.py
```
*(On first launch, open the company in TallyPrime, enter your Cloud URL, then either create an account or sign the PC in with an admin's email and password. Once connected, settings are saved to `agent_config.json` and the dashboard appears automatically.)*

The company's name in Tally must match its name in the app the first time an existing company is linked, otherwise a second company is added.

### 2. Run in Headless CLI Mode (Optional)
Sign the PC in from the GUI first; the headless agent reuses that sign-in.
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
