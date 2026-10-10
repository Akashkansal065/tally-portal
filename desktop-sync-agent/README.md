# MyTally Bridge: Desktop Sync Agent (TallyPrime Connector)

**MyTally Bridge** (the desktop sync agent) is a Windows desktop application (and background daemon) that runs on the Windows computer or virtual machine where **TallyPrime** is installed. It connects local Tally on `http://127.0.0.1:9000/` with your **SnehDistribuors Cloud ERP** backend in real time.

---

## 🌟 Key Features

1. **The MyTally Bridge window**:
   - A web page (`ui/`) drawn by **pywebview** in Edge WebView2, in light and dark (follows Windows; change it under Settings, This PC). The window title is **MyTally Bridge**; the `.exe` is still `SnehDistribuorsSync.exe`.
   - Where WebView2 or pywebview is missing (some Windows 10 PCs), the same screens open in a **CustomTkinter** window instead. `--classic` forces that window. Both share their logic in `bridge_core.py`, so sign-in, companies and settings behave the same.
   - The page loads nothing from the network and never holds a sign-in token or stored password; it asks the Python side (`webview_app.Api`) for everything.
   - A **health bar** on every page says in one sentence whether sync is working (Up to date, Syncing, Synced just now, something to check, can't reach TallyPrime or the server, paused), with dots for **TallyPrime** and the **Server**. Its button follows the agent's real state: **Sync now**, **Syncing...**, **Retry**, **Resume** or **Sign in again**. **More** holds **Full re-sync...** (asks first), **Pause syncing** and **Hide to tray**.
   - Three pages on the left: **Companies** (the home page), **Activity** (the log) and **Settings**.

2. **First run: sign up or sign this PC in**:
   - Open the company in TallyPrime first; the agent looks for it by itself and shows what it found.
   - **New business**: press **Create an account**, fill in your details, press **Email me a code**, and enter the code on the next screen. This creates the account, its first admin, this PC's device and the first company (the one open in Tally) in one step.
   - **Existing account**: press **My business already uses MyTally**, enter the email and password of someone who holds the **Manage sync agent** permission (admins do by default) and press **Sign in and start syncing**. Everyone else joins the business by invitation from the web app, not from the agent.
   - Either way the PC is signed in **as a device**: it gets its own token and stores no password afterwards. The PC is listed in the web app under Admin → Sync agent & team, where an admin can sign it out.
   - **Advanced** (a link under the button) holds the server address, the TallyPrime address and **Test connection**.

3. **Settings**:
   - **Connection**: the TallyPrime computer and port, and the server address. **Schedule**: how often to send app changes to Tally and to check Tally for changes.
   - **This PC**: start with Windows, and the theme. **Account**: **Sign in as someone else** returns to the sign-in screen. **Support**: open the logs folder or export the logs as a zip.
   - **Advanced**: vouchers sent per request in a full re-sync, finding the Tally program and data folders automatically, and **Re-check every record on each sync (slower)**.
   - **Save** applies the changes and stays on the page.

4. **System Tray & Windows Boot Auto-Start**:
   - Closing the window hides it to the Windows system tray (`pystray`); syncing continues. The tray icon carries a coloured dot for the sync state and its tooltip repeats the health sentence.
   - System tray right-click menu: **Open Bridge**, **Sync now**, **Full re-sync**, **Pause or resume syncing**, and **Quit Bridge**.
   - Toggle switch in Settings or 1-click batch script to automatically start with Windows boot.

5. **Several Companies, Each Bound to Its Tally Identity**:
   - One agent syncs every company linked to this PC. The **Companies** page lists them; a company open in Tally but not yet linked shows under "Open in Tally, not linked" with a **Link** button, and **Unlink** stops syncing one from this PC (its data in the app stays).
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

### For the people who use it: one `.exe`
Nobody who uses the agent needs Python or any of the commands below. They get one file, `SnehDistribuorsSync.exe`, and double-click it; it opens as **MyTally Bridge**. There are two ways to make that file:
- **On GitHub (no Windows PC needed)**: the "Sync agent exe" workflow builds it on every pull request that touches this folder and when run by hand from the Actions tab; download it from the run's Artifacts. Pushing a tag such as `agent-v2.0.0` also attaches it to a GitHub Release, which gives a link to send to people.
- **On a Windows PC**: double-click `installer\build_windows_exe.bat`. The file appears in `dist\`.

The `.exe` is not code-signed, so the first time it runs Windows SmartScreen says "Windows protected your PC": press **More info**, then **Run anyway**.

### 1. Launch Modern GUI
```bash
python gui_app.py
```
Add `--classic` for the CustomTkinter window. To look at the page alone with made-up data, serve this folder (`python -m http.server 8765`) and open `http://localhost:8765/ui/index.html?demo` (`?demo=sync`, `warn`, `error`, `paused` or `setup`; add `&theme=dark`).
*(On first launch, open the company in TallyPrime, then either create an account or sign the PC in with an admin's email and password (the server address is under Advanced). Once connected, settings are saved to `agent_config.json` and the Companies page appears.)*

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
