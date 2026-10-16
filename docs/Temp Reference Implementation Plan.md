# docs/temp Reference Review and Implementation Plan

**Status:** Plan only. No code has changed. Each workstream below is meant to be picked up on its own, refined into a file-by-file change list, and shipped behind its own tests.

**Date of review:** 2026-10-15

**Related documents:** this plan supersedes the gap claims in [Desktop_Sync_Agent_Architectural_Upgrade_Blueprint.md](Desktop_Sync_Agent_Architectural_Upgrade_Blueprint.md) (several are wrong, see §3) and absorbs Tracks A–D of [reference-integration-plan.md](reference-integration-plan.md), which are still open.

---

## 1. What was reviewed

`docs/temp/` holds 20 files but only **10 unique ones**. Every `(1)`, `(2)`, `(3)` and `copy` variant is byte-identical to its original (same MD5).

| File | Lines | What it is |
|---|---|---|
| `tally_sync_connector.py` | 3,663 | Zero-dependency Tally connector: XML and JSONEx request builders for every master and voucher type, parsers, a SQLite hash-based delta store, a gzip + idempotency-key micro-batch pusher, and a mock Tally server for self-tests |
| `fastapi_mysql_backend.py` | 2,171 | FastAPI + PyMySQL server: REST CRUD per master, an outbound command queue, an idempotency log for sync batches, backup upload/download, BI views, device pairing |
| `mysql_schema.sql` | 702 | 12 name-keyed tables, normalized `trn_*` line tables, and 3 BI views (ledger closing balance, bill aging, de-duplicated inventory movement) |
| `tally_backup_restore.py` | 1,271 | Backup bundles (logical XML/JSON plus a zip of Tally's `Data\<number>` folder), passphrase encryption, Local / Server / S3 (SigV4) storage, and a dependency-ordered restore |
| `tally_desktop_gui.py` | 1,556 | Tkinter GUI, anti-debug "runtime shield", machine-bound config vault, Tally install/port/process detection, auto-launch of `tally.exe` |
| `build_hardened_exe.py` | 434 | AST string-literal encryption, Cython, optional PyArmor, then Nuitka one-file build |
| `TallyPrimeSync_Installer.iss` | 60 | Inno Setup installer: shortcuts, HKCU Run autostart, a 15-minute `schtasks` headless job |
| `build_windows_release.bat` | 53 | Runs the four self-tests, then the hardened build and the installer |
| `production_deployment_runbook.md` | 132 | How the above fit together, plus a list of what it took from "desktop-sync-agent.zip" and "Archive.zip" |

### Provenance: much of this came from MyTally

The runbook (§6) says outright that it was built by reading **MyTally's own** `desktop-sync-agent` and backend ("MyTally Bridge", `SnehDistribuorsSync.exe`). Functions such as `plan_voucher_ranges`, `voucher_dates`, `tally_date_text`, `export_voucher_index`, `_TALLY_LOCK`, `discover_tally_host`, `voucher_address_attrs`, `remove_tally_ghost`, `keys_to_keep`, `extract_raw_object_blocks`, the company fingerprint, and the pairing code flow are copies of code MyTally already has. Those are listed in §2 so nobody ports them back.

What is genuinely new is: wider Tally field coverage, JSONEx builders, gzip/idempotent uploads, the report-snapshot idea, Tally install/port detection, backup encryption and off-site storage, the hardened build, and an installer. Each is assessed below.

---

## 2. Already in MyTally: do not re-port

| Reference feature | Where MyTally already has it |
|---|---|
| One-request-at-a-time lock for Tally | `desktop-sync-agent/tally_client.py:18` (`_TALLY_LOCK`, held until the response is read) |
| Density-adaptive voucher date ranges, `sv`/`filter` fallback, resumable cursor | `desktop-sync-agent/agent.py:49` (`plan_voucher_ranges`), `agent.py:1135` (`_sync_vouchers_in_ranges`), `tally_client.py:525` |
| Voucher index export (`DATE,MASTERID`) and text-based date scan | `tally_client.py:548`, `tally_client.py:78` |
| Separate master and voucher AlterID watermarks, retry floors | `backend/app/routers/sync.py:1172` (`/sync/last-alter-id`), `agent.py:1208` |
| `$$ApplicationPath` / `$$DataPath` / `$$Release` discovery | `tally_client.py:249` |
| Ghost-master detection and removal (ALTERID 0) | `backend/app/routers/sync.py:2657`, `sync.py:3206` |
| Addressing existing vouchers by MASTERID + DATE, REMOTEID for app-created ones | `TrnVoucher.tally_master_id` / `tally_remote_id` / `tally_date` in `backend/app/models/tally_core.py:670`; `find_voucher_by_master_id` / `find_voucher_by_remote_id` in `tally_client.py:638,674` |
| Company copy fingerprint (`number|books_from`) | `tally_client.py:392` and the binding check in the backend |
| Device pairing with a short code and scoped device tokens | `backend/app/routers/agent.py`, `backend/app/core/agent_auth.py` |
| Multi-company isolation | Company bound by Tally GUID, not name (`desktop-sync-agent/README.md` §5); tenant scope by `company_id` everywhere |
| One import per company at a time (cross-process) | `backend/app/core/sync_guard.py` (MySQL `GET_LOCK`) |
| Request idempotency for app writes | `backend/app/core/idempotency.py` (note: `/sync/inbound` is skipped, see WS-9) |
| Normalized voucher lines | `voucher_entries`, `bill_allocations`, `bills`, `bank_allocations`, `voucher_entry_cost_centres`, `stock_entries`, `batches` in `tally_core.py` |
| BOM, price levels, standard cost/price, HSN, e-way bill, GST effective rate, opening bill/batch allocation tables | `stock_item_boms`, `price_levels`, `stock_item_price_level_rates`, `mst_stockitem_standard_cost/price`, `hsn_details`, `eway_bills`, `mst_gst_effective_rate`, `mst_opening_bill_allocation` in `tally_core.py` |
| Hourly ZIP backups, 7-day retention, raw-block export (UDF-safe), chunked resumable upload with SHA-256, restore into the same company | `desktop-sync-agent/backups.py`, `backend/app/routers/backups.py`, `backend/app/services/backups.py` |
| Secrets at rest on the PC | `desktop-sync-agent/security.py`: Windows Credential Manager via `keyring`, Fernet fallback, never plaintext. Better than the reference's home-made vault. |
| CI build of the agent `.exe` with tests first | `.github/workflows/agent-exe.yml` |

---

## 3. Corrections to the existing Blueprint document

[Desktop_Sync_Agent_Architectural_Upgrade_Blueprint.md](Desktop_Sync_Agent_Architectural_Upgrade_Blueprint.md) was written from these same temp files and describes the current code incorrectly in several rows. It should be annotated (or retired) so it doesn't drive work.

| Blueprint claim about "current" MyTally | What the code actually does |
|---|---|
| Secrets in "plaintext or fixed-salt AES config files" | OS credential vault via `keyring`; Fernet fallback; no plaintext (`security.py`) |
| "Single-company watermark tracking" | Per-company watermarks; companies bound by GUID; several companies synced per PC |
| "Shared API tokens entered manually" | Pairing code plus per-device tokens already exist |
| "Basic date-chunking or full DayBook scan" | Density-adaptive planner with day-safe ranges and resumable cursors |
| "Restore fails on dependencies" | Restore writes masters before vouchers in a fixed order (`backups.py:447`, `backup_module` restore) |
| "Hardcoded `http://127.0.0.1:9000`" | Partly true: it is the default (`bridge_core.py:25`) but is user-configurable under Advanced. Auto-detection is a real gap (WS-12). |
| "Alt+D deletions in Tally stay forever" | **True.** Confirmed gap (WS-3). |
| "Cleartext `.py` files inside the exe" | **True.** `installer/build_exe.py:24-25` adds every module as `--add-data`. Confirmed gap (WS-2). |

---

## 4. Do not adopt: defects and unsafe patterns in the reference code

These are bugs or risks in `docs/temp`. Some contradict MyTally's own rules (idempotency, verify-before-delete).

| # | Reference location | Problem | Why it matters |
|---|---|---|---|
| 1 | `tally_sync_connector.py:1947-1948` | `build_create_voucher_request` puts Tally's **GUID in `REMOTEID`**. The file's own `voucher_address_attrs()` says this creates duplicates, but the builder never uses that helper. | Duplicate vouchers in Tally. MyTally already does this correctly. |
| 2 | `tally_sync_connector.py:2044-2095` | Bank reconciliation is sent as `ACTION="Alter"` with only **two ledger lines** rebuilt from the request. | An Alter replaces the voucher's lists, so every other line, bill allocation, cost-centre split and inventory line would be wiped. See WS-14 for the safe way. |
| 3 | `tally_backup_restore.py:902-906` | Restore **invents a "Suspense A/c" line** for any voucher with a single entry. | Fabricates accounting entries in the customer's books. |
| 4 | `tally_backup_restore.py:578` and `tally_backup_restore.py:955` | `zipfile.extractall()` with no path check (zip slip); restore again passes the Tally GUID as REMOTEID (same as #1). | Path traversal on restore; duplicate vouchers. **MyTally has the same zip-slip pattern** in `backend/backup_module/storage.py:50` (WS-1). |
| 5 | `tally_backup_restore.py:152-162`, `tally_desktop_gui.py:226-236` | Home-made XOR stream cipher built from HMAC-SHA256 in pure Python (slow, unreviewed). | Use `cryptography` AES-GCM or Fernet if encryption is needed. |
| 6 | `tally_backup_restore.py:547-581` | Zips and restores Tally's binary `Data\<number>` folder (`.900` files) while Tally may have it open. | A copy taken while Tally writes can be inconsistent; extracting over a live data folder can corrupt the company. |
| 7 | `tally_desktop_gui.py:116-122, 125-150, 168-203` | "Runtime shield": exits the process if a 500-iteration loop takes over 85 ms, or if Wireshark, Fiddler, Process Hacker etc. are running; a watchdog thread calls `os._exit(1)` every 5 s. | Kills sync on slow or busy PCs and on IT-admin machines; looks like malware to antivirus heuristics. Secrets aren't in the binary anyway (device tokens live in Credential Manager). |
| 8 | `build_hardened_exe.py:24-170` | String "vault": literals XOR'd with a key that ships in the same file. | Obscurity only. Nuitka alone gives most of the benefit (WS-2 option). |
| 9 | `tally_sync_connector.py:1000-1013` | "AlterID watermark" reads `Company.AlterId`. | Not the counter Tally keeps for masters/vouchers. The right fields are the company's `AltMstId` / `AltVchId` (already noted in `sync.py:1186`). See WS-7. |
| 10 | `fastapi_mysql_backend.py:1087-1114` | Auth is skipped entirely when `TALLY_API_TOKEN` is empty; HMAC is checked only if the header is present. | Open API by default. |
| 11 | `fastapi_mysql_backend.py` (whole file), `mysql_schema.sql` | Tenancy by `company_name`; `DELETE /companies/{name}`; f-string table names (`:1005`). | MyTally scopes by `company_id`; never copy this layer. |
| 12 | `fastapi_mysql_backend.py:1784-1791` | Large batches handed to FastAPI `BackgroundTasks` and reported as `PROCESSING`. | Lost on restart; not durable. Needs a real receipt table (WS-9). |
| 13 | `fastapi_mysql_backend.py:1879`, schema `archive_blob LONGBLOB` | Backups sent as base64 inside JSON and stored as a DB blob. | Memory blow-up and DB bloat; MyTally's chunked file upload is better. |
| 14 | `tally_desktop_gui.py:1004-1006` | `DELETE_*` commands derive the Tally tag from the command name and delete **by name**. | Violates "address by master id or stored REMOTEID only". |
| 15 | `mysql_schema.sql:623-664` | Inventory "de-duplication" by tracking number via `ROW_NUMBER()`. | Unvalidated accounting rule; can hide real movements. |
| 16 | `TallyPrimeSync_Installer.iss:56` | A 15-minute `schtasks` job running `--headless-once` next to the tray app. | Two agents at once. MyTally holds a single-instance lock; a scheduled task would fight it. |
| 17 | `tally_desktop_gui.py:560-563` | S3 access and secret keys stored on the customer's PC. | Long-lived cloud credentials on every desktop. Off-site copies should be made server-side (WS-13). |

---

## 5. Workstreams (what to implement)

Priority: **P0** safety/security (do first, small) · **P1** books correctness · **P2** reliability/performance · **P3** product features or optional.
Effort: **S** ≤ 1 day · **M** 2–5 days · **L** > 1 week.

Every workstream must follow the standing rules:
- **Repeat-safe:** a retried or re-run step never creates a duplicate in MyTally or Tally.
- **Tally deletes and alters** are addressed by master id (+ date) or stored REMOTEID only, after checking the target's content.
- **Manual deployment steps** (migrations, env vars, flags) are added to [Multi-Tenant Rollout Runbook.md](Multi-Tenant%20Rollout%20Runbook.md) in the same change.

### Summary

| ID | Workstream | Priority | Effort | Source in docs/temp |
|---|---|---|---|---|
| WS-1 | Safe ZIP extraction in `backup_module` | P0 | S | defect #4 |
| WS-2 | Stop shipping `.py` source in the agent `.exe`; code-sign it | P0 | S (+M optional) | runbook §6, `build_hardened_exe.py` |
| WS-3 | Reconcile records deleted inside Tally (Alt+D) | P1 | M | blueprint "Algorithm B" |
| WS-4 | Keep Tally's bank reconciliation dates (`BANKERSDATE`) | P1 | S | connector `BankAllocation` |
| WS-5 | Books-parity check against Tally's own balances | P1 | M | connector `fetch_report_snapshot` |
| WS-6 | Tolerant parsing of Tally numbers and names | P1 | S | `clean_tally_float`, `clean_tally_parent` |
| WS-7 | Cheap "anything changed?" probe before each inbound cycle | P2 | S | connector `build_alter_id_watermark_request` (fixed) |
| WS-8 | Gzip the agent's uploads | P2 | S–M | connector `push_dirty_records_resilient` |
| WS-9 | Durable receipts for `/sync/inbound` | P2 | L | backend `tally_sync_idempotency_log` |
| WS-10 | Export field coverage (ledger, item, voucher header, currencies, price levels, BOM) | P2 | M–L | connector fetch lists and builders |
| WS-11 | Inventory order, tracking and batch lines | P2 | M | connector `BatchAllocation` |
| WS-12 | Find Tally's port automatically | P3 | S–M | GUI `TallyEnvironmentDetector` |
| WS-13 | Backup hardening: encryption at rest, off-site copy, restore to a new company | P3 | M–L | `tally_backup_restore.py` |
| WS-14 | Write reconciliation dates back to Tally | P3 | M | connector `build_reconcile_voucher_bank_entry_request` (fixed) |
| WS-15 | Proper Windows installer | P3 | S–M | `TallyPrimeSync_Installer.iss` |
| WS-16 | Reusable mock-Tally test harness | P3 | S | connector `_MockTallyHandler` |
| WS-17 | JSONEx wire format | Deferred | L | `TallyJSONExBuilder` |

---

### WS-1 · Safe ZIP extraction (P0, S)

**Gap:** `backend/backup_module/storage.py:50` calls `zipf.extractall(target_dir)` on backup archives. A crafted archive with `../` or absolute member names writes outside `target_dir`.

**Steps**
1. Replace `extractall` with a member-by-member extract that resolves each target path and rejects anything outside `target_dir`, absolute paths, and symlinks.
2. Cap total uncompressed size and member count (protects against zip bombs).
3. Grep the repo for any other `extractall` / `ZipFile(...).extract` and apply the same helper. The agent's restore reads members by name; confirm it never writes member paths to disk.

**Tests:** archive with `../evil`, absolute path, oversized member; normal backup still restores.

**Acceptance:** no file can be written outside the target folder; existing restore tests pass.

---

### WS-2 · Agent binary: stop shipping source, sign the `.exe` (P0, S; optional M)

**Gap:** `desktop-sync-agent/installer/build_exe.py:10,24-25` passes every module (`security.py`, `config.py`, `agent.py`, `tally_client.py`, `cloud_client.py`, `backups.py`, `bridge_core.py`, `webview_app.py`) as `--add-data`, so the readable `.py` source sits inside the `.exe` next to the compiled bytecode. The comment says they are "read at run time from beside the program", but the frozen app does not appear to need them: autostart uses `sys.executable` when frozen (`config.py:202-203`), and `bridge_core.py:157` looks up only `ui/` and `assets/` files.

**Steps**
1. Confirm nothing reads those `.py` files at run time when frozen (grep `_MEIPASS` and `get_app_dir()` uses). Then remove the `--add-data` loop for modules; keep `assets` and `ui`.
2. Add a CI assertion in `agent-exe.yml`: unpack the built `.exe` (`pyi-archive_viewer` listing) and fail if any `*.py` is present.
3. **Code signing** (bigger real-world win than obfuscation): sign with an Authenticode certificate in CI so SmartScreen stops warning (README: "The `.exe` is not code-signed"). Store the certificate as a GitHub secret; sign only on tagged releases.
4. *Optional (M):* a Nuitka build job behind a manual workflow input. Compare size, start-up time and antivirus false positives against PyInstaller before switching. **Do not** adopt the string vault, PyArmor, or the runtime anti-debug shield (§4 #7, #8).

**Acceptance:** the released `.exe` contains no `.py` files, runs the same smoke test in CI, and (once a certificate exists) is signed.

---

### WS-3 · Reconcile records deleted inside Tally (P1, M)

**Gap:** When a user deletes a voucher or master in Tally (Alt+D), nothing tells MyTally. AlterID-filtered exports only return objects that still exist, and the importer has no "seen in this full export" pass (`tally_xml_importer.py` has no absent-record handling). Deleted vouchers stay in reports and balances.

**Design**
1. **Agent:** a light "active keys" export per company, using the existing voucher-index style request but fetching `MASTERID,GUID,ALTERID,DATE` (vouchers) and `MASTERID,GUID,NAME` per master type. Run it on a slow cadence (e.g. hourly and after each full sync), not every cycle.
2. **Completeness gate:** only send the list when the export is whole: voucher count must equal the count from the voucher index, the company GUID and fingerprint must match the bound company, and the export must not have failed for any type. A partial list must never be treated as "everything else was deleted".
3. **Server:** set-difference against `tally_master_id`/`tally_guid` for that `company_id`. Records missing from **two consecutive complete lists** are **soft-deleted** (`status`/flag plus an audit row with the last-seen AlterID), never hard-deleted.
4. Exclusions: app-created records not yet confirmed in Tally (`number_is_provisional`, pending outbound queue items), and anything pushed after the list was taken.
5. Surface the result in sync health ("3 vouchers were deleted in Tally and removed from reports") and allow undo by re-importing.

**Tests:** complete list with one missing voucher (deleted after second list), partial export (nothing deleted), company copy (refused), voucher created in the app but not yet in Tally (kept), duplicate/repeated list (idempotent).

**Acceptance:** a voucher deleted in Tally disappears from MyTally's reports within two list cycles; a timeout or partial export never removes anything.

---

### WS-4 · Keep Tally's bank reconciliation dates (P1, S)

Same as Track A of [reference-integration-plan.md](reference-integration-plan.md); still not implemented (`TrnBankAllocation`, `tally_core.py:821`, has no such columns).

**Steps**
1. Add nullable `bankers_date` (Date) and `bank_manual_status` (String) to `TrnBankAllocation`, with a migration.
2. Parse `BANKERSDATE` and `BANKMANUALSTATUS` in the bank-allocation branch of `tally_xml_importer.py`. Absent or malformed values must not fail the import.
3. Confirm with a real export that `ALLLEDGERENTRIES.LIST` in `VOUCHER_FETCH` (`tally_client.py:59`) already carries `BANKALLOCATIONS.LIST` with these tags; if not, add them to the fetch.
4. Use the stored dates in `routers/bank_recon.py`: an entry already reconciled in Tally should show as cleared and need no manual match.

**Acceptance:** values persist; payloads without the tags import unchanged; BRS screens show Tally-cleared items.

---

### WS-5 · Books-parity check against Tally (P1, M)

**Idea from the reference:** pull Tally's own computed reports (Trial Balance, Bills Receivable/Payable) as a snapshot. Used here as a **verification**, not as a data source.

**Steps**
1. Ledger closing balances are already exported (`CLOSINGBALANCE` in the ledger fetch, `tally_client.py:412`) and stored on `MstLedger.closing_balance` (`tally_xml_importer.py:1991-2066`). Add a server job that compares, per ledger, Tally's closing balance with the balance computed from `voucher_entries` + opening balance, for the same period.
2. Add per-company totals: voucher count per voucher type and financial year, from Tally (cheap collection count) vs MyTally.
3. Report drift in sync health with the top differing ledgers; offer "Re-sync this ledger's vouchers" (a date-range re-export, repeat-safe).
4. **Verify while building:** whether order vouchers (Sales/Purchase Order) and non-accounting inventory vouchers (Delivery/Receipt Note) put rows into `voucher_entries`. The trial balance query (`routers/reports.py`, the `WHERE` around line 261) excludes cancelled and optional vouchers but not those types. If they do land there, exclude them using `services/voucher_kinds.py`; the parity check will show it either way.

**Acceptance:** for a fully synced company, drift is zero; a deliberately missed voucher shows up as drift on the right ledger.

---

### WS-6 · Tolerant parsing of Tally numbers and names (P1, S)

**Gap:** `_decimal_or_none` (`tally_xml_importer.py:491`) strips commas and takes the first word, so `(1,250.50)` (parenthesised negative, seen in some Tally exports) becomes `None`, and a rate like `5,000.00/Nos` also fails.

**Steps**
1. Extend the helper: parenthesised negatives, trailing `/unit`, `Dr`/`Cr` suffixes where they occur, while keeping today's behaviour for every value it already handles.
2. Normalise parent names that arrive as `&#4; Primary` / `\x04 Primary` to "no parent" in one helper, and use it where parents are read (the backend already writes these spellings correctly on export).
3. Agent: decode Tally replies that start with a UTF-16 BOM (the backend inbound endpoint already does this at `sync.py:249-256`; the agent decodes UTF-8 only) and strip invalid numeric character references (`&#4;` in non-name fields) before parsing.

**Tests:** table-driven fixtures for each input form.

---

### WS-7 · Cheap "anything changed?" probe (P2, S)

**Gap:** each inbound cycle sends one AlterID-filtered export per collection (about 11 requests) even when nothing changed. Tally serves one request at a time, so this competes with the user's own work in Tally.

**Steps**
1. One Company collection request per company fetching `$AltMstId` and `$AltVchId` (the counters `sync.py:1186` already refers to). **Verify the exact field names on a real TallyPrime** before relying on them; the reference used the wrong field (§4 #9).
2. Remember the last values per company GUID. If both are unchanged, skip the cycle's exports. If either rose, run only the masters or only the vouchers side.
3. Always run a full incremental pass at least every N minutes as a safety net, and whenever the probe fails.

**Acceptance:** an idle company costs one request per cycle; changes are still picked up within one cycle.

---

### WS-8 · Gzip the agent's uploads (P2, S–M)

**Gap:** `_push_collections()` sends raw XML; `core/compression.py` only compresses responses. Tally XML typically compresses by ~90%.

**Steps**
1. Measure first: log payload bytes and duration per collection for a week (the existing plan's step 3).
2. Backend: accept `Content-Encoding: gzip` on `/sync/inbound` only; decompress with a hard cap on decompressed size (env var, e.g. `SYNC_INBOUND_MAX_BYTES`) and reject above it with a clear 413.
3. Agent: send gzip when the server advertises support (a field in `/sync/last-alter-id` or a version header), else plain XML, so old servers keep working.
4. Check the reverse proxy's body limits and timeouts and record them in the runbook.

**Acceptance:** same import results, smaller requests; an oversized or bomb payload is refused without exhausting memory.

---

### WS-9 · Durable receipts for `/sync/inbound` (P2, L)

Track C of [reference-integration-plan.md](reference-integration-plan.md), unchanged. Today `/sync/inbound` is excluded from `core/idempotency.py` (`SKIP_PREFIXES`), and a lost response after a successful import leaves the agent unsure.

**Steps (summary):** a receipt table keyed by `(company_id, idempotency_key)` with the payload SHA-256, state and stored response; replay only on a matching hash; commit receipt and import together; agent sends a deterministic key per export (company GUID + collection + AlterID window + payload hash). Only then add "retry after timeout" on the agent. Do not use in-process background tasks (§4 #12).

**Acceptance:** a lost response never causes a second import; a reused key with a different body is refused.

---

### WS-10 · Export field coverage (P2, M–L)

The reference fetch lists show many Tally fields MyTally doesn't request. The rule from the existing plan stands: **only add a fetch field when the importer parses it and a column stores it**, proven with a fixture.

**Step 1 — build a coverage matrix** (requested / parsed / stored / tested) from `tally_client.py` fetch lists vs `tally_xml_importer.py`.

**Step 2 — candidates found in this review**

| Object | Not requested today (`tally_client.py`) | Storage already exists? |
|---|---|---|
| Ledger (`:412`) | `CREDITLIMIT`, `BILLCREDITPERIOD`, `ISCOSTCENTRESON`, `AFFECTSSTOCK`, `TAXTYPE`, `GSTTYPEOFSUPPLY`, `ISTDSAPPLICABLE`/`TDSDEDUCTEETYPE`/`NATUREOFPAYMENT`, `PRICELEVEL`, `EMAIL`, `LEDGERCONTACT`, `LEDGERMOBILE`, bank details | Partly: `CREDITLIMIT` is parsed (`sync.py`, importer); `ledger_bank_details`, `ledger_tds_lower_deductions` tables exist. Check each. |
| Stock item (`:421`) | `GSTDETAILS.LIST`, `HSNDETAILS.LIST`, `MRPDETAILS.LIST`, `MULTICOMPONENTLIST.LIST` (BOM), `FULLPRICELIST.LIST`, `REORDERBASE`, `MINIMUMORDERBASE`, `STANDARDCOSTLIST.LIST`, `STANDARDPRICELIST.LIST`, `MAILINGNAME.LIST` (part no.) | Tables exist (`stock_item_boms`, `price_levels`, `stock_item_price_level_rates`, standard cost/price, `hsn_details`), but the importer does **not** parse `MULTICOMPONENTLIST` today. |
| Voucher header (`VOUCHER_FETCH`, `:59`) | `REFERENCE`, `REFERENCEDATE`, `EFFECTIVEDATE`, `PARTYGSTIN`, `PLACEOFSUPPLY`, `BASICBUYERNAME`, `CONSIGNEE*`, `IRN`/`IRNACKNO`/`IRNACKDATE`, `EWAYBILLDETAILS.LIST`, `BASICSHIPDOCUMENTNO`, `BASICSHIPPEDBY`, `BASICFINALDESTINATION`, `BASICSHIPVESSELNO`, `INVOICEDELNOTES.LIST`, `INVOICEORDERLIST.LIST`, `ISINVOICE`, `PERSISTEDVIEW`, `ISPOSTDATED` | `TrnVoucher` already has columns for nearly all of these; the importer reads several. Mostly a fetch-list change plus tests. |
| New collections | Currency, Price Level | Models exist (`currency_tds` router, `MstPriceLevel`). |
| Unit (`:415`) | `REPORTINGUQCDETAILS.LIST` / GST UQC | Check `MstUom`. |

**Step 3:** add one object family per PR, each with a real-Tally fixture. Watch export time: wider fetches make dense voucher ranges slower, so re-check `vouchers_per_range` timings.

---

### WS-11 · Inventory order, tracking and batch lines (P2, M)

Track B of the existing plan, unchanged. `stock_entries` (`TrnInventory`, `tally_core.py:1134`) has no order number, order due date or tracking number, and multiple `BATCHALLOCATIONS.LIST` per line are not kept as child rows. Do **not** adopt the reference's tracking-number de-duplication view (§4 #15).

---

### WS-12 · Find Tally's port automatically (P3, S–M)

**Gap:** default URL `http://127.0.0.1:9000` (`bridge_core.py:25`), editable under Advanced. A Tally on another port shows as "can't reach TallyPrime".

**Steps**
1. When Tally is unreachable on the configured URL, try in order: the port from `tally.ini` (`ServerPort=`; path from a previous `discover_tally_host()` `tally_ini_path`, or standard install folders/registry), then common ports (9000–9005, 9999).
2. If one answers **and** returns a company whose GUID is already linked, offer "TallyPrime is on port 9001. Use it?" in the health bar. Never switch silently.
3. Diagnostics only: whether `tally.exe` is running (`tasklist`), to word the message ("TallyPrime isn't running" vs "TallyPrime is running but its port is off: F1 > Settings > Connectivity"). Skip `netstat` PID mapping and auto-launching `tally.exe`.

**Acceptance:** a customer on a non-default port is guided to working sync in one click; the configured URL is never changed without consent.

---

### WS-13 · Backup hardening (P3, M–L)

**Gaps:** server backups are plain ZIPs on one disk (`services/backups.py`, `BACKUP_STORAGE_DIR`); no off-site copy; restore only goes into the *same* company (fingerprint check), so a lost or dead PC has no supported recovery path into a fresh Tally.

**Steps**
1. **Encryption at rest (server):** AES-GCM per file with a key from server config/KMS, key id in the backup row; decrypt on download. Rotate by re-wrapping. Add the env var to the runbook.
2. **Off-site copy (server-side):** after a backup is verified, copy it to S3-compatible storage (S3/R2/B2) with the server's credentials and lifecycle rules matching `keys_to_keep`. No cloud keys on customer PCs (§4 #17).
3. **Restore to a new company ("new PC" flow):** explicit, admin-only, with typed confirmation. Target an empty company in Tally; write masters in dependency order (groups by parent depth, units simple-before-compound, godowns, stock groups, ledgers, BOM items after their components, then vouchers by date); verify counts against the manifest; re-bind the MyTally company to the new GUID/fingerprint only after verification. Reuse the reference's topological sort idea, not its code (§4 #3, #4).
4. **Restore drills:** a scheduled job that test-restores the latest backup into a scratch Tally (or validates the archive and manifest) and reports failures.
5. Optional, later: customer-held recovery passphrase (client-side encryption), only if a customer requires that the operator cannot read backups. It makes support recovery impossible if the passphrase is lost, so it must be opt-in.

**Not planned:** copying Tally's binary `Data` folder (§4 #6). If ever needed, only with Tally closed, via Tally's own backup, never extracted over a live folder.

---

### WS-14 · Write reconciliation dates back to Tally (P3, M; after WS-4)

The reference does this unsafely (§4 #2). The safe version:
1. Only for vouchers MyTally knows by `tally_master_id` + `tally_date`.
2. Fetch the voucher's **current full XML from Tally**, check its AlterID matches what MyTally last saw (else stop and ask), change only `BANKERSDATE` / `BANKMANUALSTATUS` in the matching `BANKALLOCATIONS.LIST`, and send that whole voucher back as `ACTION="Alter"` addressed by `TAGNAME="MASTERID"` + `DATE`.
3. Repeat-safe: re-sending the same dates is a no-op; record the AlterID after success.
4. Behind a feature flag per company; queued through the existing outbound queue so it follows the same retry and audit path.

---

### WS-15 · Proper Windows installer (P3, S–M)

Useful parts of `TallyPrimeSync_Installer.iss`: Start Menu shortcut, uninstaller entry, per-user install. Adapt with:
- per-user install (`PrivilegesRequired=lowest`) instead of admin;
- autostart through the agent's own setting (it already writes HKCU Run with `--tray`), not a separate registry entry;
- **no** `schtasks` job (§4 #16);
- built and signed in `agent-exe.yml` (with WS-2), attached to the GitHub Release.

---

### WS-16 · Reusable mock-Tally test harness (P3, S)

The reference's `_MockTallyHandler` (a local HTTP server returning canned Tally XML) is a good testing idea. Add a pytest fixture in `desktop-sync-agent/tests/conftest.py` that serves recorded real Tally responses by request ID, so WS-3, WS-7, WS-10 and WS-12 can be tested end to end without Tally. Record fixtures from a real TallyPrime, with personal data scrubbed.

---

### WS-17 · JSONEx (deferred)

Track D of the existing plan. XML works on every supported Tally version; JSONEx needs TallyPrime 7.0+, and the reference code is untested against a real Tally. Revisit only with a concrete need (a field XML can't export, or measured parse cost).

---

## 6. Suggested order

| Phase | Workstreams | Why this order |
|---|---|---|
| 1 | WS-1, WS-2 (steps 1–2), WS-6 | Small, independent, remove real risks |
| 2 | WS-4, WS-3, WS-16 | Books correctness; the harness makes WS-3 testable |
| 3 | WS-5, WS-7 | Parity check proves phases 1–2; the probe cuts load on Tally |
| 4 | WS-8, WS-9 | Transport: measure, then compress, then receipts |
| 5 | WS-10, WS-11 | Coverage, one object family per PR |
| 6 | WS-13, WS-12, WS-15, WS-2 (signing/Nuitka), WS-14 | Product features once the core is solid |

## 7. Housekeeping

- `docs/temp/` holds 10 duplicate files. Delete the duplicates (or the whole folder once this plan is accepted) so they aren't mistaken for separate versions.
- Annotate [Desktop_Sync_Agent_Architectural_Upgrade_Blueprint.md](Desktop_Sync_Agent_Architectural_Upgrade_Blueprint.md) with a pointer to §3 of this plan.
- Mark Tracks A–D in [reference-integration-plan.md](reference-integration-plan.md) as tracked here (WS-4, WS-11, WS-9, WS-17).

## 8. Verification checklist for every workstream

- [ ] Tests with Tally-shaped fixtures, including missing and malformed values
- [ ] Multi-company: two companies on one PC, same ledger names, no cross-over
- [ ] Repeat-safety: run twice, retry after a dropped response, no duplicates in MyTally or Tally
- [ ] Partial failure: Tally timeout mid-way leaves nothing half-applied and nothing deleted
- [ ] Existing incremental watermarks, retry floors and full-sync cursors unchanged
- [ ] Migration runs on an existing database and a clean one
- [ ] Manual steps added to the rollout runbook
- [ ] Checked once against a real TallyPrime before release
