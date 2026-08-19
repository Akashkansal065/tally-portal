# Tally Safety & Crash Prevention Rules

Before constructing or dispatching any HTTP XML or JSON payload to TallyPrime, all agents and backend modules MUST strictly follow these safety rules:

---

### 1. STRICT BAN ON TDL FORMULAS & UI REPORT INVOCATION (MODAL POPUP PREVENTION)
- **Modal Dialog 1: "Cannot understand. Bad formula!"**:
  - When an unescaped, invalid, or shell-interpolated formula expression (such as `$= "Sales"` or unquoted strings) is sent in `<SYSTEM TYPE="Formulae">`, Tally Prime opens a modal error dialog (`Error: Cannot understand. Bad formula!`).
- **Modal Dialog 2: "Error in TDL. 'Part:DB Body' No 'PARTS' or 'LINES' or 'BUTTONS'!"**:
  - When an interactive UI display report (such as `<ID>Day Book</ID>` or `<ID>Voucher Register</ID>`) is requested with `<TYPE>Data</TYPE>`, Tally's layout engine attempts to render UI form elements and throws: `'Part:DB Body' No 'PARTS' or 'LINES' or 'BUTTONS'!`.
- **THE CRITICAL DANGER**:
  - Whenever any of these modal dialogs appear on the host Windows machine, **Tally Prime completely freezes its background HTTP/XML server thread** on port 9000 and drops all incoming connections with timeouts until a human physically clicks "OK" in the Tally application window.
- **MANDATORY RULES FOR DATA EXPORT**:
  - **NEVER** request UI Reports (`Day Book`, `Voucher Register`) with `<TYPE>Data</TYPE>`.
  - **NEVER** use `<SYSTEM TYPE="Formulae">` in automated scripts.
  - **ALWAYS** export raw data using pure `<TYPE>Collection</TYPE>`:
    ```xml
    <ENVELOPE>
      <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Collection</TYPE>
        <ID>CustomExport</ID>
      </HEADER>
      <BODY>
        <DESC>
          <STATICVARIABLES>
            <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
            <SVCURRENTCOMPANY>{comp_name}</SVCURRENTCOMPANY>
            <SVFROMDATE TYPE="Date">20260401</SVFROMDATE>
            <SVTODATE TYPE="Date">20270331</SVTODATE>
          </STATICVARIABLES>
          <TDL>
            <TDLMESSAGE>
              <COLLECTION NAME="CustomExport">
                <TYPE>Voucher</TYPE> <!-- Or Ledger, StockItem, etc. -->
                <FETCH>GUID,REMOTEID,VOUCHERNUMBER,DATE,VOUCHERTYPENAME,PARTYLEDGERNAME,AMOUNT</FETCH>
              </COLLECTION>
            </TDLMESSAGE>
          </TDL>
        </DESC>
      </BODY>
    </ENVELOPE>
    ```
  - Perform all filtering, aggregation, and querying in Python in-memory.

---

### 2. STRICT XML ENVELOPE HIERARCHY
- All master and transaction push envelopes to Tally Prime must place `<TALLYMESSAGE>` inside `<DATA>` (after `<DESC>...</DESC>`).
- **NEVER** place `<TALLYMESSAGE>` inside `<DESC>`:
  ```xml
  <!-- ✅ CORRECT ENVELOPE -->
  <ENVELOPE>
    <HEADER>
      <VERSION>1</VERSION>
      <TALLYREQUEST>Import</TALLYREQUEST>
      <TYPE>Data</TYPE>
      <ID>All Masters</ID> <!-- Or 'Vouchers' -->
    </HEADER>
    <BODY>
      <DESC>
        <STATICVARIABLES>
          <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
          <SVCURRENTCOMPANY>{comp_name}</SVCURRENTCOMPANY>
        </STATICVARIABLES>
      </DESC>
      <DATA>
        <TALLYMESSAGE xmlns:UDF="TallyUDF">
          <!-- ENTITY (UNIT, STOCKGROUP, STOCKITEM, GODOWN, LEDGER, VOUCHER) -->
        </TALLYMESSAGE>
      </DATA>
    </BODY>
  </ENVELOPE>
  ```
- If `<TALLYMESSAGE>` is nested inside `<DESC>`, Tally Prime will ignore or reject the message.

---

### 3. PREREQUISITE MASTER SEQUENCING
- In Tally Prime, a `VOUCHER` containing a stock item will fail to import if the `STOCKITEM` does not already exist in Tally's active company.
- A `STOCKITEM` will fail to import if its `UNIT` (e.g. `nos`) or `STOCKGROUP` does not already exist.
- A `VOUCHER` will fail to import if `PARTYLEDGERNAME` or accounting ledgers do not exist.
- **Mandatory Creation Order**:
  1. `UNIT` (Prefer standard Tally units like `nos`)
  2. `STOCKGROUP`
  3. `GODOWN`
  4. `STOCKITEM`
  5. `LEDGER`
  6. `VOUCHER`

---

### 4. MASTER DELETION CONSTRAINTS & NON-BLOCKING API
- In Tally Prime:
  - System ledgers (`Cash`, `Profit & Loss A/c`) cannot be deleted (`<LINEERROR>Cannot be deleted!</LINEERROR>`).
  - Masters linked to historical vouchers or active opening balances cannot be hard-deleted.
- MyTally portal endpoints must remain non-blocking: log the Tally Prime XML response to `sync_traffic_logs` and mark `SyncQueue` (`status='FAILED'` / `status='EXCEPTION'`) without crashing the REST API endpoint.

---

### 5. IN-PLACE MODIFICATIONS REQUIRE COMPOSITE KEYS
- When altering or cancelling vouchers in automatic numbering series, always bind `REMOTEID`, `VCHKEY`, and `<GUID>` (e.g., `MYTALLY-VCH-{id}`) to prevent ghost sequence generation.

---

### 6. USE CANCELLATION OVER HARD DELETE
- Vouchers with active bill allocations or stock items should preferably be cancelled with `<ISCANCELLED>Yes</ISCANCELLED>` (`"iscancelled": true`) to safely zero balances and reverse stock without integrity exceptions.

---

### 7. ALWAYS SANITIZE INCOMING XML
- Strip low-ASCII binary entities with `re.sub(r'&#\d+;', '', xml_str)` before XML ElementTree parsing.

---

### 8. VERIFY ACTIVE COMPANY
- Ensure `<SVCURRENTCOMPANY>` matches the open company in Tally before executing batch operations.
