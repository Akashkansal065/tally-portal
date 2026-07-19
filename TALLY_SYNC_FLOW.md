# Tally Synchronization Architecture

This document maps out the end-to-end flow of how data is fetched from Tally Prime by the sync daemon, transmitted to the FastAPI backend, and parsed and stored in the database.

## Synchronization Flow

```mermaid
sequenceDiagram
    autonumber
    participant D as Sync Daemon (tally_sync_daemon.py)
    participant T as Tally Prime (Local XML Server)
    participant E as ERP Backend (FastAPI - sync.py)
    participant DB as ERP Database (MySQL / Aiven)

    Note over D, DB: 1. Fetching State & Prep
    D->>+E: GET /sync/last-alter-id (Bearer Token)
    E->>+DB: Query MAX(tally_alter_id) for Ledgers & Vouchers
    DB-->>-E: Return max alter IDs
    E-->>-D: JSON { last_ledger_alter_id, last_voucher_alter_id }

    Note over D, DB: 2. Exporting Incremental Data from Tally
    D->D: Build XML Query Envelopes (with filter $ALTERID > last_alter_id)
    D->>+T: POST query (UTF-16LE, Content-Type: text/xml, charset=utf-16)
    T->T: Process query against active Tally Company
    T-->>-D: Return XML data payload (UTF-16 encoded)

    Note over D, DB: 3. Inbound ingestion & parsing on ERP Backend
    D->>+E: POST /sync/inbound (XML string, Bearer Token)
    E->E: Detect encoding & run sanitize_xml()<br/>(Filters invalid XML 1.0 control characters)
    E->E: Parse XML string with ElementTree
    
    rect rgb(240, 245, 255)
        Note over E, DB: Ingesting & Upserting Master Records (Flat loops)
        E->>+DB: get_or_create_group() / get_or_create_stock_group()
        DB-->>-E: Return IDs
        E->>+DB: get_or_create_uom() / get_or_create_godown()
        DB-->>-E: Return IDs
        E->>+DB: Upsert MstStockItem / MstLedger
        DB-->>-E: DB Flushed
    end

    rect rgb(255, 245, 240)
        Note over E, DB: Ingesting Vouchers & Accounting Entries (Nested cascade logic)
        E->>+DB: Select TrnVoucher by GUID (idempotency check)
        DB-->>-E: Return voucher details (if exists)
        alt Voucher exists & alter_id is new
            E->>+DB: delete(TrnAccounting) where voucher_id = X
            Note over DB: Cascade Delete triggers in MySQL:<br/>removes dependent bill_allocations
            DB-->>-E: DB Flushed
        end
        E->>+DB: Save voucher headers (Date, Num, Narration, AlterID)
        DB-->>-E: Return voucher_id
        E->>+DB: Insert TrnAccounting (Voucher Entries) & TrnInventory (Stock Entries)
        DB-->>-E: Return entry_ids
        E->>+DB: Query or insert TrnBill reference
        DB-->>-E: Return bill_id
        E->>+DB: Insert BillAllocation (linked to bill_id and entry_id)
        DB-->>-E: DB Flushed
    end

    E->>+DB: COMMIT transaction
    DB-->>-E: Commit OK
    E->E: Clear Redis/In-Memory Cache for company
    E-->>-D: Return Inbound sync summary JSON
    Note over D: Sleep (frequency interval)<br/>repeat cycle
```

---

## Detailed Inbound Processing Breakdown

When a raw XML document is sent to the ERP Backend's `/sync/inbound` endpoint:

### 1. Decoding & Sanitization
* **Encoding Detection**: The backend checks for the byte-order mark (`BOM`) to see if the file is `UTF-16` (standard Tally export format) or `UTF-8` and decodes it accordingly.
* **Sanitization**: Raw XML from Tally can contain invalid Unicode control characters (like `\x00-\x08`, `\x0B-\x0C`, `\x0E-\x1F`) which violate the XML 1.0 specification and crash standard parsers. The backend runs regex patterns to clean these characters out before calling `ElementTree`.

### 2. Hierarchical Parsing Order
To respect foreign key constraints, the XML is parsed in a strict dependency order:
1. **Account Groups & Stock Groups**: Loaded/created first because ledgers and stock items depend on them.
2. **Units, Godowns & Stock Categories**: Supporting masters.
3. **Stock Items**: Parsed next, referencing their corresponding units and groups.
4. **Ledgers**: Parsed next, referencing account groups.
5. **Vouchers (Transactions)**: Parsed last, referencing ledgers and stock items.

### 3. Voucher Update & Cascading Deletion
* When a voucher is modified in Tally, it is exported with a higher `ALTERID`.
* If the backend detects the voucher GUID already exists in the database, it must overwrite it.
* Instead of doing clean deletes and inserts of the voucher itself, it keeps the voucher header and resets the entries:
  1. It triggers a delete query on `voucher_entries` for that voucher.
  2. Because the `voucher_entry_id` foreign key on the `bill_allocations` table has `ON DELETE CASCADE` configured, deleting the entries automatically cleans up the allocations in a single database step.
  3. The entries and allocations are then parsed fresh from the new XML and re-inserted.
