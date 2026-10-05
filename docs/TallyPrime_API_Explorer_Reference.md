# TallyPrime API Reference — API Explorer Edition

> **Source:** [TallyPrime API Explorer](https://tallysolutions.com/tallyprime-api-explorer/) (all 63 APIs, every request payload copied verbatim from the Explorer's own page scripts), plus Tally's official [JSON integration guide](https://help.tallysolutions.com/tally-prime-integration-using-json-1/) for headers and response formats.
> **Retrieved:** 2026-10-05 · **JSON support:** TallyPrime 7.0+ · **XML support:** all TallyPrime releases
> **Audience:** MyTally backend and sync-agent developers. Keep this file as the permanent reference for Tally integration work.

Every sample in this document is tagged with where it came from:

| Tag | Meaning |
|---|---|
| 🟢 **Official** | Copied verbatim from the API Explorer or a Tally-published sample. |
| 🔵 **Observed** | Captured from a live TallyPrime and recorded in this repo's docs. |
| 🟡 **Illustrative** | Correct structure, invented values, or a shape inferred from official samples. **Verify against your TallyPrime build before you hard-code parsers.** |

The Explorer publishes request payloads but **no response samples**, so most response bodies here are 🟢/🔵 for imports and 🟡 for exports and reports.

## Table of Contents

- [1. Integration Fundamentals](#1-integration-fundamentals)
  - [1.1 How TallyPrime Exposes Its API](#11-how-tallyprime-exposes-its-api)
  - [1.2 Environment Setup and the Explorer Connector](#12-environment-setup-and-the-explorer-connector)
  - [1.3 JSON vs XML at a Glance](#13-json-vs-xml-at-a-glance)
  - [1.4 HTTP Headers (JSON)](#14-http-headers-json)
  - [1.5 Request Type Matrix](#15-request-type-matrix)
  - [1.6 Request Body Sections](#16-request-body-sections)
  - [1.7 Static Variables](#17-static-variables)
  - [1.8 XML Envelope Styles](#18-xml-envelope-styles)
  - [1.9 Response Structure](#19-response-structure)
  - [1.10 Common Error Responses](#110-common-error-responses)
  - [1.11 Data Types and Value Conventions](#111-data-types-and-value-conventions)
  - [1.12 Integration Best Practices](#112-integration-best-practices)
  - [1.13 Provenance and Accuracy Notes](#113-provenance-and-accuracy-notes)
- [2. Accounting Masters](#2-accounting-masters)
  - [2.1 Ledger](#21-ledger)
    - [2.1.1 Create a Ledger](#211-create-a-ledger)
    - [2.1.2 Alter a Ledger](#212-alter-a-ledger)
    - [2.1.3 Delete a Ledger](#213-delete-a-ledger)
    - [2.1.4 Pull a Ledger](#214-pull-a-ledger)
    - [2.1.5 Pull All Ledgers](#215-pull-all-ledgers)
    - [2.1.6 Pull Ledgers of Group](#216-pull-ledgers-of-group)
  - [2.2 Group](#22-group)
    - [2.2.1 Create a Group](#221-create-a-group)
    - [2.2.2 Alter a Group](#222-alter-a-group)
    - [2.2.3 Delete a Group](#223-delete-a-group)
    - [2.2.4 Pull a Group](#224-pull-a-group)
    - [2.2.5 Pull All Groups](#225-pull-all-groups)
    - [2.2.6 Pull Groups of Group](#226-pull-groups-of-group)
- [3. Inventory Masters](#3-inventory-masters)
  - [3.1 Stock Item](#31-stock-item)
    - [3.1.1 Create a Stock Item](#311-create-a-stock-item)
    - [3.1.2 Alter a Stock Item](#312-alter-a-stock-item)
    - [3.1.3 Delete a Stock Item](#313-delete-a-stock-item)
    - [3.1.4 Pull a Stock Item](#314-pull-a-stock-item)
    - [3.1.5 Pull All Stock Item](#315-pull-all-stock-item)
    - [3.1.6 Pull Stock Items of Stock Group](#316-pull-stock-items-of-stock-group)
  - [3.2 Stock Group](#32-stock-group)
    - [3.2.1 Create a Stock Group](#321-create-a-stock-group)
    - [3.2.2 Alter a Stock Group](#322-alter-a-stock-group)
    - [3.2.3 Delete a Stock Group](#323-delete-a-stock-group)
    - [3.2.4 Pull a Stock Group](#324-pull-a-stock-group)
    - [3.2.5 Pull All Stock Groups](#325-pull-all-stock-groups)
    - [3.2.6 Pull Stock Group With Zero Balance](#326-pull-stock-group-with-zero-balance)
  - [3.3 Units](#33-units)
    - [3.3.1 Create a Simple Unit](#331-create-a-simple-unit)
    - [3.3.2 Create a Compound Unit](#332-create-a-compound-unit)
    - [3.3.3 Alter a Unit](#333-alter-a-unit)
    - [3.3.4 Delete a Unit](#334-delete-a-unit)
    - [3.3.5 Pull a Unit](#335-pull-a-unit)
    - [3.3.6 Pull all Units](#336-pull-all-units)
- [4. Transactions — Accounting Vouchers](#4-transactions--accounting-vouchers)
  - [4.1 Payment](#41-payment)
    - [4.1.1 Create a Payment with Banking details](#411-create-a-payment-with-banking-details)
    - [4.1.2 Create a Payment with Cash](#412-create-a-payment-with-cash)
    - [4.1.3 Alter a Payment](#413-alter-a-payment)
    - [4.1.4 Delete a Payment](#414-delete-a-payment)
    - [4.1.5 Pull all Payment vouchers](#415-pull-all-payment-vouchers)
    - [4.1.6 Pull all Payment vouchers for a period](#416-pull-all-payment-vouchers-for-a-period)
  - [4.2 Receipt](#42-receipt)
    - [4.2.1 Create a Receipt with Banking Details](#421-create-a-receipt-with-banking-details)
    - [4.2.2 Create a Receipt with Cash Details](#422-create-a-receipt-with-cash-details)
    - [4.2.3 Alter a Receipt](#423-alter-a-receipt)
    - [4.2.4 Delete a Receipt](#424-delete-a-receipt)
    - [4.2.5 Pull all Receipt vouchers](#425-pull-all-receipt-vouchers)
    - [4.2.6 Pull all Receipt vouchers for a period](#426-pull-all-receipt-vouchers-for-a-period)
  - [4.3 Sales](#43-sales)
    - [4.3.1 Create Sales with Item](#431-create-sales-with-item)
    - [4.3.2 Create Sales with GST](#432-create-sales-with-gst)
    - [4.3.3 Alter a Sales](#433-alter-a-sales)
    - [4.3.4 Delete a Sales](#434-delete-a-sales)
    - [4.3.5 Pull all Sales vouchers](#435-pull-all-sales-vouchers)
    - [4.3.6 Pull all Sales vouchers for a period](#436-pull-all-sales-vouchers-for-a-period)
  - [4.4 Purchase](#44-purchase)
    - [4.4.1 Create Purchase with Item](#441-create-purchase-with-item)
    - [4.4.2 Create Purchase with GST](#442-create-purchase-with-gst)
    - [4.4.3 Alter a Purchase](#443-alter-a-purchase)
    - [4.4.4 Delete a Purchase](#444-delete-a-purchase)
    - [4.4.5 Pull all Purchase vouchers](#445-pull-all-purchase-vouchers)
    - [4.4.6 Pull all Purchase vouchers for a period](#446-pull-all-purchase-vouchers-for-a-period)
- [5. Reports](#5-reports)
  - [5.1 Trial Balance](#51-trial-balance)
    - [5.1.1 Pull Trial Balance for any Period](#511-pull-trial-balance-for-any-period)
    - [5.1.2 Pull Trial Balance Detailed](#512-pull-trial-balance-detailed)
    - [5.1.3 Pull Trial Balance Plain Format](#513-pull-trial-balance-plain-format)
    - [5.1.4 Pull Trial Balance with Empty Fields](#514-pull-trial-balance-with-empty-fields)
    - [5.1.5 Pull Trial Balance Ledger wise](#515-pull-trial-balance-ledger-wise)
    - [5.1.6 Pull Trial Balance for a Group](#516-pull-trial-balance-for-a-group)
  - [5.2 Sales Register](#52-sales-register)
    - [5.2.1 Pull Sales Register for any Period](#521-pull-sales-register-for-any-period)
    - [5.2.2 Pull Sales Register Plain Format](#522-pull-sales-register-plain-format)
    - [5.2.3 Pull Sales Register with Empty Fields](#523-pull-sales-register-with-empty-fields)
- [Appendix A. API Index](#appendix-a-api-index)
- [Appendix B. Mapping to the MyTally Codebase](#appendix-b-mapping-to-the-mytally-codebase)
- [Appendix C. Sources](#appendix-c-sources)

# 1. Integration Fundamentals

## 1.1 How TallyPrime Exposes Its API

TallyPrime runs an embedded HTTP server. There is **one endpoint**: every operation (create, alter, delete, fetch, report) is an HTTP `POST` to the root path.

| Item | Value |
|---|---|
| Endpoint | `http://<tally-host>:<port>/` (default port **9000**) |
| Method | `POST` for all operations |
| Enable / change port | TallyPrime → **F1: Help → Settings → Connectivity → Client/Server configuration** (TallyPrime acts as *Server* or *Both*; Tally restarts if the port changes) |
| Authentication | None. Anyone who can reach the port can read and write the loaded company. **Never expose port 9000 to the internet**; keep it on localhost and reach it through an agent (such as MyTally's `desktop-sync-agent`). |
| Health check | `POST /` with an empty body. A running server replies `<RESPONSE>TallyPrime Server is Running</RESPONSE>` (🟢 the Explorer's *Validate Connection* button checks for this string). |
| Company check | Export the `Company` collection (headers `tallyrequest: export`, `type: collection`, `id: company`). A non-empty `data.collection` means a company is loaded (🟢 Explorer logic). |
| Concurrency | Tally processes requests one at a time. Serialise writes and keep batches small (a few hundred objects per request). |

**What the routing fields mean**

- `tallyrequest` (Import / Export) is the direction.
- `type` (Data / Collection / Object / Function) is the kind of target.
- `id` is the target's name: `All Masters` or `Vouchers` for imports, a collection or object name for exports, or a report name such as `Trial Balance`.

## 1.2 Environment Setup and the Explorer Connector

The Explorer's own setup steps (🟢):

1. Download *Integration Setup.zip*: a configured TallyPrime, the sample company **Bhrama Enterprises**, and `TallyAPIConnectorV2.0.exe`. If TallyPrime is already installed, download *Integration Setup Lite.zip*, which omits the TallyPrime install.
2. Start `tally.exe`. Without a licence, choose **Continue in Educational Mode**.
3. Configure the port (default 9000) and load the sample company.
4. Run `TallyAPIConnectorV2.0.exe` (V1.0 only supports port 9000) and keep its console open.
5. In the Explorer, set the Request URL to `http://localhost:<port>`.

> **Educational Mode restriction:** voucher dates can only be the **1st, 2nd or 31st** of a month. Any other date is rejected.

**The Connector is an Explorer-only CORS proxy.** The browser page cannot call Tally directly, so it posts to `http://127.0.0.1:3000` and passes the real Tally port in an `x-tally-port` header. Server-side code (MyTally backend, sync agent) must **call Tally directly** at `http://<host>:9000/` and must not send `x-tally-port`.

All sample payloads target the sample company `Bhrama Enterprises`. Replace `svCurrentCompany` with your company's exact name.

## 1.3 JSON vs XML at a Glance

| Aspect | JSON (native "JSONEx") | XML |
|---|---|---|
| Availability | TallyPrime **7.0+** | All versions (also Tally.ERP 9) |
| Routing (`tallyrequest`, `type`, `id`…) | **HTTP headers** | `<HEADER>` element inside the body |
| Body root | Object with `static_variables`, `fetch_list`, `tdlmessage`, `tallymessage` | `<ENVELOPE><HEADER/><BODY><DESC>…</DESC></BODY></ENVELOPE>` |
| Format switch | `svMstImportFormat` / `svVchImportFormat` / `svExportFormat` = `jsonex` | same variables = `XML` |
| Object identity | `"metadata": { "type", "name", "action", … }` | element name + attributes: `<LEDGER NAME="…" ACTION="Create">` |
| Lists | JSON arrays, e.g. `"allledgerentries": [ … ]` | repeated `<ALLLEDGERENTRIES.LIST>` elements |
| Logical values | `true`/`false` (also `"Yes"`/`"No"`) | `Yes`/`No` |
| Key / tag case | Case-insensitive (Explorer mixes `DATE`, `date`, `"Opening Balance"`) | Case-insensitive (Explorer uses `<StockItem>`, `<BaseUnits>`) |
| Empty fields in export | Omitted by default (set report attribute *Export Empty Fields*) | Always included |
| System-name prefix | `"\u0004 Primary"` | `&#4; Primary` |
| Multilingual | `content-type: application/json;charset=utf-8` or `utf-16`; `id-encoded` (base64) header | UTF-8/UTF-16 body |

> **Recommendation for MyTally:** use **JSON** where every connected TallyPrime is on 7.0 or later. The routing lives in headers, the bodies are smaller, and the responses are valid, predictable JSON. Keep the **XML** path as the fallback for older installations. Both carry the same Tally object model, so one internal model can serialise to either.

## 1.4 HTTP Headers (JSON)

🟢 From Tally's JSON integration guide:

| Header | Required | Values / Description |
|---|---|---|
| `content-type` | Yes | `application/json`. For multilingual data use `application/json;charset=utf-8` (UTF-8 / UTF-8 BOM body) or `application/json;charset=utf-16` (UTF-16 LE BOM body). When a charset is given, **Tally responds in UTF-16**. |
| `version` | Yes | `1` |
| `tallyrequest` | Yes | `Import` (post data) · `Export` (fetch data) |
| `type` | Yes | `Data` (imports and reports) · `Collection` · `Object` · `Function` |
| `subtype` | Only when `type: Object` | Object type: `Ledger`, `Group`, `StockItem`, `Stock Group`, `Unit`, … |
| `id` | Yes | Name of the report / collection / object / function, or `All Masters` / `Vouchers` for imports |
| `id-encoded` | Multilingual object fetch | Base64 of the UTF-8 name (e.g. `ಶ್ರೀ` → `4LK24LON4LKw4LOA`). Use it **instead of** `id`. |
| `detailed-response` | No | `Yes` adds per-object-type counts (`cmp_info`) to import responses. |

Header values are case-insensitive (`import`, `Import` and `IMPORT` all work). The Explorer sends lowercase.

## 1.5 Request Type Matrix

| Goal | `tallyrequest` | `type` | `subtype` | `id` | Body carries | Format variable |
|---|---|---|---|---|---|---|
| Create / alter / delete **masters** | Import | Data | — | `All Masters` | `tallymessage` | `svMstImportFormat` |
| Create / alter / delete **vouchers** | Import | Data | — | `Vouchers` | `tallymessage` | `svVchImportFormat` |
| Fetch **one object** | Export | Object | object type | object name | `fetch_list` (optional) | `svExportFormat` |
| Fetch a **collection** (default) | Export | Collection | — | `Ledger`, `Group`, `Stock Item`, `Stock Group`, `Unit`, `Company`… | — | `svExportFormat` |
| Fetch a **custom collection** | Export | Collection | — | name of the TDL collection sent in the body | `tdlmessage` | `svExportFormat` |
| Fetch a **report** | Export | Data | — | TDL report name (`Trial Balance`, `Sales Register`…) | `static_variables`, optional `tdlmessage` | `svExportFormat` |
| Call a **function** | Export | Function | — | function name | `func_param_list` | `svExportFormat` |

## 1.6 Request Body Sections

🟢 JSON body sections (all optional except where the operation needs them):

| Section | Purpose | XML equivalent |
|---|---|---|
| `static_variables` | `[{ "name": "…", "value": "…" }]`: company, formats, report period and switches | `<DESC><STATICVARIABLES><SVCURRENTCOMPANY>…</…>` |
| `repeat_variables` | Variables repeated in a report request | `<REPEATVARIABLES>` |
| `fetch_list` / `fetchlist` | Methods to return for a `type: Object` export | `<FETCHLIST><FETCH>Name</FETCH>…` |
| `func_param_list` | Parameters for `type: Function` | `<FUNCPARAMLIST><PARAM>` |
| `tdlmessage` | Inline TDL: `[{ "definitions": [ { "metadata": {name,type,…}, "attributes": [ {…} ] } ] }]` | `<TDL><TDLMESSAGE><COLLECTION NAME="…">…` |
| `tallymessage` | Objects to import: `[{ "metadata": {type,name,action…}, …fields }]` | `<TALLYMESSAGE><LEDGER NAME="…" ACTION="…">…` |

The full template from Tally's guide:

```json
{
  "static_variables": [ { "type": "", "key": "", "name": "", "value": "" } ],
  "repeat_variables": [ { "type": "", "key": "", "name": "", "value": [ "", "" ] } ],
  "fetchlist": [ "fieldA", "fieldB" ],
  "func_param_list": [ { "type": "", "value": "" } ],
  "tdlmessage": [
    { "descriptions": [ { "metadata": {}, "attributes": [] } ] },
    { "definitions": [] }
  ],
  "tallymessage": {}
}
```

**Inline TDL in practice:** a `tdlmessage` definition of `type: Collection` declares a collection on the fly. Its main attributes:

- `Type` is the object type, or `Vouchers:VoucherType` for vouchers.
- `Child Of` restricts to children of a parent (e.g. `$$GroupBank`, `$$VchTypeSales`, `"Gadgets"`).
- `Belongs To: Yes` includes all descendants.
- `Native Method` lists the fields to return.
- `Filters` names a `System`/`Formulae` definition, e.g. `$Date >= $$Date:"1-Apr-2025"`.

A definition of `type: Report` with `ismodify: true` changes a default report for this request only (e.g. *Plain XML*, *Export Empty Fields*, `Set`).

## 1.7 Static Variables

🟢 Mandatory variables (Tally JSON guide):

| Variable | Values | When | Behaviour if missing |
|---|---|---|---|
| `svExportFormat` | `jsonex` / `XML` | Every export (`tallyrequest: Export`) | Response may come back in the wrong format |
| `svMstImportFormat` | `jsonex` / `XML` | Master import (`id: All Masters`) | Import may fail |
| `svVchImportFormat` | `jsonex` / `XML` | Voucher import (`id: Vouchers`) | Import may fail |
| `svCurrentCompany` | Exact company name | Every request | Falls back to the active company, so data may go to the **wrong company**. Always send it. |

🟢 Common report variables (Explorer *Reports* page):

| Variable | Type | Example | Purpose |
|---|---|---|---|
| `SVFromDate` / `SVToDate` | Date | `20240401` / `20240430` | Report period |
| `SVCurrentDate` | Date | `20240402` | "As on" date (Day Book, Voucher Register) |
| `ExplodeFlag` | Logical | `Yes` | Expand grouped lines one level |
| `ExplodeAllLevels` | Logical | `Yes` | Expand all levels |
| `ShowForex` | Logical | `Yes` | Show foreign-currency values |
| `IsLedgerwise` | Logical | `Yes` | Trial Balance: ledger-level rows |
| `GroupName` | String | `"Sundry Debtors"` | Group Summary / Group Vouchers |
| `LedgerName` | String | `"Cash"` | Ledger Vouchers |
| `IsItemWise` | Logical | `Yes` | Stock Summary item-wise |
| `VoucherTypeName` | String | `"Sales"` | Day Book / Voucher Register filter |
| `SVExportInPlainFormat` | Logical | `Yes` | Plain (flat) report output (🟢 Tally JSON guide) |

## 1.8 XML Envelope Styles

The Explorer uses two XML envelope styles. Use one style consistently. Do not mix their elements.

**Style A: Version-1 envelope (used by every API page in the Explorer; recommended).** The `<TALLYMESSAGE>` sits inside `<DESC>`.

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>All Masters</ID>   <!-- or Vouchers -->
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
            <TALLYMESSAGE> … objects … </TALLYMESSAGE>
        </DESC>
    </BODY>
</ENVELOPE>
```

**Style B: legacy "Import Data" envelope (shown on the Explorer's overview pages; works on all versions).**

```xml
<ENVELOPE>
    <HEADER>
        <TALLYREQUEST>Import Data</TALLYREQUEST>
    </HEADER>
    <BODY>
        <IMPORTDATA>
            <REQUESTDESC>
                <REPORTNAME>All Masters</REPORTNAME>   <!-- or Vouchers -->
                <STATICVARIABLES><SVCURRENTCOMPANY>…</SVCURRENTCOMPANY></STATICVARIABLES>
            </REQUESTDESC>
            <REQUESTDATA>
                <TALLYMESSAGE> … objects … </TALLYMESSAGE>
            </REQUESTDATA>
        </IMPORTDATA>
    </BODY>
</ENVELOPE>
```

> 🔵 **Observed in this repo:** adding `<VERSION>1</VERSION>` to a Style-B envelope (`Import Data`) makes Tally reply `<RESPONSE>Unknown Request, cannot be processed</RESPONSE>`.

## 1.9 Response Structure

### JSON response template (🟢 Tally JSON guide)

```json
{
  "status": "1/0",
  "cmp_info": { "_note": "not applicable for data" },
  "parms": [ "applicable for repeat variables" ],
  "tallymessage": [ "applicable for objects (type: Object, or full object exports such as Day Book)" ],
  "data": { "_note": "applicable for collection and data (import result / report) export" },
  "result": { "_note": "applicable for function" }
}
```

Where the payload appears, by request type:

| Request | Payload location | Shape |
|---|---|---|
| Import (`type: Data`, `tallyrequest: Import`) | `data.import_result` | counters (table below) |
| Object export | `tallymessage[]` | `{ "metadata": {...}, "<method>": { "type": "<TallyType>", "value": … } }` |
| Collection export | `data.collection[]` + `data.metadata` | same object shape as above |
| Report export | `data.<report tree>` | lowercase report tags, arrays for repeated lines |
| Function | `result` | function value |

**`import_result` fields** (🟢 Tally samples):

| Field | Type | Meaning |
|---|---|---|
| `created` | Number | Objects created |
| `altered` | Number | Objects altered |
| `deleted` | Number | Objects deleted |
| `lastvchid` | Number | Internal id (MASTERID) of the last voucher written; `0` for masters |
| `lastmid` | Number | Last master id written |
| `combined` | Number | Objects merged into existing ones |
| `ignored` | Number | Objects skipped (e.g. duplicates, `Empty` import condition true) |
| `errors` | Number | Objects rejected with an error |
| `cancelled` | Number | Vouchers cancelled |
| `exceptions` | Number | Objects imported as exceptions or rejected (e.g. missing referenced master, Dr ≠ Cr) |
| `vchnumber` | Number | Voucher imports only: voucher number of the written voucher |

> **Success rule:** `status == "1"` **and** the expected counter is ≥ 1 **and** `errors + exceptions == 0`. `status: "1"` alone only means "request processed". 🔵 This repo has seen `STATUS 1` returned together with `EXCEPTIONS 1` and a `LINEERROR`.

**Object/collection value typing.** Exported fields arrive as `{ "type": "String|Amount|Quantity|Rate|Logical|Number|Date", "value": … }`. Some identity fields (`guid`, `vouchertypename`, `vouchernumber`) come back as plain strings. Collection exports add `data.metadata`: `{ "is_mst_dep_type": true, "mst_dep_type": "8" }` for Ledger (🟢), `"512"` for Stock Item (🟢), and `{ "is_cmp_dep_type": true, "cmp_locus": 4, "cmp_dep_type": 64 }` for vouchers (🟢). These are internal dependency-type codes and can be ignored.

🟢 Official object-export response (multilingual ledger), verbatim:

```json
{
    "status": "1",
    "tallymessage": [
        {
            "metadata": { "type": "Ledger", "name": "ಶ್ರೀ", "reservedname": "", "id": "3694", "reqname": "ಶ್ರೀ" },
            "parent": { "type": "String", "value": "Sundry Debtors" },
            "isbillwiseon": { "type": "Logical", "value": true },
            "isdeemedpositive": { "type": "Logical", "value": true },
            "masterid": { "type": "Number", "value": " 3694" },
            "openingbalance": { "type": "Amount", "value": "0.00" },
            "languagename": [
                { "name": [ { "metadata": true, "type": "String" }, "ಶ್ರೀ" ], "languageid": { "type": "Number", "value": "0" } }
            ]
        }
    ]
}
```

(Excerpt: fields `taxtype`, `iscostcentreson`, `isrevenue`, `candelete` and `forpayroll` are omitted for brevity.)

🟢 Official report response, Balance Sheet in JSONEx (default, without empty fields), verbatim except some rows trimmed:

```json
{
    "status": "1",
    "data": {
        "bsbody": {
            "bsinfo": {
                "bssources": {
                    "bsdetail": [
                        { "bsname": { "dspaccname": { "dspdispname": "Capital Account" } }, "bsamt": [ { "bsmainamt": 2000000.00 } ] },
                        { "bsname": { "dspaccname": { "dspdispname": "Loans (Liability)" } }, "bsamt": [ { } ] },
                        { "bsname": { "dspaccname": { "dspdispname": "Current Liabilities" } }, "bsamt": [ { "bsmainamt": 391338.71 } ] }
                    ]
                },
                "bsapp": {
                    "bsdetail": [
                        { "bsname": { "dspaccname": { "dspdispname": "Fixed Assets" } }, "bsamt": [ { "bsmainamt": -100000.00 } ] },
                        { "bsname": { "dspaccname": { "dspdispname": "Current Assets" } }, "bsamt": [ { "bsmainamt": -3843350.00 } ] }
                    ]
                }
            }
        }
    }
}
```

### XML response envelope

- **Imports** (🔵 observed live): `<ENVELOPE><HEADER><VERSION>1</VERSION><STATUS>1</STATUS></HEADER><BODY><DATA><IMPORTRESULT>…counters…[<LINEERROR>…</LINEERROR>]</IMPORTRESULT></DATA><DESC><CMPINFO>…per-type counts…</CMPINFO></DESC></BODY></ENVELOPE>`. The counter tags are the uppercase names of the JSON fields (`<CREATED>`, `<ALTERED>`, `<LASTVCHID>`, …).
- **Object / collection exports** (🟡): `<ENVELOPE><HEADER><VERSION>1</VERSION><STATUS>1</STATUS></HEADER><BODY><DESC/><DATA><TALLYMESSAGE|COLLECTION>…objects…</…></DATA></BODY></ENVELOPE>`. Fields carry a `TYPE` attribute, e.g. `<PARENT TYPE="String">`.
- **Report exports** (🟡): a bare `<ENVELOPE>` containing the report's display tags in order (e.g. `DSPACCNAME`/`DSPACCINFO` pairs for Trial Balance).
- Tally separates XML lines with `\r\n` and may add blank lines. Parse with an XML parser, not regular expressions.

## 1.10 Common Error Responses

These apply to every API in this document.

| Situation | What you get | Source | Handling |
|---|---|---|---|
| TallyPrime not running / port closed | TCP connection refused or reset; **no HTTP response** | 🟢 (Explorer error text) | Retry with backoff and show "Tally offline" |
| Company not loaded / wrong `svCurrentCompany` | `<STATUS>0</STATUS>` + `<LINEERROR>Could not set 'SVCurrentCompany' to 'Bhrama Enterprises'</LINEERROR>` | 🔵 | Check the company collection first, then retry once a company is loaded |
| Malformed or mixed envelope | `<RESPONSE>Unknown Request, cannot be processed</RESPONSE>` | 🔵 | Fix the envelope ([§1.8](#18-xml-envelope-styles)) |
| Request too slow / Tally busy (modal dialog open on the Tally screen) | Socket timeout, empty body | 🔵 | Time out after ~30 s, alert an operator, don't blindly retry writes |
| Record-level rejection on import | `status 1` with `errors`/`exceptions` > 0 (+ `LINEERROR` in XML) | 🔵 | Log the raw body and surface the line error |
| Educational Mode date | Voucher rejected | 🟢 (Explorer note) | Use only the 1st, 2nd or 31st of a month in test data |

XML (🔵 observed):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>0</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <LINEERROR>Could not set &apos;SVCurrentCompany&apos; to &apos;Bhrama Enterprises&apos;</LINEERROR>
        </DATA>
    </BODY>
</ENVELOPE>
```

```xml
<RESPONSE>Unknown Request, cannot be processed</RESPONSE>
```

JSON (🟡: `status` `0` is documented in the template; the error-text key is not documented):

```json
{
    "status": "0"
}
```

Line errors seen on imports in this repo (🔵 observed):

| `LINEERROR` text | Cause |
|---|---|
| `Stock Group 'xyz' does not exist!` | Parent/referenced master missing |
| `Godown 'xyz' does not exist!` | Godown in batch allocation missing |
| `Voucher does not exist!` | Alter/Delete with ids that match nothing |
| `Cannot delete unnamed object: VOUCHER!` | Delete sent without `REMOTEID`/`VCHKEY` on the object |
| `Voucher date is missing` | Missing `DATE` |
| `Cannot be deleted!` | Master still referenced |
| `Cannot Decrease Number of Decimals for 'Unit'!` | Unit precision reduced |
| `BAD ORIGINAL NAME` | Unit `ORIGINALNAME` changed through Alter |
| `EXCEPTIONS 1` without a line error | Date outside books period, Dr ≠ Cr, or bank allocation ≠ bank line amount |

## 1.11 Data Types and Value Conventions

🟢 JSON ↔ Tally types:

| JSON type | Tally data types |
|---|---|
| String | Long, Amount, Rate, String, NamePtr, Time, FlagSet, RateX, Date, DateTime, NumSet, Quantity, DateRange, Duration |
| Boolean | Logical |
| Object | Tally Object |
| Array | Collection |
| Number | Number |

Conventions you must follow:

- **Dates:** `YYYYMMDD` (`20250831`). Inside TDL formulae use `$$Date:"1-Apr-2025"`.
- **Amount sign:** **Debit = negative, Credit = positive**, on vouchers and opening balances alike. `isdeemedpositive: true` (Debit) lines carry negative amounts. All lines of a voucher must sum to 0.
- **Quantities** are strings with a unit and often a leading space: `" 20 nos"`, `" 200 Kg = 2.00 Gms"` (compound).
- **Rates** carry the unit: `"75.00/nos"`.
- **Logical:** `Yes`/`No` in XML; `true`/`false` (or `"Yes"`/`"No"`) in JSON.
- **System names** are prefixed with ASCII 4: `&#4; Primary` (XML), `"\u0004 Not Applicable"` (JSON).
- **Numbers in exports** may have leading spaces (`" 1033"`). Trim before parsing.
- **Names** are case-insensitive and unique per master type. TDL definition names also ignore spaces.

## 1.12 Integration Best Practices

1. **Order of creation:** Units → Stock Groups → Stock Items; Groups → Ledgers; then Vouchers. Every reference must exist first.
2. **Always send `svCurrentCompany`**, and run the health and company checks before a batch.
3. **Persist voucher identity** (`guid`, `remoteid`, `vchkey`, `masterid`) after creating a voucher by exporting it back. Alter and Delete need these.
4. **Use the counters, not `status`**, to decide success; store the raw response for audit (MyTally's `SyncTrafficLog` does this).
5. **Incremental sync:** use period-filtered voucher collections (`$Date >= … AND $Date <= …`) or `AlterID`-based filters instead of full pulls.
6. **Fetch only the fields you need** (`fetch_list` / `Native Method`). Default collections return a lot.
7. **Keep TDL in code, not in shell strings.** `$` in formulae gets expanded by shells (🔵 incident in this repo: `$VOUCHERNUMBER` was stripped, which caused a "Bad formula" dialog in Tally).
8. **Treat Tally as single-threaded:** queue writes, cap batch size, and time out stuck calls. A modal dialog on the Tally screen blocks the API.

## 1.13 Provenance and Accuracy Notes

- All **request payloads** and **JSON header sets** come from the Explorer's `js/script.js` (`REQUEST_PAYLOADS`, `TAB_HEADERS`). Overview and field tables come from `pages/*.html`. Both were fetched on 2026-10-05.
- The Explorer's JSON and XML samples for the same API are **independent examples**: values sometimes differ (e.g. *Alter a Ledger*: `3000` in JSON vs `30000` in XML). Both are reproduced unchanged.
- **Existing repo doc warning:** `docs/TallyPrime_API_Reference.md` documents a JSON shape of the form `{"ENVELOPE": {"HEADER": …}}`. That is **not** TallyPrime's native JSON format, which is `static_variables`/`tallymessage` with routing in HTTP headers, as used by the Explorer and by `backend/app/routers/sync.py`. Prefer this document.

# 2. Accounting Masters

## 2.1 Ledger

### 2.1.0 Ledger — Overview & Field Reference

> 🟢 Official: converted from the Explorer's "About Ledger" page.

A Ledger in Tally is a core accounting unit used to record and track financial transactions for entities like customers, suppliers, expenses, or income sources. Every transaction involves at least two ledgers (debit and credit), ensuring proper accounting flow.

Ledgers are organized under Groups (Assets, Liabilities, Income, Expenses), enabling structured reporting like Balance Sheet and Profit & Loss.

In integrations, ledgers are used to create accounts and link them to vouchers (Sales, Purchase, Payment, Receipt). While a ledger supports 200+ fields, only relevant ones are required based on its type.

**For basic ledger creation, usually the following are sufficient:**

| Tag | Mandatory | Data Type | Explanation |
|---|---|---|---|
| NAME | Yes | String | The name of the ledger. This uniquely identifies the ledger within the company. |
| PARENT | Yes | String | Specifies the Group under which the ledger belongs (for example: Sundry Debtors, Sundry Creditors, Indirect Expenses). |

**For maintaining ledger of different currency following tag is necessary**

| Tag | Mandatory | Data Type | Explanation |
|---|---|---|---|
| CURRENCYNAME | No | String | Currency used by the ledger (For Indian companies the base currency is ₹ or INR). |

**The following tag is used to specify the opening balance for a ledger**

| Tag | Mandatory | Data Type | Explanation |
|---|---|---|---|
| OPENINGBALANCE | No | Amount | Opening balance of the ledger when it is created. To indicate whether a value is a debit or a credit ledger it is identified by a negative or a positive sign. |

**The following tags are applicable to party ledgers**

| Tag | Mandatory | Data Type | Explanation |
|---|---|---|---|
| ISBILLWISEON | No | Boolean (Yes/No) | Enables bill-wise tracking. Common for customer and supplier ledgers. |
| COUNTRYOFRESIDENCE | No | String | Country associated with the ledger. Used for compliance scenarios. |
| PRIORSTATENAME | No | String | State information used in tax or GST scenarios. |

**The following tags can be used to specify the ledger address**

| Tag / Collection | Mandatory | Data Type | Explanation |
|---|---|---|---|
| LEDMAILINGDETAILS |  | Collection | Contains mailing details of the ledger such as name, state, and country. |
| APPLICABLEFROM | Yes | Date (YYYYMMDD) | Effective date from which the mailing details are applicable. If you need to provide mailing details then applicable from is mandate. |
| MAILINGNAME | No | String | Name used for mailing and communication. |
| STATE | No | String | State associated with the mailing address. |
| COUNTRY | No | String | Country associated with the mailing address. |
| ADDRESS |  | Collection | Stores the address lines for the ledger. Multiple lines can be specified. |
| ADDRESS | No | String | Individual address line within the address list. |

**The following tags are mandatory to specify the opening balance details for a ledger when an opening balance is specified and IsBillWiseOn is set to Yes**

| Tag / Collection | Mandatory | Data Type | Explanation |
|---|---|---|---|
| BILLALLOCATIONS | Yes (Conditional) | Collection | Used to allocate the ledger opening balance against a bill reference when bill-wise tracking is enabled. |
| BILLDATE | Yes | Date (YYYYMMDD) | Date associated with the bill reference. |
| NAME | Yes | String | Reference name used for bill tracking (for example: OP1, INV001). |
| BILLCREDITPERIOD | Yes | Date / Period | Credit period associated with the bill reference. |
| ISADVANCE | Yes | Boolean (Yes/No) | Indicates whether the amount represents an advance payment. |
| OPENINGBALANCE | Yes | Amount | Amount allocated to the bill reference. This should match the ledger opening balance if only one reference exists. |

**The below tags are system generated and is just for your information**

| Tag | Mandatory | Data Type | Explanation |
|---|---|---|---|
| GUID | System Generated | String | Unique identifier generated by Tally for the ledger. |
| ALTERID | System Generated | Number | Internal version identifier used when a ledger is modified. |
| OBJECTUPDATEACTION | System Generated | String | Specifies the action performed (Create, Alter, Delete). |

**Sample — XML Format**

```xml
<ENVELOPE>
 <HEADER>
  <TALLYREQUEST>Import Data</TALLYREQUEST>
 </HEADER>
 <BODY>
  <IMPORTDATA>
   <REQUESTDATA>
    <TALLYMESSAGE>
     <LEDGER NAME="Balaji Transport">
      <CURRENCYNAME>₹</CURRENCYNAME>
      <PRIORSTATENAME>Maharashtra</PRIORSTATENAME>
      <VATDEALERTYPE>Regular</VATDEALERTYPE>
      <PARENT>Sundry Creditors</PARENT>
      <COUNTRYOFRESIDENCE>India</COUNTRYOFRESIDENCE>
      <LEDGERMOBILE>9902016211</LEDGERMOBILE>
      <LEDGERCOUNTRYISDCODE>+91</LEDGERCOUNTRYISDCODE>
      <ISBILLWISEON>Yes</ISBILLWISEON>
      <OPENINGBALANCE>70000.00</OPENINGBALANCE>

      <LANGUAGENAME>
       <NAME>
        <NAME>Balaji Transport</NAME>
       </NAME>
       <LANGUAGEID>1033</LANGUAGEID>
      </LANGUAGENAME>

      <BILLALLOCATIONS>
       <BILLDATE>20250331</BILLDATE>
       <NAME>OP1</NAME>
       <BILLCREDITPERIOD>31-Mar-25</BILLCREDITPERIOD>
       <ISADVANCE>No</ISADVANCE>
       <OPENINGBALANCE>45000.00</OPENINGBALANCE>
      </BILLALLOCATIONS>

      <BILLALLOCATIONS>
       <BILLDATE>20250331</BILLDATE>
       <NAME>OP2</NAME>
       <BILLCREDITPERIOD>31-Mar-25</BILLCREDITPERIOD>
       <ISADVANCE>No</ISADVANCE>
       <OPENINGBALANCE>25000.00</OPENINGBALANCE>
      </BILLALLOCATIONS>

      <LEDGSTREGDETAILS>
       <APPLICABLEFROM>20250401</APPLICABLEFROM>
       <GSTREGISTRATIONTYPE>Regular</GSTREGISTRATIONTYPE>
       <PLACEOFSUPPLY>Maharashtra</PLACEOFSUPPLY>
      </LEDGSTREGDETAILS>

      <LEDMAILINGDETAILS>
       <ADDRESS>
        <ADDRESS>#89 Raj Arcade</ADDRESS>
        <ADDRESS>S.V.Road</ADDRESS>
        <ADDRESS>VileParle (West)</ADDRESS>
       </ADDRESS>
       <APPLICABLEFROM>20250401</APPLICABLEFROM>
       <PINCODE>400056</PINCODE>
       <MAILINGNAME>Balaji Transport</MAILINGNAME>
       <STATE>Maharashtra</STATE>
       <COUNTRY>India</COUNTRY>
      </LEDMAILINGDETAILS>

      <CONTACTDETAILS>
       <NAME>Primary Mobile No.</NAME>
       <PHONENUMBER>9902016211</PHONENUMBER>
      </CONTACTDETAILS>

     </LEDGER>
    </TALLYMESSAGE>
   </REQUESTDATA>
  </IMPORTDATA>
 </BODY>
</ENVELOPE>
```

**Sample — JSON Format**

```json
{
  "tallymessage": [
    {
      "metadata": {
        "type": "Ledger",
        "name": "Balaji Transport"
      },
      "currencyname": "₹",
      "priorstatename": "Maharashtra",
      "parent": "Sundry Creditors",
      "countryofresidence": "India",
      "isbillwiseon": true,
      "openingbalance": "70000.00",

      "billallocations": [
        {
          "billdate": "20250331",
          "name": "OP1",
          "openingbalance": "45000.00"
        },
        {
          "billdate": "20250331",
          "name": "OP2",
          "openingbalance": "25000.00"
        }
      ],

      "ledmailingdetails": [
        {
          "address": [
            "#89 Raj Arcade",
            "S.V.Road",
            "VileParle (West)"
          ],
          "state": "Maharashtra",
          "country": "India"
        }
      ]
    }
  ]
}
```

### 2.1.1 Create a Ledger

> Explorer id: `create-ledger` · Kind: **import** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#create-ledger)

#### Description

The Create action is used to add a new ledger to the company data in Tally by providing details such as the ledger name and parent group. The behaviour of the ledger depends on the parent group to which it is assigned.

**Integration use:** Provision customer/supplier/bank accounts in Tally the moment they are created in your system, so vouchers posted later never fail on a missing ledger.

**Notes:**

- JSON uses lowercase method names (`name`, `parent`); XML uses `<NAME>`, `<PARENT>`. For Bank/Debtor/Creditor ledgers add the fields listed in the Ledger field reference above (`openingbalance`, `isbillwiseon`, `ledmailingdetails`, GST details).
- Creating an existing ledger again does not create a duplicate; check the counters to see what happened.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svMstImportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `import` | Yes |
| `type` | `data` | Yes |
| `id` | `All Masters` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svMstImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Ledger",
        "action": "create",
        "name": "Bank Of Baroda"
      },
      "name": "Bank Of Baroda",
      "parent": "Bank Accounts"
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>All Masters</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
            <TALLYMESSAGE>
                <LEDGER NAME="Bank of Baroda" Action="Create">
                    <NAME>Bank of Baroda</NAME>
                    <PARENT> Bank Accounts </PARENT>
                </LEDGER>
            </TALLYMESSAGE>
        </DESC>
    </BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: import" \
  -H "type: data" \
  -H "id: All Masters" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟢 Official shape: Tally's published master import response):

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 1,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 0
        }
    }
}
```

**Success — XML** (🔵 Observed: captured from a live TallyPrime in `docs/Tally_Vouchers_Integration_Guide.md`; `CMPINFO` truncated):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <CREATED>1</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>0</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
        <DESC>
            <CMPINFO>
                <COMPANY>0</COMPANY>
                <GROUP>0</GROUP>
                <LEDGER>95</LEDGER>
                <!-- … one count element per object type (COSTCENTRE, GODOWN, STOCKITEM, UNIT, VOUCHERTYPE, …) … -->
                <VOUCHER>39</VOUCHER>
            </CMPINFO>
        </DESC>
    </BODY>
</ENVELOPE>
```

Check `created` = 1 **and** `errors` + `exceptions` = 0. `status: "1"` only means the request was processed, not that the record was accepted.

#### Error Responses

**Record-level failure:** `Group 'Bank Acounts' does not exist!`. Source: 🟡 Illustrative (same message pattern as the observed stock-group error).

Cause: Example: `parent` sent as "Bank Acounts", which does not exist in the company. Create or verify the parent first.

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <LINEERROR>Group &apos;Bank Acounts&apos; does not exist!</LINEERROR>
                <CREATED>0</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>1</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
    </BODY>
</ENVELOPE>
```

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 1
        }
    }
}
```

> In JSON the failure shows up as non-zero `errors` / `exceptions` counts. Tally does not document the JSON key that carries the line-error text, so log the raw response body; this repo's parser (`parse_tally_response_metrics`) also checks `import_result.line_error`.

See also [Common errors](#110-common-error-responses) (company not loaded, unknown request, Tally not running).

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `import` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `data` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `All Masters` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svMstImportFormat]` | `<STATICVARIABLES><SVMSTIMPORTFORMAT>` | Yes (master import) | String | `jsonex` | Import format of masters: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `tallymessage[]` | `<TALLYMESSAGE>` | Yes | Array<Object> |  | The objects to import (masters or vouchers). One request can carry many objects. |
| `tallymessage[].metadata` | `<LEDGER …>` attributes | Yes | Object |  | Object identity block: type, name/identifiers and action. |
| `tallymessage[].metadata.type` | element name `<LEDGER>` | Yes | String | `Ledger` | Object type: `Ledger`, `Group`, `Stock Item`, `Stock Group`, `Unit`, `Voucher`. |
| `tallymessage[].metadata.action` | `ACTION` attribute | Yes | String | `create` | `Create`, `Alter`, or `Delete` (case-insensitive). |
| `tallymessage[].metadata.name` | `NAME` attribute | Yes (masters) | String | `Bank Of Baroda` | Name of the master; the key Tally matches on for Alter/Delete. |
| `tallymessage[].name` | `<LEDGER>/NAME` | Yes | String | `Bank Of Baroda` | Object name; unique within the company for masters. |
| `tallymessage[].parent` | `<LEDGER>/PARENT` | Rec. | String | `Bank Accounts` | Parent group / stock group. Defaults to `Primary` when omitted (use `&#4; Primary` / `\u0004 Primary` to state it explicitly). |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Create a new ledger Yes Bank under Bank Accounts. | Change tag values: NAME | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/ledger/create/json/Create%20YesBank%20JSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/ledger/create/xml/Create%20YesBank%20XML.txt) |
| Create a new ledger by Name "SADE Pvt Ltd" under Sundry Debtors with OpeningBalance as 20,000 credit. | Change tag values : NAME, PARENT, OPENINGBALANCE | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/ledger/create/json/Create%20SADEPvtLtd%20JSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/ledger/create/xml/Create%20SADEPvtLtd%20XML.txt) |

### 2.1.2 Alter a Ledger

> Explorer id: `alter-ledger` · Kind: **import** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#alter-ledger)

#### Description

The Alter action is used to modify the details of an existing ledger in Tally. You can update ledger information by sending a request with the ledger name and the storages that need to be changed. Once processed successfully, the ledger is updated with the specified changes.

**Integration use:** Push master-data edits (opening balance, address, GST details) from your system so Tally stays the mirror of record without manual re-keying.

**Notes:**

- Only the fields you send change; omitted fields keep their values.
- The JSON sample uses the spaced method name `"Opening Balance"`; `openingbalance` is equivalent. Sample values differ between JSON (`3000`) and XML (`30000`).

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svMstImportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `import` | Yes |
| `type` | `data` | Yes |
| `id` | `All Masters` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svMstImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Ledger",
        "action": "Alter",
        "name": "Bank Of Baroda"
      },
      "Opening Balance": "3000"
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>All Masters</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
            <TALLYMESSAGE>
                <LEDGER NAME="Bank of Baroda" Action="Alter">
                    <NAME>Bank of Baroda</NAME>
                    <OPENINGBALANCE>30000</OPENINGBALANCE>
                </LEDGER>
            </TALLYMESSAGE>
        </DESC>
    </BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: import" \
  -H "type: data" \
  -H "id: All Masters" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟢 Official shape: Tally's published master import response):

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 1,
            "deleted": 0,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 0
        }
    }
}
```

**Success — XML** (🔵 Observed: captured from a live TallyPrime in `docs/Tally_Vouchers_Integration_Guide.md`; `CMPINFO` truncated):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <CREATED>0</CREATED>
                <ALTERED>1</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>0</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
        <DESC>
            <CMPINFO>
                <COMPANY>0</COMPANY>
                <GROUP>0</GROUP>
                <LEDGER>95</LEDGER>
                <!-- … one count element per object type (COSTCENTRE, GODOWN, STOCKITEM, UNIT, VOUCHERTYPE, …) … -->
                <VOUCHER>39</VOUCHER>
            </CMPINFO>
        </DESC>
    </BODY>
</ENVELOPE>
```

Check `altered` = 1 **and** `errors` + `exceptions` = 0. `status: "1"` only means the request was processed, not that the record was accepted.

#### Error Responses

**Record-level failure:** `Ledger 'Bank Of Baroda' does not exist!`. Source: 🟡 Illustrative.

Cause: Alter matches on `metadata.name` (`NAME` attribute). The name must match an existing master exactly (case-insensitive).

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <LINEERROR>Ledger &apos;Bank Of Baroda&apos; does not exist!</LINEERROR>
                <CREATED>0</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>1</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
    </BODY>
</ENVELOPE>
```

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 1
        }
    }
}
```

> In JSON the failure shows up as non-zero `errors` / `exceptions` counts. Tally does not document the JSON key that carries the line-error text, so log the raw response body; this repo's parser (`parse_tally_response_metrics`) also checks `import_result.line_error`.

See also [Common errors](#110-common-error-responses) (company not loaded, unknown request, Tally not running).

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `import` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `data` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `All Masters` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svMstImportFormat]` | `<STATICVARIABLES><SVMSTIMPORTFORMAT>` | Yes (master import) | String | `jsonex` | Import format of masters: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `tallymessage[]` | `<TALLYMESSAGE>` | Yes | Array<Object> |  | The objects to import (masters or vouchers). One request can carry many objects. |
| `tallymessage[].metadata` | `<LEDGER …>` attributes | Yes | Object |  | Object identity block: type, name/identifiers and action. |
| `tallymessage[].metadata.type` | element name `<LEDGER>` | Yes | String | `Ledger` | Object type: `Ledger`, `Group`, `Stock Item`, `Stock Group`, `Unit`, `Voucher`. |
| `tallymessage[].metadata.action` | `ACTION` attribute | Yes | String | `Alter` | `Create`, `Alter`, or `Delete` (case-insensitive). |
| `tallymessage[].metadata.name` | `NAME` attribute | Yes (masters) | String | `Bank Of Baroda` | Name of the master; the key Tally matches on for Alter/Delete. |
| `tallymessage[].Opening Balance` | `<LEDGER>/OPENINGBALANCE` | No | Amount / Quantity | `3000` | Opening balance. Ledgers: Amount, negative = Debit, positive = Credit. Stock: quantity with unit (e.g. `200 nos`). |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Alter ledger Yes Bank with Opening Balance as 10,75,000. | Add a new tag : Opening Balance | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/ledger/alter/json/Alter%20YesBankJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/ledger/alter/xml/Alter%20YesBank%20XML.txt) |
| Alter ledger "SADE Pvt Ltd" with Address | Add new collection ‘LedMailingDetails’ provide tag Applicable from Address and tag Address under it | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/ledger/alter/json/Alter%20SADEPvtLtd%20JSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/ledger/alter/xml/Alter%20SADEPvtLtd%20XML.txt) |

### 2.1.3 Delete a Ledger

> Explorer id: `delete-ledger` · Kind: **import** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#delete-ledger)

#### Description

The Delete action is used to Delete a ledger from the company data. Any ledger, unless not used or referred in transactions or other masters, can be deleted.

**Integration use:** Retire accounts removed upstream. Tally refuses deletion of ledgers used in vouchers, so treat a failure as a signal to archive rather than delete.

**Notes:**

- Only identity is needed (`metadata.name` + `action: Delete`). Ledgers used in any voucher cannot be deleted.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svMstImportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `import` | Yes |
| `type` | `data` | Yes |
| `id` | `All Masters` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svMstImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Ledger",
        "action": "Delete",
        "name": "Bank Of Baroda"
      }
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>All Masters</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
            <TALLYMESSAGE>
                <LEDGER NAME="Bank of Baroda" Action="Delete">
                    <NAME>Bank of Baroda</NAME>
                </LEDGER>
            </TALLYMESSAGE>
        </DESC>
    </BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: import" \
  -H "type: data" \
  -H "id: All Masters" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟢 Official shape: Tally's published master import response):

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 0,
            "deleted": 1,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 0
        }
    }
}
```

**Success — XML** (🔵 Observed: captured from a live TallyPrime in `docs/Tally_Vouchers_Integration_Guide.md`; `CMPINFO` truncated):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <CREATED>0</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>1</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>0</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
        <DESC>
            <CMPINFO>
                <COMPANY>0</COMPANY>
                <GROUP>0</GROUP>
                <LEDGER>95</LEDGER>
                <!-- … one count element per object type (COSTCENTRE, GODOWN, STOCKITEM, UNIT, VOUCHERTYPE, …) … -->
                <VOUCHER>39</VOUCHER>
            </CMPINFO>
        </DESC>
    </BODY>
</ENVELOPE>
```

Check `deleted` = 1 **and** `errors` + `exceptions` = 0. `status: "1"` only means the request was processed, not that the record was accepted.

#### Error Responses

**Record-level failure:** `Cannot be deleted!`. Source: 🟡 Illustrative (message observed for Units in this repo).

Cause: The ledger is still referenced (by vouchers, child masters, stock items or compound units). Remove the references first, or archive instead of deleting.

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <LINEERROR>Cannot be deleted!</LINEERROR>
                <CREATED>0</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>1</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
    </BODY>
</ENVELOPE>
```

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 1
        }
    }
}
```

> In JSON the failure shows up as non-zero `errors` / `exceptions` counts. Tally does not document the JSON key that carries the line-error text, so log the raw response body; this repo's parser (`parse_tally_response_metrics`) also checks `import_result.line_error`.

See also [Common errors](#110-common-error-responses) (company not loaded, unknown request, Tally not running).

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `import` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `data` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `All Masters` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svMstImportFormat]` | `<STATICVARIABLES><SVMSTIMPORTFORMAT>` | Yes (master import) | String | `jsonex` | Import format of masters: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `tallymessage[]` | `<TALLYMESSAGE>` | Yes | Array<Object> |  | The objects to import (masters or vouchers). One request can carry many objects. |
| `tallymessage[].metadata` | `<LEDGER …>` attributes | Yes | Object |  | Object identity block: type, name/identifiers and action. |
| `tallymessage[].metadata.type` | element name `<LEDGER>` | Yes | String | `Ledger` | Object type: `Ledger`, `Group`, `Stock Item`, `Stock Group`, `Unit`, `Voucher`. |
| `tallymessage[].metadata.action` | `ACTION` attribute | Yes | String | `Delete` | `Create`, `Alter`, or `Delete` (case-insensitive). |
| `tallymessage[].metadata.name` | `NAME` attribute | Yes (masters) | String | `Bank Of Baroda` | Name of the master; the key Tally matches on for Alter/Delete. |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Delete the ledger ‘SADE Pvt Ltd’ | Change tag values: NAME | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/ledger/delete/json/TaskDeleteSADEPvtLtdJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/ledger/delete/xml/TaskDeleteSADEPvtLtdXML.txt) |

### 2.1.4 Pull a Ledger

> Explorer id: `pull-a-ledger` · Kind: **object** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#pull-a-ledger)

#### Description

Details about a single ledger can be pulled using the Name of the ledger which is the identifier. All the first level methods from ledger object can be fetched.

**Integration use:** Targeted read-back for one account, e.g. verifying a create/alter landed, or showing a live closing balance in your UI.

**Notes:**

- `fetch_list` limits the response to the listed methods. Any first-level ledger method can be requested (e.g. `Parent`, `OpeningBalance`, `ClosingBalance`, `LedgerPhone`, `PartyGSTIN`).

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svExportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVEXPORTFORMAT>XML</SVEXPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `export` | Yes |
| `type` | `object` | Yes |
| `subtype` | `Ledger` | Cond. |
| `id` | `Kotak Bank` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<SUBTYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonEx"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "fetch_list": [
    "Name",
    "Parent",
    "Opening Balance",
    "Closing Balance"
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Object</TYPE>
        <SUBTYPE>Ledger</SUBTYPE>
        <ID TYPE="Name">Kotak Bank</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
            <FETCHLIST>
                <FETCH>Name</FETCH>
                <FETCH>Parent</FETCH>
                <FETCH>Opening Balance</FETCH>
                <FETCH>Closing Balance</FETCH>
            </FETCHLIST>
        </DESC>
    </BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: export" \
  -H "type: object" \
  -H "subtype: Ledger" \
  -H "id: Kotak Bank" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟡 Illustrative: structure per Tally's published object-export sample `{type, value}` per method; values invented):

```json
{
    "status": "1",
    "tallymessage": [
        {
            "metadata": {
                "type": "Ledger",
                "name": "Kotak Bank",
                "reservedname": "",
                "id": "1042",
                "reqname": "Kotak Bank"
            },
            "parent": {
                "type": "String",
                "value": "Bank Accounts"
            },
            "openingbalance": {
                "type": "Amount",
                "value": "-250000.00"
            },
            "closingbalance": {
                "type": "Amount",
                "value": "-312450.00"
            },
            "languagename": [
                {
                    "name": [
                        {
                            "metadata": true,
                            "type": "String"
                        },
                        "Kotak Bank"
                    ],
                    "languageid": {
                        "type": "Number",
                        "value": " 1033"
                    }
                }
            ]
        }
    ]
}
```

**Success — XML** (🟡 Illustrative: TYPE-attributed fields mirroring the JSON):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DESC>
        </DESC>
        <DATA>
            <TALLYMESSAGE>
                <LEDGER NAME="Kotak Bank" RESERVEDNAME="">
                    <PARENT TYPE="String">Bank Accounts</PARENT>
                    <OPENINGBALANCE TYPE="Amount">-250000.00</OPENINGBALANCE>
                    <CLOSINGBALANCE TYPE="Amount">-312450.00</CLOSINGBALANCE>
                    <LANGUAGENAME.LIST>
                        <NAME.LIST TYPE="String">
                            <NAME>Kotak Bank</NAME>
                        </NAME.LIST>
                        <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
                    </LANGUAGENAME.LIST>
                </LEDGER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>
```

#### Error Responses

- **Object not found / wrong `subtype`** (🟡 Illustrative): Tally returns no object (an empty `tallymessage` / `<TALLYMESSAGE/>`) or `status` `0`. Treat a missing object, not just the status flag, as "not found".
- **Multilingual names:** send the name base64-encoded in `id-encoded` (with `content-type: application/json;charset=utf-8`) instead of `id`.
- [Common errors](#110-common-error-responses) apply (company not loaded, Tally not running).

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `export` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `object` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: subtype` | `<HEADER><SUBTYPE>` | Cond. | String | `Ledger` | Object type for `type: Object` (e.g. `Ledger`, `StockItem`). |
| `header: id` | `<HEADER><ID>` | Yes | String | `Kotak Bank` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svExportFormat]` | `<STATICVARIABLES><SVEXPORTFORMAT>` | Yes (export) | String | `jsonEx` | Response format: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `fetch_list[]` | `<FETCHLIST><FETCH>` | No | Array<String> | `Name, Parent, Opening Balance, Closing B…` | Methods/storages to return for an Object export (`type: object`). Omit to get the default set. |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Pull only opening balance and closing balance of the details of the ledger ‘Cash’ | Change the HTTP Header value of 'id'. Fetch relevant methods. | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/ledger/pull/json/TaskPullLedgerCashJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/ledger/pull/xml/TaskPullLedgerCashXML.txt) |

### 2.1.5 Pull All Ledgers

> Explorer id: `pull-all-ledger` · Kind: **collection** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#pull-all-ledger)

#### Description

Details about multiple ledgers can be pulled using a TDL collection definition, which can already exist in the default source code or sent via the payload. TDL collection definition has type attribute that specifies the type of object that is grouped and fetch attribute that fetches the required methods.

**Integration use:** Full chart-of-accounts sync / reconciliation. Use it on first connect and periodically to detect ledgers created directly in Tally.

**Notes:**

- Uses the built-in `Ledger` collection, so no TDL is needed. The response includes Tally's default method set (see the 🟢 sample).

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svExportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVEXPORTFORMAT>XML</SVEXPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `export` | Yes |
| `type` | `collection` | Yes |
| `id` | `Ledger` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Collection</TYPE>
        <ID>Ledger</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
    </BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: export" \
  -H "type: collection" \
  -H "id: Ledger" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟢 Official (JSON excerpt of Tally's published sample, first 2 of N objects)):

```json
{
    "status": "1",
    "data": {
        "metadata": {
            "is_mst_dep_type": true,
            "mst_dep_type": "8"
        },
        "collection": [
            {
                "metadata": {
                    "type": "Ledger",
                    "name": "Abc Party",
                    "reservedname": ""
                },
                "parent": {
                    "type": "String",
                    "value": "Sundry Debtors"
                },
                "ledgerphone": {
                    "type": "String",
                    "value": "764387326845"
                },
                "ledgercontact": {
                    "type": "String",
                    "value": "Mr. A"
                },
                "closingbalance": {
                    "type": "Amount",
                    "value": "-243900.00"
                },
                "onaccountvalue": {
                    "type": "Amount",
                    "value": ""
                },
                "tbalopening": {
                    "type": "Amount",
                    "value": "0.00"
                },
                "closingonacctvalue": {
                    "type": "Amount",
                    "value": ""
                },
                "closingdronacctvalue": {
                    "type": "Logical",
                    "value": false
                },
                "ledopeningbalance": {
                    "type": "Amount",
                    "value": "0.00"
                },
                "languagename": [
                    {
                        "name": [
                            {
                                "metadata": true,
                                "type": "String"
                            },
                            "Abc Party",
                            "(ABC Party Pvt Ltd)"
                        ],
                        "languageid": {
                            "type": "Number",
                            "value": " 1033"
                        }
                    }
                ]
            },
            {
                "metadata": {
                    "type": "Ledger",
                    "name": "Advertising Expenses",
                    "reservedname": ""
                },
                "parent": {
                    "type": "String",
                    "value": "Indirect Expenses"
                },
                "closingbalance": {
                    "type": "Amount",
                    "value": "0.00"
                },
                "onaccountvalue": {
                    "type": "Amount",
                    "value": ""
                },
                "tbalopening": {
                    "type": "Amount",
                    "value": "0.00"
                },
                "closingonacctvalue": {
                    "type": "Amount",
                    "value": ""
                },
                "closingdronacctvalue": {
                    "type": "Logical",
                    "value": false
                },
                "ledopeningbalance": {
                    "type": "Amount",
                    "value": "0.00"
                },
                "languagename": [
                    {
                        "name": [
                            {
                                "metadata": true,
                                "type": "String"
                            },
                            "Advertising Expenses"
                        ],
                        "languageid": {
                            "type": "Number",
                            "value": " 1033"
                        }
                    }
                ]
            }
        ]
    }
}
```

**Success — XML** (🟡 Illustrative):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DESC>
        </DESC>
        <DATA>
            <COLLECTION>
                <LEDGER NAME="Abc Party" RESERVEDNAME="">
                    <PARENT TYPE="String">Sundry Debtors</PARENT>
                    <LEDGERPHONE TYPE="String">764387326845</LEDGERPHONE>
                    <LEDGERCONTACT TYPE="String">Mr. A</LEDGERCONTACT>
                    <CLOSINGBALANCE TYPE="Amount">-243900.00</CLOSINGBALANCE>
                    <ONACCOUNTVALUE TYPE="Amount"></ONACCOUNTVALUE>
                    <TBALOPENING TYPE="Amount">0.00</TBALOPENING>
                    <CLOSINGONACCTVALUE TYPE="Amount"></CLOSINGONACCTVALUE>
                    <CLOSINGDRONACCTVALUE TYPE="Logical">No</CLOSINGDRONACCTVALUE>
                    <LEDOPENINGBALANCE TYPE="Amount">0.00</LEDOPENINGBALANCE>
                    <LANGUAGENAME.LIST>
                        <NAME.LIST TYPE="String">
                            <NAME>Abc Party</NAME>
                        </NAME.LIST>
                        <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
                    </LANGUAGENAME.LIST>
                </LEDGER>
                <LEDGER NAME="Advertising Expenses" RESERVEDNAME="">
                    <PARENT TYPE="String">Indirect Expenses</PARENT>
                    <CLOSINGBALANCE TYPE="Amount">0.00</CLOSINGBALANCE>
                    <ONACCOUNTVALUE TYPE="Amount"></ONACCOUNTVALUE>
                    <TBALOPENING TYPE="Amount">0.00</TBALOPENING>
                    <CLOSINGONACCTVALUE TYPE="Amount"></CLOSINGONACCTVALUE>
                    <CLOSINGDRONACCTVALUE TYPE="Logical">No</CLOSINGDRONACCTVALUE>
                    <LEDOPENINGBALANCE TYPE="Amount">0.00</LEDOPENINGBALANCE>
                    <LANGUAGENAME.LIST>
                        <NAME.LIST TYPE="String">
                            <NAME>Advertising Expenses</NAME>
                        </NAME.LIST>
                        <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
                    </LANGUAGENAME.LIST>
                </LEDGER>
            </COLLECTION>
        </DATA>
    </BODY>
</ENVELOPE>
```

#### Error Responses

- **Collection name mismatch** (🟡 Illustrative): if the `id` header / `<ID>` does not match a default collection or a definition in `tdlmessage`, Tally returns an error instead of data. TDL names ignore case and spaces (`TSPL All Payment Vouchers` = `TSPLAllPaymentVouchers`), but any other spelling difference breaks the match.
- **Invalid TDL** (bad attribute or formula): Tally may show an error dialog on the Tally screen and return nothing useful. Validate TDL in the Explorer before shipping it.
- **Empty result:** a valid request that matches nothing returns `status: "1"` with an empty `collection` (`<COLLECTION/>`).
- [Common errors](#110-common-error-responses) apply.

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `export` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `collection` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `Ledger` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svExportFormat]` | `<STATICVARIABLES><SVEXPORTFORMAT>` | Yes (export) | String | `jsonex` | Response format: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |

### 2.1.6 Pull Ledgers of Group

> Explorer id: `pull-ledgers-of-group` · Kind: **collection** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#pull-ledgers-of-group)

#### Description

Details about multiple ledgers belonging to a group can be pulled using a TDL collection definition. When the TDL collection in default source code is not serving the requirement, a new TDL collection to fetch required information can be used. The TDL collection definition has type attribute that specifies the type of object that is grouped, child of attribute specifies the name of the parent and fetch attribute that fetches the required methods.

**Integration use:** Scoped sync of one account class (banks, debtors, creditors) with an inline TDL collection, which keeps the payload small and fast.

**Notes:**

- `$$GroupBank` is a built-in function that returns the name of the reserved *Bank Accounts* group. Use a quoted literal (`"Sundry Debtors"`) for any other group.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svExportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVEXPORTFORMAT>XML</SVEXPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `export` | Yes |
| `type` | `collection` | Yes |
| `id` | `TSPLBankLedgers` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tdlmessage": [
    {
      "definitions": [
        {
          "metadata": {
            "name": "TSPLBankLedgers",
            "type": "Collection"
          },
          "attributes": [
            {
              "Type": "Ledger"
            },
            {
              "Child Of": "$$GroupBank"
            },
            {
              "Native Method": "Name, Parent, OpeningBalance, ClosingBalance, IseBankingEnabled, Mailing Name, Bank Details"
            }
          ]
        }
      ]
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Collection</TYPE>
        <ID>TSPLBankLedgers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
            <TDL>
                <TDLMESSAGE>
                    <COLLECTION NAME="TSPLBankLedgers" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
                        <TYPE>Ledger</TYPE>
                        <CHILDOF>$$GroupBank</CHILDOF>
                        <NATIVEMETHOD>Name, Parent, OpeningBalance, ClosingBalance, IseBankingEnabled, Mailing Name, Bank Details</NATIVEMETHOD>
                    </COLLECTION>
                </TDLMESSAGE>
            </TDL>
        </DESC>
    </BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: export" \
  -H "type: collection" \
  -H "id: TSPLBankLedgers" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟡 Illustrative (shape per Tally's published collection sample; values invented)):

```json
{
    "status": "1",
    "data": {
        "metadata": {
            "is_mst_dep_type": true,
            "mst_dep_type": "8"
        },
        "collection": [
            {
                "metadata": {
                    "type": "Ledger",
                    "name": "Kotak Bank",
                    "reservedname": ""
                },
                "parent": {
                    "type": "String",
                    "value": "Bank Accounts"
                },
                "openingbalance": {
                    "type": "Amount",
                    "value": "-250000.00"
                },
                "closingbalance": {
                    "type": "Amount",
                    "value": "-312450.00"
                },
                "isebankingenabled": {
                    "type": "Logical",
                    "value": true
                },
                "mailingname": {
                    "type": "String",
                    "value": "Kotak Bank"
                },
                "bankdetails": {
                    "type": "String",
                    "value": "4891289138912"
                },
                "languagename": [
                    {
                        "name": [
                            {
                                "metadata": true,
                                "type": "String"
                            },
                            "Kotak Bank"
                        ],
                        "languageid": {
                            "type": "Number",
                            "value": " 1033"
                        }
                    }
                ]
            },
            {
                "metadata": {
                    "type": "Ledger",
                    "name": "Bank of Baroda",
                    "reservedname": ""
                },
                "parent": {
                    "type": "String",
                    "value": "Bank Accounts"
                },
                "openingbalance": {
                    "type": "Amount",
                    "value": "-200000.00"
                },
                "closingbalance": {
                    "type": "Amount",
                    "value": "-206300.00"
                },
                "isebankingenabled": {
                    "type": "Logical",
                    "value": false
                },
                "mailingname": {
                    "type": "String",
                    "value": "Bank of Baroda"
                },
                "bankdetails": {
                    "type": "String",
                    "value": ""
                },
                "languagename": [
                    {
                        "name": [
                            {
                                "metadata": true,
                                "type": "String"
                            },
                            "Bank of Baroda"
                        ],
                        "languageid": {
                            "type": "Number",
                            "value": " 1033"
                        }
                    }
                ]
            }
        ]
    }
}
```

**Success — XML** (🟡 Illustrative):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DESC>
        </DESC>
        <DATA>
            <COLLECTION>
                <LEDGER NAME="Kotak Bank" RESERVEDNAME="">
                    <PARENT TYPE="String">Bank Accounts</PARENT>
                    <OPENINGBALANCE TYPE="Amount">-250000.00</OPENINGBALANCE>
                    <CLOSINGBALANCE TYPE="Amount">-312450.00</CLOSINGBALANCE>
                    <ISEBANKINGENABLED TYPE="Logical">Yes</ISEBANKINGENABLED>
                    <MAILINGNAME TYPE="String">Kotak Bank</MAILINGNAME>
                    <BANKDETAILS TYPE="String">4891289138912</BANKDETAILS>
                    <LANGUAGENAME.LIST>
                        <NAME.LIST TYPE="String">
                            <NAME>Kotak Bank</NAME>
                        </NAME.LIST>
                        <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
                    </LANGUAGENAME.LIST>
                </LEDGER>
                <LEDGER NAME="Bank of Baroda" RESERVEDNAME="">
                    <PARENT TYPE="String">Bank Accounts</PARENT>
                    <OPENINGBALANCE TYPE="Amount">-200000.00</OPENINGBALANCE>
                    <CLOSINGBALANCE TYPE="Amount">-206300.00</CLOSINGBALANCE>
                    <ISEBANKINGENABLED TYPE="Logical">No</ISEBANKINGENABLED>
                    <MAILINGNAME TYPE="String">Bank of Baroda</MAILINGNAME>
                    <BANKDETAILS TYPE="String"></BANKDETAILS>
                    <LANGUAGENAME.LIST>
                        <NAME.LIST TYPE="String">
                            <NAME>Bank of Baroda</NAME>
                        </NAME.LIST>
                        <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
                    </LANGUAGENAME.LIST>
                </LEDGER>
            </COLLECTION>
        </DATA>
    </BODY>
</ENVELOPE>
```

#### Error Responses

- **Collection name mismatch** (🟡 Illustrative): if the `id` header / `<ID>` does not match a default collection or a definition in `tdlmessage`, Tally returns an error instead of data. TDL names ignore case and spaces (`TSPL All Payment Vouchers` = `TSPLAllPaymentVouchers`), but any other spelling difference breaks the match.
- **Invalid TDL** (bad attribute or formula): Tally may show an error dialog on the Tally screen and return nothing useful. Validate TDL in the Explorer before shipping it.
- **Empty result:** a valid request that matches nothing returns `status: "1"` with an empty `collection` (`<COLLECTION/>`).
- [Common errors](#110-common-error-responses) apply.

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `export` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `collection` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `TSPLBankLedgers` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svExportFormat]` | `<STATICVARIABLES><SVEXPORTFORMAT>` | Yes (export) | String | `jsonex` | Response format: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `tdlmessage[]` | `<TDL><TDLMESSAGE>` | Cond. | Array<Object> |  | Inline TDL definitions (Collection / Report modification / System Formulae) that Tally loads before executing the request. |
| `tdlmessage[].definitions[]` | `<COLLECTION …>` | Cond. | Array<Object> |  | List of TDL definitions inside `tdlmessage`. |
| `tdlmessage[].definitions[].metadata.name` | `NAME` attribute | Yes | String | `TSPLBankLedgers` | Definition name. For a Collection it must match the `id` header / `<ID>`. TDL names are case- and space-insensitive. |
| `tdlmessage[].definitions[].metadata.type` | element name | Yes | String | `Collection` | Definition kind: `Collection`, `Report`, or `System`. |
| `tdlmessage[].definitions[].attributes[].Type` | `<TYPE>` | Yes | String | `Ledger` | Object type the collection gathers: `Ledger`, `Group`, `StockItem`, `StockGroup`, `Unit`, or `Vouchers:VoucherType` (vouchers of a voucher type). |
| `tdlmessage[].definitions[].attributes[].Child Of` | `<CHILDOF>` | No | String (TDL expr) | `$$GroupBank` | Restricts the collection to children of a parent. Accepts a literal (`"Gadgets"`) or a system-name function such as `$$GroupBank`, `$$GroupCurrentAssets`, `$$VchTypePayment`. |
| `tdlmessage[].definitions[].attributes[].Native Method` | `<NATIVEMETHOD>` | Yes | String (CSV) | `Name, Parent, OpeningBalance, ClosingBal…` | Comma-separated methods to fetch for every object in the collection. |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Fetch only name, parent, openingbalance, closing balance from bank ledgers | Fetch only relevant methods in the collection | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/ledger/pull-ledgers-of-group/json/TaskPullLedgersofBankFetchJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/ledger/pull-ledgers-of-group/xml/TaskPullLedgersofBankFetchXML.txt) |
| Fetch name, parent, openingbalance, closing balance from ledgers of group current assets | Change Child of attribute. | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/ledger/pull-ledgers-of-group/json/TaskPulLedgersOfCurrentAssetsJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/ledger/pull-ledgers-of-group/xml/TaskPulLedgersOfCurrentAssetsXML.txt) |

## 2.2 Group

### 2.2.0 Group — Overview & Field Reference

> 🟢 Official: converted from the Explorer's "About Group" page.

In TallyPrime, a Group is a classification used to organize ledgers so that financial reports like the Balance Sheet and Profit & Loss are generated correctly. In any business, it is important to categorise similar ledgers based on their nature, type, or usage under an accounting head. These accounting heads are known as Groups.

Primarily, Groups can be classified between Assets, Liabilities, Expenses, and Incomes. In TallyPrime, there are 28 predefined groups, of which 15 are Primary and 13 are Subgroups. Along with the predefined groups, one can create new Groups to accommodate the business needs.

Every ledger in TallyPrime belongs to a group and takes on the nature from the primary parent group it is associated with.

In integration scenarios, Groups are used to

Create logical sub-groups so that accounting data is organized

Example

```text
Indirect Expenses
  └── Delivery Expenses
        └──Courier Charges

```

To Separate Third-Party Data from Manual Data

Example

```text
Sundry Debtors
└──Interstate Customers
└── Local Customers

```

Understanding the structure and required fields of a group is essential as group plays an important role in getting organised financial reports.

A Group has over 100+ tags; however, all tags are not mandatory. The required tags depend on the nature of the group.

**For basic Group creation, usually the following is sufficient:**

Applicable for XML Format only

| Tag/Attribute | Identifier | Mandatory | Data Type | Explanation |
|---|---|---|---|---|
| Group | Tag | Yes | String | Specifies the Type of the Object. In this case its ‘Group’ |
| Name | Attribute of Group Tag | Yes | String | The name of the Group. This uniquely identifies the Group within the company |

Applicable for JSON format only

| Tag | Mandatory | Data Type | Explanation |
|---|---|---|---|
| metadata | Yes | Object | This contains the metadata information that specifies the type of object and name of the group |
| type | Yes | String | Specifies the Type of the Object. In this case its ‘Group’ |
| name | Yes | String | The name of the Group. This uniquely identifies the Group within the company |

Applicable for both XML and JSON formats

| Tag | Mandatory | Data Type | Explanation |
|---|---|---|---|
| name | Yes | String | The name of the Group. This uniquely identifies the Group within the company. |
| parent | Recommended, but Not Mandatory | String | Specifies the parent Group to which the Group belongs. In absence of this tag, ‘Primary’ is set as value for this tag by the system. |

**Tags to Specify Group Behaviours**

| Tag | Mandatory | Data Type | Explanation |
|---|---|---|---|
| issubledger | No | Logical | When set to Yes, the ledgers grouped under the same are not displayed in detailed mode of financial reports. When set to No, all the ledgers that are grouped are displayed in the detailed mode of financial reports.   By default, the value is No. |
| isaddable | No | Logical | If set to yes the displays the net debit or credit balance (whichever is higher) in the financial reports like Trial Balance where debit and credit balances are shown in separate columns. When set to No, the Debit and credit Balances are shown separately.   By default, the value is No. |
| addlalloctype | No | String | Values  &#4; Not Applicable (for XML)  "\u0004 Not Applicable" (for JSON)  Appropriate By Qty  Appropriate By Value   Specifies Method to Allocate when ledgers belonging to the group is used in Purchase Invoice, to allocate the expense of the item in the ratio of the quantity or value.   By default, the value is Not applicable. |

**Following Tags are applicable/required only when Parent tag is set to Primary or not specified. Else, they are set by the system based on the Parent Group set.**

| Tag | Mandatory | Data Type | Explanation |
|---|---|---|---|
| isrevenue & isdeemedpositive | No | Logical | Nature IsRevenue isdeemedpositive     Expenses Yes Yes   Income Yes No   Assets No Yes   Liabilities No No      Both these tags together determine the nature of the Group. In the absence of these tags, the tag values are defaulted to false and hence nature of group gets set as Liabilities. |
| affectsgrossprofit | No (conditional) | Logical | Applicable only for Income or Expense Groups   Set to Yes, to treat the group as a Direct expense.  Set to No, to treat the group as Indirect Expense.   Useful to display in financial reports like Profit & Loss.  Default value is No. |

**The below tags are system generated and is just for your information. These tags cannot be overridden or changed.**

| Tag | Nature of Tag | Data Type | Explanation |
|---|---|---|---|
| guid | System Generated | String | Unique identifier generated by Tally for the group. |
| alterid | System Generated | Number | Internal version identifier used when a group is modified. |
| objectupdateaction | System Generated | String | Specifies the action performed (Create, Alter, Delete). |

**Sample — XML Format**

```xml
<GROUP NAME="North Bank Accounts" >
      <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000e7d</GUID>
      <PARENT>Bank Accounts</PARENT>
      <OBJECTUPDATEACTION>Alter</OBJECTUPDATEACTION>
      <BASICGROUPISCALCULABLE>No</BASICGROUPISCALCULABLE>
      <ADDLALLOCTYPE>&#4; Not Applicable</ADDLALLOCTYPE>
      <GRPDEBITPARENT/>
      <GRPCREDITPARENT/>
      <ISBILLWISEON>No</ISBILLWISEON>
      <ISCOSTCENTRESON>No</ISCOSTCENTRESON>
      <ISADDABLE>Yes</ISADDABLE>
      <ISUPDATINGTARGETID>No</ISUPDATINGTARGETID>
      <ISDELETED>No</ISDELETED>
      <ISSECURITYONWHENENTERED>No</ISSECURITYONWHENENTERED>
      <ASORIGINAL>Yes</ASORIGINAL>
      <ISSUBLEDGER>Yes</ISSUBLEDGER>
      <ISREVENUE>No</ISREVENUE>
      <AFFECTSGROSSPROFIT>No</AFFECTSGROSSPROFIT>
      <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
      <TRACKNEGATIVEBALANCES>Yes</TRACKNEGATIVEBALANCES>
      <ISCONDENSED>No</ISCONDENSED>
      <AFFECTSSTOCK>No</AFFECTSSTOCK>
      <ISGROUPFORLOANRCPT>No</ISGROUPFORLOANRCPT>
      <ISGROUPFORLOANPYMNT>No</ISGROUPFORLOANPYMNT>
      <ISRATEINCLUSIVEVAT>No</ISRATEINCLUSIVEVAT>
      <ISINVDETAILSENABLE>No</ISINVDETAILSENABLE>
      <SORTPOSITION> 500</SORTPOSITION>
      <ALTERID> 7842</ALTERID>
      <UPDATEDDATETIME>20260305172759000</UPDATEDDATETIME>
</GROUP>

```

**Sample — JSON Format**

```json
{
            "metadata": {
                "type": "Group",
                "name": "North Bank Accounts",
                "reservedname": ""
            },
            "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000e7d",
            "parent": "Bank Accounts",
            "objectupdateaction": "Alter",
            "basicgroupiscalculable": "No",
            "addlalloctype": "\u0004 Not Applicable",
            "isbillwiseon": false,
            "iscostcentreson": false,
            "isaddable": true,
            "isupdatingtargetid": false,
            "isdeleted": false,
            "issecurityonwhenentered": false,
            "asoriginal": true,
            "issubledger": true,
            "isrevenue": false,
            "affectsgrossprofit": false,
            "isdeemedpositive": false,
            "tracknegativebalances": true,
            "iscondensed": false,
            "affectsstock": false,
            "isgroupforloanrcpt": false,
            "isgroupforloanpymnt": false,
            "israteinclusivevat": false,
            "isinvdetailsenable": false,
            "sortposition": " 500",
            "alterid": " 7842",
            "updateddatetime": "20260305172759000",
            "languagename": [
                {
                    "name": [
                        {
                            "metadata": true,
                            "type": "String"
                        },
                        "North Bank Accounts"
                    ],
                    "languageid": " 1033"
                }
            ]
        }

```

### 2.2.1 Create a Group

> Explorer id: `create-group` · Kind: **import** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#create-group)

#### Description

The Create action is used to add a new ledger to the company data in Tally by providing details such as the ledger name and parent group. The behaviour of the ledger depends on the parent group to which it is assigned.

**Integration use:** Create custom sub-groups (e.g. 'Online Customers') so ledgers created by your integration are segregated from manually created data.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svMstImportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `import` | Yes |
| `type` | `data` | Yes |
| `id` | `All Masters` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svMstImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Group",
        "action": "create",
        "name": "North Bank Accounts"
      },
      "name": "North Bank Accounts",
      "parent": "Bank Accounts"
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>All Masters</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
                <GROUP NAME="North Bank Accounts" Action="Create">
                    <NAME>North Bank Accounts</NAME>
                    <PARENT>Bank Accounts</PARENT>
                </GROUP>
            </TALLYMESSAGE>
        </DESC>
    </BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: import" \
  -H "type: data" \
  -H "id: All Masters" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟢 Official shape: Tally's published master import response):

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 1,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 0
        }
    }
}
```

**Success — XML** (🔵 Observed: captured from a live TallyPrime in `docs/Tally_Vouchers_Integration_Guide.md`; `CMPINFO` truncated):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <CREATED>1</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>0</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
        <DESC>
            <CMPINFO>
                <COMPANY>0</COMPANY>
                <GROUP>0</GROUP>
                <LEDGER>95</LEDGER>
                <!-- … one count element per object type (COSTCENTRE, GODOWN, STOCKITEM, UNIT, VOUCHERTYPE, …) … -->
                <VOUCHER>39</VOUCHER>
            </CMPINFO>
        </DESC>
    </BODY>
</ENVELOPE>
```

Check `created` = 1 **and** `errors` + `exceptions` = 0. `status: "1"` only means the request was processed, not that the record was accepted.

#### Error Responses

**Record-level failure:** `Group 'Bank Acounts' does not exist!`. Source: 🟡 Illustrative (same message pattern as the observed stock-group error).

Cause: Example: `parent` sent as "Bank Acounts", which does not exist in the company. Create or verify the parent first.

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <LINEERROR>Group &apos;Bank Acounts&apos; does not exist!</LINEERROR>
                <CREATED>0</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>1</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
    </BODY>
</ENVELOPE>
```

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 1
        }
    }
}
```

> In JSON the failure shows up as non-zero `errors` / `exceptions` counts. Tally does not document the JSON key that carries the line-error text, so log the raw response body; this repo's parser (`parse_tally_response_metrics`) also checks `import_result.line_error`.

See also [Common errors](#110-common-error-responses) (company not loaded, unknown request, Tally not running).

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `import` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `data` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `All Masters` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svMstImportFormat]` | `<STATICVARIABLES><SVMSTIMPORTFORMAT>` | Yes (master import) | String | `jsonex` | Import format of masters: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `tallymessage[]` | `<TALLYMESSAGE>` | Yes | Array<Object> |  | The objects to import (masters or vouchers). One request can carry many objects. |
| `tallymessage[].metadata` | `<GROUP …>` attributes | Yes | Object |  | Object identity block: type, name/identifiers and action. |
| `tallymessage[].metadata.type` | element name `<GROUP>` | Yes | String | `Group` | Object type: `Ledger`, `Group`, `Stock Item`, `Stock Group`, `Unit`, `Voucher`. |
| `tallymessage[].metadata.action` | `ACTION` attribute | Yes | String | `create` | `Create`, `Alter`, or `Delete` (case-insensitive). |
| `tallymessage[].metadata.name` | `NAME` attribute | Yes (masters) | String | `North Bank Accounts` | Name of the master; the key Tally matches on for Alter/Delete. |
| `tallymessage[].name` | `<GROUP>/NAME` | Yes | String | `North Bank Accounts` | Object name; unique within the company for masters. |
| `tallymessage[].parent` | `<GROUP>/PARENT` | Rec. | String | `Bank Accounts` | Parent group / stock group. Defaults to `Primary` when omitted (use `&#4; Primary` / `\u0004 Primary` to state it explicitly). |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Create a new Group ‘South Bank Accounts’ under Bank Accounts. | Change tag values: NAME | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/group/create-group/json/TaskCreateGroupSouthBankAccountsJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/group/create-group/xml/TaskCreateGroupSouthBankAccountsXML.txt) |
| Create a new Group by Name "Local Customers" under Sundry Debtors and make the group behave like sub ledger | Change tag values: NAME, PARENT. Add method issubledger | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/group/create-group/json/TaskCreateGroupLocalCustomersJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/group/create-group/xml/TaskCreateGroupLocalCustomersXML.txt) |

### 2.2.2 Alter a Group

> Explorer id: `alter-group` · Kind: **import** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#alter-group)

#### Description

The Alter action is used to modify the details of an existing group in Tally. You can update group information by sending a request with the group name and the storages that need to be changed. Once processed successfully, the group is updated with the specified changes.

**Integration use:** Adjust reporting behaviour of an integration-owned group (sub-ledger mode, parent) without touching the ledgers under it.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svMstImportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `import` | Yes |
| `type` | `data` | Yes |
| `id` | `All Masters` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svMstImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Group",
        "action": "Alter",
        "name": "North Bank Accounts"
      },
      "name": "North Bank Accounts",
      "IsSubLedger": "yes"
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>All Masters</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
                <GROUP NAME="North Bank Accounts" Action="Alter">
                    <NAME>North Bank Accounts</NAME>
                    <ISSUBLEDGER>Yes</ISSUBLEDGER>
                </GROUP>
            </TALLYMESSAGE>
        </DESC>
    </BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: import" \
  -H "type: data" \
  -H "id: All Masters" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟢 Official shape: Tally's published master import response):

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 1,
            "deleted": 0,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 0
        }
    }
}
```

**Success — XML** (🔵 Observed: captured from a live TallyPrime in `docs/Tally_Vouchers_Integration_Guide.md`; `CMPINFO` truncated):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <CREATED>0</CREATED>
                <ALTERED>1</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>0</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
        <DESC>
            <CMPINFO>
                <COMPANY>0</COMPANY>
                <GROUP>0</GROUP>
                <LEDGER>95</LEDGER>
                <!-- … one count element per object type (COSTCENTRE, GODOWN, STOCKITEM, UNIT, VOUCHERTYPE, …) … -->
                <VOUCHER>39</VOUCHER>
            </CMPINFO>
        </DESC>
    </BODY>
</ENVELOPE>
```

Check `altered` = 1 **and** `errors` + `exceptions` = 0. `status: "1"` only means the request was processed, not that the record was accepted.

#### Error Responses

**Record-level failure:** `Group 'North Bank Accounts' does not exist!`. Source: 🟡 Illustrative.

Cause: Alter matches on `metadata.name` (`NAME` attribute). The name must match an existing master exactly (case-insensitive).

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <LINEERROR>Group &apos;North Bank Accounts&apos; does not exist!</LINEERROR>
                <CREATED>0</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>1</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
    </BODY>
</ENVELOPE>
```

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 1
        }
    }
}
```

> In JSON the failure shows up as non-zero `errors` / `exceptions` counts. Tally does not document the JSON key that carries the line-error text, so log the raw response body; this repo's parser (`parse_tally_response_metrics`) also checks `import_result.line_error`.

See also [Common errors](#110-common-error-responses) (company not loaded, unknown request, Tally not running).

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `import` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `data` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `All Masters` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svMstImportFormat]` | `<STATICVARIABLES><SVMSTIMPORTFORMAT>` | Yes (master import) | String | `jsonex` | Import format of masters: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `tallymessage[]` | `<TALLYMESSAGE>` | Yes | Array<Object> |  | The objects to import (masters or vouchers). One request can carry many objects. |
| `tallymessage[].metadata` | `<GROUP …>` attributes | Yes | Object |  | Object identity block: type, name/identifiers and action. |
| `tallymessage[].metadata.type` | element name `<GROUP>` | Yes | String | `Group` | Object type: `Ledger`, `Group`, `Stock Item`, `Stock Group`, `Unit`, `Voucher`. |
| `tallymessage[].metadata.action` | `ACTION` attribute | Yes | String | `Alter` | `Create`, `Alter`, or `Delete` (case-insensitive). |
| `tallymessage[].metadata.name` | `NAME` attribute | Yes (masters) | String | `North Bank Accounts` | Name of the master; the key Tally matches on for Alter/Delete. |
| `tallymessage[].name` | `<GROUP>/NAME` | Yes | String | `North Bank Accounts` | Object name; unique within the company for masters. |
| `tallymessage[].IsSubLedger` | `<GROUP>/ISSUBLEDGER` | No | Logical | `yes` | Group behaves as sub-ledger (ledgers hidden in detailed reports). Default `No`. |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Alter group ‘North Bank Accounts’ and set issubledger as No | Change value of method issubledger | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/group/alter/json/TaskAlterGroupNorthBankAccountsJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/group/alter/xml/TaskAlterGroupNorthBankAccountsXML.txt) |
| Alter group "Local Customers" and change parent to ‘Sundry Creditors’ | Change value of method parent | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/group/alter/json/TaskAlterGroupLocalCustomersJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/group/alter/xml/TaskAlterGroupLocalCustomersXML.txt) |

### 2.2.3 Delete a Group

> Explorer id: `delete-group` · Kind: **import** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#delete-group)

#### Description

The Delete action is used to Delete a group from the company data. Any Group, unless not used or referred in ledgers or other masters, can be deleted.

**Integration use:** Clean up integration-owned groups. Fails while ledgers or sub-groups still reference it.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svMstImportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `import` | Yes |
| `type` | `data` | Yes |
| `id` | `All Masters` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svMstImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Group",
        "action": "Delete",
        "name": "North Bank Accounts"
      }
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>All Masters</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
                <GROUP NAME="North Bank Accounts" Action="Delete">
                    <NAME>North Bank Accounts</NAME>
                </GROUP>
            </TALLYMESSAGE>
        </DESC>
    </BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: import" \
  -H "type: data" \
  -H "id: All Masters" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟢 Official shape: Tally's published master import response):

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 0,
            "deleted": 1,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 0
        }
    }
}
```

**Success — XML** (🔵 Observed: captured from a live TallyPrime in `docs/Tally_Vouchers_Integration_Guide.md`; `CMPINFO` truncated):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <CREATED>0</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>1</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>0</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
        <DESC>
            <CMPINFO>
                <COMPANY>0</COMPANY>
                <GROUP>0</GROUP>
                <LEDGER>95</LEDGER>
                <!-- … one count element per object type (COSTCENTRE, GODOWN, STOCKITEM, UNIT, VOUCHERTYPE, …) … -->
                <VOUCHER>39</VOUCHER>
            </CMPINFO>
        </DESC>
    </BODY>
</ENVELOPE>
```

Check `deleted` = 1 **and** `errors` + `exceptions` = 0. `status: "1"` only means the request was processed, not that the record was accepted.

#### Error Responses

**Record-level failure:** `Cannot be deleted!`. Source: 🟡 Illustrative (message observed for Units in this repo).

Cause: The group is still referenced (by vouchers, child masters, stock items or compound units). Remove the references first, or archive instead of deleting.

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <LINEERROR>Cannot be deleted!</LINEERROR>
                <CREATED>0</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>1</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
    </BODY>
</ENVELOPE>
```

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 1
        }
    }
}
```

> In JSON the failure shows up as non-zero `errors` / `exceptions` counts. Tally does not document the JSON key that carries the line-error text, so log the raw response body; this repo's parser (`parse_tally_response_metrics`) also checks `import_result.line_error`.

See also [Common errors](#110-common-error-responses) (company not loaded, unknown request, Tally not running).

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `import` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `data` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `All Masters` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svMstImportFormat]` | `<STATICVARIABLES><SVMSTIMPORTFORMAT>` | Yes (master import) | String | `jsonex` | Import format of masters: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `tallymessage[]` | `<TALLYMESSAGE>` | Yes | Array<Object> |  | The objects to import (masters or vouchers). One request can carry many objects. |
| `tallymessage[].metadata` | `<GROUP …>` attributes | Yes | Object |  | Object identity block: type, name/identifiers and action. |
| `tallymessage[].metadata.type` | element name `<GROUP>` | Yes | String | `Group` | Object type: `Ledger`, `Group`, `Stock Item`, `Stock Group`, `Unit`, `Voucher`. |
| `tallymessage[].metadata.action` | `ACTION` attribute | Yes | String | `Delete` | `Create`, `Alter`, or `Delete` (case-insensitive). |
| `tallymessage[].metadata.name` | `NAME` attribute | Yes (masters) | String | `North Bank Accounts` | Name of the master; the key Tally matches on for Alter/Delete. |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Delete the group ‘Local Customers’ | Change tag values: NAME | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/group/delete/json/TaskDeleteGroupLocalCustomersJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/group/delete/xml/TaskDeleteGroupLocalCustomersXML.txt) |

### 2.2.4 Pull a Group

> Explorer id: `pull-group` · Kind: **object** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#pull-group)

#### Description

Details about a single group can be pulled using the Name of the group which is the identifier. All the first level methods from group object can be fetched

**Integration use:** Read a single group's hierarchy and balances, e.g. for validation before mapping an external category to a Tally group.

**Notes:**

- `Parent Hierarchy` returns the chain of parent groups.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svExportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVEXPORTFORMAT>XML</SVEXPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `export` | Yes |
| `type` | `object` | Yes |
| `subtype` | `Group` | Cond. |
| `id` | `Bank Accounts` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<SUBTYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonEx"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "fetch_list": [
    "Name",
    "Parent",
    "Parent Hierarchy",
    "Opening Balance",
    "Closing Balance"
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Object</TYPE>
        <SUBTYPE>Group</SUBTYPE>
        <ID TYPE="Name">Bank Accounts</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
            <FETCHLIST>
                <FETCH>Name</FETCH>
                <FETCH>Parent</FETCH>
                <FETCH>Parent Hierarchy</FETCH>
                <FETCH>Opening Balance</FETCH>
                <FETCH>Closing Balance</FETCH>
            </FETCHLIST>
        </DESC>
    </BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: export" \
  -H "type: object" \
  -H "subtype: Group" \
  -H "id: Bank Accounts" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟡 Illustrative: structure per Tally's published object-export sample `{type, value}` per method; values invented):

```json
{
    "status": "1",
    "tallymessage": [
        {
            "metadata": {
                "type": "Group",
                "name": "Bank Accounts",
                "reservedname": "",
                "id": "1042",
                "reqname": "Bank Accounts"
            },
            "parent": {
                "type": "String",
                "value": "Current Assets"
            },
            "parenthierarchy": {
                "type": "String",
                "value": "Current Assets"
            },
            "openingbalance": {
                "type": "Amount",
                "value": "-450000.00"
            },
            "closingbalance": {
                "type": "Amount",
                "value": "-518750.00"
            },
            "languagename": [
                {
                    "name": [
                        {
                            "metadata": true,
                            "type": "String"
                        },
                        "Bank Accounts"
                    ],
                    "languageid": {
                        "type": "Number",
                        "value": " 1033"
                    }
                }
            ]
        }
    ]
}
```

**Success — XML** (🟡 Illustrative: TYPE-attributed fields mirroring the JSON):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DESC>
        </DESC>
        <DATA>
            <TALLYMESSAGE>
                <GROUP NAME="Bank Accounts" RESERVEDNAME="">
                    <PARENT TYPE="String">Current Assets</PARENT>
                    <PARENTHIERARCHY TYPE="String">Current Assets</PARENTHIERARCHY>
                    <OPENINGBALANCE TYPE="Amount">-450000.00</OPENINGBALANCE>
                    <CLOSINGBALANCE TYPE="Amount">-518750.00</CLOSINGBALANCE>
                    <LANGUAGENAME.LIST>
                        <NAME.LIST TYPE="String">
                            <NAME>Bank Accounts</NAME>
                        </NAME.LIST>
                        <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
                    </LANGUAGENAME.LIST>
                </GROUP>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>
```

#### Error Responses

- **Object not found / wrong `subtype`** (🟡 Illustrative): Tally returns no object (an empty `tallymessage` / `<TALLYMESSAGE/>`) or `status` `0`. Treat a missing object, not just the status flag, as "not found".
- **Multilingual names:** send the name base64-encoded in `id-encoded` (with `content-type: application/json;charset=utf-8`) instead of `id`.
- [Common errors](#110-common-error-responses) apply (company not loaded, Tally not running).

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `export` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `object` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: subtype` | `<HEADER><SUBTYPE>` | Cond. | String | `Group` | Object type for `type: Object` (e.g. `Ledger`, `StockItem`). |
| `header: id` | `<HEADER><ID>` | Yes | String | `Bank Accounts` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svExportFormat]` | `<STATICVARIABLES><SVEXPORTFORMAT>` | Yes (export) | String | `jsonEx` | Response format: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `fetch_list[]` | `<FETCHLIST><FETCH>` | No | Array<String> | `Name, Parent, Parent Hierarchy, Opening …` | Methods/storages to return for an Object export (`type: object`). Omit to get the default set. |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Pull only opening balance and closing balance of the details of the Group ‘Cash-in-Hand’ | Change the HTTP Header value of 'id'. Fetch relevant methods. | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/group/pull/json/TaskPullGroupCashinhandJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/group/pull/xml/TaskPullGroupCashinhandXML.txt) |

### 2.2.5 Pull All Groups

> Explorer id: `pull-all-groups` · Kind: **collection** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#pull-all-groups)

#### Description

Details about multiple groups can be pulled using a TDL collection definition, which can already exist in the default source code or sent via the payload. TDL collection definition has type attribute that specifies the type of object that is grouped and fetch attribute that fetches the required methods.

**Integration use:** Mirror the full group tree to build a mapping UI (external category → Tally group) and to validate parents before ledger creation.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svExportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVEXPORTFORMAT>XML</SVEXPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `export` | Yes |
| `type` | `collection` | Yes |
| `id` | `Group` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Collection</TYPE>
        <ID>Group</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
    </BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: export" \
  -H "type: collection" \
  -H "id: Group" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟡 Illustrative (shape per Tally's published collection sample; values invented)):

```json
{
    "status": "1",
    "data": {
        "metadata": {
            "is_mst_dep_type": true,
            "mst_dep_type": "<type-code>"
        },
        "collection": [
            {
                "metadata": {
                    "type": "Group",
                    "name": "Bank Accounts",
                    "reservedname": ""
                },
                "parent": {
                    "type": "String",
                    "value": "Current Assets"
                },
                "languagename": [
                    {
                        "name": [
                            {
                                "metadata": true,
                                "type": "String"
                            },
                            "Bank Accounts"
                        ],
                        "languageid": {
                            "type": "Number",
                            "value": " 1033"
                        }
                    }
                ]
            },
            {
                "metadata": {
                    "type": "Group",
                    "name": "Bank OD A/c",
                    "reservedname": ""
                },
                "parent": {
                    "type": "String",
                    "value": "Loans (Liability)"
                },
                "languagename": [
                    {
                        "name": [
                            {
                                "metadata": true,
                                "type": "String"
                            },
                            "Bank OD A/c"
                        ],
                        "languageid": {
                            "type": "Number",
                            "value": " 1033"
                        }
                    }
                ]
            }
        ]
    }
}
```

**Success — XML** (🟡 Illustrative):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DESC>
        </DESC>
        <DATA>
            <COLLECTION>
                <GROUP NAME="Bank Accounts" RESERVEDNAME="">
                    <PARENT TYPE="String">Current Assets</PARENT>
                    <LANGUAGENAME.LIST>
                        <NAME.LIST TYPE="String">
                            <NAME>Bank Accounts</NAME>
                        </NAME.LIST>
                        <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
                    </LANGUAGENAME.LIST>
                </GROUP>
                <GROUP NAME="Bank OD A/c" RESERVEDNAME="">
                    <PARENT TYPE="String">Loans (Liability)</PARENT>
                    <LANGUAGENAME.LIST>
                        <NAME.LIST TYPE="String">
                            <NAME>Bank OD A/c</NAME>
                        </NAME.LIST>
                        <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
                    </LANGUAGENAME.LIST>
                </GROUP>
            </COLLECTION>
        </DATA>
    </BODY>
</ENVELOPE>
```

#### Error Responses

- **Collection name mismatch** (🟡 Illustrative): if the `id` header / `<ID>` does not match a default collection or a definition in `tdlmessage`, Tally returns an error instead of data. TDL names ignore case and spaces (`TSPL All Payment Vouchers` = `TSPLAllPaymentVouchers`), but any other spelling difference breaks the match.
- **Invalid TDL** (bad attribute or formula): Tally may show an error dialog on the Tally screen and return nothing useful. Validate TDL in the Explorer before shipping it.
- **Empty result:** a valid request that matches nothing returns `status: "1"` with an empty `collection` (`<COLLECTION/>`).
- [Common errors](#110-common-error-responses) apply.

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `export` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `collection` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `Group` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svExportFormat]` | `<STATICVARIABLES><SVEXPORTFORMAT>` | Yes (export) | String | `jsonex` | Response format: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |

### 2.2.6 Pull Groups of Group

> Explorer id: `pull-groups-of-group` · Kind: **collection** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#pull-groups-of-group)

#### Description

Details about multiple groups belonging to a group can be pulled using a TDL collection definition. When the TDL collection in default source code is not serving the requirement, a new TDL collection to fetch required information can be used. The TDL collection definition has type attribute that specifies the type of object that is grouped, child of attribute specifies the name of the parent and fetch attribute that fetches the required methods.

**Integration use:** Fetch one branch of the group tree (e.g. everything under Current Assets) with selected methods only.

**Notes:**

- `Belongs To: Yes` makes `Child Of` recursive (all descendants). Remove it to get direct children only.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svExportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVEXPORTFORMAT>XML</SVEXPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `export` | Yes |
| `type` | `collection` | Yes |
| `id` | `TSPLAssetGroups` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tdlmessage": [
    {
      "definitions": [
        {
          "metadata": {
            "name": "TSPLAssetGroups",
            "type": "Collection"
          },
          "attributes": [
            {
              "Type": "Group"
            },
            {
              "Child Of": "$$GroupCurrentAssets"
            },
            {
              "Belongs To": "Yes"
            },
            {
              "Native Method": "Name, Parent, IsSubledger, IsRevenue, Parent Hierarchy"
            }
          ]
        }
      ]
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Collection</TYPE>
        <ID>TSPLAssetGroups</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
            <TDL>
                <TDLMESSAGE>
                    <COLLECTION NAME="TSPLAssetGroups">
                        <TYPE>Group</TYPE>
                        <CHILDOF>$$GroupCurrentAssets</CHILDOF>
                        <BELONGSTO>Yes</BELONGSTO>
                        <NATIVEMETHOD>Name, Parent, IsSubledger, IsRevenue, Parent Hierarchy</NATIVEMETHOD>
                    </COLLECTION>
                </TDLMESSAGE>
            </TDL>
        </DESC>
    </BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: export" \
  -H "type: collection" \
  -H "id: TSPLAssetGroups" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟡 Illustrative (shape per Tally's published collection sample; values invented)):

```json
{
    "status": "1",
    "data": {
        "metadata": {
            "is_mst_dep_type": true,
            "mst_dep_type": "<type-code>"
        },
        "collection": [
            {
                "metadata": {
                    "type": "Group",
                    "name": "Bank Accounts",
                    "reservedname": ""
                },
                "parent": {
                    "type": "String",
                    "value": "Current Assets"
                },
                "issubledger": {
                    "type": "Logical",
                    "value": false
                },
                "isrevenue": {
                    "type": "Logical",
                    "value": false
                },
                "parenthierarchy": {
                    "type": "String",
                    "value": "Current Assets"
                },
                "languagename": [
                    {
                        "name": [
                            {
                                "metadata": true,
                                "type": "String"
                            },
                            "Bank Accounts"
                        ],
                        "languageid": {
                            "type": "Number",
                            "value": " 1033"
                        }
                    }
                ]
            },
            {
                "metadata": {
                    "type": "Group",
                    "name": "Cash-in-Hand",
                    "reservedname": ""
                },
                "parent": {
                    "type": "String",
                    "value": "Current Assets"
                },
                "issubledger": {
                    "type": "Logical",
                    "value": false
                },
                "isrevenue": {
                    "type": "Logical",
                    "value": false
                },
                "parenthierarchy": {
                    "type": "String",
                    "value": "Current Assets"
                },
                "languagename": [
                    {
                        "name": [
                            {
                                "metadata": true,
                                "type": "String"
                            },
                            "Cash-in-Hand"
                        ],
                        "languageid": {
                            "type": "Number",
                            "value": " 1033"
                        }
                    }
                ]
            }
        ]
    }
}
```

**Success — XML** (🟡 Illustrative):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DESC>
        </DESC>
        <DATA>
            <COLLECTION>
                <GROUP NAME="Bank Accounts" RESERVEDNAME="">
                    <PARENT TYPE="String">Current Assets</PARENT>
                    <ISSUBLEDGER TYPE="Logical">No</ISSUBLEDGER>
                    <ISREVENUE TYPE="Logical">No</ISREVENUE>
                    <PARENTHIERARCHY TYPE="String">Current Assets</PARENTHIERARCHY>
                    <LANGUAGENAME.LIST>
                        <NAME.LIST TYPE="String">
                            <NAME>Bank Accounts</NAME>
                        </NAME.LIST>
                        <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
                    </LANGUAGENAME.LIST>
                </GROUP>
                <GROUP NAME="Cash-in-Hand" RESERVEDNAME="">
                    <PARENT TYPE="String">Current Assets</PARENT>
                    <ISSUBLEDGER TYPE="Logical">No</ISSUBLEDGER>
                    <ISREVENUE TYPE="Logical">No</ISREVENUE>
                    <PARENTHIERARCHY TYPE="String">Current Assets</PARENTHIERARCHY>
                    <LANGUAGENAME.LIST>
                        <NAME.LIST TYPE="String">
                            <NAME>Cash-in-Hand</NAME>
                        </NAME.LIST>
                        <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
                    </LANGUAGENAME.LIST>
                </GROUP>
            </COLLECTION>
        </DATA>
    </BODY>
</ENVELOPE>
```

#### Error Responses

- **Collection name mismatch** (🟡 Illustrative): if the `id` header / `<ID>` does not match a default collection or a definition in `tdlmessage`, Tally returns an error instead of data. TDL names ignore case and spaces (`TSPL All Payment Vouchers` = `TSPLAllPaymentVouchers`), but any other spelling difference breaks the match.
- **Invalid TDL** (bad attribute or formula): Tally may show an error dialog on the Tally screen and return nothing useful. Validate TDL in the Explorer before shipping it.
- **Empty result:** a valid request that matches nothing returns `status: "1"` with an empty `collection` (`<COLLECTION/>`).
- [Common errors](#110-common-error-responses) apply.

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `export` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `collection` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `TSPLAssetGroups` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svExportFormat]` | `<STATICVARIABLES><SVEXPORTFORMAT>` | Yes (export) | String | `jsonex` | Response format: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `tdlmessage[]` | `<TDL><TDLMESSAGE>` | Cond. | Array<Object> |  | Inline TDL definitions (Collection / Report modification / System Formulae) that Tally loads before executing the request. |
| `tdlmessage[].definitions[]` | `<COLLECTION …>` | Cond. | Array<Object> |  | List of TDL definitions inside `tdlmessage`. |
| `tdlmessage[].definitions[].metadata.name` | `NAME` attribute | Yes | String | `TSPLAssetGroups` | Definition name. For a Collection it must match the `id` header / `<ID>`. TDL names are case- and space-insensitive. |
| `tdlmessage[].definitions[].metadata.type` | element name | Yes | String | `Collection` | Definition kind: `Collection`, `Report`, or `System`. |
| `tdlmessage[].definitions[].attributes[].Type` | `<TYPE>` | Yes | String | `Group` | Object type the collection gathers: `Ledger`, `Group`, `StockItem`, `StockGroup`, `Unit`, or `Vouchers:VoucherType` (vouchers of a voucher type). |
| `tdlmessage[].definitions[].attributes[].Child Of` | `<CHILDOF>` | No | String (TDL expr) | `$$GroupCurrentAssets` | Restricts the collection to children of a parent. Accepts a literal (`"Gadgets"`) or a system-name function such as `$$GroupBank`, `$$GroupCurrentAssets`, `$$VchTypePayment`. |
| `tdlmessage[].definitions[].attributes[].Belongs To` | `<BELONGSTO>` | No | Logical | `Yes` | With `Child Of`, `Yes` includes all descendants (not just direct children). |
| `tdlmessage[].definitions[].attributes[].Native Method` | `<NATIVEMETHOD>` | Yes | String (CSV) | `Name, Parent, IsSubledger, IsRevenue, Pa…` | Comma-separated methods to fetch for every object in the collection. |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Fetch only Groups that directly belong to CurrentAssets | Remove Belongs To tag | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/group/pull-group-of-groups/json/TaskGroupsofCurrentassetsJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/group/pull-group-of-groups/xml/TaskGroupsofCurrentassetsXML.txt) |
| Fetch name, parent, openingbalance, closing balance from Groups of group ‘CurrentLiabilities’ (GroupCurrentLiab) | Change Child of attribute. | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/group/pull-group-of-groups/json/TaskGroupsofCurrentLiabJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/group/pull-group-of-groups/xml/TaskGroupsofCurrentLiabXML.txt) |

# 3. Inventory Masters

## 3.1 Stock Item

### 3.1.0 Stock Item — Overview & Field Reference

> 🟢 Official: converted from the Explorer's "About Stock Item" page.

A Stock Item is a master that represents an individual product or material that a business buys, sells, or stores in inventory.

It is the actual inventory unit in TallyPrime to track for quantity, value, purchase, and sales transactions.

Each stock item has details such as: Name of the item, Unit of measurement, Stock group, Opening quantity, Rate/value

Example hierarchy:

```text
Electronics (Stock Group)
   ├── iPhone 14 (Stock Item)
   ├── Samsung Galaxy S23 (Stock Item)
    └── Dell Laptop (Stock Item)

```

In integration scenarios, Stock Items are used to

- To Synchronize Product Catalogs
- To Record Inventory Transactions
- To Enable Automated Inventory Updates

Understanding the structure and required fields of a StockItem is essential as Stock Item plays an important role in inventory management.

A StockItem has over 200+ tags; however, all tags are not mandatory. The required tags depend on the characteristics of the stockitem.

**For basic StockItem creation, usually the following is sufficient:**

Applicable for XML Format only

| Tag/Attribute | Identifier | Mandatory | Data Type | Explanation |
|---|---|---|---|---|
| stockitem | Tag | Yes | String | Specifies the Type of the Object. In this case its ‘StockItem’ |
| name | Attribute of StockItem tag | Yes | String | The name of the StockItem. This uniquely identifies the StockItem within the company |

Applicable for JSON Format only

| Tag | Mandatory | Data Type | Explanation |
|---|---|---|---|
| metadata | Yes | Object | This contains the metadata information that specifies the type of object and name of the StockItem |
| type | Yes | String | Specifies the Type of the Object. In this case its ‘StockItem’ |
| name | Yes | String | The name of the StockItem. This uniquely identifies the StockItem within the company |

Applicable for both XML and JSON formats

| Tag | Mandatory | Data Type | Explanation |
|---|---|---|---|
| name | Yes | String | The name of the StockItem. This uniquely identifies the StockItem within the company. |
| baseunits | Recommended, but Not Mandatory | String | Specifies the base unit of measure for stock item. This unit is crucial as without which one cannot update or track the quantity for the stockitem. |

**Frequently used tags**

| Tag | Mandatory | Data Type | Explanation |
|---|---|---|---|
| parent | No | String | Specifies the Stock Group to which the stockitem belongs. In absence of this tag, ‘Primary’ is set as value for this tag by the system. |
| category | No | String | Specifies the Stock Category for the stock item. Stock Category is used to create parallel grouping. For example, with parallel grouping, you can view the purchases of S sized t shirts under T shirts stock group as well as S Sized garments category.   In the absence of this tag, system automatically assigns &#4; Not Applicable (for XML), "\0004 Not Applicable" (for JSON) |
| additionalunits | No | String | Specifies additional/alternate unit of measure for stock item. The conversion & denominator tag is also necessary for the additional units tag to work as expected. The stockitem will be tracked for quantity in both base unit and additional units. |
| conversion | Yes (Conditional) | Number | Should be specified if additional units are given. Specifies the conversion factor from additional unit to base unit. |
| denominator | Yes (conditional) | Number | Should be specified if additional units are given. Specifies the denominator factor from additional unit to base unit. |
| openingbalance | No | Quantity | Specifies the opening quantity for the item |
| openingvalue | No | Amount | Specifies the opening value for the item |
| openingrate | No | Rate | Specifies the provide opening rate for the item |
| Isbatchwiseon | No | Logical | Specifies if batch wise allocations is enabled for the stockitem or not.   Default value is No. |

**Batch allocation tags for a stock item when batch-wise details are enabled using the IsBatchwiseOn tag**

| Tag/Collection | Mandatory | Data Type | Mandatory |
|---|---|---|---|
| batchallocations | Yes (Conditional) | Collection | Used to allocate the StockItem opening balance with batches when batch wise allocations is enabled. |
| Godowname | No |  | Specifies the godown name for batch. Incase no godown is available, MAIN LOCATION is provided as the default. |
| Batchname | Yes (Conditional) |  | Should be provided when batchwise is on and opening balance is given for the stock item. |
| openingbalance | Yes (Conditional) |  | Specifies the opening quantity for the batch |
| openingvalue | No |  | Specifies the opening value for the batch |
| openingrate | No |  | Specifies the opening rate for the batch |

**The below tags are system generated and is just for your information. These tags cannot be overridden or changed.**

| Tag | Nature of Tag | Data Type | Explanation |
|---|---|---|---|
| guid | System Generated | String | Unique identifier generated by Tally for the Stockitem. |
| alterid | System Generated | Number | Internal version identifier used when a Stockitem is modified. |
| objectupdateaction | System Generated | String | Specifies the action performed (Create, Alter, Delete). |

**Sample — XML Format**

```xml
<STOCKITEM NAME="Coffee Beans">
      <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000e80</GUID>
      <PARENT>Coffee</PARENT>
      <CATEGORY>Raw Materials</CATEGORY>
      <OBJECTUPDATEACTION>Alter</OBJECTUPDATEACTION>
      <GSTAPPLICABLE>&#4; Applicable</GSTAPPLICABLE>
      <TAXCLASSIFICATIONNAME>&#4; Not Applicable</TAXCLASSIFICATIONNAME>
      <GSTTYPEOFSUPPLY>Goods</GSTTYPEOFSUPPLY>
      <EXCISEAPPLICABILITY>&#4; Applicable</EXCISEAPPLICABILITY>
      <SALESTAXCESSAPPLICABLE/>
      <VATAPPLICABLE>&#4; Applicable</VATAPPLICABLE>
      <COSTINGMETHOD>Avg. Cost</COSTINGMETHOD>
      <VALUATIONMETHOD>Avg. Price</VALUATIONMETHOD>
      <BASEUNITS>Kg</BASEUNITS>
      <ADDITIONALUNITS>Gms</ADDITIONALUNITS>
      <ISCOSTCENTRESON>No</ISCOSTCENTRESON>
      <ISBATCHWISEON>Yes</ISBATCHWISEON>
      <ISPERISHABLEON>No</ISPERISHABLEON>
      <ISENTRYTAXAPPLICABLE>No</ISENTRYTAXAPPLICABLE>
      <ISCOSTTRACKINGON>No</ISCOSTTRACKINGON>
      <HASMFGDATE>No</HASMFGDATE>
      <ALTERID> 7849</ALTERID>
      <DENOMINATOR> 100</DENOMINATOR>
      <CONVERSION> 1</CONVERSION>
      <OPENINGBALANCE> 200 Kg =  2.00 Gms</OPENINGBALANCE>
      <OPENINGVALUE>-800.00</OPENINGVALUE>
      <OPENINGRATE>4.00/Kg</OPENINGRATE>
      <UPDATEDDATETIME>20260309141744000</UPDATEDDATETIME>
      <NAME>Coffee Beans</NAME>
      <BATCHALLOCATIONS.LIST>
       <GODOWNNAME>Abdul Kalith</GODOWNNAME>
       <BATCHNAME>Batch1</BATCHNAME>
       <OPENINGBALANCE> 200 Kg =  2.00 Gms</OPENINGBALANCE>
       <OPENINGVALUE>-800.00</OPENINGVALUE>
       <OPENINGRATE>4.00/Kg</OPENINGRATE>
      </BATCHALLOCATIONS.LIST>
</STOCKITEM>
```

**Sample — JSON Format**

```json
{
  "metadata": {
    "type": "Stock Item",
    "name": "Coffee Beans"
  },
  "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000e80",
  "parent": "Coffee",
  "category": "Raw Materials",
  "objectupdateaction": "Alter",
  "gstapplicable": "\u0004 Applicable",
  "taxclassificationname": "\u0004 Not Applicable",
  "gsttypeofsupply": "Goods",
  "exciseapplicability": "\u0004 Applicable",
  "vatapplicable": "\u0004 Applicable",
  "costingmethod": "Avg. Cost",
  "valuationmethod": "Avg. Price",
  "baseunits": "Kg",
  "additionalunits": "Gms",
  "exciseitemclassification": "\u0004 Not Applicable",
  "vatbaseunit": "Kg",
  "iscostcentreson": false,
  "isbatchwiseon": true,
  "isperishableon": false,
  "isentrytaxapplicable": false,
  "iscosttrackingon": false,
  "hasmfgdate": false,
  "alterid": " 7849",
  "denominator": " 100",
  "conversion": " 1",
  "openingbalance": " 200 Kg =  2.00 Gms",
  "openingvalue": "-800.00",
  "openingrate": "4.00/Kg",
  "updateddatetime": "20260309141744000",
  "name": "Coffee Beans",
  "batchallocations": [
    {
      "godownname": "Abdul Kalith",
      "batchname": "Batch1",
      "openingbalance": " 200 Kg =  2.00 Gms",
      "openingvalue": "-800.00",
      "openingrate": "4.00/Kg"
    }
  ]
}
```

### 3.1.1 Create a Stock Item

> Explorer id: `create-stock-item` · Kind: **import** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#create-stock-item)

#### Description

The Create action is used to add a new stockitem to the company data in Tally by providing details such as the stockitem name and units.

**Integration use:** Sync your product catalogue into Tally so inventory vouchers can reference items by name.

**Notes:**

- The XML sample uses mixed-case tags (`<StockItem>`, `<BaseUnits>`) and `&#4; Primary` for the root parent. Tags are case-insensitive.
- The base unit (e.g. `nos`) must exist before the item is created.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svMstImportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `import` | Yes |
| `type` | `data` | Yes |
| `id` | `All Masters` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svMstImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Stock Item",
        "name": "Tea Powder",
        "action": "create"
      },
      "name": "Tea Powder",
      "parent": "\u0004 Primary",
      "base units": "nos"
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>All Masters</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
            <TALLYMESSAGE>
                <StockItem NAME="Tea Powder" Action="Create">
                    <NAME>Tea Powder</NAME>
                    <PARENT>&#4; Primary</PARENT>
                    <BaseUnits>nos</BaseUnits>
                </StockItem>
            </TALLYMESSAGE>
        </DESC>
</BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: import" \
  -H "type: data" \
  -H "id: All Masters" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟢 Official shape: Tally's published master import response):

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 1,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 0
        }
    }
}
```

**Success — XML** (🔵 Observed: captured from a live TallyPrime in `docs/Tally_Vouchers_Integration_Guide.md`; `CMPINFO` truncated):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <CREATED>1</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>0</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
        <DESC>
            <CMPINFO>
                <COMPANY>0</COMPANY>
                <GROUP>0</GROUP>
                <LEDGER>95</LEDGER>
                <!-- … one count element per object type (COSTCENTRE, GODOWN, STOCKITEM, UNIT, VOUCHERTYPE, …) … -->
                <VOUCHER>39</VOUCHER>
            </CMPINFO>
        </DESC>
    </BODY>
</ENVELOPE>
```

Check `created` = 1 **and** `errors` + `exceptions` = 0. `status: "1"` only means the request was processed, not that the record was accepted.

#### Error Responses

**Record-level failure:** `Stock Group 'Beverages' does not exist!`. Source: 🔵 Observed.

Cause: Example: `parent` sent as "Beverages", which does not exist in the company. Create or verify the parent first.

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <LINEERROR>Stock Group &apos;Beverages&apos; does not exist!</LINEERROR>
                <CREATED>0</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>1</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
    </BODY>
</ENVELOPE>
```

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 1
        }
    }
}
```

> In JSON the failure shows up as non-zero `errors` / `exceptions` counts. Tally does not document the JSON key that carries the line-error text, so log the raw response body; this repo's parser (`parse_tally_response_metrics`) also checks `import_result.line_error`.

See also [Common errors](#110-common-error-responses) (company not loaded, unknown request, Tally not running).

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `import` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `data` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `All Masters` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svMstImportFormat]` | `<STATICVARIABLES><SVMSTIMPORTFORMAT>` | Yes (master import) | String | `jsonex` | Import format of masters: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `tallymessage[]` | `<TALLYMESSAGE>` | Yes | Array<Object> |  | The objects to import (masters or vouchers). One request can carry many objects. |
| `tallymessage[].metadata` | `<STOCKITEM …>` attributes | Yes | Object |  | Object identity block: type, name/identifiers and action. |
| `tallymessage[].metadata.type` | element name `<STOCKITEM>` | Yes | String | `Stock Item` | Object type: `Ledger`, `Group`, `Stock Item`, `Stock Group`, `Unit`, `Voucher`. |
| `tallymessage[].metadata.name` | `NAME` attribute | Yes (masters) | String | `Tea Powder` | Name of the master; the key Tally matches on for Alter/Delete. |
| `tallymessage[].metadata.action` | `ACTION` attribute | Yes | String | `create` | `Create`, `Alter`, or `Delete` (case-insensitive). |
| `tallymessage[].name` | `<STOCKITEM>/NAME` | Yes | String | `Tea Powder` | Object name; unique within the company for masters. |
| `tallymessage[].parent` | `<STOCKITEM>/PARENT` | Rec. | String | `\u0004 Primary` | Parent group / stock group. Defaults to `Primary` when omitted (use `&#4; Primary` / `\u0004 Primary` to state it explicitly). |
| `tallymessage[].base units` | `<STOCKITEM>/BASEUNITS` | Rec. / Cond. | String | `nos` | Stock item: base unit of measure. Compound unit: the first (base) unit. |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Create a new stockitem ‘NoteBooks’ | Change tag values: NAME | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/stock-item/create/json/TaskCreateStockItemNoteBooksJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/stock-item/create/xml/TaskCreateStockItemNoteBooksXML.txt) |
| Create a new stockitem ‘Ink Pens’ with units nos and opening balance 200 nos | Change tag values : NAME, baseunits, OPENINGBALANCE | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/stock-item/create/json/TaskCreateStockItemInkPensJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/stock-item/create/xml/TaskCreateStockItemInkPensXML.txt) |

### 3.1.2 Alter a Stock Item

> Explorer id: `alter-stock-item` · Kind: **import** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#alter-stock-item)

#### Description

The Alter action is used to modify the details of an existing stockitem in Tally. You can update stockitem information by sending a request with the stockitem name and the storages that need to be changed. Once processed successfully, the stockitem is updated with the specified changes.

**Integration use:** Keep item attributes (opening stock, batches, units) in step with the source catalogue.

**Notes:**

- JSON metadata type is `"Stock Item"` (with a space). The header `subtype` for object export is `StockItem`.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svMstImportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `import` | Yes |
| `type` | `data` | Yes |
| `id` | `All Masters` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svMstImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Stock Item",
        "name": "Tea Powder",
        "action": "Alter"
      },
      "opening balance": " 200 nos"
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>All Masters</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
            <TALLYMESSAGE>
                <StockItem NAME="Tea Powder" Action="Alter">
                    <NAME> Tea Powder </NAME>
                    <OPENINGBALANCE>200 NOS</OPENINGBALANCE>
                </StockItem>
            </TALLYMESSAGE>
        </DESC>
</BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: import" \
  -H "type: data" \
  -H "id: All Masters" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟢 Official shape: Tally's published master import response):

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 1,
            "deleted": 0,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 0
        }
    }
}
```

**Success — XML** (🔵 Observed: captured from a live TallyPrime in `docs/Tally_Vouchers_Integration_Guide.md`; `CMPINFO` truncated):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <CREATED>0</CREATED>
                <ALTERED>1</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>0</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
        <DESC>
            <CMPINFO>
                <COMPANY>0</COMPANY>
                <GROUP>0</GROUP>
                <LEDGER>95</LEDGER>
                <!-- … one count element per object type (COSTCENTRE, GODOWN, STOCKITEM, UNIT, VOUCHERTYPE, …) … -->
                <VOUCHER>39</VOUCHER>
            </CMPINFO>
        </DESC>
    </BODY>
</ENVELOPE>
```

Check `altered` = 1 **and** `errors` + `exceptions` = 0. `status: "1"` only means the request was processed, not that the record was accepted.

#### Error Responses

**Record-level failure:** `Stock Item 'Tea Powder' does not exist!`. Source: 🟡 Illustrative.

Cause: Alter matches on `metadata.name` (`NAME` attribute). The name must match an existing master exactly (case-insensitive).

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <LINEERROR>Stock Item &apos;Tea Powder&apos; does not exist!</LINEERROR>
                <CREATED>0</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>1</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
    </BODY>
</ENVELOPE>
```

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 1
        }
    }
}
```

> In JSON the failure shows up as non-zero `errors` / `exceptions` counts. Tally does not document the JSON key that carries the line-error text, so log the raw response body; this repo's parser (`parse_tally_response_metrics`) also checks `import_result.line_error`.

See also [Common errors](#110-common-error-responses) (company not loaded, unknown request, Tally not running).

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `import` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `data` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `All Masters` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svMstImportFormat]` | `<STATICVARIABLES><SVMSTIMPORTFORMAT>` | Yes (master import) | String | `jsonex` | Import format of masters: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `tallymessage[]` | `<TALLYMESSAGE>` | Yes | Array<Object> |  | The objects to import (masters or vouchers). One request can carry many objects. |
| `tallymessage[].metadata` | `<STOCKITEM …>` attributes | Yes | Object |  | Object identity block: type, name/identifiers and action. |
| `tallymessage[].metadata.type` | element name `<STOCKITEM>` | Yes | String | `Stock Item` | Object type: `Ledger`, `Group`, `Stock Item`, `Stock Group`, `Unit`, `Voucher`. |
| `tallymessage[].metadata.name` | `NAME` attribute | Yes (masters) | String | `Tea Powder` | Name of the master; the key Tally matches on for Alter/Delete. |
| `tallymessage[].metadata.action` | `ACTION` attribute | Yes | String | `Alter` | `Create`, `Alter`, or `Delete` (case-insensitive). |
| `tallymessage[].opening balance` | `<STOCKITEM>/OPENINGBALANCE` | No | Amount / Quantity | `200 nos` | Opening balance. Ledgers: Amount, negative = Debit, positive = Credit. Stock: quantity with unit (e.g. `200 nos`). |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Alter stockitem ‘notebooks’ with openingbalance 100 nos | Change values of name and Opening Balance | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/stock-item/alter/json/TaslAlterStockItemNoteBooksJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/stock-item/alter/xml/TaslAlterStockItemNoteBooksXML.txt) |
| Alter StockItem ‘Ink Pens’ and enable batchallocations. Add batchallocations for the opening balance 200 Nos. In the order of Godown, batchname, quantity and rate, value 1)Main Location, Batch1, 100 Nos, 10/Nos 2)Main Location, batch2, 100 Nos, 15/Nos Add new collection ‘batchallocations’ twice. provide tags godownname, batchname, openingbalance, openingrate | Add new collection ‘batchallocations’ twice. provide tags godownname, batchname, openingbalance, openingrate | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/stock-item/alter/json/TaskAlterStockItemInkPensWithBatchJSON.txt) |
| Alter StockItem ‘Ink Pens’ and enable batchallocations. Add 2 batchallocations for the opening balance 200 Nos. In the order of Godown, batchname, quantity and rate, value 1)Main Location, Batch1, 100 Nos, 10/Nos 2)Main Location, batch2, 100 Nos, 15/Nos Add new collection ‘batchallocations’ twice. provide tags godownname, batchname, openingbalance, openingrate | Add new collection ‘batchallocations’ twice. provide tags godownname, batchname, openingbalance, openingrate | [XML](https://tallysolutions.com/tallyprime-api-explorer/files/stock-item/alter/xml/TaskAlterStockItemInkPensWithBatchXML.txt) |

### 3.1.3 Delete a Stock Item

> Explorer id: `delete-stock-item` · Kind: **import** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#delete-stock-item)

#### Description

The Delete action is used to Delete a stockitem from the company data. Any stockitem, unless not used or referred in transactions or other masters, can be deleted.

**Integration use:** Remove discontinued items that were never transacted.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svMstImportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `import` | Yes |
| `type` | `data` | Yes |
| `id` | `All Masters` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svMstImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Stock Item",
        "name": "Tea Powder",
        "action": "Delete"
      }
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>All Masters</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
            <TALLYMESSAGE>
                <StockItem NAME="Tea Powder" Action="Delete">
                    <NAME> Tea Powder </NAME>
                </StockItem>
            </TALLYMESSAGE>
        </DESC>
</BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: import" \
  -H "type: data" \
  -H "id: All Masters" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟢 Official shape: Tally's published master import response):

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 0,
            "deleted": 1,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 0
        }
    }
}
```

**Success — XML** (🔵 Observed: captured from a live TallyPrime in `docs/Tally_Vouchers_Integration_Guide.md`; `CMPINFO` truncated):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <CREATED>0</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>1</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>0</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
        <DESC>
            <CMPINFO>
                <COMPANY>0</COMPANY>
                <GROUP>0</GROUP>
                <LEDGER>95</LEDGER>
                <!-- … one count element per object type (COSTCENTRE, GODOWN, STOCKITEM, UNIT, VOUCHERTYPE, …) … -->
                <VOUCHER>39</VOUCHER>
            </CMPINFO>
        </DESC>
    </BODY>
</ENVELOPE>
```

Check `deleted` = 1 **and** `errors` + `exceptions` = 0. `status: "1"` only means the request was processed, not that the record was accepted.

#### Error Responses

**Record-level failure:** `Cannot be deleted!`. Source: 🟡 Illustrative (message observed for Units in this repo).

Cause: The stock item is still referenced (by vouchers, child masters, stock items or compound units). Remove the references first, or archive instead of deleting.

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <LINEERROR>Cannot be deleted!</LINEERROR>
                <CREATED>0</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>1</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
    </BODY>
</ENVELOPE>
```

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 1
        }
    }
}
```

> In JSON the failure shows up as non-zero `errors` / `exceptions` counts. Tally does not document the JSON key that carries the line-error text, so log the raw response body; this repo's parser (`parse_tally_response_metrics`) also checks `import_result.line_error`.

See also [Common errors](#110-common-error-responses) (company not loaded, unknown request, Tally not running).

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `import` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `data` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `All Masters` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svMstImportFormat]` | `<STATICVARIABLES><SVMSTIMPORTFORMAT>` | Yes (master import) | String | `jsonex` | Import format of masters: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `tallymessage[]` | `<TALLYMESSAGE>` | Yes | Array<Object> |  | The objects to import (masters or vouchers). One request can carry many objects. |
| `tallymessage[].metadata` | `<STOCKITEM …>` attributes | Yes | Object |  | Object identity block: type, name/identifiers and action. |
| `tallymessage[].metadata.type` | element name `<STOCKITEM>` | Yes | String | `Stock Item` | Object type: `Ledger`, `Group`, `Stock Item`, `Stock Group`, `Unit`, `Voucher`. |
| `tallymessage[].metadata.name` | `NAME` attribute | Yes (masters) | String | `Tea Powder` | Name of the master; the key Tally matches on for Alter/Delete. |
| `tallymessage[].metadata.action` | `ACTION` attribute | Yes | String | `Delete` | `Create`, `Alter`, or `Delete` (case-insensitive). |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Delete the stockitem ‘NoteBooks’ | Change tag values: NAME | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/stock-item/delete/json/TaskDeleteStockItemNoteBooksJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/stock-item/delete/xml/TaskDeleteStockItemNoteBooksXML.txt) |

### 3.1.4 Pull a Stock Item

> Explorer id: `pull-stock-item` · Kind: **object** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#pull-stock-item)

#### Description

Details about a single stockitem can be pulled using the Name of the stockitem which is the identifier. All the first level methods from stockitem object can be fetched.

**Integration use:** Read back one item's balances, e.g. to display current stock before an order is placed.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svExportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVEXPORTFORMAT>XML</SVEXPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `export` | Yes |
| `type` | `object` | Yes |
| `subtype` | `StockItem` | Cond. |
| `id` | `Coffee Powder` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<SUBTYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonEx"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "fetch_list": [
    "Name",
    "Parent",
    "Opening Balance",
    "Closing Balance"
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Object</TYPE>
        <SUBTYPE>Stock Item</SUBTYPE>
        <ID TYPE="Name">Coffee Powder</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
            <FETCHLIST>
                <FETCH>Name</FETCH>
                <FETCH>Parent</FETCH>
                <FETCH>BaseUnits</FETCH>
                <FETCH>Closing Balance</FETCH>
            </FETCHLIST>
        </DESC>
    </BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: export" \
  -H "type: object" \
  -H "subtype: StockItem" \
  -H "id: Coffee Powder" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟡 Illustrative: structure per Tally's published object-export sample `{type, value}` per method; values invented):

```json
{
    "status": "1",
    "tallymessage": [
        {
            "metadata": {
                "type": "Stock Item",
                "name": "Coffee Powder",
                "reservedname": "",
                "id": "1042",
                "reqname": "Coffee Powder"
            },
            "parent": {
                "type": "String",
                "value": "Coffee"
            },
            "openingbalance": {
                "type": "Quantity",
                "value": " 100 Kg"
            },
            "closingbalance": {
                "type": "Quantity",
                "value": " 64 Kg"
            },
            "languagename": [
                {
                    "name": [
                        {
                            "metadata": true,
                            "type": "String"
                        },
                        "Coffee Powder"
                    ],
                    "languageid": {
                        "type": "Number",
                        "value": " 1033"
                    }
                }
            ]
        }
    ]
}
```

**Success — XML** (🟡 Illustrative: TYPE-attributed fields mirroring the JSON):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DESC>
        </DESC>
        <DATA>
            <TALLYMESSAGE>
                <STOCKITEM NAME="Coffee Powder" RESERVEDNAME="">
                    <PARENT TYPE="String">Coffee</PARENT>
                    <OPENINGBALANCE TYPE="Quantity"> 100 Kg</OPENINGBALANCE>
                    <CLOSINGBALANCE TYPE="Quantity"> 64 Kg</CLOSINGBALANCE>
                    <LANGUAGENAME.LIST>
                        <NAME.LIST TYPE="String">
                            <NAME>Coffee Powder</NAME>
                        </NAME.LIST>
                        <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
                    </LANGUAGENAME.LIST>
                </STOCKITEM>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>
```

#### Error Responses

- **Object not found / wrong `subtype`** (🟡 Illustrative): Tally returns no object (an empty `tallymessage` / `<TALLYMESSAGE/>`) or `status` `0`. Treat a missing object, not just the status flag, as "not found".
- **Multilingual names:** send the name base64-encoded in `id-encoded` (with `content-type: application/json;charset=utf-8`) instead of `id`.
- [Common errors](#110-common-error-responses) apply (company not loaded, Tally not running).

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `export` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `object` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: subtype` | `<HEADER><SUBTYPE>` | Cond. | String | `StockItem` | Object type for `type: Object` (e.g. `Ledger`, `StockItem`). |
| `header: id` | `<HEADER><ID>` | Yes | String | `Coffee Powder` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svExportFormat]` | `<STATICVARIABLES><SVEXPORTFORMAT>` | Yes (export) | String | `jsonEx` | Response format: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `fetch_list[]` | `<FETCHLIST><FETCH>` | No | Array<String> | `Name, Parent, Opening Balance, Closing B…` | Methods/storages to return for an Object export (`type: object`). Omit to get the default set. |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Pull only closing balance details of the stockitem ‘Apple MacBook Pro Laptop’ | Change the HTTP Header value of 'id'. Fetch relevant methods. | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/stock-item/pull/json/TaskPullStockItemAppleMacBookProLaptopJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/stock-item/pull/xml/TaskPullStockItemAppleMacBookProLaptopXML.txt) |

### 3.1.5 Pull All Stock Item

> Explorer id: `pull-all-stock-items` · Kind: **collection** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#pull-all-stock-items)

#### Description

Details about multiple stockitems can be pulled using a TDL collection definition, which can already exist in the default source code or sent via the payload. TDL collection definition has type attribute that specifies the type of object that is grouped and fetch attribute that fetches the required methods.

**Integration use:** Full catalogue reconciliation between your system and Tally.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svExportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVEXPORTFORMAT>XML</SVEXPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `export` | Yes |
| `type` | `collection` | Yes |
| `id` | `Stock Item` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Collection</TYPE>
        <ID>StockItem</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
    </BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: export" \
  -H "type: collection" \
  -H "id: Stock Item" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟢 Official (JSON excerpt of Tally's published sample, first 2 of N objects)):

```json
{
    "status": "1",
    "data": {
        "metadata": {
            "is_mst_dep_type": true,
            "mst_dep_type": "512"
        },
        "collection": [
            {
                "metadata": {
                    "type": "Stock Item",
                    "name": "Apple MacBook Pro Laptop",
                    "reservedname": ""
                },
                "languagename": [
                    {
                        "name": [
                            {
                                "metadata": true,
                                "type": "String"
                            },
                            "Apple MacBook Pro Laptop"
                        ],
                        "languageid": {
                            "type": "Number",
                            "value": " 1033"
                        }
                    }
                ]
            },
            {
                "metadata": {
                    "type": "Stock Item",
                    "name": "Computer1",
                    "reservedname": ""
                },
                "languagename": [
                    {
                        "name": [
                            {
                                "metadata": true,
                                "type": "String"
                            },
                            "Computer1"
                        ],
                        "languageid": {
                            "type": "Number",
                            "value": " 1033"
                        }
                    }
                ]
            }
        ]
    }
}
```

**Success — XML** (🟡 Illustrative):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DESC>
        </DESC>
        <DATA>
            <COLLECTION>
                <STOCKITEM NAME="Apple MacBook Pro Laptop" RESERVEDNAME="">
                    <LANGUAGENAME.LIST>
                        <NAME.LIST TYPE="String">
                            <NAME>Apple MacBook Pro Laptop</NAME>
                        </NAME.LIST>
                        <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
                    </LANGUAGENAME.LIST>
                </STOCKITEM>
                <STOCKITEM NAME="Computer1" RESERVEDNAME="">
                    <LANGUAGENAME.LIST>
                        <NAME.LIST TYPE="String">
                            <NAME>Computer1</NAME>
                        </NAME.LIST>
                        <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
                    </LANGUAGENAME.LIST>
                </STOCKITEM>
            </COLLECTION>
        </DATA>
    </BODY>
</ENVELOPE>
```

#### Error Responses

- **Collection name mismatch** (🟡 Illustrative): if the `id` header / `<ID>` does not match a default collection or a definition in `tdlmessage`, Tally returns an error instead of data. TDL names ignore case and spaces (`TSPL All Payment Vouchers` = `TSPLAllPaymentVouchers`), but any other spelling difference breaks the match.
- **Invalid TDL** (bad attribute or formula): Tally may show an error dialog on the Tally screen and return nothing useful. Validate TDL in the Explorer before shipping it.
- **Empty result:** a valid request that matches nothing returns `status: "1"` with an empty `collection` (`<COLLECTION/>`).
- [Common errors](#110-common-error-responses) apply.

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `export` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `collection` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `Stock Item` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svExportFormat]` | `<STATICVARIABLES><SVEXPORTFORMAT>` | Yes (export) | String | `jsonex` | Response format: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |

### 3.1.6 Pull Stock Items of Stock Group

> Explorer id: `pull-stock-items-of-stock-group` · Kind: **collection** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#pull-stock-items-of-stock-group)

#### Description

Details about multiple stockitems belonging to a stock group can be pulled using a TDL collection definition. When the TDL collection in default source code is not serving the requirement, a new TDL collection to fetch required information can be used. The TDL collection definition has type attribute that specifies the type of object that is grouped, child of attribute specifies the name of the parent and fetch attribute that fetches the required methods.

**Integration use:** Category-scoped stock snapshot (closing qty/value) for dashboards or storefront availability.

**Notes:**

- `Child Of` takes a quoted literal here (`"Gadgets"`).

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svExportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVEXPORTFORMAT>XML</SVEXPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `export` | Yes |
| `type` | `collection` | Yes |
| `id` | `TSPLStockOfGroup` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tdlmessage": [
    {
      "definitions": [
        {
          "metadata": {
            "name": "TSPLStockOfGroup",
            "type": "Collection"
          },
          "attributes": [
            {
              "Type": "StockItem"
            },
            {
              "Child Of": "\"Gadgets\""
            },
            {
              "Native Method": "Name, Parent, ClosingBalance, ClosingValue, BaseUnits"
            }
          ]
        }
      ]
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Collection</TYPE>
        <ID>TSPLStockOfGroup</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
<TDL>
<TDLMESSAGE>
  <COLLECTION NAME="TSPLStockOfGroup" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
   <TYPE>StockItem</TYPE>
   <CHILDOF>&quot;Gadgets&quot;</CHILDOF>
   <NATIVEMETHOD>Name, Parent, ClosingBalance, ClosingValue, BaseUnits</NATIVEMETHOD>
  </COLLECTION>
</TDLMESSAGE>
</TDL>
        </DESC>
    </BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: export" \
  -H "type: collection" \
  -H "id: TSPLStockOfGroup" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟡 Illustrative (shape per Tally's published collection sample; values invented)):

```json
{
    "status": "1",
    "data": {
        "metadata": {
            "is_mst_dep_type": true,
            "mst_dep_type": "512"
        },
        "collection": [
            {
                "metadata": {
                    "type": "Stock Item",
                    "name": "Apple MacBook Pro Laptop",
                    "reservedname": ""
                },
                "parent": {
                    "type": "String",
                    "value": "Gadgets"
                },
                "closingbalance": {
                    "type": "Quantity",
                    "value": " 4 nos"
                },
                "closingvalue": {
                    "type": "Amount",
                    "value": "-600000.00"
                },
                "baseunits": {
                    "type": "String",
                    "value": "nos"
                },
                "languagename": [
                    {
                        "name": [
                            {
                                "metadata": true,
                                "type": "String"
                            },
                            "Apple MacBook Pro Laptop"
                        ],
                        "languageid": {
                            "type": "Number",
                            "value": " 1033"
                        }
                    }
                ]
            },
            {
                "metadata": {
                    "type": "Stock Item",
                    "name": "Hp Pavilion 14 Laptop",
                    "reservedname": ""
                },
                "parent": {
                    "type": "String",
                    "value": "Gadgets"
                },
                "closingbalance": {
                    "type": "Quantity",
                    "value": " 6 nos"
                },
                "closingvalue": {
                    "type": "Amount",
                    "value": "-540000.00"
                },
                "baseunits": {
                    "type": "String",
                    "value": "nos"
                },
                "languagename": [
                    {
                        "name": [
                            {
                                "metadata": true,
                                "type": "String"
                            },
                            "Hp Pavilion 14 Laptop"
                        ],
                        "languageid": {
                            "type": "Number",
                            "value": " 1033"
                        }
                    }
                ]
            }
        ]
    }
}
```

**Success — XML** (🟡 Illustrative):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DESC>
        </DESC>
        <DATA>
            <COLLECTION>
                <STOCKITEM NAME="Apple MacBook Pro Laptop" RESERVEDNAME="">
                    <PARENT TYPE="String">Gadgets</PARENT>
                    <CLOSINGBALANCE TYPE="Quantity"> 4 nos</CLOSINGBALANCE>
                    <CLOSINGVALUE TYPE="Amount">-600000.00</CLOSINGVALUE>
                    <BASEUNITS TYPE="String">nos</BASEUNITS>
                    <LANGUAGENAME.LIST>
                        <NAME.LIST TYPE="String">
                            <NAME>Apple MacBook Pro Laptop</NAME>
                        </NAME.LIST>
                        <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
                    </LANGUAGENAME.LIST>
                </STOCKITEM>
                <STOCKITEM NAME="Hp Pavilion 14 Laptop" RESERVEDNAME="">
                    <PARENT TYPE="String">Gadgets</PARENT>
                    <CLOSINGBALANCE TYPE="Quantity"> 6 nos</CLOSINGBALANCE>
                    <CLOSINGVALUE TYPE="Amount">-540000.00</CLOSINGVALUE>
                    <BASEUNITS TYPE="String">nos</BASEUNITS>
                    <LANGUAGENAME.LIST>
                        <NAME.LIST TYPE="String">
                            <NAME>Hp Pavilion 14 Laptop</NAME>
                        </NAME.LIST>
                        <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
                    </LANGUAGENAME.LIST>
                </STOCKITEM>
            </COLLECTION>
        </DATA>
    </BODY>
</ENVELOPE>
```

#### Error Responses

- **Collection name mismatch** (🟡 Illustrative): if the `id` header / `<ID>` does not match a default collection or a definition in `tdlmessage`, Tally returns an error instead of data. TDL names ignore case and spaces (`TSPL All Payment Vouchers` = `TSPLAllPaymentVouchers`), but any other spelling difference breaks the match.
- **Invalid TDL** (bad attribute or formula): Tally may show an error dialog on the Tally screen and return nothing useful. Validate TDL in the Explorer before shipping it.
- **Empty result:** a valid request that matches nothing returns `status: "1"` with an empty `collection` (`<COLLECTION/>`).
- [Common errors](#110-common-error-responses) apply.

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `export` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `collection` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `TSPLStockOfGroup` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svExportFormat]` | `<STATICVARIABLES><SVEXPORTFORMAT>` | Yes (export) | String | `jsonex` | Response format: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `tdlmessage[]` | `<TDL><TDLMESSAGE>` | Cond. | Array<Object> |  | Inline TDL definitions (Collection / Report modification / System Formulae) that Tally loads before executing the request. |
| `tdlmessage[].definitions[]` | `<COLLECTION …>` | Cond. | Array<Object> |  | List of TDL definitions inside `tdlmessage`. |
| `tdlmessage[].definitions[].metadata.name` | `NAME` attribute | Yes | String | `TSPLStockOfGroup` | Definition name. For a Collection it must match the `id` header / `<ID>`. TDL names are case- and space-insensitive. |
| `tdlmessage[].definitions[].metadata.type` | element name | Yes | String | `Collection` | Definition kind: `Collection`, `Report`, or `System`. |
| `tdlmessage[].definitions[].attributes[].Type` | `<TYPE>` | Yes | String | `StockItem` | Object type the collection gathers: `Ledger`, `Group`, `StockItem`, `StockGroup`, `Unit`, or `Vouchers:VoucherType` (vouchers of a voucher type). |
| `tdlmessage[].definitions[].attributes[].Child Of` | `<CHILDOF>` | No | String (TDL expr) | `"Gadgets"` | Restricts the collection to children of a parent. Accepts a literal (`"Gadgets"`) or a system-name function such as `$$GroupBank`, `$$GroupCurrentAssets`, `$$VchTypePayment`. |
| `tdlmessage[].definitions[].attributes[].Native Method` | `<NATIVEMETHOD>` | Yes | String (CSV) | `Name, Parent, ClosingBalance, ClosingVal…` | Comma-separated methods to fetch for every object in the collection. |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Fetch only closingbalance, closingrate, closingvalue from the stockitems belonging to Gadgets | Fetch only relevant methods in the collection | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/stock-item/pull-stock-items-of-stock-group/json/TaskStockItemofGadgetsJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/stock-item/pull-stock-items-of-stock-group/xml/TaskStockItemofGadgetsXML.txt) |
| Fetch Name, Parent, openingbalance and closing balance for stockitems of stock group ‘Coffee’ | Change Child of attribute. Fetch relevant methods | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/stock-item/pull-stock-items-of-stock-group/json/TaskStockItemofLaptopsJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/stock-item/pull-stock-items-of-stock-group/xml/TaskStockItemofLaptopsXML.txt) |

## 3.2 Stock Group

### 3.2.0 Stock Group — Overview & Field Reference

> 🟢 Official: converted from the Explorer's "About Stock Group" page.

In TallyPrime, a Stock Group is a master used to categorize stockitems that share similar characteristics. It helps organize stock items and generate inventory reports by Group.

Instead of listing all products individually, businesses group them into logical groups. Stock groups can also have parent and sub-groups.

Example

```text
Clothing (Main Stock group)
├── Shirts (sub stockgroup)
│   └── Black Formal Shirt (Stock item)
├── Jeans (sub stockgroup)
│   └── Blue Denim Jeans (Stock item)
└── Jackets (sub stockgroup)
    └── Leather Jacket (Stock item)
```

In integration scenarios, Stock Groups are used to

- Maintain Product Categorization as per the External system
- Enable Group-Wise Inventory Reports
- Maintain Consistency Between Systems

Understanding the structure and required fields of a stock Group is recommended as it plays an important role in inventory management.

A Stock Group has over 100+ tags; however, all tags are not mandatory. The required tags depend on the nature of the stock group.

**For basic Stock Group creation, usually the following is sufficient:**

Applicable for XML Format only

| Tag/Attribute | Identifier | Mandatory | Data Type | Explanation |
|---|---|---|---|---|
| stock group | Tag | Yes | String | Specifies the Type of the Object. In this case its ‘Stock Group’ |
| name | Attribute of StockGroup Tag | Yes | String | The name of the Stock Group. This uniquely identifies the Stock Group within the company |

Applicable for JSON Format only

| Tag | Mandatory | Data Type | Explanation |
|---|---|---|---|
| metadata | Yes | Object | This contains the metadata information that specifies the type of object and name of the stock group |
| type | Yes | String | Specifies the Type of the Object. In this case its ‘Stock Group’ |
| name | Yes | String | The name of the Stock Group. This uniquely identifies the Stock Group within the company |

Applicable for both XML and JSON formats

| Tag | Mandatory | Data Type | Explanation |
|---|---|---|---|
| name | Yes | String | The name of the Stock Group. This uniquely identifies the Stock Group within the company. |

**Frequently used tags**

| Tag | Mandatory | Data Type | Explanation |
|---|---|---|---|
| parent | No | String | Specifies the Parent Stock Group to which the stockgroup belongs. In absence of this tag, ‘Primary’ is set as value for this tag by the system. |
| isaddable | No | Logical | Specifies if all the child stock items can be added. It will aggregate closing balance of all its child items if enabled and the items have same units.   By default, the value is Yes. |

**The below tags are system generated and is just for your information. These tags cannot be overridden or changed.**

| Tag | Nature of Tag | Data Type | Explanation |
|---|---|---|---|
| guid | System Generated | String | Unique identifier generated by Tally for the stock group. |
| alterid | System Generated | Number | Internal version identifier used when a stock group is modified. |
| objectupdateaction | System Generated | String | Specifies the action performed (Create, Alter, Delete). |

**Sample — XML Format**

```xml
<STOCKGROUP NAME="Gadgets">
      <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000e69</GUID>
      <PARENT>Applications</PARENT>
      <OBJECTUPDATEACTION>Create</OBJECTUPDATEACTION>
      <ISADDABLE>Yes</ISADDABLE>
      <ALTERID> 7780</ALTERID>
      <NAME>Gadgets</NAME>
</STOCKGROUP>

```

**Sample — JSON Format**

```json
{
  "metadata": {
    "type": "Stock Group",
    "name": "Gadgets"
  },
  "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000e69",
  "parent": "Applications",
  "isaddable": true,
  "alterid": " 7780",
  "name": "Gadgets"
}

```

### 3.2.1 Create a Stock Group

> Explorer id: `create-stock-group` · Kind: **import** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#create-stock-group)

#### Description

The Create action is used to add a new StockGroup to the company data in Tally by providing details such as the StockGroup name.

**Integration use:** Mirror your product categories as stock groups for group-wise inventory reporting.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svMstImportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `import` | Yes |
| `type` | `data` | Yes |
| `id` | `All Masters` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svMstImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Stock Group",
        "action": "create",
        "name": "Tea Products"
      },
      "name": "Tea Products"
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>All Masters</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
 <STOCKGROUP NAME="Tea Products" Action="Create">
  <NAME>Tea Products</NAME>
 </STOCKGROUP>
</TALLYMESSAGE>
</DESC>
</BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: import" \
  -H "type: data" \
  -H "id: All Masters" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟢 Official shape: Tally's published master import response):

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 1,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 0
        }
    }
}
```

**Success — XML** (🔵 Observed: captured from a live TallyPrime in `docs/Tally_Vouchers_Integration_Guide.md`; `CMPINFO` truncated):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <CREATED>1</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>0</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
        <DESC>
            <CMPINFO>
                <COMPANY>0</COMPANY>
                <GROUP>0</GROUP>
                <LEDGER>95</LEDGER>
                <!-- … one count element per object type (COSTCENTRE, GODOWN, STOCKITEM, UNIT, VOUCHERTYPE, …) … -->
                <VOUCHER>39</VOUCHER>
            </CMPINFO>
        </DESC>
    </BODY>
</ENVELOPE>
```

Check `created` = 1 **and** `errors` + `exceptions` = 0. `status: "1"` only means the request was processed, not that the record was accepted.

#### Error Responses

**Record-level failure:** `Stock Group 'Beverages' does not exist!`. Source: 🔵 Observed.

Cause: Example: `parent` sent as "Beverages", which does not exist in the company. Create or verify the parent first.

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <LINEERROR>Stock Group &apos;Beverages&apos; does not exist!</LINEERROR>
                <CREATED>0</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>1</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
    </BODY>
</ENVELOPE>
```

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 1
        }
    }
}
```

> In JSON the failure shows up as non-zero `errors` / `exceptions` counts. Tally does not document the JSON key that carries the line-error text, so log the raw response body; this repo's parser (`parse_tally_response_metrics`) also checks `import_result.line_error`.

See also [Common errors](#110-common-error-responses) (company not loaded, unknown request, Tally not running).

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `import` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `data` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `All Masters` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svMstImportFormat]` | `<STATICVARIABLES><SVMSTIMPORTFORMAT>` | Yes (master import) | String | `jsonex` | Import format of masters: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `tallymessage[]` | `<TALLYMESSAGE>` | Yes | Array<Object> |  | The objects to import (masters or vouchers). One request can carry many objects. |
| `tallymessage[].metadata` | `<STOCKGROUP …>` attributes | Yes | Object |  | Object identity block: type, name/identifiers and action. |
| `tallymessage[].metadata.type` | element name `<STOCKGROUP>` | Yes | String | `Stock Group` | Object type: `Ledger`, `Group`, `Stock Item`, `Stock Group`, `Unit`, `Voucher`. |
| `tallymessage[].metadata.action` | `ACTION` attribute | Yes | String | `create` | `Create`, `Alter`, or `Delete` (case-insensitive). |
| `tallymessage[].metadata.name` | `NAME` attribute | Yes (masters) | String | `Tea Products` | Name of the master; the key Tally matches on for Alter/Delete. |
| `tallymessage[].name` | `<STOCKGROUP>/NAME` | Yes | String | `Tea Products` | Object name; unique within the company for masters. |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Create a new StockGroup ‘Instant Beverages’ | Change tag values: NAME | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/stock-group/create/json/TaskCreateStockGroupInstantBeveragesJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/stock-group/create/xml/TaskCreateStockGroupInstantBeveragesXML.txt) |

### 3.2.2 Alter a Stock Group

> Explorer id: `alter-stock-group` · Kind: **import** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#alter-stock-group)

#### Description

The Alter action is used to modify the details of an existing stockgroup in Tally. You can update stockgroup information by sending a request with the stockgroup name and the storages that need to be changed. Once processed successfully, the stockgroup is updated with the specified changes.

**Integration use:** Update category attributes (parent, addability) when the category tree changes upstream.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svMstImportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `import` | Yes |
| `type` | `data` | Yes |
| `id` | `All Masters` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svMstImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Stock Group",
        "action": "Alter",
        "name": "Tea Products"
      },
      "name": "Tea Products",
      "isaddable": "Yes"
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>All Masters</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
 <STOCKGROUP NAME="Tea Products" Action="Alter">
  <NAME>Tea Products</NAME>
  <ISADDABLE>Yes</ISADDABLE>
 </STOCKGROUP>
</TALLYMESSAGE>
</DESC>
</BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: import" \
  -H "type: data" \
  -H "id: All Masters" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟢 Official shape: Tally's published master import response):

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 1,
            "deleted": 0,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 0
        }
    }
}
```

**Success — XML** (🔵 Observed: captured from a live TallyPrime in `docs/Tally_Vouchers_Integration_Guide.md`; `CMPINFO` truncated):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <CREATED>0</CREATED>
                <ALTERED>1</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>0</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
        <DESC>
            <CMPINFO>
                <COMPANY>0</COMPANY>
                <GROUP>0</GROUP>
                <LEDGER>95</LEDGER>
                <!-- … one count element per object type (COSTCENTRE, GODOWN, STOCKITEM, UNIT, VOUCHERTYPE, …) … -->
                <VOUCHER>39</VOUCHER>
            </CMPINFO>
        </DESC>
    </BODY>
</ENVELOPE>
```

Check `altered` = 1 **and** `errors` + `exceptions` = 0. `status: "1"` only means the request was processed, not that the record was accepted.

#### Error Responses

**Record-level failure:** `Stock Group 'Tea Products' does not exist!`. Source: 🟡 Illustrative.

Cause: Alter matches on `metadata.name` (`NAME` attribute). The name must match an existing master exactly (case-insensitive).

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <LINEERROR>Stock Group &apos;Tea Products&apos; does not exist!</LINEERROR>
                <CREATED>0</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>1</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
    </BODY>
</ENVELOPE>
```

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 1
        }
    }
}
```

> In JSON the failure shows up as non-zero `errors` / `exceptions` counts. Tally does not document the JSON key that carries the line-error text, so log the raw response body; this repo's parser (`parse_tally_response_metrics`) also checks `import_result.line_error`.

See also [Common errors](#110-common-error-responses) (company not loaded, unknown request, Tally not running).

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `import` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `data` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `All Masters` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svMstImportFormat]` | `<STATICVARIABLES><SVMSTIMPORTFORMAT>` | Yes (master import) | String | `jsonex` | Import format of masters: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `tallymessage[]` | `<TALLYMESSAGE>` | Yes | Array<Object> |  | The objects to import (masters or vouchers). One request can carry many objects. |
| `tallymessage[].metadata` | `<STOCKGROUP …>` attributes | Yes | Object |  | Object identity block: type, name/identifiers and action. |
| `tallymessage[].metadata.type` | element name `<STOCKGROUP>` | Yes | String | `Stock Group` | Object type: `Ledger`, `Group`, `Stock Item`, `Stock Group`, `Unit`, `Voucher`. |
| `tallymessage[].metadata.action` | `ACTION` attribute | Yes | String | `Alter` | `Create`, `Alter`, or `Delete` (case-insensitive). |
| `tallymessage[].metadata.name` | `NAME` attribute | Yes (masters) | String | `Tea Products` | Name of the master; the key Tally matches on for Alter/Delete. |
| `tallymessage[].name` | `<STOCKGROUP>/NAME` | Yes | String | `Tea Products` | Object name; unique within the company for masters. |
| `tallymessage[].isaddable` | `<STOCKGROUP>/ISADDABLE` | No | Logical | `Yes` | Group: net Dr/Cr balance shown. Stock group: child item quantities are added up.  |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Alter stock group ‘Instant Beverages’ and set Isaddable to Yes | Change values of Name | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/stock-group/alter/json/TaskAlterStockGroupInstantBeveragesJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/stock-group/alter/xml/TaskAlterStockGroupInstantBeveragesXML.txt) |

### 3.2.3 Delete a Stock Group

> Explorer id: `delete-stock-group` · Kind: **import** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#delete-stock-group)

#### Description

The Delete action is used to Delete a stockgroup from the company data. Any StockGroup, unless not used or referred in stockitems or other masters, can be deleted.

**Integration use:** Remove empty categories.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svMstImportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `import` | Yes |
| `type` | `data` | Yes |
| `id` | `All Masters` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svMstImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Stock Group",
        "action": "Delete",
        "name": "Tea Products"
      }
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>All Masters</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
 <STOCKGROUP NAME="Tea Products" Action="Delete">
  <NAME>Tea Products</NAME>
 </STOCKGROUP>
</TALLYMESSAGE>
</DESC>
</BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: import" \
  -H "type: data" \
  -H "id: All Masters" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟢 Official shape: Tally's published master import response):

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 0,
            "deleted": 1,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 0
        }
    }
}
```

**Success — XML** (🔵 Observed: captured from a live TallyPrime in `docs/Tally_Vouchers_Integration_Guide.md`; `CMPINFO` truncated):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <CREATED>0</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>1</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>0</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
        <DESC>
            <CMPINFO>
                <COMPANY>0</COMPANY>
                <GROUP>0</GROUP>
                <LEDGER>95</LEDGER>
                <!-- … one count element per object type (COSTCENTRE, GODOWN, STOCKITEM, UNIT, VOUCHERTYPE, …) … -->
                <VOUCHER>39</VOUCHER>
            </CMPINFO>
        </DESC>
    </BODY>
</ENVELOPE>
```

Check `deleted` = 1 **and** `errors` + `exceptions` = 0. `status: "1"` only means the request was processed, not that the record was accepted.

#### Error Responses

**Record-level failure:** `Cannot be deleted!`. Source: 🟡 Illustrative (message observed for Units in this repo).

Cause: The stock group is still referenced (by vouchers, child masters, stock items or compound units). Remove the references first, or archive instead of deleting.

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <LINEERROR>Cannot be deleted!</LINEERROR>
                <CREATED>0</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>1</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
    </BODY>
</ENVELOPE>
```

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 1
        }
    }
}
```

> In JSON the failure shows up as non-zero `errors` / `exceptions` counts. Tally does not document the JSON key that carries the line-error text, so log the raw response body; this repo's parser (`parse_tally_response_metrics`) also checks `import_result.line_error`.

See also [Common errors](#110-common-error-responses) (company not loaded, unknown request, Tally not running).

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `import` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `data` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `All Masters` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svMstImportFormat]` | `<STATICVARIABLES><SVMSTIMPORTFORMAT>` | Yes (master import) | String | `jsonex` | Import format of masters: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `tallymessage[]` | `<TALLYMESSAGE>` | Yes | Array<Object> |  | The objects to import (masters or vouchers). One request can carry many objects. |
| `tallymessage[].metadata` | `<STOCKGROUP …>` attributes | Yes | Object |  | Object identity block: type, name/identifiers and action. |
| `tallymessage[].metadata.type` | element name `<STOCKGROUP>` | Yes | String | `Stock Group` | Object type: `Ledger`, `Group`, `Stock Item`, `Stock Group`, `Unit`, `Voucher`. |
| `tallymessage[].metadata.action` | `ACTION` attribute | Yes | String | `Delete` | `Create`, `Alter`, or `Delete` (case-insensitive). |
| `tallymessage[].metadata.name` | `NAME` attribute | Yes (masters) | String | `Tea Products` | Name of the master; the key Tally matches on for Alter/Delete. |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Delete the stockgroup ‘Instant Beverages’ | Change tag values: NAME | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/stock-group/delete/json/TaskDeleteStockGroupInstantBeveragesJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/stock-group/delete/xml/TaskDeleteStockGroupInstantBeveragesXML.txt) |

### 3.2.4 Pull a Stock Group

> Explorer id: `pull-stock-group` · Kind: **object** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#pull-stock-group)

#### Description

Details about a single stockgroup can be pulled using the Name of the stockgroup which is the identifier. All the first level methods from stockgroup object can be fetched.

**Integration use:** Read one category's aggregate balances.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svExportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVEXPORTFORMAT>XML</SVEXPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `export` | Yes |
| `type` | `object` | Yes |
| `subtype` | `Stock Group` | Cond. |
| `id` | `Laptops` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<SUBTYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonEx"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "fetch_list": [
    "Name",
    "Parent",
    "Opening Balance",
    "Closing Balance"
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Object</TYPE>
        <SUBTYPE>Stock Group</SUBTYPE>
        <ID TYPE="Name">Laptops</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
            <FETCHLIST>
                <FETCH>Name</FETCH>
                <FETCH>Parent</FETCH>
                <FETCH>Opening Balance</FETCH>
                <FETCH>Closing Balance</FETCH>
            </FETCHLIST>
        </DESC>
    </BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: export" \
  -H "type: object" \
  -H "subtype: Stock Group" \
  -H "id: Laptops" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟡 Illustrative: structure per Tally's published object-export sample `{type, value}` per method; values invented):

```json
{
    "status": "1",
    "tallymessage": [
        {
            "metadata": {
                "type": "Stock Group",
                "name": "Laptops",
                "reservedname": "",
                "id": "1042",
                "reqname": "Laptops"
            },
            "parent": {
                "type": "String",
                "value": "Gadgets"
            },
            "openingbalance": {
                "type": "Quantity",
                "value": " 10 nos"
            },
            "closingbalance": {
                "type": "Quantity",
                "value": " 7 nos"
            },
            "languagename": [
                {
                    "name": [
                        {
                            "metadata": true,
                            "type": "String"
                        },
                        "Laptops"
                    ],
                    "languageid": {
                        "type": "Number",
                        "value": " 1033"
                    }
                }
            ]
        }
    ]
}
```

**Success — XML** (🟡 Illustrative: TYPE-attributed fields mirroring the JSON):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DESC>
        </DESC>
        <DATA>
            <TALLYMESSAGE>
                <STOCKGROUP NAME="Laptops" RESERVEDNAME="">
                    <PARENT TYPE="String">Gadgets</PARENT>
                    <OPENINGBALANCE TYPE="Quantity"> 10 nos</OPENINGBALANCE>
                    <CLOSINGBALANCE TYPE="Quantity"> 7 nos</CLOSINGBALANCE>
                    <LANGUAGENAME.LIST>
                        <NAME.LIST TYPE="String">
                            <NAME>Laptops</NAME>
                        </NAME.LIST>
                        <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
                    </LANGUAGENAME.LIST>
                </STOCKGROUP>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>
```

#### Error Responses

- **Object not found / wrong `subtype`** (🟡 Illustrative): Tally returns no object (an empty `tallymessage` / `<TALLYMESSAGE/>`) or `status` `0`. Treat a missing object, not just the status flag, as "not found".
- **Multilingual names:** send the name base64-encoded in `id-encoded` (with `content-type: application/json;charset=utf-8`) instead of `id`.
- [Common errors](#110-common-error-responses) apply (company not loaded, Tally not running).

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `export` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `object` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: subtype` | `<HEADER><SUBTYPE>` | Cond. | String | `Stock Group` | Object type for `type: Object` (e.g. `Ledger`, `StockItem`). |
| `header: id` | `<HEADER><ID>` | Yes | String | `Laptops` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svExportFormat]` | `<STATICVARIABLES><SVEXPORTFORMAT>` | Yes (export) | String | `jsonEx` | Response format: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `fetch_list[]` | `<FETCHLIST><FETCH>` | No | Array<String> | `Name, Parent, Opening Balance, Closing B…` | Methods/storages to return for an Object export (`type: object`). Omit to get the default set. |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Pull only opening balance ,closingbalance, isaddable details of the stock Group ‘Gadgets’ | Change the HTTP Header value of 'id'. Fetch relevant methods. | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/stock-group/pull/json/TaskPullStockGroupGadgetsJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/stock-group/pull/xml/TaskPullStockGroupGadgetsXML.txt) |

### 3.2.5 Pull All Stock Groups

> Explorer id: `pull-all-stock-groups` · Kind: **collection** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#pull-all-stock-groups)

#### Description

Details about multiple stockgroups can be pulled using a TDL collection definition, which can already exist in the default source code or sent via the payload. TDL collection definition has type attribute that specifies the type of object that is grouped and fetch attribute that fetches the required methods.

**Integration use:** Mirror the stock-group tree for mapping and validation.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svExportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVEXPORTFORMAT>XML</SVEXPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `export` | Yes |
| `type` | `collection` | Yes |
| `id` | `Stock Group` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Collection</TYPE>
        <ID>StockGroup</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
    </BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: export" \
  -H "type: collection" \
  -H "id: Stock Group" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟡 Illustrative (shape per Tally's published collection sample; values invented)):

```json
{
    "status": "1",
    "data": {
        "metadata": {
            "is_mst_dep_type": true,
            "mst_dep_type": "<type-code>"
        },
        "collection": [
            {
                "metadata": {
                    "type": "Stock Group",
                    "name": "Coffee",
                    "reservedname": ""
                },
                "parent": {
                    "type": "String",
                    "value": "\u0004 Primary"
                },
                "languagename": [
                    {
                        "name": [
                            {
                                "metadata": true,
                                "type": "String"
                            },
                            "Coffee"
                        ],
                        "languageid": {
                            "type": "Number",
                            "value": " 1033"
                        }
                    }
                ]
            },
            {
                "metadata": {
                    "type": "Stock Group",
                    "name": "Gadgets",
                    "reservedname": ""
                },
                "parent": {
                    "type": "String",
                    "value": "\u0004 Primary"
                },
                "languagename": [
                    {
                        "name": [
                            {
                                "metadata": true,
                                "type": "String"
                            },
                            "Gadgets"
                        ],
                        "languageid": {
                            "type": "Number",
                            "value": " 1033"
                        }
                    }
                ]
            }
        ]
    }
}
```

**Success — XML** (🟡 Illustrative):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DESC>
        </DESC>
        <DATA>
            <COLLECTION>
                <STOCKGROUP NAME="Coffee" RESERVEDNAME="">
                    <PARENT TYPE="String">&#4; Primary</PARENT>
                    <LANGUAGENAME.LIST>
                        <NAME.LIST TYPE="String">
                            <NAME>Coffee</NAME>
                        </NAME.LIST>
                        <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
                    </LANGUAGENAME.LIST>
                </STOCKGROUP>
                <STOCKGROUP NAME="Gadgets" RESERVEDNAME="">
                    <PARENT TYPE="String">&#4; Primary</PARENT>
                    <LANGUAGENAME.LIST>
                        <NAME.LIST TYPE="String">
                            <NAME>Gadgets</NAME>
                        </NAME.LIST>
                        <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
                    </LANGUAGENAME.LIST>
                </STOCKGROUP>
            </COLLECTION>
        </DATA>
    </BODY>
</ENVELOPE>
```

#### Error Responses

- **Collection name mismatch** (🟡 Illustrative): if the `id` header / `<ID>` does not match a default collection or a definition in `tdlmessage`, Tally returns an error instead of data. TDL names ignore case and spaces (`TSPL All Payment Vouchers` = `TSPLAllPaymentVouchers`), but any other spelling difference breaks the match.
- **Invalid TDL** (bad attribute or formula): Tally may show an error dialog on the Tally screen and return nothing useful. Validate TDL in the Explorer before shipping it.
- **Empty result:** a valid request that matches nothing returns `status: "1"` with an empty `collection` (`<COLLECTION/>`).
- [Common errors](#110-common-error-responses) apply.

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `export` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `collection` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `Stock Group` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svExportFormat]` | `<STATICVARIABLES><SVEXPORTFORMAT>` | Yes (export) | String | `jsonex` | Response format: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |

### 3.2.6 Pull Stock Group With Zero Balance

> Explorer id: `pull-stock-group-zero-balance` · Kind: **collection** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#pull-stock-group-zero-balance)

#### Description

Details about multiple stockgroups based on any filter can be pulled using a TDL collection definition. When the TDL collection in default source code is not serving the requirement, a new TDL collection to fetch required information can be used. The TDL collection definition has type attribute that specifies the type of object that is grouped, child of attribute specifies the name of the parent and fetch attribute that fetches the required methods, Filter attribute that specifies any condition based on which the objects should be gathered.

**Integration use:** Server-side filtering with a TDL formula. The same technique filters any collection (zero stock, negative balances, date ranges).

**Notes:**

- The filter name in the collection (`TSPL Zero Closing`) and the formula definition (`TSPL ZeroClosing`) match because TDL names ignore spaces.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svExportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVEXPORTFORMAT>XML</SVEXPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `export` | Yes |
| `type` | `collection` | Yes |
| `id` | `TSPL Stock Group ZeroBal` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tdlmessage": [
    {
      "definitions": [
        {
          "metadata": {
            "name": "TSPL Stock Group ZeroBal",
            "type": "Collection"
          },
          "attributes": [
            {
              "Type": "StockGroup"
            },
            {
              "Native Method": "Name, Parent, Openingbalance, ClosingBalance"
            },
            {
              "Filters": "TSPL Zero Closing"
            }
          ]
        },
        {
          "metadata": {
            "name": "TSPL ZeroClosing",
            "type": "System",
            "sys_type": "Formulae"
          },
          "value": "$ClosingBalance = 0"
        }
      ]
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Collection</TYPE>
        <ID>TSPL Stock Group ZeroBal</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
            <TDL>
<TDLMESSAGE>
  <COLLECTION NAME="TSPL Stock Group ZeroBal" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
   <TYPE>StockGroup</TYPE>
   <NATIVEMETHOD>Name, Parent, Openingbalance, ClosingBalance</NATIVEMETHOD>
   <FILTERS>TSPL Zero Closing</FILTERS>
  </COLLECTION>
  <SYSTEM TYPE="Formulae" NAME="TSPL ZeroClosing" ISMODIFY="No" ISFIXED="No" ISINTERNAL="No">$ClosingBalance = 0  </SYSTEM>
</TDLMESSAGE>
</TDL>
        </DESC>
    </BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: export" \
  -H "type: collection" \
  -H "id: TSPL Stock Group ZeroBal" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟡 Illustrative (shape per Tally's published collection sample; values invented)):

```json
{
    "status": "1",
    "data": {
        "metadata": {
            "is_mst_dep_type": true,
            "mst_dep_type": "<type-code>"
        },
        "collection": [
            {
                "metadata": {
                    "type": "Stock Group",
                    "name": "Instant Beverages",
                    "reservedname": ""
                },
                "parent": {
                    "type": "String",
                    "value": "Coffee"
                },
                "openingbalance": {
                    "type": "Quantity",
                    "value": ""
                },
                "closingbalance": {
                    "type": "Quantity",
                    "value": ""
                },
                "languagename": [
                    {
                        "name": [
                            {
                                "metadata": true,
                                "type": "String"
                            },
                            "Instant Beverages"
                        ],
                        "languageid": {
                            "type": "Number",
                            "value": " 1033"
                        }
                    }
                ]
            },
            {
                "metadata": {
                    "type": "Stock Group",
                    "name": "Stationery",
                    "reservedname": ""
                },
                "parent": {
                    "type": "String",
                    "value": "\u0004 Primary"
                },
                "openingbalance": {
                    "type": "Quantity",
                    "value": ""
                },
                "closingbalance": {
                    "type": "Quantity",
                    "value": ""
                },
                "languagename": [
                    {
                        "name": [
                            {
                                "metadata": true,
                                "type": "String"
                            },
                            "Stationery"
                        ],
                        "languageid": {
                            "type": "Number",
                            "value": " 1033"
                        }
                    }
                ]
            }
        ]
    }
}
```

**Success — XML** (🟡 Illustrative):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DESC>
        </DESC>
        <DATA>
            <COLLECTION>
                <STOCKGROUP NAME="Instant Beverages" RESERVEDNAME="">
                    <PARENT TYPE="String">Coffee</PARENT>
                    <OPENINGBALANCE TYPE="Quantity"></OPENINGBALANCE>
                    <CLOSINGBALANCE TYPE="Quantity"></CLOSINGBALANCE>
                    <LANGUAGENAME.LIST>
                        <NAME.LIST TYPE="String">
                            <NAME>Instant Beverages</NAME>
                        </NAME.LIST>
                        <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
                    </LANGUAGENAME.LIST>
                </STOCKGROUP>
                <STOCKGROUP NAME="Stationery" RESERVEDNAME="">
                    <PARENT TYPE="String">&#4; Primary</PARENT>
                    <OPENINGBALANCE TYPE="Quantity"></OPENINGBALANCE>
                    <CLOSINGBALANCE TYPE="Quantity"></CLOSINGBALANCE>
                    <LANGUAGENAME.LIST>
                        <NAME.LIST TYPE="String">
                            <NAME>Stationery</NAME>
                        </NAME.LIST>
                        <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
                    </LANGUAGENAME.LIST>
                </STOCKGROUP>
            </COLLECTION>
        </DATA>
    </BODY>
</ENVELOPE>
```

#### Error Responses

- **Collection name mismatch** (🟡 Illustrative): if the `id` header / `<ID>` does not match a default collection or a definition in `tdlmessage`, Tally returns an error instead of data. TDL names ignore case and spaces (`TSPL All Payment Vouchers` = `TSPLAllPaymentVouchers`), but any other spelling difference breaks the match.
- **Invalid TDL** (bad attribute or formula): Tally may show an error dialog on the Tally screen and return nothing useful. Validate TDL in the Explorer before shipping it.
- **Empty result:** a valid request that matches nothing returns `status: "1"` with an empty `collection` (`<COLLECTION/>`).
- [Common errors](#110-common-error-responses) apply.

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `export` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `collection` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `TSPL Stock Group ZeroBal` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svExportFormat]` | `<STATICVARIABLES><SVEXPORTFORMAT>` | Yes (export) | String | `jsonex` | Response format: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `tdlmessage[]` | `<TDL><TDLMESSAGE>` | Cond. | Array<Object> |  | Inline TDL definitions (Collection / Report modification / System Formulae) that Tally loads before executing the request. |
| `tdlmessage[].definitions[]` | `<COLLECTION …>` | Cond. | Array<Object> |  | List of TDL definitions inside `tdlmessage`. |
| `tdlmessage[].definitions[].metadata.name` | `NAME` attribute | Yes | String | `TSPL Stock Group ZeroBal` | Definition name. For a Collection it must match the `id` header / `<ID>`. TDL names are case- and space-insensitive. |
| `tdlmessage[].definitions[].metadata.type` | element name | Yes | String | `Collection` | Definition kind: `Collection`, `Report`, or `System`. |
| `tdlmessage[].definitions[].attributes[].Type` | `<TYPE>` | Yes | String | `StockGroup` | Object type the collection gathers: `Ledger`, `Group`, `StockItem`, `StockGroup`, `Unit`, or `Vouchers:VoucherType` (vouchers of a voucher type). |
| `tdlmessage[].definitions[].attributes[].Native Method` | `<NATIVEMETHOD>` | Yes | String (CSV) | `Name, Parent, Openingbalance, ClosingBal…` | Comma-separated methods to fetch for every object in the collection. |
| `tdlmessage[].definitions[].attributes[].Filters` | `<FILTERS>` | No | String | `TSPL Zero Closing` | Name of a System Formula used to filter the collection server-side. |
| `tdlmessage[].definitions[].metadata.sys_type` | `TYPE` attribute | Cond. | String | `Formulae` | For `type: System` only. `Formulae` declares named formulae used by `Filters`. |
| `tdlmessage[].definitions[].value` | element text | Cond. | String (TDL expr) | `$ClosingBalance = 0` | Body of a System Formula, e.g. `$ClosingBalance = 0`. |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Fetch stock Group details with stockgroups having some/non-Zero closing balance | Change the filter condition | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/stock-group/pull-stock-group-zero-balance/json/TaskStockGroupsWithBalJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/stock-group/pull-stock-group-zero-balance/xml/TaskStockGroupsWithBalXML.txt) |
| Fetch only openingbalance, closing balance, isaddable details from all the stock groups | Remove Filter, Fetch Relevant methods | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/stock-group/pull-stock-group-zero-balance/json/TaskStockGroupsWithFetchJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/stock-group/pull-stock-group-zero-balance/xml/TaskStockGroupsWithFetchXML.txt) |

## 3.3 Units

### 3.3.0 Units — Overview & Field Reference

> 🟢 Official: converted from the Explorer's "About Units" page.

In TallyPrime, Units (Unit of Measure) are masters used to define how the quantity of stock items is measured.

They determine in what measurement a stockitem is stored, purchased, sold, or tracked.

There 2 types of units

- Simple Unit: A single measurement unit. Example: Nos, Kg
- Compound Unit: A combination of two units used together. Example -> Box of 10 Nos , meaning 1 Box = 10 Nos

In Integration Scenarios, Units are created before stockitems so that,

- To Match Units used in the External System
- To Ensure Accurate Quantity Tracking
- To Maintain Consistent Inventory Reporting

Units must exist before stock items are created

Understanding the structure and required fields of a unit is essential as it is required to ensure stockitem quantities can be tracked.

A Unit has over 50+ tags; however, all tags are not mandatory. The required tags depend on the nature of the unit.

**For basic unit creation, usually the following is sufficient:**

Applicable for XML Format only

| Tag/Attribute | Identifier | Mandatory | Data Type | Explanation |
|---|---|---|---|---|
| Unit tag | Tag | Yes | String | Specifies the Type of the Object. In this case its ‘unit’ |
| name attribute | Attribute of Unit Tag | Yes | String | The name of the unit. This uniquely identifies the unit within the company |

Applicable for JSON Format only

| Tag | Mandatory | Data Type | Explanation |
|---|---|---|---|
| metadata | Yes | Object | This contains the metadata information that specifies the type of object and name of the unit |
| type | Yes | String | Specifies the Type of the Object. In this case its ‘unit’ |
| name | Yes | String | The name of the unit. This uniquely identifies the unit within the company |

Applicable for both XML and JSON formats

| Tag | Mandatory | Data Type | Explanation |
|---|---|---|---|
| name | Yes | String | The name of the unit. This uniquely identifies the unit within the company. |
| issimpleunit | Yes | Logical | Yes – Specifies it’s a simple unit  No – Specifies it’s a compound unit |
| baseunits | Yes, Conditional | String | Applicable only for compound unit. i.e when tag issimpleunit is set to No.   Specifies the base unit name for the compound unit. Should be specified along with additionalunits and conversion tags. Example: for a compound unit Kg of 1000 grams, Kg is BaseUnits, grams is additional units and 1000 is conversion |
| additionalunits | Yes, Conditional | String | Applicable only for compound unit. i.e when tag issimpleunit is set to No.   Specifies the additional unit name for the compound unit. Should be specified along with baseunits and conversion tags. Example: for a compound unit Kg of 1000 grams, Kg is BaseUnits, grams is additional units and 1000 is conversion |
| conversion | Yes, Conditional | Number | Applicable only for compound unit. i.e when tag issimpleunit is set to No.   Specifies the conversion factor from base to additional unit. Should be specified along with additionalunits and baseunits tags. Example: for a compound unit Kg of 1000 grams, Kg is BaseUnits, grams is additional units and 1000 is conversion |

**Frequently Used Tags**

| Tag | Mandatory | Data Type | Explanation |
|---|---|---|---|
| originalname | No, Conditional | String | Applicable only for Simple Unit. i.e. issimpleunit is set to Yes.   This tag is to provide formal name for unit |
| decimalplaces | No, Conditional | Number | Applicable only for Simple Unit. i.e. issimpleunit is set to Yes.   This tag is to provide number of decimal places allowed. |

**The below tags are system generated and is just for your information. These tags cannot be overridden or changed.**

| Tag | Nature of Tag | Data Type | Explanation |
|---|---|---|---|
| guid | System Generated | String | Unique identifier generated by Tally for the unit. |
| alterid | System Generated | Number | Internal version identifier used when a unit is modified. |
| objectupdateaction | System Generated | String | Specifies the action performed (Create, Alter, Delete). |

**Sample — XML Format – Simple Unit**

```xml
<UNIT NAME="Kg" >
      <NAME>Kg</NAME>
      <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000ff</GUID>
      <TYPEOFUPDATEACTIVITY>Import</TYPEOFUPDATEACTIVITY>
      <OBJECTUPDATEACTION>Alter</OBJECTUPDATEACTION>
      <ISSIMPLEUNIT>Yes</ISSIMPLEUNIT>
      <ALTERID> 392</ALTERID>
      <DECIMALPLACES> 3</DECIMALPLACES>
</UNIT>

```

**Sample — XML Format – Compound Unit**

```xml
<UNIT NAME="Kg of 1000 Gms" RESERVEDNAME="">
      <NAME>Kg of 1000 Gms</NAME>
      <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000e7f</GUID>
      <OBJECTUPDATEACTION>Create</OBJECTUPDATEACTION>
      <BASEUNITS>Kg</BASEUNITS>
      <ADDITIONALUNITS>Gms</ADDITIONALUNITS>
      <ISSIMPLEUNIT>No</ISSIMPLEUNIT>
      <ALTERID> 7845</ALTERID>
      <CONVERSION> 1000</CONVERSION>
</UNIT>

```

**Sample — JSON Format – Simple Unit**

```json
{
  "metadata": {
    "type": "Unit",
    "name": "Kg"
  },
  "name": "Kg",
  "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000ff",
  "objectupdateaction": "Create",
  "issimpleunit": true,
  "alterid": " 392",
  "decimalplaces": " 3"
}

```

**Sample — JSON Format – Compound Unit**

```json
{
  "metadata": {
    "type": "Unit",
    "name": "Kg of 1000 Gms"
  },
  "name": "Kg of 1000 Gms",
  "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000e7f",
  "objectupdateaction": "Create",
  "baseunits": "Kg",
  "additionalunits": "Gms",
  "issimpleunit": false,
  "alterid": " 7845",
  "conversion": " 1000"
}

```

### 3.3.1 Create a Simple Unit

> Explorer id: `create-simple-unit` · Kind: **import** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#create-simple-unit)

#### Description

The Create action is used to add a new Units (Units of Measurement) to the company data in Tally by providing details such as the Unit Symbol and Formal Name. It is used in the Stock Item Master to ensure accurate tracking, calculation, and reporting of inventory.

**Integration use:** Create units of measure before items. A stock item cannot be quantity-tracked without its base unit existing.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svMstImportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `import` | Yes |
| `type` | `data` | Yes |
| `id` | `All Masters` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svMstImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Unit",
        "action": "create",
        "name": "box"
      },
      "name": "box",
      "originalname": "boxes",
      "issimpleunit": true
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
   <HEADER>
      <VERSION>1</VERSION>
      <TALLYREQUEST>Import</TALLYREQUEST>
      <TYPE>Data</TYPE>
      <ID>All Masters</ID>
   </HEADER>
   <BODY>
      <DESC>
         <STATICVARIABLES>
            <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
            <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
         </STATICVARIABLES>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
 <UNIT NAME="Box" ACTION="Create">
  <NAME>Box</NAME>
  <ISSIMPLEUNIT>Yes</ISSIMPLEUNIT>
  <ORIGINALNAME>Boxes</ORIGINALNAME>
 </UNIT>
</TALLYMESSAGE>
      </DESC>
   </BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: import" \
  -H "type: data" \
  -H "id: All Masters" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟢 Official shape: Tally's published master import response):

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 1,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 0
        }
    }
}
```

**Success — XML** (🔵 Observed: captured from a live TallyPrime in `docs/Tally_Vouchers_Integration_Guide.md`; `CMPINFO` truncated):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <CREATED>1</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>0</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
        <DESC>
            <CMPINFO>
                <COMPANY>0</COMPANY>
                <GROUP>0</GROUP>
                <LEDGER>95</LEDGER>
                <!-- … one count element per object type (COSTCENTRE, GODOWN, STOCKITEM, UNIT, VOUCHERTYPE, …) … -->
                <VOUCHER>39</VOUCHER>
            </CMPINFO>
        </DESC>
    </BODY>
</ENVELOPE>
```

Check `created` = 1 **and** `errors` + `exceptions` = 0. `status: "1"` only means the request was processed, not that the record was accepted.

#### Error Responses

**Record-level failure:** `Unit 'undefined' does not exist!`. Source: 🟡 Illustrative (same message pattern as the observed stock-group error).

Cause: Example: `parent` sent as "undefined", which does not exist in the company. Create or verify the parent first.

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <LINEERROR>Unit &apos;undefined&apos; does not exist!</LINEERROR>
                <CREATED>0</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>1</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
    </BODY>
</ENVELOPE>
```

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 1
        }
    }
}
```

> In JSON the failure shows up as non-zero `errors` / `exceptions` counts. Tally does not document the JSON key that carries the line-error text, so log the raw response body; this repo's parser (`parse_tally_response_metrics`) also checks `import_result.line_error`.

See also [Common errors](#110-common-error-responses) (company not loaded, unknown request, Tally not running).

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `import` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `data` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `All Masters` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svMstImportFormat]` | `<STATICVARIABLES><SVMSTIMPORTFORMAT>` | Yes (master import) | String | `jsonex` | Import format of masters: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `tallymessage[]` | `<TALLYMESSAGE>` | Yes | Array<Object> |  | The objects to import (masters or vouchers). One request can carry many objects. |
| `tallymessage[].metadata` | `<UNIT …>` attributes | Yes | Object |  | Object identity block: type, name/identifiers and action. |
| `tallymessage[].metadata.type` | element name `<UNIT>` | Yes | String | `Unit` | Object type: `Ledger`, `Group`, `Stock Item`, `Stock Group`, `Unit`, `Voucher`. |
| `tallymessage[].metadata.action` | `ACTION` attribute | Yes | String | `create` | `Create`, `Alter`, or `Delete` (case-insensitive). |
| `tallymessage[].metadata.name` | `NAME` attribute | Yes (masters) | String | `box` | Name of the master; the key Tally matches on for Alter/Delete. |
| `tallymessage[].name` | `<UNIT>/NAME` | Yes | String | `box` | Object name; unique within the company for masters. |
| `tallymessage[].originalname` | `<UNIT>/ORIGINALNAME` | No | String | `boxes` | Simple unit formal name (e.g. `Numbers` for `Nos`). Cannot be changed through Alter. |
| `tallymessage[].issimpleunit` | `<UNIT>/ISSIMPLEUNIT` | Yes | Logical | `true` | `Yes`/`true` simple unit, `No`/`false` compound unit. |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Create a new Unit ‘BAG’ with original name ‘BAGS’ | Change tag values: NAME and OriginalName | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/units/create-unit/json/TaskCreateKGUnitJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/units/create-unit/xml/TaskCreateKGUnitXML.txt) |
| Create a new Unit ‘Tons’ with original name ‘Ton’ | Change tag values: NAME and OriginalName | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/units/create-unit/json/TaskCreateunitTonsJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/units/create-unit/xml/TaskCreateUnitTonsXML.txt) |

### 3.3.2 Create a Compound Unit

> Explorer id: `create-compound-unit` · Kind: **import** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#create-compound-unit)

#### Description

The Create action is used to add a new Compound Unit (Units of Measurement) such as 1 BAG = 100 Pkt, to the company data in Tally by providing details such as the Unit Symbol and Formal Name. It is used in the Stock Item Master to ensure accurate tracking, calculation, and reporting of inventory.

**Integration use:** Model pack conversions (e.g. 1 Box = 10 Nos) that your catalogue uses.

**Notes:**

- Both component units (`baseunits`, `additionalunits`) must already exist.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svMstImportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `import` | Yes |
| `type` | `data` | Yes |
| `id` | `All Masters` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svMstImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Unit",
        "action": "create",
        "name": "KG of 1000 gm"
      },
      "name": "KG of 1000 gm",
      "baseunits": "Kg",
      "additionalunits": "gm",
      "issimpleunit": false,
      "conversion": " 1000"
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>All Masters</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
 <UNIT NAME="Kg of 1000 gm" ACTION="Create">
  <NAME>Kg of 1000 gm</NAME>
  <BASEUNITS>Kg</BASEUNITS>
  <ADDITIONALUNITS>gm</ADDITIONALUNITS>
  <ISSIMPLEUNIT>No</ISSIMPLEUNIT>
  <CONVERSION> 1000</CONVERSION>
 </UNIT>
</TALLYMESSAGE>
        </DESC>
    </BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: import" \
  -H "type: data" \
  -H "id: All Masters" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟢 Official shape: Tally's published master import response):

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 1,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 0
        }
    }
}
```

**Success — XML** (🔵 Observed: captured from a live TallyPrime in `docs/Tally_Vouchers_Integration_Guide.md`; `CMPINFO` truncated):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <CREATED>1</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>0</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
        <DESC>
            <CMPINFO>
                <COMPANY>0</COMPANY>
                <GROUP>0</GROUP>
                <LEDGER>95</LEDGER>
                <!-- … one count element per object type (COSTCENTRE, GODOWN, STOCKITEM, UNIT, VOUCHERTYPE, …) … -->
                <VOUCHER>39</VOUCHER>
            </CMPINFO>
        </DESC>
    </BODY>
</ENVELOPE>
```

Check `created` = 1 **and** `errors` + `exceptions` = 0. `status: "1"` only means the request was processed, not that the record was accepted.

#### Error Responses

**Record-level failure:** `Unit 'gm' does not exist!`. Source: 🟡 Illustrative (same message pattern as the observed stock-group error).

Cause: Both component units of a compound unit must exist before the compound unit is created.

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <LINEERROR>Unit &apos;gm&apos; does not exist!</LINEERROR>
                <CREATED>0</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>1</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
    </BODY>
</ENVELOPE>
```

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 1
        }
    }
}
```

> In JSON the failure shows up as non-zero `errors` / `exceptions` counts. Tally does not document the JSON key that carries the line-error text, so log the raw response body; this repo's parser (`parse_tally_response_metrics`) also checks `import_result.line_error`.

See also [Common errors](#110-common-error-responses) (company not loaded, unknown request, Tally not running).

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `import` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `data` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `All Masters` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svMstImportFormat]` | `<STATICVARIABLES><SVMSTIMPORTFORMAT>` | Yes (master import) | String | `jsonex` | Import format of masters: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `tallymessage[]` | `<TALLYMESSAGE>` | Yes | Array<Object> |  | The objects to import (masters or vouchers). One request can carry many objects. |
| `tallymessage[].metadata` | `<UNIT …>` attributes | Yes | Object |  | Object identity block: type, name/identifiers and action. |
| `tallymessage[].metadata.type` | element name `<UNIT>` | Yes | String | `Unit` | Object type: `Ledger`, `Group`, `Stock Item`, `Stock Group`, `Unit`, `Voucher`. |
| `tallymessage[].metadata.action` | `ACTION` attribute | Yes | String | `create` | `Create`, `Alter`, or `Delete` (case-insensitive). |
| `tallymessage[].metadata.name` | `NAME` attribute | Yes (masters) | String | `KG of 1000 gm` | Name of the master; the key Tally matches on for Alter/Delete. |
| `tallymessage[].name` | `<UNIT>/NAME` | Yes | String | `KG of 1000 gm` | Object name; unique within the company for masters. |
| `tallymessage[].baseunits` | `<UNIT>/BASEUNITS` | Rec. / Cond. | String | `Kg` | Stock item: base unit of measure. Compound unit: the first (base) unit. |
| `tallymessage[].additionalunits` | `<UNIT>/ADDITIONALUNITS` | Cond. | String | `gm` | Compound unit / stock item alternate unit. Requires `conversion`. |
| `tallymessage[].issimpleunit` | `<UNIT>/ISSIMPLEUNIT` | Yes | Logical | `false` | `Yes`/`true` simple unit, `No`/`false` compound unit. |
| `tallymessage[].conversion` | `<UNIT>/CONVERSION` | Cond. | Number | `1000` | Conversion factor between base and additional unit (e.g. 1000 for `Kg of 1000 Gms`). |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Create a new Compound Unit ‘1 BAG = 100 Pkt’ | Change tag values: NAME , BASEUNITS, ADDITIONALUNITS, CONVERSION | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/units/create-compound/json/TaskCreateCompoundUnitBAGJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/units/create-compound/xml/TaskCreateCompoundUnitBAGXML.txt) |

### 3.3.3 Alter a Unit

> Explorer id: `alter-unit` · Kind: **import** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#alter-unit)

#### Description

The Alter action is used to modify the details of an existing Unit in Tally. You can update Unit information by sending a request with the Unit name and the storages that need to be changed. Once processed successfully, the Unit is updated with the specified changes.

**Integration use:** Adjust unit precision (decimal places can only be increased, never decreased).

**Notes:**

- Decimal places can only be increased. The unit's formal name (`originalname`) cannot be changed.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svMstImportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `import` | Yes |
| `type` | `data` | Yes |
| `id` | `All Masters` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svMstImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Unit",
        "action": "Alter",
        "name": "box"
      },
      "name": "box",
      "decimalplaces": " 2"
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>All Masters</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
 <UNIT NAME="Box" ACTION="Alter">
  <NAME>Box</NAME>
  <DECIMALPLACES>2</DECIMALPLACES>
 </UNIT>
</TALLYMESSAGE>
        </DESC>
    </BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: import" \
  -H "type: data" \
  -H "id: All Masters" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟢 Official shape: Tally's published master import response):

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 1,
            "deleted": 0,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 0
        }
    }
}
```

**Success — XML** (🔵 Observed: captured from a live TallyPrime in `docs/Tally_Vouchers_Integration_Guide.md`; `CMPINFO` truncated):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <CREATED>0</CREATED>
                <ALTERED>1</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>0</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
        <DESC>
            <CMPINFO>
                <COMPANY>0</COMPANY>
                <GROUP>0</GROUP>
                <LEDGER>95</LEDGER>
                <!-- … one count element per object type (COSTCENTRE, GODOWN, STOCKITEM, UNIT, VOUCHERTYPE, …) … -->
                <VOUCHER>39</VOUCHER>
            </CMPINFO>
        </DESC>
    </BODY>
</ENVELOPE>
```

Check `altered` = 1 **and** `errors` + `exceptions` = 0. `status: "1"` only means the request was processed, not that the record was accepted.

#### Error Responses

**Record-level failure:** `Cannot Decrease Number of Decimals for 'box'!`. Source: 🔵 Observed.

Cause: Decimal places of an existing unit can only be increased. (Changing `originalname` gives `BAD ORIGINAL NAME`.)

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <LINEERROR>Cannot Decrease Number of Decimals for &apos;box&apos;!</LINEERROR>
                <CREATED>0</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>1</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
    </BODY>
</ENVELOPE>
```

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 1
        }
    }
}
```

> In JSON the failure shows up as non-zero `errors` / `exceptions` counts. Tally does not document the JSON key that carries the line-error text, so log the raw response body; this repo's parser (`parse_tally_response_metrics`) also checks `import_result.line_error`.

See also [Common errors](#110-common-error-responses) (company not loaded, unknown request, Tally not running).

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `import` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `data` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `All Masters` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svMstImportFormat]` | `<STATICVARIABLES><SVMSTIMPORTFORMAT>` | Yes (master import) | String | `jsonex` | Import format of masters: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `tallymessage[]` | `<TALLYMESSAGE>` | Yes | Array<Object> |  | The objects to import (masters or vouchers). One request can carry many objects. |
| `tallymessage[].metadata` | `<UNIT …>` attributes | Yes | Object |  | Object identity block: type, name/identifiers and action. |
| `tallymessage[].metadata.type` | element name `<UNIT>` | Yes | String | `Unit` | Object type: `Ledger`, `Group`, `Stock Item`, `Stock Group`, `Unit`, `Voucher`. |
| `tallymessage[].metadata.action` | `ACTION` attribute | Yes | String | `Alter` | `Create`, `Alter`, or `Delete` (case-insensitive). |
| `tallymessage[].metadata.name` | `NAME` attribute | Yes (masters) | String | `box` | Name of the master; the key Tally matches on for Alter/Delete. |
| `tallymessage[].name` | `<UNIT>/NAME` | Yes | String | `box` | Object name; unique within the company for masters. |
| `tallymessage[].decimalplaces` | `<UNIT>/DECIMALPLACES` | No | Number | `2` | Simple unit precision. Can be increased later, never decreased. |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Alter a Simple Unit to add Decimal Places. | Change tag values : NAME, DECIMALPLACES | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/units/alter/json/TaskAlterKGUnitJSON.txt) |
| Alter a Unit ‘KG’ with Decimal Places | Change tag values : NAME, DECIMALPLACES | [XML](https://tallysolutions.com/tallyprime-api-explorer/files/units/alter/xml/TaskAlterUnitKGXML.txt) |

### 3.3.4 Delete a Unit

> Explorer id: `delete-unit` · Kind: **import** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#delete-unit)

#### Description

The Delete action is used to Delete a Unit from the company data. Any Unit, unless not used or referred in transactions or other masters, can be deleted.

**Integration use:** Remove unused units. Fails if referenced by items or compound units.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svMstImportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `import` | Yes |
| `type` | `data` | Yes |
| `id` | `All Masters` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svMstImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Unit",
        "action": "Delete",
        "name": "box"
      }
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>All Masters</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
 <UNIT NAME="Box" ACTION="Delete">
  <NAME>Box</NAME>
 </UNIT>
</TALLYMESSAGE>
        </DESC>
    </BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: import" \
  -H "type: data" \
  -H "id: All Masters" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟢 Official shape: Tally's published master import response):

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 0,
            "deleted": 1,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 0
        }
    }
}
```

**Success — XML** (🔵 Observed: captured from a live TallyPrime in `docs/Tally_Vouchers_Integration_Guide.md`; `CMPINFO` truncated):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <CREATED>0</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>1</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>0</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
        <DESC>
            <CMPINFO>
                <COMPANY>0</COMPANY>
                <GROUP>0</GROUP>
                <LEDGER>95</LEDGER>
                <!-- … one count element per object type (COSTCENTRE, GODOWN, STOCKITEM, UNIT, VOUCHERTYPE, …) … -->
                <VOUCHER>39</VOUCHER>
            </CMPINFO>
        </DESC>
    </BODY>
</ENVELOPE>
```

Check `deleted` = 1 **and** `errors` + `exceptions` = 0. `status: "1"` only means the request was processed, not that the record was accepted.

#### Error Responses

**Record-level failure:** `Cannot be deleted!`. Source: 🔵 Observed.

Cause: The unit is still referenced (by vouchers, child masters, stock items or compound units). Remove the references first, or archive instead of deleting.

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <LINEERROR>Cannot be deleted!</LINEERROR>
                <CREATED>0</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>1</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
    </BODY>
</ENVELOPE>
```

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 1
        }
    }
}
```

> In JSON the failure shows up as non-zero `errors` / `exceptions` counts. Tally does not document the JSON key that carries the line-error text, so log the raw response body; this repo's parser (`parse_tally_response_metrics`) also checks `import_result.line_error`.

See also [Common errors](#110-common-error-responses) (company not loaded, unknown request, Tally not running).

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `import` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `data` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `All Masters` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svMstImportFormat]` | `<STATICVARIABLES><SVMSTIMPORTFORMAT>` | Yes (master import) | String | `jsonex` | Import format of masters: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `tallymessage[]` | `<TALLYMESSAGE>` | Yes | Array<Object> |  | The objects to import (masters or vouchers). One request can carry many objects. |
| `tallymessage[].metadata` | `<UNIT …>` attributes | Yes | Object |  | Object identity block: type, name/identifiers and action. |
| `tallymessage[].metadata.type` | element name `<UNIT>` | Yes | String | `Unit` | Object type: `Ledger`, `Group`, `Stock Item`, `Stock Group`, `Unit`, `Voucher`. |
| `tallymessage[].metadata.action` | `ACTION` attribute | Yes | String | `Delete` | `Create`, `Alter`, or `Delete` (case-insensitive). |
| `tallymessage[].metadata.name` | `NAME` attribute | Yes (masters) | String | `box` | Name of the master; the key Tally matches on for Alter/Delete. |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Delete the Unit 'Tons' | Change tag values: NAME | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/units/delete/json/TaskDeleteKGUnitJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/units/delete/xml/TaskDeleteKGUnitXML.txt) |

### 3.3.5 Pull a Unit

> Explorer id: `pull-unit` · Kind: **object** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#pull-unit)

#### Description

Details about a single Unit can be pulled using the Name of the Unit which is the identifier. All the first level methods from Unit object can be fetched.

**Integration use:** Verify a unit exists before referencing it in a stock item payload.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svExportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVEXPORTFORMAT>XML</SVEXPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `export` | Yes |
| `type` | `object` | Yes |
| `subtype` | `Unit` | Cond. |
| `id` | `Nos` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<SUBTYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonEx"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "fetch_list": [
    "Name"
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Object</TYPE>
        <SUBTYPE>Unit</SUBTYPE>
        <ID TYPE="Name">Nos</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
            <FETCHLIST>
                <FETCH>Name</FETCH>
            </FETCHLIST>
        </DESC>
    </BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: export" \
  -H "type: object" \
  -H "subtype: Unit" \
  -H "id: Nos" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟡 Illustrative: structure per Tally's published object-export sample `{type, value}` per method; values invented):

```json
{
    "status": "1",
    "tallymessage": [
        {
            "metadata": {
                "type": "Unit",
                "name": "Nos",
                "reservedname": "",
                "id": "1042",
                "reqname": "Nos"
            },
            "languagename": [
                {
                    "name": [
                        {
                            "metadata": true,
                            "type": "String"
                        },
                        "Nos"
                    ],
                    "languageid": {
                        "type": "Number",
                        "value": " 1033"
                    }
                }
            ]
        }
    ]
}
```

**Success — XML** (🟡 Illustrative: TYPE-attributed fields mirroring the JSON):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DESC>
        </DESC>
        <DATA>
            <TALLYMESSAGE>
                <UNIT NAME="Nos" RESERVEDNAME="">
                    <LANGUAGENAME.LIST>
                        <NAME.LIST TYPE="String">
                            <NAME>Nos</NAME>
                        </NAME.LIST>
                        <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
                    </LANGUAGENAME.LIST>
                </UNIT>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>
```

#### Error Responses

- **Object not found / wrong `subtype`** (🟡 Illustrative): Tally returns no object (an empty `tallymessage` / `<TALLYMESSAGE/>`) or `status` `0`. Treat a missing object, not just the status flag, as "not found".
- **Multilingual names:** send the name base64-encoded in `id-encoded` (with `content-type: application/json;charset=utf-8`) instead of `id`.
- [Common errors](#110-common-error-responses) apply (company not loaded, Tally not running).

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `export` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `object` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: subtype` | `<HEADER><SUBTYPE>` | Cond. | String | `Unit` | Object type for `type: Object` (e.g. `Ledger`, `StockItem`). |
| `header: id` | `<HEADER><ID>` | Yes | String | `Nos` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svExportFormat]` | `<STATICVARIABLES><SVEXPORTFORMAT>` | Yes (export) | String | `jsonEx` | Response format: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `fetch_list[]` | `<FETCHLIST><FETCH>` | No | Array<String> | `Name` | Methods/storages to return for an Object export (`type: object`). Omit to get the default set. |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Pull only Name of the Unit ‘Pkt’ | Change the HTTP Header value of 'id' Fetch relevant methods. | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/units/pull/json/PullaUnitJSON.txt) |
| Pull a Unit ‘Pkt’ | Change the tag value of 'id'. Fetch relevant methods. | [XML](https://tallysolutions.com/tallyprime-api-explorer/files/units/pull/xml/PullaUnitXML.txt) |

### 3.3.6 Pull all Units

> Explorer id: `pull-all-units` · Kind: **collection** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#pull-all-units)

#### Description

Details about multiple Units can be pulled using a TDL collection definition, which can already exist in the default source code or sent via the payload. TDL collection definition has type attribute that specifies the type of object that is grouped and fetch attribute that fetches the required methods.

**Integration use:** Build a unit-mapping table between your system's UoM codes and Tally units.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svExportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVEXPORTFORMAT>XML</SVEXPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `export` | Yes |
| `type` | `collection` | Yes |
| `id` | `Unit` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Collection</TYPE>
        <ID>TSPLSimpleUnits</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
<TDL>
<TDLMESSAGE>
  <COLLECTION NAME="TSPL SimpleUnits" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
   <TYPE>Unit</TYPE>
   <NATIVEMETHOD>Name, OriginalName, IsSimpleUnit</NATIVEMETHOD>
   <FILTERS>TSPLSimpleUnitsOnly</FILTERS>
  </COLLECTION>
  <SYSTEM TYPE="Formulae" NAME="TSPLSimpleUnitsOnly" ISMODIFY="No" ISFIXED="No" ISINTERNAL="No">$IsSimpleUnit  </SYSTEM>
</TDLMESSAGE>
</TDL>
        </DESC>
    </BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: export" \
  -H "type: collection" \
  -H "id: Unit" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟡 Illustrative (shape per Tally's published collection sample; values invented)):

```json
{
    "status": "1",
    "data": {
        "metadata": {
            "is_mst_dep_type": true,
            "mst_dep_type": "<type-code>"
        },
        "collection": [
            {
                "metadata": {
                    "type": "Unit",
                    "name": "Kg",
                    "reservedname": ""
                },
                "languagename": [
                    {
                        "name": [
                            {
                                "metadata": true,
                                "type": "String"
                            },
                            "Kg"
                        ],
                        "languageid": {
                            "type": "Number",
                            "value": " 1033"
                        }
                    }
                ]
            },
            {
                "metadata": {
                    "type": "Unit",
                    "name": "Nos",
                    "reservedname": ""
                },
                "languagename": [
                    {
                        "name": [
                            {
                                "metadata": true,
                                "type": "String"
                            },
                            "Nos"
                        ],
                        "languageid": {
                            "type": "Number",
                            "value": " 1033"
                        }
                    }
                ]
            }
        ]
    }
}
```

**Success — XML** (🟡 Illustrative):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DESC>
        </DESC>
        <DATA>
            <COLLECTION>
                <UNIT NAME="Kg" RESERVEDNAME="">
                    <LANGUAGENAME.LIST>
                        <NAME.LIST TYPE="String">
                            <NAME>Kg</NAME>
                        </NAME.LIST>
                        <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
                    </LANGUAGENAME.LIST>
                </UNIT>
                <UNIT NAME="Nos" RESERVEDNAME="">
                    <LANGUAGENAME.LIST>
                        <NAME.LIST TYPE="String">
                            <NAME>Nos</NAME>
                        </NAME.LIST>
                        <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
                    </LANGUAGENAME.LIST>
                </UNIT>
            </COLLECTION>
        </DATA>
    </BODY>
</ENVELOPE>
```

#### Error Responses

- **Collection name mismatch** (🟡 Illustrative): if the `id` header / `<ID>` does not match a default collection or a definition in `tdlmessage`, Tally returns an error instead of data. TDL names ignore case and spaces (`TSPL All Payment Vouchers` = `TSPLAllPaymentVouchers`), but any other spelling difference breaks the match.
- **Invalid TDL** (bad attribute or formula): Tally may show an error dialog on the Tally screen and return nothing useful. Validate TDL in the Explorer before shipping it.
- **Empty result:** a valid request that matches nothing returns `status: "1"` with an empty `collection` (`<COLLECTION/>`).
- [Common errors](#110-common-error-responses) apply.

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `export` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `collection` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `Unit` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svExportFormat]` | `<STATICVARIABLES><SVEXPORTFORMAT>` | Yes (export) | String | `jsonex` | Response format: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |

# 4. Transactions — Accounting Vouchers

A transaction in Tally represents any business activity involving money, goods, or commitments—such as sales, purchases, payments, or receipts. It is recorded using vouchers and follows the double-entry system, where at least two ledgers are affected (debit and credit).

Transactions form the backbone of accounting, driving all financial reports and business insights. For ease of understanding the structure and required tags, transactions are categorized as follows:

- Accounting Vouchers
- Inventory Vouchers
- Order Vouchers
- Payroll Vouchers

In TallyPrime, transactions are referred to as the ‘Voucher’ object in the database. A voucher supports 200+ fields, however, only the relevant fields need to be provided based on the nature of the transaction being recorded.

The following are the core mandatory tags required for any voucher creation or alteration:

| Tag / Collection | Mandatory | Data Type | Explanation |
|---|---|---|---|
| VoucherType Name | Yes | String | Defines the type of voucher (e.g., Payment, Sales, Purchase) under which the transaction is recorded. |
| Date | Yes | String | Indicates the transaction date in Tally-accepted format (YYYYMMDD). |
| VoucherNumber | Conditional | String | By default, Tally auto-generates voucher numbers. This tag is required only if you want to pass a custom voucher number from your system. |

Note : Subsequent sections will cover additional mandatory tags specific to each voucher type.

**Accounting vouchers**

Accounting vouchers record transactions that involve the movement of money and financial impact within a business. They capture all core financial activities and ensure that every transaction follows the double-entry system, maintaining accurate and balanced books of accounts.

These include vouchers such as Purchase, Sales, Payment, Receipt, Contra, Debit Note, Credit Note, Journal, Memorandum, and Reversing Journal, each serving a specific purpose in recording and adjusting financial data.

All the vouchers have similar structure, however based on their behaviour there are changes in the tags.

| Tag | Mandatory | Data Type | Explanation |
|---|---|---|---|
| VoucherType Name | Yes | String | Defines the type of voucher under which the transaction is recorded. Since these are accounting vouchers should be any of the following   Purchase, Sales, Payment, Receipt, Contra, Debit Note, Credit Note, Journal, Memorandum, or Reversing Journal. |
| Date | Yes | String | Indicates the transaction date in Tally-accepted format (YYYYMMDD). |
| VoucherNumber | Conditional | String | By default, Tally auto-generates voucher numbers. This tag is required only if you want to pass a custom voucher number from your system. |
| PartyLedgerName | Yes | String | Specifies the name of primary party or account involved in the transaction (e.g., customer, supplier, bank) |
| AllLedgerEntries | Yes | Collection | Collection of ledger entries forming the transaction; ensures debit and credit entries are captured |
| LedgerName | Yes | String | Name of the ledger affected in the transaction |
| IsDeemedPositive | Yes | Logical / Boolean | Determines whether the entry is treated as Debit (Yes) or Credit (No) |
| IsPartyLedger | Yes | Logical / Boolean | Indicates whether the ledger is the main party ledger in the transaction |
| Amount | Yes | Amount | Specifies the transaction amount |

## 4.1 Payment

### 4.1.0 Payment — Overview & Field Reference

> 🟢 Official: converted from the Explorer's "About Payment" page.

A Payment Voucher is used to record all outgoing payments made by the business, whether through cash, bank, or other modes. It captures transactions where money is paid to suppliers, employees, or for expenses, ensuring proper tracking of cash outflow.

Each payment impacts at least two ledgers typically crediting Cash/Bank and debiting the respective expense or party ledger maintaining accurate financial records.

| Tag | Mandatory | Data Type | Explanation |
|---|---|---|---|
| VoucherType Name | Yes | String | Defines the type of voucher under which the transaction is recorded. Since we want to create a payment voucher, we would provide value as Payment. |
| Date | Yes | String | Indicates the transaction date in Tally-accepted format (YYYYMMDD). |
| VoucherNumber | Conditional | String | By default, Tally auto-generates voucher numbers. This tag is required only if you want to pass a custom voucher number from your system. |
| PartyLedgerName | Yes | String | Specifies the name of primary party or account involved in the transaction (e.g., customer, supplier, expense ledger) |
| AllLedgerEntries | Yes | Collection | Collection of ledger entries forming the transaction; ensures debit and credit entries are captured |
| LedgerName | Yes | String | Name of the ledger affected in the transaction |
| IsDeemedPositive | Yes | Logical / Boolean | Determines whether the entry is treated as Debit (Yes) or Credit (No) |
| IsPartyLedger | Yes | Logical / Boolean | Indicates whether the ledger is the main party ledger in the transaction |
| Amount | Yes | Amount | Specifies the transaction amount |

**Sample — XML Format**

```xml
<ENVELOPE>
 <HEADER>
  <TALLYREQUEST>Import Data</TALLYREQUEST>
 </HEADER>
 <BODY>
  <IMPORTDATA>
    <TALLYMESSAGE xmlns:UDF="TallyUDF">
     <VOUCHER VCHTYPE="Payment" ACTION="Create" OBJVIEW="Accounting Voucher View">
      <DATE>20260320</DATE>
      <COUNTRYOFRESIDENCE>India</COUNTRYOFRESIDENCE>
      <PLACEOFSUPPLY>Karnataka</PLACEOFSUPPLY>
      <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
      <PARTYNAME>Bank of Baroda</PARTYNAME>
      <PARTYLEDGERNAME>Bank of Baroda</PARTYLEDGERNAME>
      <VOUCHERNUMBER>32</VOUCHERNUMBER>
      <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
      <ALLLEDGERENTRIES.LIST>
       <LEDGERNAME>Advertising Expenses</LEDGERNAME>
       <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
       <ISPARTYLEDGER>No</ISPARTYLEDGER>
       <AMOUNT>-1000000.00</AMOUNT>
      </ALLLEDGERENTRIES.LIST>
      <ALLLEDGERENTRIES.LIST>
       <LEDGERNAME>Bank of Baroda</LEDGERNAME>
       <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
       <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
       <AMOUNT>1000000.00</AMOUNT>
       <BANKALLOCATIONS.LIST>
        <DATE>20260320</DATE>
        <INSTRUMENTDATE>20260320</INSTRUMENTDATE>
        <TRANSACTIONTYPE>Cheque</TRANSACTIONTYPE>
        <PAYMENTFAVOURING>Advertising Expenses</PAYMENTFAVOURING>
        <CHEQUECROSSCOMMENT>A/c Payee</CHEQUECROSSCOMMENT>
        <BANKPARTYNAME>Advertising Expenses</BANKPARTYNAME>
        <AMOUNT>1000000.00</AMOUNT>
       </BANKALLOCATIONS.LIST>
      </ALLLEDGERENTRIES.LIST>
     </VOUCHER>
    </TALLYMESSAGE>
   </REQUESTDATA>
  </IMPORTDATA>
 </BODY>
</ENVELOPE>

```

**Sample — JSON Format**

```json
{
  "tallymessage": [
    {
      "metadata": {
        "type": "Voucher",
        "action": "Create",
        "objectview": "Accounting Voucher View"
      },
      "DATE": "20260320",
      "VOUCHERTYPENAME": "Payment",
      "VOUCHERNUMBER": "32",
      "PERSISTEDVIEW": "Accounting Voucher View",
      "PARTYLEDGERNAME": "Bank of Baroda",
      "PARTYNAME": "Bank of Baroda",
      "COUNTRYOFRESIDENCE": "India",
      "PLACEOFSUPPLY": "Karnataka",
      "ALLLEDGERENTRIES.LIST": [
        {
          "LEDGERNAME": "Advertising Expenses",
          "ISDEEMEDPOSITIVE": "Yes",
          "ISPARTYLEDGER": "No",
          "AMOUNT": -1000000
        },
        {
          "LEDGERNAME": "Bank of Baroda",
          "ISDEEMEDPOSITIVE": "No",
          "ISPARTYLEDGER": "Yes",
          "AMOUNT": 1000000,
          "BANKALLOCATIONS.LIST": [
            {
              "DATE": "20260320",
              "INSTRUMENTDATE": "20260320",
              "TRANSACTIONTYPE": "Cheque",
              "PAYMENTFAVOURING": "Advertising Expenses",
              "CHEQUECROSSCOMMENT": "A/c Payee",
              "BANKPARTYNAME": "Advertising Expenses",
              "AMOUNT": 1000000
            }
          ]
        }
      ]
    }
  ]
}

```

### 4.1.1 Create a Payment with Banking details

> Explorer id: `payment-create-banking` · Kind: **import** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#payment-create-banking)

#### Description

The Create action is used to record a Payment voucher with bank details in the company data in Tally by providing information such as the bank ledger, party ledger, and payment amount. This captures bank-based outgoing payments and ensures correct debit and credit impact on the respective ledgers.

**Integration use:** Post outgoing bank payments (cheque/NEFT/UPI) with instrument details so bank reconciliation in Tally works out of the box.

**Notes:**

- `bankallocations` amount must equal the bank ledger line amount.
- Party line Debit (`isdeemedpositive: true`, negative amount); bank line Credit (positive amount).

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svVchImportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `import` | Yes |
| `type` | `data` | Yes |
| `id` | `Vouchers` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svVchImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Voucher",
        "vchtype": "Payment",
        "action": "Create",
        "objview": "Accounting Voucher View"
      },
      "date": "20250831",
      "vouchertypename": "Payment",
      "partyledgername": "Akshaya Enterprises",
      "persistedview": "Accounting Voucher View",
      "allledgerentries": [
        {
          "ledgername": "Akshaya Enterprises",
          "isdeemedpositive": true,
          "ispartyledger": true,
          "amount": "-200.00",
          "billallocations": [
            {
              "name": "16",
              "billtype": "New Ref",
              "amount": "-200.00"
            }
          ]
        },
        {
          "ledgername": "Kotak Bank",
          "isdeemedpositive": false,
          "ispartyledger": true,
          "amount": "200.00",
          "bankallocations": [
            {
              "date": "20250831",
              "instrumentdate": "20250831",
              "email": "a@gmail.com",
              "transactiontype": "Inter Bank Transfer",
              "ifscode": "KKBK0000431",
              "bankname": "Kotak Mahindra Bank (India)",
              "accountnumber": "4891289138912",
              "paymentfavouring": "Akshaya Enterprises",
              "transactionname": "Primary",
              "transfermode": "NEFT",
              "bankid": "10",
              "instrumentnumber": "100",
              "paymentmode": "Transacted",
              "bankpartyname": "Akshaya Enterprises",
              "amount": "200.00"
            }
          ]
        }
      ]
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
<TALLYMESSAGE>
 <VOUCHER VCHTYPE="Payment" ACTION="Create" OBJVIEW="Accounting Voucher View">
  <DATE>20250831</DATE>
  <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
  <PARTYLEDGERNAME>Akshaya Enterprises</PARTYLEDGERNAME>
  <ALLLEDGERENTRIES.LIST>
   <LEDGERNAME>Akshaya Enterprises</LEDGERNAME>
   <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
   <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
   <AMOUNT>-200.00</AMOUNT>
   <BILLALLOCATIONS.LIST>
<NAME>29</NAME>
<BILLTYPE>New Ref</BILLTYPE>
<AMOUNT>-200.00</AMOUNT>
   </BILLALLOCATIONS.LIST>
  </ALLLEDGERENTRIES.LIST>
  <ALLLEDGERENTRIES.LIST>
   <LEDGERNAME>Kotak Bank</LEDGERNAME>
   <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
   <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
   <AMOUNT>200.00</AMOUNT>
   <BANKALLOCATIONS.LIST>
<DATE>20250831</DATE>
<INSTRUMENTDATE>20250831</INSTRUMENTDATE>
<EMAIL>a@gmail.com</EMAIL>
<TRANSACTIONTYPE>Inter Bank Transfer</TRANSACTIONTYPE>
<IFSCODE>KKBK0000431</IFSCODE>
<BANKNAME>Kotak Mahindra Bank (India)</BANKNAME>
<ACCOUNTNUMBER>4891289138912</ACCOUNTNUMBER>
<PAYMENTFAVOURING>Akshaya Enterprises</PAYMENTFAVOURING>
<TRANSACTIONNAME>Primary</TRANSACTIONNAME>
<TRANSFERMODE>NEFT</TRANSFERMODE>
<INSTRUMENTNUMBER>6556876878</INSTRUMENTNUMBER>
<PAYMENTMODE>Transacted</PAYMENTMODE>
<BANKPARTYNAME>Akshaya Enterprises</BANKPARTYNAME>
<AMOUNT>200.00</AMOUNT>
   </BANKALLOCATIONS.LIST>
  </ALLLEDGERENTRIES.LIST>
 </VOUCHER>
</TALLYMESSAGE>
</DESC>
</BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: import" \
  -H "type: data" \
  -H "id: Vouchers" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟢 Official shape: Tally's published voucher import response):

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 1,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 71,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 0,
            "vchnumber": 33
        }
    }
}
```

**Success — XML** (🔵 Observed: captured from a live TallyPrime in `docs/Tally_Vouchers_Integration_Guide.md`; `CMPINFO` truncated):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <CREATED>1</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>71</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>0</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
        <DESC>
            <CMPINFO>
                <COMPANY>0</COMPANY>
                <GROUP>0</GROUP>
                <LEDGER>95</LEDGER>
                <!-- … one count element per object type (COSTCENTRE, GODOWN, STOCKITEM, UNIT, VOUCHERTYPE, …) … -->
                <VOUCHER>39</VOUCHER>
            </CMPINFO>
        </DESC>
    </BODY>
</ENVELOPE>
```

Check `created` = 1 **and** `errors` + `exceptions` = 0. `status: "1"` only means the request was processed, not that the record was accepted. `lastvchid` is the internal id (MASTERID) of the last voucher written, and `vchnumber` is its voucher number.

#### Error Responses

**Record-level failure:** `Ledger 'Akshaya Enterprises' does not exist!`. Source: 🟡 Illustrative (message pattern also reported by other Tally integrations).

Cause: A ledger (or stock item / godown) referenced by the voucher is missing, or misspelt. Create masters before vouchers.

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <LINEERROR>Ledger &apos;Akshaya Enterprises&apos; does not exist!</LINEERROR>
                <CREATED>0</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>1</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
    </BODY>
</ENVELOPE>
```

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 1
        }
    }
}
```

> In JSON the failure shows up as non-zero `errors` / `exceptions` counts. Tally does not document the JSON key that carries the line-error text, so log the raw response body; this repo's parser (`parse_tally_response_metrics`) also checks `import_result.line_error`.

See also [Common errors](#110-common-error-responses) (company not loaded, unknown request, Tally not running).

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `import` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `data` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `Vouchers` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svVchImportFormat]` | `<STATICVARIABLES><SVVCHIMPORTFORMAT>` | Yes (voucher import) | String | `jsonex` | Import format of vouchers: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `tallymessage[]` | `<TALLYMESSAGE>` | Yes | Array<Object> |  | The objects to import (masters or vouchers). One request can carry many objects. |
| `tallymessage[].metadata` | `<VOUCHER …>` attributes | Yes | Object |  | Object identity block: type, name/identifiers and action. |
| `tallymessage[].metadata.type` | element name `<VOUCHER>` | Yes | String | `Voucher` | Object type: `Ledger`, `Group`, `Stock Item`, `Stock Group`, `Unit`, `Voucher`. |
| `tallymessage[].metadata.vchtype` | `VCHTYPE` attribute | Yes (vouchers) | String | `Payment` | Voucher type name, e.g. `Payment`, `Receipt`, `Sales`, `Purchase`. |
| `tallymessage[].metadata.action` | `ACTION` attribute | Yes | String | `Create` | `Create`, `Alter`, or `Delete` (case-insensitive). |
| `tallymessage[].metadata.objview` | `OBJVIEW` attribute | Yes (vouchers) | String | `Accounting Voucher View` | `Accounting Voucher View` (ledger-only vouchers) or `Invoice Voucher View` (item invoices). |
| `tallymessage[].date` | `<VOUCHER>/DATE` | Yes | Date (YYYYMMDD) | `20250831` | Voucher date. Must fall inside the company's books period (Educational Mode: only 1st, 2nd, 31st). |
| `tallymessage[].vouchertypename` | `<VOUCHER>/VOUCHERTYPENAME` | Yes | String | `Payment` | Voucher type name, e.g. `Payment`. |
| `tallymessage[].partyledgername` | `<VOUCHER>/PARTYLEDGERNAME` | Yes | String | `Akshaya Enterprises` | Primary party / account ledger of the voucher. |
| `tallymessage[].persistedview` | `<VOUCHER>/PERSISTEDVIEW` | No | String | `Accounting Voucher View` | Voucher view persisted with the voucher (mirrors `objview`). |
| `tallymessage[].allledgerentries[]` | `<VOUCHER>/ALLLEDGERENTRIES.LIST` | Yes (acct view) | Array<Object> |  | Ledger lines of an Accounting-view voucher (`ALLLEDGERENTRIES.LIST`). |
| `tallymessage[].allledgerentries[].ledgername` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/LEDGERNAME` | Yes | String | `Akshaya Enterprises` | Ledger affected by the line. Must already exist. |
| `tallymessage[].allledgerentries[].isdeemedpositive` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/ISDEEMEDPOSITIVE` | Yes | Logical | `true` | `Yes`/`true` = Debit, `No`/`false` = Credit. |
| `tallymessage[].allledgerentries[].ispartyledger` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/ISPARTYLEDGER` | Yes | Logical | `true` | `Yes` for the party/cash/bank line of the voucher. |
| `tallymessage[].allledgerentries[].amount` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/AMOUNT` | Yes | Amount | `-200.00` | Line amount. Sign convention: Debit lines negative, Credit lines positive; all lines must net to zero. |
| `tallymessage[].allledgerentries[].billallocations[]` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/BILLALLOCATIONS.LIST` | Cond. | Array<Object> |  | Bill-wise allocation for bill-wise-enabled party ledgers (`BILLALLOCATIONS.LIST`). |
| `tallymessage[].allledgerentries[].billallocations[].name` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/BILLALLOCATIONS.LIST/NAME` | Yes | String | `16` | Bill reference number (e.g. invoice no.). |
| `tallymessage[].allledgerentries[].billallocations[].billtype` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/BILLALLOCATIONS.LIST/BILLTYPE` | Yes | String | `New Ref` | `New Ref`, `Agst Ref`, `Advance`, or `On Account`. |
| `tallymessage[].allledgerentries[].billallocations[].amount` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/BILLALLOCATIONS.LIST/AMOUNT` | Yes | Amount | `-200.00` | Line amount. Sign convention: Debit lines negative, Credit lines positive; all lines must net to zero. |
| `tallymessage[].allledgerentries[].bankallocations[]` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/BANKALLOCATIONS.LIST` | Cond. | Array<Object> |  | Banking details for a bank-ledger line (`BANKALLOCATIONS.LIST`). Total must equal the bank line amount. |
| `tallymessage[].allledgerentries[].bankallocations[].date` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/BANKALLOCATIONS.LIST/DATE` | Yes | Date (YYYYMMDD) | `20250831` | Bank allocation date. |
| `tallymessage[].allledgerentries[].bankallocations[].instrumentdate` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/BANKALLOCATIONS.LIST/INSTRUMENTDATE` | No | Date (YYYYMMDD) | `20250831` | Cheque/instrument date. |
| `tallymessage[].allledgerentries[].bankallocations[].email` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/BANKALLOCATIONS.LIST/EMAIL` | No | String | `a@gmail.com` | Counter-party e-mail for payment advice. |
| `tallymessage[].allledgerentries[].bankallocations[].transactiontype` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/BANKALLOCATIONS.LIST/TRANSACTIONTYPE` | Yes | String | `Inter Bank Transfer` | Mode: `Cheque`, `Cheque/DD`, `e-Fund Transfer`, `Inter Bank Transfer`, `Others`, etc. |
| `tallymessage[].allledgerentries[].bankallocations[].ifscode` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/BANKALLOCATIONS.LIST/IFSCODE` | No | String | `KKBK0000431` | Counter-party IFSC. |
| `tallymessage[].allledgerentries[].bankallocations[].bankname` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/BANKALLOCATIONS.LIST/BANKNAME` | No | String | `Kotak Mahindra Bank (India)` | Counter-party bank name. |
| `tallymessage[].allledgerentries[].bankallocations[].accountnumber` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/BANKALLOCATIONS.LIST/ACCOUNTNUMBER` | No | String | `4891289138912` | Counter-party account number. |
| `tallymessage[].allledgerentries[].bankallocations[].paymentfavouring` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/BANKALLOCATIONS.LIST/PAYMENTFAVOURING` | No | String | `Akshaya Enterprises` | Payee name (favouring). |
| `tallymessage[].allledgerentries[].bankallocations[].transactionname` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/BANKALLOCATIONS.LIST/TRANSACTIONNAME` | No | String | `Primary` | Bank transaction name. |
| `tallymessage[].allledgerentries[].bankallocations[].transfermode` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/BANKALLOCATIONS.LIST/TRANSFERMODE` | No | String | `NEFT` | e-Fund transfer mode, e.g. `NEFT`, `RTGS`, `IMPS`. |
| `tallymessage[].allledgerentries[].bankallocations[].bankid` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/BANKALLOCATIONS.LIST/BANKID` | No | String | `10` | Counter-party bank identifier. |
| `tallymessage[].allledgerentries[].bankallocations[].instrumentnumber` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/BANKALLOCATIONS.LIST/INSTRUMENTNUMBER` | No | String | `100` | Cheque / UTR / instrument number. |
| `tallymessage[].allledgerentries[].bankallocations[].paymentmode` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/BANKALLOCATIONS.LIST/PAYMENTMODE` | No | String | `Transacted` | `Transacted` or `Not Transacted`. |
| `tallymessage[].allledgerentries[].bankallocations[].bankpartyname` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/BANKALLOCATIONS.LIST/BANKPARTYNAME` | No | String | `Akshaya Enterprises` | Counter-party name for the bank allocation. |
| `tallymessage[].allledgerentries[].bankallocations[].amount` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/BANKALLOCATIONS.LIST/AMOUNT` | Yes | Amount | `200.00` | Line amount. Sign convention: Debit lines negative, Credit lines positive; all lines must net to zero. |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Create a Payment Voucher with same ledger but on date ‘1st August 2025” and the amount is Rs. 900 | Change the value of Date tags in voucher and bankallocations. Change the value of all amount tags | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/payment/create-banking/json/TaskCreateBankPayment900JSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/payment/create-banking/xml/TaskCreateBankPayment900XML.txt) |
| Create a Payment Voucher on date ‘2nd August 2025’ with same ledgers and amount but with Bankallocations for Cheque Payment | Change the value of Date tags in voucher and bankallocations. Add relevant methods in Bankallocations collections for Cheque Payment | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/payment/create-banking/json/TaskCreateBankPaymentChequeJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/payment/create-banking/xml/TaskCreateBankPaymentChequeXML.txt) |

### 4.1.2 Create a Payment with Cash

> Explorer id: `payment-create-cash` · Kind: **import** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#payment-create-cash)

#### Description

A Payment Voucher can be created by providing VoucherType, Date, Debit and credit ledger details with amount. A Payment with Cash will typically have Cash Ledger credited and Party / expense Ledger debited. These details when sent in appropriate methods and collections of Voucher Object, creates a payment voucher successfully.

**Integration use:** Post petty-cash / cash expense outflows from your expense or POS module.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svVchImportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `import` | Yes |
| `type` | `data` | Yes |
| `id` | `Vouchers` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svVchImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Voucher",
        "vchtype": "Payment",
        "action": "Create",
        "objview": "Accounting Voucher View"
      },
      "date": "20250831",
      "vouchertypename": "Payment",
      "partyledgername": "Cash",
      "persistedview": "Accounting Voucher View",
      "allledgerentries": [
        {
          "ledgername": "Sundry Expenses",
          "isdeemedpositive": true,
          "ispartyledger": false,
          "amount": "-100.00",
          "categoryallocations": [
            {
              "category": "Primary Cost Category",
              "isdeemedpositive": true,
              "costcentreallocations": [
                {
                  "name": "CostName",
                  "amount": "-100.00"
                }
              ]
            }
          ]
        },
        {
          "ledgername": "Cash",
          "isdeemedpositive": false,
          "ispartyledger": true,
          "amount": "100.00"
        }
      ]
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
 <VOUCHER VCHTYPE="Payment" ACTION="Create" OBJVIEW="Accounting Voucher View">
  <DATE>20250831</DATE>
  <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
  <PARTYLEDGERNAME>Cash</PARTYLEDGERNAME>
  <ALLLEDGERENTRIES.LIST>
   <LEDGERNAME>Sundry Expenses</LEDGERNAME>
   <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
   <ISPARTYLEDGER>No</ISPARTYLEDGER>
   <AMOUNT>-100.00</AMOUNT>
   <CATEGORYALLOCATIONS.LIST>
<CATEGORY>Primary Cost Category</CATEGORY>
<ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
<COSTCENTREALLOCATIONS.LIST>
 <NAME>CostName</NAME>
 <AMOUNT>-100.00</AMOUNT>
</COSTCENTREALLOCATIONS.LIST>
   </CATEGORYALLOCATIONS.LIST>
  </ALLLEDGERENTRIES.LIST>
  <ALLLEDGERENTRIES.LIST>
   <LEDGERNAME>Cash</LEDGERNAME>
   <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
   <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
   <AMOUNT>100.00</AMOUNT>
  </ALLLEDGERENTRIES.LIST>
 </VOUCHER>
</TALLYMESSAGE>
</DESC>
</BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: import" \
  -H "type: data" \
  -H "id: Vouchers" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟢 Official shape: Tally's published voucher import response):

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 1,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 71,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 0,
            "vchnumber": 33
        }
    }
}
```

**Success — XML** (🔵 Observed: captured from a live TallyPrime in `docs/Tally_Vouchers_Integration_Guide.md`; `CMPINFO` truncated):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <CREATED>1</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>71</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>0</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
        <DESC>
            <CMPINFO>
                <COMPANY>0</COMPANY>
                <GROUP>0</GROUP>
                <LEDGER>95</LEDGER>
                <!-- … one count element per object type (COSTCENTRE, GODOWN, STOCKITEM, UNIT, VOUCHERTYPE, …) … -->
                <VOUCHER>39</VOUCHER>
            </CMPINFO>
        </DESC>
    </BODY>
</ENVELOPE>
```

Check `created` = 1 **and** `errors` + `exceptions` = 0. `status: "1"` only means the request was processed, not that the record was accepted. `lastvchid` is the internal id (MASTERID) of the last voucher written, and `vchnumber` is its voucher number.

#### Error Responses

**Record-level failure:** `Ledger 'Sundry Expenses' does not exist!`. Source: 🟡 Illustrative (message pattern also reported by other Tally integrations).

Cause: A ledger (or stock item / godown) referenced by the voucher is missing, or misspelt. Create masters before vouchers.

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <LINEERROR>Ledger &apos;Sundry Expenses&apos; does not exist!</LINEERROR>
                <CREATED>0</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>1</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
    </BODY>
</ENVELOPE>
```

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 1
        }
    }
}
```

> In JSON the failure shows up as non-zero `errors` / `exceptions` counts. Tally does not document the JSON key that carries the line-error text, so log the raw response body; this repo's parser (`parse_tally_response_metrics`) also checks `import_result.line_error`.

See also [Common errors](#110-common-error-responses) (company not loaded, unknown request, Tally not running).

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `import` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `data` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `Vouchers` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svVchImportFormat]` | `<STATICVARIABLES><SVVCHIMPORTFORMAT>` | Yes (voucher import) | String | `jsonex` | Import format of vouchers: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `tallymessage[]` | `<TALLYMESSAGE>` | Yes | Array<Object> |  | The objects to import (masters or vouchers). One request can carry many objects. |
| `tallymessage[].metadata` | `<VOUCHER …>` attributes | Yes | Object |  | Object identity block: type, name/identifiers and action. |
| `tallymessage[].metadata.type` | element name `<VOUCHER>` | Yes | String | `Voucher` | Object type: `Ledger`, `Group`, `Stock Item`, `Stock Group`, `Unit`, `Voucher`. |
| `tallymessage[].metadata.vchtype` | `VCHTYPE` attribute | Yes (vouchers) | String | `Payment` | Voucher type name, e.g. `Payment`, `Receipt`, `Sales`, `Purchase`. |
| `tallymessage[].metadata.action` | `ACTION` attribute | Yes | String | `Create` | `Create`, `Alter`, or `Delete` (case-insensitive). |
| `tallymessage[].metadata.objview` | `OBJVIEW` attribute | Yes (vouchers) | String | `Accounting Voucher View` | `Accounting Voucher View` (ledger-only vouchers) or `Invoice Voucher View` (item invoices). |
| `tallymessage[].date` | `<VOUCHER>/DATE` | Yes | Date (YYYYMMDD) | `20250831` | Voucher date. Must fall inside the company's books period (Educational Mode: only 1st, 2nd, 31st). |
| `tallymessage[].vouchertypename` | `<VOUCHER>/VOUCHERTYPENAME` | Yes | String | `Payment` | Voucher type name, e.g. `Payment`. |
| `tallymessage[].partyledgername` | `<VOUCHER>/PARTYLEDGERNAME` | Yes | String | `Cash` | Primary party / account ledger of the voucher. |
| `tallymessage[].persistedview` | `<VOUCHER>/PERSISTEDVIEW` | No | String | `Accounting Voucher View` | Voucher view persisted with the voucher (mirrors `objview`). |
| `tallymessage[].allledgerentries[]` | `<VOUCHER>/ALLLEDGERENTRIES.LIST` | Yes (acct view) | Array<Object> |  | Ledger lines of an Accounting-view voucher (`ALLLEDGERENTRIES.LIST`). |
| `tallymessage[].allledgerentries[].ledgername` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/LEDGERNAME` | Yes | String | `Sundry Expenses` | Ledger affected by the line. Must already exist. |
| `tallymessage[].allledgerentries[].isdeemedpositive` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/ISDEEMEDPOSITIVE` | Yes | Logical | `true` | `Yes`/`true` = Debit, `No`/`false` = Credit. |
| `tallymessage[].allledgerentries[].ispartyledger` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/ISPARTYLEDGER` | Yes | Logical | `false` | `Yes` for the party/cash/bank line of the voucher. |
| `tallymessage[].allledgerentries[].amount` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/AMOUNT` | Yes | Amount | `-100.00` | Line amount. Sign convention: Debit lines negative, Credit lines positive; all lines must net to zero. |
| `tallymessage[].allledgerentries[].categoryallocations[]` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/CATEGORYALLOCATIONS.LIST` | Cond. | Array<Object> |  | Cost-category allocations (`CATEGORYALLOCATIONS.LIST`) for cost-centre-enabled ledgers. |
| `tallymessage[].allledgerentries[].categoryallocations[].category` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/CATEGORYALLOCATIONS.LIST/CATEGORY` | Yes | String | `Primary Cost Category` | Cost category name. |
| `tallymessage[].allledgerentries[].categoryallocations[].isdeemedpositive` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/CATEGORYALLOCATIONS.LIST/ISDEEMEDPOSITIVE` | Yes | Logical | `true` | `Yes`/`true` = Debit, `No`/`false` = Credit. |
| `tallymessage[].allledgerentries[].categoryallocations[].costcentreallocations[]` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/CATEGORYALLOCATIONS.LIST/COSTCENTREALLOCATIONS.LIST` | Cond. | Array<Object> |  | Cost-centre split inside a category (`COSTCENTREALLOCATIONS.LIST`). |
| `tallymessage[].allledgerentries[].categoryallocations[].costcentreallocations[].name` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/CATEGORYALLOCATIONS.LIST/COSTCENTREALLOCATIONS.LIST/NAME` | Yes | String | `CostName` | Object name; unique within the company for masters. |
| `tallymessage[].allledgerentries[].categoryallocations[].costcentreallocations[].amount` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/CATEGORYALLOCATIONS.LIST/COSTCENTREALLOCATIONS.LIST/AMOUNT` | Yes | Amount | `-100.00` | Line amount. Sign convention: Debit lines negative, Credit lines positive; all lines must net to zero. |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Create a Payment Voucher with same ledgers but on date ‘1st August 2025” with amount 500 | Change the value of Date tag, and all the amount tags | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/payment/create-cash/json/TaskCreateCashPayment500JSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/payment/create-cash/xml/TaskCreateCashPayment500XML.txt) |
| Create a Payment Voucher on date ‘2nd August 2025’ with Party Ledger ‘Akshaya Enterprises’ instead of Expense ledger with Billallocations with ‘New Ref’, Bill Number ‘Bill30AugAE’, with the same amount | Change the value of Date tag. Replace Income Ledger with ABC Party and add Billallocations collections with relevant storages. | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/payment/create-cash/json/TaskCreateCashPaymentAkshayaJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/payment/create-cash/xml/TaskCreateCashPaymentAkshayaXML.txt) |

### 4.1.3 Alter a Payment

> Explorer id: `payment-alter` · Kind: **import** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#payment-alter)

#### Description

Each TallyPrime voucher has unique system-generated identifiers. To modify a voucher, ensure the ‘guid’, ‘vchkey’, and ‘remoteid’ match the existing voucher’s values, which can be obtained by exporting it in XML/JSON format from TallyPrime. In the sample request, provide the right values for these tags and attributes to experience the alteration of voucher.

**Integration use:** Correct a posted payment in place (keeps the same voucher identity) instead of delete-and-recreate.

**Notes:**

- Export the voucher first (e.g. *Pull all Payment vouchers*) to get `remoteid`, `vchkey` and `guid`. Alter merges the fields you send into the voucher, and the sample changes only `date`.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svVchImportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `import` | Yes |
| `type` | `data` | Yes |
| `id` | `Vouchers` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svVchImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Voucher",
        "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000095",
        "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b348:00000058",
        "vchtype": "Payment",
        "action": "Alter",
        "objview": "Accounting Voucher View"
      },
      "date": "20250801",
      "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000095"
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
      <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000095" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b348:00000058" VCHTYPE="Payment" ACTION="Alter" OBJVIEW="Accounting Voucher View">
  <DATE>20250801</DATE>
  <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000095</GUID>
 </VOUCHER>
</TALLYMESSAGE>
</DESC>
</BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: import" \
  -H "type: data" \
  -H "id: Vouchers" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟢 Official shape: Tally's published voucher import response):

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 1,
            "deleted": 0,
            "lastvchid": 71,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 0,
            "vchnumber": 32
        }
    }
}
```

**Success — XML** (🔵 Observed: captured from a live TallyPrime in `docs/Tally_Vouchers_Integration_Guide.md`; `CMPINFO` truncated):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <CREATED>0</CREATED>
                <ALTERED>1</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>71</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>0</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
        <DESC>
            <CMPINFO>
                <COMPANY>0</COMPANY>
                <GROUP>0</GROUP>
                <LEDGER>95</LEDGER>
                <!-- … one count element per object type (COSTCENTRE, GODOWN, STOCKITEM, UNIT, VOUCHERTYPE, …) … -->
                <VOUCHER>39</VOUCHER>
            </CMPINFO>
        </DESC>
    </BODY>
</ENVELOPE>
```

Check `altered` = 1 **and** `errors` + `exceptions` = 0. `status: "1"` only means the request was processed, not that the record was accepted. `lastvchid` is the internal id (MASTERID) of the last voucher written, and `vchnumber` is its voucher number.

#### Error Responses

**Record-level failure:** `Voucher does not exist!`. Source: 🔵 Observed.

Cause: `remoteid` / `vchkey` / `guid` do not match any voucher in the company (e.g. ids copied from another company or the voucher was deleted).

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <LINEERROR>Voucher does not exist!</LINEERROR>
                <CREATED>0</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>1</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
    </BODY>
</ENVELOPE>
```

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 1
        }
    }
}
```

> In JSON the failure shows up as non-zero `errors` / `exceptions` counts. Tally does not document the JSON key that carries the line-error text, so log the raw response body; this repo's parser (`parse_tally_response_metrics`) also checks `import_result.line_error`.

See also [Common errors](#110-common-error-responses) (company not loaded, unknown request, Tally not running).

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `import` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `data` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `Vouchers` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svVchImportFormat]` | `<STATICVARIABLES><SVVCHIMPORTFORMAT>` | Yes (voucher import) | String | `jsonex` | Import format of vouchers: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `tallymessage[]` | `<TALLYMESSAGE>` | Yes | Array<Object> |  | The objects to import (masters or vouchers). One request can carry many objects. |
| `tallymessage[].metadata` | `<VOUCHER …>` attributes | Yes | Object |  | Object identity block: type, name/identifiers and action. |
| `tallymessage[].metadata.type` | element name `<VOUCHER>` | Yes | String | `Voucher` | Object type: `Ledger`, `Group`, `Stock Item`, `Stock Group`, `Unit`, `Voucher`. |
| `tallymessage[].metadata.remoteid` | `REMOTEID` attribute | Yes (alter/delete vch) | String (GUID) | `f0347998-2c19-4a5e-a4ed-01f589cb92a5-000…` | Voucher's REMOTEID as exported from Tally. Identifies the voucher to alter/delete. |
| `tallymessage[].metadata.vchkey` | `VCHKEY` attribute | Yes (alter/delete vch) | String | `f0347998-2c19-4a5e-a4ed-01f589cb92a5-000…` | Voucher's VCHKEY as exported from Tally. |
| `tallymessage[].metadata.vchtype` | `VCHTYPE` attribute | Yes (vouchers) | String | `Payment` | Voucher type name, e.g. `Payment`, `Receipt`, `Sales`, `Purchase`. |
| `tallymessage[].metadata.action` | `ACTION` attribute | Yes | String | `Alter` | `Create`, `Alter`, or `Delete` (case-insensitive). |
| `tallymessage[].metadata.objview` | `OBJVIEW` attribute | Yes (vouchers) | String | `Accounting Voucher View` | `Accounting Voucher View` (ledger-only vouchers) or `Invoice Voucher View` (item invoices). |
| `tallymessage[].date` | `<VOUCHER>/DATE` | Yes | Date (YYYYMMDD) | `20250801` | Voucher date. Must fall inside the company's books period (Educational Mode: only 1st, 2nd, 31st). |
| `tallymessage[].guid` | `<VOUCHER>/GUID` | Yes (alter/delete) | String (GUID) | `f0347998-2c19-4a5e-a4ed-01f589cb92a5-000…` | Tally GUID of the voucher; must match the existing voucher. |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Alter any Payment Voucher in the company and change the date to ‘1st September 2025’ | Change the value of Date tag, and set correct values for ‘guid’, ‘vchkey’, and ‘remoteid’ | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/payment/alter/json/TaskAlterPayment1stSept2025JSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/payment/alter/xml/TaskAlterPayment1stSept2025XML.txt) |
| Alter any Payment Voucher in the company and change the debit and credit amount values to ‘250’ | Change the value for all the amount tags, and set correct values for ‘guid’, ‘vchkey’, and ‘remoteid’ | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/payment/alter/json/TaskAlterPayment250JSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/payment/alter/xml/TaskAlterPayment250XMLtxt.txt) |

### 4.1.4 Delete a Payment

> Explorer id: `payment-delete` · Kind: **import** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#payment-delete)

#### Description

Each TallyPrime voucher has unique system-generated identifiers. To delete a voucher, ensure the ‘guid’, ‘vchkey’, and ‘remoteid’ match the existing voucher’s values, which can be obtained by exporting it in XML/JSON format from TallyPrime. In the sample request, provide the right values for these tags and attributes to experience the deletion of voucher.

**Integration use:** Reverse a payment voided upstream.

**Notes:**

- Identity must be on the object (`metadata.remoteid`, `metadata.vchkey` / XML attributes `REMOTEID`, `VCHKEY`) plus `guid`.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svVchImportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `import` | Yes |
| `type` | `data` | Yes |
| `id` | `Vouchers` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svVchImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Voucher",
        "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000095",
        "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b348:00000058",
        "vchtype": "Payment",
        "action": "Delete",
        "objview": "Accounting Voucher View"
      },
      "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000095"
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
 <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000095" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b348:00000058" VCHTYPE="Payment" ACTION="Delete" OBJVIEW="Accounting Voucher View">
  <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000095</GUID>
 </VOUCHER>
</TALLYMESSAGE>
</DESC>
</BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: import" \
  -H "type: data" \
  -H "id: Vouchers" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟢 Official shape: Tally's published voucher import response):

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 0,
            "deleted": 1,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 0,
            "vchnumber": 32
        }
    }
}
```

**Success — XML** (🔵 Observed: captured from a live TallyPrime in `docs/Tally_Vouchers_Integration_Guide.md`; `CMPINFO` truncated):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <CREATED>0</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>1</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>0</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
        <DESC>
            <CMPINFO>
                <COMPANY>0</COMPANY>
                <GROUP>0</GROUP>
                <LEDGER>95</LEDGER>
                <!-- … one count element per object type (COSTCENTRE, GODOWN, STOCKITEM, UNIT, VOUCHERTYPE, …) … -->
                <VOUCHER>39</VOUCHER>
            </CMPINFO>
        </DESC>
    </BODY>
</ENVELOPE>
```

Check `deleted` = 1 **and** `errors` + `exceptions` = 0. `status: "1"` only means the request was processed, not that the record was accepted. `lastvchid` is the internal id (MASTERID) of the last voucher written, and `vchnumber` is its voucher number.

#### Error Responses

**Record-level failure:** `Cannot delete unnamed object: VOUCHER!`. Source: 🔵 Observed.

Cause: The voucher identifiers were not sent on the object itself (`REMOTEID`/`VCHKEY` attributes in XML, `metadata.remoteid`/`metadata.vchkey` in JSON).

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <LINEERROR>Cannot delete unnamed object: VOUCHER!</LINEERROR>
                <CREATED>0</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>1</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
    </BODY>
</ENVELOPE>
```

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 1
        }
    }
}
```

> In JSON the failure shows up as non-zero `errors` / `exceptions` counts. Tally does not document the JSON key that carries the line-error text, so log the raw response body; this repo's parser (`parse_tally_response_metrics`) also checks `import_result.line_error`.

See also [Common errors](#110-common-error-responses) (company not loaded, unknown request, Tally not running).

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `import` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `data` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `Vouchers` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svVchImportFormat]` | `<STATICVARIABLES><SVVCHIMPORTFORMAT>` | Yes (voucher import) | String | `jsonex` | Import format of vouchers: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `tallymessage[]` | `<TALLYMESSAGE>` | Yes | Array<Object> |  | The objects to import (masters or vouchers). One request can carry many objects. |
| `tallymessage[].metadata` | `<VOUCHER …>` attributes | Yes | Object |  | Object identity block: type, name/identifiers and action. |
| `tallymessage[].metadata.type` | element name `<VOUCHER>` | Yes | String | `Voucher` | Object type: `Ledger`, `Group`, `Stock Item`, `Stock Group`, `Unit`, `Voucher`. |
| `tallymessage[].metadata.remoteid` | `REMOTEID` attribute | Yes (alter/delete vch) | String (GUID) | `f0347998-2c19-4a5e-a4ed-01f589cb92a5-000…` | Voucher's REMOTEID as exported from Tally. Identifies the voucher to alter/delete. |
| `tallymessage[].metadata.vchkey` | `VCHKEY` attribute | Yes (alter/delete vch) | String | `f0347998-2c19-4a5e-a4ed-01f589cb92a5-000…` | Voucher's VCHKEY as exported from Tally. |
| `tallymessage[].metadata.vchtype` | `VCHTYPE` attribute | Yes (vouchers) | String | `Payment` | Voucher type name, e.g. `Payment`, `Receipt`, `Sales`, `Purchase`. |
| `tallymessage[].metadata.action` | `ACTION` attribute | Yes | String | `Delete` | `Create`, `Alter`, or `Delete` (case-insensitive). |
| `tallymessage[].metadata.objview` | `OBJVIEW` attribute | Yes (vouchers) | String | `Accounting Voucher View` | `Accounting Voucher View` (ledger-only vouchers) or `Invoice Voucher View` (item invoices). |
| `tallymessage[].guid` | `<VOUCHER>/GUID` | Yes (alter/delete) | String (GUID) | `f0347998-2c19-4a5e-a4ed-01f589cb92a5-000…` | Tally GUID of the voucher; must match the existing voucher. |

### 4.1.5 Pull all Payment vouchers

> Explorer id: `payment-pull-all` · Kind: **collection** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#payment-pull-all)

#### Description

Details about multiple vouchers can be pulled using a TDL collection definition, which can already exist in the default source code or sent via the payload. TDL collection definition has type attribute that specifies the type of object that is grouped and fetch attribute that fetches the required methods.

**Integration use:** Read back all payments for reconciliation or to capture vouchers keyed directly in Tally.

**Notes:**

- `Type: Vouchers:VoucherType` + `Child Of: $$VchTypePayment` selects vouchers of the reserved Payment type (and types derived from it).

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svExportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVEXPORTFORMAT>XML</SVEXPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `export` | Yes |
| `type` | `collection` | Yes |
| `id` | `TSPLAllPaymentVouchers` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tdlmessage": [
    {
      "definitions": [
        {
          "metadata": {
            "name": "TSPL All Payment Vouchers",
            "type": "Collection"
          },
          "attributes": [
            {
              "Type": "Vouchers:VoucherType"
            },
            {
              "Child Of": "$$VchTypePayment"
            },
            {
              "Native Method": "Date, VoucherTypeName, VoucherNumber, partyledgername"
            }
          ]
        }
      ]
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Collection</TYPE>
        <ID>TSPL All Payment Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
           <TDL>
   <TDLMESSAGE>
  <COLLECTION NAME="TSPL All Payment Vouchers" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
   <TYPE>Vouchers:VoucherType</TYPE>
   <CHILDOF>$$VchTypePayment</CHILDOF>
   <NATIVEMETHOD>Date, VoucherTypeName, VoucherNumber, Partyledgername</NATIVEMETHOD>
   <NATIVEMETHOD>AllLedgerEntries.BankAllocations.*</NATIVEMETHOD>
  </COLLECTION>
</TDLMESSAGE>
</TDL>
        </DESC>
    </BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: export" \
  -H "type: collection" \
  -H "id: TSPLAllPaymentVouchers" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟡 Illustrative (structure follows Tally's published voucher-collection sample: `metadata.remoteid/vchkey`, typed fields, `cmp_dep_type`; values invented)):

```json
{
    "status": "1",
    "data": {
        "metadata": {
            "is_cmp_dep_type": true,
            "cmp_locus": 4,
            "cmp_dep_type": 64
        },
        "collection": [
            {
                "metadata": {
                    "type": "Voucher",
                    "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000091",
                    "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2b3:00000008",
                    "vchtype": "Payment",
                    "objview": "Accounting Voucher View"
                },
                "date": {
                    "type": "Date",
                    "value": "20250401"
                },
                "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000091",
                "vouchertypename": "Payment",
                "vouchernumber": "1",
                "partyledgername": {
                    "type": "String",
                    "value": "Akshaya Enterprises"
                },
                "masterid": {
                    "type": "Number",
                    "value": " 145"
                }
            },
            {
                "metadata": {
                    "type": "Voucher",
                    "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000092",
                    "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2b4:00000009",
                    "vchtype": "Payment",
                    "objview": "Accounting Voucher View"
                },
                "date": {
                    "type": "Date",
                    "value": "20250831"
                },
                "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000092",
                "vouchertypename": "Payment",
                "vouchernumber": "2",
                "partyledgername": {
                    "type": "String",
                    "value": "Akshaya Enterprises"
                },
                "masterid": {
                    "type": "Number",
                    "value": " 146"
                }
            }
        ]
    }
}
```

**Success — XML** (🟡 Illustrative):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DESC>
        </DESC>
        <DATA>
            <COLLECTION>
                <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000091" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2b3:00000008" VCHTYPE="Payment" OBJVIEW="Accounting Voucher View">
                    <DATE TYPE="Date">20250401</DATE>
                    <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000091</GUID>
                    <VOUCHERTYPENAME TYPE="String">Payment</VOUCHERTYPENAME>
                    <VOUCHERNUMBER TYPE="String">1</VOUCHERNUMBER>
                    <PARTYLEDGERNAME TYPE="String">Akshaya Enterprises</PARTYLEDGERNAME>
                    <MASTERID TYPE="Number"> 145</MASTERID>
                </VOUCHER>
                <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000092" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2b4:00000009" VCHTYPE="Payment" OBJVIEW="Accounting Voucher View">
                    <DATE TYPE="Date">20250831</DATE>
                    <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000092</GUID>
                    <VOUCHERTYPENAME TYPE="String">Payment</VOUCHERTYPENAME>
                    <VOUCHERNUMBER TYPE="String">2</VOUCHERNUMBER>
                    <PARTYLEDGERNAME TYPE="String">Akshaya Enterprises</PARTYLEDGERNAME>
                    <MASTERID TYPE="Number"> 146</MASTERID>
                </VOUCHER>
            </COLLECTION>
        </DATA>
    </BODY>
</ENVELOPE>
```

#### Error Responses

- **Collection name mismatch** (🟡 Illustrative): if the `id` header / `<ID>` does not match a default collection or a definition in `tdlmessage`, Tally returns an error instead of data. TDL names ignore case and spaces (`TSPL All Payment Vouchers` = `TSPLAllPaymentVouchers`), but any other spelling difference breaks the match.
- **Invalid TDL** (bad attribute or formula): Tally may show an error dialog on the Tally screen and return nothing useful. Validate TDL in the Explorer before shipping it.
- **Empty result:** a valid request that matches nothing returns `status: "1"` with an empty `collection` (`<COLLECTION/>`).
- [Common errors](#110-common-error-responses) apply.

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `export` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `collection` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `TSPLAllPaymentVouchers` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svExportFormat]` | `<STATICVARIABLES><SVEXPORTFORMAT>` | Yes (export) | String | `jsonex` | Response format: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `tdlmessage[]` | `<TDL><TDLMESSAGE>` | Cond. | Array<Object> |  | Inline TDL definitions (Collection / Report modification / System Formulae) that Tally loads before executing the request. |
| `tdlmessage[].definitions[]` | `<COLLECTION …>` | Cond. | Array<Object> |  | List of TDL definitions inside `tdlmessage`. |
| `tdlmessage[].definitions[].metadata.name` | `NAME` attribute | Yes | String | `TSPL All Payment Vouchers` | Definition name. For a Collection it must match the `id` header / `<ID>`. TDL names are case- and space-insensitive. |
| `tdlmessage[].definitions[].metadata.type` | element name | Yes | String | `Collection` | Definition kind: `Collection`, `Report`, or `System`. |
| `tdlmessage[].definitions[].attributes[].Type` | `<TYPE>` | Yes | String | `Vouchers:VoucherType` | Object type the collection gathers: `Ledger`, `Group`, `StockItem`, `StockGroup`, `Unit`, or `Vouchers:VoucherType` (vouchers of a voucher type). |
| `tdlmessage[].definitions[].attributes[].Child Of` | `<CHILDOF>` | No | String (TDL expr) | `$$VchTypePayment` | Restricts the collection to children of a parent. Accepts a literal (`"Gadgets"`) or a system-name function such as `$$GroupBank`, `$$GroupCurrentAssets`, `$$VchTypePayment`. |
| `tdlmessage[].definitions[].attributes[].Native Method` | `<NATIVEMETHOD>` | Yes | String (CSV) | `Date, VoucherTypeName, VoucherNumber, pa…` | Comma-separated methods to fetch for every object in the collection. |

### 4.1.6 Pull all Payment vouchers for a period

> Explorer id: `payment-pull-period` · Kind: **collection** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#payment-pull-period)

#### Description

Details about multiple vouchers of a vouchertype, with any filter, can be pulled using a TDL collection definition, which can already exist in the default source code or sent via the payload. TDL collection definition has type attribute that specifies the type of object that is grouped, and fetch attribute that fetches the required methods, Filter attribute that specifies any condition based on which the objects should be gathered.

**Integration use:** Incremental, date-bounded pull of payments, which is the building block of scheduled sync.

**Notes:**

- Edit the formula dates for incremental sync. `$$Date:"…"` accepts `1-Apr-2025` and `01-04-2025` styles.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svExportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVEXPORTFORMAT>XML</SVEXPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `export` | Yes |
| `type` | `collection` | Yes |
| `id` | `TSPLPaymentVouchers` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tdlmessage": [
    {
      "definitions": [
        {
          "metadata": {
            "name": "TSPL Payment Vouchers",
            "type": "Collection"
          },
          "attributes": [
            {
              "Type": "Vouchers:VoucherType"
            },
            {
              "Child Of": "$$VchTypePayment"
            },
            {
              "Native Method": "Date, VoucherTypeName, VoucherNumber, partyledgername"
            },
            {
              "Filters": "Period Filter"
            }
          ]
        },
        {
          "metadata": {
            "name": "PeriodFilter",
            "type": "System",
            "sys_type": "Formulae",
            "ismodify": true
          },
          "value": "$Date >= $$Date:\"1-Apr-2025\" AND $Date <= $$Date:\"10-Apr-2025\"" 
        }
      ]
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Collection</TYPE>
        <ID>TSPL Payment Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
           <TDL>
   <TDLMESSAGE>
  <COLLECTION NAME="TSPL Payment Vouchers" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
   <TYPE>Vouchers:VoucherType</TYPE>
   <CHILDOF>$$VchTypePayment</CHILDOF>
   <NATIVEMETHOD>Date, VoucherTypeName, VoucherNumber, Partyledgername</NATIVEMETHOD>
   <NATIVEMETHOD>AllLedgerEntries.BankAllocations.*</NATIVEMETHOD>
   <FILTERS>Period Filter</FILTERS>
  </COLLECTION>
  <SYSTEM TYPE="Formulae" NAME="PeriodFilter" ISMODIFY="Yes" ISFIXED="No" ISINTERNAL="No">$Date &gt;= ($$Date:&quot;01-04-2025&quot;) AND $Date &lt;= ($$Date:&quot;10-04-2025&quot;)  </SYSTEM>
</TDLMESSAGE>
</TDL>
        </DESC>
    </BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: export" \
  -H "type: collection" \
  -H "id: TSPLPaymentVouchers" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟡 Illustrative (structure follows Tally's published voucher-collection sample: `metadata.remoteid/vchkey`, typed fields, `cmp_dep_type`; values invented)):

```json
{
    "status": "1",
    "data": {
        "metadata": {
            "is_cmp_dep_type": true,
            "cmp_locus": 4,
            "cmp_dep_type": 64
        },
        "collection": [
            {
                "metadata": {
                    "type": "Voucher",
                    "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000091",
                    "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2b3:00000008",
                    "vchtype": "Payment",
                    "objview": "Accounting Voucher View"
                },
                "date": {
                    "type": "Date",
                    "value": "20250402"
                },
                "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000091",
                "vouchertypename": "Payment",
                "vouchernumber": "1",
                "partyledgername": {
                    "type": "String",
                    "value": "Akshaya Enterprises"
                },
                "masterid": {
                    "type": "Number",
                    "value": " 145"
                }
            },
            {
                "metadata": {
                    "type": "Voucher",
                    "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000092",
                    "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2b4:00000009",
                    "vchtype": "Payment",
                    "objview": "Accounting Voucher View"
                },
                "date": {
                    "type": "Date",
                    "value": "20250402"
                },
                "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000092",
                "vouchertypename": "Payment",
                "vouchernumber": "2",
                "partyledgername": {
                    "type": "String",
                    "value": "Akshaya Enterprises"
                },
                "masterid": {
                    "type": "Number",
                    "value": " 146"
                }
            }
        ]
    }
}
```

**Success — XML** (🟡 Illustrative):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DESC>
        </DESC>
        <DATA>
            <COLLECTION>
                <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000091" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2b3:00000008" VCHTYPE="Payment" OBJVIEW="Accounting Voucher View">
                    <DATE TYPE="Date">20250402</DATE>
                    <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000091</GUID>
                    <VOUCHERTYPENAME TYPE="String">Payment</VOUCHERTYPENAME>
                    <VOUCHERNUMBER TYPE="String">1</VOUCHERNUMBER>
                    <PARTYLEDGERNAME TYPE="String">Akshaya Enterprises</PARTYLEDGERNAME>
                    <MASTERID TYPE="Number"> 145</MASTERID>
                </VOUCHER>
                <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000092" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2b4:00000009" VCHTYPE="Payment" OBJVIEW="Accounting Voucher View">
                    <DATE TYPE="Date">20250402</DATE>
                    <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000092</GUID>
                    <VOUCHERTYPENAME TYPE="String">Payment</VOUCHERTYPENAME>
                    <VOUCHERNUMBER TYPE="String">2</VOUCHERNUMBER>
                    <PARTYLEDGERNAME TYPE="String">Akshaya Enterprises</PARTYLEDGERNAME>
                    <MASTERID TYPE="Number"> 146</MASTERID>
                </VOUCHER>
            </COLLECTION>
        </DATA>
    </BODY>
</ENVELOPE>
```

#### Error Responses

- **Collection name mismatch** (🟡 Illustrative): if the `id` header / `<ID>` does not match a default collection or a definition in `tdlmessage`, Tally returns an error instead of data. TDL names ignore case and spaces (`TSPL All Payment Vouchers` = `TSPLAllPaymentVouchers`), but any other spelling difference breaks the match.
- **Invalid TDL** (bad attribute or formula): Tally may show an error dialog on the Tally screen and return nothing useful. Validate TDL in the Explorer before shipping it.
- **Empty result:** a valid request that matches nothing returns `status: "1"` with an empty `collection` (`<COLLECTION/>`).
- [Common errors](#110-common-error-responses) apply.

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `export` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `collection` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `TSPLPaymentVouchers` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svExportFormat]` | `<STATICVARIABLES><SVEXPORTFORMAT>` | Yes (export) | String | `jsonex` | Response format: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `tdlmessage[]` | `<TDL><TDLMESSAGE>` | Cond. | Array<Object> |  | Inline TDL definitions (Collection / Report modification / System Formulae) that Tally loads before executing the request. |
| `tdlmessage[].definitions[]` | `<COLLECTION …>` | Cond. | Array<Object> |  | List of TDL definitions inside `tdlmessage`. |
| `tdlmessage[].definitions[].metadata.name` | `NAME` attribute | Yes | String | `TSPL Payment Vouchers` | Definition name. For a Collection it must match the `id` header / `<ID>`. TDL names are case- and space-insensitive. |
| `tdlmessage[].definitions[].metadata.type` | element name | Yes | String | `Collection` | Definition kind: `Collection`, `Report`, or `System`. |
| `tdlmessage[].definitions[].attributes[].Type` | `<TYPE>` | Yes | String | `Vouchers:VoucherType` | Object type the collection gathers: `Ledger`, `Group`, `StockItem`, `StockGroup`, `Unit`, or `Vouchers:VoucherType` (vouchers of a voucher type). |
| `tdlmessage[].definitions[].attributes[].Child Of` | `<CHILDOF>` | No | String (TDL expr) | `$$VchTypePayment` | Restricts the collection to children of a parent. Accepts a literal (`"Gadgets"`) or a system-name function such as `$$GroupBank`, `$$GroupCurrentAssets`, `$$VchTypePayment`. |
| `tdlmessage[].definitions[].attributes[].Native Method` | `<NATIVEMETHOD>` | Yes | String (CSV) | `Date, VoucherTypeName, VoucherNumber, pa…` | Comma-separated methods to fetch for every object in the collection. |
| `tdlmessage[].definitions[].attributes[].Filters` | `<FILTERS>` | No | String | `Period Filter` | Name of a System Formula used to filter the collection server-side. |
| `tdlmessage[].definitions[].metadata.sys_type` | `TYPE` attribute | Cond. | String | `Formulae` | For `type: System` only. `Formulae` declares named formulae used by `Filters`. |
| `tdlmessage[].definitions[].metadata.ismodify` | `ISMODIFY` attribute | No | Boolean | `true` | `true` modifies an existing (default) definition instead of declaring a new one (`#` / `ISMODIFY="Yes"` in XML). |
| `tdlmessage[].definitions[].value` | element text | Cond. | String (TDL expr) | `$Date >= $$Date:"1-Apr-2025" AND $Date <…` | Body of a System Formula, e.g. `$ClosingBalance = 0`. |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Fetch the Payment vouchers for a single date “2nd April 2025” | Change the value of the Filter Formula | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/payment/pull-period/json/TaskPullPayment2ndAprilJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/payment/pull-period/xml/TaskPullPayment2ndAprilXML.txt) |

## 4.2 Receipt

### 4.2.0 Receipt — Overview & Field Reference

> 🟢 Official: converted from the Explorer's "About Receipt" page.

A Receipt Voucher is used to record all incoming payments received by the business, whether through cash, bank, or other modes. It captures transactions where money is received from customers or other parties, ensuring proper tracking of cash inflow.

Each receipt impacts at least two ledgers typically debiting Cash/Bank and crediting the respective party or income ledger, maintaining accurate financial records.

| Tag | Mandatory | Data Type | Explanation |
|---|---|---|---|
| VoucherType Name | Yes | String | Defines the type of voucher under which the transaction is recorded. Since we want to create a receipt voucher, we would provide value as   Receipt. |
| Date | Yes | String | Indicates the transaction date in Tally-accepted format (YYYYMMDD). |
| VoucherNumber | Conditional | String | By default, Tally auto-generates voucher numbers. This tag is required only if you want to pass a custom voucher number from your system. |
| PartyLedgerName | Yes | String | Specifies the name of primary party or account involved in the transaction (e.g., customer, supplier, income ledger) |
| AllLedgerEntries | Yes | Collection | Collection of ledger entries forming the transaction; ensures debit and credit entries are captured |
| LedgerName | Yes | String | Name of the ledger affected in the transaction |
| IsDeemedPositive | Yes | Logical / Boolean | Determines whether the entry is treated as Debit (Yes) or Credit (No) |
| IsPartyLedger | Yes | Logical / Boolean | Indicates whether the ledger is the main party ledger in the transaction |
| Amount | Yes | Amount | Specifies the transaction amount |

**Sample — XML Format**

```xml
<ENVELOPE>
 <HEADER>
  <TALLYREQUEST>Import Data</TALLYREQUEST>
 </HEADER>
 <BODY>
  <IMPORTDATA>
    <TALLYMESSAGE xmlns:UDF="TallyUDF">
     <VOUCHER VCHTYPE="Receipt" ACTION="Create" OBJVIEW="Accounting Voucher View">
      <DATE>20260320</DATE>
      <COUNTRYOFRESIDENCE>India</COUNTRYOFRESIDENCE>
      <PLACEOFSUPPLY>Karnataka</PLACEOFSUPPLY>
      <VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>
      <PARTYNAME>Bank of Baroda</PARTYNAME>
      <PARTYLEDGERNAME>Bank of Baroda</PARTYLEDGERNAME>
      <VOUCHERNUMBER>32</VOUCHERNUMBER>
      <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
      <ALLLEDGERENTRIES.LIST>
       <LEDGERNAME>Advertising Expenses</LEDGERNAME>
       <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
       <ISPARTYLEDGER>No</ISPARTYLEDGER>
       <AMOUNT>1000000.00</AMOUNT>
      </ALLLEDGERENTRIES.LIST>
      <ALLLEDGERENTRIES.LIST>
       <LEDGERNAME>Bank of Baroda</LEDGERNAME>
       <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
       <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
       <AMOUNT>-1000000.00</AMOUNT>
       <BANKALLOCATIONS.LIST>
        <DATE>20260320</DATE>
        <INSTRUMENTDATE>20260320</INSTRUMENTDATE>
        <TRANSACTIONTYPE>Cheque</TRANSACTIONTYPE>
        <PAYMENTFAVOURING>Advertising Expenses</PAYMENTFAVOURING>
        <CHEQUECROSSCOMMENT>A/c Payee</CHEQUECROSSCOMMENT>
        <BANKPARTYNAME>Advertising Expenses</BANKPARTYNAME>
        <AMOUNT>1000000.00</AMOUNT>
       </BANKALLOCATIONS.LIST>
      </ALLLEDGERENTRIES.LIST>
     </VOUCHER>
    </TALLYMESSAGE>
  </IMPORTDATA>
 </BODY>
</ENVELOPE>

```

**Sample — JSON Format**

```json
{
  "static_variables": [
    {
      "name": "svMstImportFormat",
      "value": "jsonex"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Voucher",
        "action": "Create",
        "objectview": "Accounting Voucher View"
      },
      "DATE": "20260320",
      "VOUCHERTYPENAME": "Receipt",
      "VOUCHERNUMBER": "32",
      "PERSISTEDVIEW": "Accounting Voucher View",
      "PARTYLEDGERNAME": "Bank of Baroda",
      "PARTYNAME": "Bank of Baroda",
      "COUNTRYOFRESIDENCE": "India",
      "PLACEOFSUPPLY": "Karnataka",

      "ALLLEDGERENTRIES.LIST": [
        {
          "LEDGERNAME": "Advertising Expenses",
          "ISDEEMEDPOSITIVE": "No",
          "ISPARTYLEDGER": "No",
          "AMOUNT": 1000000
        },
        {
          "LEDGERNAME": "Bank of Baroda",
          "ISDEEMEDPOSITIVE": "Yes",
          "ISPARTYLEDGER": "Yes",
          "AMOUNT": -1000000,

          "BANKALLOCATIONS.LIST": [
            {
              "DATE": "20260320",
              "INSTRUMENTDATE": "20260320",
              "TRANSACTIONTYPE": "Cheque",
              "PAYMENTFAVOURING": "Advertising Expenses",
              "CHEQUECROSSCOMMENT": "A/c Payee",
              "BANKPARTYNAME": "Advertising Expenses",
              "AMOUNT": 1000000
            }
          ]
        }
      ]
    }
  ]
}

```

### 4.2.1 Create a Receipt with Banking Details

> Explorer id: `receipt-create` · Kind: **import** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#receipt-create)

#### Description

A Receipt Voucher can be created by providing VoucherType, Date, Debit and Credit ledger details with amount. A Receipt with Bank Details will typically have Bank Ledger debited and Party / Income Ledger credited. The voucher will have Banking details such as bank Name, IFSC Code, instrument number and so on depending on the mode of receipt. These details when sent in appropriate methods and collections of Voucher Object, creates a receipt voucher successfully.

**Integration use:** Post customer collections received in bank (cheque, NEFT, UPI) with banking details.

**Notes:**

- Bank line Debit (`isdeemedpositive: true`, negative amount); party line Credit (positive amount).

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svVchImportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `import` | Yes |
| `type` | `data` | Yes |
| `id` | `Vouchers` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svVchImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Voucher",
        "vchtype": "Receipt",
        "action": "Create",
        "objview": "Accounting Voucher View"
      },
      "date": "20250831",
      "vouchertypename": "Receipt",
      "partyledgername": "ABC Party",
      "allledgerentries": [
        {
          "ledgername": "ABC Party",
          "isdeemedpositive": false,
          "ispartyledger": true,
          "amount": "2500.00"
        },
        {
          "ledgername": "Kotak Bank",
          "isdeemedpositive": true,
          "ispartyledger": true,
          "amount": "-2500.00",
          "bankallocations": [
            {
              "date": "20250831",
              "instrumentdate": "20250831",
              "transactiontype": "Cheque/DD",
              "bankname": "Kotak Mahindra Bank (India)",
              "paymentfavouring": "ABC Party",
              "instrumentnumber": "56465787",
              "paymentmode": "Transacted",
              "bankpartyname": "ABC Party",
              "amount": "-2500.00"
            }
          ]
        }
      ]
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
 <VOUCHER VCHTYPE="Receipt" ACTION="Create" OBJVIEW="Accounting Voucher View">
  <DATE>20250831</DATE>
  <VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>
  <PARTYLEDGERNAME>ABC Party</PARTYLEDGERNAME>
  <ALLLEDGERENTRIES.LIST>
   <LEDGERNAME>ABC Party</LEDGERNAME>
   <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
   <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
   <AMOUNT>2500.00</AMOUNT>
  </ALLLEDGERENTRIES.LIST>
  <ALLLEDGERENTRIES.LIST>
   <LEDGERNAME>Kotak Bank</LEDGERNAME>
   <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
   <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
   <AMOUNT>-2500.00</AMOUNT>
   <BANKALLOCATIONS.LIST>
<DATE>20250831</DATE>
<INSTRUMENTDATE>20250831</INSTRUMENTDATE>
<TRANSACTIONTYPE>Cheque/DD</TRANSACTIONTYPE>
<BANKNAME>Kotak Mahindra Bank (India)</BANKNAME>
<PAYMENTFAVOURING>ABC Party</PAYMENTFAVOURING>
<INSTRUMENTNUMBER>56465787</INSTRUMENTNUMBER>
<PAYMENTMODE>Transacted</PAYMENTMODE>
<BANKPARTYNAME>ABC Party</BANKPARTYNAME>
<ISCONNECTEDPAYMENT>No</ISCONNECTEDPAYMENT>
<AMOUNT>-2500.00</AMOUNT>
   </BANKALLOCATIONS.LIST>
  </ALLLEDGERENTRIES.LIST>
 </VOUCHER>
</TALLYMESSAGE>
</DESC>
</BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: import" \
  -H "type: data" \
  -H "id: Vouchers" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟢 Official shape: Tally's published voucher import response):

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 1,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 71,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 0,
            "vchnumber": 33
        }
    }
}
```

**Success — XML** (🔵 Observed: captured from a live TallyPrime in `docs/Tally_Vouchers_Integration_Guide.md`; `CMPINFO` truncated):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <CREATED>1</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>71</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>0</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
        <DESC>
            <CMPINFO>
                <COMPANY>0</COMPANY>
                <GROUP>0</GROUP>
                <LEDGER>95</LEDGER>
                <!-- … one count element per object type (COSTCENTRE, GODOWN, STOCKITEM, UNIT, VOUCHERTYPE, …) … -->
                <VOUCHER>39</VOUCHER>
            </CMPINFO>
        </DESC>
    </BODY>
</ENVELOPE>
```

Check `created` = 1 **and** `errors` + `exceptions` = 0. `status: "1"` only means the request was processed, not that the record was accepted. `lastvchid` is the internal id (MASTERID) of the last voucher written, and `vchnumber` is its voucher number.

#### Error Responses

**Record-level failure:** `Ledger 'ABC Party' does not exist!`. Source: 🟡 Illustrative (message pattern also reported by other Tally integrations).

Cause: A ledger (or stock item / godown) referenced by the voucher is missing, or misspelt. Create masters before vouchers.

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <LINEERROR>Ledger &apos;ABC Party&apos; does not exist!</LINEERROR>
                <CREATED>0</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>1</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
    </BODY>
</ENVELOPE>
```

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 1
        }
    }
}
```

> In JSON the failure shows up as non-zero `errors` / `exceptions` counts. Tally does not document the JSON key that carries the line-error text, so log the raw response body; this repo's parser (`parse_tally_response_metrics`) also checks `import_result.line_error`.

See also [Common errors](#110-common-error-responses) (company not loaded, unknown request, Tally not running).

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `import` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `data` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `Vouchers` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svVchImportFormat]` | `<STATICVARIABLES><SVVCHIMPORTFORMAT>` | Yes (voucher import) | String | `jsonex` | Import format of vouchers: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `tallymessage[]` | `<TALLYMESSAGE>` | Yes | Array<Object> |  | The objects to import (masters or vouchers). One request can carry many objects. |
| `tallymessage[].metadata` | `<VOUCHER …>` attributes | Yes | Object |  | Object identity block: type, name/identifiers and action. |
| `tallymessage[].metadata.type` | element name `<VOUCHER>` | Yes | String | `Voucher` | Object type: `Ledger`, `Group`, `Stock Item`, `Stock Group`, `Unit`, `Voucher`. |
| `tallymessage[].metadata.vchtype` | `VCHTYPE` attribute | Yes (vouchers) | String | `Receipt` | Voucher type name, e.g. `Payment`, `Receipt`, `Sales`, `Purchase`. |
| `tallymessage[].metadata.action` | `ACTION` attribute | Yes | String | `Create` | `Create`, `Alter`, or `Delete` (case-insensitive). |
| `tallymessage[].metadata.objview` | `OBJVIEW` attribute | Yes (vouchers) | String | `Accounting Voucher View` | `Accounting Voucher View` (ledger-only vouchers) or `Invoice Voucher View` (item invoices). |
| `tallymessage[].date` | `<VOUCHER>/DATE` | Yes | Date (YYYYMMDD) | `20250831` | Voucher date. Must fall inside the company's books period (Educational Mode: only 1st, 2nd, 31st). |
| `tallymessage[].vouchertypename` | `<VOUCHER>/VOUCHERTYPENAME` | Yes | String | `Receipt` | Voucher type name, e.g. `Payment`. |
| `tallymessage[].partyledgername` | `<VOUCHER>/PARTYLEDGERNAME` | Yes | String | `ABC Party` | Primary party / account ledger of the voucher. |
| `tallymessage[].allledgerentries[]` | `<VOUCHER>/ALLLEDGERENTRIES.LIST` | Yes (acct view) | Array<Object> |  | Ledger lines of an Accounting-view voucher (`ALLLEDGERENTRIES.LIST`). |
| `tallymessage[].allledgerentries[].ledgername` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/LEDGERNAME` | Yes | String | `ABC Party` | Ledger affected by the line. Must already exist. |
| `tallymessage[].allledgerentries[].isdeemedpositive` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/ISDEEMEDPOSITIVE` | Yes | Logical | `false` | `Yes`/`true` = Debit, `No`/`false` = Credit. |
| `tallymessage[].allledgerentries[].ispartyledger` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/ISPARTYLEDGER` | Yes | Logical | `true` | `Yes` for the party/cash/bank line of the voucher. |
| `tallymessage[].allledgerentries[].amount` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/AMOUNT` | Yes | Amount | `2500.00` | Line amount. Sign convention: Debit lines negative, Credit lines positive; all lines must net to zero. |
| `tallymessage[].allledgerentries[].bankallocations[]` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/BANKALLOCATIONS.LIST` | Cond. | Array<Object> |  | Banking details for a bank-ledger line (`BANKALLOCATIONS.LIST`). Total must equal the bank line amount. |
| `tallymessage[].allledgerentries[].bankallocations[].date` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/BANKALLOCATIONS.LIST/DATE` | Yes | Date (YYYYMMDD) | `20250831` | Bank allocation date. |
| `tallymessage[].allledgerentries[].bankallocations[].instrumentdate` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/BANKALLOCATIONS.LIST/INSTRUMENTDATE` | No | Date (YYYYMMDD) | `20250831` | Cheque/instrument date. |
| `tallymessage[].allledgerentries[].bankallocations[].transactiontype` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/BANKALLOCATIONS.LIST/TRANSACTIONTYPE` | Yes | String | `Cheque/DD` | Mode: `Cheque`, `Cheque/DD`, `e-Fund Transfer`, `Inter Bank Transfer`, `Others`, etc. |
| `tallymessage[].allledgerentries[].bankallocations[].bankname` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/BANKALLOCATIONS.LIST/BANKNAME` | No | String | `Kotak Mahindra Bank (India)` | Counter-party bank name. |
| `tallymessage[].allledgerentries[].bankallocations[].paymentfavouring` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/BANKALLOCATIONS.LIST/PAYMENTFAVOURING` | No | String | `ABC Party` | Payee name (favouring). |
| `tallymessage[].allledgerentries[].bankallocations[].instrumentnumber` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/BANKALLOCATIONS.LIST/INSTRUMENTNUMBER` | No | String | `56465787` | Cheque / UTR / instrument number. |
| `tallymessage[].allledgerentries[].bankallocations[].paymentmode` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/BANKALLOCATIONS.LIST/PAYMENTMODE` | No | String | `Transacted` | `Transacted` or `Not Transacted`. |
| `tallymessage[].allledgerentries[].bankallocations[].bankpartyname` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/BANKALLOCATIONS.LIST/BANKPARTYNAME` | No | String | `ABC Party` | Counter-party name for the bank allocation. |
| `tallymessage[].allledgerentries[].bankallocations[].amount` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/BANKALLOCATIONS.LIST/AMOUNT` | Yes | Amount | `-2500.00` | Line amount. Sign convention: Debit lines negative, Credit lines positive; all lines must net to zero. |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Create a Receipt Voucher with same details but on date ‘1st August 2025” | Change the value of Date tags in voucher and bankallocations | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/receipt/create/json/TaskCreateReceiptJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/receipt/create/xml/TaskCreateReceiptXML.txt) |
| Create a Receipt Voucher on date ‘2nd August 2025’ with same ledgers and amount but with Bankallocations for UPI Payment | Change the value of Date tags in voucher and bankallocations. Add relevant methods in Bankallocations collections for UPI Payment | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/receipt/create/json/TaskCreateReceiptUPIJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/receipt/create/xml/TaskCreateReceiptUPIXML.txt) |

### 4.2.2 Create a Receipt with Cash Details

> Explorer id: `receipt-create-cash` · Kind: **import** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#receipt-create-cash)

#### Description

A Receipt Voucher can be created by providing VoucherType, Date, Debit and Credit ledger details with amount. A Receipt with Cash will typically have Cash Ledger debited and Party / Income Ledger credited. These details when sent in appropriate methods and collections of Voucher Object, creates a receipt voucher successfully.To create a Receipt Voucher manually in TallyPrime, .

**Integration use:** Post cash collections, optionally adjusted against a customer's bill reference.

**Notes:**

- Shows cost-centre allocation (`categoryallocations` → `costcentreallocations`) on an income line.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svVchImportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `import` | Yes |
| `type` | `data` | Yes |
| `id` | `Vouchers` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svVchImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Voucher",
        "vchtype": "Receipt",
        "action": "Create",
        "objview": "Accounting Voucher View"
      },
      "date": "20250831",
      "vouchertypename": "Receipt",
      "partyname": "Cash",
      "partyledgername": "Cash",
      "allledgerentries": [
        {
          "ledgername": "Income",
          "isdeemedpositive": false,
          "ispartyledger": false,
          "amount": "100.00",
          "categoryallocations": [
            {
              "category": "Primary Cost Category",
              "isdeemedpositive": false,
              "costcentreallocations": [
                {
                  "name": "CostName",
                  "amount": "100.00"
                }
              ]
            }
          ]
        },
        {
          "ledgername": "Cash",
          "isdeemedpositive": true,
          "ispartyledger": true,
          "amount": "-100.00"
        }
      ]
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
 <VOUCHER VCHTYPE="Receipt" ACTION="Create" OBJVIEW="Accounting Voucher View">
  <DATE>20250831</DATE>
  <VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>
  <PARTYNAME>Cash</PARTYNAME>
  <PARTYLEDGERNAME>Cash</PARTYLEDGERNAME>
  <ALLLEDGERENTRIES.LIST>
   <LEDGERNAME>Income</LEDGERNAME>
   <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
   <ISPARTYLEDGER>No</ISPARTYLEDGER>
   <AMOUNT>100.00</AMOUNT>
   <CATEGORYALLOCATIONS.LIST>
<CATEGORY>Primary Cost Category</CATEGORY>
<ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
<COSTCENTREALLOCATIONS.LIST>
 <NAME>CostName</NAME>
 <AMOUNT>100.00</AMOUNT>
</COSTCENTREALLOCATIONS.LIST>
   </CATEGORYALLOCATIONS.LIST>
  </ALLLEDGERENTRIES.LIST>
  <ALLLEDGERENTRIES.LIST>
   <LEDGERNAME>Cash</LEDGERNAME>
   <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
   <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
   <AMOUNT>-100.00</AMOUNT>
  </ALLLEDGERENTRIES.LIST>
 </VOUCHER>
</TALLYMESSAGE>
</DESC>
</BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: import" \
  -H "type: data" \
  -H "id: Vouchers" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟢 Official shape: Tally's published voucher import response):

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 1,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 71,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 0,
            "vchnumber": 33
        }
    }
}
```

**Success — XML** (🔵 Observed: captured from a live TallyPrime in `docs/Tally_Vouchers_Integration_Guide.md`; `CMPINFO` truncated):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <CREATED>1</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>71</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>0</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
        <DESC>
            <CMPINFO>
                <COMPANY>0</COMPANY>
                <GROUP>0</GROUP>
                <LEDGER>95</LEDGER>
                <!-- … one count element per object type (COSTCENTRE, GODOWN, STOCKITEM, UNIT, VOUCHERTYPE, …) … -->
                <VOUCHER>39</VOUCHER>
            </CMPINFO>
        </DESC>
    </BODY>
</ENVELOPE>
```

Check `created` = 1 **and** `errors` + `exceptions` = 0. `status: "1"` only means the request was processed, not that the record was accepted. `lastvchid` is the internal id (MASTERID) of the last voucher written, and `vchnumber` is its voucher number.

#### Error Responses

**Record-level failure:** `Ledger 'Income' does not exist!`. Source: 🟡 Illustrative (message pattern also reported by other Tally integrations).

Cause: A ledger (or stock item / godown) referenced by the voucher is missing, or misspelt. Create masters before vouchers.

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <LINEERROR>Ledger &apos;Income&apos; does not exist!</LINEERROR>
                <CREATED>0</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>1</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
    </BODY>
</ENVELOPE>
```

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 1
        }
    }
}
```

> In JSON the failure shows up as non-zero `errors` / `exceptions` counts. Tally does not document the JSON key that carries the line-error text, so log the raw response body; this repo's parser (`parse_tally_response_metrics`) also checks `import_result.line_error`.

See also [Common errors](#110-common-error-responses) (company not loaded, unknown request, Tally not running).

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `import` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `data` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `Vouchers` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svVchImportFormat]` | `<STATICVARIABLES><SVVCHIMPORTFORMAT>` | Yes (voucher import) | String | `jsonex` | Import format of vouchers: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `tallymessage[]` | `<TALLYMESSAGE>` | Yes | Array<Object> |  | The objects to import (masters or vouchers). One request can carry many objects. |
| `tallymessage[].metadata` | `<VOUCHER …>` attributes | Yes | Object |  | Object identity block: type, name/identifiers and action. |
| `tallymessage[].metadata.type` | element name `<VOUCHER>` | Yes | String | `Voucher` | Object type: `Ledger`, `Group`, `Stock Item`, `Stock Group`, `Unit`, `Voucher`. |
| `tallymessage[].metadata.vchtype` | `VCHTYPE` attribute | Yes (vouchers) | String | `Receipt` | Voucher type name, e.g. `Payment`, `Receipt`, `Sales`, `Purchase`. |
| `tallymessage[].metadata.action` | `ACTION` attribute | Yes | String | `Create` | `Create`, `Alter`, or `Delete` (case-insensitive). |
| `tallymessage[].metadata.objview` | `OBJVIEW` attribute | Yes (vouchers) | String | `Accounting Voucher View` | `Accounting Voucher View` (ledger-only vouchers) or `Invoice Voucher View` (item invoices). |
| `tallymessage[].date` | `<VOUCHER>/DATE` | Yes | Date (YYYYMMDD) | `20250831` | Voucher date. Must fall inside the company's books period (Educational Mode: only 1st, 2nd, 31st). |
| `tallymessage[].vouchertypename` | `<VOUCHER>/VOUCHERTYPENAME` | Yes | String | `Receipt` | Voucher type name, e.g. `Payment`. |
| `tallymessage[].partyname` | `<VOUCHER>/PARTYNAME` | No | String | `Cash` | Party name printed on the voucher. |
| `tallymessage[].partyledgername` | `<VOUCHER>/PARTYLEDGERNAME` | Yes | String | `Cash` | Primary party / account ledger of the voucher. |
| `tallymessage[].allledgerentries[]` | `<VOUCHER>/ALLLEDGERENTRIES.LIST` | Yes (acct view) | Array<Object> |  | Ledger lines of an Accounting-view voucher (`ALLLEDGERENTRIES.LIST`). |
| `tallymessage[].allledgerentries[].ledgername` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/LEDGERNAME` | Yes | String | `Income` | Ledger affected by the line. Must already exist. |
| `tallymessage[].allledgerentries[].isdeemedpositive` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/ISDEEMEDPOSITIVE` | Yes | Logical | `false` | `Yes`/`true` = Debit, `No`/`false` = Credit. |
| `tallymessage[].allledgerentries[].ispartyledger` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/ISPARTYLEDGER` | Yes | Logical | `false` | `Yes` for the party/cash/bank line of the voucher. |
| `tallymessage[].allledgerentries[].amount` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/AMOUNT` | Yes | Amount | `100.00` | Line amount. Sign convention: Debit lines negative, Credit lines positive; all lines must net to zero. |
| `tallymessage[].allledgerentries[].categoryallocations[]` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/CATEGORYALLOCATIONS.LIST` | Cond. | Array<Object> |  | Cost-category allocations (`CATEGORYALLOCATIONS.LIST`) for cost-centre-enabled ledgers. |
| `tallymessage[].allledgerentries[].categoryallocations[].category` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/CATEGORYALLOCATIONS.LIST/CATEGORY` | Yes | String | `Primary Cost Category` | Cost category name. |
| `tallymessage[].allledgerentries[].categoryallocations[].isdeemedpositive` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/CATEGORYALLOCATIONS.LIST/ISDEEMEDPOSITIVE` | Yes | Logical | `false` | `Yes`/`true` = Debit, `No`/`false` = Credit. |
| `tallymessage[].allledgerentries[].categoryallocations[].costcentreallocations[]` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/CATEGORYALLOCATIONS.LIST/COSTCENTREALLOCATIONS.LIST` | Cond. | Array<Object> |  | Cost-centre split inside a category (`COSTCENTREALLOCATIONS.LIST`). |
| `tallymessage[].allledgerentries[].categoryallocations[].costcentreallocations[].name` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/CATEGORYALLOCATIONS.LIST/COSTCENTREALLOCATIONS.LIST/NAME` | Yes | String | `CostName` | Object name; unique within the company for masters. |
| `tallymessage[].allledgerentries[].categoryallocations[].costcentreallocations[].amount` | `<VOUCHER>/ALLLEDGERENTRIES.LIST/CATEGORYALLOCATIONS.LIST/COSTCENTREALLOCATIONS.LIST/AMOUNT` | Yes | Amount | `100.00` | Line amount. Sign convention: Debit lines negative, Credit lines positive; all lines must net to zero. |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Create a Receipt Voucher with same ledgers but on date ‘1st August 2025” with amount 500 | Change the value of Date tag, and all the amount tags | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/receipt/create-cash/json/TaskCreateCashReceipt1stAugJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/receipt/create-cash/xml/TaskCreateCashReceipt1stAugXML.txt) |
| Create a Receipt Voucher on date ‘2nd august 2025’ with Party Ledger ‘ABC Party’ instead of Income ledger with Billallocations with ‘New Ref’, Bill Number ‘Bill30AugABC’, with the same amount | Change the value of Date tag. Replace Income Ledger with ABC Party and add Billallocations collections with relevant storages | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/receipt/create-cash/json/TaskCreateCashReceiptABCPartyJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/receipt/create-cash/xml/TaskCreateCashReceiptABCPartyXML.txt) |

### 4.2.3 Alter a Receipt

> Explorer id: `receipt-alter` · Kind: **import** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#receipt-alter)

#### Description

Each TallyPrime voucher has unique system-generated identifiers. To modify a voucher, ensure the ‘guid’, ‘vchkey’, and ‘remoteid’ match the existing voucher’s values, which can be obtained by exporting it in XML/JSON format from TallyPrime. In the sample request, provide the right values for these tags and attributes to experience the alteration of voucher.

**Integration use:** Correct a posted receipt while preserving its identity.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svVchImportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `import` | Yes |
| `type` | `data` | Yes |
| `id` | `Vouchers` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svVchImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Voucher",
        "vchtype": "Receipt",
        "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000006d",
        "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:000000d0",
        "action": "Alter",
        "objview": "Accounting Voucher View"
      },
      "date": "20250801",
      "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000006d"
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
 <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000006b" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:000000d0" VCHTYPE="Receipt" ACTION="Alter" OBJVIEW="Accounting Voucher View">
  <DATE>20250801</DATE>
  <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000006b</GUID>
 </VOUCHER>
</TALLYMESSAGE>
</DESC>
</BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: import" \
  -H "type: data" \
  -H "id: Vouchers" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟢 Official shape: Tally's published voucher import response):

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 1,
            "deleted": 0,
            "lastvchid": 71,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 0,
            "vchnumber": 32
        }
    }
}
```

**Success — XML** (🔵 Observed: captured from a live TallyPrime in `docs/Tally_Vouchers_Integration_Guide.md`; `CMPINFO` truncated):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <CREATED>0</CREATED>
                <ALTERED>1</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>71</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>0</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
        <DESC>
            <CMPINFO>
                <COMPANY>0</COMPANY>
                <GROUP>0</GROUP>
                <LEDGER>95</LEDGER>
                <!-- … one count element per object type (COSTCENTRE, GODOWN, STOCKITEM, UNIT, VOUCHERTYPE, …) … -->
                <VOUCHER>39</VOUCHER>
            </CMPINFO>
        </DESC>
    </BODY>
</ENVELOPE>
```

Check `altered` = 1 **and** `errors` + `exceptions` = 0. `status: "1"` only means the request was processed, not that the record was accepted. `lastvchid` is the internal id (MASTERID) of the last voucher written, and `vchnumber` is its voucher number.

#### Error Responses

**Record-level failure:** `Voucher does not exist!`. Source: 🔵 Observed.

Cause: `remoteid` / `vchkey` / `guid` do not match any voucher in the company (e.g. ids copied from another company or the voucher was deleted).

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <LINEERROR>Voucher does not exist!</LINEERROR>
                <CREATED>0</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>1</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
    </BODY>
</ENVELOPE>
```

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 1
        }
    }
}
```

> In JSON the failure shows up as non-zero `errors` / `exceptions` counts. Tally does not document the JSON key that carries the line-error text, so log the raw response body; this repo's parser (`parse_tally_response_metrics`) also checks `import_result.line_error`.

See also [Common errors](#110-common-error-responses) (company not loaded, unknown request, Tally not running).

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `import` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `data` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `Vouchers` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svVchImportFormat]` | `<STATICVARIABLES><SVVCHIMPORTFORMAT>` | Yes (voucher import) | String | `jsonex` | Import format of vouchers: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `tallymessage[]` | `<TALLYMESSAGE>` | Yes | Array<Object> |  | The objects to import (masters or vouchers). One request can carry many objects. |
| `tallymessage[].metadata` | `<VOUCHER …>` attributes | Yes | Object |  | Object identity block: type, name/identifiers and action. |
| `tallymessage[].metadata.type` | element name `<VOUCHER>` | Yes | String | `Voucher` | Object type: `Ledger`, `Group`, `Stock Item`, `Stock Group`, `Unit`, `Voucher`. |
| `tallymessage[].metadata.vchtype` | `VCHTYPE` attribute | Yes (vouchers) | String | `Receipt` | Voucher type name, e.g. `Payment`, `Receipt`, `Sales`, `Purchase`. |
| `tallymessage[].metadata.remoteid` | `REMOTEID` attribute | Yes (alter/delete vch) | String (GUID) | `f0347998-2c19-4a5e-a4ed-01f589cb92a5-000…` | Voucher's REMOTEID as exported from Tally. Identifies the voucher to alter/delete. |
| `tallymessage[].metadata.vchkey` | `VCHKEY` attribute | Yes (alter/delete vch) | String | `f0347998-2c19-4a5e-a4ed-01f589cb92a5-000…` | Voucher's VCHKEY as exported from Tally. |
| `tallymessage[].metadata.action` | `ACTION` attribute | Yes | String | `Alter` | `Create`, `Alter`, or `Delete` (case-insensitive). |
| `tallymessage[].metadata.objview` | `OBJVIEW` attribute | Yes (vouchers) | String | `Accounting Voucher View` | `Accounting Voucher View` (ledger-only vouchers) or `Invoice Voucher View` (item invoices). |
| `tallymessage[].date` | `<VOUCHER>/DATE` | Yes | Date (YYYYMMDD) | `20250801` | Voucher date. Must fall inside the company's books period (Educational Mode: only 1st, 2nd, 31st). |
| `tallymessage[].guid` | `<VOUCHER>/GUID` | Yes (alter/delete) | String (GUID) | `f0347998-2c19-4a5e-a4ed-01f589cb92a5-000…` | Tally GUID of the voucher; must match the existing voucher. |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Alter any Receipt Voucher in the company and change the date to ‘1st September 2025’ | Change the value of Date tag, and set correct values for ‘guid’, ‘vchkey’, and ‘remoteid’ | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/receipt/alter/json/TaskAlterReceipt1SeptJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/receipt/alter/xml/TaskAlterReceipt1SeptXML.txt) |
| Alter any Receipt Voucher in the company and change the debit and credit amount values to ‘250’ | Change the value for all the amount tags, and set correct values for ‘guid’, ‘vchkey’, and ‘remoteid’ | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/receipt/alter/json/TaskAlterReceiptAmountJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/receipt/alter/xml/TaskAlterReceiptAmountXML.txt) |

### 4.2.4 Delete a Receipt

> Explorer id: `receipt-delete` · Kind: **import** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#receipt-delete)

#### Description

Each TallyPrime voucher has unique system-generated identifiers. To delete a voucher, ensure the ‘guid’, ‘vchkey’, and ‘remoteid’ match the existing voucher’s values, which can be obtained by exporting it in XML/JSON format from TallyPrime. In the sample request, provide the right values for these tags and attributes to experience the deletion of voucher.

**Integration use:** Reverse a receipt voided upstream.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svVchImportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `import` | Yes |
| `type` | `data` | Yes |
| `id` | `Vouchers` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svVchImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Voucher",
        "vchtype": "Receipt",
        "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000006d",
        "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:000000d0",
        "action": "Delete",
        "objview": "Accounting Voucher View"
      },
      "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000006d"
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
 <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000006b" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:000000d0" VCHTYPE="Receipt" ACTION="Delete" OBJVIEW="Accounting Voucher View">
  <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000006b</GUID>
 </VOUCHER>
</TALLYMESSAGE>
</DESC>
</BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: import" \
  -H "type: data" \
  -H "id: Vouchers" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟢 Official shape: Tally's published voucher import response):

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 0,
            "deleted": 1,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 0,
            "vchnumber": 32
        }
    }
}
```

**Success — XML** (🔵 Observed: captured from a live TallyPrime in `docs/Tally_Vouchers_Integration_Guide.md`; `CMPINFO` truncated):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <CREATED>0</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>1</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>0</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
        <DESC>
            <CMPINFO>
                <COMPANY>0</COMPANY>
                <GROUP>0</GROUP>
                <LEDGER>95</LEDGER>
                <!-- … one count element per object type (COSTCENTRE, GODOWN, STOCKITEM, UNIT, VOUCHERTYPE, …) … -->
                <VOUCHER>39</VOUCHER>
            </CMPINFO>
        </DESC>
    </BODY>
</ENVELOPE>
```

Check `deleted` = 1 **and** `errors` + `exceptions` = 0. `status: "1"` only means the request was processed, not that the record was accepted. `lastvchid` is the internal id (MASTERID) of the last voucher written, and `vchnumber` is its voucher number.

#### Error Responses

**Record-level failure:** `Cannot delete unnamed object: VOUCHER!`. Source: 🔵 Observed.

Cause: The voucher identifiers were not sent on the object itself (`REMOTEID`/`VCHKEY` attributes in XML, `metadata.remoteid`/`metadata.vchkey` in JSON).

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <LINEERROR>Cannot delete unnamed object: VOUCHER!</LINEERROR>
                <CREATED>0</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>1</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
    </BODY>
</ENVELOPE>
```

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 1
        }
    }
}
```

> In JSON the failure shows up as non-zero `errors` / `exceptions` counts. Tally does not document the JSON key that carries the line-error text, so log the raw response body; this repo's parser (`parse_tally_response_metrics`) also checks `import_result.line_error`.

See also [Common errors](#110-common-error-responses) (company not loaded, unknown request, Tally not running).

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `import` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `data` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `Vouchers` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svVchImportFormat]` | `<STATICVARIABLES><SVVCHIMPORTFORMAT>` | Yes (voucher import) | String | `jsonex` | Import format of vouchers: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `tallymessage[]` | `<TALLYMESSAGE>` | Yes | Array<Object> |  | The objects to import (masters or vouchers). One request can carry many objects. |
| `tallymessage[].metadata` | `<VOUCHER …>` attributes | Yes | Object |  | Object identity block: type, name/identifiers and action. |
| `tallymessage[].metadata.type` | element name `<VOUCHER>` | Yes | String | `Voucher` | Object type: `Ledger`, `Group`, `Stock Item`, `Stock Group`, `Unit`, `Voucher`. |
| `tallymessage[].metadata.vchtype` | `VCHTYPE` attribute | Yes (vouchers) | String | `Receipt` | Voucher type name, e.g. `Payment`, `Receipt`, `Sales`, `Purchase`. |
| `tallymessage[].metadata.remoteid` | `REMOTEID` attribute | Yes (alter/delete vch) | String (GUID) | `f0347998-2c19-4a5e-a4ed-01f589cb92a5-000…` | Voucher's REMOTEID as exported from Tally. Identifies the voucher to alter/delete. |
| `tallymessage[].metadata.vchkey` | `VCHKEY` attribute | Yes (alter/delete vch) | String | `f0347998-2c19-4a5e-a4ed-01f589cb92a5-000…` | Voucher's VCHKEY as exported from Tally. |
| `tallymessage[].metadata.action` | `ACTION` attribute | Yes | String | `Delete` | `Create`, `Alter`, or `Delete` (case-insensitive). |
| `tallymessage[].metadata.objview` | `OBJVIEW` attribute | Yes (vouchers) | String | `Accounting Voucher View` | `Accounting Voucher View` (ledger-only vouchers) or `Invoice Voucher View` (item invoices). |
| `tallymessage[].guid` | `<VOUCHER>/GUID` | Yes (alter/delete) | String (GUID) | `f0347998-2c19-4a5e-a4ed-01f589cb92a5-000…` | Tally GUID of the voucher; must match the existing voucher. |

### 4.2.5 Pull all Receipt vouchers

> Explorer id: `receipt-pull-all` · Kind: **collection** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#receipt-pull-all)

#### Description

Details about multiple vouchers can be pulled using a TDL collection definition, which can already exist in the default source code or sent via the payload. TDL collection definition has type attribute that specifies the type of object that is grouped and fetch attribute that fetches the required methods.

**Integration use:** Pull all receipts for receivables reconciliation.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svExportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVEXPORTFORMAT>XML</SVEXPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `export` | Yes |
| `type` | `collection` | Yes |
| `id` | `TSPL All Receipt Vouchers` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tdlmessage": [
    {
      "definitions": [
        {
          "metadata": {
            "name": "TSPL All Receipt Vouchers",
            "type": "Collection"
          },
          "attributes": [
            {
              "Type": "Vouchers:VoucherType"
            },
            {
              "Child Of": "$$VchTypeReceipt"
            },
            {
              "Native Method": "Date, VoucherTypeName, VoucherNumber, Partyledgername"
            }
          ]
        }
      ]
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Collection</TYPE>
        <ID>TSPL All Receipt Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
<TDL>
<TDLMESSAGE>
  <COLLECTION NAME="TSPL All Receipt Vouchers" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
   <TYPE>Vouchers:VoucherType</TYPE>
   <CHILDOF>$$VchTypeReceipt</CHILDOF>
   <NATIVEMETHOD>Date, VoucherTypeName, VoucherNumber, Partyledgername</NATIVEMETHOD>
  </COLLECTION>
</TDLMESSAGE>
</TDL>
        </DESC>
    </BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: export" \
  -H "type: collection" \
  -H "id: TSPL All Receipt Vouchers" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟡 Illustrative (structure follows Tally's published voucher-collection sample: `metadata.remoteid/vchkey`, typed fields, `cmp_dep_type`; values invented)):

```json
{
    "status": "1",
    "data": {
        "metadata": {
            "is_cmp_dep_type": true,
            "cmp_locus": 4,
            "cmp_dep_type": 64
        },
        "collection": [
            {
                "metadata": {
                    "type": "Voucher",
                    "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000091",
                    "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2b3:00000008",
                    "vchtype": "Receipt",
                    "objview": "Accounting Voucher View"
                },
                "date": {
                    "type": "Date",
                    "value": "20250401"
                },
                "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000091",
                "vouchertypename": "Receipt",
                "vouchernumber": "1",
                "partyledgername": {
                    "type": "String",
                    "value": "ABC Party"
                },
                "masterid": {
                    "type": "Number",
                    "value": " 145"
                }
            },
            {
                "metadata": {
                    "type": "Voucher",
                    "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000092",
                    "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2b4:00000009",
                    "vchtype": "Receipt",
                    "objview": "Accounting Voucher View"
                },
                "date": {
                    "type": "Date",
                    "value": "20250831"
                },
                "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000092",
                "vouchertypename": "Receipt",
                "vouchernumber": "2",
                "partyledgername": {
                    "type": "String",
                    "value": "ABC Party"
                },
                "masterid": {
                    "type": "Number",
                    "value": " 146"
                }
            }
        ]
    }
}
```

**Success — XML** (🟡 Illustrative):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DESC>
        </DESC>
        <DATA>
            <COLLECTION>
                <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000091" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2b3:00000008" VCHTYPE="Receipt" OBJVIEW="Accounting Voucher View">
                    <DATE TYPE="Date">20250401</DATE>
                    <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000091</GUID>
                    <VOUCHERTYPENAME TYPE="String">Receipt</VOUCHERTYPENAME>
                    <VOUCHERNUMBER TYPE="String">1</VOUCHERNUMBER>
                    <PARTYLEDGERNAME TYPE="String">ABC Party</PARTYLEDGERNAME>
                    <MASTERID TYPE="Number"> 145</MASTERID>
                </VOUCHER>
                <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000092" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2b4:00000009" VCHTYPE="Receipt" OBJVIEW="Accounting Voucher View">
                    <DATE TYPE="Date">20250831</DATE>
                    <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000092</GUID>
                    <VOUCHERTYPENAME TYPE="String">Receipt</VOUCHERTYPENAME>
                    <VOUCHERNUMBER TYPE="String">2</VOUCHERNUMBER>
                    <PARTYLEDGERNAME TYPE="String">ABC Party</PARTYLEDGERNAME>
                    <MASTERID TYPE="Number"> 146</MASTERID>
                </VOUCHER>
            </COLLECTION>
        </DATA>
    </BODY>
</ENVELOPE>
```

#### Error Responses

- **Collection name mismatch** (🟡 Illustrative): if the `id` header / `<ID>` does not match a default collection or a definition in `tdlmessage`, Tally returns an error instead of data. TDL names ignore case and spaces (`TSPL All Payment Vouchers` = `TSPLAllPaymentVouchers`), but any other spelling difference breaks the match.
- **Invalid TDL** (bad attribute or formula): Tally may show an error dialog on the Tally screen and return nothing useful. Validate TDL in the Explorer before shipping it.
- **Empty result:** a valid request that matches nothing returns `status: "1"` with an empty `collection` (`<COLLECTION/>`).
- [Common errors](#110-common-error-responses) apply.

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `export` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `collection` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `TSPL All Receipt Vouchers` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svExportFormat]` | `<STATICVARIABLES><SVEXPORTFORMAT>` | Yes (export) | String | `jsonex` | Response format: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `tdlmessage[]` | `<TDL><TDLMESSAGE>` | Cond. | Array<Object> |  | Inline TDL definitions (Collection / Report modification / System Formulae) that Tally loads before executing the request. |
| `tdlmessage[].definitions[]` | `<COLLECTION …>` | Cond. | Array<Object> |  | List of TDL definitions inside `tdlmessage`. |
| `tdlmessage[].definitions[].metadata.name` | `NAME` attribute | Yes | String | `TSPL All Receipt Vouchers` | Definition name. For a Collection it must match the `id` header / `<ID>`. TDL names are case- and space-insensitive. |
| `tdlmessage[].definitions[].metadata.type` | element name | Yes | String | `Collection` | Definition kind: `Collection`, `Report`, or `System`. |
| `tdlmessage[].definitions[].attributes[].Type` | `<TYPE>` | Yes | String | `Vouchers:VoucherType` | Object type the collection gathers: `Ledger`, `Group`, `StockItem`, `StockGroup`, `Unit`, or `Vouchers:VoucherType` (vouchers of a voucher type). |
| `tdlmessage[].definitions[].attributes[].Child Of` | `<CHILDOF>` | No | String (TDL expr) | `$$VchTypeReceipt` | Restricts the collection to children of a parent. Accepts a literal (`"Gadgets"`) or a system-name function such as `$$GroupBank`, `$$GroupCurrentAssets`, `$$VchTypePayment`. |
| `tdlmessage[].definitions[].attributes[].Native Method` | `<NATIVEMETHOD>` | Yes | String (CSV) | `Date, VoucherTypeName, VoucherNumber, Pa…` | Comma-separated methods to fetch for every object in the collection. |

### 4.2.6 Pull all Receipt vouchers for a period

> Explorer id: `receipt-pull-period` · Kind: **collection** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#receipt-pull-period)

#### Description

Details about multiple vouchers of a vouchertype, with any filter, can be pulled using a TDL collection definition, which can already exist in the default source code or sent via the payload. TDL collection definition has type attribute that specifies the type of object that is grouped, and fetch attribute that fetches the required methods, Filter attribute that specifies any condition based on which the objects should be gathered.

**Integration use:** Date-bounded incremental pull of receipts.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svExportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVEXPORTFORMAT>XML</SVEXPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `export` | Yes |
| `type` | `collection` | Yes |
| `id` | `TSPL Receipt Vouchers` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tdlmessage": [
    {
      "definitions": [
        {
          "metadata": {
            "name": "TSPL Receipt Vouchers",
            "type": "Collection"
          },
          "attributes": [
            {
              "Type": "Vouchers:VoucherType"
            },
            {
              "Child Of": "$$VchTypeReceipt"
            },
            {
              "Native Method": "Date, VoucherTypeName, VoucherNumber, Partyledgername"
            },
            {
              "Filters": "Period Filter"
            }
          ]
        },
        {
          "metadata": {
            "name": "PeriodFilter",
            "type": "System",
            "sys_type": "Formulae",
            "ismodify": true
          },
          "value": "$Date >= ($$Date:\"01-07-2025\") AND $Date <= ($$Date:\"10-07-2025\")"
        }
      ]
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Collection</TYPE>
        <ID>TSPL Receipt Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
<TDL>
<TDLMESSAGE>
  <COLLECTION NAME="TSPL Receipt Vouchers" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
   <TYPE>Vouchers:VoucherType</TYPE>
   <CHILDOF>$$VchTypeReceipt</CHILDOF>
   <NATIVEMETHOD>Date, VoucherTypeName, VoucherNumber, Partyledgername</NATIVEMETHOD>
   <FILTERS>Period Filter</FILTERS>
  </COLLECTION>
  <SYSTEM TYPE="Formulae" NAME="PeriodFilter" ISMODIFY="Yes" ISFIXED="No" ISINTERNAL="No">$Date &gt;= ($$Date:&quot;01-07-2025&quot;) AND $Date &lt;= ($$Date:&quot;10-07-2025&quot;)  </SYSTEM>
</TDLMESSAGE>
</TDL>
        </DESC>
    </BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: export" \
  -H "type: collection" \
  -H "id: TSPL Receipt Vouchers" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟡 Illustrative (structure follows Tally's published voucher-collection sample: `metadata.remoteid/vchkey`, typed fields, `cmp_dep_type`; values invented)):

```json
{
    "status": "1",
    "data": {
        "metadata": {
            "is_cmp_dep_type": true,
            "cmp_locus": 4,
            "cmp_dep_type": 64
        },
        "collection": [
            {
                "metadata": {
                    "type": "Voucher",
                    "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000091",
                    "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2b3:00000008",
                    "vchtype": "Receipt",
                    "objview": "Accounting Voucher View"
                },
                "date": {
                    "type": "Date",
                    "value": "20250402"
                },
                "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000091",
                "vouchertypename": "Receipt",
                "vouchernumber": "1",
                "partyledgername": {
                    "type": "String",
                    "value": "ABC Party"
                },
                "masterid": {
                    "type": "Number",
                    "value": " 145"
                }
            },
            {
                "metadata": {
                    "type": "Voucher",
                    "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000092",
                    "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2b4:00000009",
                    "vchtype": "Receipt",
                    "objview": "Accounting Voucher View"
                },
                "date": {
                    "type": "Date",
                    "value": "20250402"
                },
                "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000092",
                "vouchertypename": "Receipt",
                "vouchernumber": "2",
                "partyledgername": {
                    "type": "String",
                    "value": "ABC Party"
                },
                "masterid": {
                    "type": "Number",
                    "value": " 146"
                }
            }
        ]
    }
}
```

**Success — XML** (🟡 Illustrative):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DESC>
        </DESC>
        <DATA>
            <COLLECTION>
                <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000091" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2b3:00000008" VCHTYPE="Receipt" OBJVIEW="Accounting Voucher View">
                    <DATE TYPE="Date">20250402</DATE>
                    <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000091</GUID>
                    <VOUCHERTYPENAME TYPE="String">Receipt</VOUCHERTYPENAME>
                    <VOUCHERNUMBER TYPE="String">1</VOUCHERNUMBER>
                    <PARTYLEDGERNAME TYPE="String">ABC Party</PARTYLEDGERNAME>
                    <MASTERID TYPE="Number"> 145</MASTERID>
                </VOUCHER>
                <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000092" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2b4:00000009" VCHTYPE="Receipt" OBJVIEW="Accounting Voucher View">
                    <DATE TYPE="Date">20250402</DATE>
                    <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000092</GUID>
                    <VOUCHERTYPENAME TYPE="String">Receipt</VOUCHERTYPENAME>
                    <VOUCHERNUMBER TYPE="String">2</VOUCHERNUMBER>
                    <PARTYLEDGERNAME TYPE="String">ABC Party</PARTYLEDGERNAME>
                    <MASTERID TYPE="Number"> 146</MASTERID>
                </VOUCHER>
            </COLLECTION>
        </DATA>
    </BODY>
</ENVELOPE>
```

#### Error Responses

- **Collection name mismatch** (🟡 Illustrative): if the `id` header / `<ID>` does not match a default collection or a definition in `tdlmessage`, Tally returns an error instead of data. TDL names ignore case and spaces (`TSPL All Payment Vouchers` = `TSPLAllPaymentVouchers`), but any other spelling difference breaks the match.
- **Invalid TDL** (bad attribute or formula): Tally may show an error dialog on the Tally screen and return nothing useful. Validate TDL in the Explorer before shipping it.
- **Empty result:** a valid request that matches nothing returns `status: "1"` with an empty `collection` (`<COLLECTION/>`).
- [Common errors](#110-common-error-responses) apply.

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `export` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `collection` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `TSPL Receipt Vouchers` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svExportFormat]` | `<STATICVARIABLES><SVEXPORTFORMAT>` | Yes (export) | String | `jsonex` | Response format: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `tdlmessage[]` | `<TDL><TDLMESSAGE>` | Cond. | Array<Object> |  | Inline TDL definitions (Collection / Report modification / System Formulae) that Tally loads before executing the request. |
| `tdlmessage[].definitions[]` | `<COLLECTION …>` | Cond. | Array<Object> |  | List of TDL definitions inside `tdlmessage`. |
| `tdlmessage[].definitions[].metadata.name` | `NAME` attribute | Yes | String | `TSPL Receipt Vouchers` | Definition name. For a Collection it must match the `id` header / `<ID>`. TDL names are case- and space-insensitive. |
| `tdlmessage[].definitions[].metadata.type` | element name | Yes | String | `Collection` | Definition kind: `Collection`, `Report`, or `System`. |
| `tdlmessage[].definitions[].attributes[].Type` | `<TYPE>` | Yes | String | `Vouchers:VoucherType` | Object type the collection gathers: `Ledger`, `Group`, `StockItem`, `StockGroup`, `Unit`, or `Vouchers:VoucherType` (vouchers of a voucher type). |
| `tdlmessage[].definitions[].attributes[].Child Of` | `<CHILDOF>` | No | String (TDL expr) | `$$VchTypeReceipt` | Restricts the collection to children of a parent. Accepts a literal (`"Gadgets"`) or a system-name function such as `$$GroupBank`, `$$GroupCurrentAssets`, `$$VchTypePayment`. |
| `tdlmessage[].definitions[].attributes[].Native Method` | `<NATIVEMETHOD>` | Yes | String (CSV) | `Date, VoucherTypeName, VoucherNumber, Pa…` | Comma-separated methods to fetch for every object in the collection. |
| `tdlmessage[].definitions[].attributes[].Filters` | `<FILTERS>` | No | String | `Period Filter` | Name of a System Formula used to filter the collection server-side. |
| `tdlmessage[].definitions[].metadata.sys_type` | `TYPE` attribute | Cond. | String | `Formulae` | For `type: System` only. `Formulae` declares named formulae used by `Filters`. |
| `tdlmessage[].definitions[].metadata.ismodify` | `ISMODIFY` attribute | No | Boolean | `true` | `true` modifies an existing (default) definition instead of declaring a new one (`#` / `ISMODIFY="Yes"` in XML). |
| `tdlmessage[].definitions[].value` | element text | Cond. | String (TDL expr) | `$Date >= ($$Date:"01-07-2025") AND $Date…` | Body of a System Formula, e.g. `$ClosingBalance = 0`. |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Fetch the Receipt vouchers for a single date “1st April 2025” | Change the value of the Filter Formula | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/receipt/pull-period/json/TaskPullReceiptFor1stApril2025JSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/receipt/pull-period/xml/TaskPullReceiptFor1stApril2025XML.txt) |

## 4.3 Sales

### 4.3.0 Sales — Overview & Field Reference

> 🟢 Official: converted from the Explorer's "About Sales" page.

A Sales Voucher is used to record all sales transactions of goods or services made by the business. It captures details such as the party involved, items sold, quantities, rates, and applicable taxes, ensuring proper tracking of revenue and stock movement.

Each sales transaction impacts at least two ledgers—typically debiting the customer (party) ledger and crediting the sales ledger, along with affecting inventory for the items sold, thereby maintaining accurate financial and stock records.

| Tag | Mandatory | Data Type | Explanation |
|---|---|---|---|
| VoucherType Name | Yes | String | Defines the type of voucher under which the transaction is recorded. Since we want to create a sales voucher, we would provide value as   Sales. |
| Date | Yes | String | Indicates the transaction date in Tally-accepted format (YYYYMMDD). |
| VoucherNumber | Conditional | String | By default, Tally auto-generates voucher numbers. This tag is required only if you want to pass a custom voucher number from your system. |
| PartyLedgerName | Yes | String | Specifies the name of primary party or account involved in the transaction (e.g., buyer or cash/bank ) |
| AllLedgerEntries | Yes | Collection | Collection of ledger entries forming the transaction; ensures debit and credit entries are captured |
| LedgerName | Yes | String | Name of the ledger affected in the transaction |
| IsDeemedPositive | Yes | Logical / Boolean | Determines whether the entry is treated as Debit (Yes) or Credit (No) |
| IsPartyLedger | Yes | Logical / Boolean | Indicates whether the ledger is the main party ledger in the transaction |
| Amount | Yes | Amount | Specifies the transaction amount |

Additional tags of inventory information would depend on whether the transaction contains stock items.

**Sample — XML Format**

```xml
<ENVELOPE>
 <HEADER>
  <TALLYREQUEST>Import Data</TALLYREQUEST>
 </HEADER>
 <BODY>
    <TALLYMESSAGE>
     <VOUCHER VCHTYPE="Sales" ACTION="Create" OBJVIEW="Invoice Voucher View">
      <DATE>20260320</DATE>
      <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
      <PARTYLEDGERNAME>Amar Enterprises</PARTYLEDGERNAME>
      <VOUCHERNUMBER>1</VOUCHERNUMBER>
      <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
      <ISINVOICE>Yes</ISINVOICE>
      <ALLINVENTORYENTRIES.LIST>
       <STOCKITEMNAME>Hp Pavilion 14 Laptop</STOCKITEMNAME>
       <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
       <RATE>125000.00/nos</RATE>
       <AMOUNT>125000.00</AMOUNT>
       <ACTUALQTY> 1 nos</ACTUALQTY>
       <BILLEDQTY> 1 nos</BILLEDQTY>
       <ACCOUNTINGALLOCATIONS.LIST>
        <LEDGERNAME>Sales</LEDGERNAME>
        <AMOUNT>125000.00</AMOUNT>
       </ACCOUNTINGALLOCATIONS.LIST>
      </ALLINVENTORYENTRIES.LIST>
      <LEDGERENTRIES.LIST>
       <LEDGERNAME>Amar Enterprises</LEDGERNAME>
       <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
       <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
       <AMOUNT>125000.00</AMOUNT>
       <BILLALLOCATIONS.LIST>
        <NAME>22</NAME>
        <BILLTYPE>New Ref</BILLTYPE>
        <TDSDEDUCTEEISSPECIALRATE>No</TDSDEDUCTEEISSPECIALRATE>
        <AMOUNT>125000.00</AMOUNT>
       </BILLALLOCATIONS.LIST>
      </LEDGERENTRIES.LIST>
     </VOUCHER>
    </TALLYMESSAGE>
   </REQUESTDATA>
  </IMPORTDATA>
 </BODY>
</ENVELOPE>

```

**Sample — JSON Format**

```json
{
  "tallymessage": [
    {
      "metadata": {
        "type": "Voucher",
        "action": "Create",
        "objectview": "Invoice Voucher View"
      },
      "DATE": "20260320",
      "VOUCHERTYPENAME": "Sales",
      "VOUCHERNUMBER": "1",
      "PERSISTEDVIEW": "Invoice Voucher View",
      "ISINVOICE": "Yes",
      "PARTYLEDGERNAME": "Amar Enterprises",

      "ALLINVENTORYENTRIES.LIST": [
        {
          "STOCKITEMNAME": "Hp Pavilion 14 Laptop",
          "ISDEEMEDPOSITIVE": "Yes",
          "RATE": "125000.00/nos",
          "AMOUNT": 125000,
          "ACTUALQTY": "1 nos",
          "BILLEDQTY": "1 nos",

          "ACCOUNTINGALLOCATIONS.LIST": [
            {
              "LEDGERNAME": "Sales",
              "AMOUNT": 125000
            }
          ]
        }
      ],

      "LEDGERENTRIES.LIST": [
        {
          "LEDGERNAME": "Amar Enterprises",
          "ISDEEMEDPOSITIVE": "Yes",
          "ISPARTYLEDGER": "Yes",
          "AMOUNT": 125000,

          "BILLALLOCATIONS.LIST": [
            {
              "NAME": "22",
              "BILLTYPE": "New Ref",
              "TDSDEDUCTEEISSPECIALRATE": "No",
              "AMOUNT": 125000
            }
          ]
        }
      ]
    }
  ]
}

```

### 4.3.1 Create Sales with Item

> Explorer id: `sales-create-item` · Kind: **import** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#sales-create-item)

#### Description

The Create action is used to record a Sales voucher with Item details in the company data in Tally by providing information such as the StockItemName, Quantity, Rate & Amount. This captures Inventory outgoing sales and ensures correct debit and credit impact on the respective ledgers.

**Integration use:** Post item invoices from your order/POS system so stock and revenue both update in Tally.

**Notes:**

- Invoice view: item lines go in `allinventoryentries` (each with `accountingallocations` to the Sales ledger and `batchallocations` to a godown); party and tax lines go in `ledgerentries`.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svVchImportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `import` | Yes |
| `type` | `data` | Yes |
| `id` | `Vouchers` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svVchImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Voucher",
        "vchtype": "Sales",
        "action": "Create",
        "objview": "Invoice Voucher View"
      },
      "date": "20250831",
      "vouchertypename": "Sales",
      "partyname": "Amar Enterprises",
      "partyledgername": "Amar Enterprises",
      "allinventoryentries": [
        {
          "stockitemname": "Coffee Powder",
          "isdeemedpositive": false,
          "rate": "2.00/nos",
          "amount": "40.00",
          "actualqty": " 20 nos",
          "billedqty": " 20 nos",
          "batchallocations": [
            {
              "godownname": "Main Location",
              "batchname": "Primary Batch",
              "destinationgodownname": "Main Location",
              "trackingnumber": "T001",
              "amount": "40.00",
              "actualqty": " 20 nos",
              "billedqty": " 20 nos"
            }
          ],
          "accountingallocations": [
            {
              "oldauditentryids": [
                {
                  "metadata": true,
                  "type": "Number"
                },
                "-1"
              ],
              "ledgername": "Sales",
              "isdeemedpositive": false,
              "ispartyledger": false,
              "amount": "40.00"
            }
          ]
        }
      ],
      "ledgerentries": [
        {
          "oldauditentryids": [
            {
              "metadata": true,
              "type": "Number"
            },
            "-1"
          ],
          "ledgername": "Amar Enterprises",
          "isdeemedpositive": true,
          "ispartyledger": true,
          "amount": "-40.00",
          "billallocations": [
            {
              "name": "12",
              "billtype": "New Ref",
              "amount": "-40.00"
            }
          ]
        }
      ]
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
 <VOUCHER VCHTYPE="Sales" ACTION="Create" OBJVIEW="Accounting Voucher View">
  <DATE>20250831</DATE>
  <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
  <PARTYNAME>Amar Enterprises</PARTYNAME>
  <PARTYLEDGERNAME>Amar Enterprises</PARTYLEDGERNAME>
  <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
  <ALLLEDGERENTRIES.LIST>
   <OLDAUDITENTRYIDS.LIST TYPE="Number">
<OLDAUDITENTRYIDS>-1</OLDAUDITENTRYIDS>
   </OLDAUDITENTRYIDS.LIST>
   <LEDGERNAME>Amar Enterprises</LEDGERNAME>
   <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
   <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
   <AMOUNT>-40.00</AMOUNT>
   <BILLALLOCATIONS.LIST>
<NAME>12</NAME>
<BILLTYPE>New Ref</BILLTYPE>
<AMOUNT>-40.00</AMOUNT>
   </BILLALLOCATIONS.LIST>
  </ALLLEDGERENTRIES.LIST>
  <ALLLEDGERENTRIES.LIST>
   <OLDAUDITENTRYIDS.LIST TYPE="Number">
<OLDAUDITENTRYIDS>-1</OLDAUDITENTRYIDS>
   </OLDAUDITENTRYIDS.LIST>
   <LEDGERNAME>Sales</LEDGERNAME>
   <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
   <ISPARTYLEDGER>No</ISPARTYLEDGER>
   <AMOUNT>40.00</AMOUNT>
   <INVENTORYALLOCATIONS.LIST>
<STOCKITEMNAME>Coffee Powder</STOCKITEMNAME>
<ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
<RATE>2.00/nos</RATE>
<AMOUNT>40.00</AMOUNT>
<ACTUALQTY> 20 nos</ACTUALQTY>
<BILLEDQTY> 20 nos</BILLEDQTY>
<BATCHALLOCATIONS.LIST>
 <GODOWNNAME>Main Location</GODOWNNAME>
 <BATCHNAME>Primary Batch</BATCHNAME>
 <DESTINATIONGODOWNNAME>Main Location</DESTINATIONGODOWNNAME>
 <TRACKINGNUMBER>T001</TRACKINGNUMBER>
 <AMOUNT>40.00</AMOUNT>
 <ACTUALQTY> 20 nos</ACTUALQTY>
 <BILLEDQTY> 20 nos</BILLEDQTY>
</BATCHALLOCATIONS.LIST>
   </INVENTORYALLOCATIONS.LIST>
   </ALLLEDGERENTRIES.LIST>
 </VOUCHER>
</TALLYMESSAGE>
</DESC>
</BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: import" \
  -H "type: data" \
  -H "id: Vouchers" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟢 Official shape: Tally's published voucher import response):

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 1,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 71,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 0,
            "vchnumber": 33
        }
    }
}
```

**Success — XML** (🔵 Observed: captured from a live TallyPrime in `docs/Tally_Vouchers_Integration_Guide.md`; `CMPINFO` truncated):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <CREATED>1</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>71</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>0</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
        <DESC>
            <CMPINFO>
                <COMPANY>0</COMPANY>
                <GROUP>0</GROUP>
                <LEDGER>95</LEDGER>
                <!-- … one count element per object type (COSTCENTRE, GODOWN, STOCKITEM, UNIT, VOUCHERTYPE, …) … -->
                <VOUCHER>39</VOUCHER>
            </CMPINFO>
        </DESC>
    </BODY>
</ENVELOPE>
```

Check `created` = 1 **and** `errors` + `exceptions` = 0. `status: "1"` only means the request was processed, not that the record was accepted. `lastvchid` is the internal id (MASTERID) of the last voucher written, and `vchnumber` is its voucher number.

#### Error Responses

**Record-level failure:** `Ledger 'Amar Enterprises' does not exist!`. Source: 🟡 Illustrative (message pattern also reported by other Tally integrations).

Cause: A ledger (or stock item / godown) referenced by the voucher is missing, or misspelt. Create masters before vouchers.

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <LINEERROR>Ledger &apos;Amar Enterprises&apos; does not exist!</LINEERROR>
                <CREATED>0</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>1</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
    </BODY>
</ENVELOPE>
```

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 1
        }
    }
}
```

> In JSON the failure shows up as non-zero `errors` / `exceptions` counts. Tally does not document the JSON key that carries the line-error text, so log the raw response body; this repo's parser (`parse_tally_response_metrics`) also checks `import_result.line_error`.

See also [Common errors](#110-common-error-responses) (company not loaded, unknown request, Tally not running).

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `import` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `data` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `Vouchers` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svVchImportFormat]` | `<STATICVARIABLES><SVVCHIMPORTFORMAT>` | Yes (voucher import) | String | `jsonex` | Import format of vouchers: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `tallymessage[]` | `<TALLYMESSAGE>` | Yes | Array<Object> |  | The objects to import (masters or vouchers). One request can carry many objects. |
| `tallymessage[].metadata` | `<VOUCHER …>` attributes | Yes | Object |  | Object identity block: type, name/identifiers and action. |
| `tallymessage[].metadata.type` | element name `<VOUCHER>` | Yes | String | `Voucher` | Object type: `Ledger`, `Group`, `Stock Item`, `Stock Group`, `Unit`, `Voucher`. |
| `tallymessage[].metadata.vchtype` | `VCHTYPE` attribute | Yes (vouchers) | String | `Sales` | Voucher type name, e.g. `Payment`, `Receipt`, `Sales`, `Purchase`. |
| `tallymessage[].metadata.action` | `ACTION` attribute | Yes | String | `Create` | `Create`, `Alter`, or `Delete` (case-insensitive). |
| `tallymessage[].metadata.objview` | `OBJVIEW` attribute | Yes (vouchers) | String | `Invoice Voucher View` | `Accounting Voucher View` (ledger-only vouchers) or `Invoice Voucher View` (item invoices). |
| `tallymessage[].date` | `<VOUCHER>/DATE` | Yes | Date (YYYYMMDD) | `20250831` | Voucher date. Must fall inside the company's books period (Educational Mode: only 1st, 2nd, 31st). |
| `tallymessage[].vouchertypename` | `<VOUCHER>/VOUCHERTYPENAME` | Yes | String | `Sales` | Voucher type name, e.g. `Payment`. |
| `tallymessage[].partyname` | `<VOUCHER>/PARTYNAME` | No | String | `Amar Enterprises` | Party name printed on the voucher. |
| `tallymessage[].partyledgername` | `<VOUCHER>/PARTYLEDGERNAME` | Yes | String | `Amar Enterprises` | Primary party / account ledger of the voucher. |
| `tallymessage[].allinventoryentries[]` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST` | Yes (item invoice) | Array<Object> |  | Item lines (`ALLINVENTORYENTRIES.LIST`). |
| `tallymessage[].allinventoryentries[].stockitemname` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/STOCKITEMNAME` | Yes | String | `Coffee Powder` | Stock item on the line. Must already exist. |
| `tallymessage[].allinventoryentries[].isdeemedpositive` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/ISDEEMEDPOSITIVE` | Yes | Logical | `false` | `Yes`/`true` = Debit, `No`/`false` = Credit. |
| `tallymessage[].allinventoryentries[].rate` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/RATE` | Yes | Rate | `2.00/nos` | Rate with unit, e.g. `75.00/nos`. |
| `tallymessage[].allinventoryentries[].amount` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/AMOUNT` | Yes | Amount | `40.00` | Line amount. Sign convention: Debit lines negative, Credit lines positive; all lines must net to zero. |
| `tallymessage[].allinventoryentries[].actualqty` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/ACTUALQTY` | Yes | Quantity | `20 nos` | Actual quantity with unit, e.g. `20 nos`. |
| `tallymessage[].allinventoryentries[].billedqty` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/BILLEDQTY` | Yes | Quantity | `20 nos` | Billed quantity with unit. |
| `tallymessage[].allinventoryentries[].batchallocations[]` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/BATCHALLOCATIONS.LIST` | Yes (items) | Array<Object> |  | Godown/batch split of the item line (`BATCHALLOCATIONS.LIST`). |
| `tallymessage[].allinventoryentries[].batchallocations[].godownname` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/BATCHALLOCATIONS.LIST/GODOWNNAME` | Yes | String | `Main Location` | Godown (location). Default company godown is `Main Location`. |
| `tallymessage[].allinventoryentries[].batchallocations[].batchname` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/BATCHALLOCATIONS.LIST/BATCHNAME` | Cond. | String | `Primary Batch` | Batch name (`Primary Batch` when batches are not tracked). |
| `tallymessage[].allinventoryentries[].batchallocations[].destinationgodownname` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/BATCHALLOCATIONS.LIST/DESTINATIONGODOWNNAME` | No | String | `Main Location` | Destination godown (transfers). |
| `tallymessage[].allinventoryentries[].batchallocations[].trackingnumber` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/BATCHALLOCATIONS.LIST/TRACKINGNUMBER` | No | String | `T001` | Tracking (delivery/receipt note) number. |
| `tallymessage[].allinventoryentries[].batchallocations[].amount` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/BATCHALLOCATIONS.LIST/AMOUNT` | Yes | Amount | `40.00` | Line amount. Sign convention: Debit lines negative, Credit lines positive; all lines must net to zero. |
| `tallymessage[].allinventoryentries[].batchallocations[].actualqty` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/BATCHALLOCATIONS.LIST/ACTUALQTY` | Yes | Quantity | `20 nos` | Actual quantity with unit, e.g. `20 nos`. |
| `tallymessage[].allinventoryentries[].batchallocations[].billedqty` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/BATCHALLOCATIONS.LIST/BILLEDQTY` | Yes | Quantity | `20 nos` | Billed quantity with unit. |
| `tallymessage[].allinventoryentries[].accountingallocations[]` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/ACCOUNTINGALLOCATIONS.LIST` | Yes (items) | Array<Object> |  | Sales/Purchase ledger the item amount posts to (`ACCOUNTINGALLOCATIONS.LIST`). |
| `tallymessage[].allinventoryentries[].accountingallocations[].oldauditentryids[]` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/ACCOUNTINGALLOCATIONS.LIST/OLDAUDITENTRYIDS.LIST` | No | Array<Number> |  | Audit-trail ids carried on alteration exports; safe to omit on create. |
| `tallymessage[].allinventoryentries[].accountingallocations[].oldauditentryids[].metadata` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/ACCOUNTINGALLOCATIONS.LIST/OLDAUDITENTRYIDS.LIST/METADATA` | Yes | Object | `true` | Object identity block: type, name/identifiers and action. |
| `tallymessage[].allinventoryentries[].accountingallocations[].oldauditentryids[].type` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/ACCOUNTINGALLOCATIONS.LIST/OLDAUDITENTRYIDS.LIST/TYPE` | No | String | `Number` | Audit-trail entry type (export artefact). |
| `tallymessage[].allinventoryentries[].accountingallocations[].ledgername` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/ACCOUNTINGALLOCATIONS.LIST/LEDGERNAME` | Yes | String | `Sales` | Ledger affected by the line. Must already exist. |
| `tallymessage[].allinventoryentries[].accountingallocations[].isdeemedpositive` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/ACCOUNTINGALLOCATIONS.LIST/ISDEEMEDPOSITIVE` | Yes | Logical | `false` | `Yes`/`true` = Debit, `No`/`false` = Credit. |
| `tallymessage[].allinventoryentries[].accountingallocations[].ispartyledger` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/ACCOUNTINGALLOCATIONS.LIST/ISPARTYLEDGER` | Yes | Logical | `false` | `Yes` for the party/cash/bank line of the voucher. |
| `tallymessage[].allinventoryentries[].accountingallocations[].amount` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/ACCOUNTINGALLOCATIONS.LIST/AMOUNT` | Yes | Amount | `40.00` | Line amount. Sign convention: Debit lines negative, Credit lines positive; all lines must net to zero. |
| `tallymessage[].ledgerentries[]` | `<VOUCHER>/LEDGERENTRIES.LIST` | Yes (invoice view) | Array<Object> |  | Ledger lines (party, taxes) of an Invoice-view voucher (`LEDGERENTRIES.LIST`). |
| `tallymessage[].ledgerentries[].oldauditentryids[]` | `<VOUCHER>/LEDGERENTRIES.LIST/OLDAUDITENTRYIDS.LIST` | No | Array<Number> |  | Audit-trail ids carried on alteration exports; safe to omit on create. |
| `tallymessage[].ledgerentries[].oldauditentryids[].metadata` | `<VOUCHER>/LEDGERENTRIES.LIST/OLDAUDITENTRYIDS.LIST/METADATA` | Yes | Object | `true` | Object identity block: type, name/identifiers and action. |
| `tallymessage[].ledgerentries[].oldauditentryids[].type` | `<VOUCHER>/LEDGERENTRIES.LIST/OLDAUDITENTRYIDS.LIST/TYPE` | No | String | `Number` | Audit-trail entry type (export artefact). |
| `tallymessage[].ledgerentries[].ledgername` | `<VOUCHER>/LEDGERENTRIES.LIST/LEDGERNAME` | Yes | String | `Amar Enterprises` | Ledger affected by the line. Must already exist. |
| `tallymessage[].ledgerentries[].isdeemedpositive` | `<VOUCHER>/LEDGERENTRIES.LIST/ISDEEMEDPOSITIVE` | Yes | Logical | `true` | `Yes`/`true` = Debit, `No`/`false` = Credit. |
| `tallymessage[].ledgerentries[].ispartyledger` | `<VOUCHER>/LEDGERENTRIES.LIST/ISPARTYLEDGER` | Yes | Logical | `true` | `Yes` for the party/cash/bank line of the voucher. |
| `tallymessage[].ledgerentries[].amount` | `<VOUCHER>/LEDGERENTRIES.LIST/AMOUNT` | Yes | Amount | `-40.00` | Line amount. Sign convention: Debit lines negative, Credit lines positive; all lines must net to zero. |
| `tallymessage[].ledgerentries[].billallocations[]` | `<VOUCHER>/LEDGERENTRIES.LIST/BILLALLOCATIONS.LIST` | Cond. | Array<Object> |  | Bill-wise allocation for bill-wise-enabled party ledgers (`BILLALLOCATIONS.LIST`). |
| `tallymessage[].ledgerentries[].billallocations[].name` | `<VOUCHER>/LEDGERENTRIES.LIST/BILLALLOCATIONS.LIST/NAME` | Yes | String | `12` | Bill reference number (e.g. invoice no.). |
| `tallymessage[].ledgerentries[].billallocations[].billtype` | `<VOUCHER>/LEDGERENTRIES.LIST/BILLALLOCATIONS.LIST/BILLTYPE` | Yes | String | `New Ref` | `New Ref`, `Agst Ref`, `Advance`, or `On Account`. |
| `tallymessage[].ledgerentries[].billallocations[].amount` | `<VOUCHER>/LEDGERENTRIES.LIST/BILLALLOCATIONS.LIST/AMOUNT` | Yes | Amount | `-40.00` | Line amount. Sign convention: Debit lines negative, Credit lines positive; all lines must net to zero. |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Create a Sales Voucher with same ledger but on date ‘01st August 2025” and the ItemName “Decaf Coffee”. | Change the value of Date tags in voucher. Change the value of Stock Item Name in Inventory Entries. | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/sales/create-item/json/TaskItemSalesVoucherJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/sales/create-item/xml/TaskItemSalesVoucherXML.txt) |

### 4.3.2 Create Sales with GST

> Explorer id: `sales-create-gst` · Kind: **import** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#sales-create-gst)

#### Description

The Create action is used to record a Sales voucher with GST details in the company data in Tally by providing information such as the CGST, SGST & IGST.

**Integration use:** Post GST-compliant B2B/B2C invoices (CGST/SGST/IGST lines, GSTIN, place of supply) so GST returns in Tally are correct.

**Notes:**

- Intra-state supply shows CGST + SGST lines; use IGST for inter-state. `ratedetails` carries the item's GST rates.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svVchImportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `import` | Yes |
| `type` | `data` | Yes |
| `id` | `Vouchers` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svVchImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Voucher",
        "vchtype": "Sales",
        "action": "Create",
        "objview": "Invoice Voucher View"
      },
      "date": "20260301",
      "vchstatusdate": "20260301",
      "gstregistrationtype": "Regular",
      "statename": "Karnataka",
      "countryofresidence": "India",
      "partygstin": "29AAACH1004N1ZQ",
      "placeofsupply": "Karnataka",
      "vouchertypename": "Sales",
      "partyname": "Chanda Enterprises",
      "gstregistration": {
        "value": "Karnataka Registration",
        "taxtype": "GST",
        "taxregistration": "29AAECP4424C1ZN"
      },
      "cmpgstin": "29AAECP4424C1ZN",
      "partyledgername": "Chanda Enterprises",
      "basicbuyername": "Chanda Enterprises",
      "cmpgstregistrationtype": "Regular",
      "partymailingname": "Chanda Enterprises",
      "dispatchfromname": "Bhrama Enterprises",
      "dispatchfromstatename": "Karnataka",
      "consigneegstin": "29AAACH1004N1ZQ",
      "consigneemailingname": "Chanda Enterprises",
      "consigneestatename": "Karnataka",
      "cmpgststate": "Karnataka",
      "consigneecountryname": "India",
      "basicbasepartyname": "Chanda Enterprises",
      "effectivedate": "20260301",
      "isinvoice": true,
      "allinventoryentries": [
        {
          "stockitemname": "GST Coffee",
          "gstovrdnisrevchargeappl": "\u0004 Not Applicable",
          "gstovrdntaxability": "Taxable",
          "gstsourcetype": "Stock Item",
          "gstitemsource": "GST Coffee",
          "hsnsourcetype": "Stock Item",
          "hsnitemsource": "GST Coffee",
          "gstovrdntypeofsupply": "Goods",
          "gstrateinferapplicability": "As per Masters/Company",
          "gsthsnname": "4820",
          "gsthsninferapplicability": "As per Masters/Company",
          "isdeemedpositive": false,
          "rate": "75.00/nos",
          "amount": "1500.00",
          "actualqty": " 20 nos",
          "billedqty": " 20 nos",
          "batchallocations": [
            {
              "godownname": "Main Location",
              "batchname": "Primary Batch",
              "amount": "1500.00",
              "actualqty": " 20 nos",
              "billedqty": " 20 nos"
            }
          ],
          "accountingallocations": [
            {
              "ledgername": "GST Sales",
              "isdeemedpositive": false,
              "ispartyledger": false,
              "amount": "1500.00"
            }
          ],
          "ratedetails": [
            {
              "gstratedutyhead": "CGST",
              "gstratevaluationtype": "Based on Value",
              "gstrate": " 2.50"
            },
            {
              "gstratedutyhead": "SGST/UTGST",
              "gstratevaluationtype": "Based on Value",
              "gstrate": " 2.50"
            },
            {
              "gstratedutyhead": "IGST",
              "gstratevaluationtype": "Based on Value",
              "gstrate": " 5"
            },
            {
              "gstratedutyhead": "Cess",
              "gstratevaluationtype": "\u0004 Not Applicable"
            },
            {
              "gstratedutyhead": "State Cess",
              "gstratevaluationtype": "Based on Value"
            }
          ]
        }
      ],
      "ledgerentries": [
        {
          "ledgername": "Chanda Enterprises",
          "isdeemedpositive": true,
          "ispartyledger": true,
          "amount": "-1575.00",
          "billallocations": [
            {
              "name": "22",
              "billtype": "New Ref",
              "tdsdeducteeisspecialrate": false,
              "amount": "-1575.00"
            }
          ]
        },
        {
          "ledgername": "CGST",
          "isdeemedpositive": false,
          "ispartyledger": false,
          "amount": "37.50"
        },
        {
          "ledgername": "SGST",
          "isdeemedpositive": false,
          "ispartyledger": false,
          "amount": "37.50"
        }
      ]
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
<VOUCHER VCHTYPE="Sales" ACTION="Create" OBJVIEW="Invoice Voucher View">
      <DATE>20260301</DATE>
      <VCHSTATUSDATE>20260301</VCHSTATUSDATE>
      <GSTREGISTRATIONTYPE>Regular</GSTREGISTRATIONTYPE>
      <STATENAME>Karnataka</STATENAME>
      <COUNTRYOFRESIDENCE>India</COUNTRYOFRESIDENCE>
      <PARTYGSTIN>29AAACH1004N1ZQ</PARTYGSTIN>
      <PLACEOFSUPPLY>Karnataka</PLACEOFSUPPLY>
      <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
      <PARTYNAME>Chanda Enterprises</PARTYNAME>
      <GSTREGISTRATION TAXTYPE="GST" TAXREGISTRATION="29AAECP4424C1ZN">Karnataka Registration</GSTREGISTRATION>
      <CMPGSTIN>29AAECP4424C1ZN</CMPGSTIN>
      <PARTYLEDGERNAME>Chanda Enterprises</PARTYLEDGERNAME>
      <BASICBUYERNAME>Chanda Enterprises</BASICBUYERNAME>
      <CMPGSTREGISTRATIONTYPE>Regular</CMPGSTREGISTRATIONTYPE>
      <PARTYMAILINGNAME>Chanda Enterprises</PARTYMAILINGNAME>
      <DISPATCHFROMNAME>Bhrama Enterprises</DISPATCHFROMNAME>
      <DISPATCHFROMSTATENAME>Karnataka</DISPATCHFROMSTATENAME>
      <CONSIGNEEGSTIN>29AAACH1004N1ZQ</CONSIGNEEGSTIN>
      <CONSIGNEEMAILINGNAME>Chanda Enterprises</CONSIGNEEMAILINGNAME>
      <CONSIGNEESTATENAME>Karnataka</CONSIGNEESTATENAME>
      <CMPGSTSTATE>Karnataka</CMPGSTSTATE>
      <CONSIGNEECOUNTRYNAME>India</CONSIGNEECOUNTRYNAME>
      <BASICBASEPARTYNAME>Chanda Enterprises</BASICBASEPARTYNAME>
      <EFFECTIVEDATE> 20260301 </EFFECTIVEDATE>
      <ISINVOICE>Yes</ISINVOICE>
      <ALLINVENTORYENTRIES.LIST>
       <STOCKITEMNAME>GST Coffee</STOCKITEMNAME>
       <GSTOVRDNISREVCHARGEAPPL>&#4; Not Applicable</GSTOVRDNISREVCHARGEAPPL>
       <GSTOVRDNTAXABILITY>Taxable</GSTOVRDNTAXABILITY>
       <GSTSOURCETYPE>Stock Item</GSTSOURCETYPE>
       <GSTITEMSOURCE>GST Coffee</GSTITEMSOURCE>
       <HSNSOURCETYPE>Stock Item</HSNSOURCETYPE>
       <HSNITEMSOURCE>GST Coffee</HSNITEMSOURCE>
       <GSTOVRDNTYPEOFSUPPLY>Goods</GSTOVRDNTYPEOFSUPPLY>
       <GSTRATEINFERAPPLICABILITY>As per Masters/Company</GSTRATEINFERAPPLICABILITY>
       <GSTHSNNAME>4820</GSTHSNNAME>
       <GSTHSNINFERAPPLICABILITY>As per Masters/Company</GSTHSNINFERAPPLICABILITY>
       <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
       <RATE>75.00/nos</RATE>
       <AMOUNT>1500.00</AMOUNT>
       <ACTUALQTY> 20 nos</ACTUALQTY>
       <BILLEDQTY> 20 nos</BILLEDQTY>
       <BATCHALLOCATIONS.LIST>
        <GODOWNNAME>Main Location</GODOWNNAME>
        <BATCHNAME>Primary Batch</BATCHNAME>
        <AMOUNT>1500.00</AMOUNT>
        <ACTUALQTY> 20 nos</ACTUALQTY>
        <BILLEDQTY> 20 nos</BILLEDQTY>
       </BATCHALLOCATIONS.LIST>
       <ACCOUNTINGALLOCATIONS.LIST>
        <LEDGERNAME>GST Sales</LEDGERNAME>
        <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
        <ISPARTYLEDGER>No</ISPARTYLEDGER>
        <AMOUNT>1500.00</AMOUNT>
       </ACCOUNTINGALLOCATIONS.LIST>
       <RATEDETAILS.LIST>
        <GSTRATEDUTYHEAD>CGST</GSTRATEDUTYHEAD>
        <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>
        <GSTRATE> 2.50</GSTRATE>
       </RATEDETAILS.LIST>
       <RATEDETAILS.LIST>
        <GSTRATEDUTYHEAD>SGST/UTGST</GSTRATEDUTYHEAD>
        <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>
        <GSTRATE> 2.50</GSTRATE>
       </RATEDETAILS.LIST>
       <RATEDETAILS.LIST>
        <GSTRATEDUTYHEAD>IGST</GSTRATEDUTYHEAD>
        <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>
        <GSTRATE> 5</GSTRATE>
       </RATEDETAILS.LIST>
       <RATEDETAILS.LIST>
        <GSTRATEDUTYHEAD>Cess</GSTRATEDUTYHEAD>
        <GSTRATEVALUATIONTYPE>&#4; Not Applicable</GSTRATEVALUATIONTYPE>
       </RATEDETAILS.LIST>
       <RATEDETAILS.LIST>
        <GSTRATEDUTYHEAD>State Cess</GSTRATEDUTYHEAD>
        <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>
       </RATEDETAILS.LIST>
      </ALLINVENTORYENTRIES.LIST>
      <LEDGERENTRIES.LIST>
       <LEDGERNAME>Chanda Enterprises</LEDGERNAME>
       <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
       <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
       <AMOUNT>-1575.00</AMOUNT>
       <BILLALLOCATIONS.LIST>
        <NAME>22</NAME>
        <BILLTYPE>New Ref</BILLTYPE>
        <TDSDEDUCTEEISSPECIALRATE>No</TDSDEDUCTEEISSPECIALRATE>
        <AMOUNT>-1575.00</AMOUNT>
       </BILLALLOCATIONS.LIST>
      </LEDGERENTRIES.LIST>
      <LEDGERENTRIES.LIST>
       <LEDGERNAME>CGST</LEDGERNAME>
       <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
       <ISPARTYLEDGER>No</ISPARTYLEDGER>
       <AMOUNT>37.50</AMOUNT>
      </LEDGERENTRIES.LIST>
      <LEDGERENTRIES.LIST>
       <LEDGERNAME>SGST</LEDGERNAME>
       <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
       <ISPARTYLEDGER>No</ISPARTYLEDGER>
       <AMOUNT>37.50</AMOUNT>
      </LEDGERENTRIES.LIST>
     </VOUCHER>
</TALLYMESSAGE>
</DESC>
</BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: import" \
  -H "type: data" \
  -H "id: Vouchers" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟢 Official shape: Tally's published voucher import response):

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 1,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 71,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 0,
            "vchnumber": 33
        }
    }
}
```

**Success — XML** (🔵 Observed: captured from a live TallyPrime in `docs/Tally_Vouchers_Integration_Guide.md`; `CMPINFO` truncated):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <CREATED>1</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>71</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>0</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
        <DESC>
            <CMPINFO>
                <COMPANY>0</COMPANY>
                <GROUP>0</GROUP>
                <LEDGER>95</LEDGER>
                <!-- … one count element per object type (COSTCENTRE, GODOWN, STOCKITEM, UNIT, VOUCHERTYPE, …) … -->
                <VOUCHER>39</VOUCHER>
            </CMPINFO>
        </DESC>
    </BODY>
</ENVELOPE>
```

Check `created` = 1 **and** `errors` + `exceptions` = 0. `status: "1"` only means the request was processed, not that the record was accepted. `lastvchid` is the internal id (MASTERID) of the last voucher written, and `vchnumber` is its voucher number.

#### Error Responses

**Record-level failure:** `Ledger 'Chanda Enterprises' does not exist!`. Source: 🟡 Illustrative (message pattern also reported by other Tally integrations).

Cause: A ledger (or stock item / godown) referenced by the voucher is missing, or misspelt. Create masters before vouchers.

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <LINEERROR>Ledger &apos;Chanda Enterprises&apos; does not exist!</LINEERROR>
                <CREATED>0</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>1</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
    </BODY>
</ENVELOPE>
```

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 1
        }
    }
}
```

> In JSON the failure shows up as non-zero `errors` / `exceptions` counts. Tally does not document the JSON key that carries the line-error text, so log the raw response body; this repo's parser (`parse_tally_response_metrics`) also checks `import_result.line_error`.

See also [Common errors](#110-common-error-responses) (company not loaded, unknown request, Tally not running).

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `import` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `data` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `Vouchers` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svVchImportFormat]` | `<STATICVARIABLES><SVVCHIMPORTFORMAT>` | Yes (voucher import) | String | `jsonex` | Import format of vouchers: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `tallymessage[]` | `<TALLYMESSAGE>` | Yes | Array<Object> |  | The objects to import (masters or vouchers). One request can carry many objects. |
| `tallymessage[].metadata` | `<VOUCHER …>` attributes | Yes | Object |  | Object identity block: type, name/identifiers and action. |
| `tallymessage[].metadata.type` | element name `<VOUCHER>` | Yes | String | `Voucher` | Object type: `Ledger`, `Group`, `Stock Item`, `Stock Group`, `Unit`, `Voucher`. |
| `tallymessage[].metadata.vchtype` | `VCHTYPE` attribute | Yes (vouchers) | String | `Sales` | Voucher type name, e.g. `Payment`, `Receipt`, `Sales`, `Purchase`. |
| `tallymessage[].metadata.action` | `ACTION` attribute | Yes | String | `Create` | `Create`, `Alter`, or `Delete` (case-insensitive). |
| `tallymessage[].metadata.objview` | `OBJVIEW` attribute | Yes (vouchers) | String | `Invoice Voucher View` | `Accounting Voucher View` (ledger-only vouchers) or `Invoice Voucher View` (item invoices). |
| `tallymessage[].date` | `<VOUCHER>/DATE` | Yes | Date (YYYYMMDD) | `20260301` | Voucher date. Must fall inside the company's books period (Educational Mode: only 1st, 2nd, 31st). |
| `tallymessage[].vchstatusdate` | `<VOUCHER>/VCHSTATUSDATE` | No | Date (YYYYMMDD) | `20260301` | Voucher status date (usually = `date`). |
| `tallymessage[].gstregistrationtype` | `<VOUCHER>/GSTREGISTRATIONTYPE` | Cond. | String | `Regular` | Party GST registration type: `Regular`, `Composition`, `Consumer`, `Unregistered`, `\u0004 Unknown`. |
| `tallymessage[].statename` | `<VOUCHER>/STATENAME` | Cond. | String | `Karnataka` | Party state. |
| `tallymessage[].countryofresidence` | `<VOUCHER>/COUNTRYOFRESIDENCE` | No | String | `India` | Party country. |
| `tallymessage[].partygstin` | `<VOUCHER>/PARTYGSTIN` | Cond. | String | `29AAACH1004N1ZQ` | Party GSTIN (B2B). |
| `tallymessage[].placeofsupply` | `<VOUCHER>/PLACEOFSUPPLY` | Cond. | String | `Karnataka` | GST place of supply (state). Drives CGST+SGST vs IGST. |
| `tallymessage[].vouchertypename` | `<VOUCHER>/VOUCHERTYPENAME` | Yes | String | `Sales` | Voucher type name, e.g. `Payment`. |
| `tallymessage[].partyname` | `<VOUCHER>/PARTYNAME` | No | String | `Chanda Enterprises` | Party name printed on the voucher. |
| `tallymessage[].gstregistration` | `<VOUCHER>/GSTREGISTRATION` | Cond. | Object |  | Company GST registration used (`<GSTREGISTRATION TAXTYPE=… TAXREGISTRATION=…>name</…>` in XML). |
| `tallymessage[].gstregistration.value` | element text | Cond. | String | `Karnataka Registration` | Registration name, e.g. `Karnataka Registration`. |
| `tallymessage[].gstregistration.taxtype` | `TAXTYPE` attribute | Cond. | String | `GST` | Tax type of the registration (`GST`). |
| `tallymessage[].gstregistration.taxregistration` | `TAXREGISTRATION` attribute | Cond. | String | `29AAECP4424C1ZN` | Company GSTIN for the registration. |
| `tallymessage[].cmpgstin` | `<VOUCHER>/CMPGSTIN` | Cond. | String | `29AAECP4424C1ZN` | Company GSTIN. |
| `tallymessage[].partyledgername` | `<VOUCHER>/PARTYLEDGERNAME` | Yes | String | `Chanda Enterprises` | Primary party / account ledger of the voucher. |
| `tallymessage[].basicbuyername` | `<VOUCHER>/BASICBUYERNAME` | No | String | `Chanda Enterprises` | Buyer name (invoice). |
| `tallymessage[].cmpgstregistrationtype` | `<VOUCHER>/CMPGSTREGISTRATIONTYPE` | Cond. | String | `Regular` | Company GST registration type. |
| `tallymessage[].partymailingname` | `<VOUCHER>/PARTYMAILINGNAME` | No | String | `Chanda Enterprises` | Party mailing name. |
| `tallymessage[].dispatchfromname` | `<VOUCHER>/DISPATCHFROMNAME` | No | String | `Bhrama Enterprises` | Dispatch-from name. |
| `tallymessage[].dispatchfromstatename` | `<VOUCHER>/DISPATCHFROMSTATENAME` | No | String | `Karnataka` | Dispatch-from state. |
| `tallymessage[].consigneegstin` | `<VOUCHER>/CONSIGNEEGSTIN` | No | String | `29AAACH1004N1ZQ` | Consignee GSTIN. |
| `tallymessage[].consigneemailingname` | `<VOUCHER>/CONSIGNEEMAILINGNAME` | No | String | `Chanda Enterprises` | Consignee name. |
| `tallymessage[].consigneestatename` | `<VOUCHER>/CONSIGNEESTATENAME` | No | String | `Karnataka` | Consignee state. |
| `tallymessage[].cmpgststate` | `<VOUCHER>/CMPGSTSTATE` | Cond. | String | `Karnataka` | Company GST state. |
| `tallymessage[].consigneecountryname` | `<VOUCHER>/CONSIGNEECOUNTRYNAME` | No | String | `India` | Consignee country. |
| `tallymessage[].basicbasepartyname` | `<VOUCHER>/BASICBASEPARTYNAME` | No | String | `Chanda Enterprises` | Base party name. |
| `tallymessage[].effectivedate` | `<VOUCHER>/EFFECTIVEDATE` | No | Date (YYYYMMDD) | `20260301` | Effective date (usually = `date`). |
| `tallymessage[].isinvoice` | `<VOUCHER>/ISINVOICE` | Cond. | Logical | `true` | `Yes` for Invoice-mode vouchers (with item lines). |
| `tallymessage[].allinventoryentries[]` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST` | Yes (item invoice) | Array<Object> |  | Item lines (`ALLINVENTORYENTRIES.LIST`). |
| `tallymessage[].allinventoryentries[].stockitemname` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/STOCKITEMNAME` | Yes | String | `GST Coffee` | Stock item on the line. Must already exist. |
| `tallymessage[].allinventoryentries[].gstovrdnisrevchargeappl` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/GSTOVRDNISREVCHARGEAPPL` | No | String | `\u0004 Not Applicable` | Reverse-charge override for the line. |
| `tallymessage[].allinventoryentries[].gstovrdntaxability` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/GSTOVRDNTAXABILITY` | No | String | `Taxable` | Taxability override: `Taxable`, `Exempt`, `Nil Rated`. |
| `tallymessage[].allinventoryentries[].gstsourcetype` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/GSTSOURCETYPE` | No | String | `Stock Item` | Where GST details are sourced from (`Stock Item`, `Ledger`, ...). |
| `tallymessage[].allinventoryentries[].gstitemsource` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/GSTITEMSOURCE` | No | String | `GST Coffee` | Source object name for GST details. |
| `tallymessage[].allinventoryentries[].hsnsourcetype` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/HSNSOURCETYPE` | No | String | `Stock Item` | Where HSN is sourced from. |
| `tallymessage[].allinventoryentries[].hsnitemsource` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/HSNITEMSOURCE` | No | String | `GST Coffee` | Source object name for HSN. |
| `tallymessage[].allinventoryentries[].gstovrdntypeofsupply` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/GSTOVRDNTYPEOFSUPPLY` | No | String | `Goods` | `Goods` or `Services`. |
| `tallymessage[].allinventoryentries[].gstrateinferapplicability` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/GSTRATEINFERAPPLICABILITY` | No | String | `As per Masters/Company` | Rate inference: `As per Masters/Company`, `Specify Details Here`, ... |
| `tallymessage[].allinventoryentries[].gsthsnname` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/GSTHSNNAME` | No | String | `4820` | HSN/SAC code. |
| `tallymessage[].allinventoryentries[].gsthsninferapplicability` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/GSTHSNINFERAPPLICABILITY` | No | String | `As per Masters/Company` | HSN inference mode. |
| `tallymessage[].allinventoryentries[].isdeemedpositive` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/ISDEEMEDPOSITIVE` | Yes | Logical | `false` | `Yes`/`true` = Debit, `No`/`false` = Credit. |
| `tallymessage[].allinventoryentries[].rate` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/RATE` | Yes | Rate | `75.00/nos` | Rate with unit, e.g. `75.00/nos`. |
| `tallymessage[].allinventoryentries[].amount` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/AMOUNT` | Yes | Amount | `1500.00` | Line amount. Sign convention: Debit lines negative, Credit lines positive; all lines must net to zero. |
| `tallymessage[].allinventoryentries[].actualqty` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/ACTUALQTY` | Yes | Quantity | `20 nos` | Actual quantity with unit, e.g. `20 nos`. |
| `tallymessage[].allinventoryentries[].billedqty` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/BILLEDQTY` | Yes | Quantity | `20 nos` | Billed quantity with unit. |
| `tallymessage[].allinventoryentries[].batchallocations[]` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/BATCHALLOCATIONS.LIST` | Yes (items) | Array<Object> |  | Godown/batch split of the item line (`BATCHALLOCATIONS.LIST`). |
| `tallymessage[].allinventoryentries[].batchallocations[].godownname` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/BATCHALLOCATIONS.LIST/GODOWNNAME` | Yes | String | `Main Location` | Godown (location). Default company godown is `Main Location`. |
| `tallymessage[].allinventoryentries[].batchallocations[].batchname` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/BATCHALLOCATIONS.LIST/BATCHNAME` | Cond. | String | `Primary Batch` | Batch name (`Primary Batch` when batches are not tracked). |
| `tallymessage[].allinventoryentries[].batchallocations[].amount` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/BATCHALLOCATIONS.LIST/AMOUNT` | Yes | Amount | `1500.00` | Line amount. Sign convention: Debit lines negative, Credit lines positive; all lines must net to zero. |
| `tallymessage[].allinventoryentries[].batchallocations[].actualqty` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/BATCHALLOCATIONS.LIST/ACTUALQTY` | Yes | Quantity | `20 nos` | Actual quantity with unit, e.g. `20 nos`. |
| `tallymessage[].allinventoryentries[].batchallocations[].billedqty` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/BATCHALLOCATIONS.LIST/BILLEDQTY` | Yes | Quantity | `20 nos` | Billed quantity with unit. |
| `tallymessage[].allinventoryentries[].accountingallocations[]` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/ACCOUNTINGALLOCATIONS.LIST` | Yes (items) | Array<Object> |  | Sales/Purchase ledger the item amount posts to (`ACCOUNTINGALLOCATIONS.LIST`). |
| `tallymessage[].allinventoryentries[].accountingallocations[].ledgername` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/ACCOUNTINGALLOCATIONS.LIST/LEDGERNAME` | Yes | String | `GST Sales` | Ledger affected by the line. Must already exist. |
| `tallymessage[].allinventoryentries[].accountingallocations[].isdeemedpositive` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/ACCOUNTINGALLOCATIONS.LIST/ISDEEMEDPOSITIVE` | Yes | Logical | `false` | `Yes`/`true` = Debit, `No`/`false` = Credit. |
| `tallymessage[].allinventoryentries[].accountingallocations[].ispartyledger` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/ACCOUNTINGALLOCATIONS.LIST/ISPARTYLEDGER` | Yes | Logical | `false` | `Yes` for the party/cash/bank line of the voucher. |
| `tallymessage[].allinventoryentries[].accountingallocations[].amount` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/ACCOUNTINGALLOCATIONS.LIST/AMOUNT` | Yes | Amount | `1500.00` | Line amount. Sign convention: Debit lines negative, Credit lines positive; all lines must net to zero. |
| `tallymessage[].allinventoryentries[].ratedetails[]` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/RATEDETAILS.LIST` | No | Array<Object> |  | Per-duty-head GST rates on the line (`RATEDETAILS.LIST`). |
| `tallymessage[].allinventoryentries[].ratedetails[].gstratedutyhead` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/RATEDETAILS.LIST/GSTRATEDUTYHEAD` | Yes | String | `CGST` | `CGST`, `SGST/UTGST`, `IGST`, `Cess`, `State Cess`. |
| `tallymessage[].allinventoryentries[].ratedetails[].gstratevaluationtype` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/RATEDETAILS.LIST/GSTRATEVALUATIONTYPE` | Yes | String | `Based on Value` | `Based on Value`, `Based on Quantity`, `\u0004 Not Applicable`. |
| `tallymessage[].allinventoryentries[].ratedetails[].gstrate` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/RATEDETAILS.LIST/GSTRATE` | Cond. | Number | `2.50` | Rate percentage. |
| `tallymessage[].ledgerentries[]` | `<VOUCHER>/LEDGERENTRIES.LIST` | Yes (invoice view) | Array<Object> |  | Ledger lines (party, taxes) of an Invoice-view voucher (`LEDGERENTRIES.LIST`). |
| `tallymessage[].ledgerentries[].ledgername` | `<VOUCHER>/LEDGERENTRIES.LIST/LEDGERNAME` | Yes | String | `Chanda Enterprises` | Ledger affected by the line. Must already exist. |
| `tallymessage[].ledgerentries[].isdeemedpositive` | `<VOUCHER>/LEDGERENTRIES.LIST/ISDEEMEDPOSITIVE` | Yes | Logical | `true` | `Yes`/`true` = Debit, `No`/`false` = Credit. |
| `tallymessage[].ledgerentries[].ispartyledger` | `<VOUCHER>/LEDGERENTRIES.LIST/ISPARTYLEDGER` | Yes | Logical | `true` | `Yes` for the party/cash/bank line of the voucher. |
| `tallymessage[].ledgerentries[].amount` | `<VOUCHER>/LEDGERENTRIES.LIST/AMOUNT` | Yes | Amount | `-1575.00` | Line amount. Sign convention: Debit lines negative, Credit lines positive; all lines must net to zero. |
| `tallymessage[].ledgerentries[].billallocations[]` | `<VOUCHER>/LEDGERENTRIES.LIST/BILLALLOCATIONS.LIST` | Cond. | Array<Object> |  | Bill-wise allocation for bill-wise-enabled party ledgers (`BILLALLOCATIONS.LIST`). |
| `tallymessage[].ledgerentries[].billallocations[].name` | `<VOUCHER>/LEDGERENTRIES.LIST/BILLALLOCATIONS.LIST/NAME` | Yes | String | `22` | Bill reference number (e.g. invoice no.). |
| `tallymessage[].ledgerentries[].billallocations[].billtype` | `<VOUCHER>/LEDGERENTRIES.LIST/BILLALLOCATIONS.LIST/BILLTYPE` | Yes | String | `New Ref` | `New Ref`, `Agst Ref`, `Advance`, or `On Account`. |
| `tallymessage[].ledgerentries[].billallocations[].tdsdeducteeisspecialrate` | `<VOUCHER>/LEDGERENTRIES.LIST/BILLALLOCATIONS.LIST/TDSDEDUCTEEISSPECIALRATE` | No | Logical | `false` | TDS special-rate flag on the bill line. |
| `tallymessage[].ledgerentries[].billallocations[].amount` | `<VOUCHER>/LEDGERENTRIES.LIST/BILLALLOCATIONS.LIST/AMOUNT` | Yes | Amount | `-1575.00` | Line amount. Sign convention: Debit lines negative, Credit lines positive; all lines must net to zero. |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Create a Sales Voucher with same ledger but on date ‘01st August 2026” | Change the value of Date tags in voucher. | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/sales/create-gst/json/TaskCreateGSTSales1stFeb40nosJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/sales/create-gst/xml/TaskCreateGSTSales1stFeb40nosXML.txt) |

### 4.3.3 Alter a Sales

> Explorer id: `sales-alter` · Kind: **import** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#sales-alter)

#### Description

Each TallyPrime voucher has unique system-generated identifiers. To modify a voucher, ensure the ‘guid’, ‘vchkey’, and ‘remoteid’ match the existing voucher’s values, which can be obtained by exporting it in XML/JSON format from TallyPrime. In the sample request, provide the right values for these tags and attributes to experience the alteration of voucher.

**Integration use:** Amend an invoice (date, lines) after posting while preserving voucher identity.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svVchImportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `import` | Yes |
| `type` | `data` | Yes |
| `id` | `Vouchers` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svVchImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Voucher",
        "vchtype": "Sales",
        "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000055",
        "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:00000088",
        "action": "Alter",
        "objview": "Invoice Voucher View"
      },
      "date": "20250801",
      "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000055",
      "vouchertypename": "Sales"
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
 <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000059" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:00000090" VCHTYPE="Sales" ACTION="Alter" OBJVIEW="Accounting Voucher View">
  <DATE>20250801</DATE>
  <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000059</GUID>
 </VOUCHER>
</TALLYMESSAGE>
</DESC>
</BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: import" \
  -H "type: data" \
  -H "id: Vouchers" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟢 Official shape: Tally's published voucher import response):

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 1,
            "deleted": 0,
            "lastvchid": 71,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 0,
            "vchnumber": 32
        }
    }
}
```

**Success — XML** (🔵 Observed: captured from a live TallyPrime in `docs/Tally_Vouchers_Integration_Guide.md`; `CMPINFO` truncated):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <CREATED>0</CREATED>
                <ALTERED>1</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>71</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>0</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
        <DESC>
            <CMPINFO>
                <COMPANY>0</COMPANY>
                <GROUP>0</GROUP>
                <LEDGER>95</LEDGER>
                <!-- … one count element per object type (COSTCENTRE, GODOWN, STOCKITEM, UNIT, VOUCHERTYPE, …) … -->
                <VOUCHER>39</VOUCHER>
            </CMPINFO>
        </DESC>
    </BODY>
</ENVELOPE>
```

Check `altered` = 1 **and** `errors` + `exceptions` = 0. `status: "1"` only means the request was processed, not that the record was accepted. `lastvchid` is the internal id (MASTERID) of the last voucher written, and `vchnumber` is its voucher number.

#### Error Responses

**Record-level failure:** `Voucher does not exist!`. Source: 🔵 Observed.

Cause: `remoteid` / `vchkey` / `guid` do not match any voucher in the company (e.g. ids copied from another company or the voucher was deleted).

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <LINEERROR>Voucher does not exist!</LINEERROR>
                <CREATED>0</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>1</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
    </BODY>
</ENVELOPE>
```

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 1
        }
    }
}
```

> In JSON the failure shows up as non-zero `errors` / `exceptions` counts. Tally does not document the JSON key that carries the line-error text, so log the raw response body; this repo's parser (`parse_tally_response_metrics`) also checks `import_result.line_error`.

See also [Common errors](#110-common-error-responses) (company not loaded, unknown request, Tally not running).

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `import` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `data` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `Vouchers` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svVchImportFormat]` | `<STATICVARIABLES><SVVCHIMPORTFORMAT>` | Yes (voucher import) | String | `jsonex` | Import format of vouchers: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `tallymessage[]` | `<TALLYMESSAGE>` | Yes | Array<Object> |  | The objects to import (masters or vouchers). One request can carry many objects. |
| `tallymessage[].metadata` | `<VOUCHER …>` attributes | Yes | Object |  | Object identity block: type, name/identifiers and action. |
| `tallymessage[].metadata.type` | element name `<VOUCHER>` | Yes | String | `Voucher` | Object type: `Ledger`, `Group`, `Stock Item`, `Stock Group`, `Unit`, `Voucher`. |
| `tallymessage[].metadata.vchtype` | `VCHTYPE` attribute | Yes (vouchers) | String | `Sales` | Voucher type name, e.g. `Payment`, `Receipt`, `Sales`, `Purchase`. |
| `tallymessage[].metadata.remoteid` | `REMOTEID` attribute | Yes (alter/delete vch) | String (GUID) | `f0347998-2c19-4a5e-a4ed-01f589cb92a5-000…` | Voucher's REMOTEID as exported from Tally. Identifies the voucher to alter/delete. |
| `tallymessage[].metadata.vchkey` | `VCHKEY` attribute | Yes (alter/delete vch) | String | `f0347998-2c19-4a5e-a4ed-01f589cb92a5-000…` | Voucher's VCHKEY as exported from Tally. |
| `tallymessage[].metadata.action` | `ACTION` attribute | Yes | String | `Alter` | `Create`, `Alter`, or `Delete` (case-insensitive). |
| `tallymessage[].metadata.objview` | `OBJVIEW` attribute | Yes (vouchers) | String | `Invoice Voucher View` | `Accounting Voucher View` (ledger-only vouchers) or `Invoice Voucher View` (item invoices). |
| `tallymessage[].date` | `<VOUCHER>/DATE` | Yes | Date (YYYYMMDD) | `20250801` | Voucher date. Must fall inside the company's books period (Educational Mode: only 1st, 2nd, 31st). |
| `tallymessage[].guid` | `<VOUCHER>/GUID` | Yes (alter/delete) | String (GUID) | `f0347998-2c19-4a5e-a4ed-01f589cb92a5-000…` | Tally GUID of the voucher; must match the existing voucher. |
| `tallymessage[].vouchertypename` | `<VOUCHER>/VOUCHERTYPENAME` | Yes | String | `Sales` | Voucher type name, e.g. `Payment`. |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Alter any Sales Voucher in the company and change the date to ‘1st September 2025’ | Change the value of Date tag, and set correct values for ‘guid’, ‘vchkey’, and ‘remoteid’ | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/sales/alter/json/TaskAlterSalesVoucherJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/sales/alter/xml/TaskAlterSalesVoucherXML.txt) |

### 4.3.4 Delete a Sales

> Explorer id: `sales-delete` · Kind: **import** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#sales-delete)

#### Description

Each TallyPrime voucher has unique system-generated identifiers. To delete a voucher, ensure the ‘guid’, ‘vchkey’, and ‘remoteid’ match the existing voucher’s values, which can be obtained by exporting it in XML/JSON format from TallyPrime. In the sample request, provide the right values for these tags and attributes to experience the deletion of voucher.

**Integration use:** Cancel an invoice voided upstream.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svVchImportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `import` | Yes |
| `type` | `data` | Yes |
| `id` | `Vouchers` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svVchImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Voucher",
        "vchtype": "Sales",
        "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000055",
        "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:00000088",
        "action": "Delete",
        "objview": "Invoice Voucher View"
      },
      "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000055"
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
 <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000059" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:00000090" VCHTYPE="Sales" ACTION="Delete" OBJVIEW="Accounting Voucher View">
  <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000059</GUID>
 </VOUCHER>
</TALLYMESSAGE>
</DESC>
</BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: import" \
  -H "type: data" \
  -H "id: Vouchers" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟢 Official shape: Tally's published voucher import response):

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 0,
            "deleted": 1,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 0,
            "vchnumber": 32
        }
    }
}
```

**Success — XML** (🔵 Observed: captured from a live TallyPrime in `docs/Tally_Vouchers_Integration_Guide.md`; `CMPINFO` truncated):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <CREATED>0</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>1</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>0</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
        <DESC>
            <CMPINFO>
                <COMPANY>0</COMPANY>
                <GROUP>0</GROUP>
                <LEDGER>95</LEDGER>
                <!-- … one count element per object type (COSTCENTRE, GODOWN, STOCKITEM, UNIT, VOUCHERTYPE, …) … -->
                <VOUCHER>39</VOUCHER>
            </CMPINFO>
        </DESC>
    </BODY>
</ENVELOPE>
```

Check `deleted` = 1 **and** `errors` + `exceptions` = 0. `status: "1"` only means the request was processed, not that the record was accepted. `lastvchid` is the internal id (MASTERID) of the last voucher written, and `vchnumber` is its voucher number.

#### Error Responses

**Record-level failure:** `Cannot delete unnamed object: VOUCHER!`. Source: 🔵 Observed.

Cause: The voucher identifiers were not sent on the object itself (`REMOTEID`/`VCHKEY` attributes in XML, `metadata.remoteid`/`metadata.vchkey` in JSON).

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <LINEERROR>Cannot delete unnamed object: VOUCHER!</LINEERROR>
                <CREATED>0</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>1</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
    </BODY>
</ENVELOPE>
```

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 1
        }
    }
}
```

> In JSON the failure shows up as non-zero `errors` / `exceptions` counts. Tally does not document the JSON key that carries the line-error text, so log the raw response body; this repo's parser (`parse_tally_response_metrics`) also checks `import_result.line_error`.

See also [Common errors](#110-common-error-responses) (company not loaded, unknown request, Tally not running).

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `import` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `data` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `Vouchers` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svVchImportFormat]` | `<STATICVARIABLES><SVVCHIMPORTFORMAT>` | Yes (voucher import) | String | `jsonex` | Import format of vouchers: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `tallymessage[]` | `<TALLYMESSAGE>` | Yes | Array<Object> |  | The objects to import (masters or vouchers). One request can carry many objects. |
| `tallymessage[].metadata` | `<VOUCHER …>` attributes | Yes | Object |  | Object identity block: type, name/identifiers and action. |
| `tallymessage[].metadata.type` | element name `<VOUCHER>` | Yes | String | `Voucher` | Object type: `Ledger`, `Group`, `Stock Item`, `Stock Group`, `Unit`, `Voucher`. |
| `tallymessage[].metadata.vchtype` | `VCHTYPE` attribute | Yes (vouchers) | String | `Sales` | Voucher type name, e.g. `Payment`, `Receipt`, `Sales`, `Purchase`. |
| `tallymessage[].metadata.remoteid` | `REMOTEID` attribute | Yes (alter/delete vch) | String (GUID) | `f0347998-2c19-4a5e-a4ed-01f589cb92a5-000…` | Voucher's REMOTEID as exported from Tally. Identifies the voucher to alter/delete. |
| `tallymessage[].metadata.vchkey` | `VCHKEY` attribute | Yes (alter/delete vch) | String | `f0347998-2c19-4a5e-a4ed-01f589cb92a5-000…` | Voucher's VCHKEY as exported from Tally. |
| `tallymessage[].metadata.action` | `ACTION` attribute | Yes | String | `Delete` | `Create`, `Alter`, or `Delete` (case-insensitive). |
| `tallymessage[].metadata.objview` | `OBJVIEW` attribute | Yes (vouchers) | String | `Invoice Voucher View` | `Accounting Voucher View` (ledger-only vouchers) or `Invoice Voucher View` (item invoices). |
| `tallymessage[].guid` | `<VOUCHER>/GUID` | Yes (alter/delete) | String (GUID) | `f0347998-2c19-4a5e-a4ed-01f589cb92a5-000…` | Tally GUID of the voucher; must match the existing voucher. |

### 4.3.5 Pull all Sales vouchers

> Explorer id: `sales-pull-all` · Kind: **collection** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#sales-pull-all)

#### Description

This action sends a request to TallyPrime to fetch all sales vouchers from the loaded company.

**Integration use:** Pull all sales vouchers for revenue reconciliation or analytics.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svExportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVEXPORTFORMAT>XML</SVEXPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `export` | Yes |
| `type` | `collection` | Yes |
| `id` | `TSPLAllSalesVouchers` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tdlmessage": [
    {
      "definitions": [
        {
          "metadata": {
            "name": "TSPL All Sales Vouchers",
            "type": "Collection"
          },
          "attributes": [
            {
              "Type": "Vouchers:VoucherType"
            },
            {
              "Child Of": "$$VchTypeSales"
            },
            {
              "Native Method": "Date, VoucherTypeName, VoucherNumber, Partyledgername"
            }
          ]
        }
      ]
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Collection</TYPE>
        <ID>TSPL ALL Sales Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
<TDL>
<TDLMESSAGE>
  <COLLECTION NAME="TSPL ALL Sales Vouchers" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
   <TYPE>Vouchers:VoucherType</TYPE>
   <CHILDOF>$$VchTypeSales</CHILDOF>
   <NATIVEMETHOD>Date, VoucherTypeName, VoucherNumber, Partyledgername</NATIVEMETHOD>
  </COLLECTION>
</TDLMESSAGE>
</TDL>
        </DESC>
    </BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: export" \
  -H "type: collection" \
  -H "id: TSPLAllSalesVouchers" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟡 Illustrative (structure follows Tally's published voucher-collection sample: `metadata.remoteid/vchkey`, typed fields, `cmp_dep_type`; values invented)):

```json
{
    "status": "1",
    "data": {
        "metadata": {
            "is_cmp_dep_type": true,
            "cmp_locus": 4,
            "cmp_dep_type": 64
        },
        "collection": [
            {
                "metadata": {
                    "type": "Voucher",
                    "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000091",
                    "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2b3:00000008",
                    "vchtype": "Sales",
                    "objview": "Invoice Voucher View"
                },
                "date": {
                    "type": "Date",
                    "value": "20250401"
                },
                "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000091",
                "vouchertypename": "Sales",
                "vouchernumber": "1",
                "partyledgername": {
                    "type": "String",
                    "value": "Amar Enterprises"
                },
                "masterid": {
                    "type": "Number",
                    "value": " 145"
                }
            },
            {
                "metadata": {
                    "type": "Voucher",
                    "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000092",
                    "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2b4:00000009",
                    "vchtype": "Sales",
                    "objview": "Invoice Voucher View"
                },
                "date": {
                    "type": "Date",
                    "value": "20250831"
                },
                "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000092",
                "vouchertypename": "Sales",
                "vouchernumber": "2",
                "partyledgername": {
                    "type": "String",
                    "value": "Amar Enterprises"
                },
                "masterid": {
                    "type": "Number",
                    "value": " 146"
                }
            }
        ]
    }
}
```

**Success — XML** (🟡 Illustrative):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DESC>
        </DESC>
        <DATA>
            <COLLECTION>
                <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000091" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2b3:00000008" VCHTYPE="Sales" OBJVIEW="Invoice Voucher View">
                    <DATE TYPE="Date">20250401</DATE>
                    <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000091</GUID>
                    <VOUCHERTYPENAME TYPE="String">Sales</VOUCHERTYPENAME>
                    <VOUCHERNUMBER TYPE="String">1</VOUCHERNUMBER>
                    <PARTYLEDGERNAME TYPE="String">Amar Enterprises</PARTYLEDGERNAME>
                    <MASTERID TYPE="Number"> 145</MASTERID>
                </VOUCHER>
                <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000092" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2b4:00000009" VCHTYPE="Sales" OBJVIEW="Invoice Voucher View">
                    <DATE TYPE="Date">20250831</DATE>
                    <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000092</GUID>
                    <VOUCHERTYPENAME TYPE="String">Sales</VOUCHERTYPENAME>
                    <VOUCHERNUMBER TYPE="String">2</VOUCHERNUMBER>
                    <PARTYLEDGERNAME TYPE="String">Amar Enterprises</PARTYLEDGERNAME>
                    <MASTERID TYPE="Number"> 146</MASTERID>
                </VOUCHER>
            </COLLECTION>
        </DATA>
    </BODY>
</ENVELOPE>
```

#### Error Responses

- **Collection name mismatch** (🟡 Illustrative): if the `id` header / `<ID>` does not match a default collection or a definition in `tdlmessage`, Tally returns an error instead of data. TDL names ignore case and spaces (`TSPL All Payment Vouchers` = `TSPLAllPaymentVouchers`), but any other spelling difference breaks the match.
- **Invalid TDL** (bad attribute or formula): Tally may show an error dialog on the Tally screen and return nothing useful. Validate TDL in the Explorer before shipping it.
- **Empty result:** a valid request that matches nothing returns `status: "1"` with an empty `collection` (`<COLLECTION/>`).
- [Common errors](#110-common-error-responses) apply.

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `export` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `collection` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `TSPLAllSalesVouchers` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svExportFormat]` | `<STATICVARIABLES><SVEXPORTFORMAT>` | Yes (export) | String | `jsonex` | Response format: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `tdlmessage[]` | `<TDL><TDLMESSAGE>` | Cond. | Array<Object> |  | Inline TDL definitions (Collection / Report modification / System Formulae) that Tally loads before executing the request. |
| `tdlmessage[].definitions[]` | `<COLLECTION …>` | Cond. | Array<Object> |  | List of TDL definitions inside `tdlmessage`. |
| `tdlmessage[].definitions[].metadata.name` | `NAME` attribute | Yes | String | `TSPL All Sales Vouchers` | Definition name. For a Collection it must match the `id` header / `<ID>`. TDL names are case- and space-insensitive. |
| `tdlmessage[].definitions[].metadata.type` | element name | Yes | String | `Collection` | Definition kind: `Collection`, `Report`, or `System`. |
| `tdlmessage[].definitions[].attributes[].Type` | `<TYPE>` | Yes | String | `Vouchers:VoucherType` | Object type the collection gathers: `Ledger`, `Group`, `StockItem`, `StockGroup`, `Unit`, or `Vouchers:VoucherType` (vouchers of a voucher type). |
| `tdlmessage[].definitions[].attributes[].Child Of` | `<CHILDOF>` | No | String (TDL expr) | `$$VchTypeSales` | Restricts the collection to children of a parent. Accepts a literal (`"Gadgets"`) or a system-name function such as `$$GroupBank`, `$$GroupCurrentAssets`, `$$VchTypePayment`. |
| `tdlmessage[].definitions[].attributes[].Native Method` | `<NATIVEMETHOD>` | Yes | String (CSV) | `Date, VoucherTypeName, VoucherNumber, Pa…` | Comma-separated methods to fetch for every object in the collection. |

### 4.3.6 Pull all Sales vouchers for a period

> Explorer id: `sales-pull-period` · Kind: **collection** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#sales-pull-period)

#### Description

This action sends a request to TallyPrime to fetch sales vouchers for a selected date range.

**Integration use:** Incremental, date-bounded sales sync.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svExportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVEXPORTFORMAT>XML</SVEXPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `export` | Yes |
| `type` | `collection` | Yes |
| `id` | `TSPLSalesVouchers` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tdlmessage": [
    {
      "definitions": [
        {
          "metadata": {
            "name": "TSPL Sales Vouchers",
            "type": "Collection"
          },
          "attributes": [
            {
              "Type": "Vouchers:VoucherType"
            },
            {
              "Child Of": "$$VchTypeSales"
            },
            {
              "Native Method": "Date, VoucherTypeName, VoucherNumber, Partyledgername"
            },
            {
              "Filters": "Period Filter"
            }
          ]
        },
        {
          "metadata": {
            "name": "PeriodFilter",
            "type": "System",
            "sys_type": "Formulae",
            "ismodify": true
          },
          "value": "$Date >= ($$Date:\"01-05-2025\") AND $Date <= ($$Date:\"10-05-2025\")"
        }
      ]
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Collection</TYPE>
        <ID>TSPL Sales Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
<TDL>
<TDLMESSAGE>
  <COLLECTION NAME="TSPL Sales Vouchers" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
   <TYPE>Vouchers:VoucherType</TYPE>
   <CHILDOF>$$VchTypeSales</CHILDOF>
   <NATIVEMETHOD>Date, VoucherTypeName, VoucherNumber, Partyledgername</NATIVEMETHOD>
   <FILTERS>Period Filter</FILTERS>
  </COLLECTION>
  <SYSTEM TYPE="Formulae" NAME="PeriodFilter" ISMODIFY="Yes" ISFIXED="No" ISINTERNAL="No">$Date &gt;= ($$Date:"01-05-2025") AND $Date &lt;= ($$Date:"10-05-2025")  </SYSTEM>
</TDLMESSAGE>
</TDL>
        </DESC>
    </BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: export" \
  -H "type: collection" \
  -H "id: TSPLSalesVouchers" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟡 Illustrative (structure follows Tally's published voucher-collection sample: `metadata.remoteid/vchkey`, typed fields, `cmp_dep_type`; values invented)):

```json
{
    "status": "1",
    "data": {
        "metadata": {
            "is_cmp_dep_type": true,
            "cmp_locus": 4,
            "cmp_dep_type": 64
        },
        "collection": [
            {
                "metadata": {
                    "type": "Voucher",
                    "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000091",
                    "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2b3:00000008",
                    "vchtype": "Sales",
                    "objview": "Invoice Voucher View"
                },
                "date": {
                    "type": "Date",
                    "value": "20250402"
                },
                "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000091",
                "vouchertypename": "Sales",
                "vouchernumber": "1",
                "partyledgername": {
                    "type": "String",
                    "value": "Amar Enterprises"
                },
                "masterid": {
                    "type": "Number",
                    "value": " 145"
                }
            },
            {
                "metadata": {
                    "type": "Voucher",
                    "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000092",
                    "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2b4:00000009",
                    "vchtype": "Sales",
                    "objview": "Invoice Voucher View"
                },
                "date": {
                    "type": "Date",
                    "value": "20250402"
                },
                "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000092",
                "vouchertypename": "Sales",
                "vouchernumber": "2",
                "partyledgername": {
                    "type": "String",
                    "value": "Amar Enterprises"
                },
                "masterid": {
                    "type": "Number",
                    "value": " 146"
                }
            }
        ]
    }
}
```

**Success — XML** (🟡 Illustrative):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DESC>
        </DESC>
        <DATA>
            <COLLECTION>
                <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000091" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2b3:00000008" VCHTYPE="Sales" OBJVIEW="Invoice Voucher View">
                    <DATE TYPE="Date">20250402</DATE>
                    <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000091</GUID>
                    <VOUCHERTYPENAME TYPE="String">Sales</VOUCHERTYPENAME>
                    <VOUCHERNUMBER TYPE="String">1</VOUCHERNUMBER>
                    <PARTYLEDGERNAME TYPE="String">Amar Enterprises</PARTYLEDGERNAME>
                    <MASTERID TYPE="Number"> 145</MASTERID>
                </VOUCHER>
                <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000092" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2b4:00000009" VCHTYPE="Sales" OBJVIEW="Invoice Voucher View">
                    <DATE TYPE="Date">20250402</DATE>
                    <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000092</GUID>
                    <VOUCHERTYPENAME TYPE="String">Sales</VOUCHERTYPENAME>
                    <VOUCHERNUMBER TYPE="String">2</VOUCHERNUMBER>
                    <PARTYLEDGERNAME TYPE="String">Amar Enterprises</PARTYLEDGERNAME>
                    <MASTERID TYPE="Number"> 146</MASTERID>
                </VOUCHER>
            </COLLECTION>
        </DATA>
    </BODY>
</ENVELOPE>
```

#### Error Responses

- **Collection name mismatch** (🟡 Illustrative): if the `id` header / `<ID>` does not match a default collection or a definition in `tdlmessage`, Tally returns an error instead of data. TDL names ignore case and spaces (`TSPL All Payment Vouchers` = `TSPLAllPaymentVouchers`), but any other spelling difference breaks the match.
- **Invalid TDL** (bad attribute or formula): Tally may show an error dialog on the Tally screen and return nothing useful. Validate TDL in the Explorer before shipping it.
- **Empty result:** a valid request that matches nothing returns `status: "1"` with an empty `collection` (`<COLLECTION/>`).
- [Common errors](#110-common-error-responses) apply.

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `export` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `collection` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `TSPLSalesVouchers` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svExportFormat]` | `<STATICVARIABLES><SVEXPORTFORMAT>` | Yes (export) | String | `jsonex` | Response format: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `tdlmessage[]` | `<TDL><TDLMESSAGE>` | Cond. | Array<Object> |  | Inline TDL definitions (Collection / Report modification / System Formulae) that Tally loads before executing the request. |
| `tdlmessage[].definitions[]` | `<COLLECTION …>` | Cond. | Array<Object> |  | List of TDL definitions inside `tdlmessage`. |
| `tdlmessage[].definitions[].metadata.name` | `NAME` attribute | Yes | String | `TSPL Sales Vouchers` | Definition name. For a Collection it must match the `id` header / `<ID>`. TDL names are case- and space-insensitive. |
| `tdlmessage[].definitions[].metadata.type` | element name | Yes | String | `Collection` | Definition kind: `Collection`, `Report`, or `System`. |
| `tdlmessage[].definitions[].attributes[].Type` | `<TYPE>` | Yes | String | `Vouchers:VoucherType` | Object type the collection gathers: `Ledger`, `Group`, `StockItem`, `StockGroup`, `Unit`, or `Vouchers:VoucherType` (vouchers of a voucher type). |
| `tdlmessage[].definitions[].attributes[].Child Of` | `<CHILDOF>` | No | String (TDL expr) | `$$VchTypeSales` | Restricts the collection to children of a parent. Accepts a literal (`"Gadgets"`) or a system-name function such as `$$GroupBank`, `$$GroupCurrentAssets`, `$$VchTypePayment`. |
| `tdlmessage[].definitions[].attributes[].Native Method` | `<NATIVEMETHOD>` | Yes | String (CSV) | `Date, VoucherTypeName, VoucherNumber, Pa…` | Comma-separated methods to fetch for every object in the collection. |
| `tdlmessage[].definitions[].attributes[].Filters` | `<FILTERS>` | No | String | `Period Filter` | Name of a System Formula used to filter the collection server-side. |
| `tdlmessage[].definitions[].metadata.sys_type` | `TYPE` attribute | Cond. | String | `Formulae` | For `type: System` only. `Formulae` declares named formulae used by `Filters`. |
| `tdlmessage[].definitions[].metadata.ismodify` | `ISMODIFY` attribute | No | Boolean | `true` | `true` modifies an existing (default) definition instead of declaring a new one (`#` / `ISMODIFY="Yes"` in XML). |
| `tdlmessage[].definitions[].value` | element text | Cond. | String (TDL expr) | `$Date >= ($$Date:"01-05-2025") AND $Date…` | Body of a System Formula, e.g. `$ClosingBalance = 0`. |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Fetch the sales vouchers for a single date “1st June 2025” | Change the value of the Filter Formula | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/sales/pull-period/json/TaskPullAllSaleswithPeriodJSON.txt) |
| Fetch the Sales vouchers for a single date “1st June 2025” | Change the value of the Filter Formula | [XML](https://tallysolutions.com/tallyprime-api-explorer/files/sales/pull-period/xml/TaskPullAllSaleswithPeriodXML.txt) |

## 4.4 Purchase

### 4.4.0 Purchase — Overview & Field Reference

> 🟢 Official: converted from the Explorer's "About Purchase" page.

A Purchase Voucher is used to record all purchase transactions of goods or services made by the business. It captures details such as the supplier involved, items purchased, quantities, rates, and applicable taxes, ensuring proper tracking of expenses and stock inflow.

Each purchase transaction impacts at least two ledgers typically crediting the supplier (party) ledger and debiting the purchase or expense ledger, along with affecting inventory for the items purchased, thereby maintaining accurate financial and stock records.

| Tag | Mandatory | Data Type | Explanation |
|---|---|---|---|
| VoucherType Name | Yes | String | Defines the type of voucher under which the transaction is recorded. Since we want to create a purchase voucher, we would provide value as   Purchase. |
| Date | Yes | String | Indicates the transaction date in Tally-accepted format (YYYYMMDD). |
| VoucherNumber | Conditional | String | By default, Tally auto-generates voucher numbers. This tag is required only if you want to pass a custom voucher number from your system. |
| PartyLedgerName | Yes | String | Specifies the name of primary party or account involved in the transaction (e.g., supplier or cash/bank ) |
| AllLedgerEntries | Yes | Collection | Collection of ledger entries forming the transaction; ensures debit and credit entries are captured |
| LedgerName | Yes | String | Name of the ledger affected in the transaction |
| IsDeemedPositive | Yes | Logical / Boolean | Determines whether the entry is treated as Debit (Yes) or Credit (No) |
| IsPartyLedger | Yes | Logical / Boolean | Indicates whether the ledger is the main party ledger in the transaction |
| Amount | Yes | Amount | Specifies the transaction amount |

Additional tags of inventory information would depend on whether the transaction contains stock items.

**Sample — XML Format**

```xml
<ENVELOPE>
 <HEADER>
  <TALLYREQUEST>Import Data</TALLYREQUEST>
 </HEADER>
 <BODY>
    <TALLYMESSAGE>
     <VOUCHER VCHTYPE="Purchase" ACTION="Create" OBJVIEW="Invoice Voucher View">
      <DATE>20260321</DATE>
      <PARTYLEDGERNAME>Akshaya Enterprises</PARTYLEDGERNAME>
      <VOUCHERNUMBER>5</VOUCHERNUMBER>
      <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
      <ISINVOICE>Yes</ISINVOICE>
      <ALLINVENTORYENTRIES.LIST>
       <STOCKITEMNAME>Hp Smart Tank 670 Printers</STOCKITEMNAME>
       <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
       <RATE>25000.00/nos</RATE>
       <AMOUNT>-25000.00</AMOUNT>
       <ACTUALQTY> 1 nos</ACTUALQTY>
       <BILLEDQTY> 1 nos</BILLEDQTY>
       <ACCOUNTINGALLOCATIONS.LIST>
        <LEDGERNAME>Purchase</LEDGERNAME>
        <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
        <AMOUNT>-25000.00</AMOUNT>
       </ACCOUNTINGALLOCATIONS.LIST>
      </ALLINVENTORYENTRIES.LIST>
      <LEDGERENTRIES.LIST>
       <LEDGERNAME>Akshaya Enterprises</LEDGERNAME>
       <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
       <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
       <AMOUNT>25000.00</AMOUNT>
       <BILLALLOCATIONS.LIST>
        <NAME>5</NAME>
        <BILLTYPE>New Ref</BILLTYPE>
        <AMOUNT>25000.00</AMOUNT>
       </BILLALLOCATIONS.LIST>
      </LEDGERENTRIES.LIST>
     </VOUCHER>
    </TALLYMESSAGE>
   </REQUESTDATA>
  </IMPORTDATA>
 </BODY>
</ENVELOPE>

```

**Sample — JSON Format**

```json
{
  "tallymessage": [
    {
      "metadata": {
        "type": "Voucher",
        "action": "Create",
        "objectview": "Invoice Voucher View"
      },
      "DATE": "20260321",
      "VOUCHERTYPENAME": "Purchase",
      "VOUCHERNUMBER": "5",
      "PERSISTEDVIEW": "Invoice Voucher View",
      "ISINVOICE": "Yes",
      "PARTYLEDGERNAME": "Akshaya Enterprises",

      "ALLINVENTORYENTRIES.LIST": [
        {
          "STOCKITEMNAME": "Hp Smart Tank 670 Printers",
          "ISDEEMEDPOSITIVE": "Yes",
          "RATE": "25000.00/nos",
          "AMOUNT": -25000,
          "ACTUALQTY": "1 nos",
          "BILLEDQTY": "1 nos",

          "ACCOUNTINGALLOCATIONS.LIST": [
            {
              "LEDGERNAME": "Purchase",
              "ISDEEMEDPOSITIVE": "Yes",
              "AMOUNT": -25000
            }
          ]
        }
      ],

      "LEDGERENTRIES.LIST": [
        {
          "LEDGERNAME": "Akshaya Enterprises",
          "ISDEEMEDPOSITIVE": "No",
          "ISPARTYLEDGER": "Yes",
          "AMOUNT": 25000,

          "BILLALLOCATIONS.LIST": [
            {
              "NAME": "5",
              "BILLTYPE": "New Ref",
              "AMOUNT": 25000
            }
          ]
        }
      ]
    }
  ]
}

```

### 4.4.1 Create Purchase with Item

> Explorer id: `purchase-create-item` · Kind: **import** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#purchase-create-item)

#### Description

An Item Purchase Voucher is created by providing the Voucher Type, Date, Purchase Ledger (Debit), and Supplier Ledger (Credit), along with item details and amount. These details, when passed through the appropriate methods and collections of the Voucher object, result in the successful creation of the voucher.

**Integration use:** Post supplier bills with item lines so inventory and payables update together.

**Notes:**

- ⚠️ The Explorer's JSON sample has **no `static_variables`**. In production always add `svVchImportFormat = jsonex` and `svCurrentCompany`, otherwise the voucher goes to whichever company is active.
- Purchase direction: item and purchase-ledger amounts Debit (negative); supplier Credit (positive).

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svVchImportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `import` | Yes |
| `type` | `data` | Yes |
| `id` | `Vouchers` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "tallymessage": [
    {
      "metadata": {
        "type": "Voucher",
        "vchtype": "Purchase",
        "action": "Create",
        "objview": "Invoice Voucher View"
      },
      "date": "20260301",
      "vchstatusdate": "20260301",
      "gstregistrationtype": "\u0004 Unknown",
      "statename": "Alabama",
      "countryofresidence": "United States of America",
      "vouchertypename": "Purchase",
      "partyname": "International Party",
      "partyledgername": "International Party",
      "basicbuyername": "Bhrama Enterprises",
      "cmpgstregistrationtype": "Regular",
      "partymailingname": "International Party",
      "consigneegstin": "29AAECP4424C1ZN",
      "consigneemailingname": "Bhrama Enterprises",
      "consigneestatename": "Karnataka",
      "cmpgststate": "Karnataka",
      "consigneecountryname": "India",
      "basicbasepartyname": "International Party",
      "effectivedate": "20260301",
      "isinvoice": true,
      "allinventoryentries": [
        {
          "stockitemname": "Computer US",
          "isdeemedpositive": true,
          "rate": "10000.00/nos",
          "amount": "-200000.00",
          "actualqty": " 20 nos",
          "billedqty": " 20 nos",
          "batchallocations": [
            {
              "godownname": "Main Location",
              "batchname": "Primary Batch",
              "amount": "-200000.00",
              "actualqty": " 20 nos",
              "billedqty": " 20 nos"
            }
          ],
          "accountingallocations": [
            {
              "ledgername": "Purchase",
              "isdeemedpositive": true,
              "ispartyledger": false,
              "amount": "-200000.00"
            }
          ]
        }
      ],
      "ledgerentries": [
        {
          "ledgername": "International Party",
          "isdeemedpositive": false,
          "ispartyledger": true,
          "amount": "200000.00",
          "billallocations": [
            {
              "name": "12",
              "billtype": "New Ref",
              "amount": "200000.00"
            }
          ]
        }
      ]
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
  <VOUCHER VCHTYPE="Purchase" ACTION="Create" OBJVIEW="Invoice Voucher View">
      <DATE>20260301</DATE>
      <VCHSTATUSDATE>20260301</VCHSTATUSDATE>
      <GSTREGISTRATIONTYPE>&#4; Unknown</GSTREGISTRATIONTYPE>
      <STATENAME>Alabama</STATENAME>
      <COUNTRYOFRESIDENCE>United States of America</COUNTRYOFRESIDENCE>
      <VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
      <PARTYNAME>International Party</PARTYNAME>
      <PARTYLEDGERNAME>International Party</PARTYLEDGERNAME>
      <BASICBUYERNAME>Bhrama Enterprises</BASICBUYERNAME>
      <CMPGSTREGISTRATIONTYPE>Regular</CMPGSTREGISTRATIONTYPE>
      <PARTYMAILINGNAME>International Party</PARTYMAILINGNAME>
      <CONSIGNEEGSTIN>29AAECP4424C1ZN</CONSIGNEEGSTIN>
      <CONSIGNEEMAILINGNAME>Bhrama Enterprises</CONSIGNEEMAILINGNAME>
      <CONSIGNEESTATENAME>Karnataka</CONSIGNEESTATENAME>
      <CMPGSTSTATE>Karnataka</CMPGSTSTATE>
      <CONSIGNEECOUNTRYNAME>India</CONSIGNEECOUNTRYNAME>
      <BASICBASEPARTYNAME>International Party</BASICBASEPARTYNAME>
      <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
      <EFFECTIVEDATE>20260301</EFFECTIVEDATE>
      <ISINVOICE>Yes</ISINVOICE>
      <ALLINVENTORYENTRIES.LIST>
       <STOCKITEMNAME>Computer US</STOCKITEMNAME>
       <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
       <RATE>10000.00/nos</RATE>
       <AMOUNT>-200000.00</AMOUNT>
       <ACTUALQTY> 20 nos</ACTUALQTY>
       <BILLEDQTY> 20 nos</BILLEDQTY>
       <BATCHALLOCATIONS.LIST>
        <GODOWNNAME>Main Location</GODOWNNAME>
        <BATCHNAME>Primary Batch</BATCHNAME>
        <AMOUNT>-200000.00</AMOUNT>
        <ACTUALQTY> 20 nos</ACTUALQTY>
        <BILLEDQTY> 20 nos</BILLEDQTY>
       </BATCHALLOCATIONS.LIST>
       <ACCOUNTINGALLOCATIONS.LIST>
        <LEDGERNAME>Purchase</LEDGERNAME>
        <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
        <ISPARTYLEDGER>No</ISPARTYLEDGER>
        <AMOUNT>-200000.00</AMOUNT>
       </ACCOUNTINGALLOCATIONS.LIST>
      </ALLINVENTORYENTRIES.LIST>
      <LEDGERENTRIES.LIST>
       <LEDGERNAME>International Party</LEDGERNAME>
       <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
       <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
       <AMOUNT>200000.00</AMOUNT>
       <BILLALLOCATIONS.LIST>
        <NAME>12</NAME>
        <BILLTYPE>New Ref</BILLTYPE>
        <AMOUNT>200000.00</AMOUNT>
       </BILLALLOCATIONS.LIST>
      </LEDGERENTRIES.LIST>
     </VOUCHER>
</TALLYMESSAGE>
</DESC>
</BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: import" \
  -H "type: data" \
  -H "id: Vouchers" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟢 Official shape: Tally's published voucher import response):

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 1,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 71,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 0,
            "vchnumber": 33
        }
    }
}
```

**Success — XML** (🔵 Observed: captured from a live TallyPrime in `docs/Tally_Vouchers_Integration_Guide.md`; `CMPINFO` truncated):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <CREATED>1</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>71</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>0</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
        <DESC>
            <CMPINFO>
                <COMPANY>0</COMPANY>
                <GROUP>0</GROUP>
                <LEDGER>95</LEDGER>
                <!-- … one count element per object type (COSTCENTRE, GODOWN, STOCKITEM, UNIT, VOUCHERTYPE, …) … -->
                <VOUCHER>39</VOUCHER>
            </CMPINFO>
        </DESC>
    </BODY>
</ENVELOPE>
```

Check `created` = 1 **and** `errors` + `exceptions` = 0. `status: "1"` only means the request was processed, not that the record was accepted. `lastvchid` is the internal id (MASTERID) of the last voucher written, and `vchnumber` is its voucher number.

#### Error Responses

**Record-level failure:** `Ledger 'International Party' does not exist!`. Source: 🟡 Illustrative (message pattern also reported by other Tally integrations).

Cause: A ledger (or stock item / godown) referenced by the voucher is missing, or misspelt. Create masters before vouchers.

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <LINEERROR>Ledger &apos;International Party&apos; does not exist!</LINEERROR>
                <CREATED>0</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>1</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
    </BODY>
</ENVELOPE>
```

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 1
        }
    }
}
```

> In JSON the failure shows up as non-zero `errors` / `exceptions` counts. Tally does not document the JSON key that carries the line-error text, so log the raw response body; this repo's parser (`parse_tally_response_metrics`) also checks `import_result.line_error`.

See also [Common errors](#110-common-error-responses) (company not loaded, unknown request, Tally not running).

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `import` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `data` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `Vouchers` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `tallymessage[]` | `<TALLYMESSAGE>` | Yes | Array<Object> |  | The objects to import (masters or vouchers). One request can carry many objects. |
| `tallymessage[].metadata` | `<VOUCHER …>` attributes | Yes | Object |  | Object identity block: type, name/identifiers and action. |
| `tallymessage[].metadata.type` | element name `<VOUCHER>` | Yes | String | `Voucher` | Object type: `Ledger`, `Group`, `Stock Item`, `Stock Group`, `Unit`, `Voucher`. |
| `tallymessage[].metadata.vchtype` | `VCHTYPE` attribute | Yes (vouchers) | String | `Purchase` | Voucher type name, e.g. `Payment`, `Receipt`, `Sales`, `Purchase`. |
| `tallymessage[].metadata.action` | `ACTION` attribute | Yes | String | `Create` | `Create`, `Alter`, or `Delete` (case-insensitive). |
| `tallymessage[].metadata.objview` | `OBJVIEW` attribute | Yes (vouchers) | String | `Invoice Voucher View` | `Accounting Voucher View` (ledger-only vouchers) or `Invoice Voucher View` (item invoices). |
| `tallymessage[].date` | `<VOUCHER>/DATE` | Yes | Date (YYYYMMDD) | `20260301` | Voucher date. Must fall inside the company's books period (Educational Mode: only 1st, 2nd, 31st). |
| `tallymessage[].vchstatusdate` | `<VOUCHER>/VCHSTATUSDATE` | No | Date (YYYYMMDD) | `20260301` | Voucher status date (usually = `date`). |
| `tallymessage[].gstregistrationtype` | `<VOUCHER>/GSTREGISTRATIONTYPE` | Cond. | String | `\u0004 Unknown` | Party GST registration type: `Regular`, `Composition`, `Consumer`, `Unregistered`, `\u0004 Unknown`. |
| `tallymessage[].statename` | `<VOUCHER>/STATENAME` | Cond. | String | `Alabama` | Party state. |
| `tallymessage[].countryofresidence` | `<VOUCHER>/COUNTRYOFRESIDENCE` | No | String | `United States of America` | Party country. |
| `tallymessage[].vouchertypename` | `<VOUCHER>/VOUCHERTYPENAME` | Yes | String | `Purchase` | Voucher type name, e.g. `Payment`. |
| `tallymessage[].partyname` | `<VOUCHER>/PARTYNAME` | No | String | `International Party` | Party name printed on the voucher. |
| `tallymessage[].partyledgername` | `<VOUCHER>/PARTYLEDGERNAME` | Yes | String | `International Party` | Primary party / account ledger of the voucher. |
| `tallymessage[].basicbuyername` | `<VOUCHER>/BASICBUYERNAME` | No | String | `Bhrama Enterprises` | Buyer name (invoice). |
| `tallymessage[].cmpgstregistrationtype` | `<VOUCHER>/CMPGSTREGISTRATIONTYPE` | Cond. | String | `Regular` | Company GST registration type. |
| `tallymessage[].partymailingname` | `<VOUCHER>/PARTYMAILINGNAME` | No | String | `International Party` | Party mailing name. |
| `tallymessage[].consigneegstin` | `<VOUCHER>/CONSIGNEEGSTIN` | No | String | `29AAECP4424C1ZN` | Consignee GSTIN. |
| `tallymessage[].consigneemailingname` | `<VOUCHER>/CONSIGNEEMAILINGNAME` | No | String | `Bhrama Enterprises` | Consignee name. |
| `tallymessage[].consigneestatename` | `<VOUCHER>/CONSIGNEESTATENAME` | No | String | `Karnataka` | Consignee state. |
| `tallymessage[].cmpgststate` | `<VOUCHER>/CMPGSTSTATE` | Cond. | String | `Karnataka` | Company GST state. |
| `tallymessage[].consigneecountryname` | `<VOUCHER>/CONSIGNEECOUNTRYNAME` | No | String | `India` | Consignee country. |
| `tallymessage[].basicbasepartyname` | `<VOUCHER>/BASICBASEPARTYNAME` | No | String | `International Party` | Base party name. |
| `tallymessage[].effectivedate` | `<VOUCHER>/EFFECTIVEDATE` | No | Date (YYYYMMDD) | `20260301` | Effective date (usually = `date`). |
| `tallymessage[].isinvoice` | `<VOUCHER>/ISINVOICE` | Cond. | Logical | `true` | `Yes` for Invoice-mode vouchers (with item lines). |
| `tallymessage[].allinventoryentries[]` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST` | Yes (item invoice) | Array<Object> |  | Item lines (`ALLINVENTORYENTRIES.LIST`). |
| `tallymessage[].allinventoryentries[].stockitemname` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/STOCKITEMNAME` | Yes | String | `Computer US` | Stock item on the line. Must already exist. |
| `tallymessage[].allinventoryentries[].isdeemedpositive` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/ISDEEMEDPOSITIVE` | Yes | Logical | `true` | `Yes`/`true` = Debit, `No`/`false` = Credit. |
| `tallymessage[].allinventoryentries[].rate` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/RATE` | Yes | Rate | `10000.00/nos` | Rate with unit, e.g. `75.00/nos`. |
| `tallymessage[].allinventoryentries[].amount` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/AMOUNT` | Yes | Amount | `-200000.00` | Line amount. Sign convention: Debit lines negative, Credit lines positive; all lines must net to zero. |
| `tallymessage[].allinventoryentries[].actualqty` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/ACTUALQTY` | Yes | Quantity | `20 nos` | Actual quantity with unit, e.g. `20 nos`. |
| `tallymessage[].allinventoryentries[].billedqty` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/BILLEDQTY` | Yes | Quantity | `20 nos` | Billed quantity with unit. |
| `tallymessage[].allinventoryentries[].batchallocations[]` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/BATCHALLOCATIONS.LIST` | Yes (items) | Array<Object> |  | Godown/batch split of the item line (`BATCHALLOCATIONS.LIST`). |
| `tallymessage[].allinventoryentries[].batchallocations[].godownname` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/BATCHALLOCATIONS.LIST/GODOWNNAME` | Yes | String | `Main Location` | Godown (location). Default company godown is `Main Location`. |
| `tallymessage[].allinventoryentries[].batchallocations[].batchname` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/BATCHALLOCATIONS.LIST/BATCHNAME` | Cond. | String | `Primary Batch` | Batch name (`Primary Batch` when batches are not tracked). |
| `tallymessage[].allinventoryentries[].batchallocations[].amount` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/BATCHALLOCATIONS.LIST/AMOUNT` | Yes | Amount | `-200000.00` | Line amount. Sign convention: Debit lines negative, Credit lines positive; all lines must net to zero. |
| `tallymessage[].allinventoryentries[].batchallocations[].actualqty` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/BATCHALLOCATIONS.LIST/ACTUALQTY` | Yes | Quantity | `20 nos` | Actual quantity with unit, e.g. `20 nos`. |
| `tallymessage[].allinventoryentries[].batchallocations[].billedqty` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/BATCHALLOCATIONS.LIST/BILLEDQTY` | Yes | Quantity | `20 nos` | Billed quantity with unit. |
| `tallymessage[].allinventoryentries[].accountingallocations[]` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/ACCOUNTINGALLOCATIONS.LIST` | Yes (items) | Array<Object> |  | Sales/Purchase ledger the item amount posts to (`ACCOUNTINGALLOCATIONS.LIST`). |
| `tallymessage[].allinventoryentries[].accountingallocations[].ledgername` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/ACCOUNTINGALLOCATIONS.LIST/LEDGERNAME` | Yes | String | `Purchase` | Ledger affected by the line. Must already exist. |
| `tallymessage[].allinventoryentries[].accountingallocations[].isdeemedpositive` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/ACCOUNTINGALLOCATIONS.LIST/ISDEEMEDPOSITIVE` | Yes | Logical | `true` | `Yes`/`true` = Debit, `No`/`false` = Credit. |
| `tallymessage[].allinventoryentries[].accountingallocations[].ispartyledger` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/ACCOUNTINGALLOCATIONS.LIST/ISPARTYLEDGER` | Yes | Logical | `false` | `Yes` for the party/cash/bank line of the voucher. |
| `tallymessage[].allinventoryentries[].accountingallocations[].amount` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/ACCOUNTINGALLOCATIONS.LIST/AMOUNT` | Yes | Amount | `-200000.00` | Line amount. Sign convention: Debit lines negative, Credit lines positive; all lines must net to zero. |
| `tallymessage[].ledgerentries[]` | `<VOUCHER>/LEDGERENTRIES.LIST` | Yes (invoice view) | Array<Object> |  | Ledger lines (party, taxes) of an Invoice-view voucher (`LEDGERENTRIES.LIST`). |
| `tallymessage[].ledgerentries[].ledgername` | `<VOUCHER>/LEDGERENTRIES.LIST/LEDGERNAME` | Yes | String | `International Party` | Ledger affected by the line. Must already exist. |
| `tallymessage[].ledgerentries[].isdeemedpositive` | `<VOUCHER>/LEDGERENTRIES.LIST/ISDEEMEDPOSITIVE` | Yes | Logical | `false` | `Yes`/`true` = Debit, `No`/`false` = Credit. |
| `tallymessage[].ledgerentries[].ispartyledger` | `<VOUCHER>/LEDGERENTRIES.LIST/ISPARTYLEDGER` | Yes | Logical | `true` | `Yes` for the party/cash/bank line of the voucher. |
| `tallymessage[].ledgerentries[].amount` | `<VOUCHER>/LEDGERENTRIES.LIST/AMOUNT` | Yes | Amount | `200000.00` | Line amount. Sign convention: Debit lines negative, Credit lines positive; all lines must net to zero. |
| `tallymessage[].ledgerentries[].billallocations[]` | `<VOUCHER>/LEDGERENTRIES.LIST/BILLALLOCATIONS.LIST` | Cond. | Array<Object> |  | Bill-wise allocation for bill-wise-enabled party ledgers (`BILLALLOCATIONS.LIST`). |
| `tallymessage[].ledgerentries[].billallocations[].name` | `<VOUCHER>/LEDGERENTRIES.LIST/BILLALLOCATIONS.LIST/NAME` | Yes | String | `12` | Bill reference number (e.g. invoice no.). |
| `tallymessage[].ledgerentries[].billallocations[].billtype` | `<VOUCHER>/LEDGERENTRIES.LIST/BILLALLOCATIONS.LIST/BILLTYPE` | Yes | String | `New Ref` | `New Ref`, `Agst Ref`, `Advance`, or `On Account`. |
| `tallymessage[].ledgerentries[].billallocations[].amount` | `<VOUCHER>/LEDGERENTRIES.LIST/BILLALLOCATIONS.LIST/AMOUNT` | Yes | Amount | `200000.00` | Line amount. Sign convention: Debit lines negative, Credit lines positive; all lines must net to zero. |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Create a purchase Voucher with same ledgers but on date ‘1st Feb 2026” with quantity 10 nos, at same rate, with bill number ‘Bill28Pur1’ | Change the values of all Date tags, and all the quantity and amount tags | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/purchase/create-item/json/TaskCreatePurJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/purchase/create-item/xml/TaskCreatePurXML.txt) |

### 4.4.2 Create Purchase with GST

> Explorer id: `purchase-create-gst` · Kind: **import** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#purchase-create-gst)

#### Description

A Purchase Voucher with GST is created by providing the Voucher Type, Date, Purchase Ledger with GST enabled (Debit), and Supplier Ledger with GSTIN details(Credit), Duty ledgers(Debit): CGST, SGST for intra-state purchase and IGST for Interstate purchase, amount and item details if applicable. These details, when passed through the appropriate methods and collections of the Voucher object, result in the successful creation of the voucher.

**Integration use:** Post purchase bills with input GST lines so ITC is tracked correctly.

**Notes:**

- Input CGST/SGST (or IGST) ledgers are Debit lines.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svVchImportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `import` | Yes |
| `type` | `data` | Yes |
| `id` | `Vouchers` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svVchImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Voucher",
        "vchtype": "Purchase",
        "action": "Create",
        "objview": "Invoice Voucher View"
      },
      "date": "20250901",
      "vchstatusdate": "20250901",
      "gstregistrationtype": "Regular",
      "vatdealertype": "Regular",
      "statename": "Karnataka",
      "countryofresidence": "India",
      "partygstin": "29AAACH1004N1ZQ",
      "placeofsupply": "Karnataka",
      "vouchertypename": "Purchase",
      "partyname": "Mondal Enterprises",
      "gstregistration": {
        "value": "Karnataka Registration",
        "taxtype": "GST",
        "taxregistration": "29AAECP4424C1ZN"
      },
      "cmpgstin": "29AAECP4424C1ZN",
      "partyledgername": "Mondal Enterprises",
      "basicbuyername": "Bhrama Enterprises",
      "cmpgstregistrationtype": "Regular",
      "partymailingname": "Mondal Enterprises",
      "consigneegstin": "29AAECP4424C1ZN",
      "consigneemailingname": "Bhrama Enterprises",
      "consigneestatename": "Karnataka",
      "cmpgststate": "Karnataka",
      "consigneecountryname": "India",
      "basicbasepartyname": "Mondal Enterprises",
      "effectivedate": "20250901",
      "isinvoice": true,
      "allinventoryentries": [
        {
          "stockitemname": "Decaf Coffee",
          "gstovrdnineligibleitc": "\u0004 Not Applicable",
          "gstovrdnisrevchargeappl": "\u0004 Not Applicable",
          "gstovrdntaxability": "Taxable",
          "gstsourcetype": "Stock Item",
          "gstitemsource": "Decaf Coffee",
          "hsnsourcetype": "Stock Item",
          "hsnitemsource": "Decaf Coffee",
          "gstovrdntypeofsupply": "Goods",
          "gstrateinferapplicability": "As per Masters/Company",
          "gsthsninferapplicability": "As per Masters/Company",
          "isdeemedpositive": true,
          "rate": "15.00/nos",
          "amount": "-1500.00",
          "actualqty": " 100 nos",
          "billedqty": " 100 nos",
          "batchallocations": [
            {
              "godownname": "Main Location",
              "batchname": "Primary Batch",
              "amount": "-1500.00",
              "actualqty": " 100 nos",
              "billedqty": " 100 nos"
            }
          ],
          "accountingallocations": [
            {
              "ledgername": "GST Purchase",
              "isdeemedpositive": true,
              "ispartyledger": false,
              "amount": "-1500.00"
            }
          ],
          "ratedetails": [
            {
              "gstratedutyhead": "CGST",
              "gstratevaluationtype": "Based on Value",
              "gstrate": " 2"
            },
            {
              "gstratedutyhead": "SGST/UTGST",
              "gstratevaluationtype": "Based on Value",
              "gstrate": " 2"
            },
            {
              "gstratedutyhead": "IGST",
              "gstratevaluationtype": "Based on Value",
              "gstrate": " 4"
            },
            {
              "gstratedutyhead": "Cess",
              "gstratevaluationtype": "\u0004 Not Applicable"
            },
            {
              "gstratedutyhead": "State Cess",
              "gstratevaluationtype": "Based on Value"
            }
          ]
        }
      ],
      "ledgerentries": [
        {
          "ledgername": "Mondal Enterprises",
          "isdeemedpositive": false,
          "ispartyledger": true,
          "amount": "1560.00",
          "billallocations": [
            {
              "name": "46",
              "billtype": "New Ref",
              "amount": "1560.00"
            }
          ]
        },
        {
          "ledgername": "CGST",
          "isdeemedpositive": true,
          "ispartyledger": false,
          "amount": "-30.00"
        },
        {
          "ledgername": "SGST",
          "isdeemedpositive": true,
          "ispartyledger": false,
          "amount": "-30.00"
        }
      ]
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
  <VOUCHER VCHTYPE="Purchase" ACTION="Create" OBJVIEW="Invoice Voucher View">
      <DATE>20250901</DATE>
      <GSTREGISTRATIONTYPE>Regular</GSTREGISTRATIONTYPE>
      <VATDEALERTYPE>Regular</VATDEALERTYPE>
      <STATENAME>Karnataka</STATENAME>
      <COUNTRYOFRESIDENCE>India</COUNTRYOFRESIDENCE>
      <PARTYGSTIN>29AAACH1004N1ZQ</PARTYGSTIN>
      <PLACEOFSUPPLY>Karnataka</PLACEOFSUPPLY>
      <VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
      <PARTYNAME>Mondal Enterprises</PARTYNAME>
      <GSTREGISTRATION TAXTYPE="GST" TAXREGISTRATION="29AAECP4424C1ZN">Karnataka Registration</GSTREGISTRATION>
      <CMPGSTIN>29AAECP4424C1ZN</CMPGSTIN>
      <PARTYLEDGERNAME>Mondal Enterprises</PARTYLEDGERNAME>
      <BASICBUYERNAME>Bhrama Enterprises</BASICBUYERNAME>
      <CMPGSTREGISTRATIONTYPE>Regular</CMPGSTREGISTRATIONTYPE>
      <PARTYMAILINGNAME>Mondal Enterprises</PARTYMAILINGNAME>
      <CONSIGNEEGSTIN>29AAECP4424C1ZN</CONSIGNEEGSTIN>
      <CONSIGNEEMAILINGNAME>Bhrama Enterprises</CONSIGNEEMAILINGNAME>
      <CONSIGNEESTATENAME>Karnataka</CONSIGNEESTATENAME>
      <CMPGSTSTATE>Karnataka</CMPGSTSTATE>
      <CONSIGNEECOUNTRYNAME>India</CONSIGNEECOUNTRYNAME>
      <BASICBASEPARTYNAME>Mondal Enterprises</BASICBASEPARTYNAME>
      <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
      <VCHENTRYMODE>Item Invoice</VCHENTRYMODE>
      <EFFECTIVEDATE>20250901</EFFECTIVEDATE>
      <ISINVOICE>Yes</ISINVOICE>
      <ALLINVENTORYENTRIES.LIST>
       <STOCKITEMNAME>Decaf Coffee</STOCKITEMNAME>
       <GSTOVRDNINELIGIBLEITC>&#4; Not Applicable</GSTOVRDNINELIGIBLEITC>
       <GSTOVRDNISREVCHARGEAPPL>&#4; Not Applicable</GSTOVRDNISREVCHARGEAPPL>
       <GSTOVRDNTAXABILITY>Taxable</GSTOVRDNTAXABILITY>
       <GSTSOURCETYPE>Stock Item</GSTSOURCETYPE>
       <GSTITEMSOURCE>Decaf Coffee</GSTITEMSOURCE>
       <HSNSOURCETYPE>Stock Item</HSNSOURCETYPE>
       <HSNITEMSOURCE>Decaf Coffee</HSNITEMSOURCE>
       <GSTOVRDNTYPEOFSUPPLY>Goods</GSTOVRDNTYPEOFSUPPLY>
       <GSTRATEINFERAPPLICABILITY>As per Masters/Company</GSTRATEINFERAPPLICABILITY>
       <GSTHSNINFERAPPLICABILITY>As per Masters/Company</GSTHSNINFERAPPLICABILITY>
       <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
       <RATE>15.00/nos</RATE>
       <AMOUNT>-1500.00</AMOUNT>
       <ACTUALQTY> 100 nos</ACTUALQTY>
       <BILLEDQTY> 100 nos</BILLEDQTY>
       <BATCHALLOCATIONS.LIST>
        <GODOWNNAME>Main Location</GODOWNNAME>
        <BATCHNAME>Primary Batch</BATCHNAME>
        <DESTINATIONGODOWNNAME>Main Location</DESTINATIONGODOWNNAME>
        <AMOUNT>-1500.00</AMOUNT>
        <ACTUALQTY> 100 nos</ACTUALQTY>
        <BILLEDQTY> 100 nos</BILLEDQTY>
       </BATCHALLOCATIONS.LIST>
       <ACCOUNTINGALLOCATIONS.LIST>
        <LEDGERNAME>GST Purchase</LEDGERNAME>
        <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
        <ISPARTYLEDGER>No</ISPARTYLEDGER>
        <AMOUNT>-1500.00</AMOUNT>
       </ACCOUNTINGALLOCATIONS.LIST>
       <RATEDETAILS.LIST>
        <GSTRATEDUTYHEAD>CGST</GSTRATEDUTYHEAD>
        <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>
        <GSTRATE> 2</GSTRATE>
       </RATEDETAILS.LIST>
       <RATEDETAILS.LIST>
        <GSTRATEDUTYHEAD>SGST/UTGST</GSTRATEDUTYHEAD>
        <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>
        <GSTRATE> 2</GSTRATE>
       </RATEDETAILS.LIST>
       <RATEDETAILS.LIST>
        <GSTRATEDUTYHEAD>IGST</GSTRATEDUTYHEAD>
        <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>
        <GSTRATE> 4</GSTRATE>
       </RATEDETAILS.LIST>
       <RATEDETAILS.LIST>
        <GSTRATEDUTYHEAD>Cess</GSTRATEDUTYHEAD>
        <GSTRATEVALUATIONTYPE>&#4; Not Applicable</GSTRATEVALUATIONTYPE>
       </RATEDETAILS.LIST>
       <RATEDETAILS.LIST>
        <GSTRATEDUTYHEAD>State Cess</GSTRATEDUTYHEAD>
        <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>
       </RATEDETAILS.LIST>
      </ALLINVENTORYENTRIES.LIST>
      <LEDGERENTRIES.LIST>
       <LEDGERNAME>Mondal Enterprises</LEDGERNAME>
       <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
       <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
       <AMOUNT>1560.00</AMOUNT>
       <BILLALLOCATIONS.LIST>
        <NAME>23</NAME>
        <BILLTYPE>New Ref</BILLTYPE>
        <AMOUNT>1560.00</AMOUNT>
       </BILLALLOCATIONS.LIST>
      </LEDGERENTRIES.LIST>
      <LEDGERENTRIES.LIST>
       <LEDGERNAME>CGST</LEDGERNAME>
       <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
       <ISPARTYLEDGER>No</ISPARTYLEDGER>
       <AMOUNT>-30.00</AMOUNT>
      </LEDGERENTRIES.LIST>
      <LEDGERENTRIES.LIST>
       <LEDGERNAME>SGST</LEDGERNAME>
       <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
       <ISPARTYLEDGER>No</ISPARTYLEDGER>
       <AMOUNT>-30.00</AMOUNT>
      </LEDGERENTRIES.LIST>
     </VOUCHER>
</TALLYMESSAGE>
</DESC>
</BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: import" \
  -H "type: data" \
  -H "id: Vouchers" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟢 Official shape: Tally's published voucher import response):

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 1,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 71,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 0,
            "vchnumber": 33
        }
    }
}
```

**Success — XML** (🔵 Observed: captured from a live TallyPrime in `docs/Tally_Vouchers_Integration_Guide.md`; `CMPINFO` truncated):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <CREATED>1</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>71</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>0</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
        <DESC>
            <CMPINFO>
                <COMPANY>0</COMPANY>
                <GROUP>0</GROUP>
                <LEDGER>95</LEDGER>
                <!-- … one count element per object type (COSTCENTRE, GODOWN, STOCKITEM, UNIT, VOUCHERTYPE, …) … -->
                <VOUCHER>39</VOUCHER>
            </CMPINFO>
        </DESC>
    </BODY>
</ENVELOPE>
```

Check `created` = 1 **and** `errors` + `exceptions` = 0. `status: "1"` only means the request was processed, not that the record was accepted. `lastvchid` is the internal id (MASTERID) of the last voucher written, and `vchnumber` is its voucher number.

#### Error Responses

**Record-level failure:** `Ledger 'Mondal Enterprises' does not exist!`. Source: 🟡 Illustrative (message pattern also reported by other Tally integrations).

Cause: A ledger (or stock item / godown) referenced by the voucher is missing, or misspelt. Create masters before vouchers.

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <LINEERROR>Ledger &apos;Mondal Enterprises&apos; does not exist!</LINEERROR>
                <CREATED>0</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>1</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
    </BODY>
</ENVELOPE>
```

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 1
        }
    }
}
```

> In JSON the failure shows up as non-zero `errors` / `exceptions` counts. Tally does not document the JSON key that carries the line-error text, so log the raw response body; this repo's parser (`parse_tally_response_metrics`) also checks `import_result.line_error`.

See also [Common errors](#110-common-error-responses) (company not loaded, unknown request, Tally not running).

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `import` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `data` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `Vouchers` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svVchImportFormat]` | `<STATICVARIABLES><SVVCHIMPORTFORMAT>` | Yes (voucher import) | String | `jsonex` | Import format of vouchers: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `tallymessage[]` | `<TALLYMESSAGE>` | Yes | Array<Object> |  | The objects to import (masters or vouchers). One request can carry many objects. |
| `tallymessage[].metadata` | `<VOUCHER …>` attributes | Yes | Object |  | Object identity block: type, name/identifiers and action. |
| `tallymessage[].metadata.type` | element name `<VOUCHER>` | Yes | String | `Voucher` | Object type: `Ledger`, `Group`, `Stock Item`, `Stock Group`, `Unit`, `Voucher`. |
| `tallymessage[].metadata.vchtype` | `VCHTYPE` attribute | Yes (vouchers) | String | `Purchase` | Voucher type name, e.g. `Payment`, `Receipt`, `Sales`, `Purchase`. |
| `tallymessage[].metadata.action` | `ACTION` attribute | Yes | String | `Create` | `Create`, `Alter`, or `Delete` (case-insensitive). |
| `tallymessage[].metadata.objview` | `OBJVIEW` attribute | Yes (vouchers) | String | `Invoice Voucher View` | `Accounting Voucher View` (ledger-only vouchers) or `Invoice Voucher View` (item invoices). |
| `tallymessage[].date` | `<VOUCHER>/DATE` | Yes | Date (YYYYMMDD) | `20250901` | Voucher date. Must fall inside the company's books period (Educational Mode: only 1st, 2nd, 31st). |
| `tallymessage[].vchstatusdate` | `<VOUCHER>/VCHSTATUSDATE` | No | Date (YYYYMMDD) | `20250901` | Voucher status date (usually = `date`). |
| `tallymessage[].gstregistrationtype` | `<VOUCHER>/GSTREGISTRATIONTYPE` | Cond. | String | `Regular` | Party GST registration type: `Regular`, `Composition`, `Consumer`, `Unregistered`, `\u0004 Unknown`. |
| `tallymessage[].vatdealertype` | `<VOUCHER>/VATDEALERTYPE` | No | String | `Regular` | Legacy VAT dealer type. |
| `tallymessage[].statename` | `<VOUCHER>/STATENAME` | Cond. | String | `Karnataka` | Party state. |
| `tallymessage[].countryofresidence` | `<VOUCHER>/COUNTRYOFRESIDENCE` | No | String | `India` | Party country. |
| `tallymessage[].partygstin` | `<VOUCHER>/PARTYGSTIN` | Cond. | String | `29AAACH1004N1ZQ` | Party GSTIN (B2B). |
| `tallymessage[].placeofsupply` | `<VOUCHER>/PLACEOFSUPPLY` | Cond. | String | `Karnataka` | GST place of supply (state). Drives CGST+SGST vs IGST. |
| `tallymessage[].vouchertypename` | `<VOUCHER>/VOUCHERTYPENAME` | Yes | String | `Purchase` | Voucher type name, e.g. `Payment`. |
| `tallymessage[].partyname` | `<VOUCHER>/PARTYNAME` | No | String | `Mondal Enterprises` | Party name printed on the voucher. |
| `tallymessage[].gstregistration` | `<VOUCHER>/GSTREGISTRATION` | Cond. | Object |  | Company GST registration used (`<GSTREGISTRATION TAXTYPE=… TAXREGISTRATION=…>name</…>` in XML). |
| `tallymessage[].gstregistration.value` | element text | Cond. | String | `Karnataka Registration` | Registration name, e.g. `Karnataka Registration`. |
| `tallymessage[].gstregistration.taxtype` | `TAXTYPE` attribute | Cond. | String | `GST` | Tax type of the registration (`GST`). |
| `tallymessage[].gstregistration.taxregistration` | `TAXREGISTRATION` attribute | Cond. | String | `29AAECP4424C1ZN` | Company GSTIN for the registration. |
| `tallymessage[].cmpgstin` | `<VOUCHER>/CMPGSTIN` | Cond. | String | `29AAECP4424C1ZN` | Company GSTIN. |
| `tallymessage[].partyledgername` | `<VOUCHER>/PARTYLEDGERNAME` | Yes | String | `Mondal Enterprises` | Primary party / account ledger of the voucher. |
| `tallymessage[].basicbuyername` | `<VOUCHER>/BASICBUYERNAME` | No | String | `Bhrama Enterprises` | Buyer name (invoice). |
| `tallymessage[].cmpgstregistrationtype` | `<VOUCHER>/CMPGSTREGISTRATIONTYPE` | Cond. | String | `Regular` | Company GST registration type. |
| `tallymessage[].partymailingname` | `<VOUCHER>/PARTYMAILINGNAME` | No | String | `Mondal Enterprises` | Party mailing name. |
| `tallymessage[].consigneegstin` | `<VOUCHER>/CONSIGNEEGSTIN` | No | String | `29AAECP4424C1ZN` | Consignee GSTIN. |
| `tallymessage[].consigneemailingname` | `<VOUCHER>/CONSIGNEEMAILINGNAME` | No | String | `Bhrama Enterprises` | Consignee name. |
| `tallymessage[].consigneestatename` | `<VOUCHER>/CONSIGNEESTATENAME` | No | String | `Karnataka` | Consignee state. |
| `tallymessage[].cmpgststate` | `<VOUCHER>/CMPGSTSTATE` | Cond. | String | `Karnataka` | Company GST state. |
| `tallymessage[].consigneecountryname` | `<VOUCHER>/CONSIGNEECOUNTRYNAME` | No | String | `India` | Consignee country. |
| `tallymessage[].basicbasepartyname` | `<VOUCHER>/BASICBASEPARTYNAME` | No | String | `Mondal Enterprises` | Base party name. |
| `tallymessage[].effectivedate` | `<VOUCHER>/EFFECTIVEDATE` | No | Date (YYYYMMDD) | `20250901` | Effective date (usually = `date`). |
| `tallymessage[].isinvoice` | `<VOUCHER>/ISINVOICE` | Cond. | Logical | `true` | `Yes` for Invoice-mode vouchers (with item lines). |
| `tallymessage[].allinventoryentries[]` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST` | Yes (item invoice) | Array<Object> |  | Item lines (`ALLINVENTORYENTRIES.LIST`). |
| `tallymessage[].allinventoryentries[].stockitemname` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/STOCKITEMNAME` | Yes | String | `Decaf Coffee` | Stock item on the line. Must already exist. |
| `tallymessage[].allinventoryentries[].gstovrdnineligibleitc` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/GSTOVRDNINELIGIBLEITC` | No | String | `\u0004 Not Applicable` | Ineligible-ITC override (purchases). |
| `tallymessage[].allinventoryentries[].gstovrdnisrevchargeappl` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/GSTOVRDNISREVCHARGEAPPL` | No | String | `\u0004 Not Applicable` | Reverse-charge override for the line. |
| `tallymessage[].allinventoryentries[].gstovrdntaxability` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/GSTOVRDNTAXABILITY` | No | String | `Taxable` | Taxability override: `Taxable`, `Exempt`, `Nil Rated`. |
| `tallymessage[].allinventoryentries[].gstsourcetype` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/GSTSOURCETYPE` | No | String | `Stock Item` | Where GST details are sourced from (`Stock Item`, `Ledger`, ...). |
| `tallymessage[].allinventoryentries[].gstitemsource` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/GSTITEMSOURCE` | No | String | `Decaf Coffee` | Source object name for GST details. |
| `tallymessage[].allinventoryentries[].hsnsourcetype` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/HSNSOURCETYPE` | No | String | `Stock Item` | Where HSN is sourced from. |
| `tallymessage[].allinventoryentries[].hsnitemsource` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/HSNITEMSOURCE` | No | String | `Decaf Coffee` | Source object name for HSN. |
| `tallymessage[].allinventoryentries[].gstovrdntypeofsupply` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/GSTOVRDNTYPEOFSUPPLY` | No | String | `Goods` | `Goods` or `Services`. |
| `tallymessage[].allinventoryentries[].gstrateinferapplicability` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/GSTRATEINFERAPPLICABILITY` | No | String | `As per Masters/Company` | Rate inference: `As per Masters/Company`, `Specify Details Here`, ... |
| `tallymessage[].allinventoryentries[].gsthsninferapplicability` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/GSTHSNINFERAPPLICABILITY` | No | String | `As per Masters/Company` | HSN inference mode. |
| `tallymessage[].allinventoryentries[].isdeemedpositive` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/ISDEEMEDPOSITIVE` | Yes | Logical | `true` | `Yes`/`true` = Debit, `No`/`false` = Credit. |
| `tallymessage[].allinventoryentries[].rate` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/RATE` | Yes | Rate | `15.00/nos` | Rate with unit, e.g. `75.00/nos`. |
| `tallymessage[].allinventoryentries[].amount` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/AMOUNT` | Yes | Amount | `-1500.00` | Line amount. Sign convention: Debit lines negative, Credit lines positive; all lines must net to zero. |
| `tallymessage[].allinventoryentries[].actualqty` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/ACTUALQTY` | Yes | Quantity | `100 nos` | Actual quantity with unit, e.g. `20 nos`. |
| `tallymessage[].allinventoryentries[].billedqty` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/BILLEDQTY` | Yes | Quantity | `100 nos` | Billed quantity with unit. |
| `tallymessage[].allinventoryentries[].batchallocations[]` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/BATCHALLOCATIONS.LIST` | Yes (items) | Array<Object> |  | Godown/batch split of the item line (`BATCHALLOCATIONS.LIST`). |
| `tallymessage[].allinventoryentries[].batchallocations[].godownname` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/BATCHALLOCATIONS.LIST/GODOWNNAME` | Yes | String | `Main Location` | Godown (location). Default company godown is `Main Location`. |
| `tallymessage[].allinventoryentries[].batchallocations[].batchname` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/BATCHALLOCATIONS.LIST/BATCHNAME` | Cond. | String | `Primary Batch` | Batch name (`Primary Batch` when batches are not tracked). |
| `tallymessage[].allinventoryentries[].batchallocations[].amount` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/BATCHALLOCATIONS.LIST/AMOUNT` | Yes | Amount | `-1500.00` | Line amount. Sign convention: Debit lines negative, Credit lines positive; all lines must net to zero. |
| `tallymessage[].allinventoryentries[].batchallocations[].actualqty` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/BATCHALLOCATIONS.LIST/ACTUALQTY` | Yes | Quantity | `100 nos` | Actual quantity with unit, e.g. `20 nos`. |
| `tallymessage[].allinventoryentries[].batchallocations[].billedqty` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/BATCHALLOCATIONS.LIST/BILLEDQTY` | Yes | Quantity | `100 nos` | Billed quantity with unit. |
| `tallymessage[].allinventoryentries[].accountingallocations[]` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/ACCOUNTINGALLOCATIONS.LIST` | Yes (items) | Array<Object> |  | Sales/Purchase ledger the item amount posts to (`ACCOUNTINGALLOCATIONS.LIST`). |
| `tallymessage[].allinventoryentries[].accountingallocations[].ledgername` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/ACCOUNTINGALLOCATIONS.LIST/LEDGERNAME` | Yes | String | `GST Purchase` | Ledger affected by the line. Must already exist. |
| `tallymessage[].allinventoryentries[].accountingallocations[].isdeemedpositive` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/ACCOUNTINGALLOCATIONS.LIST/ISDEEMEDPOSITIVE` | Yes | Logical | `true` | `Yes`/`true` = Debit, `No`/`false` = Credit. |
| `tallymessage[].allinventoryentries[].accountingallocations[].ispartyledger` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/ACCOUNTINGALLOCATIONS.LIST/ISPARTYLEDGER` | Yes | Logical | `false` | `Yes` for the party/cash/bank line of the voucher. |
| `tallymessage[].allinventoryentries[].accountingallocations[].amount` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/ACCOUNTINGALLOCATIONS.LIST/AMOUNT` | Yes | Amount | `-1500.00` | Line amount. Sign convention: Debit lines negative, Credit lines positive; all lines must net to zero. |
| `tallymessage[].allinventoryentries[].ratedetails[]` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/RATEDETAILS.LIST` | No | Array<Object> |  | Per-duty-head GST rates on the line (`RATEDETAILS.LIST`). |
| `tallymessage[].allinventoryentries[].ratedetails[].gstratedutyhead` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/RATEDETAILS.LIST/GSTRATEDUTYHEAD` | Yes | String | `CGST` | `CGST`, `SGST/UTGST`, `IGST`, `Cess`, `State Cess`. |
| `tallymessage[].allinventoryentries[].ratedetails[].gstratevaluationtype` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/RATEDETAILS.LIST/GSTRATEVALUATIONTYPE` | Yes | String | `Based on Value` | `Based on Value`, `Based on Quantity`, `\u0004 Not Applicable`. |
| `tallymessage[].allinventoryentries[].ratedetails[].gstrate` | `<VOUCHER>/ALLINVENTORYENTRIES.LIST/RATEDETAILS.LIST/GSTRATE` | Cond. | Number | `2` | Rate percentage. |
| `tallymessage[].ledgerentries[]` | `<VOUCHER>/LEDGERENTRIES.LIST` | Yes (invoice view) | Array<Object> |  | Ledger lines (party, taxes) of an Invoice-view voucher (`LEDGERENTRIES.LIST`). |
| `tallymessage[].ledgerentries[].ledgername` | `<VOUCHER>/LEDGERENTRIES.LIST/LEDGERNAME` | Yes | String | `Mondal Enterprises` | Ledger affected by the line. Must already exist. |
| `tallymessage[].ledgerentries[].isdeemedpositive` | `<VOUCHER>/LEDGERENTRIES.LIST/ISDEEMEDPOSITIVE` | Yes | Logical | `false` | `Yes`/`true` = Debit, `No`/`false` = Credit. |
| `tallymessage[].ledgerentries[].ispartyledger` | `<VOUCHER>/LEDGERENTRIES.LIST/ISPARTYLEDGER` | Yes | Logical | `true` | `Yes` for the party/cash/bank line of the voucher. |
| `tallymessage[].ledgerentries[].amount` | `<VOUCHER>/LEDGERENTRIES.LIST/AMOUNT` | Yes | Amount | `1560.00` | Line amount. Sign convention: Debit lines negative, Credit lines positive; all lines must net to zero. |
| `tallymessage[].ledgerentries[].billallocations[]` | `<VOUCHER>/LEDGERENTRIES.LIST/BILLALLOCATIONS.LIST` | Cond. | Array<Object> |  | Bill-wise allocation for bill-wise-enabled party ledgers (`BILLALLOCATIONS.LIST`). |
| `tallymessage[].ledgerentries[].billallocations[].name` | `<VOUCHER>/LEDGERENTRIES.LIST/BILLALLOCATIONS.LIST/NAME` | Yes | String | `46` | Bill reference number (e.g. invoice no.). |
| `tallymessage[].ledgerentries[].billallocations[].billtype` | `<VOUCHER>/LEDGERENTRIES.LIST/BILLALLOCATIONS.LIST/BILLTYPE` | Yes | String | `New Ref` | `New Ref`, `Agst Ref`, `Advance`, or `On Account`. |
| `tallymessage[].ledgerentries[].billallocations[].amount` | `<VOUCHER>/LEDGERENTRIES.LIST/BILLALLOCATIONS.LIST/AMOUNT` | Yes | Amount | `1560.00` | Line amount. Sign convention: Debit lines negative, Credit lines positive; all lines must net to zero. |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Create a purchase Voucher with same ledgers but on date ‘1st August 2025” with quantity 200 nos, at rate 15/nos, amount 3000, with bill number ‘Bill28PurGST1’ . Recalculate the GST ledger values for the same GST rates. | Change the value of Date tag, and all the quantity and amount tags. Recalculate GST | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/purchase/create-gst/json/TaskCreateGSTPurJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/purchase/create-gst/xml/TaskCreateGSTPurXML.txt) |

### 4.4.3 Alter a Purchase

> Explorer id: `purchase-alter` · Kind: **import** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#purchase-alter)

#### Description

Each TallyPrime voucher has unique system-generated identifiers. To modify a voucher, ensure the ‘guid’, ‘vchkey’, and ‘remoteid’ match the existing voucher’s values, which can be obtained by exporting it in XML/JSON format from TallyPrime. In the sample request, provide the right values for these tags and attributes to experience the alteration of voucher.

**Integration use:** Amend a purchase bill in place.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svVchImportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `import` | Yes |
| `type` | `data` | Yes |
| `id` | `Vouchers` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svVchImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Voucher",
        "vchtype": "Purchase",
        "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000075",
        "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:000000f8",
        "action": "Alter",
        "objview": "Invoice Voucher View"
      },
      "date": "20250802",
      "effectivedate": "20250802",
      "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000075"
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
<VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000079" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:000000f8" VCHTYPE="Purchase" ACTION="Alter" OBJVIEW="Invoice Voucher View">
  <DATE>20250802</DATE>
  <EFFECTIVEDATE>20250802</EFFECTIVEDATE>
  <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000079</GUID>
 </VOUCHER>
</TALLYMESSAGE>
</DESC>
</BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: import" \
  -H "type: data" \
  -H "id: Vouchers" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟢 Official shape: Tally's published voucher import response):

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 1,
            "deleted": 0,
            "lastvchid": 71,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 0,
            "vchnumber": 32
        }
    }
}
```

**Success — XML** (🔵 Observed: captured from a live TallyPrime in `docs/Tally_Vouchers_Integration_Guide.md`; `CMPINFO` truncated):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <CREATED>0</CREATED>
                <ALTERED>1</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>71</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>0</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
        <DESC>
            <CMPINFO>
                <COMPANY>0</COMPANY>
                <GROUP>0</GROUP>
                <LEDGER>95</LEDGER>
                <!-- … one count element per object type (COSTCENTRE, GODOWN, STOCKITEM, UNIT, VOUCHERTYPE, …) … -->
                <VOUCHER>39</VOUCHER>
            </CMPINFO>
        </DESC>
    </BODY>
</ENVELOPE>
```

Check `altered` = 1 **and** `errors` + `exceptions` = 0. `status: "1"` only means the request was processed, not that the record was accepted. `lastvchid` is the internal id (MASTERID) of the last voucher written, and `vchnumber` is its voucher number.

#### Error Responses

**Record-level failure:** `Voucher does not exist!`. Source: 🔵 Observed.

Cause: `remoteid` / `vchkey` / `guid` do not match any voucher in the company (e.g. ids copied from another company or the voucher was deleted).

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <LINEERROR>Voucher does not exist!</LINEERROR>
                <CREATED>0</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>1</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
    </BODY>
</ENVELOPE>
```

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 1
        }
    }
}
```

> In JSON the failure shows up as non-zero `errors` / `exceptions` counts. Tally does not document the JSON key that carries the line-error text, so log the raw response body; this repo's parser (`parse_tally_response_metrics`) also checks `import_result.line_error`.

See also [Common errors](#110-common-error-responses) (company not loaded, unknown request, Tally not running).

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `import` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `data` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `Vouchers` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svVchImportFormat]` | `<STATICVARIABLES><SVVCHIMPORTFORMAT>` | Yes (voucher import) | String | `jsonex` | Import format of vouchers: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `tallymessage[]` | `<TALLYMESSAGE>` | Yes | Array<Object> |  | The objects to import (masters or vouchers). One request can carry many objects. |
| `tallymessage[].metadata` | `<VOUCHER …>` attributes | Yes | Object |  | Object identity block: type, name/identifiers and action. |
| `tallymessage[].metadata.type` | element name `<VOUCHER>` | Yes | String | `Voucher` | Object type: `Ledger`, `Group`, `Stock Item`, `Stock Group`, `Unit`, `Voucher`. |
| `tallymessage[].metadata.vchtype` | `VCHTYPE` attribute | Yes (vouchers) | String | `Purchase` | Voucher type name, e.g. `Payment`, `Receipt`, `Sales`, `Purchase`. |
| `tallymessage[].metadata.remoteid` | `REMOTEID` attribute | Yes (alter/delete vch) | String (GUID) | `f0347998-2c19-4a5e-a4ed-01f589cb92a5-000…` | Voucher's REMOTEID as exported from Tally. Identifies the voucher to alter/delete. |
| `tallymessage[].metadata.vchkey` | `VCHKEY` attribute | Yes (alter/delete vch) | String | `f0347998-2c19-4a5e-a4ed-01f589cb92a5-000…` | Voucher's VCHKEY as exported from Tally. |
| `tallymessage[].metadata.action` | `ACTION` attribute | Yes | String | `Alter` | `Create`, `Alter`, or `Delete` (case-insensitive). |
| `tallymessage[].metadata.objview` | `OBJVIEW` attribute | Yes (vouchers) | String | `Invoice Voucher View` | `Accounting Voucher View` (ledger-only vouchers) or `Invoice Voucher View` (item invoices). |
| `tallymessage[].date` | `<VOUCHER>/DATE` | Yes | Date (YYYYMMDD) | `20250802` | Voucher date. Must fall inside the company's books period (Educational Mode: only 1st, 2nd, 31st). |
| `tallymessage[].effectivedate` | `<VOUCHER>/EFFECTIVEDATE` | No | Date (YYYYMMDD) | `20250802` | Effective date (usually = `date`). |
| `tallymessage[].guid` | `<VOUCHER>/GUID` | Yes (alter/delete) | String (GUID) | `f0347998-2c19-4a5e-a4ed-01f589cb92a5-000…` | Tally GUID of the voucher; must match the existing voucher. |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Alter any Purchase Voucher in the company and change the date to ‘1st March 2026’ | Change the value of Date tag, and set correct values for ‘guid’, ‘vchkey’, and ‘remoteid’ | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/purchase/alter/json/TaskAlterPurJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/purchase/alter/xml/TaskAlterPurXML.txt) |
| Alter any Purchase Voucher in the company and change the quantity to 15 nos, at the same rate. | Change the value for all the quantity & amount tags, and set correct values for ‘guid’, ‘vchkey’, and ‘remoteid’ | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/purchase/alter/json/TaskAlterPur15nosJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/purchase/alter/xml/TaskAlterPur15nosXML.txt) |

### 4.4.4 Delete a Purchase

> Explorer id: `purchase-delete` · Kind: **import** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#purchase-delete)

#### Description

Each TallyPrime voucher has unique system-generated identifiers. To delete a voucher, ensure the ‘guid’, ‘vchkey’, and ‘remoteid’ match the existing voucher’s values, which can be obtained by exporting it in XML/JSON format from TallyPrime. In the sample request, provide the right values for these tags and attributes to experience the deletion of voucher.

**Integration use:** Reverse a purchase bill voided upstream.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svVchImportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `import` | Yes |
| `type` | `data` | Yes |
| `id` | `Vouchers` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svVchImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Voucher",
        "vchtype": "Purchase",
        "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000083",
        "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b400:00000010",
        "action": "Delete",
        "objview": "Invoice Voucher View"
      },
      "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000083"
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
 <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000083" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b400:00000010" VCHTYPE="Purchase" ACTION="Delete" OBJVIEW="Invoice Voucher View">
<GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000083</GUID>
 </VOUCHER>
</TALLYMESSAGE>
</DESC>
</BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: import" \
  -H "type: data" \
  -H "id: Vouchers" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟢 Official shape: Tally's published voucher import response):

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 0,
            "deleted": 1,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 0,
            "vchnumber": 32
        }
    }
}
```

**Success — XML** (🔵 Observed: captured from a live TallyPrime in `docs/Tally_Vouchers_Integration_Guide.md`; `CMPINFO` truncated):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <CREATED>0</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>1</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>0</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
        <DESC>
            <CMPINFO>
                <COMPANY>0</COMPANY>
                <GROUP>0</GROUP>
                <LEDGER>95</LEDGER>
                <!-- … one count element per object type (COSTCENTRE, GODOWN, STOCKITEM, UNIT, VOUCHERTYPE, …) … -->
                <VOUCHER>39</VOUCHER>
            </CMPINFO>
        </DESC>
    </BODY>
</ENVELOPE>
```

Check `deleted` = 1 **and** `errors` + `exceptions` = 0. `status: "1"` only means the request was processed, not that the record was accepted. `lastvchid` is the internal id (MASTERID) of the last voucher written, and `vchnumber` is its voucher number.

#### Error Responses

**Record-level failure:** `Cannot delete unnamed object: VOUCHER!`. Source: 🔵 Observed.

Cause: The voucher identifiers were not sent on the object itself (`REMOTEID`/`VCHKEY` attributes in XML, `metadata.remoteid`/`metadata.vchkey` in JSON).

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DATA>
            <IMPORTRESULT>
                <LINEERROR>Cannot delete unnamed object: VOUCHER!</LINEERROR>
                <CREATED>0</CREATED>
                <ALTERED>0</ALTERED>
                <DELETED>0</DELETED>
                <LASTVCHID>0</LASTVCHID>
                <LASTMID>0</LASTMID>
                <COMBINED>0</COMBINED>
                <IGNORED>0</IGNORED>
                <ERRORS>0</ERRORS>
                <CANCELLED>0</CANCELLED>
                <EXCEPTIONS>1</EXCEPTIONS>
            </IMPORTRESULT>
        </DATA>
    </BODY>
</ENVELOPE>
```

```json
{
    "status": "1",
    "data": {
        "import_result": {
            "created": 0,
            "altered": 0,
            "deleted": 0,
            "lastvchid": 0,
            "lastmid": 0,
            "combined": 0,
            "ignored": 0,
            "errors": 0,
            "cancelled": 0,
            "exceptions": 1
        }
    }
}
```

> In JSON the failure shows up as non-zero `errors` / `exceptions` counts. Tally does not document the JSON key that carries the line-error text, so log the raw response body; this repo's parser (`parse_tally_response_metrics`) also checks `import_result.line_error`.

See also [Common errors](#110-common-error-responses) (company not loaded, unknown request, Tally not running).

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `import` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `data` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `Vouchers` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svVchImportFormat]` | `<STATICVARIABLES><SVVCHIMPORTFORMAT>` | Yes (voucher import) | String | `jsonex` | Import format of vouchers: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `tallymessage[]` | `<TALLYMESSAGE>` | Yes | Array<Object> |  | The objects to import (masters or vouchers). One request can carry many objects. |
| `tallymessage[].metadata` | `<VOUCHER …>` attributes | Yes | Object |  | Object identity block: type, name/identifiers and action. |
| `tallymessage[].metadata.type` | element name `<VOUCHER>` | Yes | String | `Voucher` | Object type: `Ledger`, `Group`, `Stock Item`, `Stock Group`, `Unit`, `Voucher`. |
| `tallymessage[].metadata.vchtype` | `VCHTYPE` attribute | Yes (vouchers) | String | `Purchase` | Voucher type name, e.g. `Payment`, `Receipt`, `Sales`, `Purchase`. |
| `tallymessage[].metadata.remoteid` | `REMOTEID` attribute | Yes (alter/delete vch) | String (GUID) | `f0347998-2c19-4a5e-a4ed-01f589cb92a5-000…` | Voucher's REMOTEID as exported from Tally. Identifies the voucher to alter/delete. |
| `tallymessage[].metadata.vchkey` | `VCHKEY` attribute | Yes (alter/delete vch) | String | `f0347998-2c19-4a5e-a4ed-01f589cb92a5-000…` | Voucher's VCHKEY as exported from Tally. |
| `tallymessage[].metadata.action` | `ACTION` attribute | Yes | String | `Delete` | `Create`, `Alter`, or `Delete` (case-insensitive). |
| `tallymessage[].metadata.objview` | `OBJVIEW` attribute | Yes (vouchers) | String | `Invoice Voucher View` | `Accounting Voucher View` (ledger-only vouchers) or `Invoice Voucher View` (item invoices). |
| `tallymessage[].guid` | `<VOUCHER>/GUID` | Yes (alter/delete) | String (GUID) | `f0347998-2c19-4a5e-a4ed-01f589cb92a5-000…` | Tally GUID of the voucher; must match the existing voucher. |

### 4.4.5 Pull all Purchase vouchers

> Explorer id: `purchase-pull-all` · Kind: **collection** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#purchase-pull-all)

#### Description

TDetails about multiple vouchers can be pulled using a TDL collection definition, which can already exist in the default source code or sent via the payload. TDL collection definition has type attribute that specifies the type of object that is grouped and fetch attribute that fetches the required methods.

**Integration use:** Pull all purchase vouchers for payables reconciliation.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svExportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVEXPORTFORMAT>XML</SVEXPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `export` | Yes |
| `type` | `collection` | Yes |
| `id` | `TSPL All Purchase Vouchers` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tdlmessage": [
    {
      "definitions": [
        {
          "metadata": {
            "name": "TSPL All Purchase Vouchers",
            "type": "Collection"
          },
          "attributes": [
            {
              "Type": "Vouchers:VoucherType"
            },
            {
              "Child Of": "$$VchTypePurchase"
            },
            {
              "Native Method": "Date, VoucherTypeName, VoucherNumber, Partyledgername"
            }
          ]
        }
      ]
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Collection</TYPE>
        <ID>TSPL All Purchase Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
<TDL>
<TDLMESSAGE>
  <COLLECTION NAME="TSPL All Purchase Vouchers" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
   <TYPE>Vouchers:VoucherType</TYPE>
   <CHILDOF>$$VchTypePurchase</CHILDOF>
   <NATIVEMETHOD>Date, VoucherTypeName, VoucherNumber, Partyledgername</NATIVEMETHOD>
  </COLLECTION>
</TDLMESSAGE>
</TDL>
        </DESC>
    </BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: export" \
  -H "type: collection" \
  -H "id: TSPL All Purchase Vouchers" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟡 Illustrative (structure follows Tally's published voucher-collection sample: `metadata.remoteid/vchkey`, typed fields, `cmp_dep_type`; values invented)):

```json
{
    "status": "1",
    "data": {
        "metadata": {
            "is_cmp_dep_type": true,
            "cmp_locus": 4,
            "cmp_dep_type": 64
        },
        "collection": [
            {
                "metadata": {
                    "type": "Voucher",
                    "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000091",
                    "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2b3:00000008",
                    "vchtype": "Purchase",
                    "objview": "Invoice Voucher View"
                },
                "date": {
                    "type": "Date",
                    "value": "20250401"
                },
                "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000091",
                "vouchertypename": "Purchase",
                "vouchernumber": "1",
                "partyledgername": {
                    "type": "String",
                    "value": "International Party"
                },
                "masterid": {
                    "type": "Number",
                    "value": " 145"
                }
            },
            {
                "metadata": {
                    "type": "Voucher",
                    "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000092",
                    "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2b4:00000009",
                    "vchtype": "Purchase",
                    "objview": "Invoice Voucher View"
                },
                "date": {
                    "type": "Date",
                    "value": "20250831"
                },
                "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000092",
                "vouchertypename": "Purchase",
                "vouchernumber": "2",
                "partyledgername": {
                    "type": "String",
                    "value": "International Party"
                },
                "masterid": {
                    "type": "Number",
                    "value": " 146"
                }
            }
        ]
    }
}
```

**Success — XML** (🟡 Illustrative):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DESC>
        </DESC>
        <DATA>
            <COLLECTION>
                <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000091" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2b3:00000008" VCHTYPE="Purchase" OBJVIEW="Invoice Voucher View">
                    <DATE TYPE="Date">20250401</DATE>
                    <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000091</GUID>
                    <VOUCHERTYPENAME TYPE="String">Purchase</VOUCHERTYPENAME>
                    <VOUCHERNUMBER TYPE="String">1</VOUCHERNUMBER>
                    <PARTYLEDGERNAME TYPE="String">International Party</PARTYLEDGERNAME>
                    <MASTERID TYPE="Number"> 145</MASTERID>
                </VOUCHER>
                <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000092" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2b4:00000009" VCHTYPE="Purchase" OBJVIEW="Invoice Voucher View">
                    <DATE TYPE="Date">20250831</DATE>
                    <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000092</GUID>
                    <VOUCHERTYPENAME TYPE="String">Purchase</VOUCHERTYPENAME>
                    <VOUCHERNUMBER TYPE="String">2</VOUCHERNUMBER>
                    <PARTYLEDGERNAME TYPE="String">International Party</PARTYLEDGERNAME>
                    <MASTERID TYPE="Number"> 146</MASTERID>
                </VOUCHER>
            </COLLECTION>
        </DATA>
    </BODY>
</ENVELOPE>
```

#### Error Responses

- **Collection name mismatch** (🟡 Illustrative): if the `id` header / `<ID>` does not match a default collection or a definition in `tdlmessage`, Tally returns an error instead of data. TDL names ignore case and spaces (`TSPL All Payment Vouchers` = `TSPLAllPaymentVouchers`), but any other spelling difference breaks the match.
- **Invalid TDL** (bad attribute or formula): Tally may show an error dialog on the Tally screen and return nothing useful. Validate TDL in the Explorer before shipping it.
- **Empty result:** a valid request that matches nothing returns `status: "1"` with an empty `collection` (`<COLLECTION/>`).
- [Common errors](#110-common-error-responses) apply.

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `export` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `collection` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `TSPL All Purchase Vouchers` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svExportFormat]` | `<STATICVARIABLES><SVEXPORTFORMAT>` | Yes (export) | String | `jsonex` | Response format: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `tdlmessage[]` | `<TDL><TDLMESSAGE>` | Cond. | Array<Object> |  | Inline TDL definitions (Collection / Report modification / System Formulae) that Tally loads before executing the request. |
| `tdlmessage[].definitions[]` | `<COLLECTION …>` | Cond. | Array<Object> |  | List of TDL definitions inside `tdlmessage`. |
| `tdlmessage[].definitions[].metadata.name` | `NAME` attribute | Yes | String | `TSPL All Purchase Vouchers` | Definition name. For a Collection it must match the `id` header / `<ID>`. TDL names are case- and space-insensitive. |
| `tdlmessage[].definitions[].metadata.type` | element name | Yes | String | `Collection` | Definition kind: `Collection`, `Report`, or `System`. |
| `tdlmessage[].definitions[].attributes[].Type` | `<TYPE>` | Yes | String | `Vouchers:VoucherType` | Object type the collection gathers: `Ledger`, `Group`, `StockItem`, `StockGroup`, `Unit`, or `Vouchers:VoucherType` (vouchers of a voucher type). |
| `tdlmessage[].definitions[].attributes[].Child Of` | `<CHILDOF>` | No | String (TDL expr) | `$$VchTypePurchase` | Restricts the collection to children of a parent. Accepts a literal (`"Gadgets"`) or a system-name function such as `$$GroupBank`, `$$GroupCurrentAssets`, `$$VchTypePayment`. |
| `tdlmessage[].definitions[].attributes[].Native Method` | `<NATIVEMETHOD>` | Yes | String (CSV) | `Date, VoucherTypeName, VoucherNumber, Pa…` | Comma-separated methods to fetch for every object in the collection. |

### 4.4.6 Pull all Purchase vouchers for a period

> Explorer id: `purchase-pull-period` · Kind: **collection** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#purchase-pull-period)

#### Description

Details about multiple vouchers of a vouchertype, with any filter, can be pulled using a TDL collection definition, which can already exist in the default source code or sent via the payload. TDL collection definition has type attribute that specifies the type of object that is grouped, and fetch attribute that fetches the required methods, Filter attribute that specifies any condition based on which the objects should be gathered.

**Integration use:** Incremental, date-bounded purchase sync.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svExportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVEXPORTFORMAT>XML</SVEXPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `export` | Yes |
| `type` | `collection` | Yes |
| `id` | `TSPL Purchase Vouchers` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tdlmessage": [
    {
      "definitions": [
        {
          "metadata": {
            "name": "TSPL Purchase Vouchers",
            "type": "Collection"
          },
          "attributes": [
            {
              "Type": "Vouchers:VoucherType"
            },
            {
              "Child Of": "$$VchTypePurchase"
            },
            {
              "Native Method": "Date, VoucherTypeName, VoucherNumber, Partyledgername"
            },
            {
              "Filters": "Period Filter"
            }
          ]
        },
        {
          "metadata": {
            "name": "PeriodFilter",
            "type": "System",
            "sys_type": "Formulae",
            "ismodify": true
          },
          "value": "$Date >= ($$Date:\"01-07-2025\") AND $Date <= ($$Date:\"10-07-2025\")"
        }
      ]
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Collection</TYPE>
        <ID>TSPL Purchase Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
<TDL>
<TDLMESSAGE>
  <COLLECTION NAME="TSPL Purchase Vouchers" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
   <TYPE>Vouchers:VoucherType</TYPE>
   <CHILDOF>$$VchTypePurchase</CHILDOF>
   <NATIVEMETHOD>Date, VoucherTypeName, VoucherNumber, Partyledgername</NATIVEMETHOD>
   <FILTERS>Period Filter</FILTERS>
  </COLLECTION>
  <SYSTEM TYPE="Formulae" NAME="PeriodFilter" ISMODIFY="Yes" ISFIXED="No" ISINTERNAL="No">$Date &gt;= ($$Date:"01-07-2025") AND $Date &lt;= ($$Date:"10-07-2025")  </SYSTEM>
</TDLMESSAGE>
</TDL>
        </DESC>
    </BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: export" \
  -H "type: collection" \
  -H "id: TSPL Purchase Vouchers" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟡 Illustrative (structure follows Tally's published voucher-collection sample: `metadata.remoteid/vchkey`, typed fields, `cmp_dep_type`; values invented)):

```json
{
    "status": "1",
    "data": {
        "metadata": {
            "is_cmp_dep_type": true,
            "cmp_locus": 4,
            "cmp_dep_type": 64
        },
        "collection": [
            {
                "metadata": {
                    "type": "Voucher",
                    "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000091",
                    "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2b3:00000008",
                    "vchtype": "Purchase",
                    "objview": "Invoice Voucher View"
                },
                "date": {
                    "type": "Date",
                    "value": "20250402"
                },
                "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000091",
                "vouchertypename": "Purchase",
                "vouchernumber": "1",
                "partyledgername": {
                    "type": "String",
                    "value": "International Party"
                },
                "masterid": {
                    "type": "Number",
                    "value": " 145"
                }
            },
            {
                "metadata": {
                    "type": "Voucher",
                    "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000092",
                    "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2b4:00000009",
                    "vchtype": "Purchase",
                    "objview": "Invoice Voucher View"
                },
                "date": {
                    "type": "Date",
                    "value": "20250402"
                },
                "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000092",
                "vouchertypename": "Purchase",
                "vouchernumber": "2",
                "partyledgername": {
                    "type": "String",
                    "value": "International Party"
                },
                "masterid": {
                    "type": "Number",
                    "value": " 146"
                }
            }
        ]
    }
}
```

**Success — XML** (🟡 Illustrative):

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <STATUS>1</STATUS>
    </HEADER>
    <BODY>
        <DESC>
        </DESC>
        <DATA>
            <COLLECTION>
                <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000091" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2b3:00000008" VCHTYPE="Purchase" OBJVIEW="Invoice Voucher View">
                    <DATE TYPE="Date">20250402</DATE>
                    <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000091</GUID>
                    <VOUCHERTYPENAME TYPE="String">Purchase</VOUCHERTYPENAME>
                    <VOUCHERNUMBER TYPE="String">1</VOUCHERNUMBER>
                    <PARTYLEDGERNAME TYPE="String">International Party</PARTYLEDGERNAME>
                    <MASTERID TYPE="Number"> 145</MASTERID>
                </VOUCHER>
                <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000092" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2b4:00000009" VCHTYPE="Purchase" OBJVIEW="Invoice Voucher View">
                    <DATE TYPE="Date">20250402</DATE>
                    <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000092</GUID>
                    <VOUCHERTYPENAME TYPE="String">Purchase</VOUCHERTYPENAME>
                    <VOUCHERNUMBER TYPE="String">2</VOUCHERNUMBER>
                    <PARTYLEDGERNAME TYPE="String">International Party</PARTYLEDGERNAME>
                    <MASTERID TYPE="Number"> 146</MASTERID>
                </VOUCHER>
            </COLLECTION>
        </DATA>
    </BODY>
</ENVELOPE>
```

#### Error Responses

- **Collection name mismatch** (🟡 Illustrative): if the `id` header / `<ID>` does not match a default collection or a definition in `tdlmessage`, Tally returns an error instead of data. TDL names ignore case and spaces (`TSPL All Payment Vouchers` = `TSPLAllPaymentVouchers`), but any other spelling difference breaks the match.
- **Invalid TDL** (bad attribute or formula): Tally may show an error dialog on the Tally screen and return nothing useful. Validate TDL in the Explorer before shipping it.
- **Empty result:** a valid request that matches nothing returns `status: "1"` with an empty `collection` (`<COLLECTION/>`).
- [Common errors](#110-common-error-responses) apply.

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `export` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `collection` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `TSPL Purchase Vouchers` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svExportFormat]` | `<STATICVARIABLES><SVEXPORTFORMAT>` | Yes (export) | String | `jsonex` | Response format: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `tdlmessage[]` | `<TDL><TDLMESSAGE>` | Cond. | Array<Object> |  | Inline TDL definitions (Collection / Report modification / System Formulae) that Tally loads before executing the request. |
| `tdlmessage[].definitions[]` | `<COLLECTION …>` | Cond. | Array<Object> |  | List of TDL definitions inside `tdlmessage`. |
| `tdlmessage[].definitions[].metadata.name` | `NAME` attribute | Yes | String | `TSPL Purchase Vouchers` | Definition name. For a Collection it must match the `id` header / `<ID>`. TDL names are case- and space-insensitive. |
| `tdlmessage[].definitions[].metadata.type` | element name | Yes | String | `Collection` | Definition kind: `Collection`, `Report`, or `System`. |
| `tdlmessage[].definitions[].attributes[].Type` | `<TYPE>` | Yes | String | `Vouchers:VoucherType` | Object type the collection gathers: `Ledger`, `Group`, `StockItem`, `StockGroup`, `Unit`, or `Vouchers:VoucherType` (vouchers of a voucher type). |
| `tdlmessage[].definitions[].attributes[].Child Of` | `<CHILDOF>` | No | String (TDL expr) | `$$VchTypePurchase` | Restricts the collection to children of a parent. Accepts a literal (`"Gadgets"`) or a system-name function such as `$$GroupBank`, `$$GroupCurrentAssets`, `$$VchTypePayment`. |
| `tdlmessage[].definitions[].attributes[].Native Method` | `<NATIVEMETHOD>` | Yes | String (CSV) | `Date, VoucherTypeName, VoucherNumber, Pa…` | Comma-separated methods to fetch for every object in the collection. |
| `tdlmessage[].definitions[].attributes[].Filters` | `<FILTERS>` | No | String | `Period Filter` | Name of a System Formula used to filter the collection server-side. |
| `tdlmessage[].definitions[].metadata.sys_type` | `TYPE` attribute | Cond. | String | `Formulae` | For `type: System` only. `Formulae` declares named formulae used by `Filters`. |
| `tdlmessage[].definitions[].metadata.ismodify` | `ISMODIFY` attribute | No | Boolean | `true` | `true` modifies an existing (default) definition instead of declaring a new one (`#` / `ISMODIFY="Yes"` in XML). |
| `tdlmessage[].definitions[].value` | element text | Cond. | String (TDL expr) | `$Date >= ($$Date:"01-07-2025") AND $Date…` | Body of a System Formula, e.g. `$ClosingBalance = 0`. |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Fetch the Purchase vouchers for a single date “2nd April 2025” | Change the value of the Filter Formula | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/purchase/pull-period/json/TaskPullPur2AprilJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/purchase/pull-period/xml/TaskPullPur2AprilXML.txt) |

# 5. Reports

Reports provide a structured view of business data captured in TallyPrime; helping you analyse balances, track performance, and derive insights.

In the API Explorer, Reports allow you to understand how summarized and computed data can be accessed, beyond just raw transactions and masters. This includes key business views like stock summaries, outstanding receivables, and financial statements that are essential for decision-making.

Use this section to explore how TallyPrime organizes report data and how you can retrieve meaningful insights programmatically for your applications.

Any report in TallyPrime can be fetched using its TDL Report Name a.k.a. Report ID as a unique identifier specified in the <ID> tag (XML) or id HTTP header (JSON) of the request.

Let's understand few commonly used reports in TallyPrime and the IDs.

**Common Report IDs in TallyPrime**

Use the following Report IDs to access standard business reports, along with a quick understanding of what each report provides:

| Report Name | Report ID (TallyPrime) | Description |
|---|---|---|
| Trial Balance | Trial Balance | Shows closing balances of all ledgers and groups, helping verify accounting accuracy. |
| Balance Sheet | Balance Sheet | Displays financial position of the business—assets, liabilities, and capital. |
| Profit & Loss A/c | Profit and Loss | Summarizes income and expenses to determine net profit or loss. |
| Stock Summary | Stock Summary | Provides item-wise stock position, including quantities and values. |
| Day Book | Day Book | Lists all transactions recorded day-wise in chronological order. |
| Vouchers of a Ledger | Ledger Vouchers | Shows detailed transactions and balance for a specific ledger. |
| Group Summary | Group Summary | Displays summarized balances for a selected group of ledgers. |
| Vouchers of a Group | Group Vouchers | Displays all vouchers associated with ledgers under a selected group, helping analyse transaction-level activity for that group. |
| Outstanding Receivables | Bills Receivable | Lists pending amounts to be received from customers. |
| Outstanding Payables | Bills Payable | Lists pending amounts to be paid to suppliers. |
| Cash/Bank Book | Bank Book Summary | Shows all cash and bank transactions with running balances. |
| Voucher Register | Voucher Register | Lists all transactions recorded day-wise in chronological order. |
| Sales Register | Sales Register | Shows a comprehensive view of the month-wise sales done. |
| Purchase Register | Purchase Register | Shows a comprehensive view of the month-wise purchases done. |
| Payment Register | Payment Register | Shows a comprehensive view of the month-wise payments done. |
| Receipt Register | Receipts Register | Shows a comprehensive view of the month-wise receipts recorded. |
| Contra Register | Contra Register | Shows a comprehensive month-wise view of all contra transactions recorded. |
| Journal Register | Journal Register | Shows a comprehensive month-wise view of all journal transactions recorded. |
| Debit Note Register | Debit Note Register | Shows a comprehensive month-wise view of all debit note transactions recorded. |
| Credit Note Register | Credit Note Register | Shows a comprehensive month-wise view of all credit note transactions recorded. |

**Frequently Used Static Variables for Reports**

Static Variables are used to control the context, scope, and behavior of reports while fetching data through APIs. They help you filter, format, and customize report output without modifying the report itself. These variables should be used within <StaticVariables> tag.

Below are some commonly used Static Variables across reports:

| Variable Name | Data Type | Example Value | Purpose |
|---|---|---|---|
| SVFromDate | Date | 20240401 | Start date of the report period (YYYYMMDD). |
| SVToDate | Date | 20240430 | End date of the report period (YYYYMMDD). |
| SVCurrentDate | Date | 20240402 | Current date of the report (YYYYMMDD). Applicable for reports listing transactions like Day Book and Voucher Register |
| SVCurrentCompany | String | "ABC Pvt Ltd" | Specifies the company for which data is fetched. In absence would fetch from currently loaded active company |
| SVExportFormat | String | "XML" | Output format for export (XML/JSONEx). |
| ExplodeFlag | Logical | Yes | Expands a selected line item to show underlying details. |
| ExplodeAllLevels | Logical | Yes | Expands all hierarchical levels in the report for complete drill-down visibility. |
| ShowForex | Logical | Yes | Displays values in foreign currency along with base currency in reports. |

**Report-Specific Static Variables**

| Report Name | Report ID | Variable Name | Data Type | Example Value | Purpose |
|---|---|---|---|---|---|
| Trial Balance Vouchers of a Group | Trial Balance Group Vouchers | GroupName | String | "Sundry Debtors" | Fetches data for a specific group. |
| Trial Balance | Trial Balance | IsLedgerwise | Logical | Yes | Controls whether the Trial Balance is displayed at the ledger level instead of grouped summaries. |
| Group Summary | Group Summary | GroupName | String | "Current Assets" | Filters data for a specific group. |
| Ledger | Ledger | LedgerName | String | "Cash" | Specifies the ledger for the report. |
| Stock Summary | Stock Summary | IsItemWise | Logical | Yes | Shows report stockitemwise |
| Day Book Voucher Register | Day Book Voucher Register | VoucherTypeName | String | "Sales" | Filters vouchers by vouchertype |
| Vouchers of a Ledger | Ledger Vouchers | LedgerName | String | "Cash" | Fetches data for a specific ledger. |

## 5.1 Trial Balance

### 5.1.0 Trial Balance — Overview & Field Reference

> 🟢 Official: converted from the Explorer's "About Trial Balance" page.

Trial Balance is a summary report that displays the closing balances of all ledgers and groups for a specified period. It helps verify the accuracy of accounting entries by ensuring that total debits and total credits are balanced.

In TallyPrime API Explorer, the Trial Balance report provides a structured view of financial data that can be accessed programmatically for analysis, reconciliation, and reporting purposes.

Businesses commonly use Trial Balance to:

- Verify accounting accuracy
- Identify discrepancies or unbalanced entries
- Analyze ledger and group balances
- Prepare financial statements such as Balance Sheet and Profit & Loss
- Monitor business performance and financial health

This report supports:

- Group-wise and ledger-wise views
- Hierarchical drill-down using explode options
- Filtering using report-specific static variables
- Export in XML and JSON formats

Trial Balance is commonly used in integrations involving:

- Financial dashboards
- Audit and reconciliation systems
- MIS and analytical reporting
- Accounting data synchronization

Its structured and hierarchical nature makes it one of the most widely used reports in TallyPrime.

### 5.1.1 Pull Trial Balance for any Period

> Explorer id: `pull-trial-balance-period` · Kind: **report** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#pull-trial-balance-period)

#### Description

Any report in TallyPrime can be fetched using its TDL Report Name as a unique identifier. To fetch Trial Balance, the TDL report name - Trial Balance is specified in the &lt;ID&gt; tag (XML) or id HTTP header (JSON). The report period is defined using SVFromDate and SVToDate in the static variables section.

**Integration use:** Feed financial dashboards with Tally-computed balances, with no need to re-implement accounting logic in your system.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svExportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVEXPORTFORMAT>XML</SVEXPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `export` | Yes |
| `type` | `data` | Yes |
| `id` | `Trial Balance` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    },
    {
      "name": "svFromDate",
      "value": "20250401"
    },
    {
      "name": "svToDate",
      "value": "20250430"
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Data</TYPE>
    <ID>Trial Balance</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>
        <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
        <SVFROMDATE>20250401</SVFROMDATE>
        <SVTODATE>20250430</SVTODATE>
      </STATICVARIABLES>
    </DESC>
  </BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: export" \
  -H "type: data" \
  -H "id: Trial Balance" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟡 Illustrative: JSONEx output lowercases the report's XML tags and wraps repeated lines in arrays named after the report's Form → Part → Line structure, see the official Balance Sheet sample in [§1.9](#19-response-structure). Find rows by looking for objects that contain `dspaccname`/`dspaccinfo`; `<line-array>` stands for that array name):

```json
{
    "status": "1",
    "data": {
        "<line-array>": [
            {
                "dspaccname": {
                    "dspdispname": "Capital Account"
                },
                "dspaccinfo": {
                    "dspclcramt": {
                        "dspclcramta": 2000000
                    }
                }
            },
            {
                "dspaccname": {
                    "dspdispname": "Current Liabilities"
                },
                "dspaccinfo": {
                    "dspclcramt": {
                        "dspclcramta": 391338.71
                    }
                }
            },
            {
                "dspaccname": {
                    "dspdispname": "Fixed Assets"
                },
                "dspaccinfo": {
                    "dspcldramt": {
                        "dspcldramta": -100000
                    }
                }
            },
            {
                "dspaccname": {
                    "dspdispname": "Current Assets"
                },
                "dspaccinfo": {
                    "dspcldramt": {
                        "dspcldramta": -3843350
                    }
                }
            },
            {
                "dspaccname": {
                    "dspdispname": "Sales Accounts"
                },
                "dspaccinfo": {
                    "dspclcramt": {
                        "dspclcramta": 1650000
                    }
                }
            },
            {
                "dspaccname": {
                    "dspdispname": "Indirect Expenses"
                },
                "dspaccinfo": {
                    "dspcldramt": {
                        "dspcldramta": -97988.71
                    }
                }
            }
        ]
    }
}
```

**Success — XML** (🟡 Illustrative: classic report XML has no `HEADER/STATUS` wrapper, just the report's display tags in order; Debit amounts are negative):

```xml
<ENVELOPE>
    <DSPACCNAME>
        <DSPDISPNAME>Capital Account</DSPDISPNAME>
    </DSPACCNAME>
    <DSPACCINFO>
        <DSPCLDRAMT>
            <DSPCLDRAMTA></DSPCLDRAMTA>
        </DSPCLDRAMT>
        <DSPCLCRAMT>
            <DSPCLCRAMTA>2000000.00</DSPCLCRAMTA>
        </DSPCLCRAMT>
    </DSPACCINFO>
    <DSPACCNAME>
        <DSPDISPNAME>Current Liabilities</DSPDISPNAME>
    </DSPACCNAME>
    <DSPACCINFO>
        <DSPCLDRAMT>
            <DSPCLDRAMTA></DSPCLDRAMTA>
        </DSPCLDRAMT>
        <DSPCLCRAMT>
            <DSPCLCRAMTA>391338.71</DSPCLCRAMTA>
        </DSPCLCRAMT>
    </DSPACCINFO>
    <DSPACCNAME>
        <DSPDISPNAME>Fixed Assets</DSPDISPNAME>
    </DSPACCNAME>
    <DSPACCINFO>
        <DSPCLDRAMT>
            <DSPCLDRAMTA>-100000.00</DSPCLDRAMTA>
        </DSPCLDRAMT>
        <DSPCLCRAMT>
            <DSPCLCRAMTA></DSPCLCRAMTA>
        </DSPCLCRAMT>
    </DSPACCINFO>
    <DSPACCNAME>
        <DSPDISPNAME>Current Assets</DSPDISPNAME>
    </DSPACCNAME>
    <DSPACCINFO>
        <DSPCLDRAMT>
            <DSPCLDRAMTA>-3843350.00</DSPCLDRAMTA>
        </DSPCLDRAMT>
        <DSPCLCRAMT>
            <DSPCLCRAMTA></DSPCLCRAMTA>
        </DSPCLCRAMT>
    </DSPACCINFO>
    <DSPACCNAME>
        <DSPDISPNAME>Sales Accounts</DSPDISPNAME>
    </DSPACCNAME>
    <DSPACCINFO>
        <DSPCLDRAMT>
            <DSPCLDRAMTA></DSPCLDRAMTA>
        </DSPCLDRAMT>
        <DSPCLCRAMT>
            <DSPCLCRAMTA>1650000.00</DSPCLCRAMTA>
        </DSPCLCRAMT>
    </DSPACCINFO>
    <DSPACCNAME>
        <DSPDISPNAME>Indirect Expenses</DSPDISPNAME>
    </DSPACCNAME>
    <DSPACCINFO>
        <DSPCLDRAMT>
            <DSPCLDRAMTA>-97988.71</DSPCLDRAMTA>
        </DSPCLDRAMT>
        <DSPCLCRAMT>
            <DSPCLCRAMTA></DSPCLCRAMTA>
        </DSPCLCRAMT>
    </DSPACCINFO>
</ENVELOPE>
```

#### Error Responses

- **Unknown report name** (🟡 Illustrative): an `id` that is not a TDL report name returns an error or an empty envelope. Use the exact Report IDs in [§5](#5-reports).
- **Period outside books** returns zero rows, not an error. Validate `svFromDate` ≤ `svToDate` yourself.
- [Common errors](#110-common-error-responses) apply.

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `export` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `data` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `Trial Balance` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svExportFormat]` | `<STATICVARIABLES><SVEXPORTFORMAT>` | Yes (export) | String | `jsonex` | Response format: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `static_variables[name=svFromDate]` | `<STATICVARIABLES><SVFROMDATE>` | Cond. | Date (YYYYMMDD) | `20250401` | Report period start. |
| `static_variables[name=svToDate]` | `<STATICVARIABLES><SVTODATE>` | Cond. | Date (YYYYMMDD) | `20250430` | Report period end. |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Fetch the report Profit &amp; Loss from TallyPrime | TDL Report name is Profit and Loss | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/trial-balance/any-period/json/TaskFetchProfitandLossJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/trial-balance/any-period/xml/TaskFetchProfitandLossXML.txt) |
| Fetch the report Balance Sheet for the month of May from TallyPrime | TDL Report name is Balance Sheet. Change the values of variables svFromDate and svToDate | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/trial-balance/any-period/json/TaskFetchBalanceSheetMayJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/trial-balance/any-period/xml/TaskFetchBalanceSheetMayXML.txt) |

### 5.1.2 Pull Trial Balance Detailed

> Explorer id: `pull-trial-balance-detailed` · Kind: **report** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#pull-trial-balance-detailed)

#### Description

Any report in TallyPrime can be fetched using its TDL Report Name as a unique identifier. To fetch Trial Balance, the TDL report name - Trial Balance is specified in the &lt;ID&gt; tag (XML) or id HTTP header (JSON). Detailed format of report is defined using the logical variables ExplodeFlag and ExplodeAllLevels in the static variables section.

**Integration use:** Drill-down view (every group expanded to ledgers) for audit and reconciliation screens.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svExportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVEXPORTFORMAT>XML</SVEXPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `export` | Yes |
| `type` | `data` | Yes |
| `id` | `Trial Balance` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    },
    {
      "name": "svFromDate",
      "value": "20250401"
    },
    {
      "name": "svToDate",
      "value": "20250430"
    },
    {
      "name": "ExplodeFlag",
      "value": "Yes"
    },
    {
      "name": "ExplodeAllLevels",
      "value": "Yes"
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Data</TYPE>
    <ID>Trial Balance</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>
        <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
        <SVFROMDATE>20250401</SVFROMDATE>
        <SVTODATE>20250430</SVTODATE>
        <EXPLODEFLAG>Yes</EXPLODEFLAG>
        <EXPLODEALLLEVELS>Yes</EXPLODEALLLEVELS>
      </STATICVARIABLES>
    </DESC>
  </BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: export" \
  -H "type: data" \
  -H "id: Trial Balance" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟡 Illustrative: JSONEx output lowercases the report's XML tags and wraps repeated lines in arrays named after the report's Form → Part → Line structure, see the official Balance Sheet sample in [§1.9](#19-response-structure). Find rows by looking for objects that contain `dspaccname`/`dspaccinfo`; `<line-array>` stands for that array name):

```json
{
    "status": "1",
    "data": {
        "<line-array>": [
            {
                "dspaccname": {
                    "dspdispname": "Capital Account"
                },
                "dspaccinfo": {
                    "dspclcramt": {
                        "dspclcramta": 2000000
                    }
                }
            },
            {
                "dspaccname": {
                    "dspdispname": "Current Liabilities"
                },
                "dspaccinfo": {
                    "dspclcramt": {
                        "dspclcramta": 391338.71
                    }
                }
            },
            {
                "dspaccname": {
                    "dspdispname": "Fixed Assets"
                },
                "dspaccinfo": {
                    "dspcldramt": {
                        "dspcldramta": -100000
                    }
                }
            },
            {
                "dspaccname": {
                    "dspdispname": "Current Assets"
                },
                "dspaccinfo": {
                    "dspcldramt": {
                        "dspcldramta": -3843350
                    }
                }
            },
            {
                "dspaccname": {
                    "dspdispname": "Bank Accounts"
                },
                "dspaccinfo": {
                    "dspcldramt": {
                        "dspcldramta": -518750
                    }
                }
            },
            {
                "dspaccname": {
                    "dspdispname": "Kotak Bank"
                },
                "dspaccinfo": {
                    "dspcldramt": {
                        "dspcldramta": -312450
                    }
                }
            },
            {
                "dspaccname": {
                    "dspdispname": "Bank of Baroda"
                },
                "dspaccinfo": {
                    "dspcldramt": {
                        "dspcldramta": -206300
                    }
                }
            },
            {
                "dspaccname": {
                    "dspdispname": "Cash-in-Hand"
                },
                "dspaccinfo": {
                    "dspcldramt": {
                        "dspcldramta": -24600
                    }
                }
            },
            {
                "dspaccname": {
                    "dspdispname": "Cash"
                },
                "dspaccinfo": {
                    "dspcldramt": {
                        "dspcldramta": -24600
                    }
                }
            },
            {
                "dspaccname": {
                    "dspdispname": "Sundry Debtors"
                },
                "dspaccinfo": {
                    "dspcldramt": {
                        "dspcldramta": -3300000
                    }
                }
            },
            {
                "dspaccname": {
                    "dspdispname": "ABC Party"
                },
                "dspaccinfo": {
                    "dspcldramt": {
                        "dspcldramta": -3300000
                    }
                }
            },
            {
                "dspaccname": {
                    "dspdispname": "Sales Accounts"
                },
                "dspaccinfo": {
                    "dspclcramt": {
                        "dspclcramta": 1650000
                    }
                }
            },
            {
                "dspaccname": {
                    "dspdispname": "Indirect Expenses"
                },
                "dspaccinfo": {
                    "dspcldramt": {
                        "dspcldramta": -97988.71
                    }
                }
            }
        ]
    }
}
```

**Success — XML** (🟡 Illustrative: classic report XML has no `HEADER/STATUS` wrapper, just the report's display tags in order; Debit amounts are negative):

```xml
<ENVELOPE>
    <DSPACCNAME>
        <DSPDISPNAME>Capital Account</DSPDISPNAME>
    </DSPACCNAME>
    <DSPACCINFO>
        <DSPCLDRAMT>
            <DSPCLDRAMTA></DSPCLDRAMTA>
        </DSPCLDRAMT>
        <DSPCLCRAMT>
            <DSPCLCRAMTA>2000000.00</DSPCLCRAMTA>
        </DSPCLCRAMT>
    </DSPACCINFO>
    <DSPACCNAME>
        <DSPDISPNAME>Current Liabilities</DSPDISPNAME>
    </DSPACCNAME>
    <DSPACCINFO>
        <DSPCLDRAMT>
            <DSPCLDRAMTA></DSPCLDRAMTA>
        </DSPCLDRAMT>
        <DSPCLCRAMT>
            <DSPCLCRAMTA>391338.71</DSPCLCRAMTA>
        </DSPCLCRAMT>
    </DSPACCINFO>
    <DSPACCNAME>
        <DSPDISPNAME>Fixed Assets</DSPDISPNAME>
    </DSPACCNAME>
    <DSPACCINFO>
        <DSPCLDRAMT>
            <DSPCLDRAMTA>-100000.00</DSPCLDRAMTA>
        </DSPCLDRAMT>
        <DSPCLCRAMT>
            <DSPCLCRAMTA></DSPCLCRAMTA>
        </DSPCLCRAMT>
    </DSPACCINFO>
    <DSPACCNAME>
        <DSPDISPNAME>Current Assets</DSPDISPNAME>
    </DSPACCNAME>
    <DSPACCINFO>
        <DSPCLDRAMT>
            <DSPCLDRAMTA>-3843350.00</DSPCLDRAMTA>
        </DSPCLDRAMT>
        <DSPCLCRAMT>
            <DSPCLCRAMTA></DSPCLCRAMTA>
        </DSPCLCRAMT>
    </DSPACCINFO>
    <DSPACCNAME>
        <DSPDISPNAME>Bank Accounts</DSPDISPNAME>
    </DSPACCNAME>
    <DSPACCINFO>
        <DSPCLDRAMT>
            <DSPCLDRAMTA>-518750.00</DSPCLDRAMTA>
        </DSPCLDRAMT>
        <DSPCLCRAMT>
            <DSPCLCRAMTA></DSPCLCRAMTA>
        </DSPCLCRAMT>
    </DSPACCINFO>
    <DSPACCNAME>
        <DSPDISPNAME>Kotak Bank</DSPDISPNAME>
    </DSPACCNAME>
    <DSPACCINFO>
        <DSPCLDRAMT>
            <DSPCLDRAMTA>-312450.00</DSPCLDRAMTA>
        </DSPCLDRAMT>
        <DSPCLCRAMT>
            <DSPCLCRAMTA></DSPCLCRAMTA>
        </DSPCLCRAMT>
    </DSPACCINFO>
    <DSPACCNAME>
        <DSPDISPNAME>Bank of Baroda</DSPDISPNAME>
    </DSPACCNAME>
    <DSPACCINFO>
        <DSPCLDRAMT>
            <DSPCLDRAMTA>-206300.00</DSPCLDRAMTA>
        </DSPCLDRAMT>
        <DSPCLCRAMT>
            <DSPCLCRAMTA></DSPCLCRAMTA>
        </DSPCLCRAMT>
    </DSPACCINFO>
    <DSPACCNAME>
        <DSPDISPNAME>Cash-in-Hand</DSPDISPNAME>
    </DSPACCNAME>
    <DSPACCINFO>
        <DSPCLDRAMT>
            <DSPCLDRAMTA>-24600.00</DSPCLDRAMTA>
        </DSPCLDRAMT>
        <DSPCLCRAMT>
            <DSPCLCRAMTA></DSPCLCRAMTA>
        </DSPCLCRAMT>
    </DSPACCINFO>
    <DSPACCNAME>
        <DSPDISPNAME>Cash</DSPDISPNAME>
    </DSPACCNAME>
    <DSPACCINFO>
        <DSPCLDRAMT>
            <DSPCLDRAMTA>-24600.00</DSPCLDRAMTA>
        </DSPCLDRAMT>
        <DSPCLCRAMT>
            <DSPCLCRAMTA></DSPCLCRAMTA>
        </DSPCLCRAMT>
    </DSPACCINFO>
    <DSPACCNAME>
        <DSPDISPNAME>Sundry Debtors</DSPDISPNAME>
    </DSPACCNAME>
    <DSPACCINFO>
        <DSPCLDRAMT>
            <DSPCLDRAMTA>-3300000.00</DSPCLDRAMTA>
        </DSPCLDRAMT>
        <DSPCLCRAMT>
            <DSPCLCRAMTA></DSPCLCRAMTA>
        </DSPCLCRAMT>
    </DSPACCINFO>
    <DSPACCNAME>
        <DSPDISPNAME>ABC Party</DSPDISPNAME>
    </DSPACCNAME>
    <DSPACCINFO>
        <DSPCLDRAMT>
            <DSPCLDRAMTA>-3300000.00</DSPCLDRAMTA>
        </DSPCLDRAMT>
        <DSPCLCRAMT>
            <DSPCLCRAMTA></DSPCLCRAMTA>
        </DSPCLCRAMT>
    </DSPACCINFO>
    <DSPACCNAME>
        <DSPDISPNAME>Sales Accounts</DSPDISPNAME>
    </DSPACCNAME>
    <DSPACCINFO>
        <DSPCLDRAMT>
            <DSPCLDRAMTA></DSPCLDRAMTA>
        </DSPCLDRAMT>
        <DSPCLCRAMT>
            <DSPCLCRAMTA>1650000.00</DSPCLCRAMTA>
        </DSPCLCRAMT>
    </DSPACCINFO>
    <DSPACCNAME>
        <DSPDISPNAME>Indirect Expenses</DSPDISPNAME>
    </DSPACCNAME>
    <DSPACCINFO>
        <DSPCLDRAMT>
            <DSPCLDRAMTA>-97988.71</DSPCLDRAMTA>
        </DSPCLDRAMT>
        <DSPCLCRAMT>
            <DSPCLCRAMTA></DSPCLCRAMTA>
        </DSPCLCRAMT>
    </DSPACCINFO>
</ENVELOPE>
```

#### Error Responses

- **Unknown report name** (🟡 Illustrative): an `id` that is not a TDL report name returns an error or an empty envelope. Use the exact Report IDs in [§5](#5-reports).
- **Period outside books** returns zero rows, not an error. Validate `svFromDate` ≤ `svToDate` yourself.
- [Common errors](#110-common-error-responses) apply.

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `export` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `data` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `Trial Balance` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svExportFormat]` | `<STATICVARIABLES><SVEXPORTFORMAT>` | Yes (export) | String | `jsonex` | Response format: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `static_variables[name=svFromDate]` | `<STATICVARIABLES><SVFROMDATE>` | Cond. | Date (YYYYMMDD) | `20250401` | Report period start. |
| `static_variables[name=svToDate]` | `<STATICVARIABLES><SVTODATE>` | Cond. | Date (YYYYMMDD) | `20250430` | Report period end. |
| `static_variables[name=ExplodeFlag]` | `<STATICVARIABLES><EXPLODEFLAG>` | No | Logical | `Yes` | Expand grouped lines to their next level. |
| `static_variables[name=ExplodeAllLevels]` | `<STATICVARIABLES><EXPLODEALLLEVELS>` | No | Logical | `Yes` | Expand all hierarchy levels (full drill-down). |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Fetch the report Profit &amp; Loss from TallyPrime in detailed format | TDL Report name is Profit and Loss | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/trial-balance/detailed/json/TaskFetchProfitandLossDetailedJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/trial-balance/detailed/xml/TaskFetchProfitandLossDetailedXML.txt) |

### 5.1.3 Pull Trial Balance Plain Format

> Explorer id: `pull-trial-balance-plain` · Kind: **report** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#pull-trial-balance-plain)

#### Description

Any report in TallyPrime can be fetched using its TDL Report Name as a unique identifier. To fetch Trial Balance, the TDL report name - Trial Balance is specified in the &lt;ID&gt; tag (XML) or id HTTP header (JSON). Plain format of report is defined by the Logical Report attribute Plain XML/Plain JSON. Report to be fetched is modified with this attribute set to yes and sent in the tdlmessage section of the request.

**Integration use:** Flat output that is easier to parse when you do not need the report's visual hierarchy.

**Notes:**

- The Explorer sets the report attribute `Plain Xml: Yes`, which also applies to JSON. Alternatives from Tally's guide: static variable `SVExportInPlainFormat = Yes`, or report attribute `Plain JSON`.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svExportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVEXPORTFORMAT>XML</SVEXPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `export` | Yes |
| `type` | `data` | Yes |
| `id` | `Trial Balance` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    },
    {
      "name": "svFromDate",
      "value": "20250401"
    },
    {
      "name": "svToDate",
      "value": "20250430"
    }
  ],
  "tdlmessage": [
    {
      "definitions": [
        {
          "metadata": {
            "name": "Trial Balance",
            "type": "Report",
            "ismodify": true
          },
          "attributes": [
            {
              "Plain Xml": "Yes"
            }
          ]
        }
      ]
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Data</TYPE>
    <ID>Trial Balance</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>
        <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
        <SVFROMDATE>20250401</SVFROMDATE>
        <SVTODATE>20250430</SVTODATE>
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <REPORT NAME="Trial Balance" ISMODIFY="Yes" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
            <PLAINXML>Yes</PLAINXML>
          </REPORT>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: export" \
  -H "type: data" \
  -H "id: Trial Balance" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟡 Illustrative: JSONEx output lowercases the report's XML tags and wraps repeated lines in arrays named after the report's Form → Part → Line structure, see the official Balance Sheet sample in [§1.9](#19-response-structure). Find rows by looking for objects that contain `dspaccname`/`dspaccinfo`; `<line-array>` stands for that array name):

```json
{
    "status": "1",
    "data": {
        "<line-array>": [
            {
                "dspaccname": {
                    "dspdispname": "Capital Account"
                },
                "dspaccinfo": {
                    "dspclcramt": {
                        "dspclcramta": 2000000
                    }
                }
            },
            {
                "dspaccname": {
                    "dspdispname": "Current Liabilities"
                },
                "dspaccinfo": {
                    "dspclcramt": {
                        "dspclcramta": 391338.71
                    }
                }
            },
            {
                "dspaccname": {
                    "dspdispname": "Fixed Assets"
                },
                "dspaccinfo": {
                    "dspcldramt": {
                        "dspcldramta": -100000
                    }
                }
            },
            {
                "dspaccname": {
                    "dspdispname": "Current Assets"
                },
                "dspaccinfo": {
                    "dspcldramt": {
                        "dspcldramta": -3843350
                    }
                }
            },
            {
                "dspaccname": {
                    "dspdispname": "Sales Accounts"
                },
                "dspaccinfo": {
                    "dspclcramt": {
                        "dspclcramta": 1650000
                    }
                }
            },
            {
                "dspaccname": {
                    "dspdispname": "Indirect Expenses"
                },
                "dspaccinfo": {
                    "dspcldramt": {
                        "dspcldramta": -97988.71
                    }
                }
            }
        ]
    }
}
```

**Success — XML** (🟡 Illustrative: classic report XML has no `HEADER/STATUS` wrapper, just the report's display tags in order; Debit amounts are negative):

```xml
<ENVELOPE>
    <DSPACCNAME>
        <DSPDISPNAME>Capital Account</DSPDISPNAME>
    </DSPACCNAME>
    <DSPACCINFO>
        <DSPCLDRAMT>
            <DSPCLDRAMTA></DSPCLDRAMTA>
        </DSPCLDRAMT>
        <DSPCLCRAMT>
            <DSPCLCRAMTA>2000000.00</DSPCLCRAMTA>
        </DSPCLCRAMT>
    </DSPACCINFO>
    <DSPACCNAME>
        <DSPDISPNAME>Current Liabilities</DSPDISPNAME>
    </DSPACCNAME>
    <DSPACCINFO>
        <DSPCLDRAMT>
            <DSPCLDRAMTA></DSPCLDRAMTA>
        </DSPCLDRAMT>
        <DSPCLCRAMT>
            <DSPCLCRAMTA>391338.71</DSPCLCRAMTA>
        </DSPCLCRAMT>
    </DSPACCINFO>
    <DSPACCNAME>
        <DSPDISPNAME>Fixed Assets</DSPDISPNAME>
    </DSPACCNAME>
    <DSPACCINFO>
        <DSPCLDRAMT>
            <DSPCLDRAMTA>-100000.00</DSPCLDRAMTA>
        </DSPCLDRAMT>
        <DSPCLCRAMT>
            <DSPCLCRAMTA></DSPCLCRAMTA>
        </DSPCLCRAMT>
    </DSPACCINFO>
    <DSPACCNAME>
        <DSPDISPNAME>Current Assets</DSPDISPNAME>
    </DSPACCNAME>
    <DSPACCINFO>
        <DSPCLDRAMT>
            <DSPCLDRAMTA>-3843350.00</DSPCLDRAMTA>
        </DSPCLDRAMT>
        <DSPCLCRAMT>
            <DSPCLCRAMTA></DSPCLCRAMTA>
        </DSPCLCRAMT>
    </DSPACCINFO>
    <DSPACCNAME>
        <DSPDISPNAME>Sales Accounts</DSPDISPNAME>
    </DSPACCNAME>
    <DSPACCINFO>
        <DSPCLDRAMT>
            <DSPCLDRAMTA></DSPCLDRAMTA>
        </DSPCLDRAMT>
        <DSPCLCRAMT>
            <DSPCLCRAMTA>1650000.00</DSPCLCRAMTA>
        </DSPCLCRAMT>
    </DSPACCINFO>
    <DSPACCNAME>
        <DSPDISPNAME>Indirect Expenses</DSPDISPNAME>
    </DSPACCNAME>
    <DSPACCINFO>
        <DSPCLDRAMT>
            <DSPCLDRAMTA>-97988.71</DSPCLDRAMTA>
        </DSPCLDRAMT>
        <DSPCLCRAMT>
            <DSPCLCRAMTA></DSPCLCRAMTA>
        </DSPCLCRAMT>
    </DSPACCINFO>
</ENVELOPE>
```

#### Error Responses

- **Unknown report name** (🟡 Illustrative): an `id` that is not a TDL report name returns an error or an empty envelope. Use the exact Report IDs in [§5](#5-reports).
- **Period outside books** returns zero rows, not an error. Validate `svFromDate` ≤ `svToDate` yourself.
- [Common errors](#110-common-error-responses) apply.

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `export` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `data` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `Trial Balance` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svExportFormat]` | `<STATICVARIABLES><SVEXPORTFORMAT>` | Yes (export) | String | `jsonex` | Response format: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `static_variables[name=svFromDate]` | `<STATICVARIABLES><SVFROMDATE>` | Cond. | Date (YYYYMMDD) | `20250401` | Report period start. |
| `static_variables[name=svToDate]` | `<STATICVARIABLES><SVTODATE>` | Cond. | Date (YYYYMMDD) | `20250430` | Report period end. |
| `tdlmessage[]` | `<TDL><TDLMESSAGE>` | Cond. | Array<Object> |  | Inline TDL definitions (Collection / Report modification / System Formulae) that Tally loads before executing the request. |
| `tdlmessage[].definitions[]` | `<REPORT …>` | Cond. | Array<Object> |  | List of TDL definitions inside `tdlmessage`. |
| `tdlmessage[].definitions[].metadata.name` | `NAME` attribute | Yes | String | `Trial Balance` | Definition name. For a Collection it must match the `id` header / `<ID>`. TDL names are case- and space-insensitive. |
| `tdlmessage[].definitions[].metadata.type` | element name | Yes | String | `Report` | Definition kind: `Collection`, `Report`, or `System`. |
| `tdlmessage[].definitions[].metadata.ismodify` | `ISMODIFY` attribute | No | Boolean | `true` | `true` modifies an existing (default) definition instead of declaring a new one (`#` / `ISMODIFY="Yes"` in XML). |
| `tdlmessage[].definitions[].attributes[].Plain Xml` | `<PLAINXML>` | No | Logical | `Yes` | Report attribute. `Yes` returns the report in plain (flat) XML/JSON. |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Fetch the report Profit &amp; Loss from TallyPrime in plain format | TDL Report name is Profit and Loss | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/trial-balance/plain-format/json/TaskFetchProfitandLossPlainJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/trial-balance/plain-format/xml/TaskFetchProfitandLossPlainXML.txt) |

### 5.1.4 Pull Trial Balance with Empty Fields

> Explorer id: `pull-trial-balance-empty-fields` · Kind: **report** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#pull-trial-balance-empty-fields)

#### Description

Any report in TallyPrime can be fetched using its TDL Report Name as a unique identifier. To fetch Trial Balance, the TDL report name - Trial Balance is specified in the &lt;ID&gt; tag (XML) or id HTTP header (JSON). By default, XML responses include all tags (even those with empty values), whereas JSON responses include only tags with values. To include empty fields in JSON, the Export Empty Fields report attribute must be set to Yes by modifying the report in the tdlmessage section of the request. This attribute is applicable only for JSON, as XML by default includes all tags.

**Integration use:** Stable JSON schema: every field is present even when blank, which simplifies typed deserialisation.

**Notes:**

- Only affects JSON. XML always includes empty tags.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svExportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVEXPORTFORMAT>XML</SVEXPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `export` | Yes |
| `type` | `data` | Yes |
| `id` | `Trial Balance` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    },
    {
      "name": "svFromDate",
      "value": "20250401"
    },
    {
      "name": "svToDate",
      "value": "20250430"
    }
  ],
  "tdlmessage": [
    {
      "definitions": [
        {
          "metadata": {
            "name": "Trial Balance",
            "type": "Report",
            "ismodify": true
          },
          "attributes": [
            {
              "Export Empty Fields": "Yes"
            }
          ]
        }
      ]
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Data</TYPE>
    <ID>Trial Balance</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>
        <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
        <SVFROMDATE>20250401</SVFROMDATE>
        <SVTODATE>20250430</SVTODATE>
      </STATICVARIABLES>
    </DESC>
  </BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: export" \
  -H "type: data" \
  -H "id: Trial Balance" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟡 Illustrative: JSONEx output lowercases the report's XML tags and wraps repeated lines in arrays named after the report's Form → Part → Line structure, see the official Balance Sheet sample in [§1.9](#19-response-structure). Find rows by looking for objects that contain `dspaccname`/`dspaccinfo`; `<line-array>` stands for that array name):

```json
{
    "status": "1",
    "data": {
        "<line-array>": [
            {
                "dspaccname": {
                    "dspdispname": "Capital Account"
                },
                "dspaccinfo": {
                    "dspcldramt": {
                        "dspcldramta": ""
                    },
                    "dspclcramt": {
                        "dspclcramta": 2000000
                    }
                }
            },
            {
                "dspaccname": {
                    "dspdispname": "Current Liabilities"
                },
                "dspaccinfo": {
                    "dspcldramt": {
                        "dspcldramta": ""
                    },
                    "dspclcramt": {
                        "dspclcramta": 391338.71
                    }
                }
            },
            {
                "dspaccname": {
                    "dspdispname": "Fixed Assets"
                },
                "dspaccinfo": {
                    "dspcldramt": {
                        "dspcldramta": -100000
                    },
                    "dspclcramt": {
                        "dspclcramta": ""
                    }
                }
            },
            {
                "dspaccname": {
                    "dspdispname": "Current Assets"
                },
                "dspaccinfo": {
                    "dspcldramt": {
                        "dspcldramta": -3843350
                    },
                    "dspclcramt": {
                        "dspclcramta": ""
                    }
                }
            },
            {
                "dspaccname": {
                    "dspdispname": "Sales Accounts"
                },
                "dspaccinfo": {
                    "dspcldramt": {
                        "dspcldramta": ""
                    },
                    "dspclcramt": {
                        "dspclcramta": 1650000
                    }
                }
            },
            {
                "dspaccname": {
                    "dspdispname": "Indirect Expenses"
                },
                "dspaccinfo": {
                    "dspcldramt": {
                        "dspcldramta": -97988.71
                    },
                    "dspclcramt": {
                        "dspclcramta": ""
                    }
                }
            }
        ]
    }
}
```

**Success — XML** (🟡 Illustrative: classic report XML has no `HEADER/STATUS` wrapper, just the report's display tags in order; Debit amounts are negative):

```xml
<ENVELOPE>
    <DSPACCNAME>
        <DSPDISPNAME>Capital Account</DSPDISPNAME>
    </DSPACCNAME>
    <DSPACCINFO>
        <DSPCLDRAMT>
            <DSPCLDRAMTA></DSPCLDRAMTA>
        </DSPCLDRAMT>
        <DSPCLCRAMT>
            <DSPCLCRAMTA>2000000.00</DSPCLCRAMTA>
        </DSPCLCRAMT>
    </DSPACCINFO>
    <DSPACCNAME>
        <DSPDISPNAME>Current Liabilities</DSPDISPNAME>
    </DSPACCNAME>
    <DSPACCINFO>
        <DSPCLDRAMT>
            <DSPCLDRAMTA></DSPCLDRAMTA>
        </DSPCLDRAMT>
        <DSPCLCRAMT>
            <DSPCLCRAMTA>391338.71</DSPCLCRAMTA>
        </DSPCLCRAMT>
    </DSPACCINFO>
    <DSPACCNAME>
        <DSPDISPNAME>Fixed Assets</DSPDISPNAME>
    </DSPACCNAME>
    <DSPACCINFO>
        <DSPCLDRAMT>
            <DSPCLDRAMTA>-100000.00</DSPCLDRAMTA>
        </DSPCLDRAMT>
        <DSPCLCRAMT>
            <DSPCLCRAMTA></DSPCLCRAMTA>
        </DSPCLCRAMT>
    </DSPACCINFO>
    <DSPACCNAME>
        <DSPDISPNAME>Current Assets</DSPDISPNAME>
    </DSPACCNAME>
    <DSPACCINFO>
        <DSPCLDRAMT>
            <DSPCLDRAMTA>-3843350.00</DSPCLDRAMTA>
        </DSPCLDRAMT>
        <DSPCLCRAMT>
            <DSPCLCRAMTA></DSPCLCRAMTA>
        </DSPCLCRAMT>
    </DSPACCINFO>
    <DSPACCNAME>
        <DSPDISPNAME>Sales Accounts</DSPDISPNAME>
    </DSPACCNAME>
    <DSPACCINFO>
        <DSPCLDRAMT>
            <DSPCLDRAMTA></DSPCLDRAMTA>
        </DSPCLDRAMT>
        <DSPCLCRAMT>
            <DSPCLCRAMTA>1650000.00</DSPCLCRAMTA>
        </DSPCLCRAMT>
    </DSPACCINFO>
    <DSPACCNAME>
        <DSPDISPNAME>Indirect Expenses</DSPDISPNAME>
    </DSPACCNAME>
    <DSPACCINFO>
        <DSPCLDRAMT>
            <DSPCLDRAMTA>-97988.71</DSPCLDRAMTA>
        </DSPCLDRAMT>
        <DSPCLCRAMT>
            <DSPCLCRAMTA></DSPCLCRAMTA>
        </DSPCLCRAMT>
    </DSPACCINFO>
</ENVELOPE>
```

#### Error Responses

- **Unknown report name** (🟡 Illustrative): an `id` that is not a TDL report name returns an error or an empty envelope. Use the exact Report IDs in [§5](#5-reports).
- **Period outside books** returns zero rows, not an error. Validate `svFromDate` ≤ `svToDate` yourself.
- [Common errors](#110-common-error-responses) apply.

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `export` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `data` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `Trial Balance` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svExportFormat]` | `<STATICVARIABLES><SVEXPORTFORMAT>` | Yes (export) | String | `jsonex` | Response format: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `static_variables[name=svFromDate]` | `<STATICVARIABLES><SVFROMDATE>` | Cond. | Date (YYYYMMDD) | `20250401` | Report period start. |
| `static_variables[name=svToDate]` | `<STATICVARIABLES><SVTODATE>` | Cond. | Date (YYYYMMDD) | `20250430` | Report period end. |
| `tdlmessage[]` | `<TDL><TDLMESSAGE>` | Cond. | Array<Object> |  | Inline TDL definitions (Collection / Report modification / System Formulae) that Tally loads before executing the request. |
| `tdlmessage[].definitions[]` | `<REPORT …>` | Cond. | Array<Object> |  | List of TDL definitions inside `tdlmessage`. |
| `tdlmessage[].definitions[].metadata.name` | `NAME` attribute | Yes | String | `Trial Balance` | Definition name. For a Collection it must match the `id` header / `<ID>`. TDL names are case- and space-insensitive. |
| `tdlmessage[].definitions[].metadata.type` | element name | Yes | String | `Report` | Definition kind: `Collection`, `Report`, or `System`. |
| `tdlmessage[].definitions[].metadata.ismodify` | `ISMODIFY` attribute | No | Boolean | `true` | `true` modifies an existing (default) definition instead of declaring a new one (`#` / `ISMODIFY="Yes"` in XML). |
| `tdlmessage[].definitions[].attributes[].Export Empty Fields` | `<EXPORTEMPTYFIELDS>` | No | Logical | `Yes` | Report attribute (JSON only). `Yes` keeps empty fields in the JSON response; XML always includes them. |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Fetch the report Profit &amp; Loss from TallyPrime with empty fields | TDL Report name is Profit and Loss | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/trial-balance/empty-fields/json/TaskFetchProfitandLossEmptyJSON.txt) |

### 5.1.5 Pull Trial Balance Ledger wise

> Explorer id: `pull-trial-balance-ledger-wise` · Kind: **report** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#pull-trial-balance-ledger-wise)

#### Description

Any report in TallyPrime can be fetched using its TDL Report Name as a unique identifier. To fetch Trial Balance, the TDL report name - Trial Balance is specified in the &lt;ID&gt; tag (XML) or id HTTP header (JSON). Ledger-wise format of Trial Balance is defined using the logical variable IsLedgerwise in the static variables section.

**Integration use:** Ledger-level balances in one call, the most common input for MIS and BI pipelines.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svExportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVEXPORTFORMAT>XML</SVEXPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `export` | Yes |
| `type` | `data` | Yes |
| `id` | `Trial Balance` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    },
    {
      "name": "svFromDate",
      "value": "20250401"
    },
    {
      "name": "svToDate",
      "value": "20250430"
    },
    {
      "name": "IsLedgerwise",
      "value": "Yes"
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Data</TYPE>
    <ID>Trial Balance</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>
        <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
        <SVFROMDATE>20250401</SVFROMDATE>
        <SVTODATE>20250430</SVTODATE>
        <ISLEDGERWISE>Yes</ISLEDGERWISE>
      </STATICVARIABLES>
    </DESC>
  </BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: export" \
  -H "type: data" \
  -H "id: Trial Balance" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟡 Illustrative: JSONEx output lowercases the report's XML tags and wraps repeated lines in arrays named after the report's Form → Part → Line structure, see the official Balance Sheet sample in [§1.9](#19-response-structure). Find rows by looking for objects that contain `dspaccname`/`dspaccinfo`; `<line-array>` stands for that array name):

```json
{
    "status": "1",
    "data": {
        "<line-array>": [
            {
                "dspaccname": {
                    "dspdispname": "Capital A/c - Sanjay Sharma"
                },
                "dspaccinfo": {
                    "dspclcramt": {
                        "dspclcramta": 2000000
                    }
                }
            },
            {
                "dspaccname": {
                    "dspdispname": "Akshaya Enterprises"
                },
                "dspaccinfo": {
                    "dspclcramt": {
                        "dspclcramta": 391338.71
                    }
                }
            },
            {
                "dspaccname": {
                    "dspdispname": "Computers"
                },
                "dspaccinfo": {
                    "dspcldramt": {
                        "dspcldramta": -100000
                    }
                }
            },
            {
                "dspaccname": {
                    "dspdispname": "Kotak Bank"
                },
                "dspaccinfo": {
                    "dspcldramt": {
                        "dspcldramta": -312450
                    }
                }
            },
            {
                "dspaccname": {
                    "dspdispname": "Bank of Baroda"
                },
                "dspaccinfo": {
                    "dspcldramt": {
                        "dspcldramta": -206300
                    }
                }
            },
            {
                "dspaccname": {
                    "dspdispname": "Cash"
                },
                "dspaccinfo": {
                    "dspcldramt": {
                        "dspcldramta": -24600
                    }
                }
            },
            {
                "dspaccname": {
                    "dspdispname": "ABC Party"
                },
                "dspaccinfo": {
                    "dspcldramt": {
                        "dspcldramta": -3300000
                    }
                }
            },
            {
                "dspaccname": {
                    "dspdispname": "Sales"
                },
                "dspaccinfo": {
                    "dspclcramt": {
                        "dspclcramta": 1650000
                    }
                }
            },
            {
                "dspaccname": {
                    "dspdispname": "Advertising Expenses"
                },
                "dspaccinfo": {
                    "dspcldramt": {
                        "dspcldramta": -97988.71
                    }
                }
            }
        ]
    }
}
```

**Success — XML** (🟡 Illustrative: classic report XML has no `HEADER/STATUS` wrapper, just the report's display tags in order; Debit amounts are negative):

```xml
<ENVELOPE>
    <DSPACCNAME>
        <DSPDISPNAME>Capital A/c - Sanjay Sharma</DSPDISPNAME>
    </DSPACCNAME>
    <DSPACCINFO>
        <DSPCLDRAMT>
            <DSPCLDRAMTA></DSPCLDRAMTA>
        </DSPCLDRAMT>
        <DSPCLCRAMT>
            <DSPCLCRAMTA>2000000.00</DSPCLCRAMTA>
        </DSPCLCRAMT>
    </DSPACCINFO>
    <DSPACCNAME>
        <DSPDISPNAME>Akshaya Enterprises</DSPDISPNAME>
    </DSPACCNAME>
    <DSPACCINFO>
        <DSPCLDRAMT>
            <DSPCLDRAMTA></DSPCLDRAMTA>
        </DSPCLDRAMT>
        <DSPCLCRAMT>
            <DSPCLCRAMTA>391338.71</DSPCLCRAMTA>
        </DSPCLCRAMT>
    </DSPACCINFO>
    <DSPACCNAME>
        <DSPDISPNAME>Computers</DSPDISPNAME>
    </DSPACCNAME>
    <DSPACCINFO>
        <DSPCLDRAMT>
            <DSPCLDRAMTA>-100000.00</DSPCLDRAMTA>
        </DSPCLDRAMT>
        <DSPCLCRAMT>
            <DSPCLCRAMTA></DSPCLCRAMTA>
        </DSPCLCRAMT>
    </DSPACCINFO>
    <DSPACCNAME>
        <DSPDISPNAME>Kotak Bank</DSPDISPNAME>
    </DSPACCNAME>
    <DSPACCINFO>
        <DSPCLDRAMT>
            <DSPCLDRAMTA>-312450.00</DSPCLDRAMTA>
        </DSPCLDRAMT>
        <DSPCLCRAMT>
            <DSPCLCRAMTA></DSPCLCRAMTA>
        </DSPCLCRAMT>
    </DSPACCINFO>
    <DSPACCNAME>
        <DSPDISPNAME>Bank of Baroda</DSPDISPNAME>
    </DSPACCNAME>
    <DSPACCINFO>
        <DSPCLDRAMT>
            <DSPCLDRAMTA>-206300.00</DSPCLDRAMTA>
        </DSPCLDRAMT>
        <DSPCLCRAMT>
            <DSPCLCRAMTA></DSPCLCRAMTA>
        </DSPCLCRAMT>
    </DSPACCINFO>
    <DSPACCNAME>
        <DSPDISPNAME>Cash</DSPDISPNAME>
    </DSPACCNAME>
    <DSPACCINFO>
        <DSPCLDRAMT>
            <DSPCLDRAMTA>-24600.00</DSPCLDRAMTA>
        </DSPCLDRAMT>
        <DSPCLCRAMT>
            <DSPCLCRAMTA></DSPCLCRAMTA>
        </DSPCLCRAMT>
    </DSPACCINFO>
    <DSPACCNAME>
        <DSPDISPNAME>ABC Party</DSPDISPNAME>
    </DSPACCNAME>
    <DSPACCINFO>
        <DSPCLDRAMT>
            <DSPCLDRAMTA>-3300000.00</DSPCLDRAMTA>
        </DSPCLDRAMT>
        <DSPCLCRAMT>
            <DSPCLCRAMTA></DSPCLCRAMTA>
        </DSPCLCRAMT>
    </DSPACCINFO>
    <DSPACCNAME>
        <DSPDISPNAME>Sales</DSPDISPNAME>
    </DSPACCNAME>
    <DSPACCINFO>
        <DSPCLDRAMT>
            <DSPCLDRAMTA></DSPCLDRAMTA>
        </DSPCLDRAMT>
        <DSPCLCRAMT>
            <DSPCLCRAMTA>1650000.00</DSPCLCRAMTA>
        </DSPCLCRAMT>
    </DSPACCINFO>
    <DSPACCNAME>
        <DSPDISPNAME>Advertising Expenses</DSPDISPNAME>
    </DSPACCNAME>
    <DSPACCINFO>
        <DSPCLDRAMT>
            <DSPCLDRAMTA>-97988.71</DSPCLDRAMTA>
        </DSPCLDRAMT>
        <DSPCLCRAMT>
            <DSPCLCRAMTA></DSPCLCRAMTA>
        </DSPCLCRAMT>
    </DSPACCINFO>
</ENVELOPE>
```

#### Error Responses

- **Unknown report name** (🟡 Illustrative): an `id` that is not a TDL report name returns an error or an empty envelope. Use the exact Report IDs in [§5](#5-reports).
- **Period outside books** returns zero rows, not an error. Validate `svFromDate` ≤ `svToDate` yourself.
- [Common errors](#110-common-error-responses) apply.

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `export` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `data` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `Trial Balance` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svExportFormat]` | `<STATICVARIABLES><SVEXPORTFORMAT>` | Yes (export) | String | `jsonex` | Response format: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `static_variables[name=svFromDate]` | `<STATICVARIABLES><SVFROMDATE>` | Cond. | Date (YYYYMMDD) | `20250401` | Report period start. |
| `static_variables[name=svToDate]` | `<STATICVARIABLES><SVTODATE>` | Cond. | Date (YYYYMMDD) | `20250430` | Report period end. |
| `static_variables[name=IsLedgerwise]` | `<STATICVARIABLES><ISLEDGERWISE>` | No | Logical | `Yes` | Trial Balance only: list ledgers instead of groups. |

### 5.1.6 Pull Trial Balance for a Group

> Explorer id: `pull-trial-balance-group` · Kind: **report** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#pull-trial-balance-group)

#### Description

Any report in TallyPrime can be fetched using its TDL Report Name as a unique identifier. To fetch Trial Balance, the TDL report name - Trial Balance is specified in the &lt;ID&gt; tag (XML) or id HTTP header (JSON). To fetch Trial Balance for a Group, the report is modified with the report variable GroupName set to the required group name and sent in the tdlmessage section of the request.

**Integration use:** Balances for one group only (e.g. Bank Accounts) for a focused widget or check.

**Notes:**

- The XML sample modifies the report with `<ADD>SET: Groupname :"Bank Accounts"</ADD>` on `NAME="TrialBalance"`. This is the same report, because TDL names ignore spaces.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svExportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVEXPORTFORMAT>XML</SVEXPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `export` | Yes |
| `type` | `data` | Yes |
| `id` | `Trial Balance` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    },
    {
      "name": "svFromDate",
      "value": "20250401"
    },
    {
      "name": "svToDate",
      "value": "20250430"
    }
  ],
  "tdlmessage": [
    {
      "definitions": [
        {
          "metadata": {
            "name": "Trial Balance",
            "type": "Report",
            "ismodify": true
          },
          "attributes": [
            {
              "Set": "Groupname :\"Bank Accounts\""
            }
          ]
        }
      ]
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Data</TYPE>
    <ID>Trial Balance</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>
        <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
        <SVFROMDATE>20250401</SVFROMDATE>
        <SVTODATE>20250430</SVTODATE>
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <REPORT NAME="TrialBalance" ISMODIFY="Yes">
            <ADD>SET: Groupname :"Bank Accounts"</ADD>
          </REPORT>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: export" \
  -H "type: data" \
  -H "id: Trial Balance" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟡 Illustrative: JSONEx output lowercases the report's XML tags and wraps repeated lines in arrays named after the report's Form → Part → Line structure, see the official Balance Sheet sample in [§1.9](#19-response-structure). Find rows by looking for objects that contain `dspaccname`/`dspaccinfo`; `<line-array>` stands for that array name):

```json
{
    "status": "1",
    "data": {
        "<line-array>": [
            {
                "dspaccname": {
                    "dspdispname": "Kotak Bank"
                },
                "dspaccinfo": {
                    "dspcldramt": {
                        "dspcldramta": -312450
                    }
                }
            },
            {
                "dspaccname": {
                    "dspdispname": "Bank of Baroda"
                },
                "dspaccinfo": {
                    "dspcldramt": {
                        "dspcldramta": -206300
                    }
                }
            }
        ]
    }
}
```

**Success — XML** (🟡 Illustrative: classic report XML has no `HEADER/STATUS` wrapper, just the report's display tags in order; Debit amounts are negative):

```xml
<ENVELOPE>
    <DSPACCNAME>
        <DSPDISPNAME>Kotak Bank</DSPDISPNAME>
    </DSPACCNAME>
    <DSPACCINFO>
        <DSPCLDRAMT>
            <DSPCLDRAMTA>-312450.00</DSPCLDRAMTA>
        </DSPCLDRAMT>
        <DSPCLCRAMT>
            <DSPCLCRAMTA></DSPCLCRAMTA>
        </DSPCLCRAMT>
    </DSPACCINFO>
    <DSPACCNAME>
        <DSPDISPNAME>Bank of Baroda</DSPDISPNAME>
    </DSPACCNAME>
    <DSPACCINFO>
        <DSPCLDRAMT>
            <DSPCLDRAMTA>-206300.00</DSPCLDRAMTA>
        </DSPCLDRAMT>
        <DSPCLCRAMT>
            <DSPCLCRAMTA></DSPCLCRAMTA>
        </DSPCLCRAMT>
    </DSPACCINFO>
</ENVELOPE>
```

#### Error Responses

- **Unknown report name** (🟡 Illustrative): an `id` that is not a TDL report name returns an error or an empty envelope. Use the exact Report IDs in [§5](#5-reports).
- **Period outside books** returns zero rows, not an error. Validate `svFromDate` ≤ `svToDate` yourself.
- [Common errors](#110-common-error-responses) apply.

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `export` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `data` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `Trial Balance` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svExportFormat]` | `<STATICVARIABLES><SVEXPORTFORMAT>` | Yes (export) | String | `jsonex` | Response format: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `static_variables[name=svFromDate]` | `<STATICVARIABLES><SVFROMDATE>` | Cond. | Date (YYYYMMDD) | `20250401` | Report period start. |
| `static_variables[name=svToDate]` | `<STATICVARIABLES><SVTODATE>` | Cond. | Date (YYYYMMDD) | `20250430` | Report period end. |
| `tdlmessage[]` | `<TDL><TDLMESSAGE>` | Cond. | Array<Object> |  | Inline TDL definitions (Collection / Report modification / System Formulae) that Tally loads before executing the request. |
| `tdlmessage[].definitions[]` | `<REPORT …>` | Cond. | Array<Object> |  | List of TDL definitions inside `tdlmessage`. |
| `tdlmessage[].definitions[].metadata.name` | `NAME` attribute | Yes | String | `Trial Balance` | Definition name. For a Collection it must match the `id` header / `<ID>`. TDL names are case- and space-insensitive. |
| `tdlmessage[].definitions[].metadata.type` | element name | Yes | String | `Report` | Definition kind: `Collection`, `Report`, or `System`. |
| `tdlmessage[].definitions[].metadata.ismodify` | `ISMODIFY` attribute | No | Boolean | `true` | `true` modifies an existing (default) definition instead of declaring a new one (`#` / `ISMODIFY="Yes"` in XML). |
| `tdlmessage[].definitions[].attributes[].Set` | `<SET>` | No | String (TDL) | `Groupname :"Bank Accounts"` | Report attribute that sets a report variable, e.g. `Groupname : "Bank Accounts"`. |

## 5.2 Sales Register

### 5.2.0 Sales Register — Overview & Field Reference

> 🟢 Official: converted from the Explorer's "About Sales Register" page.

Sales Register is a transaction-based report that displays all sales vouchers recorded during a specified period. It provides a consolidated view of sales activity, helping businesses track revenue, customer transactions, taxes, and item-wise sales details.

In TallyPrime API Explorer, the Sales Register report enables programmatic access to sales data for analysis, reporting, and integration purposes.

This report is commonly used to:

- Monitor sales transactions
- Analyze customer-wise or item-wise sales
- Track tax and GST details
- Reconcile invoices and revenue
- Generate MIS and sales analytics reports

Sales Register supports:

- Date-based filtering
- Voucher-type filtering
- Drill-down into voucher details
- Export in XML and JSON formats

It is widely used in integrations involving:

- Sales dashboards
- GST and tax reporting
- ERP and CRM synchronization
- Business intelligence and analytics systems

### 5.2.1 Pull Sales Register for any Period

> Explorer id: `pull-sales-register-period` · Kind: **report** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#pull-sales-register-period)

#### Description

Any report in TallyPrime can be fetched using its TDL Report Name as a unique identifier. To fetch Sales Register, the TDL report name – Sales Register is specified in the &lt;ID&gt; tag (XML) or id HTTP header (JSON). The report period is defined using SVFromDate and SVToDate in the static variables section.

**Integration use:** Month-wise sales totals for revenue dashboards and GST sanity checks.

**Notes:**

- Change `id` to `Purchase Register`, `Payment Register`, `Receipts Register`, `Journal Register`, etc. to fetch the other registers with the same body.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svExportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVEXPORTFORMAT>XML</SVEXPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `export` | Yes |
| `type` | `data` | Yes |
| `id` | `Sales Register` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    },
    {
      "name": "svFromDate",
      "value": "20250401"
    },
    {
      "name": "svToDate",
      "value": "20260331"
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Data</TYPE>
    <ID>Sales Register</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>
        <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
        <SVFROMDATE>20250401</SVFROMDATE>
        <SVTODATE>20260331</SVTODATE>
      </STATICVARIABLES>
    </DESC>
  </BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: export" \
  -H "type: data" \
  -H "id: Sales Register" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟡 Illustrative: JSONEx output lowercases the report's XML tags and wraps repeated lines in arrays named after the report's Form → Part → Line structure, see the official Balance Sheet sample in [§1.9](#19-response-structure). Find rows by looking for objects that contain `dspaccname`/`dspaccinfo`; `<line-array>` stands for that array name):

```json
{
    "status": "1",
    "data": {
        "<line-array>": [
            {
                "dspperiod": "April",
                "dspaccinfo": {
                    "dspcramt": {
                        "dspcramta": 126500
                    },
                    "dspclamt": {
                        "dspclamta": -126500
                    }
                }
            },
            {
                "dspperiod": "May",
                "dspaccinfo": {
                    "dspcramt": {
                        "dspcramta": 98250
                    },
                    "dspclamt": {
                        "dspclamta": -98250
                    }
                }
            },
            {
                "dspperiod": "June",
                "dspaccinfo": {
                    "dspcramt": {
                        "dspcramta": 143700
                    },
                    "dspclamt": {
                        "dspclamta": -143700
                    }
                }
            }
        ]
    }
}
```

**Success — XML** (🟡 Illustrative: classic report XML has no `HEADER/STATUS` wrapper, just the report's display tags in order; Debit amounts are negative):

```xml
<ENVELOPE>
    <DSPPERIOD>April</DSPPERIOD>
    <DSPACCINFO>
        <DSPDRAMT>
            <DSPDRAMTA></DSPDRAMTA>
        </DSPDRAMT>
        <DSPCRAMT>
            <DSPCRAMTA>126500.00</DSPCRAMTA>
        </DSPCRAMT>
        <DSPCLAMT>
            <DSPCLAMTA>-126500.00</DSPCLAMTA>
        </DSPCLAMT>
    </DSPACCINFO>
    <DSPPERIOD>May</DSPPERIOD>
    <DSPACCINFO>
        <DSPDRAMT>
            <DSPDRAMTA></DSPDRAMTA>
        </DSPDRAMT>
        <DSPCRAMT>
            <DSPCRAMTA>98250.00</DSPCRAMTA>
        </DSPCRAMT>
        <DSPCLAMT>
            <DSPCLAMTA>-98250.00</DSPCLAMTA>
        </DSPCLAMT>
    </DSPACCINFO>
    <DSPPERIOD>June</DSPPERIOD>
    <DSPACCINFO>
        <DSPDRAMT>
            <DSPDRAMTA></DSPDRAMTA>
        </DSPDRAMT>
        <DSPCRAMT>
            <DSPCRAMTA>143700.00</DSPCRAMTA>
        </DSPCRAMT>
        <DSPCLAMT>
            <DSPCLAMTA>-143700.00</DSPCLAMTA>
        </DSPCLAMT>
    </DSPACCINFO>
</ENVELOPE>
```

#### Error Responses

- **Unknown report name** (🟡 Illustrative): an `id` that is not a TDL report name returns an error or an empty envelope. Use the exact Report IDs in [§5](#5-reports).
- **Period outside books** returns zero rows, not an error. Validate `svFromDate` ≤ `svToDate` yourself.
- [Common errors](#110-common-error-responses) apply.

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `export` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `data` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `Sales Register` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svExportFormat]` | `<STATICVARIABLES><SVEXPORTFORMAT>` | Yes (export) | String | `jsonex` | Response format: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `static_variables[name=svFromDate]` | `<STATICVARIABLES><SVFROMDATE>` | Cond. | Date (YYYYMMDD) | `20250401` | Report period start. |
| `static_variables[name=svToDate]` | `<STATICVARIABLES><SVTODATE>` | Cond. | Date (YYYYMMDD) | `20260331` | Report period end. |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Fetch the report Purchase Register from TallyPrime for the period April to December 2025 | TDL Report name is Purchase Register. Set the variables svFromDate and svToDate appropriately | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/sales-register/any-period/json/TaskFetchPurchaseRegisterAprDecJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/sales-register/any-period/xml/TaskFetchPurchaseRegisterAprDecXML.txt) |

### 5.2.2 Pull Sales Register Plain Format

> Explorer id: `pull-sales-register-plain` · Kind: **report** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#pull-sales-register-plain)

#### Description

Any report in TallyPrime can be fetched using its TDL Report Name as a unique identifier. To fetch Sales Register, the TDL report name – Sales Register is specified in the &lt;ID&gt; tag (XML) or id HTTP header (JSON). Plain format of report is defined by the Logical Report attribute Plain XML/Plain JSON. Report to be fetched is modified with this attribute set to yes and sent in the tdlmessage section of the request.

**Integration use:** Flat Sales Register output for simpler parsing.

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svExportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVEXPORTFORMAT>XML</SVEXPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `export` | Yes |
| `type` | `data` | Yes |
| `id` | `Sales Register` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    },
    {
      "name": "svFromDate",
      "value": "20250401"
    },
    {
      "name": "svToDate",
      "value": "20260331"
    }
  ],
  "tdlmessage": [
    {
      "definitions": [
        {
          "metadata": {
            "name": "Sales Register",
            "type": "Report",
            "ismodify": true
          },
          "attributes": [
            {
              "Plain Xml": "Yes"
            }
          ]
        }
      ]
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Data</TYPE>
    <ID>Sales Register</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>
        <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
        <SVFROMDATE>20250401</SVFROMDATE>
        <SVTODATE>20260331</SVTODATE>
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <REPORT NAME="Sales Register" ISMODIFY="Yes" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
            <PLAINXML>Yes</PLAINXML>
          </REPORT>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: export" \
  -H "type: data" \
  -H "id: Sales Register" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟡 Illustrative: JSONEx output lowercases the report's XML tags and wraps repeated lines in arrays named after the report's Form → Part → Line structure, see the official Balance Sheet sample in [§1.9](#19-response-structure). Find rows by looking for objects that contain `dspaccname`/`dspaccinfo`; `<line-array>` stands for that array name):

```json
{
    "status": "1",
    "data": {
        "<line-array>": [
            {
                "dspperiod": "April",
                "dspaccinfo": {
                    "dspcramt": {
                        "dspcramta": 126500
                    },
                    "dspclamt": {
                        "dspclamta": -126500
                    }
                }
            },
            {
                "dspperiod": "May",
                "dspaccinfo": {
                    "dspcramt": {
                        "dspcramta": 98250
                    },
                    "dspclamt": {
                        "dspclamta": -98250
                    }
                }
            },
            {
                "dspperiod": "June",
                "dspaccinfo": {
                    "dspcramt": {
                        "dspcramta": 143700
                    },
                    "dspclamt": {
                        "dspclamta": -143700
                    }
                }
            }
        ]
    }
}
```

**Success — XML** (🟡 Illustrative: classic report XML has no `HEADER/STATUS` wrapper, just the report's display tags in order; Debit amounts are negative):

```xml
<ENVELOPE>
    <DSPPERIOD>April</DSPPERIOD>
    <DSPACCINFO>
        <DSPDRAMT>
            <DSPDRAMTA></DSPDRAMTA>
        </DSPDRAMT>
        <DSPCRAMT>
            <DSPCRAMTA>126500.00</DSPCRAMTA>
        </DSPCRAMT>
        <DSPCLAMT>
            <DSPCLAMTA>-126500.00</DSPCLAMTA>
        </DSPCLAMT>
    </DSPACCINFO>
    <DSPPERIOD>May</DSPPERIOD>
    <DSPACCINFO>
        <DSPDRAMT>
            <DSPDRAMTA></DSPDRAMTA>
        </DSPDRAMT>
        <DSPCRAMT>
            <DSPCRAMTA>98250.00</DSPCRAMTA>
        </DSPCRAMT>
        <DSPCLAMT>
            <DSPCLAMTA>-98250.00</DSPCLAMTA>
        </DSPCLAMT>
    </DSPACCINFO>
    <DSPPERIOD>June</DSPPERIOD>
    <DSPACCINFO>
        <DSPDRAMT>
            <DSPDRAMTA></DSPDRAMTA>
        </DSPDRAMT>
        <DSPCRAMT>
            <DSPCRAMTA>143700.00</DSPCRAMTA>
        </DSPCRAMT>
        <DSPCLAMT>
            <DSPCLAMTA>-143700.00</DSPCLAMTA>
        </DSPCLAMT>
    </DSPACCINFO>
</ENVELOPE>
```

#### Error Responses

- **Unknown report name** (🟡 Illustrative): an `id` that is not a TDL report name returns an error or an empty envelope. Use the exact Report IDs in [§5](#5-reports).
- **Period outside books** returns zero rows, not an error. Validate `svFromDate` ≤ `svToDate` yourself.
- [Common errors](#110-common-error-responses) apply.

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `export` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `data` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `Sales Register` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svExportFormat]` | `<STATICVARIABLES><SVEXPORTFORMAT>` | Yes (export) | String | `jsonex` | Response format: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `static_variables[name=svFromDate]` | `<STATICVARIABLES><SVFROMDATE>` | Cond. | Date (YYYYMMDD) | `20250401` | Report period start. |
| `static_variables[name=svToDate]` | `<STATICVARIABLES><SVTODATE>` | Cond. | Date (YYYYMMDD) | `20260331` | Report period end. |
| `tdlmessage[]` | `<TDL><TDLMESSAGE>` | Cond. | Array<Object> |  | Inline TDL definitions (Collection / Report modification / System Formulae) that Tally loads before executing the request. |
| `tdlmessage[].definitions[]` | `<REPORT …>` | Cond. | Array<Object> |  | List of TDL definitions inside `tdlmessage`. |
| `tdlmessage[].definitions[].metadata.name` | `NAME` attribute | Yes | String | `Sales Register` | Definition name. For a Collection it must match the `id` header / `<ID>`. TDL names are case- and space-insensitive. |
| `tdlmessage[].definitions[].metadata.type` | element name | Yes | String | `Report` | Definition kind: `Collection`, `Report`, or `System`. |
| `tdlmessage[].definitions[].metadata.ismodify` | `ISMODIFY` attribute | No | Boolean | `true` | `true` modifies an existing (default) definition instead of declaring a new one (`#` / `ISMODIFY="Yes"` in XML). |
| `tdlmessage[].definitions[].attributes[].Plain Xml` | `<PLAINXML>` | No | Logical | `Yes` | Report attribute. `Yes` returns the report in plain (flat) XML/JSON. |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Fetch the report Purchase Register from TallyPrime in plain format | TDL Report name is Purchase Register | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/sales-register/plain-format/json/TaskFetchPurchaseRegisterPlainJSON.txt) · [XML](https://tallysolutions.com/tallyprime-api-explorer/files/sales-register/plain-format/xml/TaskFetchPurchaseRegisterPlainXML.txt) |

### 5.2.3 Pull Sales Register with Empty Fields

> Explorer id: `pull-sales-register-empty-fields` · Kind: **report** · [Open in API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#pull-sales-register-empty-fields)

#### Description

Any report in TallyPrime can be fetched using its TDL Report Name as a unique identifier. To fetch Sales Register, the TDL report name – Sales Register is specified in the &lt;ID&gt; tag (XML) or id HTTP header (JSON). By default, XML responses include all tags (even those with empty values), whereas JSON responses include only tags with values. To include empty fields in JSON, the Export Empty Fields report attribute must be set to Yes by modifying the report in the tdlmessage section of the request. This attribute is applicable only for JSON, as XML by default includes all tags.

**Integration use:** Sales Register with a stable JSON schema (empty fields retained).

#### Supported Formats

| Format | Supported | Routing | Body format variable |
|---|---|---|---|
| JSON | ✅ TallyPrime 7.0+ | HTTP headers | `svExportFormat` = `jsonex` |
| XML | ✅ All TallyPrime releases | `<HEADER>` inside the envelope | `<SVEXPORTFORMAT>XML</SVEXPORTFORMAT>` |

#### Request Structure

| | JSON | XML |
|---|---|---|
| HTTP method | `POST` | `POST` |
| Endpoint URL | `http://<tally-host>:9000/` | `http://<tally-host>:9000/` |
| Content-Type | `application/json` | `text/xml` (recommended; Tally reads the body regardless) |
| Routing info | Headers below | `<HEADER>` block in the body |

**Required headers (JSON):**

| Header | Value | Required |
|---|---|---|
| `content-type` | `application/json` | Yes |
| `version` | `1` | Yes |
| `tallyrequest` | `export` | Yes |
| `type` | `data` | Yes |
| `id` | `Sales Register` | Yes |

XML requests carry no Tally-specific HTTP headers; the same values are in `<HEADER>` (`<VERSION>`, `<TALLYREQUEST>`, `<TYPE>`, `<ID>`).

**Request body — JSON** (🟢 Official, verbatim from the Explorer):

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    },
    {
      "name": "svFromDate",
      "value": "20250401"
    },
    {
      "name": "svToDate",
      "value": "20260331"
    }
  ],
  "tdlmessage": [
    {
      "definitions": [
        {
          "metadata": {
            "name": "Sales Register",
            "type": "Report",
            "ismodify": true
          },
          "attributes": [
            {
              "Export Empty Fields": "Yes"
            }
          ]
        }
      ]
    }
  ]
}
```

**Request body — XML** (🟢 Official, verbatim from the Explorer):

```xml
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Data</TYPE>
    <ID>Sales Register</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>
        <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
        <SVFROMDATE>20250401</SVFROMDATE>
        <SVTODATE>20260331</SVTODATE>
      </STATICVARIABLES>
    </DESC>
  </BODY>
</ENVELOPE>
```

**cURL (JSON):**

```bash
curl -s -X POST "http://localhost:9000/" \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: export" \
  -H "type: data" \
  -H "id: Sales Register" \
  --data-binary @request.json
```

#### Response Structure

**Success — JSON** (🟡 Illustrative: JSONEx output lowercases the report's XML tags and wraps repeated lines in arrays named after the report's Form → Part → Line structure, see the official Balance Sheet sample in [§1.9](#19-response-structure). Find rows by looking for objects that contain `dspaccname`/`dspaccinfo`; `<line-array>` stands for that array name):

```json
{
    "status": "1",
    "data": {
        "<line-array>": [
            {
                "dspperiod": "April",
                "dspaccinfo": {
                    "dspcramt": {
                        "dspcramta": 126500
                    },
                    "dspclamt": {
                        "dspclamta": -126500
                    },
                    "dspdramt": {
                        "dspdramta": ""
                    }
                }
            },
            {
                "dspperiod": "May",
                "dspaccinfo": {
                    "dspcramt": {
                        "dspcramta": 98250
                    },
                    "dspclamt": {
                        "dspclamta": -98250
                    },
                    "dspdramt": {
                        "dspdramta": ""
                    }
                }
            },
            {
                "dspperiod": "June",
                "dspaccinfo": {
                    "dspcramt": {
                        "dspcramta": 143700
                    },
                    "dspclamt": {
                        "dspclamta": -143700
                    },
                    "dspdramt": {
                        "dspdramta": ""
                    }
                }
            }
        ]
    }
}
```

**Success — XML** (🟡 Illustrative: classic report XML has no `HEADER/STATUS` wrapper, just the report's display tags in order; Debit amounts are negative):

```xml
<ENVELOPE>
    <DSPPERIOD>April</DSPPERIOD>
    <DSPACCINFO>
        <DSPDRAMT>
            <DSPDRAMTA></DSPDRAMTA>
        </DSPDRAMT>
        <DSPCRAMT>
            <DSPCRAMTA>126500.00</DSPCRAMTA>
        </DSPCRAMT>
        <DSPCLAMT>
            <DSPCLAMTA>-126500.00</DSPCLAMTA>
        </DSPCLAMT>
    </DSPACCINFO>
    <DSPPERIOD>May</DSPPERIOD>
    <DSPACCINFO>
        <DSPDRAMT>
            <DSPDRAMTA></DSPDRAMTA>
        </DSPDRAMT>
        <DSPCRAMT>
            <DSPCRAMTA>98250.00</DSPCRAMTA>
        </DSPCRAMT>
        <DSPCLAMT>
            <DSPCLAMTA>-98250.00</DSPCLAMTA>
        </DSPCLAMT>
    </DSPACCINFO>
    <DSPPERIOD>June</DSPPERIOD>
    <DSPACCINFO>
        <DSPDRAMT>
            <DSPDRAMTA></DSPDRAMTA>
        </DSPDRAMT>
        <DSPCRAMT>
            <DSPCRAMTA>143700.00</DSPCRAMTA>
        </DSPCRAMT>
        <DSPCLAMT>
            <DSPCLAMTA>-143700.00</DSPCLAMTA>
        </DSPCLAMT>
    </DSPACCINFO>
</ENVELOPE>
```

#### Error Responses

- **Unknown report name** (🟡 Illustrative): an `id` that is not a TDL report name returns an error or an empty envelope. Use the exact Report IDs in [§5](#5-reports).
- **Period outside books** returns zero rows, not an error. Validate `svFromDate` ≤ `svToDate` yourself.
- [Common errors](#110-common-error-responses) apply.

#### Data Dictionary

| Parameter (JSON) | XML equivalent | Required | Data type | Example | Description |
|---|---|---|---|---|---|
| `header: content-type` | n/a (`Content-Type: text/xml`) | Yes | String | `application/json` | `application/json` (add `;charset=utf-8` or `;charset=utf-16` for multilingual data; Tally then replies in UTF-16). |
| `header: version` | `<HEADER><VERSION>` | Yes | Number | `1` | Protocol version. Always `1`. |
| `header: tallyrequest` | `<HEADER><TALLYREQUEST>` | Yes | String | `export` | `Import` (post data) or `Export` (fetch data). |
| `header: type` | `<HEADER><TYPE>` | Yes | String | `data` | `Data` (imports & reports), `Collection`, `Object`, or `Function`. |
| `header: id` | `<HEADER><ID>` | Yes | String | `Sales Register` | Target: `All Masters` / `Vouchers` for imports, collection name, object name, or report name. |
| `static_variables[name=svExportFormat]` | `<STATICVARIABLES><SVEXPORTFORMAT>` | Yes (export) | String | `jsonex` | Response format: `jsonex` (JSON) / `XML`. |
| `static_variables[name=svCurrentCompany]` | `<STATICVARIABLES><SVCURRENTCOMPANY>` | Yes | String | `Bhrama Enterprises` | Exact name of a company loaded in TallyPrime. Without it the active company is used, which risks writing to the wrong company. |
| `static_variables[name=svFromDate]` | `<STATICVARIABLES><SVFROMDATE>` | Cond. | Date (YYYYMMDD) | `20250401` | Report period start. |
| `static_variables[name=svToDate]` | `<STATICVARIABLES><SVTODATE>` | Cond. | Date (YYYYMMDD) | `20260331` | Report period end. |
| `tdlmessage[]` | `<TDL><TDLMESSAGE>` | Cond. | Array<Object> |  | Inline TDL definitions (Collection / Report modification / System Formulae) that Tally loads before executing the request. |
| `tdlmessage[].definitions[]` | `<REPORT …>` | Cond. | Array<Object> |  | List of TDL definitions inside `tdlmessage`. |
| `tdlmessage[].definitions[].metadata.name` | `NAME` attribute | Yes | String | `Sales Register` | Definition name. For a Collection it must match the `id` header / `<ID>`. TDL names are case- and space-insensitive. |
| `tdlmessage[].definitions[].metadata.type` | element name | Yes | String | `Report` | Definition kind: `Collection`, `Report`, or `System`. |
| `tdlmessage[].definitions[].metadata.ismodify` | `ISMODIFY` attribute | No | Boolean | `true` | `true` modifies an existing (default) definition instead of declaring a new one (`#` / `ISMODIFY="Yes"` in XML). |
| `tdlmessage[].definitions[].attributes[].Export Empty Fields` | `<EXPORTEMPTYFIELDS>` | No | Logical | `Yes` | Report attribute (JSON only). `Yes` keeps empty fields in the JSON response; XML always includes them. |

#### Hands-on Variations (from the Explorer)

| Exercise | Hint | Solution files |
|---|---|---|
| Fetch the report Purchase Register from TallyPrime with empty fields | TDL Report name is Purchase Register | [JSON](https://tallysolutions.com/tallyprime-api-explorer/files/sales-register/empty-fields/json/TaskFetchPurchaseRegisterEmptyJSON.txt) |

# Appendix A. API Index

| # | API | Kind | tallyrequest | type | id |
|---|---|---|---|---|---|
| 2.1.1 | [Create a Ledger](#211-create-a-ledger) | import | `import` | `data` | `All Masters` |
| 2.1.2 | [Alter a Ledger](#212-alter-a-ledger) | import | `import` | `data` | `All Masters` |
| 2.1.3 | [Delete a Ledger](#213-delete-a-ledger) | import | `import` | `data` | `All Masters` |
| 2.1.4 | [Pull a Ledger](#214-pull-a-ledger) | object | `export` | `object` | `Kotak Bank` |
| 2.1.5 | [Pull All Ledgers](#215-pull-all-ledgers) | collection | `export` | `collection` | `Ledger` |
| 2.1.6 | [Pull Ledgers of Group](#216-pull-ledgers-of-group) | collection | `export` | `collection` | `TSPLBankLedgers` |
| 2.2.1 | [Create a Group](#221-create-a-group) | import | `import` | `data` | `All Masters` |
| 2.2.2 | [Alter a Group](#222-alter-a-group) | import | `import` | `data` | `All Masters` |
| 2.2.3 | [Delete a Group](#223-delete-a-group) | import | `import` | `data` | `All Masters` |
| 2.2.4 | [Pull a Group](#224-pull-a-group) | object | `export` | `object` | `Bank Accounts` |
| 2.2.5 | [Pull All Groups](#225-pull-all-groups) | collection | `export` | `collection` | `Group` |
| 2.2.6 | [Pull Groups of Group](#226-pull-groups-of-group) | collection | `export` | `collection` | `TSPLAssetGroups` |
| 3.1.1 | [Create a Stock Item](#311-create-a-stock-item) | import | `import` | `data` | `All Masters` |
| 3.1.2 | [Alter a Stock Item](#312-alter-a-stock-item) | import | `import` | `data` | `All Masters` |
| 3.1.3 | [Delete a Stock Item](#313-delete-a-stock-item) | import | `import` | `data` | `All Masters` |
| 3.1.4 | [Pull a Stock Item](#314-pull-a-stock-item) | object | `export` | `object` | `Coffee Powder` |
| 3.1.5 | [Pull All Stock Item](#315-pull-all-stock-item) | collection | `export` | `collection` | `Stock Item` |
| 3.1.6 | [Pull Stock Items of Stock Group](#316-pull-stock-items-of-stock-group) | collection | `export` | `collection` | `TSPLStockOfGroup` |
| 3.2.1 | [Create a Stock Group](#321-create-a-stock-group) | import | `import` | `data` | `All Masters` |
| 3.2.2 | [Alter a Stock Group](#322-alter-a-stock-group) | import | `import` | `data` | `All Masters` |
| 3.2.3 | [Delete a Stock Group](#323-delete-a-stock-group) | import | `import` | `data` | `All Masters` |
| 3.2.4 | [Pull a Stock Group](#324-pull-a-stock-group) | object | `export` | `object` | `Laptops` |
| 3.2.5 | [Pull All Stock Groups](#325-pull-all-stock-groups) | collection | `export` | `collection` | `Stock Group` |
| 3.2.6 | [Pull Stock Group With Zero Balance](#326-pull-stock-group-with-zero-balance) | collection | `export` | `collection` | `TSPL Stock Group ZeroBal` |
| 3.3.1 | [Create a Simple Unit](#331-create-a-simple-unit) | import | `import` | `data` | `All Masters` |
| 3.3.2 | [Create a Compound Unit](#332-create-a-compound-unit) | import | `import` | `data` | `All Masters` |
| 3.3.3 | [Alter a Unit](#333-alter-a-unit) | import | `import` | `data` | `All Masters` |
| 3.3.4 | [Delete a Unit](#334-delete-a-unit) | import | `import` | `data` | `All Masters` |
| 3.3.5 | [Pull a Unit](#335-pull-a-unit) | object | `export` | `object` | `Nos` |
| 3.3.6 | [Pull all Units](#336-pull-all-units) | collection | `export` | `collection` | `Unit` |
| 4.1.1 | [Create a Payment with Banking details](#411-create-a-payment-with-banking-details) | import | `import` | `data` | `Vouchers` |
| 4.1.2 | [Create a Payment with Cash](#412-create-a-payment-with-cash) | import | `import` | `data` | `Vouchers` |
| 4.1.3 | [Alter a Payment](#413-alter-a-payment) | import | `import` | `data` | `Vouchers` |
| 4.1.4 | [Delete a Payment](#414-delete-a-payment) | import | `import` | `data` | `Vouchers` |
| 4.1.5 | [Pull all Payment vouchers](#415-pull-all-payment-vouchers) | collection | `export` | `collection` | `TSPLAllPaymentVouchers` |
| 4.1.6 | [Pull all Payment vouchers for a period](#416-pull-all-payment-vouchers-for-a-period) | collection | `export` | `collection` | `TSPLPaymentVouchers` |
| 4.2.1 | [Create a Receipt with Banking Details](#421-create-a-receipt-with-banking-details) | import | `import` | `data` | `Vouchers` |
| 4.2.2 | [Create a Receipt with Cash Details](#422-create-a-receipt-with-cash-details) | import | `import` | `data` | `Vouchers` |
| 4.2.3 | [Alter a Receipt](#423-alter-a-receipt) | import | `import` | `data` | `Vouchers` |
| 4.2.4 | [Delete a Receipt](#424-delete-a-receipt) | import | `import` | `data` | `Vouchers` |
| 4.2.5 | [Pull all Receipt vouchers](#425-pull-all-receipt-vouchers) | collection | `export` | `collection` | `TSPL All Receipt Vouchers` |
| 4.2.6 | [Pull all Receipt vouchers for a period](#426-pull-all-receipt-vouchers-for-a-period) | collection | `export` | `collection` | `TSPL Receipt Vouchers` |
| 4.3.1 | [Create Sales with Item](#431-create-sales-with-item) | import | `import` | `data` | `Vouchers` |
| 4.3.2 | [Create Sales with GST](#432-create-sales-with-gst) | import | `import` | `data` | `Vouchers` |
| 4.3.3 | [Alter a Sales](#433-alter-a-sales) | import | `import` | `data` | `Vouchers` |
| 4.3.4 | [Delete a Sales](#434-delete-a-sales) | import | `import` | `data` | `Vouchers` |
| 4.3.5 | [Pull all Sales vouchers](#435-pull-all-sales-vouchers) | collection | `export` | `collection` | `TSPLAllSalesVouchers` |
| 4.3.6 | [Pull all Sales vouchers for a period](#436-pull-all-sales-vouchers-for-a-period) | collection | `export` | `collection` | `TSPLSalesVouchers` |
| 4.4.1 | [Create Purchase with Item](#441-create-purchase-with-item) | import | `import` | `data` | `Vouchers` |
| 4.4.2 | [Create Purchase with GST](#442-create-purchase-with-gst) | import | `import` | `data` | `Vouchers` |
| 4.4.3 | [Alter a Purchase](#443-alter-a-purchase) | import | `import` | `data` | `Vouchers` |
| 4.4.4 | [Delete a Purchase](#444-delete-a-purchase) | import | `import` | `data` | `Vouchers` |
| 4.4.5 | [Pull all Purchase vouchers](#445-pull-all-purchase-vouchers) | collection | `export` | `collection` | `TSPL All Purchase Vouchers` |
| 4.4.6 | [Pull all Purchase vouchers for a period](#446-pull-all-purchase-vouchers-for-a-period) | collection | `export` | `collection` | `TSPL Purchase Vouchers` |
| 5.1.1 | [Pull Trial Balance for any Period](#511-pull-trial-balance-for-any-period) | report | `export` | `data` | `Trial Balance` |
| 5.1.2 | [Pull Trial Balance Detailed](#512-pull-trial-balance-detailed) | report | `export` | `data` | `Trial Balance` |
| 5.1.3 | [Pull Trial Balance Plain Format](#513-pull-trial-balance-plain-format) | report | `export` | `data` | `Trial Balance` |
| 5.1.4 | [Pull Trial Balance with Empty Fields](#514-pull-trial-balance-with-empty-fields) | report | `export` | `data` | `Trial Balance` |
| 5.1.5 | [Pull Trial Balance Ledger wise](#515-pull-trial-balance-ledger-wise) | report | `export` | `data` | `Trial Balance` |
| 5.1.6 | [Pull Trial Balance for a Group](#516-pull-trial-balance-for-a-group) | report | `export` | `data` | `Trial Balance` |
| 5.2.1 | [Pull Sales Register for any Period](#521-pull-sales-register-for-any-period) | report | `export` | `data` | `Sales Register` |
| 5.2.2 | [Pull Sales Register Plain Format](#522-pull-sales-register-plain-format) | report | `export` | `data` | `Sales Register` |
| 5.2.3 | [Pull Sales Register with Empty Fields](#523-pull-sales-register-with-empty-fields) | report | `export` | `data` | `Sales Register` |

# Appendix B. Mapping to the MyTally Codebase

| Concern | Where it lives today | Notes |
|---|---|---|
| Native JSON import payloads (`static_variables` + `tallymessage`) | `backend/app/routers/sync.py` | Matches this reference. |
| XML payload builder | `backend/app/services/tally_xml_builder.py` | Check it uses one envelope style ([§1.8](#18-xml-envelope-styles)). |
| Response parsing (`parse_tally_response_metrics`) | `backend/app/routers/sync.py` | Handles both XML counters/`LINEERROR` and JSON `import_result`. |
| Export (backup) queries | `backend/backup_module/tally_queries/*.xml` | XML collection exports ([§1.5](#15-request-type-matrix)). |
| Older JSON reference | `docs/TallyPrime_API_Reference.md` | Uses a non-native `ENVELOPE` JSON shape; superseded by this file. |
| Live-captured responses and errors | `docs/Tally_Vouchers_Integration_Guide.md`, `docs/Tally_Inventory_Integration_Guide.md`, `docs/TALLY_CRASH_PREVENTION_GUIDE.md` | Source of the 🔵 samples here. |

# Appendix C. Sources

- TallyPrime API Explorer: https://tallysolutions.com/tallyprime-api-explorer/ (payloads: `js/script.js`; pages: `pages/<id>.html`; hands-on files: `files/…`)
- How to Integrate with TallyPrime Using JSON: https://help.tallysolutions.com/tally-prime-integration-using-json-1/ (headers, body template, response template, sample responses)
- How to Use Import File Definition and Related Events (Response Report): https://help.tallysolutions.com/how-to-use-import-file-definition-and-related-events/
- Integration Methods and Technologies: https://help.tallysolutions.com/integration-methods-and-technologies/

