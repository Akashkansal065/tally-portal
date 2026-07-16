# Running Tally Sync on a Distributed Network

Since Tally Prime is installed on a different system (e.g. a Windows PC) and the Web ERP codebase is hosted on another server/machine, you can run the sync daemon on the Tally machine by following these steps:

---

## 1. Prerequisites on the Tally Machine
Ensure the machine running Tally Prime has:
1. **Python 3.x** installed.
2. **Tally Prime** running with the **XML Server** enabled on port `9000`.
   - To enable: `Help (F1) > Settings > Connectivity > Set Client/Server Configuration` and set TallyPrime to **Both** on port `9000`.

---

## 2. Copy the Sync Daemon to the Tally Machine
You only need a single file on the Tally machine. Copy the `tally_sync_daemon.py` script to any folder on the Tally machine:
- File path in this repo: [tally_sync_daemon.py](file:///Users/akashkansal/Documents/Github/MyTally/backend/scratch/tally_sync_daemon.py)

---

## 3. Configure the Daemon
The daemon can be configured dynamically without editing the script code directly. You have two options:

### Option A: Create a `.env` File (Recommended)
Create a file named `.env` in the same directory as `tally_sync_daemon.py` and populate your credentials and URLs:
```env
# The local Tally Prime URL (using 127.0.0.1 avoids IPv6 localhost lookup timeouts)
TALLY_URL=http://127.0.0.1:9000

# Change this to your Web ERP server URL or ngrok domain
ERP_URL=https://evolved-eagerly-mule.ngrok-free.app

# ERP Credentials
ERP_EMAIL=akashkansal065@gmail.com
ERP_PASSWORD=your_secure_password

# Sync interval in seconds
SYNC_FREQUENCY=120
```

### Option B: Set Environment Variables
You can export environment variables in your terminal shell:
- `TALLY_URL`
- `ERP_URL`
- `ERP_EMAIL`
- `ERP_PASSWORD`
- `SYNC_FREQUENCY`

---

## 4. Run the Daemon
On the Tally machine, open a command prompt (CMD) or terminal in the folder containing `tally_sync_daemon.py` and run:

```bash
python tally_sync_daemon.py
```
*(Or specify command line arguments from Option B)*

The daemon will:
1. Authenticate against the ERP server and fetch a JWT token (printing clean error details if authentication fails).
2. Fetch pending outbound sync requests from ERP and push them to local Tally.
3. Query Tally Prime for incremental ledger/voucher modifications using standard `<TDLMESSAGE>` syntax and sync them back to ERP.

