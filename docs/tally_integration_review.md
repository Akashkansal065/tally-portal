# Tally integration review: MyTally vs five reference repositories

**Date:** 7 Oct 2026 · **Scope:** how MyTally talks to TallyPrime (XML over HTTP), compared with five open-source Tally clients. MCP plumbing is ignored.

This supersedes parts of [`tally_reference_repositories_deep_analysis.md`](tally_reference_repositories_deep_analysis.md). Several of that document's claims did not hold up against the code; see [Corrections](#5-corrections-to-the-earlier-analysis).

**How this was checked.** Each reference repository was cloned at its latest commit and read directly. Every finding below cites a file and line in MyTally and, where relevant, in a reference repository. Nothing here was run against a live Tally. Items marked **Verify** need a test on a scratch Tally company before relying on them.

| Repository | What it is | Most useful for |
|---|---|---|
| `ComplyEaze/bridge` (Rust, ~342k lines) | Desktop app for CA compliance, heavily tested against captured Tally responses | Request serialisation, safe voucher posting, company identity, outstandings |
| `dhananjay1405/tally-mcp-server` (TypeScript) | Compact, well-designed TDL query layer | TDL report and collection templates, trial balance, bills, GSTIN |
| `anshveerturna/tally-mcp` (TypeScript) | Broad tool coverage | Request queue, UTF-16 transport, response error detection |
| `vaijaaaaa/Tally-MCP-Server` (TypeScript) | Small, simple | Gotchas list; built-in report calls |
| `learnwithcc/tally-mcp` | Integrates with **Tally.so (a form builder), not TallyPrime** | Nothing Tally-specific; skip |

---

## 1. Top fixes, in order

| # | Severity | Problem | Where |
|---|---|---|---|
| 1 | **High** | No XML escaping in any outbound builder: a `&` or `<` in a ledger name, narration, item name or payment URL makes Tally reject the request, and the task retries forever | `backend/app/routers/sync.py:380-579` and ~20 master builders |
| 2 | **High** | The agent's health check requests the `Company` *report* with `<TYPE>Data</TYPE>`, the same pattern your own safety rules say opens a modal and freezes Tally's XML server | `desktop-sync-agent/tally_client.py:40` |
| 3 | **High** | Nothing makes requests to Tally take turns: GUI threads and the daemon, and concurrent API requests in direct-push mode, can hit Tally at once | `tally_client.py` (all methods), `gui_app.py:542-546,581-593`, `sync.py` (`asyncio.to_thread` × 20) |
| 4 | **Medium** | Outbound posts time out after 6 s (agent) or 5–10 s (backend), well under how long a busy Tally can take, so a post that succeeded is reported as failed and is resent | `tally_client.py:29,329`, `sync.py:1551-2830` |
| 5 | **Medium** | Import results are matched as exact strings (`<CREATED>1</CREATED>`): a 2-object batch counts as failed, and `EXCEPTIONS` counts are not checked | `tally_client.py:335-344` |
| 6 | **Medium** | If the configured company isn't open, the agent silently switches to whichever company *is* open (matched by name, not GUID) and keeps syncing | `agent.py` `check_and_handle_company_switch` |
| 7 | **Medium** | Fields the importer reads are never requested: GST registration and mailing details (TallyPrime 3+), ledger `GUID`, voucher `ISCANCELLED`/`ISOPTIONAL` | `tally_client.py:205,211` vs `tally_xml_importer.py:1428,1459,1908` |
| 8 | **Medium** | A full sync exports every voucher from 2000 to 2099 in one request | `tally_client.py:223` |
| 9 | **Low** | HTTPS certificate checks are switched off when posting to a tunnelled Tally URL | `sync.py` `_post_to_tally_sync`, `_post_json_to_tally_sync` |
| 10 | **Low** | Voucher lines are rounded to 2 decimals one by one, so amounts with more decimals can reach Tally unbalanced | `sync.py:426,435`; `vouchers.py:368-372` |

What MyTally already does well, and should keep:

- **Stable `REMOTEID` on vouchers** (`sync.py:489-491`). A resend after a timeout alters the same voucher instead of creating a duplicate, which none of the TypeScript repos do.
- **`Decimal` balance check** before a voucher is queued (`vouchers.py:368-372`).
- **An inbound retry point** that keeps the watermark from moving past a failed export (`agent.py:414-438`, `tally_client.py:284-287`).
- **AlterID-based incremental sync**, the same high-water idea ComplyEaze uses.

---

## 2. What the reference repositories do

### 2.1 Reading data

**Custom reports and collections, not built-in screens.** dhananjay defines its own `REPORT → FORM → PART → LINE → FIELD` in the request and asks for `<TYPE>Data</TYPE>` of *that* report (`templates/generic/query-collection.njk`). Because every part and line is defined, Tally never has to render a built-in UI form. ComplyEaze uses `<TYPE>Collection</TYPE>` with `ISMODIFY="No"` and explicit `FETCH`, and pins the company with a GUID filter:

```xml
<SYSTEM TYPE="Formulae" NAME="BridgeCompanyGuidFilter">$GUID = "c3edf50d-…"</SYSTEM>
<COLLECTION NAME="BridgeCompanyBookExtentV2" ISMODIFY="No">
  <TYPE>Company</TYPE>
  <FETCH>Name, GUID, CompanyNumber, BooksFrom, LastVoucherDate, ALTVCHID, ALTMSTID, …</FETCH>
  <FILTERS>BridgeCompanyGuidFilter</FILTERS>
</COLLECTION>
```
(ComplyEaze `crates/bridge-tally-protocol/tests/fixtures/company_inventory_flags_request.utf16le.xml`)

**What the safety rules should actually say.** `.agents/rules/tally-safety-rules.md` bans `<SYSTEM TYPE="Formulae">` and `<TYPE>Data</TYPE>` outright. Both reference repos that are tested against real Tally use both. The real hazards are narrower:

1. Requesting a **built-in UI report or form** (Day Book, Voucher Register, `Company`) as `Data`. vaijaaaaa hit the same modal with `Company` (`src/tools.ts:391-393`: *"requesting it via REPORTNAME throws Error in TDL. 'Form:Company' No 'PARTS'!"*).
2. A **malformed formula**, most often from pasting a name containing `"` into a formula string. anshveerturna does this (`src/tools/reports-outstanding.ts:75`: `` `$Parent = "${params.party_ledger}"` ``). Filter by GUID or AlterID instead of by name, or refuse names containing `"`.

Suggested rewording for the rules file: *"Never request a built-in report or form with `TYPE=Data`. Define your own report, or use a `Collection`. Formulae are allowed, but only built from numbers, GUIDs and fixed text, never from user-entered names."*

**Trial balance straight from Tally.** dhananjay's `trial-balance` tool (`src/mcp.mts`) queries the `Ledger` collection with `SVFROMDATE`/`SVTODATE` set. Tally then fills in the period's `OpeningBalance`, `DebitTotals`, `CreditTotals` and `ClosingBalance` per ledger. Amounts go through `if $$IsDebit:$X then -$$NumValue:$X else $$NumValue:$X`, so debits come out negative (`query-collection.njk`, the `amount` branch).

**Outstandings.** dhananjay queries the `Bill` collection for `BillDate, Name, ClosingBalance, Parent, _OverDueDays` as of a date (`src/definition.mts:178-188`). ComplyEaze ages by **due date by default** (bill date optional) and reports **on-account (unallocated) amounts per party** separately from open bills (`src-tauri/src/agent_outstandings.rs:26-94`). anshveerturna's ageing query (`src/tally/tdl-builder.ts`, `buildAgeingAnalysis`) is wrong: it reads `$BillDate` on a `Ledger` collection and ages from `$$MachineDate` (today) rather than the report date. Don't copy it.

**GSTIN on TallyPrime 3+.** `if $$IsEmpty:$PartyGSTIN then $LedGSTRegDetails[Last].GSTIN else $PartyGSTIN`, and the same pattern for registration type (dhananjay `src/definition.mts:104-105`). `LEDGSTREGDETAILS.LIST` also carries `APPLICABLEFROM`, so it doubles as the party's GSTIN history.

**Large books.** ComplyEaze reads in windows of AlterID (`$AlterID > 400 AND $AlterID <= 800`, `crates/bridge-tally-protocol/tests/outstandings.rs`) or of date, never "everything since 2000".

### 2.2 Posting vouchers

| Practice | Who | Notes |
|---|---|---|
| Escape every value | dhananjay (Nunjucks `| escape`), anshveerturna (`esc()` in `xml-builder.ts:219`), vaijaaaaa (`autoescape: true`) | MyTally doesn't (finding 1) |
| Debit = `ISDEEMEDPOSITIVE` Yes **and a negative amount** | dhananjay (`voucher-journal.njk`), vaijaaaaa | anshveerturna's default is inverted (`isDeemedPositive = amount >= 0`, `xml-builder.ts`); don't copy |
| Balance check in whole paise | dhananjay `validateVoucherDebitCreditBalancing` (`Math.round(amount * 100)`) | MyTally uses `Decimal`, which is as good |
| Check ledgers and voucher type exist in Tally before posting | dhananjay `validateLedgers`, `validateVoucherTypeParent` | |
| Recheck each ledger's name still resolves to the same GUID just before posting | ComplyEaze `agent_import_post.rs:312-348, 2112` | Protects against a ledger renamed or merged in Tally meanwhile |
| Record a `REMOTEID` before sending; after a timeout, **look the voucher up, don't resend** | ComplyEaze `agent_import_post.rs:710-718, 2256-2275`; preview text: *"After a timeout, reconcile this batch; do not rebuild or resend it."* | Resending a known `REMOTEID` can bring back a voucher someone cancelled or deleted in Tally |
| Confirm an import by the company's voucher counter (`ALTVCHID`) moving by exactly `CREATED` | ComplyEaze `agent_import_post.rs:1788-1800`, `agent_import.rs:117-123` | |

### 2.3 Transport and errors

| Practice | Who |
|---|---|
| **One request at a time.** A promise queue in one client (anshveerturna `src/tally/client.ts`, `enqueue`). ComplyEaze goes further: a lock shared across every process on the machine, held for exactly one send, with a 10 s total wait before reporting "busy" (`crates/bridge-tally-transport/src/wire_gate.rs`) | anshveerturna, ComplyEaze |
| **UTF-16LE** request and response (`Content-Type: text/xml;charset=utf-16`) | dhananjay, anshveerturna, ComplyEaze |
| **Timeouts:** 20 s default and 120 s maximum (ComplyEaze `bridge-tally-transport/src/lib.rs:102-103`); 30 s (anshveerturna) | |
| **Retries for reads only:** 3 attempts, 250 ms–2 s backoff with 20 % jitter (ComplyEaze `runtime_control.rs` `transient_default`). Writes are never retried blindly | ComplyEaze |
| **Errors:** response starts with `<EXCEPTION>`; any `<LINEERROR>`; `<STATUS>0</STATUS>`; `ERRORS` > 0; `IMPORTRESULT` with nothing created, altered or deleted (anshveerturna `src/tally/xml-parser.ts:76-135`). An empty body usually means no company is open (vaijaaaaa) | |
| **Parse lists as lists:** any `*.LIST` tag, plus `LEDGER`, `VOUCHER` and similar, always parsed as an array (anshveerturna `xml-parser.ts:10-31`) | |

---

## 3. Findings in MyTally, with fixes

### F1. Escape everything that goes into outbound XML (High)

`build_voucher_xml_payload` (`backend/app/routers/sync.py:260-579`) interpolates `lname`, `party_ledger_name`, `comp_name`, `vtype_name`, `voucher.narration`, `item_name`, `godown_name`, `batch_name`, bill names, cost centre names, `pl.payment_url` and more directly into the XML. A payment URL (`?a=1&b=2`), a narration such as "Cash & cheque", or a party such as "M/s Shah & Sons" makes the payload invalid XML. Tally rejects it, the task is never acknowledged, and the agent resends it every 5 seconds. The master builders have the same problem (`sync.py:663, 678, 712, 739, 1017, 1670, 1733, 1772, 1860, 2085, 2091, 2232, 2335, 2438-2465, 2569-2579, 2680-2690, 2790-2802, 2970`).

An escaping builder already exists, `backend/app/services/tally_xml_builder.py` (`SchemaXmlBuilder.tag` calls `escape_xml`), **but nothing imports it**.

Fix: one helper, applied at each interpolation.

```python
# backend/app/services/tally_xml.py (new)
from xml.sax.saxutils import escape

def x(value) -> str:
    """Text safe for an XML element or a double-quoted attribute."""
    return escape("" if value is None else str(value), {'"': "&quot;"})
```

```python
# backend/app/routers/sync.py: build_voucher_xml_payload (excerpt, same pattern everywhere)
from app.services.tally_xml import x

               <LEDGERNAME>{x(lname)}</LEDGERNAME>
...
        vch_tag_attrs = f'REMOTEID="{x(guid_val)}" VCHTYPE="{x(vtype_name)}" ACTION="{x(action)}" OBJVIEW="{x(obj_view)}"'
...
                <SVCURRENTCOMPANY>{x(comp_name)}</SVCURRENTCOMPANY>
...
              <PARTYNAME>{x(party_ledger_name)}</PARTYNAME>
              <PARTYLEDGERNAME>{x(party_ledger_name)}</PARTYLEDGERNAME>
              <NARRATION>{x(voucher.narration)}</NARRATION>
...
               <PAYMENTURL>{x(pl.payment_url)}</PAYMENTURL>
```

The agent has the same problem when it adds the company name (`tally_client.py:200`, `agent.py:368,372`): `"A & B Traders"` breaks every export. Use `xml.sax.saxutils.escape` there too.

Test to add (backend): build a voucher whose party is `Shah & Sons <Kolkata>` and whose narration contains `"&<>`; assert `xml.etree.ElementTree.fromstring(payload)` parses, and that the `LEDGERNAME` text round-trips exactly.

### F2. Replace the health check that can freeze Tally (High)

`tally_client.py:40` sends `<TYPE>Data</TYPE><ID>Company</ID>`, which asks Tally to render its built-in `Company` form. That is what vaijaaaaa documents as raising *"Error in TDL. 'Form:Company' No 'PARTS'!"*, and it's the same class of request your safety rules say opens a modal and stops the XML server. It runs from `agent.py:397`, once per inbound cycle while Tally is unreachable, so it fires right as Tally comes back.

```python
# desktop-sync-agent/tally_client.py
HEALTH_XML = """<ENVELOPE><HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Collection</TYPE><ID>MyTallyPing</ID></HEADER>
<BODY><DESC><STATICVARIABLES><SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT></STATICVARIABLES>
<TDL><TDLMESSAGE><COLLECTION NAME="MyTallyPing" ISMODIFY="No"><TYPE>Company</TYPE><FETCH>NAME</FETCH></COLLECTION></TDLMESSAGE></TDL>
</DESC></BODY></ENVELOPE>"""

def check_health(self) -> Tuple[bool, str]:
    """Pings Tally with a Company collection (never a built-in report, which can open a modal)."""
    try:
        data = self._post(HEALTH_XML, timeout=self.timeout)
        return "<ENVELOPE>" in data, "Connected"
    except urllib.error.URLError as e:
        return False, f"Unreachable ({e.reason})"
    except Exception as e:
        return False, str(e)
```

**Verify:** if Tally ever showed the "Form:Company" or "No PARTS" popup on the sync PC right after it reconnected, this was the cause.

### F3. Make requests to Tally take turns (High)

**Agent.** `TallyClient` has no lock, and `gui_app.py:542,581` creates *separate* clients on worker threads (`gui_app.py:546,593`) while the daemon thread may be in the middle of a 120 s export. A lock on one client wouldn't help, so the lock has to be shared by every client in the process. Route every request through one method:

```python
# desktop-sync-agent/tally_client.py
import threading

# Tally's XML server answers one request at a time. The daemon and the GUI's buttons each create their own
# TallyClient on their own thread, so this lock is shared by every client in the agent.
_TALLY_LOCK = threading.Lock()

class TallyClient:
    def _post(self, xml: str, timeout: float, lock_wait: float = 30) -> str:
        """POST one request to Tally, one at a time across the whole agent."""
        if not _TALLY_LOCK.acquire(timeout=lock_wait):
            raise TimeoutError("Tally is busy with another request from this agent")
        try:
            req = urllib.request.Request(self.tally_url, data=xml.encode("utf-8"),
                                         headers={"Content-Type": "text/xml;charset=utf-8"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        finally:
            _TALLY_LOCK.release()
```

Then replace the five copies of `urllib.request.urlopen` in `check_health`, `discover_tally_host`, `get_open_companies`, `export_full_collections` and `send_xml` with `self._post(...)`.

**Backend (direct-push mode, `TALLY_URL`).** About 20 call sites run `_post_to_tally_sync` / `_post_json_to_tally_sync` through `asyncio.to_thread`, so two users saving at once reach Tally at once. The backend already runs a single worker (README), so a thread lock is enough:

```python
# backend/app/routers/sync.py
import threading
_TALLY_LOCK = threading.Lock()  # one request at a time to Tally, across all API requests in this process

def _post_to_tally_sync(url: str, xml_payload: str, timeout: int = 30) -> str:
    with _TALLY_LOCK:
        return _post_to_tally_unlocked(url, xml_payload, timeout)  # the current body, renamed
```

The agent and the backend can still collide with each other. Use one of the two paths per company, not both.

### F4. Outbound timeouts and what happens after one (Medium)

`send_xml` uses `self.timeout = 6` s (`tally_client.py:29,329`). Backend pushes use 5–10 s. A voucher with many lines, or a Tally busy recalculating, takes longer, and the post is then reported as failed even though Tally may have saved it. Because the `REMOTEID` is stable, the resend alters the same voucher rather than duplicating it, which is good. But it also brings back a voucher someone deleted or cancelled in Tally in the meantime (ComplyEaze `agent_import_post.rs:710-711`).

1. Give imports a longer timeout: `send_xml(self, xml_payload, timeout=60)`. Keep short timeouts for pings.
2. After a timeout, look the voucher up by `REMOTEID` before resending. **Verify** on a scratch company; `$RemoteID` is used as a voucher method by ComplyEaze (`src/tally/tdl_engine.rs:154`).

```xml
<ENVELOPE><HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Collection</TYPE><ID>MyTallyFindVch</ID></HEADER>
<BODY><DESC><STATICVARIABLES>
  <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
  <SVCURRENTCOMPANY>{x(company)}</SVCURRENTCOMPANY>
  <SVFROMDATE TYPE="Date">{yyyymmdd}</SVFROMDATE><SVTODATE TYPE="Date">{yyyymmdd}</SVTODATE>
</STATICVARIABLES><TDL><TDLMESSAGE>
  <SYSTEM TYPE="Formulae" NAME="MyTallyByRemoteId">$RemoteID = "{remote_id}"</SYSTEM>
  <COLLECTION NAME="MyTallyFindVch" ISMODIFY="No"><TYPE>Voucher</TYPE>
    <FETCH>GUID,ALTERID,VOUCHERNUMBER,DATE,ISCANCELLED</FETCH><FILTERS>MyTallyByRemoteId</FILTERS>
  </COLLECTION>
</TDLMESSAGE></TDL></DESC></BODY></ENVELOPE>
```

Only build this when `remote_id` matches `^[A-Za-z0-9-]+$` (yours are `MYTALLY-VCH-<id>` or a GUID), since it goes inside a formula. If the voucher is found, acknowledge the task instead of resending it.

### F5. Read import results as numbers (Medium)

`tally_client.py:335-344` looks for exact strings such as `<CREATED>1</CREATED>`. A batch that creates 2 objects (`<CREATED>2</CREATED>`) is reported as failed and resent, and `<EXCEPTIONS>` is never checked.

```python
# desktop-sync-agent/tally_client.py
import re
_COUNT = re.compile(r"<(CREATED|ALTERED|DELETED|CANCELLED|IGNORED|ERRORS|EXCEPTIONS)>\s*(\d+)\s*</\1>")

def parse_import_result(resp: str) -> Tuple[bool, str]:
    """True only when Tally reports no errors or exceptions and accepted at least one object."""
    if not resp or not resp.strip():
        return False, "Empty response (is a company open in Tally?)"
    if resp.lstrip().startswith("<EXCEPTION>"):
        return False, "Tally exception: " + re.sub(r"<[^>]+>", " ", resp).strip()[:300]
    line_errors = [e.strip() for e in re.findall(r"<LINEERROR>(.*?)</LINEERROR>", resp, re.S)]
    if line_errors:
        return False, " | ".join(line_errors)[:500]
    counts: Dict[str, int] = {}
    for key, value in _COUNT.findall(resp):
        counts[key] = counts.get(key, 0) + int(value)
    if counts.get("ERRORS") or counts.get("EXCEPTIONS"):
        return False, f"Tally reported {counts.get('ERRORS', 0)} error(s), {counts.get('EXCEPTIONS', 0)} exception(s)"
    # IGNORED is kept as accepted: it's what a resend of an already-saved object can return
    accepted = sum(counts.get(k, 0) for k in ("CREATED", "ALTERED", "DELETED", "CANCELLED", "IGNORED"))
    return (accepted > 0, "OK" if accepted else f"Tally changed nothing ({counts or 'no counts'})")
```

`send_xml` then becomes `resp = self._post(xml_payload, timeout); ok, why = parse_import_result(resp); return ok, resp if ok else why`. Add unit tests with fixture responses for each branch: an `EXCEPTION` wrapper, a `LINEERROR`, `ERRORS` 1, `EXCEPTIONS` 1, `CREATED` 2, and everything zero.

### F6. Pin the company by GUID instead of following whatever is open (Medium)

In `check_and_handle_company_switch`, if the configured company isn't open, the agent switches to `open_cmps[0]` (matched by name) and carries on syncing. If an accountant opens a different company, the agent starts syncing that one. The agent already stores `active_company_guid`.

```python
# desktop-sync-agent/agent.py: check_and_handle_company_switch (replace the switch branch)
match = next((c for c in open_cmps if self.active_company_guid and c.get("guid") == self.active_company_guid), None)
if match is None:
    # Same name but a different GUID is a different company (a restore, or a copy), not the one we sync
    if not self.company_paused:
        logger.warning(f"⏸️ '{self.active_company_name}' (GUID {self.active_company_guid}) isn't open in Tally; "
                       f"sync paused. Open companies: {', '.join(c['name'] for c in open_cmps)}")
    self.company_paused = True
    return
self.company_paused = False
self.active_company_name = match["name"]  # a rename in Tally is fine; the GUID is what identifies it
```

Initialise `self.company_paused = False` in `__init__`, and return early from both `sync_outbound_cycle` and `sync_inbound_cycle` while it's set. Setting `tally_connected = False` instead wouldn't hold the pause, because the inbound pre-flight (`agent.py:396-402`) reconnects on the next cycle. The inbound cycle also needs to call `check_and_handle_company_switch()`; today only the outbound cycle does (`agent.py:342`).

Switching companies should stay an explicit action in the GUI (Auto-Detect → Save).

### F7. Ask Tally for the fields the importer reads (Medium)

| Collection | Add to `FETCH` | Why |
|---|---|---|
| Ledgers (`tally_client.py:205`) | `GUID,LEDGSTREGDETAILS.LIST,LEDMAILINGDETAILS.LIST` | The importer reads all three (`tally_xml_importer.py:1420-1477`). Without `GUID` it falls back to `REMOTEID`, then to a random `GEN-…` id. TallyPrime 3+ keeps GSTIN, state and pincode in the two `.LIST`s |
| Groups, StockGroups (`:204,207`) | `GUID` | Same fallback |
| Vouchers (`:211`) | `ISCANCELLED,ISOPTIONAL` | The importer reads them (`tally_xml_importer.py:1908-1909`), and every report filters on them. ComplyEaze fetches them explicitly |

**Verify** whether cancelled vouchers are reaching the mirror today. Compare Tally's count of cancelled vouchers for a month with the database:

```sql
SELECT COUNT(*) FROM tally_sync.vouchers WHERE company_id = ? AND is_cancelled = 1 AND voucher_date BETWEEN ? AND ?;
```

If the database shows 0 and Tally doesn't, cancelled vouchers are being counted as live in every report.

### F8. Export large books in windows (Medium)

`tally_client.py:223` asks for every voucher dated 2000–2099 in one response. On a large book that's a very large payload and a long hold on Tally's single request slot. Page by AlterID instead, as ComplyEaze does:

```python
# desktop-sync-agent/tally_client.py (sketch): inside export_full_collections, for Vouchers only
WINDOW = 5000
low = min_alter_id
while True:
    high = low + WINDOW
    alter_system_xml = f'<SYSTEM TYPE="Formulae" NAME="AlteredFilter">$ALTERID &gt; {low} AND $ALTERID &lt;= {high}</SYSTEM>'
    resp = self._post(build_request(alter_filter_xml="<FILTERS>AlteredFilter</FILTERS>", alter_system_xml=alter_system_xml), timeout=120)
    if has_collection_records(resp, "Voucher"):
        results.append(("Vouchers", resp))
    if high >= highest_voucher_alter_id:  # from the company's ALTVCHID, see N1
        break
    low = high
```

### F9. Don't switch off certificate checks (Low)

`_post_to_tally_sync` and `_post_json_to_tally_sync` set `check_hostname = False` and `CERT_NONE` for `https` URLs. Tally's XML port has no authentication, so anyone who can reach a tunnelled `TALLY_URL` can read and write the books, and turning off certificate checks also lets anyone in the path read and change what you send. Keep verification on. If a self-signed tunnel is truly needed, make it an explicit setting that is off by default.

### F10. Round amounts to paise once, before both the check and the XML (Low)

`vouchers.py:368-372` checks the balance on the `Decimal` amounts as entered, and `sync.py:426,435` then formats each line with `:.2f`. If the API accepts amounts with more than 2 decimals, the rounded lines can disagree by a paisa and Tally rejects the voucher. Quantize on input:

```python
# backend/app/schemas/voucher.py: on the entry model
from decimal import Decimal, ROUND_HALF_UP
from pydantic import field_validator

@field_validator("debit_amount", "credit_amount")
@classmethod
def to_paise(cls, v: Decimal) -> Decimal:
    return Decimal(v).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
```

### F11. Encoding (Low, verify)

The agent sends UTF-8 and decodes replies with `errors="replace"`. The references send and receive UTF-16LE. Tally escapes non-ASCII characters as `&#NNNN;` in XML, so this is probably fine. But `errors="replace"` would silently turn an unexpected byte into `�`, and the corrupted ledger name would then fail to match when posted back. **Verify:** create a ledger named `परीक्षण ₹ Test` in a scratch company, sync it, and confirm the name in MySQL is identical. If it isn't, switch to UTF-16LE as in anshveerturna `src/tally/client.ts`.

---

## 4. Recommended new features

| # | Feature | Source of the technique | Value | Effort |
|---|---|---|---|---|
| N1 | **Cheap change detection.** Before the 6 incremental exports each minute, read the company's `ALTVCHID` and `ALTMSTID` (one small request) and skip the exports when neither has moved past the watermark | ComplyEaze reads them as voucher and master high-water marks (`agent_import.rs:117-123`; fixtures above) | Far less load on Tally on idle minutes | Low. **Verify** both values increase on every create and alter |
| N2 | **"Check against Tally" for the trial balance.** For a period, fetch Tally's per-ledger `OpeningBalance / DebitTotals / CreditTotals / ClosingBalance` and compare them with the mirror. List the ledgers that differ | dhananjay `trial-balance` (Ledger collection with period variables) | Proves the mirror is complete, and pinpoints a missed voucher. It also checks the new period-aware trial balance | Medium |
| N3 | **Outstandings: due-date ageing and on-account amounts.** Add an ageing-basis switch (bill date or due date, defaulting to due date) and show unallocated advances per party separately from open bills | ComplyEaze `agent_outstandings.rs:26-94` | Matches how Indian credit terms are judged, and stops advances from hiding overdue bills | Medium |
| N4 | **Pre-post binding check.** Just before a queued voucher is sent, confirm every ledger name still resolves to the GUID it had when the voucher was created. If not, hold the task for review | ComplyEaze `agent_import_post.rs:2112-2140` | Prevents posting to a ledger renamed or merged in Tally | Medium |
| N5 | **Import confirmation by counter.** Record `ALTVCHID` before a post and confirm it moved by `CREATED` afterwards | ComplyEaze `agent_import_post.rs:1788-1800` | Catches "Tally said OK but saved nothing" | Low after N1 |
| N6 | **GSTIN history per party** from `LEDGSTREGDETAILS.LIST` (`APPLICABLEFROM`, `GSTIN`, `GSTREGISTRATIONTYPE`). Flag invoices dated before a GSTIN's start date | dhananjay `definition.mts:104-105`; ledger push template | GST compliance check, close to free after F7 | Low |
| N7 | **Live ledger statement from Tally** for disputes: one request returns opening balance and every voucher for a ledger and period | dhananjay `templates/report/ledger-account.njk` | Shows Tally's own figures when a customer disputes the mirror | Low |
| N8 | **Read retries with jitter, never for writes**: 3 attempts, 250 ms–2 s | ComplyEaze `runtime_control.rs` | Fewer spurious inbound failures | Low |

Not found in any of the five repositories: reading bank-statement PDFs. That would need a separate design.

---

## 5. Corrections to the earlier analysis

| Earlier claim (`tally_reference_repositories_deep_analysis.md`) | What the code shows |
|---|---|
| "Voucher balancing: float comparison in `vouchers.py`" | Uses `Decimal` (`vouchers.py:368-372`). Only the per-line rounding edge in F10 remains |
| "`<EXCEPTION>` is treated as success by `send_xml`" | Not quite: success needs a `<CREATED>1</CREATED>`-style match, so an exception reply fails. The real problems are the exact-string matching and the unchecked `EXCEPTIONS` count (F5) |
| "Multi-GSTIN not handled; fix the importer" | The importer already reads `LEDGSTREGDETAILS.LIST/GSTIN` first (`tally_xml_importer.py:1428`). The agent never asks for it (F7) |
| "Voucher exports are chunked: no" and "use `<FILTER>`" | `<FILTERS>` is valid; ComplyEaze uses it in requests captured from real Tally. The incremental filter works |
| `learnwithcc/tally-mcp` "circuit breaker" as a Tally pattern | That repo talks to Tally.so, a form builder |
| Not mentioned | The missing XML escaping (F1) and the health check that can freeze Tally (F2), the two highest-impact findings |

---

## 6. Order of work

1. **F1** escaping (backend and agent), with the round-trip test.
2. **F2** health check, and **F3** shared lock (agent first, then backend).
3. **F5** result parsing, with fixture tests, then **F4** timeouts and the `REMOTEID` lookup (verify on a scratch company).
4. **F7** fetch fields (and run the cancelled-voucher check), then **F6** GUID pinning.
5. **N1** change detection, then **F8** windowed export.
6. Features **N2**, **N3**, **N6** in whatever order the business needs.

Anything touching posting (F4, F5, N4, N5) should be tried on a copy of a real company before it reaches a customer's books.
