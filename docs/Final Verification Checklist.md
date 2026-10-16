# Final verification checklist

The one list of everything to do after all phases are built. Nothing here was run against a real TallyPrime or
real Google credentials while building; every automated test used fixtures and fakes. Kept up to date in the same
commit as each change. Branch: `claude/phase2-books-correctness-07b1b7`.

Order: 1 apply → 2 configure → 3 deploy steps → 4 run the suites → 5 real-Tally checks → 6 real-Google checks →
7 read the known gaps.

## 1. Migrations (in order)

There is no Alembic. The backend's startup schema sync (`auto_sync_all_model_schemas`, `create_all` for missing
tables) adds missing columns and creates missing tables on the first start of the new build, on an existing and on
a clean database. Nothing to run by hand; check the start-up log for `Auto Schema Synchronizer: Adding missing
column ...` lines. Back up the database first. In the order the commits added them:

| # | Change | Commit area | Where |
|---|---|---|---|
| 1 | `bank_allocations.bankers_date` (DATE, NULL), `bank_allocations.bank_manual_status` (VARCHAR 30, NULL) | WS-4 | `tally_core.py` `TrnBankAllocation` |
| 2 | tables `tally_key_list_state`, `tally_missing_records` | WS-3 | `portal_core.py` |
| 3 | table `tally_parity_reports` | WS-5 | `portal_core.py` |
| 4 | table `sync_inbound_receipts` (unique `company_id, idempotency_key`) | WS-9 | `portal_core.py` |
| 5 | `company_backups.drive_status`, `drive_file_id`, `drive_error`, `drive_attempts`, `drive_next_retry_at`, `drive_uploaded_at`; tables `google_drive_links`, `drive_file_deletions` | Google Drive | `portal_core.py` |
| 6 | `stock_entries.order_number`, `order_due_date`, `tracking_number`; table `stock_entry_batch_allocations` | WS-11 | `tally_core.py` |
| 7 | `company_backups.encryption_key_id` (VARCHAR 64, NULL); table `backup_drill_results` | WS-13 | `portal_core.py` |

Not a schema change but a data step: existing backup files are encrypted by `python scripts/backup_crypto.py
encrypt-existing` (section 3b), once an active key is set.

After the first start, confirm each exists (`SHOW COLUMNS` / `SHOW TABLES`) before upgrading agents.

## 2. New settings (`backend/.env`)

| Variable | Default | Needed for |
|---|---|---|
| `SYNC_INBOUND_MAX_BYTES` | `536870912` (512 MB) | cap on a `/sync/inbound` body after gzip is undone (WS-8) |
| `GOOGLE_OAUTH_CLIENT_ID` | unset | Google Drive link (all four must be set) |
| `GOOGLE_OAUTH_CLIENT_SECRET` | unset | Google Drive link |
| `GOOGLE_OAUTH_REDIRECT_URI` | unset | Google Drive link; must equal the Cloud console redirect URI |
| `SECRETS_ENCRYPTION_KEY` | unset | Fernet key encrypting stored Google refresh tokens; back it up |
| `APP_PUBLIC_URL` | unset (existing setting) | where the Google callback sends the browser (`<url>/backup`) |
| `BACKUP_ENCRYPTION_KEYS` | unset | `id:base64key,id2:base64key2`, 32-byte keys; every listed key can read (WS-13) |
| `BACKUP_ENCRYPTION_ACTIVE_KEY_ID` | unset (= no encryption) | the key id new backups are written with |
| `BACKUP_RESTORE_NEW_COMPANY_ENABLED` | `false` | restore a backup into a NEW MyTally company (WS-13) |

Per company, in the web app: Admin → Integrations → **Google Drive copy of backups** (off by default).

## 3. Manual deployment steps

1. **Order:** deploy the backend first, then rebuild and redistribute the agent (tag `agent-v*`). Old agents keep
   working against the new backend (no gzip, no key, no active-keys list); new agents work against an old backend
   (they fall back to plain XML and log a 404 for the key list).
2. **Reverse proxy:** body limit at least the largest compressed upload, and the largest *plain* upload while old
   agents remain (100 MB is a sensible floor); `proxy_read_timeout` above 300 s; do not decompress requests at the
   proxy. See runbook "Phase 4 gzip uploads".
3. **Backfill:** one **Sync All** (force full sync) per company after the agent upgrade, to fill bank dates
   (WS-4), header/ledger/stock fields (WS-10) and batch rows (WS-11) for records not altered since.
4. **Google Cloud project** (once): enable Drive API; consent screen with `drive.file`; Web-application OAuth
   client with the backend callback as redirect URI; add test users while in Testing; publish when ready. Steps in
   runbook "Google Drive backup".
5. **Agent code signing (WS-2):** conditional Authenticode step in `agent-exe.yml`; see section 3b when added.
6. **Flags:** features that stay off until chosen are listed in section 7.

### 3b. Added with later workstreams

**WS-13 backup hardening**
1. Generate a key: `cd backend && python3 scripts/backup_crypto.py new-key`. Put it in `BACKUP_ENCRYPTION_KEYS` as
   `k1:<key>` and set `BACKUP_ENCRYPTION_ACTIVE_KEY_ID=k1`; keep the key with your other secrets (a backup cannot
   be read without it). Restart the backend.
2. Encrypt files already on disk: `python3 scripts/backup_crypto.py encrypt-existing` (repeat-safe; a file is replaced
   only after it decrypts back to its recorded SHA-256). Check with `python3 scripts/backup_crypto.py status`.
3. Rotation: add `k2:<new key>` to `BACKUP_ENCRYPTION_KEYS`, set the active id to `k2`, restart, run
   `python3 scripts/backup_crypto.py rewrap`, check `status` shows only `k2`, then remove `k1`.
4. Restore into a new company stays off until you set `BACKUP_RESTORE_NEW_COMPANY_ENABLED=true`; try it first on a
   test account (checks R1-R3 in section 6b).
5. The daily restore drill needs nothing; its first result appears in `/sync/health` `backup_drill` about ten
   minutes after the backend starts.

**WS-12 Tally port detection**
- Agent rebuild only; nothing to configure. The health bar offers "Use this port" only when a port answers and
  names an already-linked company; the configured URL is never changed without the click.

**WS-2 signing and Nuitka comparison**
1. Optional: add repository secrets `WINDOWS_CODESIGN_PFX_BASE64` (the code-signing `.pfx`, base64) and
   `WINDOWS_CODESIGN_PFX_PASSWORD`. The signing step runs only on an `agent-v*` tag and only when both exist; with
   neither, the exe is built unsigned and the log says `Authenticode status: NotSigned`.
2. Nuitka: Actions > Sync agent exe > Run workflow > builder = nuitka. It uploads
   `SnehDistribuorsSync-nuitka-exe-comparison`; it is never attached to a release.

**WS-15 installer**
- Built by CI after the exe (Inno Setup, installed with Chocolatey if the runner lacks it) and attached to the release
  as `MyTallyBridge-Setup-<version>.exe`, signed under the same conditions as the exe. Per-user, no admin, no
  scheduled task; "Start with Windows" stays the agent's own setting.

**WS-14 reconciliation write-back**
1. Rebuild and redistribute the agent (it carries the read-back-and-alter logic); the backend needs no migration.
2. Per company, Admin > Integrations > **Write bank reconciliation back to Tally** (off by default). Pilot it on one
   test company first (checks W1-W4).

## 4. Run the suites (once, at the end)

Backend (from the repo root; about 5 minutes):

```bash
cd backend && python3 -m pytest tests -q
```

Agent (about 20 seconds):

```bash
cd desktop-sync-agent && python3 -m pytest tests -q
```

Frontend type check and build:

```bash
cd frontend-nextjs && npx tsc --noEmit -p . && npm run build
```

Last known results, taken on the tree before the rule to stop running suites: backend **584 passed**, agent
**151 passed**; both predate WS-12/13/14/15 and the remaining WS-2 work, which were written without running.

## 5. Checks that need a REAL TallyPrime

Do these on a test company first. "Expected" is what proves the assumption; if it fails, the note says what to
change.

| # | What to do | Expected | Assumption it tests |
|---|---|---|---|
| T1 | Reconcile an entry in Tally's bank reconciliation, then Sync All; look at `bank_allocations` for that entry and at `GET /bank-recon/unmatched-books` | `bankers_date` and `bank_manual_status` filled; the entry is absent from the list (present with `include_cleared=true`) | `BANKERSDATE` / `BANKMANUALSTATUS` come back inside `BANKALLOCATIONS.LIST` with the current `ALLLEDGERENTRIES.LIST` fetch. If not, add the nested field to `VOUCHER_FETCH` |
| T2 | Send a manual `MyTallyVoucherKeys` request (agent log shows it) after a full sync | One `<VOUCHER>` per voucher with `MASTERID`, `GUID`, `ALTERID`, `DATE`, and `VCHTYPE` or `VOUCHERTYPENAME`; count equals the voucher index | active-keys export field names (WS-3) |
| T3 | Same for `MyTallyLedgerKeys` and `MyTallyStockItemKeys` | `NAME` as attribute or element, `GUID`, `MASTERID`; ledgers also `CLOSINGBALANCE` | master key export names; `CLOSINGBALANCE` sign (negative = debit) used by the parity check (WS-5) |
| T4 | Delete a voucher in Tally; wait two key lists (a full sync, then an hour or a second Sync All) | Voucher is cancelled in MyTally, `tally_missing_records.status = 'deleted'`, `/sync/health` `deleted_in_tally_count` = 1; re-creating it restores it | WS-3 end to end, including that a Tally delete really drops the key from the export |
| T5 | Open the same company copied to another data folder (different fingerprint) | No key list is sent; agent log says the open company does not match | fingerprint gate (`COMPANYNUMBER\|BOOKSFROM`) |
| T6 | Run the `MyTallyChangeProbe` request; save a voucher; alter a master | Both `ALTMSTID` and `ALTVCHID` come back as numbers; the vouchers counter rises on a voucher save, the masters one on a master alter | WS-7 field names. If they do not rise, set `PROBE_SAFETY_PASS_SECONDS = 0` in `agent.py` |
| T7 | Sync All of a pilot company; read the agent log lines `📏 '...' bytes` | Every collection finishes under its timeout; vouchers import | WS-10: unknown or extra FETCH tags are ignored and exports stay in time. If one times out, trim the fetch constant named in the runbook |
| T8 | After T7 check a voucher with a party reference, place of supply, buyer address, an e-invoiced voucher and one with an e-way bill | `reference_number`, `place_of_supply`, `buyer_*`, `irn*`, `eway_bills` populated | voucher-header tags (`REFERENCE`, `PLACEOFSUPPLY`, `BASICBUYERNAME`, `BASICBUYERADDRESS.LIST`, `IRN*`, `EWAYBILLDETAILS.LIST`, `ISINVOICE`, `PERSISTEDVIEW`) |
| T9 | Check a ledger with credit limit/period, contact, MSME, lower TDS; a stock item with HSN and an alias | the matching columns/rows filled | WS-10 ledger and stock-item families |
| T10 | Check currencies and price levels after Sync All | Currency rows updated, price levels created | WS-10 `Currency` / `PriceLevel` collections and tag names |
| T11 | Enter a Delivery Note with two batches, two godowns and an order number | one `stock_entries` row, two `stock_entry_batch_allocations` rows, `order_number`/`tracking_number` set | WS-11 tags (`BATCHALLOCATIONS.LIST`, `BATCHNAME`, `GODOWNNAME`, `DESTINATIONGODOWNNAME`, `ORDERNO`, `ORDERDUEDATE`, `TRACKINGNUMBER`) and whether order refs sit on the line or in the allocation |
| T12 | Compare `/sync/health` `books_parity` for a fully synced company with Tally's Trial Balance | zero drifting ledgers; Sales/Purchase Order and Delivery/Receipt Note not counted in the trial balance | WS-5 sign and period assumptions; the `NON_POSTING` type list |
| T13 | Lose a response on purpose (stop the backend mid-import, restart, let the agent retry) | Second attempt returns the stored answer or imports once; no duplicates | WS-9 stale-PROCESSING takeover timing |
| T14 | Upload a large export with gzip through the real proxy | 200, smaller request; an upload above the cap gets 413 | WS-8 and the production proxy limits |

## 5a. Results of the live read-only run (TallyPrime at 192.168.1.50:9000, company "Sneh Distributors")

Read-only requests only; nothing was written to Tally.

| Check | Result |
|---|---|
| Connection, open companies, fingerprint | OK. One open company; fingerprint `100000|20250401`. Release and data path are not returned by `discover_tally_host` (app path is). |
| T2 voucher keys | **Passes.** 1234 keys with MASTERID, GUID, ALTERID, DATE and type; equals the voucher index count (1234). |
| T3 master keys | **Found and fixed a bug:** the CMPINFO counts block (`<LEDGER>217</LEDGER>`) was read as an object, giving an empty key and one extra count. Fixed in `master_keys`; now 190 ledgers and 536 stock items, none incomplete. `NAME` is an attribute, `MASTERID` carries `TYPE="Number"` and a leading space (handled). |
| T3 closing balance sign | A debtor ledger shows `-62018.64`, so negative = debit as assumed. 159 of 190 ledgers return one (blank = zero). |
| T6 change probe | Returns numbers: masters 1143, vouchers 1733. Whether they rise on a save is still to be tried (needs a write). |

New findings to act on:
- **CMPINFO counts are unreliable** (217 ledgers / 252 stock items against 190 / 536 returned). Never use them as a completeness gate; the voucher index count is the gate and it matched.
- **Stock item `CLOSINGBALANCE` is a quantity with a unit** (`690 PCS`), not an amount. Make sure the parity check reads `closing_balance` only for ledgers.

### 5b. Server-side checks that need real data (no Tally, no Google)

| # | What to do | Expected | Assumption it tests |
|---|---|---|---|
| R1 | With a key set, finish a real backup from an agent, then download it from the Backup page | The file on disk starts with `MTBKENC1`; the download opens as a ZIP | encryption at rest end to end |
| R2 | Turn `BACKUP_RESTORE_NEW_COMPANY_ENABLED` on; restore a real backup into a new company (`POST /backups/{id}/restore-new-company`) | A new company with the same ledger, stock item and voucher counts as the manifest; `verified: true` | the importer accepts the agent's real archive in dependency order; manifest counts match what the importer stores |
| R3 | Compare the new company's trial balance with the source company's for the same date | same figures | restore fidelity |
| R4 | Damage a stored backup file on a test server, wait for the drill (or call `drill_all`) | `/sync/health` shows `backup_drill.ok = false` and status degraded | drill reporting |

### 5c. WS-12 port detection (real TallyPrime)

| # | What to do | Expected | Assumption it tests |
|---|---|---|---|
| P1 | In TallyPrime set the XML server port to 9001 (F1 > Settings > Connectivity) while the agent still points at 9000 | Within about a minute the health bar says "TallyPrime is on port 9001 ... Use that port?"; clicking switches and syncing resumes | `tally.ini` `ServerPort` location and format, and that a probe on another port returns the open companies |
| P2 | Close TallyPrime | Message: "TallyPrime isn't running on this PC" | `tasklist /FI "IMAGENAME eq tally.exe"` output on the customer's Windows |
| P3 | Open TallyPrime with the XML server off | Message names F1 > Settings > Connectivity | the wording matches TallyPrime's actual menu path in the installed release |

### 5d. WS-2 signing (real certificate, Windows)

| # | What to do | Expected | Assumption it tests |
|---|---|---|---|
| S1 | Push an `agent-v*` tag with the two secrets set | Workflow log shows `Successfully verified` and `Authenticode status: Valid`; the released exe shows the publisher in Properties > Digital Signatures | signtool path on `windows-latest`, timestamp server reachable, PFX password handling |
| S2 | Push a tag with the secrets missing | Build succeeds, unsigned, signing step skipped | the conditional really skips (a secret in `if:` is read through job `env`) |
| S3 | Run the workflow manually with builder = nuitka | A comparison artifact appears; the normal exe is unchanged | Nuitka flags build this app (they were not tried) |

### 5e. WS-15 installer (Windows)

| # | What to do | Expected | Assumption it tests |
|---|---|---|---|
| I1 | Run `MyTallyBridge-Setup-<version>.exe` as a standard (non-admin) user | Installs without a UAC prompt under `%LOCALAPPDATA%\Programs\MyTally Bridge`; Start menu entry; app opens | `PrivilegesRequired=lowest` and `{autopf}` resolving per-user |
| I2 | Check `schtasks /query` and the HKCU Run key after install | No MyTally entry from the installer | no autostart is added by the installer |
| I3 | Uninstall from Settings > Apps | Program removed; sign-in, settings and backups folder remain | user data untouched |
| I4 | Install over an older version while the agent runs | The old agent is closed and the new one installed | `CloseApplications=yes` |

### 5f. WS-14 reconciliation write-back (real TallyPrime)

| # | What to do | Expected | Assumption it tests |
|---|---|---|---|
| W1 | On a test company switch the integration on, then `POST /bank-recon/writeback` for a receipt with one bank allocation (`bankers_date`, `manual_status`) | Within a cycle the voucher shows the bank date in Tally's Bank Reconciliation; MyTally then holds the same values and the new AlterID | `FETCH *` of a voucher returns a complete voucher that Tally accepts back as an Alter addressed by `TAGNAME=MASTERID` + `DATE` without changing anything else |
| W2 | Compare the voucher before and after (narration, entries, bill and cost-centre allocations, GST fields) | Identical except `BANKERSDATE` / `BANKMANUALSTATUS` | the read-modify-write preserves nested lists the importer does not model |
| W3 | Alter the voucher in Tally, then queue a write-back using MyTally's stale AlterID | Outcome `stale`; the request shows FAILED with the reason; Tally untouched | AlterID comparison (the value format `<ALTERID> 9</ALTERID>` is trimmed) |
| W4 | Queue the same values twice | Second is `unchanged` (or `already` if Tally already holds them); no second Tally voucher, no AlterID change on repeat | idempotency end to end |

## 6. Checks that need REAL Google credentials

| # | What to do | Expected | Assumption it tests |
|---|---|---|---|
| G1 | Backup page → Connect Google Drive, sign in, allow | Returns to `/backup?drive=linked`; card shows the account; a `MyTally Backups/<company>` folder exists | OAuth redirect URI match, consent screen, scope `drive.file` |
| G2 | Make a backup (Back up now) | File `<backup key>.zip` appears; backup line says "In Google Drive" | resumable upload, MD5/size verification |
| G3 | Repeat the copy (Copy waiting backups) | no second file | idempotency by stored id and by name + properties against real Drive |
| G4 | Remove MyTally at myaccount.google.com/permissions, then back up again | Card says Reconnect; backups stay "Waiting" | revoked-token response is `invalid_grant` |
| G5 | Fill the Drive (or use a nearly full account) | "Google Drive is full" message and retries | real quota error reason string `storageQuotaExceeded` |
| G6 | Disconnect | Token revoked, link gone, files remain | revoke endpoint |
| G7 | Leave the app in Testing mode for 8 days | Link asks to Reconnect after about 7 days | refresh-token lifetime in Testing |
| G8 | Delete a backup by retention (or age one) | its Drive file is deleted; a file you added by hand to the folder is not | retention deletes only recorded, tagged files |

## 7. Known gaps and decisions deferred

- Groups, voucher types and other masters are not reconciled for deletion (no active flag); only vouchers, ledgers
  and stock items.
- Books parity compares the whole voucher history with Tally's closing balance; a company with several open
  financial years may show a constant offset (see T12).
- Stock item MRP, BOM, price lists, reorder, standard cost/price, part number and unit UQC are not exported: the
  importer does not parse them (`docs/Export Field Coverage Matrix.md`).
- Receipt and import for `/sync/inbound` are not one transaction (the importer commits in steps); recovery is the
  stale-PROCESSING takeover.
- Google Workspace shared drives and one Drive for several companies are not supported.
- The Drive retention delete is best effort (8 tries, then the file stays in the user's Drive).
- Other reports (daybook, P&L, balance sheet) were not audited for order/delivery-note rows after the trial
  balance fix.
- "Re-sync this ledger's vouchers" from the parity report was not built.
- **Written but never run** (the user's rule was to run no suites while building; run them in section 4 and expect
  small fixes on the first run): backend `test_backup_hardening.py` (WS-13), `test_reconcile_writeback.py` (WS-14);
  agent `test_tally_ports.py` (WS-12), `test_reconcile_writeback.py` (WS-14), `test_installer_script.py` (WS-15).
  Code from WS-12 to WS-15 was only syntax-checked (`py_compile`); the CI workflow was only parsed as YAML.
- WS-13 restore into a new company writes into MyTally from the archive (nothing goes to Tally) and binds the new
  company to the backup's GUID only when no other company of the account holds it, so a restore beside the original
  stays unbound by design.
- WS-14 writes one bank allocation per request and refuses an ambiguous match; there is no bulk write-back.
- WS-12 offers a port only for a company already linked to the PC; a first-time setup on a non-default port is
  still manual.
- Not built by decision: S3 off-site backup (covered by Google Drive), the string vault, PyArmor, anti-debug,
  JSONEx (WS-17).

### 5a-2. Live run on the test VM (TallyPrime at 192.168.71.130:9001, "Bhrama Enterprises", 44 vouchers)

- **T7 timing:** with the fix below, a full export of 14 collections finishes in 0.3 s, no failures; vouchers are 335 KB.
- **BUG FOUND AND FIXED: a `PriceLevel` collection request hangs TallyPrime.** It never answered, the next request (`UOMs`) timed out too, and the XML server stayed dead until Tally was restarted. The request is no longer sent. Never add a PriceLevel collection export again; read price levels from stock item price lists or the ledger's `PRICELEVEL`.
- **BUG FOUND AND FIXED (WS-11): "Not Applicable" was stored as an order and tracking number.** Real Tally writes `<ORDERNO>` / `<TRACKINGNUMBER>` as "Not Applicable" (behind a control character) on all 88 batch lines of the test company. The importer now treats that as no reference. Real tracking numbers `T001` / `T003` are read correctly.
- **Real batch lines carry no `GODOWNNAME`** when godowns are not enabled for the voucher; quantities arrive as ` 100 nos`. Both are handled.
- **BUG FOUND AND FIXED (WS-14): `fetch_voucher_block` always returned nothing.** Tally's `CMPINFO` counts hold `<VOUCHER>44</VOUCHER>`, so two "vouchers" were found and the code refused to guess. Every reconcile write-back would have failed with "Tally did not return exactly one voucher". Fixed (CMPINFO is dropped first, and the request now names the full date range). Verified live: a full block (about 24 KB) comes back for masters 1, 3, 14 and 139.
- **T2 / T3 / T4 / T6 / T11 verified live** (writes done on the test company, all test records removed afterwards; company is back to 44 vouchers):
  - T4 at Tally level: deleting a voucher by `DATE` + `TAGNAME="MASTERID"` after checking its narration removes it from the voucher keys (46 to 45).
  - T6: the master counter rose on ledger create, alter and delete (845 to 846, 847, 848) and did not move on voucher changes; the voucher counter rose on voucher create and delete and did not move on master changes. So `AltMstId` / `AltVchId` are right.
  - Repeat-safety: sending the same voucher twice under one `REMOTEID` gives `ALTERED 1`, never a second voucher.
  - T11: a Delivery Note with one line and two batch allocations comes back as two `BATCHALLOCATIONS.LIST` under one line, `TRACKINGNUMBER` on each allocation, and the parser yields two rows with tracking `T-LIVE-1`. No `GODOWNNAME` comes back when godowns are not enabled on vouchers, so two allocations in different godowns cannot be told apart in this company.
  - T8: all voucher-header tags are present in every voucher (`REFERENCE`, `EFFECTIVEDATE`, `PLACEOFSUPPLY`, `BASICBUYERNAME`, `IRN`, `EWAYBILLDETAILS.LIST`, `ISINVOICE`, `PERSISTEDVIEW`, `ISPOSTDATED`, `CONSIGNEEMAILINGNAME`); values were mostly empty in this company. `PARTYGSTIN` was never returned.
- **STILL OPEN, needs a Tally setting (T1, W1-W4):** this company has no bank allocations at all, and Tally silently drops `BANKALLOCATIONS.LIST` sent by import (tried `Cheque/DD` and MyTally's `Others` + `PAYMENTMODE Transacted`; the block comes back without it). Enable bank allocation entry in the test company's Receipt/Payment voucher configuration (F12), or enter one Receipt against HDFC BANK A/c with a cheque number by hand, then re-run.
- **Voucher dates after 2025-08-31 were rejected** ("Voucher date is missing", really out of the company's period); test vouchers used 2025-07-01.
