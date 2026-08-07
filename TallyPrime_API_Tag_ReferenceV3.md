# TallyPrime API — Complete Tag Reference (v3)

A single glossary of every tag/field used across TallyPrime's XML/JSON API — masters (Ledger, Group, Stock Item, Stock Group, Stock Category, Unit, Godown, Company), vouchers (Payment, Receipt, Sales, Purchase), report/query tags, and alternative integration patterns (incremental sync). Companion to `TallyPrime_API_Reference.md`.

> **Provenance history:**
> - v1 tags were built from the general native-JSON/XML object model (schema-consistent, not independently confirmed).
> - v2 cross-checked against TallyHelp's official developer docs (`help.tallysolutions.com/understanding-tally-xml-tags/`, `help.tallysolutions.com/sample-xml/`) — those tags are marked **verified**. One correction landed here: the response tag for last voucher ID is `LASTVCHID`, not `LASTVOUCHERID`.
> - v3 adds tags confirmed against two real, running integrations: a production Tally↔ERP sync daemon (uploaded by the user, live `POST` calls against a real TallyPrime instance) and the open-source [`tally-database-loader`](https://github.com/dhananjay1405/tally-database-loader) utility. These are marked **field-confirmed** — the strongest confidence level, since they're pulled from working code that has actually talked to TallyPrime, not just documentation examples.

---

## 1. Envelope / Transport tags

| Tag | Verified? | Purpose |
|---|---|---|
| `ENVELOPE` | verified | Root wrapper for every request and response. |
| `HEADER` | verified | Metadata block describing what kind of request this is. |
| `VERSION` | verified | Mandatory. Messaging format version, currently `1`. |
| `TALLYREQUEST` | verified | Declares intent: `Import` (save data into Tally), `Export` (retrieve data), or `Execute` (run a TDL action). |
| `TYPE` | verified | Refines the request. For Import: `Data`. For Export: `Data` (reports), `Collection` (multiple objects), `Object` (single object), `Function`. For Execute: `TDLAction`. |
| `SUBTYPE` | verified | Optional, only used with `TYPE=Object` — names the object class being fetched, e.g. `Ledger`. |
| `ID` | verified | Meaning depends on `TYPE`: Report/request name (Data), Collection name (Collection), Object ID or name (Object), Action name (Action), Function name (Function). Can carry a `TYPE="Name"` attribute, e.g. `<ID TYPE="Name">CustomerABC</ID>`. |
| `STATUS` | verified | Response-only. `1` = success, `0` = failure. |
| `BODY` | verified | Wraps the actual payload. |
| `IMPORTDATA` | verified | Older/alternate wrapper (still supported) for Import requests, containing `REQUESTDESC` and `REQUESTDATA`. |
| `REQUESTDESC` | verified | Inside `IMPORTDATA` — holds `REPORTNAME`. |
| `REPORTNAME` | verified | Inside `REQUESTDESC` — typically `"All Masters"` for master imports. |
| `REQUESTDATA` | verified | Inside `IMPORTDATA` — wraps the `TALLYMESSAGE` block(s), equivalent role to `DATA` in the simpler modern structure. |
| `DESC` | verified | Modern/simpler wrapper for request-scoped settings: `STATICVARIABLES`, `TDL`, `FETCHLIST`, `FUNCPARAMLIST`. |
| `DATA` | verified | Modern/simpler wrapper for the objects being imported, or the container for exported data in a response. |
| `TALLYMESSAGE` | verified | One block per master/voucher object being created/altered/deleted; takes `xmlns:UDF="TallyUDF"` namespace attribute. |

---

## 2. Query-control tags (Pull / Export operations)

| Tag | Verified? | Purpose |
|---|---|---|
| `STATICVARIABLES` | verified | Holds all system-variable (`SV...`) settings for the request — company, dates, export format. |
| `SVCURRENTCOMPANY` | verified | Name of the company to query. |
| `SVFROMDATE` / `SVTODATE` | verified | Date range filter, format `YYYYMMDD` (or `D-Mon-YYYY` with `TYPE="Date"`). |
| `SVEXPORTFORMAT` | verified | Output format, e.g. `$$SysName:XML` or `$$SysName:HTML`. |
| `EXPLODEFLAG` | verified | Boolean — toggles Detailed vs Condensed report mode. |
| `REPEATVARIABLES` | verified | Wraps `REPEATSET` blocks for requesting repeated variable ranges (e.g. multiple date ranges in one call). |
| `REPEATSET` | verified | One set of repeated variable values inside `REPEATVARIABLES`. |
| `FETCHLIST` | verified | For `TYPE=Object` pulls — lists which fields/methods to retrieve via `FETCH` children. |
| `FETCH` | verified | One field name inside `FETCHLIST` or a Collection's field list. |
| `FUNCPARAMLIST` | verified | Wraps `PARAM` values passed to a `TYPE=Function` request. |
| `PARAM` | verified | One parameter value inside `FUNCPARAMLIST`, optionally typed via `TYPE="Number"` etc. |
| `TDL` | verified | Wraps custom TDL needed to serve a request when the target Report/Collection/Object/Function doesn't already exist in Tally. |
| `TDLMESSAGE` | verified | Mandatory container inside `TDL` holding the actual definitions (`REPORT`, `FORM`, `PART`, `LINE`, `FIELD`, `COLLECTION`, `OBJECT`, `SYSTEM`). |

---

## 3. TDL definition tags (used when defining custom Reports/Collections inline)

| Tag | Verified? | Purpose |
|---|---|---|
| `REPORT` | verified | Defines a report; `NAME` attribute names it, `FORMS` child lists the form(s) it uses. |
| `FORM` | verified | Defines a form; `TOPPARTS` lists the part(s) it displays, plus layout tags `HEIGHT`/`WIDTH`. |
| `PART` | verified | Defines a part; `TOPLINES`/`REPEAT` control which lines repeat over a collection, `SCROLLED` and `COMMONBORDERS` control display. |
| `LINE` | verified | Defines a line; `LEFTFIELDS`/`RIGHTFIELDS` place fields, `USE` inherits from another line, `XMLTAG` names the tag used when this line's data is exported as XML. |
| `FIELD` | verified | Defines a field; `SET` gives its value expression (e.g. `$Name`, `$ClosingBalance`), `USE` inherits from another field, `BORDER` controls styling. |
| `COLLECTION` | verified | Defines a queryable list of objects. Key attributes: `NAME`, `ISMODIFY` (Yes = alter an existing built-in collection), `ISFIXED`, `ISINITIALIZE`, `ISOPTION`, `ISINTERNAL`. Children: `TYPE` (object class), `CHILDOF`, `FETCH`, `FILTER`/`FILTERS`, `ADD`, `NATIVEMETHOD`. |
| `OBJECT` | verified | Defines a custom object for `TYPE=Object` requests; `NAME` attribute, `ISINITIALIZE` attribute, can carry `LOCALFORMULA`. |
| `SYSTEM` | verified | Defines a named Formula (`TYPE="Formulae"`) used by `FILTER`; body holds the expression, e.g. `$VoucherTypeName=Sales`. |
| `LOCAL` | verified | Modifies part of an existing definition inline, e.g. `Collection : Default : Add : Filter : VchTypeFilter`. |
| `ADD` | verified | Shorthand modification instruction inside a `COLLECTION`, e.g. `CHILD OF : Bank Accounts`. |
| `NATIVEMETHOD` | verified | Declares a built-in field to expose on a Collection, e.g. `Name`, `Parent`. |
| `LOCALFORMULA` | verified | Inline formula attached to an `OBJECT` definition. |
| `TITLE` | verified | Display title for a custom report. |
| `CHILDOF` | schema-consistent | Restricts a Collection to children of a named parent (Group/Stock Group). |
| `FILTER` / `FILTERS` | verified | References named `SYSTEM` Formulae to include/exclude records from a Collection or Report. |

---

## 4. Common object-level tags (masters)

| Tag | Verified? | Purpose |
|---|---|---|
| `NAME` | verified | The master's identifying name. As an attribute (`LEDGER NAME="..."`) or child tag depending on style used. |
| `Action` / `ACTION` | verified | Declares the operation: `Create`, `Alter`, `Delete` (Tally accepts both cases). |
| `PARENT` | verified | Name of the parent Group/Stock Group this master belongs to. |
| `GUID` | field-confirmed | Globally unique ID Tally assigns to every master and voucher — the stable identifier to key off when syncing into an external database, since names can be renamed. |
| `ALTERID` | field-confirmed | Monotonically increasing integer that changes every time an object is created or modified. This is the backbone of **incremental sync** — see section 16. |

---

## 5. Ledger-specific tags

| Tag | Verified? | Purpose |
|---|---|---|
| `ISBILLWISEON` | schema-consistent | Enables bill-by-bill outstanding tracking. |
| `OPENINGBALANCE` | verified | Opening balance on creation. |
| `CLOSINGBALANCE` | schema-consistent | Current balance — returned on Pull. |
| `GSTREGISTRATIONTYPE` | schema-consistent | Party's GST registration category. |
| `PARTYGSTIN` | schema-consistent | Party's GSTIN. |
| `MAILINGNAME.LIST` / `MAILINGNAME` | verified | List wrapper + value for the ledger's mailing name (also reused for Part No. on stock items — see section 6). |
| `ADDRESS.LIST` / `ADDRESS` | verified | List wrapper + repeatable address lines. |
| `PINCODE` | verified | Postal code. |
| `COUNTRYNAME` | verified | Country name. |
| `LEDSTATENAME` | verified | State name (ledger-specific state field). |
| `EMAIL` | verified | Primary contact email. |
| `EMAILCC` | verified | CC email address. |
| `LEDGERPHONE` | verified | Landline/phone number. |
| `LEDGERMOBILE` | verified | Mobile number. |

---

## 6. Group-specific tags

| Tag | Verified? | Purpose |
|---|---|---|
| `ISADDABLE` | schema-consistent | Whether sub-ledgers/sub-groups can be created directly under this group. |

---

## 7. Stock Item-specific tags

| Tag | Verified? | Purpose |
|---|---|---|
| `BASEUNITS` | verified | Primary unit of measure (must be a defined Unit). |
| `GSTAPPLICABLE` | schema-consistent | Whether GST applies to this item. |
| `HSNCODE` | schema-consistent | HSN code for GST classification. |
| `GSTTYPEOFSUPPLY` | schema-consistent | `Goods` or `Services`. |
| `OPENINGBALANCE` | verified | Opening stock quantity. |
| `OPENINGRATE` | verified | Rate applied to opening stock. |
| `OPENINGVALUE` | verified | Opening stock value. |
| `CLOSINGBALANCE` / `CLOSINGVALUE` | schema-consistent | Current stock qty/value — returned on Pull. |
| `STANDARDPRICELIST.LIST` | verified | Wrapper for a standard selling price entry, holding `DATE` + `RATE`. |
| `STANDARDCOSTLIST.LIST` | verified | Wrapper for a standard cost price entry, holding `DATE` + `RATE`. |
| `GODOWN` | verified | Default godown/location name for the stock item (use `"Main Location"` if multi-godown isn't enabled). |
| `BATCHNAME` | verified | Batch name associated with the item. |
| `NAME.LIST` / `NAME` (repeated) | verified | Wrapper + repeatable entries for **Alias** names (enabled via "Provide aliases along with name?"). |
| `MAILINGNAME.LIST` / `MAILINGNAME` (repeated) | verified | Reused here for **Part Number** entries (enabled via "Use Part Number for stock items?"). |
| `CATEGORY` | field-confirmed | The Stock Item's Stock Category (a separate classification axis from Stock Group — see section 8a). |
| `INFGSTHSNCODE` | field-confirmed | The actual live field name for a stock item's HSN code as returned by TallyPrime's Collection export — supersedes the plain `HSNCODE` guess in earlier versions of this doc for GST-enabled items. |
| `INFGSTIGSTRATE` | field-confirmed | The stock item's IGST rate as returned by Collection export. |

---

## 8. Stock Group-specific tags

_Uses the common object tags (`NAME`, `PARENT`) — no additional unique tags found beyond those in section 4._

---

## 8a. Stock Category — a master type missing from earlier versions of this doc

`StockCategory` is a separate master type from Stock Group — it's a second, independent classification axis for stock items (e.g. Stock Group = "Electronics", Stock Category = "Fast Moving"). It didn't appear anywhere in the API Explorer nav or the TallyHelp pages checked so far; it turned up only in the production sync daemon's field list.

| Tag | Verified? | Purpose |
|---|---|---|
| `NAME` | field-confirmed | Category name. |
| `PARENT` | field-confirmed | Parent Stock Category (categories can nest, same as Stock Groups). |

Fetched via a `Collection` with `TYPE=StockCategory`, same pattern as any other master collection pull.

---

## 9. Unit-specific tags

| Tag | Verified? | Purpose |
|---|---|---|
| `ISSIMPLEUNIT` | verified | `Yes` = standalone unit (Nos, Kg); `No` = compound unit. |
| `ORIGINALNAME` | verified | Formal/long-form name of the unit (e.g. `Pieces` for `Pcs`) — used when **creating** a unit. |
| `SYMBOL` | field-confirmed | The unit's short display symbol as returned when **pulling** units via Collection — a different field name than `ORIGINALNAME`/`NAME` used on Create; worth fetching both `NAME` and `SYMBOL` since Tally exposes them separately on read. |
| `DECIMALPLACES` | verified | Decimal places allowed for quantities (simple units). |
| `BASEUNITS` | verified | Base (smaller) unit in a compound unit. |
| `ADDITIONALUNITS` | verified | Additional (larger) unit in a compound unit. |
| `CONVERSION` | verified | Conversion factor from base to additional unit. |

Note: for compound units, the `NAME` tag value is ignored — Tally auto-generates the compound unit's name from the base/additional/conversion combination.

---

## 10. Godown / Location tags

| Tag | Verified? | Purpose |
|---|---|---|
| `GODOWN` (as a master, `Action="Create"`) | verified | Creates a Location/Godown master, identified by `NAME`. Default godown is `"Main Location"`. |

---

## 11. Voucher tags — common to all types

| Tag | Verified? | Purpose |
|---|---|---|
| `VOUCHER` | verified | Root tag for a voucher. Can carry attributes `VCHTYPE`, `ACTION`, `OBJVIEW` in the compact single-tag style, or use child tags for the same info. |
| `VCHTYPE` (attribute) | verified | Voucher type name, e.g. `Sales`, `Payment`. |
| `VOUCHERTYPENAME` (child tag) | verified | Same info as `VCHTYPE`, as a child element — used in the modern DATA/TALLYMESSAGE style. |
| `PERSISTEDVIEW` | verified | Declares voucher behaviour/UI mode: `Accounting Voucher View`, `Invoice Voucher View`, `Inventory Voucher View`, `Pay Slip Voucher View`, `Consumption Voucher View`, `Multi Consumption Voucher View`. |
| `OBJVIEW` | verified | Similar role to `PERSISTEDVIEW`, set on the `VOUCHER` opening tag itself in some styles. |
| `DATE` | verified | Voucher date, `YYYYMMDD`. |
| `VOUCHERNUMBER` | verified | Voucher number — used to identify a voucher for Alter/Delete/Cancel. |
| `ISINVOICE` | verified | Boolean — whether the voucher is recorded as an invoice (`Yes`) or plain voucher (`No`). |
| `NARRATION` | schema-consistent | Free-text notes on the voucher. |
| `PARTYLEDGERNAME` | schema-consistent | The customer/supplier ledger, used in Sales/Purchase. |
| `LEDGERENTRIES.LIST` | verified | Older/voucher-mode style ledger entry wrapper (one block per posting). |
| `ALLLEDGERENTRIES.LIST` | schema-consistent | Modern equivalent wrapper for ledger postings, used across the curl reference doc. |
| `LEDGERNAME` | verified | Ledger being posted to, inside a ledger entry. |
| `ISDEEMEDPOSITIVE` | verified | Debit/credit flag for the entry — convention differs by voucher type and entry role (see notes in the curl reference doc). |
| `ISPARTYLEDGER` | verified | Flags whether this specific ledger entry is the party (customer/supplier) ledger. |
| `ISLASTDEEMEDPOSITIVE` | verified | Internal bookkeeping flag Tally uses/returns alongside `ISDEEMEDPOSITIVE` on the last entry of a set. |
| `AMOUNT` | verified | Posted amount for the entry. |
| `TAGNAME` / `TAGVALUE` (on `VOUCHER` attributes) | verified | Alternate way to identify an existing voucher for Alter/Cancel, e.g. `TAGNAME="Voucher Number" TAGVALUE="1"`, alongside `DATE` and `VCHTYPE`. |
| `Action="Cancel"` | verified | Used instead of `Alter`/`Delete` to cancel a voucher while keeping it in the books as cancelled. |

---

## 12. Bill / Accounting / Batch allocation tags (nested inside ledger and inventory entries)

| Tag | Verified? | Purpose |
|---|---|---|
| `BILLALLOCATIONS.LIST` | verified | Wraps bill-tracking details for a party ledger entry — mandatory only for party ledgers with bill-wise tracking on. |
| `NAME` (inside BILLALLOCATIONS) | verified | Bill name/number. |
| `BILLTYPE` | verified | `Advance`, `Agst Ref`, `New Ref`, or `On Account` — how this payment/receipt relates to outstanding bills. |
| `AMOUNT` (inside BILLALLOCATIONS) | verified | Amount allocated to this specific bill. |
| `ACCOUNTINGALLOCATIONS.LIST` | verified | Wraps the accounting-side ledger postings (e.g. Sales, Tax) generated by an inventory line item. |
| `BATCHALLOCATIONS.LIST` | verified | Wraps batch-tracking details for an inventory entry. |
| `GODOWNNAME` | verified | Godown the batch quantity is stored in/moved from. |
| `DESTINATIONGODOWNNAME` | verified | Destination godown for stock transfers within a batch allocation. |
| `BATCHNAME` (inside BATCHALLOCATIONS) | verified | Batch identifier for this allocation. |
| `ACTUALQTY` | verified | Physical quantity, with unit, e.g. `1 nos`. |
| `BILLEDQTY` | verified | Quantity actually billed (can differ from actual in free-sample/partial-billing cases). |

---

## 13. Inventory entry tags (Sales/Purchase line items)

| Tag | Verified? | Purpose |
|---|---|---|
| `ALLINVENTORYENTRIES.LIST` | verified | Wraps all stock item line entries on an invoice/voucher. |
| `INVENTORYALLOCATIONS.LIST` | verified | Voucher-mode style alternative used to break down a sales/purchase ledger amount by stock item, nested under the ledger entry rather than as a sibling list. |
| `STOCKITEMNAME` | verified | Stock item being sold/purchased on this line. |
| `RATE` | verified | Price per unit, format `"<amount>/<unit>"`, e.g. `15000.00/nos`. |
| `AMOUNT` (inventory entry) | verified | Line total (rate × qty). |
| `PLACEOFSUPPLY` | schema-consistent | State/location used to determine GST treatment. |
| `GSTRATE` / `GSTHSNNAME` | schema-consistent | GST percentage and HSN override applied to this specific line. |
| `BASICRATEOFINVOICETAX.LIST` / `BASICRATEOFINVOICETAX` | verified | Tax rate applied at invoice level (older VAT-era pattern, still supported). |
| `ROUNDTYPE` | verified | Rounding method tag seen on tax ledger entries. |

---

## 14. Response tags (returned by TallyPrime, not sent by the client)

| Tag | Verified? | Purpose |
|---|---|---|
| `RESPONSE` | verified | Root of the acknowledgement after an Import request. |
| `CREATED` | verified | Count of new masters/transactions created. |
| `ALTERED` | verified | Count altered. |
| `DELETED` | verified | Count deleted. |
| `LASTVCHID` | verified | Master ID of the last voucher imported. **(Correction: earlier version of this doc had this as `LASTVOUCHERID` — the real tag is `LASTVCHID`.)** |
| `LASTMID` | verified | Last Master ID — per TallyHelp, this always returns `0`. |
| `COMBINED` | verified | Count of masters combined with existing ones. |
| `IGNORED` | verified | Count of masters ignored. |
| `ERRORS` | verified | Count of errors during import. |
| `CANCELLED` | verified | Count of transactions cancelled. |
| `LINEERROR` | verified | Human-readable error text for a failed record, e.g. a Dr/Cr mismatch. |
| `VCHNUMBER` | verified | Voucher number referenced in an error response. |
| `DESC` (in error response) | verified | Present but typically empty in error payloads. |

---

## 15. Common report-level static variables

| Tag | Verified? | Purpose |
|---|---|---|
| `SVFROMDATE` / `SVTODATE` | verified | Report period, `YYYYMMDD`. |
| `SVEXPORTFORMAT` | verified | `$$SysName:XML` or `$$SysName:HTML`. |
| `EXPLODEFLAG` | verified | Detailed vs condensed report mode. |
| `AccountType` | verified | Used with report `List of Accounts` to scope the master type returned, e.g. `Stock Items`. |

Frequently-used built-in report `ID` names (per TallyHelp): `Day Book`, `Trial Balance`, `Ledger Vouchers` (needs `LedgerName`), `Ledger Outstandings` (needs `LedgerName`), `Bills Payable`, `Bills Receivable`, `Group Outstandings` (needs `GroupName`), `List of Accounts`.

---

## Quick index — which section covers which operation

| Operation group | Relevant sections |
|---|---|
| Ledger (Create/Alter/Delete/Pull) | 1, 2, 4, 5, 14 |
| Group (Create/Alter/Delete/Pull) | 1, 2, 4, 6, 14 |
| Stock Item (Create/Alter/Delete/Pull) | 1, 2, 4, 7, 14 |
| Stock Group (Create/Alter/Delete/Pull) | 1, 2, 4, 8, 14 |
| Unit (Create/Alter/Delete/Pull) | 1, 2, 4, 9, 14 |
| Godown/Location (Create) | 1, 10 |
| Payment / Receipt (Create/Alter/Delete/Pull) | 1, 2, 11, 12, 14 |
| Sales / Purchase (Create/Alter/Delete/Pull) | 1, 2, 11, 12, 13, 14 |
| Custom report/collection building | 1, 2, 3, 15 |
