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
_(Filled in as WS-13, WS-12, WS-2, WS-15 and WS-14 land.)_

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
- Not built by decision: S3 off-site backup (covered by Google Drive), the string vault, PyArmor, anti-debug,
  JSONEx (WS-17).
