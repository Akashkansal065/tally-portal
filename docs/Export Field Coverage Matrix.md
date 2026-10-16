# Export field coverage matrix (WS-10)

What the agent asks Tally for (`desktop-sync-agent/tally_client.py`, `VOUCHER_FETCH` and the collection list in
`export_full_collections`) against what the importer reads (`backend/app/services/tally_xml_importer.py`), what is
stored, and what a test covers. In a Tally collection export only the fields listed in `FETCH` come back, so a tag
the importer reads but the fetch does not list is dead code in practice. Rule for this workstream: **request a
field only where the importer reads it and a column or table stores it.**

Legend: **Fetched** = in the agent's FETCH today · **Parsed** = the importer reads it · **Stored** = a column/table
holds it · **Test** = a fixture test covers the parsed value (before WS-10 / after).

Tag names are those the importer already reads; they were **not** verified against a real TallyPrime export.

## Voucher header

| Tag | Fetched | Parsed | Stored in | Action |
|---|---|---|---|---|
| GUID, MASTERID, REMOTEALTGUID, ALTERID, VOUCHERTYPENAME, VOUCHERNUMBER, DATE, NARRATION, PARTYLEDGERNAME, AMOUNT, ISCANCELLED, ISOPTIONAL | yes | yes | vouchers.* | none |
| ISPOSTDATED | no | yes | is_post_dated | **request** |
| EFFECTIVEDATE | no | yes | effective_date | **request** |
| REFERENCEDATE | no | yes | reference_date | **request** |
| REFERENCE | no | no | reference_number (column exists) | **parse + request** |
| PLACEOFSUPPLY | no | yes | place_of_supply | **request** |
| BASICBUYERNAME | no | yes | buyer_name | **request** |
| BASICBUYERADDRESS.LIST | no | yes | buyer_address | **request** |
| CONSIGNEEMAILINGNAME | no | yes | consignee_name | **request** |
| CONSIGNEEADDRESS.LIST | no | yes | consignee_address | **request** |
| BASICORDERREF | no | yes | order_reference | **request** |
| BASICSHIPDELIVERYNOTE | no | yes | despatch_doc_no | **request** |
| IRN, IRNACKNO, IRNACKDATE, IRNQRCODE | no | yes | irn, irn_ack_no, irn_ack_date, irn_qr_code | **request** |
| IRNCANCELLED, IRNCANCELDATE, IRNCANCELREASON, IRNIRPSOURCE | no | yes | irn_cancel_* , irn_source | **request** (kept out of the first fetch: not seen in TallyPrime exports of ordinary vouchers; see note) |
| EWAYBILLDETAILS.LIST | no | yes | eway_bills | **request** |
| ISINVOICE | no | no | is_invoice (column exists) | **parse + request** |
| PERSISTEDVIEW | no | no | persisted_view (column exists) | **parse + request** |
| PARTYGSTIN (voucher level) | no | no | none (GSTIN lives on the ledger) | not requested |
| Shipping fields (vehicle, transporter) | no | only inside EWAYBILLDETAILS.LIST | eway_bills | covered by EWAYBILLDETAILS.LIST |
| ALLLEDGERENTRIES.LIST, INVENTORYENTRIES.LIST, ALLINVENTORYENTRIES.LIST, INVENTORYENTRIESIN/OUT.LIST, ATTENDANCEENTRIES.*, CATEGORYENTRY.LIST | yes (whole lists) | yes | entries, inventory, bank/bill allocations, cost centres, attendance | none (nested tags come with a whole list) |

Note: entries that are fetched as whole lists include `BANKALLOCATIONS.LIST` with `BANKERSDATE` (WS-4) and
`BATCHALLOCATIONS.LIST` (WS-11).

## Ledger

| Tag | Fetched | Parsed | Stored in | Action |
|---|---|---|---|---|
| NAME, GUID, MASTERID, PARENT, ALTERID, PAYTYPE, OPENINGBALANCE, CLOSINGBALANCE, ADDRESS.LIST, STATENAME, PINCODE, LEDGERPHONE, INCOMETAXNUMBER, PARTYGSTIN, ISBILLWISEON, LEDGSTREGDETAILS.LIST, LEDMAILINGDETAILS.LIST | yes | yes | ledgers.* | none |
| CREDITLIMIT | no | yes | credit_limit | **request** |
| BILLCREDITPERIOD | no | yes | credit_period_days | **request** |
| LEDGERCONTACT, LEDGERMOBILE, EMAIL, EMAILCC, WEBSITE, LEDGERFAX | no | yes | contact_person, mobile, email, email_cc, website, fax | **request** |
| COUNTRYNAME | no | yes | country | **request** |
| TAXCLASSIFICATIONNAME | no | yes | tax_classification_name | **request** |
| LEDGERTYPE | no | yes | ledger_type | not requested (not a TallyPrime ledger field name; unverified) |
| TDSCATEGORY, LOWERDEDUCTION.LIST | no | yes | tds fields, ledger_tds_lower_deductions | **request** |
| MSMEREGISTRATIONDETAILS.LIST | no | yes | ledger_msme_details | **request** |
| HSNDETAILS.LIST | no | yes | hsn details | **request** |
| LEDMULTIADDRESSLIST.LIST | no | yes | ledger_addresses | **request** |
| MAILINGNAME.LIST, LANGUAGENAME.LIST | no | yes | alias / mailing name | **request** |
| Bank details (account no, IFSC), price level, cost centres on, affects stock | no | partly (bank via bank_details model) | ledger columns exist | not requested: the importer reads no tag for them |

## Stock item

| Tag | Fetched | Parsed | Stored in | Action |
|---|---|---|---|---|
| NAME, GUID, MASTERID, ALTERID, PARENT, CATEGORY, BASEUNITS, ADDITIONALUNITS, CONVERSION, DENOMINATOR, OPENINGBALANCE, OPENINGVALUE, OPENINGRATE, DESCRIPTION, NARRATION, ISBATCHWISEON, ISPERISHABLEON, IGNORENEGATIVESTOCK, COSTINGMETHOD, VALUATIONMETHOD, GSTTYPEOFSUPPLY, BATCHALLOCATIONS.LIST | yes | yes | stock_items.*, batches | none |
| HSNDETAILS.LIST (HSNCODE, HSNDESCRIPTION, TAXABILITY, rate details) | no | yes | hsn_code, gst_rate_percent, hsn details | **request** |
| GST rate list (GSTDETAILS.LIST) | no | partly (INFGSTHSNCODE, INFGSTIGSTRATE) | gst_rate_percent | **request** with HSNDETAILS.LIST |
| LANGUAGENAME.LIST (alias) | no | yes | alias | **request** |
| MRP list, MULTICOMPONENTLIST (BOM), FULLPRICELIST, reorder level, minimum order, standard cost/price lists, part number | no | **no** | columns exist for reorder_level, minimum_order_qty, standard_cost_price, standard_selling_price | **not requested**: needs importer parsing first (gap) |

## Other masters

| Object | Fetched | Parsed | Stored in | Action |
|---|---|---|---|---|
| Currency | **no** (no collection) | yes (`<CURRENCY>`: symbol, ISO code, decimals, millions, suffix, space, decimal symbol) | currencies | **add collection** (full passes only: no ALTERID filter) |
| Price Level | no | **no** | price_levels, stock_item_price_level_rates | **parse + add collection** (names only) |
| Unit UQC | no | no | no column | not requested (no storage) |
| Group, Voucher type, Stock group, UOM, Godown, Stock category, Cost category/centre, Attendance type | yes | yes | yes | none |

## Size and timing

`VOUCHERS_PER_RANGE` is 50 vouchers per date range. Each voucher gains the header fields above; the IRN QR
code is the largest (about 0.5-1 KB for an e-invoiced voucher) and `EWAYBILLDETAILS.LIST` a few hundred bytes. A
range of 50 vouchers grows by at most roughly 50 KB, well inside the 120 s per-range export timeout. Ledger and
stock-item exports gain small fixed fields per record; they are not split by range, so the per-collection timeout
(120 s, 2 retries) is the figure to watch for companies with tens of thousands of ledgers or items.
