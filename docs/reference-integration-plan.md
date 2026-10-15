# External Reference Integration Plan

**Status:** Review proposal only. No implementation is included in this plan.

The nine attachments reduce to three unique files: the MySQL schema, connector, and FastAPI backend were each attached three times byte-for-byte.

## Existing capabilities to preserve

The repository already has per-company master and voucher watermarks, retry floors for incomplete incremental imports, a density-adaptive voucher date planner with range validation and resumable full-sync cursors, a serialized Tally HTTP client, company-scoped sync locks, device/company binding and Tally-copy fingerprints, normalized voucher accounting/inventory/bill/bank models, and chunked backup uploads with SHA-256 verification.

The references are standalone MySQL designs keyed mainly by company name. MyTally scopes tenant data by company ID across portal and Tally schemas and uses async SQLAlchemy. Reuse domain behavior only; do not transplant the schema, PyMySQL data layer, or company-name tenancy model.

## Prioritized upgrade matrix

| Priority | Upgrade | Current gap | Main repository surfaces | Effort / impact |
|---|---|---|---|---|
| Quick win | Bank reconciliation metadata | The importer creates bank allocations but does not retain Tally's `BANKERSDATE` or `BANKMANUALSTATUS`. | `backend/app/models/tally_core.py` (`TrnBankAllocation`); `backend/app/services/tally_xml_importer.py` (bank allocation parser) | Small / high |
| Strategic | Inventory order and batch traceability | Inventory lines do not retain order/tracking references or map nested batch allocations to existing batch/inventory models. | `backend/app/models/tally_core.py` (`TrnInventory`, `Batch`); `backend/app/services/tally_xml_importer.py` (inventory parser) | Medium / high |
| Strategic | Durable inbound import receipts | `/sync/inbound` is excluded from process-local idempotency. Company locking prevents concurrent imports, but there is no durable request receipt or status API. | `backend/app/routers/sync.py`; `backend/app/core/idempotency.py`; `backend/app/services/tally_xml_importer.py` | Large / high reliability |
| Optional discovery | TallyPrime JSONEx support | Desktop sync currently uses XML; the sample connector has JSONEx builders, but there is no end-to-end JSONEx route here. | `desktop-sync-agent/tally_client.py`; `backend/app/routers/sync.py`; `backend/app/services/tally_xml_importer.py` | Large / conditional |

## Desktop sync agent: additional transferable upgrades

The desktop agent is already comparatively mature: do not replace its date-range planning, checkpointed range cursor, Tally request lock, failed-cycle retry floors, company isolation, or timeout diagnostics with the reference connector's alternate implementations. The useful desktop-specific opportunity is **coverage and bounded cloud delivery**, not a second sync engine.

| Priority | Upgrade | What the references add | Current agent / repository gap | Suggested scope |
|---|---|---|---|---|
| Quick win | Audit export fields against importer needs | Explicit fetch sets for detailed ledger, voucher, batch, bank, bill, order, and inventory fields; tolerant parsers for Tally numeric/parent values and invalid XML characters. | `desktop-sync-agent/tally_client.py` explicitly fetches only selected fields. The master collections omit dedicated payroll-master, price-level, and some auxiliary-master exports; the stock-item fetch does not explicitly request BOM, price-list, MRP, or GST effective-rate lists. Voucher fetch does not explicitly list bank/bill allocation child collections. Some importer/model support exists, but whether a Tally tag arrives depends on the export request. | Build a field coverage matrix from current importer parsers and actual Tally fixtures; add only fetch fields/collections whose values are parsed and persisted. |
| Strategic | Complete missing Tally master coverage | The connector models include payroll, BOM, price lists, batch openings, and richer vouchers; the schema includes currencies, price levels, payroll masters, GST rates, and report snapshots. | `export_full_collections()` in `desktop-sync-agent/tally_client.py` has no separate Employee/PayHead/EmployeeGroup, PriceLevel, or Currency collection entries. The backend importer has some currency, employee/payhead, salary-rate, and attendance parsing, but the desktop export must request the corresponding roots for those branches to run. | Add one entity family at a time after confirming matching parser and persistence behavior. Start with a fixture-driven coverage test; avoid exporting unsupported roots that the importer silently ignores. |
| Strategic | Bound and compress inbound cloud requests | The connector sends deterministic, gzip-compressed micro-batches, shrinks batches after repeated timeout, backs off, polls async receipts, and checkpoints only after a positive acknowledgment. | `_push_collections()` sends each XML collection as one uncompressed request. `CloudClient.push_inbound_xml()` uses a long timeout and handles token refresh, but does not retry a timed-out upload in the same call. Existing voucher date-range slices already bound voucher uploads; large master collections can still be large. | First instrument request sizes and latency by collection. Then add request compression only with matching backend decompression and size limits. Consider safe, entity-aware splitting for oversized collections; do not split XML by arbitrary string boundaries. Gate retry-after-timeout on durable server receipts so an accepted-but-unacknowledged import cannot be applied ambiguously. |
| Optional | Local durable upload staging | `LocalSyncStore` keeps company-scoped records/hashes and dirty flags in SQLite, then marks a micro-batch clean after acknowledgment. | The current agent re-exports from Tally and relies on AlterID retry floors/full-sync cursors rather than a local mirror. That is simpler and correct for the present architecture; it can repeat Tally export work when the cloud is unavailable. | Consider a local spool only if measured Tally re-export cost or prolonged disconnected operation warrants it. It needs bounded storage, company/copy fingerprinting, schema versioning, and safe cleanup; it is not a default port. |
| Optional | Native JSONEx wire format | Connector provides JSONEx builders alongside XML builders. | Current desktop sync and inbound backend contract use XML. | Treat as a protocol project after confirming supported Tally versions and a real performance or feature need. |

### Desktop-specific implementation sequence

1. **Inventory fields first:** map each collection's `<FETCH>` list in `desktop-sync-agent/tally_client.py` to the corresponding tag reads and database writes in `backend/app/services/tally_xml_importer.py`. Label each field as requested, parsed, persisted, and tested. This will expose missing fetches separately from missing importer/model support.
2. **Prove domain coverage with fixtures:** use representative Tally XML for nested bill/bank allocations, inventory batches/godowns, payroll, GST effective dates, currencies, and price data. Add requests only for tags the importer consumes, and add missing persistence support as an independently reviewed scope.
3. **Measure delivery limits:** record per-company/per-collection payload bytes, request duration, and outcomes. Set a supported request limit based on the backend/proxy deployment before adding gzip or splitting.
4. **Make retries safe before increasing them:** persist a tenant-scoped request receipt with payload digest and result; add client request identity; replay only matching completed payloads. Define `PROCESSING` recovery before exposing polling.
5. **Add transfer optimizations incrementally:** support compressed request bodies end to end, then safely split only collections with a parser-aware boundary. Keep voucher date-range checkpoints and server watermark retry floors authoritative.
6. **Run compatibility gates:** retain existing XML exports, incremental/full-sync semantics, device/company fingerprint binding, and server-side authorization. Test lost response after server commit, network interruption between chunks, oversized payload response, and retry without duplicate import.

### Patterns already present or not recommended as a default port

- **Already present:** per-company voucher range planning/checkpoints; count/range validation; serialized Tally requests; separate master/voucher watermarks; failed-cycle re-pull floors; safe XML escaping/control-character cleanup; diagnostic import-result parsing; outbound create recovery by `REMOTEID`; chunked backup upload/download with checksum validation.
- **Potentially valuable after measurement:** gzip transfer, adaptive per-collection upload chunks, and local SQLite staging.
- **Do not port blindly:** a second SQLite mirror as a prerequisite for syncing, a second voucher date planner, generic retry of every HTTP response, batch splitting by raw XML string slices, or the reference's name-scoped MySQL identity model.

## Track A — Bank reconciliation metadata (recommended first)

1. Add nullable `bankers_date` and `bank_manual_status` fields to `TrnBankAllocation`. Keep the fields optional because existing Tally payloads may omit them.
2. Parse `BANKERSDATE` and `BANKMANUALSTATUS` from each `BANKALLOCATIONS.LIST` in `tally_xml_importer.py`. Reuse current date parsing conventions; malformed or absent dates should not break an import.
3. Add a forward-compatible database migration using the repository's supported migration mechanism. Verify the deployment migration path before choosing the migration artifact; model changes alone do not update existing databases.
4. Add focused importer tests for populated values, absent values, malformed dates, and multiple bank allocations. Run those tests and the narrow relevant sync/import selection.

**Acceptance:** imported values are persisted; payloads without these tags continue to import; other bank allocation fields and import behavior remain unchanged.

## Track B — Inventory order and batch traceability

1. Confirm which Tally tags and semantics are required: tracking number, order number/due date, batch name, godown, destination godown, quantity, rate, and amount per allocation.
2. Extend existing `TrnInventory`/`Batch` relationships rather than introducing reference-only tables. If one stock line can contain multiple batches or godowns, represent allocations as child rows; do not flatten multiple values into a single lossy field.
3. Parse voucher inventory lines and nested `BATCHALLOCATIONS.LIST` values with per-allocation decimal/date validation. Resolve stock item, godown, and batch within the correct company.
4. Migrate the schema; update relevant response schemas and reports only where the product needs to expose the information.
5. Add fixtures for multiple batches, partial fulfillment, absent optional tags, and signed quantities.

**Acceptance:** each source allocation remains attributable to its voucher and company. Do not discard or deduplicate movements by tracking number without an independently validated accounting rule.

## Track C — Durable idempotent inbound import receipts

1. Agree on the request contract: stable key generation, retention period, status polling, retryable versus terminal failures, and the response after reconnect.
2. Add a durable receipt scoped by `(company_id, idempotency_key)`, storing a canonical payload hash, state, timestamps, and response. Do not scope receipts by company name.
3. Replay a completed response only if the payload hash matches. Reject reuse of a key for different XML. Use a database uniqueness constraint and company lock to coordinate concurrent requests.
4. Inspect the importer's transaction/commit ownership. Ensure imported data and receipt completion commit atomically, or explicitly design recovery for intermediate states.
5. Add status polling and agent retry behavior if asynchronous processing is required. Use a durable worker/queue for work that must survive process restarts; in-process FastAPI background tasks are not durable.
6. Test replay after a lost response, concurrent duplicate keys, payload mismatch, process interruption, tenant isolation, failed-import retry, and receipt retention/cleanup.

**Acceptance:** a lost response cannot cause a duplicate import; one company cannot see or replay another's receipt; unfinished work is never reported as successful.

## Track D — JSONEx feasibility and gated support

1. Establish the required TallyPrime versions, supported JSONEx envelopes, and a concrete need such as feature coverage or measured parsing cost.
2. Build a protocol compatibility spike with representative golden fixtures before changing production sync. Add explicit capability detection and opt-in negotiation, retaining XML fallback.
3. Implement matching parse/build semantics for each in-scope entity. Validate against a real Tally instance and compare resulting records with the XML path.

**Acceptance:** unsupported versions stay on XML; equivalent records produce equivalent application state; existing XML behavior is unchanged.

## Cross-cutting gates

- **Schema:** migration applies to existing data and a clean database; rollback or forward recovery is understood.
- **Correctness:** tests cover Tally-shaped XML, optional/malformed values, and multi-company isolation.
- **Compatibility:** current XML sync, incremental watermarks, retry floors, and full-sync cursors remain intact.
- **Operations:** failures remain explicit in logs/API results; no silent fallback to a success-shaped response.
- **Release:** implement only the selected track and run focused tests before broader suites or rollout.

## Patterns to adapt cautiously

Potentially useful patterns from the references include deterministic batch identity, bounded retries with backoff, checkpoint-after-ack, explicit asynchronous status, normalized voucher lines, and payload hashes. Some are already implemented in this repository's own architecture.

Do not copy the sample's optional API-token/HMAC checks, company-name-only tenant scope, synchronous PyMySQL execution, in-process background-job assumption, or batch-ID-only replay without checking the payload hash. Do not adopt tracking-number movement deduplication before validating its accounting and reporting semantics.

## Review checkpoint

No code changes are part of this proposal. Select one track for implementation; refine it into a file-by-file change list and test plan before writing implementation code.
