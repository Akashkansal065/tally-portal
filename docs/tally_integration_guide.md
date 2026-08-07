# Complete Tally Prime Integration & Developer Reference Guide

This document serves as an exhaustive, production-grade technical reference manual for integrating **Tally Prime** with web portals, ERPs, CRMs, databases, and third-party applications (TPAs). It covers HTTP XML protocols, TDL specifications, TDL language architecture, ODBC, Voucher Numbering & GST series configurations, Inventory/Batch allocations, User-Defined Fields (UDFs), TallyPrime API Explorer, Register & Financial Report Exports, and error handling.

---

## Table of Contents
1. [Integration Architectural Modes](#1-integration-architectural-modes)
2. [Tally Connector & Developer Reference Architecture](#2-tally-connector--developer-reference-architecture)
3. [TallyPrime API Explorer & Operations Matrix](#3-tallyprime-api-explorer--operations-matrix)
4. [Accounting Masters Specification (Ledger, Group)](#4-accounting-masters-specification-ledger-group)
5. [Inventory Masters Specification (Stock Item, Stock Group, Units)](#5-inventory-masters-specification-stock-item-stock-group-units)
6. [Transactions Specification (Payment, Receipt, Sales, Purchase)](#6-transactions-specification-payment-receipt-sales-purchase)
7. [Reports Specification (Trial Balance & Sales Register)](#7-reports-specification-trial-balance--sales-register)
8. [Pulling Sales/Purchase Registers & Financial Reports](#8-pulling-salespurchase-registers--financial-reports)
9. [Handling Empty/Null Fields in Tally Response XML](#9-handling-emptynull-fields-in-tally-response-xml)
10. [Understanding Tally XML Tags Dictionary](#10-understanding-tally-xml-tags-dictionary)
11. [Company Profile Master Specification](#11-company-profile-master-specification)
12. [Inventory, Godown & Batch Allocations](#12-inventory-godown--batch-allocations)
13. [User Defined Fields (UDF) & Custom Namespaces](#13-user-defined-fields-udf--custom-namespaces)
14. [TDL Architecture & Language Components](#14-tdl-architecture--language-components)
15. [TDL Language Reference: Symbols, Data Types, Procedural Logic & Customization](#15-tdl-language-reference-symbols-data-types-procedural-logic--customization)
16. [TDL Developer FAQ & Debugging Guide](#16-tdl-developer-faq--debugging-guide)
17. [Voucher Numbering Methods, Series & GST Compliance](#17-voucher-numbering-methods-series--gst-compliance)
18. [Handling Duplicate or Incorrect Voucher Numbers](#18-handling-duplicate-or-incorrect-voucher-numbers)
19. [ODBC & Advanced TDL Capabilities](#19-odbc--advanced-tdl-capabilities)
20. [Developer Troubleshooting & Known Gotchas Cheat Sheet](#20-developer-troubleshooting--known-gotchas-cheat-sheet)

---

## 1. Integration Architectural Modes

Tally Prime supports three distinct modes of integration with external software systems:

### Mode A: Integration Initiated from Third-Party Applications (TPAs) *(Current System)*
- **Role of Tally Prime**: **HTTP Server** (default listening port: `9000`).
- **Role of Web Portal**: **HTTP Client**.
- **Mechanism**: Web Portal sends HTTP POST requests containing XML envelopes (`<TALLYREQUEST>Import Data</TALLYREQUEST>` or `<TALLYREQUEST>Export Data</TALLYREQUEST>`) to Tally's IP and port.
- **Use Cases**: Pushing vouchers, creating ledgers, altering company profile, pulling financial reports, and live dashboard sync.

### Mode B: Integration Initiated from Tally Prime
- **Role of Tally Prime**: **HTTP Client**.
- **Role of Web Portal**: **HTTP Server / REST API**.
- **Mechanism**: Tally Prime triggers outbound HTTP POST/GET requests (defined via TDL `Trigger` or `Collection` with `URL` attributes) to external web endpoints.
- **Use Cases**: Real-time webhook notifications when a voucher is created/altered in Tally Prime, fetching live currency conversion rates, WhatsApp integration, or Cloud e-Invoicing.

### Mode C: ODBC Integration (Database Access)
- **Role of Tally Prime**: **ODBC Server** and **ODBC Client**.
- **Mechanism**: External software queries Tally data via SQL statements using the Tally ODBC Driver. Conversely, Tally uses TDL SQL/ODBC collections to pull data from external relational databases (MySQL, MS SQL, PostgreSQL).

---

## 2. Tally Connector & Developer Reference Architecture

```
+------------------------+                  +------------------------+
|  Web Portal / REST API |                  |  Tally Prime Instance  |
|   (FastAPI / Next.js)  |                  |    (Port 9000 HTTP)    |
|                        |                  |                        |
|  [Outbound Sync Queue] |--(XML POST)----->|  [Tally Import Engine] |
|                        |                  |  - Master Import       |
|                        |                  |  - Voucher Import      |
|  [Inbound TDL Importer]|<--(XML Response)-|  [Tally TDL Engine]    |
+------------------------+                  +------------------------+
```

---

## 3. TallyPrime API Explorer & Operations Matrix

The **[TallyPrime API Explorer](https://tallysolutions.com/tallyprime-api-explorer/#tally-api-explorer)** is Tally Solutions' official interactive sandbox tool designed for developers to test, validate, and inspect API operations prior to production deployment.

### API Explorer Category & Operations Map

| Category | Module | Actions Supported | Primary XML Tags |
| :--- | :--- | :--- | :--- |
| **Accounting Masters** | **Ledger** | Create, Alter, Delete, Pull | `<LEDGER>`, `<NAME>`, `<PARENT>`, `<OPENINGBALANCE>`, `<GSTIN>` |
| | **Group** | Create, Alter, Delete, Pull | `<GROUP>`, `<NAME>`, `<PARENT>` |
| **Inventory Masters** | **Stock Item** | Create, Alter, Delete, Pull | `<STOCKITEM>`, `<NAME>`, `<PARENT>`, `<BASEUNITS>` |
| | **Stock Group** | Create, Alter, Delete, Pull | `<STOCKGROUP>`, `<NAME>`, `<PARENT>` |
| | **Units** | Create, Alter, Delete, Pull | `<UNIT>`, `<NAME>`, `<ISSIMPLEUNIT>` |
| **Transactions** | **Payment** | Create, Alter, Delete, Pull | `<VOUCHER VOUCHERTYPENAME="Payment">`, `<ALLLEDGERENTRIES.LIST>` |
| | **Receipt** | Create, Alter, Delete, Pull | `<VOUCHER VOUCHERTYPENAME="Receipt">`, `<ALLLEDGERENTRIES.LIST>` |
| | **Sales** | Create, Alter, Delete, Pull | `<VOUCHER VOUCHERTYPENAME="Sales">`, `<ALLINVENTORYENTRIES.LIST>` |
| | **Purchase** | Create, Alter, Delete, Pull | `<VOUCHER VOUCHERTYPENAME="Purchase">`, `<ALLINVENTORYENTRIES.LIST>` |
| **Reports** | **Trial Balance** | Export XML | `<REPORTNAME>Trial Balance</REPORTNAME>` |
| | **Sales Register** | Export XML | `<REPORTNAME>Sales Register</REPORTNAME>`, `SVFROMDATE`, `SVTODATE` |

---

## 4. Accounting Masters Specification (Ledger, Group)

### A. Ledger Master (`<LEDGER>`)
- **Create**:
  ```xml
  <TALLYMESSAGE xmlns:UDF="TallyUDF">
    <LEDGER NAME="Apex Traders" ACTION="Create">
      <NAME>Apex Traders</NAME>
      <PARENT>Sundry Debtors</PARENT>
      <OPENINGBALANCE>-15000.00</OPENINGBALANCE>
      <GSTIN>09AAAAA0000A1Z5</GSTIN>
    </LEDGER>
  </TALLYMESSAGE>
  ```
- **Alter**: Set `ACTION="Alter"`.
- **Delete**: Set `ACTION="Delete"`.

### B. Group Master (`<GROUP>`)
- **Create**:
  ```xml
  <TALLYMESSAGE xmlns:UDF="TallyUDF">
    <GROUP NAME="North Region Debtors" ACTION="Create">
      <NAME>North Region Debtors</NAME>
      <PARENT>Sundry Debtors</PARENT>
    </GROUP>
  </TALLYMESSAGE>
  ```
- **Alter**: Set `ACTION="Alter"`.
- **Delete**: Set `ACTION="Delete"`.

---

## 5. Inventory Masters Specification (Stock Item, Stock Group, Units)

### A. Stock Item Master (`<STOCKITEM>`)
- **Create**:
  ```xml
  <TALLYMESSAGE xmlns:UDF="TallyUDF">
    <STOCKITEM NAME="Widget Deluxe A1" ACTION="Create">
      <NAME>Widget Deluxe A1</NAME>
      <PARENT>Electronics</PARENT>
      <BASEUNITS>Nos</BASEUNITS>
      <OPENINGBALANCE>100 Nos</OPENINGBALANCE>
      <OPENINGVALUE>10000.00</OPENINGVALUE>
    </STOCKITEM>
  </TALLYMESSAGE>
  ```

### B. Stock Group Master (`<STOCKGROUP>`)
- **Create**:
  ```xml
  <TALLYMESSAGE xmlns:UDF="TallyUDF">
    <STOCKGROUP NAME="Electronics" ACTION="Create">
      <NAME>Electronics</NAME>
      <PARENT>Primary</PARENT>
    </STOCKGROUP>
  </TALLYMESSAGE>
  ```

### C. Units Master (`<UNIT>`)
- **Create**:
  ```xml
  <TALLYMESSAGE xmlns:UDF="TallyUDF">
    <UNIT NAME="Nos" ACTION="Create">
      <NAME>Nos</NAME>
      <ISSIMPLEUNIT>Yes</ISSIMPLEUNIT>
    </UNIT>
  </TALLYMESSAGE>
  ```

---

## 6. Transactions Specification (Payment, Receipt, Sales, Purchase)

### A. Payment Voucher (`<VOUCHER VOUCHERTYPENAME="Payment">`)
- **Create**:
  ```xml
  <VOUCHER DATE="20260401" VOUCHERTYPENAME="Payment" ACTION="Create">
    <DATE>20260401</DATE>
    <VOUCHERNUMBER>PAY-001</VOUCHERNUMBER>
    <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
    <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME>Supplier Account</LEDGERNAME>
      <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
      <AMOUNT>-5000.00</AMOUNT>
    </ALLLEDGERENTRIES.LIST>
    <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME>Bank Account</LEDGERNAME>
      <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
      <AMOUNT>5000.00</AMOUNT>
    </ALLLEDGERENTRIES.LIST>
  </VOUCHER>
  ```

### B. Receipt Voucher (`<VOUCHER VOUCHERTYPENAME="Receipt">`)
- **Create**:
  ```xml
  <VOUCHER DATE="20260401" VOUCHERTYPENAME="Receipt" ACTION="Create">
    <DATE>20260401</DATE>
    <VOUCHERNUMBER>RCT-001</VOUCHERNUMBER>
    <VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>
    <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME>Bank Account</LEDGERNAME>
      <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
      <AMOUNT>-10000.00</AMOUNT>
    </ALLLEDGERENTRIES.LIST>
    <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME>Apex Traders</LEDGERNAME>
      <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
      <AMOUNT>10000.00</AMOUNT>
    </ALLLEDGERENTRIES.LIST>
  </VOUCHER>
  ```

### C. Purchase Voucher (`<VOUCHER VOUCHERTYPENAME="Purchase">`)
- **Create**:
  ```xml
  <VOUCHER DATE="20260401" VOUCHERTYPENAME="Purchase" ACTION="Create">
    <DATE>20260401</DATE>
    <VOUCHERNUMBER>PUR-001</VOUCHERNUMBER>
    <VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
    <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
    <ISINVOICE>Yes</ISINVOICE>
    <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME>Supplier Account</LEDGERNAME>
      <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
      <AMOUNT>11800.00</AMOUNT>
    </ALLLEDGERENTRIES.LIST>
    <ALLINVENTORYENTRIES.LIST>
      <STOCKITEMNAME>Widget Deluxe A1</STOCKITEMNAME>
      <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
      <RATE>100.00/nos</RATE>
      <AMOUNT>-10000.00</AMOUNT>
      <ACTUALQTY>100 nos</ACTUALQTY>
      <BILLEDQTY>100 nos</BILLEDQTY>
    </ALLINVENTORYENTRIES.LIST>
  </VOUCHER>
  ```

---

## 7. Reports Specification (Trial Balance & Sales Register)

### A. Trial Balance Report Export Request
```xml
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export Data</TALLYREQUEST>
    <TYPE>Data</TYPE>
    <ID>Trial Balance</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
        <SVCURRENTCOMPANY>Sneh Distributors</SVCURRENTCOMPANY>
      </STATICVARIABLES>
    </DESC>
  </BODY>
</ENVELOPE>
```

### B. Sales Register Export Request
```xml
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export Data</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>SalesRegisterCollection</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
        <SVCURRENTCOMPANY>Sneh Distributors</SVCURRENTCOMPANY>
        <SVFROMDATE>20260401</SVFROMDATE>
        <SVTODATE>20260430</SVTODATE>
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="SalesRegisterCollection">
            <TYPE>Voucher</TYPE>
            <FETCH>DATE, VOUCHERNUMBER, VOUCHERTYPENAME, PARTYNAME, PARTYLEDGERNAME, AMOUNT, NARRATION, GSTIN</FETCH>
            <FILTER>IsSalesFilter</FILTER>
          </COLLECTION>
          <SYSTEM TYPE="Formulae" NAME="IsSalesFilter">$$IsSales:$VoucherTypeName</SYSTEM>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>
```

---

## 8. Pulling Sales/Purchase Registers & Financial Reports
(Detailed export filters with date variables `SVFROMDATE` & `SVTODATE` as specified in Section 4).

---

## 9. Handling Empty/Null Fields in Tally Response XML

When querying vouchers or registers from Tally Prime, optional fields (such as `NARRATION`, `GSTIN`, `WEBSITE`, `TELEPHONE`, or `BATCHNAME`) may be blank or absent in the XML response.

### Defensive XML Parser Pattern (Python Example)
```python
def get_xml_text(element, tag: str, default: str = "") -> str:
    """Safely extracts text content from XML tags, handling empty or missing elements."""
    child = element.find(tag)
    if child is not None and child.text is not None:
        return child.text.strip()
    return default
```

---

## 10. Understanding Tally XML Tags Dictionary
(Standard `<ENVELOPE>`, `<HEADER>`, `<BODY>`, `<TALLYREQUEST>` hierarchy).

---

## 11. Company Profile Master Specification

```xml
<ENVELOPE>
  <HEADER>
    <TALLYREQUEST>Import Data</TALLYREQUEST>
  </HEADER>
  <BODY>
    <IMPORTDATA>
      <REQUESTDESC>
        <REPORTNAME>All Masters</REPORTNAME>
        <STATICVARIABLES>
          <SVCURRENTCOMPANY>Sneh Distributors</SVCURRENTCOMPANY>
        </STATICVARIABLES>
      </REQUESTDESC>
      <REQUESTDATA>
        <TALLYMESSAGE xmlns:UDF="TallyUDF">
          <COMPANY NAME="Sneh Distributors" ACTION="Alter">
            <NAME>Sneh Distributors</NAME>
            <STATENAME>Uttar Pradesh</STATENAME>
            <COUNTRYNAME>India</COUNTRYNAME>
            <PINCODE>250004</PINCODE>
            <BASICCOMPANYPHONE>8979921514</BASICCOMPANYPHONE>
            <BASICCOMPANYMOBILE>8384854172</BASICCOMPANYMOBILE>
            <BASICCOMPANYEMAIL>sneh.distributor@gmail.com</BASICCOMPANYEMAIL>
            <WEBSITE>https://tally-web-gamma.vercel.app/</WEBSITE>
            <ADDRESS.LIST>
              <ADDRESS>43, Sector -7</ADDRESS>
              <ADDRESS>shastri nagar, meerut</ADDRESS>
            </ADDRESS.LIST>
          </COMPANY>
        </TALLYMESSAGE>
      </REQUESTDATA>
    </IMPORTDATA>
  </BODY>
</ENVELOPE>
```

---

## 12. Inventory, Godown & Batch Allocations
(Detailed `<ALLINVENTORYENTRIES.LIST>` and `<BATCHALLOCATIONS.LIST>` schemas).

---

## 13. User Defined Fields (UDF) & Custom Namespaces
(`xmlns:UDF="TallyUDF"` custom tag binding).

---

## 14. TDL Architecture & Language Components
(`Report` $\rightarrow$ `Form` $\rightarrow$ `Part` $\rightarrow$ `Line` $\rightarrow$ `Field`).

---

## 15. TDL Language Reference: Symbols, Data Types, Procedural Logic & Customization
(Symbols, prefixes, procedural functions, and form overrides).

---

## 16. TDL Developer FAQ & Debugging Guide
(`$$DebugLog`, SQL Stored Procedures, QR code generation).

---

## 17. Voucher Numbering Methods, Series & GST Compliance
(Automatic, Retain Original No., Multi-user Auto, GST series).

---

## 18. Handling Duplicate or Incorrect Voucher Numbers
(Resolving duplicate voucher number collisions).

---

## 19. ODBC & Advanced TDL Capabilities
(ODBC Server/Client SQL queries, Release 5.0+ Dashboard tiles, WhatsApp & e-Invoicing).

---

## 20. Developer Troubleshooting & Known Gotchas Cheat Sheet

| Issue | Root Cause | Solution |
| :--- | :--- | :--- |
| **Company Alteration returns `<STATUS>0</STATUS>`** | Missing `<IMPORTDATA><REQUESTDESC>` wrapper | Wrap XML in `<IMPORTDATA><REQUESTDESC><REPORTNAME>All Masters</REPORTNAME>...` |
| **MySQL Data Error 1265** | `sync_queue.record_type` set to `ENUM('Ledger','Voucher')` | Execute `ALTER TABLE tally_portal.sync_queue MODIFY COLUMN record_type VARCHAR(50) NOT NULL;` |
| **Frontend 401 Unauthorized** | Using `localStorage.getItem('token')` | Change to `localStorage.getItem('mytally_token')` |
| **UnboundLocalError in Python** | Inner import inside a loop hides global symbol | Move imports to the top of the file / function |
| **Tally Date Parsing Failure** | Format mismatch (`YYYY-MM-DD` vs `YYYYMMDD`) | Parse with `datetime.strptime(date_str, "%Y%m%d").date()` |
| **Multi-Company Context Mismatch** | Header `X-Company-ID` not forwarded | Include `X-Company-ID` header on all API requests |
| **Inventory Voucher Import Fail** | Missing `<PERSISTEDVIEW>` or `<ISINVOICE>` | Add `<PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>` and `<ISINVOICE>Yes</ISINVOICE>` |
